"""Camera orientation follows the caregiver setting for streams and captures."""
import io
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pi'))
import core
from service import Service
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'functions'))
import api


class CameraRotationTest(unittest.TestCase):
    def test_api_accepts_only_right_angle_rotations(self):
        class Ref:
            def __init__(self): self.saved = None
            def set(self, value, merge): self.saved = value

        ref = Ref()
        with patch.object(api, 'root', return_value=(ref, 'caregiver')):
            client = api.app.test_client()
            self.assertEqual(client.post('/api/settings', json={'cameraRotation': 90}).status_code, 200)
            self.assertEqual(ref.saved, {'settings': {'cameraRotation': 90}})
            for invalid in [45, -90, True, '90']:
                self.assertEqual(client.post('/api/settings', json={'cameraRotation': invalid}).status_code, 400)

    def test_fresh_capture_uses_synced_rotation(self):
        service = Service.__new__(Service)
        service.config = {'camera': 'http://camera.local/capture', 'rotate': 0}
        service.camera = service.config['camera']
        service.settings = lambda: {'cameraRotation': 270}
        with patch.object(core, 'capture', return_value=b'jpeg') as capture:
            self.assertEqual(service.capture(), b'jpeg')
        capture.assert_called_once_with('http://camera.local/capture', 270)

    def test_live_stream_frame_is_rotated(self):
        source = io.BytesIO()
        Image.new('RGB', (20, 10), 'red').save(source, format='JPEG')
        service = Service.__new__(Service)
        service.config = {'camera': 'http://camera.local/capture', 'rotate': 0}
        service.settings = lambda: {'cameraRotation': 90}
        service.stop = threading.Event()
        service.lock = threading.RLock()
        service.camera = None
        service.camera_ok = False
        service.busy = False
        service.frame = None

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size):
                yield source.getvalue()
                service.stop.set()

        with patch('service.requests.get', return_value=Response()):
            service.camera_loop()
        with Image.open(io.BytesIO(service.frame)) as frame:
            self.assertEqual(frame.size, (10, 20))


if __name__ == '__main__':
    unittest.main()
