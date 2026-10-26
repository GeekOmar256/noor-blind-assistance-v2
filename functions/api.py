"""Authenticated caregiver/device API. All object access stays server-side."""
import base64
import os
import re
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, Response
from firebase_admin import auth, firestore, storage

app = Flask(__name__, static_folder='public')
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
VOICES = ['alloy','ash','ballad','coral','echo','fable','nova','onyx','sage','shimmer','verse','marin','cedar']

def now():
    return datetime.now(timezone.utc).isoformat()

def defaults():
    return dict(language='ar', voice='marin', speech=True, faceRecognition=False,
                faceModel='sface', sceneDescription=True, theme='light', uiVisible=True)

def root():
    device = request.headers.get('X-Device-ID', '')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', device):
        raise ValueError('Invalid device ID')
    token = request.headers.get('Authorization', '').removeprefix('Bearer ')
    claims = auth.verify_id_token(token, check_revoked=True)
    ref = firestore.client().collection('noor_devices').document(device)
    info = ref.get().to_dict() or {}
    role = 'device' if claims['uid'] == info.get('deviceUid') else 'caregiver' if claims['uid'] == info.get('ownerUid') else None
    if not role:
        raise PermissionError('This account is not paired with this Pi')
    return ref, role

@app.errorhandler(Exception)
def error(exc):
    if isinstance(exc, PermissionError): return jsonify(error=str(exc)), 403
    if isinstance(exc, (ValueError, KeyError)): return jsonify(error=str(exc)), 400
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException): return jsonify(error=exc.description), exc.code
    if isinstance(exc, auth.InvalidIdTokenError): return jsonify(error='Sign in again'), 401
    app.logger.exception('API failure')
    return jsonify(error='Request failed; check server logs'), 500

@app.get('/')
def index(): return send_from_directory('public', 'index.html')

@app.get('/api/config')
def config():
    return jsonify(apiKey=os.getenv('WEB_API_KEY',''), projectId=os.getenv('GCLOUD_PROJECT',os.getenv('GOOGLE_CLOUD_PROJECT','')), timezone='Asia/Kuwait')

@app.get('/api/state')
def state():
    ref, role = root()
    info = ref.get().to_dict() or {}
    result = {key: info.get(key) for key in ['settings','profile','status','snapshot']}
    result['settings'] = {**defaults(), **(result['settings'] or {})}
    for name in ['persons','reminders','commands']:
        query = ref.collection(name)
        if name == 'commands': query = query.order_by('createdAt', direction=firestore.Query.DESCENDING).limit(60)
        items = {x.id:dict(x.to_dict(), id=x.id) for x in query.stream()}
        if name == 'commands':
            from google.cloud.firestore_v1.base_query import FieldFilter
            for x in ref.collection(name).where(filter=FieldFilter('state','==','pending')).stream():
                items[x.id] = dict(x.to_dict(),id=x.id)
        result[name] = list(items.values())
    result['role'] = role
    return jsonify(result)

@app.post('/api/settings')
def settings():
    ref, role = root()
    data = request.get_json()
    allowed = defaults()
    if set(data) - set(allowed): raise ValueError('Unknown setting')
    for key, value in data.items():
        if key in ['speech','faceRecognition','sceneDescription','uiVisible'] and type(value) is not bool: raise ValueError('Expected boolean')
        if key == 'faceModel' and value not in ['sface','dlib']: raise ValueError('Invalid face model')
        if key == 'language' and value not in ['ar','en']: raise ValueError('Invalid language')
        if key == 'voice' and value not in VOICES: raise ValueError('Invalid voice')
        if key == 'theme' and value not in ['light','dark']: raise ValueError('Invalid theme')
    ref.set({'settings': data}, merge=True)
    return jsonify(ok=True)

@app.post('/api/profile')
def profile():
    ref, role = root()
    if role != 'caregiver': raise PermissionError('Caregiver only')
    data = request.get_json()
    ref.set({'profile': {k: str(data.get(k,''))[:8000] for k in ['name','details','restrictions','requirements','medical']}}, merge=True)
    return jsonify(ok=True)

@app.route('/api/persons', methods=['POST'])
@app.route('/api/persons/<pid>', methods=['POST','DELETE'])
def persons(pid=None):
    ref, role = root()
    if role != 'caregiver': raise PermissionError('Caregiver only')
    if pid and not re.fullmatch(r'[a-f0-9]{32}',pid): raise ValueError('Invalid person ID')
    doc = ref.collection('persons').document(pid or uuid.uuid4().hex)
    if request.method == 'DELETE':
        old = doc.get().to_dict() or {}
        for media in old.get('images',[]):
            storage.bucket().blob(media).delete()
        doc.delete()
        return jsonify(ok=True)
    data = request.get_json()
    name = str(data.get('name','')).strip()
    if not name: raise ValueError('Name is required')
    doc.set({k: str(data.get(k,''))[:2000] for k in ['name','relation','note']}, merge=True)
    return jsonify(id=doc.id)

@app.post('/api/reminders')
def reminders():
    ref, role = root()
    if role != 'caregiver': raise PermissionError('Caregiver only')
    data = request.get_json()
    due = datetime.fromisoformat(data['dueAt'])
    if due.tzinfo is None or due <= datetime.now(timezone.utc): raise ValueError('Choose a future Kuwait date and time')
    text = str(data.get('text','')).strip()[:2000]
    if not text: raise ValueError('Reminder text required')
    doc = ref.collection('reminders').document()
    doc.set(dict(text=text,dueAt=due.astimezone(timezone.utc).isoformat(),state='pending',createdAt=now()))
    return jsonify(id=doc.id)

