"""Run with Google Application Default Credentials, never ship admin keys to Pi."""
import argparse
import getpass
import secrets
import json
from pathlib import Path
import firebase_admin
from firebase_admin import auth, firestore

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--caregiver-email',required=True);parser.add_argument('--device-id',default='blind-pi');parser.add_argument('--api-base',required=True);parser.add_argument('--web-api-key',required=True);args=parser.parse_args()
    firebase_admin.initialize_app(options={'projectId':args.project})
    try:owner=auth.get_user_by_email(args.caregiver_email)
    except auth.UserNotFoundError:
        owner=auth.create_user(email=args.caregiver_email,password=getpass.getpass('New caregiver password (at least 12 characters): '))
    email=f'{args.device_id}@devices.{args.project}.invalid';password=secrets.token_urlsafe(36)
    try:
        device=auth.get_user_by_email(email);auth.update_user(device.uid,password=password)
    except auth.UserNotFoundError:device=auth.create_user(email=email,password=password)
    firestore.client().collection('noor_devices').document(args.device_id).set({'ownerUid':owner.uid,'deviceUid':device.uid},merge=True)
    config={'apiBase':args.api_base,'firebaseApiKey':args.web_api_key,'deviceId':args.device_id,'deviceEmail':email,'devicePassword':password,'camera':'auto','rotate':0,'model':'gpt-4o-mini','faceThreshold':.45}
    output=Path(__file__).parents[1]/'pi/config.json';output.write_text(json.dumps(config,indent=2));output.chmod(0o600)
    print('Paired. Private Pi configuration written to',output)
if __name__=='__main__':main()
