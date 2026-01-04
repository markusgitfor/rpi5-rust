import threading
import time
import yaml
import os
from camera.recorder import CameraRecorder
from storage.ringbuffer import RingBufferManager
from secrets import token_hex
from obd_pi.read_obd import CarLogger

# -----------------------------
# CONFIGURATION
# -----------------------------
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Create a unique session directory for this run
CLIP_DIR = os.path.join(config["storage"]["clip_dir"], "%Y%m%d_%H%M%S")
os.makedirs(CLIP_DIR, exist_ok=True)  # Ensure directory exists immediately

MAX_STORAGE_GIGABYTES = config["storage"]["max_storage_gigabytes"]
SEGMENT_SECONDS = config["recording"]["segment_seconds"]

CAM_WIDTH = config["camera"]["width"]
CAM_HEIGHT = config["camera"]["height"]
CAM_FPS = config["camera"]["fps"]
CAM_BUFFER_COUNT = config["camera"]["buffer_count"]
CAM_CODEC = config["camera"]["codec"]
CAM_HDR = config["camera"]["hdr"]
CAM_PREVIEW = config["camera"]["preview"]
CAM_EXTRA_ARGS = config["camera"]["extra_args"]

RING_CHECK_INTERVAL = config["ring_buffer"]["check_interval_seconds"]

# OBD Config defaults
OBD_PORT = config.get("obd", {}).get("port", "/dev/rfcomm0")
OBD_ENABLED = config.get("obd", {}).get("enabled", False)


# -----------------------------
# RING BUFFER THREAD
# -----------------------------
def ring_buffer_loop(ring_buffer: RingBufferManager):
    while True:
        ring_buffer.enforce_limit()
        time.sleep(RING_CHECK_INTERVAL)  # check every minute


# -----------------------------
# MAIN
# -----------------------------
def main():
    print(f"--- Starting Dashcam Session: {CLIP_DIR} ---")

    # 1. Initialize Managers
    ring_buffer = RingBufferManager(CLIP_DIR, MAX_STORAGE_GIGABYTES)
    recorder = CameraRecorder(
        output_dir=CLIP_DIR,
        width=CAM_WIDTH,
        height=CAM_HEIGHT,
        fps=CAM_FPS,
        segment_seconds=SEGMENT_SECONDS,
        buffer_count=CAM_BUFFER_COUNT,
        codec=CAM_CODEC,
        hdr=CAM_HDR,
        preview=CAM_PREVIEW,
        extra_args=CAM_EXTRA_ARGS
    )

    # 2. Initialize OBD Logger
    # We pass the same CLIP_DIR so telemetry.csv is next to the videos
    car_logger = CarLogger(port=OBD_PORT, output_dir=CLIP_DIR, obd_enabled=OBD_ENABLED)

    # 3. Start Background Threads
    # Start Ring Buffer
    threading.Thread(target=ring_buffer_loop, args=(ring_buffer,), daemon=True).start()

    # Start OBD (Connect first, then thread)
    # We do this BEFORE camera so we don't delay video start too much,
    # but we don't let it block indefinitely.
    if car_logger.connect():
        car_logger.start_logging()

    # 4. Start Camera (Main Process)
    recorder.start()

    # 5. Monitor Loop
    try:
        while True:
            # Check if camera process is still alive
            if recorder.process.poll() is not None:
                print("[MAIN] Recorder crashed. Restarting...")
                recorder.start()

            # (Optional) Check if OBD disconnected and retry?
            # Usually better to leave it off to prevent bluetooth spamming
            # while driving, but you could add retry logic here.

            time.sleep(2)

    except KeyboardInterrupt:
        print("\n[MAIN] Stopping dashcam...")
    finally:
        # 6. Clean Shutdown
        recorder.stop()
        car_logger.stop_logging()
        print("[MAIN] Shutdown complete.")


if __name__ == "__main__":
    main()
