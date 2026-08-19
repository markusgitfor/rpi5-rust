import cv2
import pandas as pd
from datetime import timedelta

# --- CONFIGURATION ---
VIDEO_FILE = '/home/markus/Videos/dashcam-videos/videos/20260111_150421/20260111_150513.mp4'
CSV_FILE = '/home/markus/Videos/dashcam-videos/videos/20260111_150421/telemetry.csv'
OUTPUT_FILE = '/home/markus/Videos/dashcam-videos/videos/20260111_150421/20260111_150513_overlay.mp4'

# SYNC: How many seconds after the video starts does the log start?
# Positive = Log starts AFTER video. Negative = Log starts BEFORE video.
TIME_OFFSET_SECONDS = 0.0

# --- 1. LOAD DATA ---
df = pd.read_csv(CSV_FILE)

# Ensure timestamps are datetime objects
# Adjust the format string to match your CSV: '%Y-%m-%d %H:%M:%S.%f'
df['timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
if df.empty:
    raise RuntimeError("Telemetry file contains no valid timestamps")
start_time_log = df['timestamp'].iloc[0]

# --- 2. SETUP VIDEO ---
cap = cv2.VideoCapture(VIDEO_FILE)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

# Setup Video Writer
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(OUTPUT_FILE, fourcc, fps, (width, height))

print(f"Processing {VIDEO_FILE} ({width}x{height} @ {fps} fps)...")

frame_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # --- 3. CALCULATE TIME ---
    # Current time in the video (in seconds)
    video_current_seconds = frame_count / fps

    # Calculate the "Real World" time for this frame
    # (Video Start Time) + (Current Duration)
    # We approximate "Video Start Time" as (Log Start - Offset)
    current_frame_time = (
        start_time_log
        - timedelta(seconds=TIME_OFFSET_SECONDS)
        + timedelta(seconds=video_current_seconds)
    )

    # --- 4. FIND CLOSEST DATA POINT ---
    # Find the row nearest to this frame's time
    # 'method="nearest"' is crucial for syncing different refresh rates
    nearest_idx = df['timestamp'].searchsorted(current_frame_time)

    # Handle edge cases (start/end of file)
    if nearest_idx >= len(df):
        row = df.iloc[-1]
    elif nearest_idx == 0:
        row = df.iloc[0]
    else:
        previous_row = df.iloc[nearest_idx - 1]
        next_row = df.iloc[nearest_idx]
        row = (
            previous_row
            if current_frame_time - previous_row['timestamp'] <= next_row['timestamp'] - current_frame_time
            else next_row
        )

    # Get Speed (assuming column name is 'speed')
    # Use .get() or check column names if unsure
    speed = pd.to_numeric(row.get('Speed', 0), errors='coerce')
    coolant = pd.to_numeric(row.get('Coolant', 0), errors='coerce')
    speed = 0 if pd.isna(speed) else speed
    coolant = 0 if pd.isna(coolant) else coolant

    # --- 5. DRAW OVERLAY ---
    text = f"SPEED: {int(speed)} km/h, Coolant: {int(coolant)} Celsius"

    # Font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 2.5
    thickness = 5
    color = (0, 255, 0)  # Green

    # Position: Bottom Left
    text_size = cv2.getTextSize(text, font, scale, thickness)[0]
    text_x = 50
    text_y = height - 100

    # Draw black outline (for visibility)
    cv2.putText(frame, text, (text_x, text_y), font, scale, (0, 0, 0), thickness + 5)
    # Draw text
    cv2.putText(frame, text, (text_x, text_y), font, scale, color, thickness)

    # Write frame
    out.write(frame)
    frame_count += 1

    if frame_count % 100 == 0:
        print(f"Processed {frame_count} frames...")

cap.release()
out.release()
print("Done! Video saved as", OUTPUT_FILE)
