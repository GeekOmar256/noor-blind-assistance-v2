"""Workstation deployment helper. SSH password is read only from the environment."""
import argparse
import os
import shlex
import sys
from pathlib import Path
import paramiko

CODE_FILES = (
    'pi/app.py', 'pi/cloud.py', 'pi/core.py', 'pi/recognition.py',
    'pi/service.py', 'pi/download_models.py', 'pi/install.sh',
    'pi/install_dlib.sh', 'pi/requirements.txt',
)

def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['upload','exec'])
    parser.add_argument('command',nargs='?')
    args=parser.parse_args()
    client=paramiko.SSHClient()
    client.load_system_host_keys()
    known=Path.home()/'.ssh/known_hosts'
    if known.exists():client.load_host_keys(str(known))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    host=os.environ.get('NOOR_PI_HOST','abc.local')
    if host not in client.get_host_keys() and '192.168.1.10' in client.get_host_keys():
        # The Pi retains the same SSH identity after its Wi-Fi address changes.
        for algorithm,key in client.get_host_keys()['192.168.1.10'].items():
            client.get_host_keys().add(host,algorithm,key)
    client.connect(host,username='abc',password=os.environ['NOOR_SSH_PASSWORD'],look_for_keys=False,allow_agent=False,timeout=15)
    try:
        if args.action=='upload':
            sftp=client.open_sftp();remote='/home/abc/noor_v2'
            def mkdir(path):
                try:sftp.stat(path)
                except FileNotFoundError:sftp.mkdir(path)
            mkdir(remote);mkdir(remote+'/pi')
            source=Path(__file__).parents[1]
            if args.command:
                names=args.command.split(',')
                if not all(name in CODE_FILES for name in names):
                    raise ValueError('Only Pi runtime code files may be uploaded')
            else:
                names=CODE_FILES
            for relative in names:
                file=source/relative
                if not file.is_file():
                    raise FileNotFoundError(file)
                target=remote+'/'+relative
                sftp.put(str(file),target)
                sftp.chmod(target,0o755 if file.suffix=='.sh' else 0o644)
                print('Uploaded',relative,flush=True)
            sftp.close()
        else:
            stdin,stdout,stderr=client.exec_command(args.command,timeout=1800)
            stdin.close()
            channel=stdout.channel
            import time
            while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
                if channel.recv_ready():print(channel.recv(32768).decode(errors='replace'),end='',flush=True)
                if channel.recv_stderr_ready():print(channel.recv_stderr(32768).decode(errors='replace'),end='',flush=True)
                time.sleep(.1)
            raise SystemExit(channel.recv_exit_status())
    finally:client.close()

if __name__=='__main__':main()
