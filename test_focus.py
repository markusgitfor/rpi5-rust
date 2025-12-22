import time
import os
import subprocess

# Settings
start_focus = 0.0
end_focus = 4.0  # 0=Infinity, 10=Macro (10cm). We only care about 0-4 for dashcams.
steps = 20  # How many photos to take
output_dir = "focus_test"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print(f"Starting focus sweep from {start_focus} to {end_focus}...")

for i in range(steps + 1):
    # Calculate lens position
    lens_pos = start_focus + (end_focus - start_focus) * (i / steps)
    lens_pos = round(lens_pos, 2)

    filename = f"{output_dir}/focus_{lens_pos}.jpg"

    # Command to take a single picture at this specific lens position
    # We use a slight delay (--timeout 1000) to let the lens move
    cmd = [
        "rpicam-still",
        "-t", "1000",
        "--width", "4608",  # Full Resolution for checking sharpness
        "--height", "2592",
        "--autofocus-mode", "manual",
        "--lens-position", str(lens_pos),
        "-o", filename
    ]

    print(f"Capturing: {filename} (Lens: {lens_pos})")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Done! Check the 'focus_test' folder and find the sharpest image.")