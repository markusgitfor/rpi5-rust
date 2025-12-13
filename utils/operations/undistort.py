import cv2
import numpy as np
from base import VideoOperation


class UndistortOperation(VideoOperation):
    def __init__(self, camera_matrix, dist_coeffs):
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self.new_camera_matrix = None

    def setup(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        self.new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix,
            self.dist_coeffs,
            (w, h),
            alpha=0
        )

    def apply(self, frame: np.ndarray) -> np.ndarray:
        return cv2.undistort(
            frame,
            self.camera_matrix,
            self.dist_coeffs,
            None,
            self.new_camera_matrix
        )
