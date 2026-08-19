# ----------------------------
# Dashcam Project Makefile
# ----------------------------

# Entry point of the project
ENTRY = main.py

# uv is installed per-user by the official installer. Override with `make UV=uv ...`
# when uv is already available on PATH.
UV ?= $(HOME)/.local/bin/uv

# ----------------------------
# Install system dependencies
# ----------------------------
.PHONY: systemdeps
systemdeps:
	@echo "Installing system dependencies for Pi Camera..."
	sudo apt update
	sudo apt install -y curl libcamera-apps libcamera-dev python3-libcamera
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
.PHONY: install
install:
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
# Update branch
# ----------------------------
.PHONY: update
update:
	git pull origin main
