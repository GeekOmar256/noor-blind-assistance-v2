# Noor — Blind assistance v2

This is the separate Noor v2 source repository. The Pi upload helper transfers only the runtime code listed in `deploy/pi_remote.py`. It leaves local credentials, enrolled data, and downloaded models on the Pi intact.

## Caregiver app

- Site: https://alzheimer-noor.web.app
- Interface preview: https://alzheimer-noor.web.app/?demo=1 (sample data only)
- Account: `cargiver@gmail.com` (spelling supplied by the user).
- Device ID: `blind-pi`.
- Initial password, when this account is newly created, is in the private `LOCAL_ACCESS.txt`. Do not commit or share that file.
- Keep the paired `pi/config.json` and `pi/.env` privately on the Pi. They are not included in this repository or in code updates.
- Firebase Hosting forwards to the Python `caregiver` Cloud Function in `europe-west1`.
- This uses the existing Alzheimer Firebase project, but a separate Hosting site, function codebase, and `noor_devices` collection. Existing Firestore and Storage rules are not overwritten.
- Media is stored in the separate private `alzheimer-noor-private` bucket with public access prevention; the existing app's public bucket is not used.

Sign in, add people and any number of photos (6 MB maximum per image, JPEG/PNG/WebP), then select **Sync & train on Pi**. Photos should show exactly one face. Add more photos with **Edit / add photos**. The Pi downloads every profile and referenced image before replacing its gallery. Any download failure preserves the previous gallery; photos without exactly one detected face are skipped and counted in the training result.

After the Pi captures a photo, the overview offers **Use this photo for recognition**. Choose an existing person or enter a new name, relationship, and note. The server attaches the current Pi photo and queues gallery training as one database operation. The photo must show one face for enrollment to succeed.

SFace is a pretrained embedding model: training here builds a local gallery rather than changing neural network weights. Recognition uses YuNet detection, aligned SFace embeddings, cosine similarity, and an ambiguity margin. Validate thresholds with your actual camera and people; unfamiliar/ambiguous faces remain unknown. Only current profile IDs can match, including after profile deletion.

The caregiver Settings page can switch between SFace and dlib. Both have separate galleries. dlib uses a frontal-face detector, five-point alignment, and 128-dimensional face descriptors. Install it on the Pi after its base environment is ready:

```bash
cd /home/abc/noor_v2/pi
bash install_dlib.sh
systemctl --user restart noor
```

The dlib installer compiles the Python extension and downloads both official model files. This can take time on the Pi. It validates that the models load before reporting success. Selecting dlib in the app before installation saves the preference but shows an installation notice; run **Sync & train on Pi** after installation and upload person photos. The Pi reports model availability in its heartbeat.

The care profile and locally matched people's names, relationships, and notes are supplied to the scene AI. Medical information is contextual; the prompt does not ask the model to diagnose or recite the record. Recognition can be disabled from either interface.

The Settings page also toggles face recognition and scene description independently. Disabling scene description prevents AI scene analysis from the Pi button and the interface; voice notes and reminders still work.

## Raspberry Pi installation

Use Raspberry Pi OS Desktop, preferably a 64-bit Pi 4/5. For an existing installation, run `python deploy/pi_remote.py upload` on the workstation after setting `NOOR_SSH_PASSWORD`; this copies only Pi runtime code to `/home/abc/noor_v2/pi`. Keep the Pi's existing `config.json`, `.env`, models, data, and virtual environment in place. A first installation also needs private configuration and dependencies provisioned separately.

```bash
cd /home/abc/noor_v2/pi
# Keep the prepared .env; if missing, copy .env.example and enter your key.
nano .env                      # verify your OpenAI key
bash install.sh
chmod 600 .env config.json
systemctl --user start noor
```

Enable desktop auto-login through `raspi-config`. The installer adds a graphical session autostart entry and a user service. This opens the full-screen Tkinter app on desktop login and reports actual visibility to Firebase. A desktop session is required; a headless Pi cannot show a Tk window.

To run manually, export the OpenAI key first (systemd loads `.env`, a direct Python invocation does not):

```bash
set -a; source .env; set +a
.venv/bin/python app.py
# optional: --windowed or --offline
```

The installer sets the OS timezone to `Asia/Kuwait`. The app also explicitly uses that timezone. Reminders are stored as UTC instants, selected as Kuwait dates and 12-hour AM/PM times, and compared against the Pi clock. Enable system time synchronization; software timezone selection does not repair an incorrect clock.

