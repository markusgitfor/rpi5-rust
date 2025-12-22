import threading
import time
import yaml
from camera.recorder import CameraRecorder
from storage.ringbuffer import RingBufferManager
from test_focus import test_focus

# -----------------------------
# CONFIGURATION
# -----------------------------
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

CLIP_DIR = config["storage"]["clip_dir"]
MAX_STORAGE_BYTES = config["storage"]["max_storage_bytes"]
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
    # Start ring buffer manager
    ring_buffer = RingBufferManager(CLIP_DIR, MAX_STORAGE_BYTES)
    threading.Thread(target=ring_buffer_loop, args=(ring_buffer,), daemon=True).start()

    # Start camera recorder (outputs to stdout)
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
    recorder.start()

    # Monitor and auto-restart if needed
    try:
        while True:
            if not recorder.process.poll() is None:
                print("[MAIN] Recorder crashed. Restarting...")
                recorder.start()
            time.sleep(2)
    except KeyboardInterrupt:
        print("[MAIN] Stopping dashcam...")
        recorder.stop()


if __name__ == "__main__":
    test_focus()
    main()
