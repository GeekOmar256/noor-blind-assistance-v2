"""Check the Pi button's short, long and disabled actions without GPIO hardware."""
import sys
import json
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pi'))
from service import Service
import core


class FakeButton:
    def __init__(self, pin, **kwargs):
        self.pin = pin
        self.options = kwargs
        self.when_held = None
        self.when_released = None
        self.closed = False

    def close(self):
        self.closed = True


class FakeStop:
    def __init__(self, actions):
        self.actions = actions

    def wait(self):
        self.actions()


class PiButtonTest(unittest.TestCase):
    def test_short_long_and_disabled(self):
        service = Service.__new__(Service)
        service.config = {'gpioButton': 14}
        settings = {'sceneDescription': True, 'faceRecognition': True}
        service.settings = lambda: settings
        queued = []
        service.enqueue = lambda identifier, item, collection: queued.append((item['type'], collection))
        button = None

        def press_sequence():
            button.when_released()  # Short press.
            button.when_held()
            button.when_released()  # Long press must not also request objects.
            settings['faceRecognition'] = False
            button.when_held()
            button.when_released()
            settings['sceneDescription'] = False
            button.when_released()

        service.stop = FakeStop(press_sequence)

        def make_button(*args, **kwargs):
            nonlocal button
            button = FakeButton(*args, **kwargs)
            return button

        with patch.dict(sys.modules, {'gpiozero': types.SimpleNamespace(Button=make_button)}):
            service.pi_button_loop()

        self.assertEqual(button.pin, 14)
        self.assertFalse(button.options['pull_up'])
        self.assertEqual(button.options['hold_time'], 1.2)
        self.assertTrue(button.closed)
        self.assertEqual(queued, [('objects', 'local'), ('faces', 'local')])

    def test_object_request_does_not_identify_faces(self):
        service = Service.__new__(Service)
        service.lock = threading.RLock()
        service.state = {'profile': {}, 'persons': [{'id': '1', 'name': 'Sam'}]}
        service.config = {'model': 'test-model'}
        service.settings = lambda: {'sceneDescription': True, 'faceRecognition': True, 'speech': False}
        service.recognizer = lambda settings: self.fail('Object request called face recognizer')
        prompt = []

        class FakeClient:
            def __enter__(self):
                self.responses = types.SimpleNamespace(create=self.create)
                return self

            def __exit__(self, *args):
                pass

            def create(self, **kwargs):
                prompt.append(kwargs['input'][0]['content'][0]['text'])
                return types.SimpleNamespace(output_text=json.dumps({'description': 'A chair', 'objects': [], 'visible_hazards': [], 'uncertainty': ''}))

        with patch.dict(sys.modules, {'openai': types.SimpleNamespace(OpenAI=lambda **kwargs: FakeClient())}), \
             patch.object(core, 'api_key', return_value='test'), \
             patch.object(core, 'narration', return_value='A chair'):
            service.analyse(b'jpeg', include_faces=False)

        self.assertEqual(service.description, 'A chair')
        self.assertIn('Do not identify people by name.', prompt[0])

    def test_face_request_uses_selected_local_model(self):
        service = Service.__new__(Service)
        service.lock = threading.RLock()
        service.state = {'persons': [{'id': '1', 'name': 'Sam', 'relation': 'Brother'}]}
        service.settings = lambda: {'faceRecognition': True, 'faceModel': 'dlib', 'language': 'en', 'speech': False}
        chosen = []

        class FakeRecognizer:
            def identify(self, image, persons):
                chosen.append((image, persons))
                return [{'name': 'Sam', 'relation': 'Brother'}]

        service.recognizer = lambda settings: chosen.append(settings['faceModel']) or FakeRecognizer()
        service.identify_faces(b'jpeg')
        self.assertEqual(chosen[0], 'dlib')
        self.assertEqual(chosen[1][0], b'jpeg')
        self.assertIn('Sam (Brother)', service.description)


if __name__ == '__main__':
    unittest.main()