Live camera streaming starts automatically and reconnects with 1–15 second backoff. Physical GPIO13 button handling from the included ESP sketch is retained. Set `camera` in `pi/config.json` to `auto`, a hostname or an IP. Every caregiver photo request captures a new frame rather than returning a cached stream image.

Before compiling the ESP sketch, copy `esp32cam_stream/wifi_config.example.h` to `esp32cam_stream/wifi_config.h` and enter the camera's Wi-Fi network and password. The real header is excluded from Git.

Closing the window hides it, leaving sync and reminders running. The caregiver's **Open screen / Close screen** changes visibility remotely. The lens button shows/hides the text zoom slider; Escape exits fullscreen. Restarting the Pi app opens the screen again.

The Pi's zoom slider now scales the live camera image from 60% to 200% within its viewport as well as interface text. The adjacent screen icon switches between fullscreen and a smaller window. The live stream itself continues independently of these display controls.

For Windows preview, create `pi/.venv`, install `pi/requirements.txt`, and double-click `Run Noor.bat`. ONNX models are downloaded with `python pi/download_models.py`. Pi camera, FFmpeg and audio features still require their corresponding devices/dependencies.

## Reminders and voice notes

The agent polls Firebase every 3 seconds. Reminders are cached locally; it attempts to generate their speech before they are due, allowing playback without internet once audio has been cached. A reminder created while the Pi is offline remains pending until reconnection. An overdue pending reminder is delivered after sync.

Playback status is journaled locally before audio begins to avoid duplicate reminders after reboot. A crash during playback is reported as interrupted/failed and requires a new message or reminder; this favors avoiding duplicate playback over claiming exactly-once delivery. Sync status and command completion are shown in the caregiver interface. The offline indicator uses a 25-second heartbeat age, not just the last reported flag.

Safari recording uses microphone feature detection and a supported MIME type, preferring MP4/AAC. Recording needs HTTPS and user microphone permission. File upload provides a fallback; notes are limited to 8 MB and recordings to 3 minutes. FFmpeg on the Pi decodes MP4/AAC, WebM, MP3, and WAV before native playback. Actual iPhone microphone permissions and Pi speaker output require testing on those devices.

The Voice notes page lists sent notes. **Listen here** loads the private recording through the authenticated API; **Replay on Pi** queues playback of the same recording without uploading it again.

## Deployment and access

```powershell
cd noor-blind-assistance-v2
firebase deploy --only functions:blind-assistance-v2,hosting --project alzheimer-g3qi6e
```

Install Python function dependencies in `functions/venv` before deploying. Deployment uses Python 3.11 because that runtime is available on this workstation. `functions/.env.alzheimer-g3qi6e` contains the public Firebase web API key and private bucket name; it contains no Admin credential. Copy `.env.example` for another project.

`deploy/provision.py` pairs a caregiver and a dedicated Firebase Auth device user using an administrator's Application Default Credentials. No Admin service account key is placed on the Pi. Device/caregiver authorization is checked on every API call against the paired UIDs. Direct database and storage access is unnecessary. `firestore.rules` and `storage.rules` are reference deny-all rules for a dedicated project only: do not deploy them over this shared project's rules.

Keep `pi/config.json`, `pi/.env`, cached faces, medical records, and `LOCAL_ACCESS.txt` private. Firebase web API keys are public app configuration; Firebase Auth plus server-side ownership checks provide authorization.

## Verification

```powershell
functions\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
node tests/browser.cjs
```

Browser tests use the workstation's bundled Playwright and Edge; adjust its require path on another machine. They test the explicitly labeled demo, not a connected Pi. Device acceptance still needs: real enrollment and recognition, Wi-Fi disconnect/reconnect, boot auto-start, fresh snapshot, remote screen visibility, reminder audio, Safari recording/upload, and Pi speaker playback. No hardware success is assumed from browser tests.

Live cloud tests also passed: caregiver and device login, pairing authorization, cross-device denial, person/image upload and download, anonymous media denial, reminder storage, and command acknowledgements. Their fixtures were removed. `tests/live_browser.cjs` passed against the deployed site with the paired caregiver account. These transport checks do not represent Pi hardware playback or camera tests.

Model sources and licenses: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet and https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface.

dlib model reference and download links: https://www.dlib.net/face_recognition.py.html. dlib face-distance matching uses a conservative 0.55 cutoff and a separation margin to leave ambiguous matches unidentified. Real accuracy must be checked with enrolled people and the project's camera.
