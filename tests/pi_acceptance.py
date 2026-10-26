"""Run against the paired Pi: remote screen, MP4 audio, and spoken reminder."""
import base64
import json
import math
import os
import re
import sys
import time
from datetime import datetime,timezone,timedelta
from pathlib import Path
import requests
import paramiko

BASE=Path(__file__).parents[1]
sys.path.insert(0,str(BASE/'pi'))
from cloud import Cloud

def main():
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    config=json.loads((BASE/'pi/config.json').read_text());cloud=Cloud(config)
    password=re.search(r'Initial password: (.*)',(BASE/'LOCAL_ACCESS.txt').read_text()).group(1)
    r=requests.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',params={'key':config['firebaseApiKey']},json={'email':'cargiver@gmail.com','password':password,'returnSecureToken':True},timeout=20)
    r.raise_for_status();token=r.json()['idToken']
    def post(path,data):
        r=requests.post(config['apiBase']+'/api/'+path,headers={'Authorization':'Bearer '+token,'X-Device-ID':config['deviceId']},json=data,timeout=30);r.raise_for_status();return r.json()
    def wait_for(predicate,seconds=45):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            state=cloud.api('state')
            if predicate(state):return state
            time.sleep(2)
        raise TimeoutError('Pi did not acknowledge within deadline')
    for visible in [False,True]:
        post('settings',{'uiVisible':visible})
        wait_for(lambda state:state.get('status',{}).get('uiVisible') is visible)
        print('PASS: caregiver screen '+('open' if visible else 'close'),flush=True)
    ssh=paramiko.SSHClient();ssh.load_host_keys(str(Path.home()/'.ssh/known_hosts'));ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect('192.168.1.10',username='abc',password=os.environ['NOOR_SSH_PASSWORD'],look_for_keys=False,allow_agent=False,timeout=10)
    try:
        stdin,stdout,stderr=ssh.exec_command("ffmpeg -v error -f lavfi -i 'sine=frequency=440:sample_rate=24000:duration=0.5' -c:a aac -f mp4 -movflags frag_keyframe+empty_moov pipe:1",timeout=15)
        raw=stdout.read();error=stderr.read()
        if stdout.channel.recv_exit_status():raise RuntimeError('Could not generate AAC test audio')
    finally:ssh.close()
    path=post('media',{'kind':'audio','mime':'audio/mp4','data':base64.b64encode(raw).decode()})['path']
    command=post('commands',{'type':'voice','media':path})['id']
    state=wait_for(lambda state:any(c['id']==command and c['state'] in ['done','failed'] for c in state['commands']),60)
    result=next(c for c in state['commands'] if c['id']==command)
    if result['state']!='done':raise RuntimeError('Pi MP4 playback failed: '+result.get('message',''))
    print('PASS: uploaded MP4/AAC voice-note transport, Pi decoding, and audio playback',flush=True)
    reminder=post('reminders',{'text':'تم تشغيل نظام نور بنجاح. هذا تذكير تجريبي.','dueAt':(datetime.now(timezone.utc)+timedelta(seconds=55)).isoformat()})['id']
    print('Spoken reminder scheduled; waiting for Pi playback…',flush=True)
    state=wait_for(lambda state:any(r['id']==reminder and r['state'] in ['done','failed'] for r in state['reminders']),110)
    result=next(r for r in state['reminders'] if r['id']==reminder)
    if result['state']!='done':raise RuntimeError('Pi spoken reminder failed: '+result.get('message',''))
    print('PASS: reminder sync, scheduled execution, AI speech generation and Pi playback',flush=True)

if __name__=='__main__':main()
