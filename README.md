# rpi5-dashcam

A modular, lightweight dashcam and vehicle telemetry recording system designed for the **Raspberry Pi 5** using the **Raspberry Pi Camera Module v3** (wide-angle lens) and **Bluetooth OBD-II (ELM327)** adapters, implemented in **Rust**.

---

## ✨ Features

- **Continuous Segmented Recording**: Uses `rpicam-vid` hardware video capture piped into `ffmpeg` for seamless, timestamped MP4 video segmentation.
- **Automatic Ring Buffer Storage**: Monitors disk usage and automatically purges the oldest un-protected video sessions (FIFO) once storage exceeds the configured limit.
- **OBD-II Vehicle Telemetry**: Simultaneously logs vehicle parameters (Speed, RPM, Throttle, Coolant Temperature, plus custom Mazda SkyActiv Oil Temperature & Oil Pressure) to a synchronized `telemetry.csv` file.
- **Crash Recovery & Reliability**: Monitors capture and encoding subprocesses, automatically restarting the recording pipeline if a crash is detected.
- **Auto-Start on Boot**: Complete `systemd` service setup for hands-free, headless operation when the vehicle starts.
- **Dedicated Tooling Suite**: Companion post-processing, calibration, and diagnostic tools are available in [`rpi5-tooling`](https://github.com/markusgitfor/rpi5-tooling).
- **Dev Container Support**: Pre-configured VS Code Dev Container replicating the Raspberry Pi OS (Debian 12 Bookworm) environment for development and simulation testing with the Rust toolchain pre-installed.

---

## 📋 Table of Contents

- [Hardware Requirements](#-hardware-requirements)
- [Installation & Setup](#-installation--setup)
  - [Native Installation (Raspberry Pi OS)](#native-installation-raspberry-pi-os)
  - [Development with Dev Containers](#development-with-dev-containers)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Auto-Start on Boot (systemd Service)](#-auto-start-on-boot-systemd-service)
- [OBD-II Telemetry Setup](#-obd-ii-telemetry-setup)
- [Remote Access & File Transfer](#-remote-access--file-transfer)
  - [SSH Remote Access](#ssh-remote-access)
  - [Transferring Videos to PC (rsync)](#transferring-videos-to-pc-rsync)
- [Companion Tooling (`rpi5-tooling`)](#-companion-tooling-rpi5-tooling)
- [Project Structure](#-project-structure)
- [Development & Testing](#-development--testing)

---

## 🛠 Hardware Requirements

- **Raspberry Pi 5** (recommended: 4GB or 8GB RAM)
- **Raspberry Pi Camera Module v3** (Wide-angle FOV 120° recommended for dashcam use)
- **MicroSD Card or NVMe SSD** (fast storage class recommended for continuous video writes)
- **Bluetooth OBD-II Adapter** (optional, e.g., ELM327 / OBDLink / Carly adapter for telemetry)
- **Power Supply**: 5V/5A USB-C power source or 12V-to-5V vehicle hardwire kit

---

## 🚀 Installation & Setup

### Native Installation (Raspberry Pi OS)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/markusgitfor/rpi5-rust.git
   cd rpi5-rust
   ```

2. **Install system dependencies & Rust toolchain:**
   ```bash
   make systemdeps
   ```
   This command installs essential system packages (`ffmpeg`, `libcamera-dev`, `v4l-utils`, `libudev-dev`, `pkg-config`, etc.) and sets up the Rust toolchain via [`rustup`](https://rustup.rs).

3. **Build the release binary:**
   ```bash
   make setup
   ```
   This command compiles the project in release mode (`cargo build --release`).

---

### Development with Dev Containers

This repository includes a ready-to-use `.devcontainer` configuration replicating the Raspberry Pi 5 (Debian 12 Bookworm) environment with the Rust toolchain, `libcamera`, `ffmpeg`, `bluez`, and `libudev-dev` pre-installed.

1. Open this repository in **VS Code**.
2. When prompted, click **"Reopen in Container"** (or run `Dev Containers: Reopen in Container` from the Command Palette `F1` / `Ctrl+Shift+P`).
3. VS Code will automatically build the container and run `make setup` to compile the project.

---

## 🎬 Usage

### Starting the Dashcam

To start the dashcam recorder manually:

```bash
make run
```

Or run directly via `cargo`:

```bash
cargo run --release
```

Or execute the compiled binary directly:

```bash
./target/release/rpi5_dashcam
```

### Stopping the Dashcam

Press `Ctrl+C` in the terminal to trigger a graceful shutdown. All active video segments and telemetry CSV files will be cleanly closed.

---

## ⚙️ Configuration

All runtime settings are managed via [`config/config.yaml`](config/config.yaml).

```yaml
# =============================
# Dashcam Configuration
# =============================

storage:
  clip_dir: "videos"                 # Destination root directory for recorded sessions
  max_storage_gigabytes: 12          # Maximum disk space before FIFO deletion triggers

obd:
  port: "/tmp/ttyCarly"              # Serial/RFCOMM port or PTY for OBD-II adapter
  enabled: true                      # Enable or disable telemetry recording
  commands:                          # Configurable OBD-II PIDs and custom addresses to query
    - name: "RPM"                    # CSV header label
      address: "010C"                # OBD PID / command hex address
    - name: "Speed"
      address: "010D"
    - name: "Coolant"
      address: "0105"
    - name: "Intake Temp"
      address: "010F"
    - name: "Oil Temp"
      address: "221310"
    - name: "Load"
      address: "0104"
    - name: "Timing"
      address: "010E"
    - name: "Rail Press"
      address: "0159"

recording:
  segment_seconds: 60                # Length of each segmented video clip (in seconds)

camera:
  width: 2304                        # Video capture resolution width
  height: 1008                       # Video capture resolution height
  fps: 25                            # Frame rate (FPS)
  buffer_count: 30                   # Frame buffer count
  codec: "libav"                     # Video codec: "libav" (software) or "h264" (hardware)
  hdr: "off"                         # HDR mode: "on" or "off"
  preview: false                     # Enable or disable live preview window
  extra_args: []                     # Additional flags passed directly to rpicam-vid
  # libav_opts:                      # Advanced encoding options for libav (optional)
  #   - "crf=23"
  #   - "preset=superfast"
  #   - "profile=high"
  #   - "maxrate=15M"
  #   - "bufsize=30M"
  #   - "g=25"

ring_buffer:
  check_interval_seconds: 60         # How often to check and enforce storage limits
```

### Session Storage Structure

Each time the dashcam starts, a new timestamped folder is created inside the configured `clip_dir`:

```
videos/
└── 20260830_120000/
    ├── output_000.mp4       # 60-second video segment 0
    ├── output_001.mp4       # 60-second video segment 1
    ├── output_002.mp4       # 60-second video segment 2
    └── telemetry.csv        # Synchronized OBD-II telemetry log
```

---

## 🔄 Auto-Start on Boot (systemd Service)

To run the dashcam automatically when the Raspberry Pi boots up, configure a `systemd` service.

### 1. Create the Service File

Create `/etc/systemd/system/dashcam.service` with root privileges:

```bash
sudo nano /etc/systemd/system/dashcam.service
```

Add the following configuration (adjust paths and user according to your setup):

```ini
[Unit]
Description=Dashcam Service
After=network.target

[Service]
# Path to compiled Rust release binary and working directory
ExecStart=/home/markus/Documents/rpi5-rust/target/release/rpi5_dashcam
WorkingDirectory=/home/markus/Documents/rpi5-rust
StandardOutput=inherit
StandardError=inherit
Restart=always
RestartSec=5
User=markus
Group=markus

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start the Service

```bash
# Reload systemd manager configuration
sudo systemctl daemon-reload

# Enable service to run on boot
sudo systemctl enable dashcam.service

# Start the service immediately
sudo systemctl start dashcam.service
```

### 3. Service Management Commands

| Action | Command |
|---|---|
| **Check Status** | `sudo systemctl status dashcam.service` |
| **Stop Service** | `sudo systemctl stop dashcam.service` |
| **Start Service** | `sudo systemctl start dashcam.service` |
| **Restart Service** | `sudo systemctl restart dashcam.service` |
| **Disable on Boot** | `sudo systemctl disable dashcam.service` |
| **View Live Logs** | `journalctl -u dashcam.service -f` |

---

## 🚗 OBD-II Telemetry Setup

The dashcam system includes telemetry logging through standard OBD-II protocols and custom Mazda SkyActiv PIDs.

1. **Pair the Bluetooth OBD-II Adapter**:
   ```bash
   bluetoothctl
   [bluetooth]# scan on
   [bluetooth]# pair <ADAPTER_MAC_ADDRESS>
   [bluetooth]# trust <ADAPTER_MAC_ADDRESS>
   [bluetooth]# exit
   ```

2. **Bind RFCOMM Port (if using classic Bluetooth ELM327)**:
   ```bash
   sudo rfcomm bind rfcomm0 <ADAPTER_MAC_ADDRESS>
   ```

3. **Configure the Port**:
   Set `port: "/dev/rfcomm0"` (or your custom device path) and `enabled: true` in `config/config.yaml`.

4. **Logged Telemetry Metrics**:
   - Timestamp (`YYYY-MM-DD HH:MM:SS.fff`)
   - Speed (km/h)
   - Engine RPM
   - Throttle Position (%)
   - Coolant Temperature (°C)
   - Oil Temperature (°C) *(Mazda SkyActiv PID)*
   - Oil Pressure (kPa) *(Mazda SkyActiv PID)*

---

## 📶 Remote Access & File Transfer

### SSH Remote Access

You can access and manage your Raspberry Pi over Wi-Fi via SSH:

```bash
ssh markus@192.168.0.33
```

> **Note:** Replace `markus` with your Raspberry Pi username and `192.168.0.33` with your Raspberry Pi's actual IP address. Enter your password when prompted.

### Transferring Videos to PC (rsync)

To copy or sync recorded video sessions and telemetry logs from the Raspberry Pi directly to your PC, run the following command in your PC's terminal:

```bash
rsync -avP markus@192.168.0.33:/home/markus/Documents/rpi5-rust/videos/ .
```

- `-a` (archive): Preserves timestamps, permissions, and directory structure.
- `-v` (verbose): Displays detailed transfer progress.
- `-P` (progress & partial): Shows a real-time progress bar and allows resuming interrupted transfers.
- `.` (destination): Copies all session folders directly into your current working directory.

---

## 🧰 Companion Tooling (`rpi5-tooling`)

Post-processing, camera calibration, focus diagnostics, and telemetry overlay utilities have been decoupled into the dedicated repository **[`rpi5-tooling`](https://github.com/markusgitfor/rpi5-tooling)**:

- **Camera Undistortion & Calibration**:
  - `calibration/camera_calibration.py`: Computes camera calibration matrix and distortion coefficients using chessboard pattern images.
  - `calibration/convert_colmap.py`: Converts COLMAP intrinsics to OpenCV `.npz` calibration format.
  - `video/undistort.py`: Removes fisheye barrel distortion from recorded video files.
- **Focus & Sharpness Diagnostics**:
  - `diagnostics/test_focus.py`: Interactive focus testing utility using `rpicam-still`.
  - `diagnostics/check_sharpness.py`: Calculates image sharpness metrics (Laplacian variance) on camera frames.
- **Video & Telemetry Processing**:
  - `telemetry/overlay_video.py`: Overlays real-time speed and telemetry onto recorded dashcam videos.
  - `video/merger.py`: Merges segmented MP4 video clips into combined session files.
  - `video/processor.py`: Extensible video transformation pipeline.

---

## 📁 Project Structure

```
rpi5-rust/
├── config/
│   └── config.yaml          # Central dashcam and hardware configuration
├── src/
│   ├── camera.rs            # CameraRecorder (rpicam-vid + ffmpeg pipeline)
│   ├── main.rs              # Application entrypoint and subsystem orchestration
│   ├── obd_pi.rs            # CarLogger OBD-II telemetry with custom Mazda PIDs
│   └── storage.rs           # RingBufferManager (FIFO disk space enforcement)
├── .devcontainer/           # VS Code Dev Container configuration
├── Cargo.lock               # Dependency lockfile
├── Cargo.toml               # Cargo package manifest & dependencies
└── Makefile                 # Automation targets (run, test, code-check, setup, etc.)
```

---

## 🧪 Development & Testing

### Running Tests and Lint Checks

Always verify changes using the Makefile test suite:

```bash
# Run full verification (clippy + formatting + test suite)
make test

# Run code formatting and linter checks only
make code-check
```

### Dependency Management

Dependencies are managed using `Cargo` and tracked in `Cargo.toml` and `Cargo.lock`.

```bash
# Add a new crate dependency
cargo add <crate-name>

# Build the project
cargo build

# Run unit tests
cargo test
```
