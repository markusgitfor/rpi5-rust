# rpi5-cam

This a software that can be used for controlling and recording camera data
using Raspberry Pi 5 and camera module v3 (wide angle lens). 

Installation is simple using following commands:

```
make systemdeps
make install
```

### Development with Dev Containers

This repository includes a ready-to-use `.devcontainer` configuration replicating the Raspberry Pi 5 (Debian 12 Bookworm) environment with `libcamera`, `ffmpeg`, `bluez`, and `uv` pre-installed.

1. Open this repository in VS Code.
2. When prompted, click **"Reopen in Container"** (or run `Dev Containers: Reopen in Container` from the Command Palette `F1` / `Ctrl+Shift+P`).
3. VS Code will automatically build the container and run `uv sync` to set up the virtual environment with all required dependencies.

Recording can be started with only using command: 

```
make run
```

Settings and path configured for saving the videos is found from the `config/config.yaml` file

Getting the recording to be started when turning on the device is done the following way:

`/etc/systemd/system/dashcam.service` has the following content:
```
[Unit]
Description=Dashcam Python Script
After=network.target

[Service]
ExecStart=/home/markus/Documents/rpi5/venv/bin/python3 /home/markus/Documents/rpi5/main.py
WorkingDirectory=/home/markus/Documents/rpi5
StandardOutput=inherit
StandardError=inherit
Restart=always
User=markus
Group=markus

[Install]
WantedBy=multi-user.target
```

Service can be monitored using the command:
```
sudo systemctl status dashcam.service
```
Stopped with this command: 
```
sudo systemctl stop dashcam.service
```
Started or restarted with this command: 
```
sudo systemctl start dashcam.service
sudo systemctl restart dashcam.service
```
Raspberry Pi can be accessed through Wi-Fi
```
ssh markus@192.168.0.033
```
Replace `192.168.0.33` with your Raspberry Pi’s actual IP address. Enter your password when prompted.
