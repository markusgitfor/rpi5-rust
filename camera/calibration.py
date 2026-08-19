import cv2
import numpy as np


def calibrate_from_video(video_path, checkerboard_size, square_size_mm=100, error_threshold=0.5):
    """
    Calibrates camera from a video file, automatically removing bad frames.

    :param error_threshold: Maximum allowed reprojection error (pixels) per frame.
    """

    # 1. Setup termination criteria
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # 2. Prepare object points
    objp = np.zeros((checkerboard_size[0] * checkerboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:checkerboard_size[0], 0:checkerboard_size[1]].T.reshape(-1, 2)
    objp = objp * square_size_mm

    obj_points = []
    img_points = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return None, None

    frame_count = 0
    success_count = 0

    print("Processing video... Press 'q' to stop early.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Process every 10th frame
        if frame_count % 5 == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 3. Find the chess board corners
            ret_corners, corners = cv2.findChessboardCorners(gray, checkerboard_size, None)

            if ret_corners:
                # Refine corner locations
                corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

                # Add to lists
                obj_points.append(objp)
                img_points.append(corners2)

                # Visualize
                cv2.drawChessboardCorners(frame, checkerboard_size, corners2, ret_corners)
                success_count += 1
                cv2.imshow('Calibration in Progress', frame)
                cv2.waitKey(1)

        frame_count += 1
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if success_count == 0:
        print("Error: Chessboard corners were not detected in any frame.")
        return None, None

    # --- STEP 4: INITIAL CALIBRATION ---
    print(f"\nPerforming initial calibration on {len(obj_points)} frames...")
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points, gray.shape[::-1], None, None)
    print(f"Initial RMS Error: {ret:.4f} pixels")

    # --- STEP 5: FILTERING (REFINEMENT) ---
    print("\nFiltering poor frames...")
    objpoints_clean = []
    imgpoints_clean = []

    total_initial_error = 0

    for i in range(len(obj_points)):
        # Project the 3D points back to 2D using the initial calibration
        imgpoints2, _ = cv2.projectPoints(obj_points[i], rvecs[i], tvecs[i], mtx, dist)

        # Calculate error for this specific frame
        error = cv2.norm(img_points[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)

        # Accumulate the error (Fixed line)
        total_initial_error += error

        if error < error_threshold:
            objpoints_clean.append(obj_points[i])
            imgpoints_clean.append(img_points[i])
        else:
            print(f" -> Removed frame {i}: Error {error:.4f} is too high")

        # Calculate average arithmetic error
    mean_error = total_initial_error / len(obj_points)
    print(f"\nAverage Arithmetic Error (all frames): {mean_error:.4f}")
    print(f"Kept {len(objpoints_clean)} out of {len(obj_points)} frames.")

    if len(objpoints_clean) == 0:
        print("Error: All frames were removed! Try increasing the error_threshold.")
        return None, None

    # --- STEP 6: FINAL CALIBRATION ---
    print("\nPerforming final calibration...")
    ret_final, mtx_final, dist_final, rvecs_final, tvecs_final = cv2.calibrateCamera(
        objpoints_clean, imgpoints_clean, gray.shape[::-1], None, None
    )

    print("\n--- Final Calibration Results ---")
    print(f"Original Error: {ret:.4f}")
    print(f"Improved Error: {ret_final:.4f}")
    print("\nCamera Matrix:\n", mtx_final)
    print("\nDistortion Coefficients:\n", dist_final)

    np.savez("camera_calibration_data.npz", mtx=mtx_final, dist=dist_final)
    print("\nSaved to 'camera_calibration_data.npz'")

    return mtx_final, dist_final


if __name__ == "__main__":
    CHECKERBOARD_DIMS = (10, 7)
    VIDEO_FILE = '/home/markus/Videos/rasp/output.mp4'
    calibrate_from_video(VIDEO_FILE, CHECKERBOARD_DIMS, error_threshold=0.5)
