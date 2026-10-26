import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

BASE=Path(__file__).parents[1]
sys.path.insert(0,str(BASE/'pi'));sys.path.insert(0,str(BASE/'functions'))
from recognition import Recognizer,DlibRecognizer
from service import Service
import api

class RecognitionTests(unittest.TestCase):
    def test_models_load_and_blank_is_unknown(self):
        model_dir=BASE/'pi/models'
        if not all((model_dir/name).is_file() for name in ('face_detection_yunet_2023mar.onnx','face_recognition_sface_2021dec.onnx')):
            self.skipTest('Download the SFace and YuNet models to run this integration test')
        from PIL import Image
        raw=io.BytesIO();Image.new('RGB',(320,320),'white').save(raw,format='JPEG')
        r=Recognizer(BASE/'pi/models');self.assertEqual(r.features(raw.getvalue()),[])
    def test_multiple_images_and_atomic_training(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Recognizer(directory);people=[{'id':'one','name':'Person','images':['a','b','c']}]
            r.features=lambda raw:[np.array([1.,0.,0.])]
            report=r.train(people,lambda path:b'image')
            self.assertEqual(report['embeddings'],3);self.assertEqual(len(r.gallery),3)
            def fail(path):raise ConnectionError('offline')
            with self.assertRaises(ConnectionError):r.train(people,fail)
            self.assertEqual(len(Recognizer(directory).gallery),3)
    def test_ambiguous_and_deleted_people_stay_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Recognizer(directory);r.features=lambda raw:[np.array([1.,0.])]
            r.gallery=[{'id':'a','embedding':[1.,0.]},{'id':'b','embedding':[.99,.01]}]
            people=[{'id':'a','name':'A'},{'id':'b','name':'B'}]
            self.assertEqual(r.identify(b'',people),[])
            self.assertEqual(r.identify(b'',[]),[])
            self.assertEqual(r.identify(b'',people[:1])[0]['name'],'A')
    def test_empty_retraining_clears_gallery(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Recognizer(directory);r.gallery=[{'id':'deleted','embedding':[1.]}]
            r.train([],lambda p:b'');self.assertEqual(r.gallery,[])
    def test_dlib_uses_separate_gallery_and_distance(self):
        with tempfile.TemporaryDirectory() as directory:
            sface=Recognizer(directory); dlib=DlibRecognizer(directory)
            dlib.load=lambda:None
            dlib.features=lambda raw:[np.array([.1,.2,.3])]
            people=[{'id':'one','name':'Known','images':['a','b']}]
            dlib.train(people,lambda path:b'image')
            self.assertFalse((Path(directory)/'gallery.json').exists())
            self.assertEqual(len(json.loads((Path(directory)/'dlib-gallery.json').read_text())),2)
            self.assertEqual(dlib.identify(b'',people)[0]['model'],'dlib')
            self.assertEqual(sface.gallery,[])

class ServiceTests(unittest.TestCase):
    def test_journal_prevents_duplicate_playback_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            s=Service({'dataDir':directory});s.ack('reminders','one','done','Played')
            restarted=Service({'dataDir':directory});restarted.enqueue('one',{'type':'reminder'},'reminders')
            self.assertTrue(restarted.jobs.empty());self.assertEqual(restarted.acks['reminders/one']['state'],'done')
    def test_interrupted_playback_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            s=Service({'dataDir':directory});s.ack('commands','one','running')
            restarted=Service({'dataDir':directory});self.assertEqual(restarted.completed['commands/one']['state'],'failed')
    def test_queue_coalesces_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            s=Service({'dataDir':directory});s.enqueue('one',{'type':'capture'});s.enqueue('one',{'type':'capture'});self.assertEqual(s.jobs.qsize(),1)
    def test_disabled_scene_does_not_contact_ai(self):
        with tempfile.TemporaryDirectory() as directory:
            s=Service({'dataDir':directory});s.update_setting('sceneDescription',False)
            with self.assertRaisesRegex(ValueError,'disabled'):s.analyse(b'not a camera image')

class APITests(unittest.TestCase):
    def setUp(self):self.client=api.app.test_client()
    def test_missing_device_id_rejected(self):
        response=self.client.get('/api/state');self.assertEqual(response.status_code,400)
    def test_cross_device_access_rejected(self):
        with patch('api.auth.verify_id_token',return_value={'uid':'stranger'}),patch('api.firestore.client') as client:
            client.return_value.collection.return_value.document.return_value.get.return_value.to_dict.return_value={'ownerUid':'owner','deviceUid':'pi'}
            r=self.client.get('/api/state',headers={'X-Device-ID':'blind-pi','Authorization':'Bearer abc'});self.assertEqual(r.status_code,403)
    def test_device_cannot_edit_medical_profile(self):
        with patch('api.root',return_value=(object(),'device')):
            self.assertEqual(self.client.post('/api/profile',json={'medical':'test'}).status_code,403)
    def test_reminder_requires_aware_future_time(self):
        with patch('api.root',return_value=(object(),'caregiver')):
            self.assertEqual(self.client.post('/api/reminders',json={'dueAt':'2020-01-01T12:00:00+03:00','text':'test'}).status_code,400)
            self.assertEqual(self.client.post('/api/reminders',json={'dueAt':'2099-01-01T12:00:00','text':'test'}).status_code,400)
    def test_settings_validate_types_and_voice(self):
        with patch('api.root',return_value=(object(),'caregiver')):
            for data in [{'faceRecognition':'true'},{'sceneDescription':'false'},{'faceModel':'invalid'},{'voice':'invalid'},{'language':'invalid'},{'ownerUid':'injected'}]:
                self.assertEqual(self.client.post('/api/settings',json=data).status_code,400)
    def test_media_access_scope(self):
        class Ref:path='noor_devices/paired'
        with patch('api.root',return_value=(Ref(),'caregiver')):
            self.assertEqual(self.client.get('/api/media?path=noor_devices/other/media/a').status_code,403)
    def test_capture_can_enroll_existing_person_and_queue_training(self):
        from unittest.mock import MagicMock
        ref=MagicMock();ref.path='noor_devices/paired';ref.get.return_value.to_dict.return_value={'snapshot':{'media':ref.path+'/media/photo'}}
        person=ref.collection.return_value.document.return_value;person.get.return_value.exists=True;person.id='ab'*16
        with patch('api.root',return_value=(ref,'caregiver')),patch('api.storage.bucket') as bucket,patch('api.firestore.client') as db:
            bucket.return_value.get_blob.return_value.content_type='image/jpeg'
            r=self.client.post('/api/snapshot/enroll',json={'personId':person.id})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json['personId'],person.id)
            self.assertTrue(db.return_value.batch.return_value.update.called)
            self.assertTrue(bucket.return_value.copy_blob.called)
            self.assertTrue(db.return_value.batch.return_value.commit.called)
    def test_capture_enrollment_requires_real_snapshot(self):
        from unittest.mock import MagicMock
        ref=MagicMock();ref.path='noor_devices/paired';ref.get.return_value.to_dict.return_value={}
        with patch('api.root',return_value=(ref,'caregiver')):
            self.assertEqual(self.client.post('/api/snapshot/enroll',json={'newPerson':{'name':'A'}}).status_code,400)

if __name__=='__main__':unittest.main(verbosity=2)
