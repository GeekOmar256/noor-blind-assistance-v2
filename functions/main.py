import os
import firebase_admin
from firebase_admin import credentials
from firebase_functions import https_fn
from api import app

firebase_admin.initialize_app(options={'storageBucket':os.getenv('STORAGE_BUCKET','alzheimer-noor-private')})

@https_fn.on_request(region='europe-west1', memory=512, timeout_sec=60)
def caregiver(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()
