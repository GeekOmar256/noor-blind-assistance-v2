"""One-time provisioning using this workstation's gcloud login. Prints no secrets."""
import json
import secrets
import subprocess
from pathlib import Path
import requests
import firebase_admin
from firebase_admin import auth, credentials, firestore
from google.oauth2.credentials import Credentials

PROJECT='alzheimer-g3qi6e'
BASE=Path(__file__).parents[1]

class Workstation(credentials.Base):
    def get_credential(self):
        token=subprocess.run(['gcloud.cmd','auth','print-access-token'],capture_output=True,text=True,check=True).stdout.strip()
        return Credentials(token=token,quota_project_id=PROJECT)

def main():
    cred=Workstation()
    firebase_admin.initialize_app(cred,options={'projectId':PROJECT})
    api_key='AIzaSyCeElbXVC3K49Xr7IZuC02JmL9DIPUqh0k'
    email='cargiver@gmail.com';password=None
    try:owner=auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        password=secrets.token_urlsafe(20);owner=auth.create_user(email=email,password=password)
    device_email='blind-pi@devices.alzheimer-g3qi6e.invalid'
    device_password=secrets.token_urlsafe(36)
    try:
        device=auth.get_user_by_email(device_email)
        # Do not rotate credentials when re-running an already provisioned install.
        if (BASE/'pi/config.json').exists(): device_password=json.loads((BASE/'pi/config.json').read_text())['devicePassword']
        else: auth.update_user(device.uid,password=device_password)
    except auth.UserNotFoundError:device=auth.create_user(email=device_email,password=device_password)
    firestore.client().collection('noor_devices').document('blind-pi').set({'ownerUid':owner.uid,'deviceUid':device.uid},merge=True)
    config={'apiBase':'https://alzheimer-noor.web.app','firebaseApiKey':api_key,'deviceId':'blind-pi','deviceEmail':device_email,'devicePassword':device_password,'camera':'auto','rotate':0,'model':'gpt-4o-mini','faceThreshold':.45}
    (BASE/'pi/config.json').write_text(json.dumps(config,indent=2))
    if password:
        (BASE/'LOCAL_ACCESS.txt').write_text('Noor caregiver access\nURL: https://alzheimer-noor.web.app\nEmail: '+email+'\nInitial password: '+password+'\nDevice ID: blind-pi\nKeep this file private. Use a password reset to set your own password.\n')
    else:
        print('Caregiver already exists; its password was preserved.')
    print('Caregiver paired and private Pi config written. New-account login is in LOCAL_ACCESS.txt, if created.')
if __name__=='__main__':main()
