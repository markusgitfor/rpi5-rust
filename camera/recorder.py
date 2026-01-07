import subprocess
import os
import signal
from typing import Optional


class CameraRecorder:
    def __init__(
            self,
            output_dir: str,
            width: int = 2304,
            height: int = 1296,
            fps: int = 30,
            buffer_count: int = 50,  # Increased slightly for safety
            segment_seconds: int = 60,
            codec: str = "libav",
            hdr: str = "off",
            preview: bool = False,
            extra_args: Optional[list] = None
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

        self.rpicam_process: Optional[subprocess.Popen] = None
        self.ffmpeg_process: Optional[subprocess.Popen] = None

        os.makedirs(output_dir, exist_ok=True)

    def start(self):
        """Start the recording and pipe to FFmpeg for segmentation."""

        # 1. Configure Video Encoding Options (libav)
        codec_opts = [
            "crf=23",
            "preset=superfast",
            "profile=high",
            "maxrate=15M",
            "bufsize=30M",
            f"g={int(self.fps)}"  # Keep this (1 keyframe/sec) for dashcam safety
        ]
        codec_opts_string = ";".join(codec_opts)

        # 2. Build rpicam-vid command (Continuous Stream)
        # We REMOVED internal segmentation here. rpicam sends one long stream.
        rpicam_vid_cmd = [
            "rpicam-vid", "-t", "0",
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(self.fps),
            "--buffer-count", str(self.buffer_count),  # Fixed typo here
            "--nopreview", "0" if self.preview else "1",
            "--autofocus-mode", "manual",
            "--lens-position", "0.2",
            "--denoise", "cdn_off",
            "--exposure", "short",
            "--awb", "auto",
            "--hdr", self.hdr,
            "--roi", "0.0,0.0,1.0,0.77777",
            "--codec", self.codec,
            "--libav-format", "mpegts",  # mpegts is robust for piping
            "--libav-video-codec-opts", codec_opts_string,
            "--inline",  # Helps with headers in streams
            "-o", "-"  # Output explicitly to stdout
        ]

        rpicam_vid_cmd += self.extra_args

        # 3. Build FFmpeg command (Segmentation Logic)
        output_pattern = os.path.join(self.output_dir, "%Y%m%d_%H%M%S.mp4")

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            # OPTIMIZATION: Input buffer size prevents pipe blocking
            "-thread_queue_size", "8192",
            "-f", "mpegts",
            "-i", "-",  # Read from stdin
            "-c:v", "copy",  # Zero-copy (extremely fast)
            "-an",  # No audio (unless you add a mic later)
            "-f", "segment",
            "-segment_time", str(self.segment_seconds),
            "-reset_timestamps", "1",
            "-strftime", "1",
            "-segment_format", "mp4",
            output_pattern
        ]

        print(f"Starting recording to: {self.output_dir}")

        # 4. Launch Processes
        # Start rpicam-vid
        self.rpicam_process = subprocess.Popen(
            rpicam_vid_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE  # Keep pipe open but don't read nicely yet to avoid blocking
        )

        # Start ffmpeg connecting stdin to rpicam's stdout
        self.ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=self.rpicam_process.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Allow rpicam process to receive SIGPIPE if ffmpeg dies
        self.rpicam_process.stdout.close()

    def stop(self):
        """Stop the recording gracefully."""
        print("Stopping recording...")

        # Terminate rpicam first (stops the source)
        if self.rpicam_process:
            self.rpicam_process.terminate()
            try:
                self.rpicam_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.rpicam_process.kill()

        # Terminate ffmpeg (finish writing the last file)
        if self.ffmpeg_process:
            # We can send SIGINT to ffmpeg to let it finalize the MP4 atom
            self.ffmpeg_process.send_signal(signal.SIGINT)
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()

        print("Recording stopped.")
