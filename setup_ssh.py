import getopt
import os
import random
import re
import subprocess
import sys


class SSHConfig(object):
    def __init__(self, argv, port_range_min=2200, port_range_max=2299):
        if port_range_max < port_range_min:
            raise Exception
        self.username = 'admin'
        self.sshd_config_tpl_path = 'sshd_config.tpl'
        self.sshd_config_path = '/etc/ssh/sshd_config'
        self.root_authorized_keys_path = '/root/.ssh/authorized_keys'
        self.argv = argv
        self.port_range_min = port_range_min
        self.port_range_max = port_range_max
        self.port_range = range(self.port_range_min, self.port_range_max)
        self.supported_opt_short = 'p:u:'
        self.supported_opt_long = ['port=', 'user=']
        ret = self.__get_opt__(self.argv, 'p', 'port', self.__parse_port_arg__)
        self.ssh_port = random.choice(self.port_range) if ret is None else ret

        ret = self.__get_opt__(self.argv, 'u', 'user', self.__parse_user_arg__)
        self.username = self.username if ret is None else ret
        self.is_success = False
        print("SSH Port: {0}".format(self.ssh_port))
        print("Admin username: {0}\n".format(self.username))

        print("====SETTING UP NEW SYSTEM USER====")
        self.__setup_user_profile__(self.username)
        print("OK\n")
        print("====SETTING UP FIREWALL====")
        self.__setup_firewall__()
        print("OK\n")
        print("====SETTING UP SSH DAEMON====")
        self.__setup_sshd__()
        print("OK\n")
        print("====CLEANING ROOT AUTHORIZED KEYS====")
        self.__linux_clean_root_authorized_keys__()
        print("OK\n")
        print("====DEACTIVATING ROOT====")
        self.__linux_deactivate_root__()
        print("OK\n")
        self.is_success = True

    def __setup_sshd__(self):
        self.__generate_sshd_config__()
        self.__linux_restart_sshd__()

    def __setup_user_profile__(self, user):
        self.__linux_adduser__(user)
        self.__linux_usermod__(user)
        self.__linux_passwd__(user)
        self.__linux_add_authorized_keys__(user)

    def __setup_firewall__(self):
        self.__firewall_add_port__(self.ssh_port)
        self.__firewall_remove_port__(22)
        self.__firewall_reload__()

    def __linux_restart_sshd__(self):
        ret = subprocess.check_call("systemctl restart sshd", shell=True)
        if ret:
            raise Exception

    def __linux_adduser__(self, user):
        ret = subprocess.check_call("adduser {0}".format(user), shell=True)
        if ret:
            print("Error creating a new user: {0}".format(user))
            raise Exception
        print("Created new linux user: {0}".format(user))

    def __linux_usermod__(self, user):
        ret = subprocess.check_call("usermod -aG wheel {0}".format(user), shell=True)
        if ret:
            print("Admin assignment failed for user: {0}".format(user))
            raise Exception
        print("Admin assignment succeed for user: {0}".format(user))

    def __linux_passwd__(self, user):
        ret = subprocess.check_call("passwd {0}".format(user), shell=True)
        if ret:
            raise Exception

    def __linux_add_authorized_keys__(self, user):
        ret = subprocess.check_call("mkdir -p /home/{0}/.ssh".format(user), shell=True)
        if ret:
            raise Exception
        ret = subprocess.check_call("chmod 0700 /home/{0}/.ssh".format(user), shell=True)
        if ret:
            raise Exception
        ret = subprocess.check_call("cp authorized_keys /home/{0}/.ssh/authorized_keys".format(user), shell=True)
        if ret:
            raise Exception
        ret = subprocess.check_call("chmod 0600 /home/{0}/.ssh/authorized_keys".format(user), shell=True)
        if ret:
            raise Exception
        ret = subprocess.check_call("chown {0} /home/{0}/.ssh".format(user), shell=True)
        if ret:
            raise Exception
        ret = subprocess.check_call("chown {0} /home/{0}/.ssh/authorized_keys".format(user), shell=True)
        if ret:
            raise Exception
        print("Public keys added")

    def __linux_deactivate_root__(self):
        ret = subprocess.check_call("passwd -l root", shell=True)
        if ret:
            raise Exception

    def __linux_clean_root_authorized_keys__(self):
        with open(self.root_authorized_keys_path, mode='w') as fo:
            fo.write('')

    def __firewall_add_port__(self, port):
        ret = subprocess.check_call("firewall-cmd --zone=public --add-port={0}/tcp --permanent".format(port),
                                    shell=True)
        if ret:
            raise Exception

    def __firewall_remove_port__(self, port):
        ret = subprocess.check_call("firewall-cmd --zone=public --remove-port={0}/tcp --permanent".format(port),
                                    shell=True)
        if ret:
            raise Exception

    def __firewall_reload__(self):
        ret = subprocess.check_call("firewall-cmd --reload".format(self.ssh_port),
                                    shell=True)
        if ret:
            raise Exception

    def __get_opt__(self, argv, short_opt, long_opt, parse_opt_arg_funct):
        try:
            opts, args = getopt.getopt(argv, self.supported_opt_short, self.supported_opt_long)
            for opt, arg in opts:
                if opt in ('-{0}'.format(short_opt), '--{0}'.format(long_opt)):
                    retval = parse_opt_arg_funct(arg)
                    if retval:
                        return retval
                    else:
                        raise getopt.GetoptError
        except getopt.GetoptError:
            raise getopt.GetoptError
        return None

    def __parse_user_arg__(self, arg):
        arg_stripped = arg.strip()
        res = re.match(r"^[a-z0-9][-a-z0-9]*$", arg_stripped)
        if res:
            username = res.string
            if not username == 'root':
                return username
        print("Username is incorrect\n")
        return False

    def __parse_port_arg__(self, arg):
        try:
            value = int(arg)
            if value in self.port_range:
                return value
            else:
                raise ValueError
        except ValueError:
            print(ValueError)
            print("SSH Port should be in range({1},{2}), given: {0}\n"
                  .format(arg, self.port_range_min, self.port_range_max))
            return False
        except Exception:
            print(Exception)
            return False

    def __generate_sshd_config__(self):
        if not os.path.exists(self.sshd_config_tpl_path):
            print('ERROR: {0} is not exists'.format(self.sshd_config_tpl_path))
            raise Exception
        try:
            with open(self.sshd_config_tpl_path, mode='r') as ft:
                text = str(ft.read())
                text = re.sub('\$ALLOWUSERS', str(self.username), text)
                text = re.sub('\$PORT', str(self.ssh_port), text)
                with open(self.sshd_config_path, mode='w') as fo:
                    fo.write(text)
        except Exception as e:
            print(e)
            raise e


print("setup_ssh.py\n")
try:
    SSHConfig(sys.argv[1:])
    sys.exit(0)
except Exception:
    sys.exit(2)
