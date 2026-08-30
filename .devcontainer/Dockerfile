FROM mcr.microsoft.com/devcontainers/base:bookworm

# Prevent prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

# Install system dependencies matching Raspberry Pi 5 (Debian Bookworm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    make \
    curl \
    wget \
    git \
    python3 \
    python3-dev \
    python3-venv \
    python3-pip \
    # Camera & Video dependencies
    ffmpeg \
    libcamera-dev \
    libcamera-tools \
    v4l-utils \
    # OpenCV GUI and runtime dependencies
    libgl1 \
    libglib2.0-0 \
    # Bluetooth & OBD dependencies
    bluez \
    libbluetooth-dev \
    libudev-dev \
    rfkill \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Astral uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Add vscode user to hardware device access groups
RUN for group in video dialout bluetooth plugdev input; do \
        groupadd -f -r "$group" && usermod -aG "$group" vscode; \
    done

# Switch to vscode user and install Rust toolchain
USER vscode
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable

# Ensure vscode cargo and local bin are in PATH
ENV PATH="/home/vscode/.cargo/bin:/home/vscode/.local/bin:$PATH"

