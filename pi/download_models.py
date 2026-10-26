"""Fetch official OpenCV Zoo models; atomic writes and ONNX parse validation."""
from pathlib import Path
import argparse
import bz2
import requests
import cv2

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--with-dlib',action='store_true')
    args=parser.parse_args()
    folder=Path(__file__).parent/'models';folder.mkdir(exist_ok=True)
    models={'face_detection_yunet_2023mar.onnx':'face_detection_yunet','face_recognition_sface_2021dec.onnx':'face_recognition_sface'}
    for name,component in models.items():
        target=folder/name
        if target.exists():continue
        url=f'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/{component}/{name}'
        with requests.get(url,stream=True,timeout=(10,180)) as r:
            r.raise_for_status();temp=target.with_suffix('.tmp')
            with temp.open('wb') as f:
                for chunk in r.iter_content(1024*1024):f.write(chunk)
        cv2.dnn.readNetFromONNX(str(temp));temp.replace(target);print('Downloaded',name)
    if args.with_dlib:
        import dlib
        for name in ['shape_predictor_5_face_landmarks.dat','dlib_face_recognition_resnet_model_v1.dat']:
            target=folder/name
            if not target.exists():
                compressed=target.with_suffix('.bz2')
                with requests.get(f'https://dlib.net/files/{name}.bz2',stream=True,timeout=(10,180)) as r:
                    r.raise_for_status()
                    with compressed.open('wb') as f:
                        for chunk in r.iter_content(1024*1024): f.write(chunk)
                temp=target.with_suffix('.tmp')
                with bz2.open(compressed,'rb') as source, temp.open('wb') as result:
                    while chunk:=source.read(1024*1024): result.write(chunk)
                if name.startswith('shape_'): dlib.shape_predictor(str(temp))
                else: dlib.face_recognition_model_v1(str(temp))
                temp.replace(target); compressed.unlink(); print('Downloaded and validated',name)
    print('Models ready. See OpenCV Zoo and dlib model pages for licenses.')
if __name__=='__main__':main()
