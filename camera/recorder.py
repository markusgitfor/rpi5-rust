import subprocess
import os
import signal
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CameraRecorder:
    def __init__(
            self,
            output_dir: str,
            width: int = 2304,
            height: int = 1296,
            fps: int = 30,
            buffer_count: int = 50,
            segment_seconds: int = 60,
            codec: str = "libav",
            hdr: str = "off",
            preview: bool = False,
            extra_args: Optional[list] = None,
            libav_opts: Optional[list] = None
    ):
        self.output_dir = output_dir
        self.width = width
        self.height = height
        self.fps = fps
        self.buffer_count = buffer_count
        self.segment_seconds = segment_seconds
        self.codec = codec
        self.hdr = hdr
        self.preview = preview
        self.extra_args = extra_args or []
        self.libav_opts = libav_opts or [
            "crf=23",
            "preset=superfast",
            "profile=high",
            "maxrate=15M",
            "bufsize=30M",
            f"g={int(self.fps)}"
        ]

        self.rpicam_process: Optional[subprocess.Popen] = None
        self.ffmpeg_process: Optional[subprocess.Popen] = None

        os.makedirs(output_dir, exist_ok=True)

    @property
    def is_running(self) -> bool:
        """Check if both processes are currently running."""
        rpicam_alive = self.rpicam_process and self.rpicam_process.poll() is None
        ffmpeg_alive = self.ffmpeg_process and self.ffmpeg_process.poll() is None
        return bool(rpicam_alive and ffmpeg_alive)

    def start(self) -> None:
        """Start the recording and pipe to FFmpeg for segmentation."""
        if self.is_running:
            logger.warning("Recording is already running.")
            return

        # 1. Build rpicam-vid command
        rpicam_vid_cmd = [
            "rpicam-vid", "-t", "0",
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(self.fps),
            "--buffer-count", str(self.buffer_count),
            "--autofocus-mode", "manual",
            "--lens-position", "0.2",
            "--denoise", "cdn_off",
            "--exposure", "short",
            "--awb", "auto",
            "--hdr", self.hdr,
            "--roi", "0.0,0.0,1.0,0.77777",
            "--codec", self.codec,
            "--inline",
            "-o", "-"
        ]

        if not self.preview:
            rpicam_vid_cmd.append("--nopreview")

        # Conditionally add libav specific options
        if self.codec == "libav":
            rpicam_vid_cmd.extend([
                "--libav-format", "mpegts",
                "--libav-video-codec-opts", ";".join(self.libav_opts)
            ])

        rpicam_vid_cmd += self.extra_args

        # 2. Build FFmpeg command
        output_pattern = os.path.join(self.output_dir, "%Y%m%d_%H%M%S.mp4")
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-thread_queue_size", "8192",
            "-f", "mpegts",
            "-i", "-",
            "-c:v", "copy",
            "-an",
            "-f", "segment",
            "-segment_time", str(self.segment_seconds),
            "-reset_timestamps", "1",
            "-strftime", "1",
            "-segment_format", "mp4",
            "-segment_format_options", "movflags=+faststart",
            output_pattern
        ]

        logger.info(f"Starting recording to: {self.output_dir}")

        # 3. Launch Processes
        try:
            self.rpicam_process = subprocess.Popen(
                rpicam_vid_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            if self.rpicam_process.stdout is None:
                raise RuntimeError("Failed to open rpicam stdout pipe.")

            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=self.rpicam_process.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Allow rpicam process to receive SIGPIPE if ffmpeg dies
            self.rpicam_process.stdout.close()

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.stop()  # Ensure cleanup on partial startup failure
            raise

    def stop(self) -> None:
        """Stop the recording gracefully."""
        logger.info("Stopping recording...")

        if self.rpicam_process:
            if self.rpicam_process.poll() is None:
                self.rpicam_process.terminate()
                try:
                    self.rpicam_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.rpicam_process.kill()
            self.rpicam_process = None

        if self.ffmpeg_process:
            if self.ffmpeg_process.poll() is None:
                self.ffmpeg_process.send_signal(signal.SIGINT)
                try:
                    self.ffmpeg_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.ffmpeg_process.kill()
            self.ffmpeg_process = None

        logger.info("Recording stopped.")
