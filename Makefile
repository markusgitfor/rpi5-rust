# ----------------------------
# Dashcam Project Makefile
# ----------------------------

# Entry point of the project
ENTRY = main.py

# uv is detected from PATH if available, or fallback to user local bin.
UV ?= $(shell which uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

# ----------------------------
# Install system dependencies
# ----------------------------
.PHONY: systemdeps
systemdeps:
	@echo "Installing system dependencies..."
	sudo apt update
	sudo apt install -y curl ffmpeg libcamera-dev v4l-utils libgl1 libglib2.0-0
	@sudo apt install -y rpicam-apps libcamera-apps python3-libcamera 2>/dev/null || sudo apt install -y libcamera-tools 2>/dev/null || true
	@if [ ! -x "$(UV)" ]; then \
	    curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi
	
# ----------------------------
# Run code checks
# ----------------------------
.PHONY: code-check
code-check:
	@echo "Running flake8 code check..."
	$(UV) run flake8 . --max-line-length=120 --exclude venv,.venv

# ----------------------------
# Install Python packages
# ----------------------------
.PHONY: setup
setup:
	@echo "Installing Python dependencies..."
	$(UV) sync

# ----------------------------
# Run the dashcam project
# ----------------------------
.PHONY: run
run:
	@echo "Running dashcam project..."
	$(UV) run python $(ENTRY)

# ----------------------------
# Run tests
# ----------------------------
.PHONY: test
test: code-check
	@echo "Running simulation tests..."
	$(UV) run python -m unittest discover -s tests

# ----------------------------
# Update branch
# ----------------------------
.PHONY: update
update:
	git pull origin main
