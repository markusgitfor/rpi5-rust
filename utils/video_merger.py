import threading
import time
import os
import subprocess
import glob


class VideoMerger(threading.Thread):
    def __init__(self, root_dir: str, interval: int = 10):
        """
        :param root_dir: The main folder containing timestamped subfolders.
        :param interval: How often (in seconds) to scan for folders to merge.
        """
        super().__init__()
        self.root_dir = root_dir
        self.interval = interval
        self.current_active_dir = None
        self.running = True
        self.daemon = True  # Thread dies if main program dies

    def set_active_folder(self, folder_path: str):
        """Tell the merger which folder is currently recording (so we don't touch it)."""
        self.current_active_dir = folder_path

    def stop(self):
        self.running = False

    def run(self):
        print("[MERGER] Thread started.")
        while self.running:
            try:
                self._scan_and_merge()
            except Exception as e:
                print(f"[MERGER] Error: {e}")

            # Wait for next scan loop
            time.sleep(self.interval)

    def _scan_and_merge(self):
        # 1. Get all subdirectories in the root folder
        subdirs = [
            f.path for f in os.scandir(self.root_dir)
            if f.is_dir()
        ]

        for folder in subdirs:
            # SKIP if this folder is the one currently recording
            if folder == self.current_active_dir:
                continue

            # Check if already merged
            output_file = os.path.join(folder, "merged_full.mp4")
            if os.path.exists(output_file):
                continue

            # Check if there are MP4 segments to merge
            segments = sorted(glob.glob(os.path.join(folder, "*.mp4")))
            if not segments:
                continue

            # If we found segments but no "merged_full.mp4", let's merge!
            print(f"[MERGER] Processing: {os.path.basename(folder)} ({len(segments)} segments)")
            self._execute_ffmpeg_merge(folder, segments, output_file)

    def _execute_ffmpeg_merge(self, folder, segments, output_file):
        # 1. Create the 'mylist.txt' required by FFmpeg concat
        # Format: file '/absolute/path/to/video.mp4'
        list_path = os.path.join(folder, "merge_list.txt")

        with open(list_path, "w") as f:
            for segment in segments:
                # Use absolute paths to be safe
                abs_path = os.path.abspath(segment)
                # Escape single quotes in filenames if necessary
                abs_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{abs_path}'\n")

        # 2. Run FFmpeg command
        # -f concat: The concat demuxer
        # -safe 0: Allow absolute paths
        # -c copy: COPY STREAMS (No re-encoding, very fast, low CPU)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            output_file
        ]

        result = subprocess.run(cmd)

        if result.returncode == 0:
            print(f"[MERGER] Success: {os.path.basename(folder)} -> merged_full.mp4")
            # Optional: Delete the list file to clean up
            os.remove(list_path)
            # Optional: Delete original segments?
            # for s in segments: os.remove(s)
        else:
            print(f"[MERGER] Failed to merge {folder}")