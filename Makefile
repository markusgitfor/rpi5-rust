# ----------------------------
# Dashcam Project Makefile
# ----------------------------

# Name of the virtual environment folder
VENV = venv

# Python interpreter
PYTHON = python3

# Requirements file
REQS = requirements.txt

# Entry point of the project
ENTRY = main.py

# ----------------------------
# Install system dependencies
# ----------------------------
.PHONY: systemdeps
systemdeps:
	@echo "Installing system dependencies for Pi Camera..."
	sudo apt update
	sudo apt install -y libcamera-apps libcamera-dev python3-libcamera
	
# ----------------------------
# Run code checks
# ----------------------------
.PHONY: code-check
code-check:
	@echo "Running flake8 code check..."
	$(VENV)/bin/flake8 . --max-line-length=120 --exclude venv  # Ignore the 'venv' directory

# ----------------------------
# Create virtual environment & install Python packages
# ----------------------------
.PHONY: install
install: venv
	@echo "Installing Python dependencies..."
	$(VENV)/bin/pip install --upgrade pip setuptools wheel
	@if [ -f $(REQS) ]; then \
	    $(VENV)/bin/pip install -r $(REQS); \
	else \
	    echo "No requirements.txt found, skipping pip install."; \
	fi

.PHONY: venv
venv:
	@echo "Creating Python virtual environment (with access to system packages)..."
	$(PYTHON) -m venv --system-site-packages $(VENV)
	@echo "Virtual environment created in $(VENV)"

# ----------------------------
# Run the dashcam project
# ----------------------------
.PHONY: run
run:
	@echo "Running dashcam project..."
	$(VENV)/bin/python3 $(ENTRY)

# ----------------------------
# Clean virtual environment
# ----------------------------
.PHONY: clean
clean:
	rm -rf $(VENV)
	@echo "Removed virtual environment $(VENV)"
