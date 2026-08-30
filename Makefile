# ----------------------------
# Dashcam Project Makefile
# ----------------------------

# Entry point of the project
ENTRY = target/release/rpi5_dashcam

# ----------------------------
# Install system dependencies
# ----------------------------
.PHONY: systemdeps
systemdeps:
	@echo "Installing system dependencies..."
	sudo apt update
	sudo apt install -y curl ffmpeg libcamera-dev v4l-utils libgl1 libglib2.0-0 libudev-dev pkg-config
	@sudo apt install -y rpicam-apps libcamera-apps python3-libcamera 2>/dev/null || sudo apt install -y libcamera-tools 2>/dev/null || true
	@if ! command -v cargo &> /dev/null; then \
	    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; \
	fi
	
# ----------------------------
# Run code checks
# ----------------------------
.PHONY: code-check
code-check:
	@echo "Running cargo clippy..."
	cargo clippy -- -D warnings
	@echo "Running cargo fmt..."
	cargo fmt -- --check

# ----------------------------
# Install Python packages / Setup
# ----------------------------
.PHONY: setup
setup:
	@echo "Building Rust project..."
	cargo build --release

# ----------------------------
# Run the dashcam project
# ----------------------------
.PHONY: run
run:
	@echo "Running dashcam project..."
	cargo run --release

# ----------------------------
# Run tests
# ----------------------------
.PHONY: test
test: code-check
	@echo "Running simulation tests..."
	cargo test

# ----------------------------
# Update branch
# ----------------------------
.PHONY: update
update:
	git pull origin main