@app.post('/api/commands')
def commands():
    ref, role = root()
    if role != 'caregiver': raise PermissionError('Caregiver only')
    data = request.get_json()
    if data.get('type') not in ['capture','train','voice','analyse']: raise ValueError('Invalid command')
    media = data.get('media','')
    if data['type'] == 'voice' and not media.startswith(ref.path + '/media/'): raise ValueError('Upload audio first')
    doc = ref.collection('commands').document()
    doc.set(dict(type=data['type'],media=media,state='pending',createdAt=now()))
    return jsonify(id=doc.id)

@app.post('/api/snapshot/enroll')
def enroll_snapshot():
    ref, role = root()
    if role != 'caregiver': raise PermissionError('Caregiver only')
    data = request.get_json()
    snapshot = (ref.get().to_dict() or {}).get('snapshot') or {}
    path = snapshot.get('media','')
    if not path.startswith(ref.path+'/media/'): raise ValueError('Capture a photo from the Pi first')
    bucket = storage.bucket()
    blob = bucket.get_blob(path)
    if not blob or not (blob.content_type or '').startswith('image/'): raise ValueError('Captured photo is no longer available')
    pid = data.get('personId')
    if pid:
        if not isinstance(pid,str) or not re.fullmatch(r'[a-f0-9]{32}',pid): raise ValueError('Invalid person ID')
        person = ref.collection('persons').document(pid)
        if not person.get().exists: raise ValueError('Person no longer exists')
    else:
        details = data.get('newPerson') or {}
        name = str(details.get('name','')).strip()[:120]
        if not name: raise ValueError('Enter the new person’s name')
        person = ref.collection('persons').document(uuid.uuid4().hex)
    # Each enrolled profile owns a copy. Deleting one person must not delete
    # the current camera snapshot or another person's enrollment photo.
    enrolled_path = ref.path + '/media/' + uuid.uuid4().hex
    enrolled_blob = bucket.copy_blob(blob,bucket,enrolled_path)
    batch = firestore.client().batch()
    if pid:
        batch.update(person, {'images':firestore.ArrayUnion([enrolled_path]),'updatedAt':now()})
    else:
        batch.set(person, {'name':name,'relation':str(details.get('relation',''))[:120],
                           'note':str(details.get('note',''))[:2000],'images':[enrolled_path],'updatedAt':now()})
    command = ref.collection('commands').document()
    batch.set(command, {'type':'train','media':'','state':'pending','createdAt':now()})
    try: batch.commit()
    except Exception:
        enrolled_blob.delete()
        raise
    return jsonify(personId=person.id,trainingCommandId=command.id)

@app.post('/api/device')
def device_update():
    ref, role = root()
    if role != 'device': raise PermissionError('Device only')
    data = request.get_json()
    if 'status' in data: ref.set({'status': {**data['status'], 'lastSeen': now()}}, merge=True)
    if 'snapshot' in data:
        if not data['snapshot'].startswith(ref.path + '/media/'): raise ValueError('Invalid snapshot')
        ref.set({'snapshot': {'media':data['snapshot'],'capturedAt':now()}}, merge=True)
    if 'ack' in data:
        item = data['ack']
        if item['collection'] not in ['commands','reminders']: raise ValueError('Invalid acknowledgement')
        doc = ref.collection(item['collection']).document(item['id'])
        if item['state'] not in ['running','done','failed']: raise ValueError('Invalid state')
        doc.update(dict(state=item['state'], message=str(item.get('message',''))[:2000],updatedAt=now()))
    return jsonify(ok=True)

@app.route('/api/media', methods=['POST','GET'])
def media():
    ref, role = root()
    if request.method == 'GET':
        path = request.args.get('path','')
        if not path.startswith(ref.path+'/media/'): raise PermissionError('Invalid media path')
        blob = storage.bucket().blob(path)
        data = blob.download_as_bytes()
        return Response(data, content_type=blob.content_type or 'application/octet-stream', headers={'Cache-Control':'private, no-store'})
    data = request.get_json()
    kind = data.get('kind')
    if kind not in ['image','audio','snapshot']: raise ValueError('Invalid media kind')
    if role == 'device' and kind != 'snapshot': raise PermissionError('Device may upload snapshots only')
    if role == 'caregiver' and kind == 'snapshot': raise PermissionError('Pi captures snapshots')
    raw = base64.b64decode(data['data'], validate=True)
    if len(raw) > (8 if kind == 'audio' else 6)*1024*1024: raise ValueError('File too large')
    mime = data.get('mime','')
    if kind in ['image','snapshot']:
        import io
        from PIL import Image
        image = Image.open(io.BytesIO(raw))
        if max(image.size)>8192 or image.width*image.height>24000000: raise ValueError('Image resolution too large; resize below 24 megapixels')
        image.verify()
        if mime not in ['image/jpeg','image/png','image/webp']: raise ValueError('Use JPEG, PNG or WebP')
    elif mime.split(';')[0] not in ['audio/mp4','audio/mpeg','audio/wav','audio/x-wav','audio/webm','audio/ogg','audio/aac','audio/x-m4a','video/mp4']:
        raise ValueError('Unsupported audio type')
    path = ref.path + '/media/' + uuid.uuid4().hex
    storage.bucket().blob(path).upload_from_string(raw, content_type=mime)
    if kind == 'image':
        pid = data.get('personId','')
        doc = ref.collection('persons').document(pid)
        if not doc.get().exists: raise ValueError('Person no longer exists')
        doc.update({'images':firestore.ArrayUnion([path]),'updatedAt':now()})
    return jsonify(path=path)

@app.after_request
def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'microphone=(self)'
    return response
