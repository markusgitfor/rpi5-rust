# Agent Guidelines for `rpi5-dashcam`

This document provides essential instructions, architectural context, and development standards for AI agents working in this repository.

---

## 🚨 Mandatory Verification Rule

> **Every change must be verified by running:**
> ```bash
> make test
> ```
> **No task is complete until `make test` passes cleanly.**

`make test` executes two verification steps:
1. **Linter & Style Check (`make code-check`)**: Runs `cargo clippy -- -D warnings` and `cargo fmt -- --check`.
2. **Test Suite**: Runs all unit and simulation tests (`cargo test`).

---

## Project Overview

`rpi5-dashcam` is a modular dashcam and vehicle telemetry recording system designed for Raspberry Pi 5 with Camera Module v3 (wide-angle lens) and Bluetooth OBD-II (ELM327) readers, implemented in **Rust**.

### Key Components

- **`src/main.rs`**: Application entrypoint. Initializes recorder, ring buffer, and OBD logging threads; monitors subprocess health and handles graceful shutdown.
- **`src/camera.rs`**: Camera recording pipeline (`CameraRecorder`) spawning and managing `rpicam-vid` piped into `ffmpeg` for segmented MP4 video recording.
- **`src/storage.rs`**: Video and telemetry data storage management (`RingBufferManager`) monitoring disk usage against configured storage limits (`max_storage_gigabytes`) and purging oldest un-protected video sessions (FIFO).
- **`src/obd_pi.rs`**: Vehicle telemetry logging (`CarLogger`) querying OBD-II PIDs (including custom Mazda SkyActiv PIDs for oil temperature and pressure) and writing timestamped CSV logs.
- **`config/config.yaml`**: Central configuration for camera parameters, video segmentation, storage limits, and OBD port/settings.
- *(Note: Post-processing, calibration, and diagnostic tools have been moved to the [`rpi5-tooling`](https://github.com/markusgitfor/rpi5-tooling) repository).*

---

## Development Environment & Tooling

The project uses **Rust** (managed via `cargo` / `rustup`).

### Common Makefile Commands

| Command | Description |
|---|---|
| `make test` | **Run full validation** (clippy + formatting + test suite) |
| `make code-check` | Run `cargo clippy` with `-D warnings` and `cargo fmt -- --check` |
| `make setup` | Build the Rust project release binary (`cargo build --release`) |
| `make run` | Start the dashcam application (`cargo run --release`) |
| `make systemdeps` | Install required Linux system packages and Rust toolchain |
| `make update` | Pull latest updates from `origin main` |

### Dependency Management

- Dependencies are declared in `Cargo.toml` and locked in `Cargo.lock`.
- Use `cargo add` or edit `Cargo.toml` and run `cargo check` / `cargo build`.

---

## Coding Standards & Guidelines

1. **Code Style & Formatting**:
   - Adhere to PEP 8 standards.
   - Max line length is **120 characters**.
   - Ensure clean imports without unused dependencies.
   - Run `make code-check` to verify linting.

2. **Process Lifecycle & Cleanup**:
   - Subprocesses (`rpicam-vid`, `ffmpeg`) and background threads (`RingBufferManager`, `CarLogger`) must be managed safely.
   - Always implement graceful termination (`SIGINT` / `terminate()` before `kill()`) and cleanup logic in `try...finally` or explicit `stop()` methods.

3. **Hardware Simulation & Testing**:
   - Physical hardware (Raspberry Pi camera sensor, `/dev/rfcomm*` OBD dongles) is not available in standard CI / devcontainer environments.
   - Any new features touching camera subprocesses or OBD serial communication must include unit tests with appropriate mocks (`unittest.mock.patch`, `MagicMock`).
   - All tests must be self-contained and clean up temporary test files in `tearDown()`.

4. **Configuration Decoupling**:
   - Avoid hardcoding paths, resolutions, frame rates, or thresholds in source code.
   - Read configurations from `config/config.yaml` or provide sensible defaults.

5. **Documentation Integrity**:
   - Preserve existing comments, docstrings, and type hints when editing files.

---

## 🔀 Git & Pull Request Workflow

When developing features, bug fixes, or documentation, follow this frictionless Git and GitHub workflow:

### 1. Branch Naming Convention
Create a descriptive feature branch from `main`:
```bash
git checkout -b <type>/<short-description>
```
Examples:
- `feature/add-gps-telemetry`
- `fix/ffmpeg-restart-loop`
- `docs/add-agents-guidelines`
- `refactor/ringbuffer-cleanup`

### 2. Verification Before Committing
Run the required verification step before staging changes:
```bash
make test
```
Ensure linting (`flake8`) and tests pass cleanly without errors.

### 3. Stage & Commit
Write clear, concise commit messages following standard conventions:
```bash
git add <files>
git commit -m "<type>: <brief description of changes>"
```

### 4. Push Branch to Origin
Push the feature branch to GitHub:
```bash
git push -u origin <branch-name>
```

### 5. Create Pull Request with GitHub CLI (`gh`)
Open a Pull Request with a clear title and description:
```bash
gh pr create --title "<PR Title>" --body "<Detailed description of changes and verification>"
```

### 6. Automated Skill
A reusable workspace skill is available at `.agents/skills/git-pr/SKILL.md` for invoking and following this workflow.

