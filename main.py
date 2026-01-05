import threading
import time
import yaml
import os
from camera.recorder import CameraRecorder
from storage.ringbuffer import RingBufferManager
from obd_pi.read_obd import CarLogger
from utils.video_merger import VideoMerger
from datetime import datetime

import asyncio
from bleak import BleakScanner

# --- CONFIGURATION ---
OUTPUT_FILE = "candidates.txt"
MIN_SIGNAL_STRENGTH = -90  # dBm (Lower = allow weaker signals. -75 is good for "inside the car")
SCAN_DURATION = 10.0  # Seconds per scan loop
TOTAL_LOOPS = 6  # How many times to scan (6 * 10s = 60 seconds total)


def log_to_file(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)


async def run_scan():
    print(f"Starting scan... Results saved to {OUTPUT_FILE}")
    log_to_file("--- New Scan Session Started ---")

    for i in range(TOTAL_LOOPS):
        print(f"Scanning loop {i + 1}/{TOTAL_LOOPS}...")

        try:
            # FIX: return_adv=True returns a dictionary of {address: (device, adv_data)}
            # This ensures we have the AdvertisementData object which definitely has .rssi
            scanned_results = await BleakScanner.discover(timeout=SCAN_DURATION, return_adv=True)

            # Convert dictionary values to a list we can sort
            # Each item is a tuple: (BLEDevice, AdvertisementData)
            devices_list = list(scanned_results.values())

            # Sort by RSSI (signal strength) in the AdvertisementData (item[1])
            devices_list.sort(key=lambda x: x[1].rssi, reverse=True)

            found_close_device = False
            for device, adv_data in devices_list:
                rssi = adv_data.rssi

                if rssi > MIN_SIGNAL_STRENGTH:
                    found_close_device = True
                    # Use local name from advertisement if available, otherwise device name
                    name = adv_data.local_name if adv_data.local_name else (device.name or "Unknown")

                    log_line = f"FOUND: {name} | MAC: {device.address} | RSSI: {rssi}"
                    log_to_file(log_line)

            if not found_close_device:
                log_to_file(f"Loop {i + 1}: No devices stronger than {MIN_SIGNAL_STRENGTH} found.")

        except Exception as e:
            log_to_file(f"Error during scan: {e}")

    log_to_file("--- Scan Session Finished ---")
    print("Done.")

# -----------------------------
# CONFIGURATION
# -----------------------------
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Create a unique session directory for this run
CLIP_DIR = os.path.join(config["storage"]["clip_dir"], datetime.now().strftime("%Y%m%d_%H%M%S"))
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

    # Merging videos in a thread
    merger = VideoMerger(root_dir=config["storage"]["clip_dir"], interval=120)
    merger.set_active_folder(CLIP_DIR)
    merger.start()

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

    # 5. Monitor Loop
    try:
        # Start immediately before the loop
        recorder.start()

        while True:
            time.sleep(2)

            # Check: Is the process object created? AND has it exited?
            # poll() returns None if running, or an exit code (e.g. 1, -9) if stopped.
            rpicam_dead = (recorder.rpicam_process is not None) and (recorder.rpicam_process.poll() is not None)
            ffmpeg_dead = (recorder.ffmpeg_process is not None) and (recorder.ffmpeg_process.poll() is not None)

            if rpicam_dead or ffmpeg_dead:
                print("[MAIN] Recorder pipeline crashed/stopped. Restarting...")
                print(f"RPICAM-status: {rpicam_dead}, FFMPEG-status: {ffmpeg_dead}")

                # 1. Clean up any remaining zombie processes (e.g., if only ffmpeg died)
                recorder.stop()

                # 2. Restart fresh
                recorder.start()
                print("[MAIN] Restart successful.")

    except KeyboardInterrupt:
        print("\n[MAIN] Stopping dashcam...")
    finally:
        # 6. Clean Shutdown
        recorder.stop()
        # car_logger.stop_logging() # Uncomment if you have this object
        print("[MAIN] Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(run_scan())
    except KeyboardInterrupt:
        print("\nScan stopped by user.")
    main()
