import getpass
import socket
import sys
import threading
import traceback
from random import randrange

import paramiko
from paramiko.py3compat import input

# paramiko.util.log_to_file("ssh_secure_setup.log")

SSHD_CONFIG_TPL_PATH = "sshd_config.tpl"
SETUP_SSH_PY_PATH = "setup_ssh.py"
AUTHORIZED_KEYS_PATH = "authorized_keys"


def run_setup(ssh_host, ssh_port, ssh_user, ssh_pass):
    def writeall(chan):
        while True:
            data = chan.recv(256)
            if not data:
                sys.stdout.write("\r\n*** EOF ***\r\n\r\n")
                sys.stdout.flush()
                break
            msg = str(data, encoding='utf-8')
            sys.stdout.write(msg)
            sys.stdout.flush()

    # now, connect and use paramiko Transport to negotiate SSH2 across the connection
    try:
        t = paramiko.Transport((ssh_host, ssh_port))
        t.connect(
            hostkey=None,
            username=ssh_user,
            password=ssh_pass,
            gss_host=socket.getfqdn(ssh_host))
        sftp = paramiko.SFTPClient.from_transport(t)

        sftp.put(SETUP_SSH_PY_PATH, SETUP_SSH_PY_PATH)
        sftp.put(SSHD_CONFIG_TPL_PATH, SSHD_CONFIG_TPL_PATH)
        sftp.put(AUTHORIZED_KEYS_PATH, AUTHORIZED_KEYS_PATH)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(policy=paramiko.AutoAddPolicy)
        ssh.connect(hostname=ssh_host, port=ssh_port, username=ssh_user, password=ssh_pass)
        channel = ssh.invoke_shell()
        target_user = input('New admin name [admin]:') or "admin"
        target_port = input('New ssh port [2200-2299]:') or randrange(2200, 2299)
        writer = threading.Thread(target=writeall, args=(channel,))
        writer.start()
        channel.send(f"python setup_ssh.py -u {target_user} -p {target_port}\n")
        try:
            while True:
                d = sys.stdin.read(1)
                if not d:
                    break
                channel.send(d)
        except EOFError:
            # user hit ^Z or F6
            pass
        ssh.close()
        t.close()

    except Exception as e:
        print("*** Caught exception: %s: %s" % (e.__class__, e))
        traceback.print_exc()
        try:
            t.close()
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    ssh_user = ""
    ssh_port = 22
    if len(sys.argv) > 1:
        ssh_host = sys.argv[1]
    else:
        ssh_host = input("Hostname [user@example.com:22] > ")
    if ssh_host.find("@") >= 0:
        ssh_user, ssh_host = ssh_host.split("@")

    if len(ssh_host) == 0:
        print("*** Hostname required.")
        sys.exit(1)

    if ssh_host.find(":") >= 0:
        ssh_host, ssh_port_str = ssh_host.split(":")
        ssh_port = int(ssh_port_str)

    # get username
    if ssh_user == "":
        default_username = getpass.getuser()
        ssh_user = input("Username [%s]: " % default_username)
        if len(ssh_user) == 0:
            ssh_user = default_username
    ssh_pass = getpass.getpass("Password for %s@%s: " % (ssh_user, ssh_host))
    run_setup(ssh_host, ssh_port, ssh_user, ssh_pass)
