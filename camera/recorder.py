import subprocess
import os
from typing import Optional


class CameraRecorder:
    def __init__(
        self,
        output_dir: str,
        width: int = 2304,
        height: int = 1296,
        fps: int = 30,
        bitrate: int = 20000000,  # bits per second
        buffer_count: int = 50,
        segment_seconds: int = 60,
        codec: str = "libav",         # "libav" for rpicam-vid FFmpeg, "h264" for hardware
        hdr: str = "off",             # "on" or "off"
        preview: bool = False,        # show preview window
        extra_args: Optional[list] = None  # any extra rpicam-vid args
    ):
        self.output_dir = output_dir
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.buffer_count = buffer_count
        self.segment_seconds = segment_seconds
        self.codec = codec
        self.hdr = hdr
        self.preview = preview
        self.extra_args = extra_args or []

        self.process: Optional[subprocess.Popen] = None
        os.makedirs(output_dir, exist_ok=True)

    def start(self):
        """Start the recording and pipe to FFmpeg for segmentation."""
        # Build rpicam-vid command
        rpicam_vid_cmd = [
            "rpicam-vid", "-t", "0",  # Continuous capture
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(self.fps),
            "--buffer-count", str(self.buffer_count),
            "--nopreview", "0" if self.preview else "1",
            "--autofocus-mode", "manual",
            "--lens-position", "0.0",
            "--denoise", "cdn_off",
            "--exposure", "normal", # or sports
            "--awb", "auto",
            "--hdr", self.hdr,
            "--codec", self.codec,
            "--libav-format", "mpegts",
            "--bitrate", str(self.bitrate),
        ]

        rpicam_vid_cmd += self.extra_args
        rpicam_vid_cmd += ["-o", "-"]  # Output to stdout for piping

        # Create the command for ffmpeg
        output_pattern = os.path.join(self.output_dir, "%Y%m%d_%H%M%S.mp4")
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",  # FFmpeg options
            "-f", "mpegts",  # Input format (h264 for streaming from rpicam-vid)
            "-i", "-",  # Read from stdin
            "-c:v", "copy",  # Codec copy (for direct passthrough)
            "-f", "segment",
            "-segment_time", str(self.segment_seconds),
            "-g", str(self.fps * 2),  # Keyframes after every n, for compression
            "-crf", "20",  # Constant Rate Factor (0 = best, 51 = worst quality)
            "-r", str(self.fps),
            "-reset_timestamps", "1",  # FFmpeg option
            "-strftime", "1",  # Allow strftime in filenames
            output_pattern,  # Output filename with strftime
        ]

        # Start rpicam-vid process
        rpicam_process = subprocess.Popen(
            rpicam_vid_cmd,
            stdout=subprocess.PIPE,  # Pipe the output to ffmpeg
            stderr=subprocess.PIPE,  # Capture stderr for debugging
        )

        # Start ffmpeg process
        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=rpicam_process.stdout,  # Pipe rpicam output to ffmpeg input
            stdout=subprocess.PIPE,  # Capture ffmpeg output (if needed)
            stderr=subprocess.PIPE,  # Capture ffmpeg stderr
        )

        # Close the rpicam-vid stdout so it doesn't hang
        rpicam_process.stdout.close()

        # Store both processes for later management (like stopping)
        self.process = rpicam_process

        # Optionally, monitor stderr for debugging
        stderr_output = rpicam_process.stderr.read().decode()
        if stderr_output:
            print("[CameraRecorder stderr]:", stderr_output)
        stderr_output = ffmpeg_process.stderr.read().decode()
        if stderr_output:
            print("[FFmpeg stderr]:", stderr_output)

    def stop(self):
        """Stop the recording and terminate the processes."""
        if self.process:
            self.process.terminate()
            self.process.wait()
