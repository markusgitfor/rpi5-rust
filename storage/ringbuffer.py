from pathlib import Path
from typing import List


class RingBufferManager:
    """
    Manages a directory of video clips as a ring buffer.
    Deletes oldest clips when total storage exceeds the defined limit.
    """

    def __init__(self, directory: str, max_storage_bytes: int = 10 * 1024**3):
        """
        :param directory: Path to clip directory
        :param max_storage_bytes: Maximum allowed storage in bytes (default 10 GB)
        """
        self.directory = Path(directory)
        self.max_storage_bytes = max_storage_bytes
        self.directory.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _get_clip_files(self) -> List[Path]:
        """
        Returns a list of `.mp4` files in the directory sorted by modification time.
        """
        return sorted(
            (f for f in self.directory.glob("*.mp4") if f.is_file()),
            key=lambda f: f.stat().st_mtime
        )

    def _calculate_total_size(self, clips: List[Path]) -> int:
        """
        Calculates the total size of the given clips.
        """
        return sum(f.stat().st_size for f in clips)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def enforce_limit(self):
        """
        Deletes the oldest clips until total size is below the storage limit.
        """
        clips = self._get_clip_files()
        total_size = self._calculate_total_size(clips)

        while total_size > self.max_storage_bytes and clips:
            oldest = clips.pop(0)
            try:
                total_size -= oldest.stat().st_size
                oldest.unlink()
                print(f"[RingBuffer] Deleted {oldest.name} to free space")
            except Exception as e:
                print(f"[RingBuffer] Error deleting {oldest.name}: {e}")
