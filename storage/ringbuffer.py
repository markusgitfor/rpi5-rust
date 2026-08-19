from pathlib import Path
from typing import Iterable, List, Optional


def _calculate_total_size(files: List[Path]) -> int:
    """
    Calculates the total size of the given files in bytes.
    """
    return sum(f.stat().st_size for f in files)


class RingBufferManager:
    """
    Manages a directory tree of video clips and data logs as a ring buffer.
    Recursively checks all subfolders, calculates combined size, and deletes
    the oldest files (and empty subfolders) when the limit is exceeded.
    """

    def __init__(
        self,
        base_directory: str,
        max_storage_gigabytes: int = 10,
        protected_directories: Optional[Iterable[str]] = None,
    ):
        """
        :param base_directory: Root path containing session subfolders
        :param max_storage_gigabytes: Maximum allowed storage in GiB (default 10 GiB).
        :param protected_directories: Directories whose files must not be deleted.
        """
        self.base_directory = Path(base_directory)
        self.max_storage_bytes = max_storage_gigabytes * 1024 ** 3
        self.protected_directories = {
            Path(directory).resolve() for directory in (protected_directories or [])
        }
        self.base_directory.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def _get_all_files(self) -> List[Path]:
        """
        Returns a list of ALL files in the directory tree (recursive),
        sorted by modification time (oldest first).
        """
        # rglob("*") searches recursively through all subdirectories.
        # We filter for is_file() to ignore directory names in the list.
        return sorted(
            [
                f for f in self.base_directory.rglob("*")
                if f.is_file() and not self._is_protected(f)
            ],
            key=lambda f: f.stat().st_mtime
        )

    def _is_protected(self, file_path: Path) -> bool:
        resolved_path = file_path.resolve()
        return any(
            resolved_path.is_relative_to(directory)
            for directory in self.protected_directories
        )

    def _remove_empty_parents(self, file_path: Path):
        """
        Removes the parent directory of the file if it is empty.
        Does not remove the base_directory itself.
        """
        parent = file_path.parent
        # Check if parent is a subdirectory (not the root) and is effectively empty
        if parent != self.base_directory and parent.exists():
            try:
                # iterdir() raises error if not empty, so we check if list is empty
                if not any(parent.iterdir()):
                    parent.rmdir()
                    print(f"[RingBuffer] Removed empty folder: {parent.name}")
            except OSError:
                # Directory likely not empty or busy
                pass

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def enforce_limit(self):
        """
        Deletes the oldest files across ALL subfolders until
        combined total size is below the storage limit.
        """
        all_files = [f for f in self.base_directory.rglob("*") if f.is_file()]
        total_size = _calculate_total_size(all_files)
        files = self._get_all_files()

        # Check if we are over the limit
        while total_size > self.max_storage_bytes and files:
            oldest_file = files.pop(0)  # The first item is the oldest

            try:
                file_size = oldest_file.stat().st_size
                oldest_file.unlink()  # Delete the file

                # Update our running total
                total_size -= file_size
                print(f"[RingBuffer] Deleted {oldest_file.name} ({file_size / 1024 / 1024:.2f} MB) to free space")

                # Clean up the folder if it's now empty
                self._remove_empty_parents(oldest_file)

            except Exception as e:
                print(f"[RingBuffer] Error deleting {oldest_file.name}: {e}")
