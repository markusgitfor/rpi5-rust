import cv2
from typing import List
from operations.base import VideoOperation


class VideoPostProcessor:
    def __init__(self, operations: List[VideoOperation]):
        self.operations = operations

    def process(self, input_path: str, output_path: str):
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {input_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        ret, frame = cap.read()
        if not ret:
            raise RuntimeError("Empty video file")

        # Setup operations using first frame
        for op in self.operations:
            op.setup(frame)

        while ret:
            for op in self.operations:
                frame = op.apply(frame)

            out.write(frame)
            ret, frame = cap.read()

        for op in self.operations:
            op.teardown()

        cap.release()
        out.release()
