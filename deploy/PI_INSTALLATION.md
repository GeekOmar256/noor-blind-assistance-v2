# Pi installation record

- Host: `abc.local` (`192.168.1.10` at installation)
- SSH user: `abc`
- OS: Debian 13 / Raspberry Pi desktop, ARM64, Python 3.13
- Application: `/home/abc/noor_v2/pi`
- Service: `systemctl --user status noor`
- Startup: `/home/abc/.config/autostart/noor.desktop`, validated with `desktop-file-validate`
- Timezone: `Asia/Kuwait`; system clock synchronization enabled
- Caregiver app: https://alzheimer-noor.web.app

Installed the native Pi dependencies and an isolated Python virtual environment. Both ONNX models match the workstation SHA-256 hashes and load successfully on the Pi. The application authenticates using its paired device account. Secret configuration files have mode `600`.

Hardware acceptance checks completed:

- Firebase device sign-in and live status updates.
- Caregiver remote close/open of the running Tkinter window.
- Uploaded MP4/AAC audio downloaded, decoded by FFmpeg, and played successfully through the Pi audio pipeline.
- An Arabic test reminder synchronized, generated speech, executed at its scheduled time, and reported `done`.
- Rebooted the Pi and confirmed automatic launch with no service restarts, the screen visible, and a fresh Firebase heartbeat after boot.

Successful playback return codes do not establish that a connected speaker was audible to a person. Actual iPhone Safari microphone behavior remains a separate device test.

Camera testing is pending: the Pi is on Wi-Fi `HAMZA`, but `blindcam.local` and the ESP camera's advertised service were not discoverable during installation. Once the ESP camera is connected to the same network, the running agent automatically retries discovery and streaming. Face enrollment and recognition accuracy require real user-supplied photos and a working camera.

The SSH password is not stored in this project. The source is published in the separate private `noor-blind-assistance-v2` repository.

## Update pending

The caregiver app now adds captured-photo enrollment, voice replay, model selection, and independent face/scene switches. Local Pi code adds camera-image zoom and a fullscreen icon. Pi installation and live camera/face checks for this update were deferred at the user's request while the Pi's Firebase heartbeat was stale. When reachable, run the workstation helper `deploy/pi_remote.py upload` with `NOOR_SSH_PASSWORD` set to transfer only the Pi runtime code to `/home/abc/noor_v2/pi`. It does not upload credentials, person data, models, tests, web files, or documentation. Restart `noor.service` separately to load the updated code. Run the dlib installer separately if that model is wanted.
