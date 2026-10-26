#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
sudo apt-get update
sudo apt-get install -y python3-venv python3-tk python3-dev alsa-utils libsndfile1 ffmpeg libgl1
sudo timedatectl set-timezone Asia/Kuwait
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python download_models.py
mkdir -p "$HOME/.config/systemd/user"
python3 - <<'PY'
from pathlib import Path
import os
p=Path.cwd()
unit=f'''[Unit]
Description=Noor accessible companion and cloud agent
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
WorkingDirectory={p}
Environment=TZ=Asia/Kuwait
EnvironmentFile=-{p}/.env
ExecStart="{p}/.venv/bin/python" "{p}/app.py"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
'''
target=Path.home()/'.config/systemd/user/noor.service'
target.write_text(unit)
autostart=Path.home()/'.config/autostart'
autostart.mkdir(parents=True,exist_ok=True)
(autostart/'noor.desktop').write_text('''[Desktop Entry]
Type=Application
Name=Noor companion
Exec=sh -c "systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY XDG_RUNTIME_DIR; systemctl --user restart noor.service"
Terminal=false
X-GNOME-Autostart-enabled=true
''')
PY
systemctl --user daemon-reload
systemctl --user enable noor.service
echo 'Set pi/config.json and pi/.env with OPENAI_API_KEY, then: systemctl --user start noor'
echo 'Enable desktop auto-login in raspi-config. The UI service needs the logged-in graphical session.'
