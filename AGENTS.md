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
1. **Linter & Style Check (`make code-check`)**: Runs `flake8 . --max-line-length=120 --exclude venv,.venv`.
2. **Test Suite**: Discovers and runs all unit and simulation tests (`uv run python -m unittest discover -s tests`).

---

## Project Overview

`rpi5-dashcam` is a modular dashcam and vehicle telemetry recording system designed for Raspberry Pi 5 with Camera Module v3 (wide-angle lens) and Bluetooth OBD-II (ELM327) readers.

### Key Components

- **`main.py`**: Application entrypoint. Initializes recorder, ring buffer, and OBD logging threads; monitors subprocess health and handles graceful shutdown.
- **`camera/`**: Camera recording pipeline.
  - `recorder.py`: `CameraRecorder` spawns and manages `rpicam-vid` piped into `ffmpeg` for segmented MP4 video recording.
  - `undistort.py` & `calibration.py`: Lens calibration and video undistortion tools.
- **`storage/`**: Video and telemetry data storage management.
  - `ringbuffer.py`: `RingBufferManager` monitors disk usage against configured storage limits (`max_storage_gigabytes`) and purges oldest un-protected video sessions (FIFO).
- **`obd_pi/`**: Vehicle telemetry logging.
  - `read_obd.py`: `CarLogger` queries OBD-II PIDs (including custom Mazda SkyActiv PIDs for oil temperature and pressure) and writes timestamped CSV logs.
- **`config/`**:
  - `config.yaml`: Central configuration for camera parameters, video segmentation, storage limits, and OBD port/settings.
- **`utils/`**: Video processing utilities (`processor.py`, `operations/`, `video_merger.py`).
- **`tests/`**: Unit and simulation tests.
- **`etc/`**: Diagnostic and utility scripts (focus checking, sharpness testing, speed overlay).

---

## Development Environment & Tooling

The project uses **Python 3.12+** and **[uv](https://github.com/astral-sh/uv)** for fast dependency management.

### Common Makefile Commands

| Command | Description |
|---|---|
| `make test` | **Run full validation** (flake8 linting + test suite) |
| `make code-check` | Run flake8 linter with 120-character line length |
| `make setup` | Install/sync Python dependencies using `uv sync` |
| `make run` | Start the dashcam application (`uv run python main.py`) |
| `make systemdeps` | Install required Linux system packages and `uv` |
| `make update` | Pull latest updates from `origin main` |

### Dependency Management

- Package dependencies are declared in `pyproject.toml` and locked in `uv.lock`.
- When adding or updating dependencies, update `pyproject.toml` and run `uv sync` or `uv lock`.

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

