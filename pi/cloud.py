import json
import time
import base64
import threading
from pathlib import Path
import requests

class Cloud:
    def __init__(self, config):
        self.config=config; self.token=None; self.expires=0; self.lock=threading.RLock()
    def headers(self):
        with self.lock:
            if time.time()>self.expires-60:
                r=requests.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',params={'key':self.config['firebaseApiKey']},json={'email':self.config['deviceEmail'],'password':self.config['devicePassword'],'returnSecureToken':True},timeout=20)
                r.raise_for_status(); data=r.json(); self.token=data['idToken']; self.expires=time.time()+int(data['expiresIn'])
            return {'Authorization':'Bearer '+self.token,'X-Device-ID':self.config['deviceId']}
    def api(self,path,data=None):
        r=requests.request('GET' if data is None else 'POST',self.config['apiBase'].rstrip('/')+'/api/'+path,headers=self.headers(),json=data,timeout=30)
        r.raise_for_status(); return r.json()
    def download(self,path):
        r=requests.get(self.config['apiBase'].rstrip('/')+'/api/media',params={'path':path},headers=self.headers(),timeout=30)
        r.raise_for_status(); return r.content
    def upload(self,jpeg):
        return self.api('media',{'kind':'snapshot','mime':'image/jpeg','data':base64.b64encode(jpeg).decode()})['path']
