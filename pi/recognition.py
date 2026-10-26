"""YuNet detection + SFace embedding gallery, never cloud face identification."""
import json
import threading
import tempfile
from pathlib import Path
import cv2
import numpy as np

class Recognizer:
    gallery_name='gallery.json'
    model_name='sface'
    def __init__(self, folder, threshold=.45):
        self.folder=Path(folder); self.threshold=threshold; self.lock=threading.RLock()
        self.detector=None; self.recognizer=None; self.gallery=[]
        gallery=self.folder/self.gallery_name
        if gallery.exists(): self.gallery=json.loads(gallery.read_text())

    def load(self):
        if self.detector is None:
            self.detector=cv2.FaceDetectorYN.create(str(self.folder/'face_detection_yunet_2023mar.onnx'),'',(320,320),.85,.3,5000)
            self.recognizer=cv2.FaceRecognizerSF.create(str(self.folder/'face_recognition_sface_2021dec.onnx'),'')

    def features(self, raw):
        self.load()
        image=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None: raise ValueError('Invalid enrollment image')
        height,width=image.shape[:2]
        scale=min(1,1280/max(height,width))
        if scale<1: image=cv2.resize(image,(int(width*scale),int(height*scale)))
        self.detector.setInputSize((image.shape[1],image.shape[0]))
        _,faces=self.detector.detect(image)
        return [] if faces is None else [self.recognizer.feature(self.recognizer.alignCrop(image,face)).flatten() for face in faces]

    def train(self, persons, download):
        gallery=[]; skipped=[]
        # Commit only after every referenced image has downloaded successfully.
        with tempfile.TemporaryDirectory(dir=self.folder) as temporary:
          images=[]
          for person in persons:
            for path in person.get('images',[]):
                file=Path(temporary)/str(len(images));file.write_bytes(download(path));images.append((person,path,file))
          with self.lock:
            for person,path,file in images:
                features=self.features(file.read_bytes())
                if len(features)!=1:
                    skipped.append(dict(person=person['name'],image=path,reason='Expected exactly one face'))
                    continue
                vector=self.prepare_vector(features[0])
                gallery.append(dict(id=person['id'],embedding=vector.tolist()))
            if persons and not gallery: raise ValueError('No usable faces; previous gallery kept. Use single-face photos.')
            target=self.folder/self.gallery_name; temp=target.with_suffix('.tmp')
            temp.write_text(json.dumps(gallery)); temp.replace(target); self.gallery=gallery
        return dict(embeddings=len(gallery),persons=len(set(x['id'] for x in gallery)),skipped=skipped)

    def identify(self, raw, persons):
        with self.lock:
            if not self.gallery: return []
            available={p['id']:p for p in persons}; found=[]
            for feature in self.features(raw):
                vector=self.prepare_vector(feature)
                scores={}
                for item in self.gallery:
                    if item['id'] in available:
                        score=self.compare(vector,np.array(item['embedding']))
                        scores[item['id']]=max(score,scores.get(item['id'],-1))
                ranked=sorted(scores.items(),key=lambda item:item[1],reverse=True)
                if not ranked or ranked[0][1]<self.threshold: continue
                if len(ranked)>1 and ranked[0][1]-ranked[1][1]<.06: continue
                pid,score=ranked[0]; p=available[pid]
                if not any(f['id']==pid for f in found): found.append({k:p.get(k,'') for k in ['id','name','relation','note']}|{self.score_label:round(self.present_score(score),3),'model':self.model_name})
            return found

    score_label='similarity'
    def prepare_vector(self,feature):
        return feature/(np.linalg.norm(feature)+1e-12)
    def compare(self,a,b):
        return float(np.dot(a,b))
    def present_score(self,score):
        return score

class DlibRecognizer(Recognizer):
    """dlib's 128D face descriptor and HOG detector, with a separate gallery."""
    gallery_name='dlib-gallery.json'
    model_name='dlib'
    score_label='distance'
    def __init__(self,folder,threshold=.55):
        super().__init__(folder,-threshold)
        self.predictor=None;self.encoder=None

    def load(self):
        if self.detector is None:
            try: import dlib
            except ImportError as exc: raise RuntimeError('dlib is not installed on the Pi') from exc
            self.detector=dlib.get_frontal_face_detector()
            self.predictor=dlib.shape_predictor(str(self.folder/'shape_predictor_5_face_landmarks.dat'))
            self.encoder=dlib.face_recognition_model_v1(str(self.folder/'dlib_face_recognition_resnet_model_v1.dat'))

    def train(self,persons,download):
        self.load()
        return super().train(persons,download)

    def features(self,raw):
        self.load()
        from PIL import Image,ImageOps
        import io
        with Image.open(io.BytesIO(raw)) as source:
            image=ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((1280,1280))
            pixels=np.ascontiguousarray(np.asarray(image,dtype=np.uint8))
        faces=self.detector(pixels,1)
        return [np.asarray(self.encoder.compute_face_descriptor(pixels,self.predictor(pixels,face)),dtype=np.float64) for face in faces]

    def prepare_vector(self,feature):
        return feature
    def compare(self,a,b):
        return -float(np.linalg.norm(a-b))
    def present_score(self,score):
        return -score
