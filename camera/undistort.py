import cv2
import numpy as np
import time


def undistort_video_file(input_path, output_path, calibration_file, crop=True):
    # 1. Load calibration data
    try:
        with np.load(calibration_file) as X:
            mtx, dist = X['mtx'], X['dist']
            print(f"[INFO] Loaded calibration parameters from {calibration_file}")
    except FileNotFoundError:
        print(f"[ERROR] Calibration file '{calibration_file}' not found.")
        return

    # 2. Open the video
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"[ERROR] Could not open video {input_path}")
        return

    # Get video properties
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"[INFO] Input Video: {w}x{h} @ {fps:.2f} FPS ({total_frames} frames)")

    # 3. Calculate New Camera Matrix (optimized for the view)
    # alpha=0: Crop the image to remove black borders (valid pixels only)
    # alpha=1: Keep all pixels (retain black curve borders)
    alpha = 0 if crop else 1
    new_camera_mtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), alpha, (w, h))

    # 4. Generate the Undistort Map (The optimization step)
    # We compute the mapping functions only ONCE here.
    map_x, mapy = cv2.initUndistortRectifyMap(mtx, dist, None, new_camera_mtx, (w, h), 5)

    # 5. Setup Video Writer
    # We use 'mp4v' for .mp4. If you have issues, try 'XVID' with .avi output.
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    # If cropping (alpha=0), the dimensions might change slightly depending on ROI implementation
    # But usually, Remap keeps the original canvas size unless we manually crop.
    # To be safe, we use the original w, h for the writer.
    # If you want to physically crop the black pixels out:
    x, y, w_roi, h_roi = roi

    # If we are strictly cropping (alpha=0), we might want the output video to be smaller
    # to match the valid area.
    if crop:
        out_w, out_h = w_roi, h_roi
    else:
        out_w, out_h = w, h

    out = cv2.VideoWriter(output_path, fourcc, fps, (out_w, out_h))

    print(f"[INFO] Processing... Output resolution: {out_w}x{out_h}")

    frame_idx = 0
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 6. Apply the mapping (Fast Undistortion)
        dst = cv2.remap(frame, map_x, mapy, cv2.INTER_LINEAR)

        # If we selected crop=True, we physically slice the image to the valid ROI
        if crop:
            dst = dst[y:y + h_roi, x:x + w_roi]

        out.write(dst)

        # Progress indicator
        frame_idx += 1
        if frame_idx % 50 == 0:
            print(f"Processed {frame_idx}/{total_frames} frames...", end='\r')

    end_time = time.time()
    duration = end_time - start_time

    cap.release()
    out.release()

    print(f"\n[INFO] Done! Saved to '{output_path}'")
    processing_fps = frame_idx / duration if duration else 0
    print(f"[INFO] Time taken: {duration:.2f} seconds ({processing_fps:.2f} fps processed)")


if __name__ == "__main__":
    INPUT_VIDEO = '/home/markus/Videos/rasp-all/videos/bc4c/merged_output.mp4'
    OUTPUT_VIDEO = '/home/markus/Videos/rasp-all/videos/bc4c/merged_output_undistorted.mp4'
    CALIB_FILE = 'calibration_data.npz'
    undistort_video_file(INPUT_VIDEO, OUTPUT_VIDEO, CALIB_FILE, crop=True)
