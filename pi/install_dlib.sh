#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
sudo apt-get update
sudo apt-get install -y build-essential cmake libopenblas-dev
.venv/bin/python -m pip install 'dlib>=19.24,<21'
.venv/bin/python download_models.py --with-dlib
.venv/bin/python - <<'PY'
from pathlib import Path
from recognition import DlibRecognizer
DlibRecognizer(Path('models')).load()
print('dlib detector, landmark predictor and recognition network are ready')
PY
