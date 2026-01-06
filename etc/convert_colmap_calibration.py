import numpy as np

# ==========================================
# PASTE YOUR VALUES FROM cameras.txt BELOW
# ==========================================
# Example Line from cameras.txt:
# 1 OPENCV 1920 1080 1205.3 1205.3 960.0 540.0 -0.25 0.12 0.001 0.001

fx = 974.47298208873099   # Focal Length X
fy = 989.38283549038738   # Focal Length Y
cx = 1152.0    # Principal Point X
cy = 648.0    # Principal Point Y

# Distortion Coefficients
k1 = 0.055467773120429067    # Radial Distortion 1
k2 = -0.04726968041993624     # Radial Distortion 2
p1 = 0.0047247701161419377    # Tangential Distortion 1
p2 = -0.010473737234142614    # Tangential Distortion 2
k3 = 0.0      # Radial Distortion 3 (Leave as 0.0, COLMAP usually doesn't give this)

# Output filename
OUTPUT_FILE = "calibration_data.npz"

# ==========================================
# DO NOT EDIT BELOW THIS LINE
# ==========================================

# 1. Construct the Camera Matrix (3x3)
mtx = np.array([
    [fx, 0, cx],
    [0, fy, cy],
    [0,  0,  1]
], dtype=np.float64)

# 2. Construct the Distortion Coefficients Vector (1x5)
# Standard OpenCV order: k1, k2, p1, p2, k3
dist = np.array([k1, k2, p1, p2, k3], dtype=np.float64)

# 3. Save to .npz file
print(f"Saving to {OUTPUT_FILE}...")
print(f"Matrix:\n{mtx}")
print(f"Distortion: {dist}")

np.savez(OUTPUT_FILE, mtx=mtx, dist=dist)

print("Done! You can now run your video processing script.")
