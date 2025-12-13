import threading
import time
from camera.recorder import CameraRecorder
from storage.ringbuffer import RingBufferManager

# -----------------------------
# CONFIGURATION
# -----------------------------
CLIP_DIR = "/home/markus/Documents/rpi5-cam/videos/clips"  # Directory for video clips
MAX_STORAGE_BYTES = 1 * 1024**3  # 1 GB max storage
SEGMENT_SECONDS = 60  # Each clip = 1 minute
CAM_WIDTH = 2560
CAM_HEIGHT = 1440
CAM_FPS = 30
CAM_BITRATE = 20_000_000  # 50 MB/s

# -----------------------------
# RING BUFFER THREAD
# -----------------------------


def ring_buffer_loop(ring_buffer: RingBufferManager):
    while True:
        ring_buffer.enforce_limit()
        time.sleep(60)  # check every minute

# -----------------------------
# MAIN
# -----------------------------


def main():
    # 1️⃣ Start ring buffer manager
    ring_buffer = RingBufferManager(CLIP_DIR, MAX_STORAGE_BYTES)
    threading.Thread(target=ring_buffer_loop, args=(ring_buffer,), daemon=True).start()

    # 2️⃣ Start camera recorder (outputs to stdout)
    recorder = CameraRecorder(
        output_dir=CLIP_DIR,  # temporary directory for rpicam output
        width=CAM_WIDTH,
        height=CAM_HEIGHT,
        fps=CAM_FPS,
        bitrate=CAM_BITRATE,
        segment_seconds=SEGMENT_SECONDS,
    )
    recorder.start()

    # 4️⃣ Monitor and auto-restart if needed
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
    main()
