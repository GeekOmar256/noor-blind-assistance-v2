"""Cloud transport/security smoke test. Removes its own fixtures in finally."""
import base64
import io
import json
import re
import sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
import requests
from PIL import Image

BASE=Path(__file__).parents[1]
sys.path.insert(0,str(BASE/'deploy'))
from setup_local import Workstation,PROJECT
import firebase_admin
from firebase_admin import firestore,storage

def main():
    config=json.loads((BASE/'pi/config.json').read_text());url=config['apiBase'];key=config['firebaseApiKey']
    password=re.search(r'Initial password: (.*)',(BASE/'LOCAL_ACCESS.txt').read_text()).group(1)
    def login(email,password):
        r=requests.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',params={'key':key},json={'email':email,'password':password,'returnSecureToken':True},timeout=20);r.raise_for_status();return r.json()['idToken']
    tokens={'caregiver':login('cargiver@gmail.com',password),'device':login(config['deviceEmail'],config['devicePassword'])}
    def call(path,data=None,role='caregiver',method=None,device='blind-pi'):
        r=requests.request(method or ('GET' if data is None else 'POST'),url+'/api/'+path,headers={'Authorization':'Bearer '+tokens[role],'X-Device-ID':device},json=data,timeout=45);return r
    firebase_admin.initialize_app(Workstation(),options={'projectId':PROJECT,'storageBucket':'alzheimer-noor-private'})
    ref=firestore.client().collection('noor_devices').document('blind-pi');created=[];media=[]
    try:
        r=call('state');r.raise_for_status();assert r.json()['role']=='caregiver'
        assert call('state',device='another-device').status_code==403
        assert call('profile',{'medical':'test'},role='device').status_code==403
        assert call('device',{'status':{}},role='caregiver').status_code==403
        r=call('persons',{'name':'Cloud transport test','relation':'TEST FIXTURE','note':'Will be removed'});r.raise_for_status();pid=r.json()['id'];created.append(('persons',pid))
        image=io.BytesIO();Image.new('RGB',(64,64),'white').save(image,format='JPEG')
        r=call('media',{'kind':'image','personId':pid,'mime':'image/jpeg','data':base64.b64encode(image.getvalue()).decode()});r.raise_for_status();path=r.json()['path'];media.append(path)
        r=call('media?path='+requests.utils.quote(path,safe=''));r.raise_for_status();assert r.content==image.getvalue()
        public=requests.get('https://storage.googleapis.com/alzheimer-noor-private/'+path,timeout=20);assert public.status_code in [401,403]
        r=call('reminders',{'text':'Cloud transport fixture','dueAt':(datetime.now(timezone.utc)+timedelta(days=365)).isoformat()});r.raise_for_status();created.append(('reminders',r.json()['id']))
        r=call('commands',{'type':'capture'});r.raise_for_status();cid=r.json()['id'];created.append(('commands',cid))
        r=call('device',{'ack':{'collection':'commands','id':cid,'state':'done','message':'Transport test; no hardware capture'}},role='device');r.raise_for_status()
        r=call('state');r.raise_for_status();assert any(c['id']==cid and c['state']=='done' for c in r.json()['commands'])
        print('PASS: live sign-in, pairing, caregiver/device permissions, person+photo upload/download, private object access, reminder sync, command acknowledgement')
    finally:
        for collection,id in created:ref.collection(collection).document(id).delete()
        for path in media:storage.bucket().blob(path).delete()
        print('Live test fixtures removed')
if __name__=='__main__':main()
