from pathlib import Path
from typing import Iterable, List, Optional


def _calculate_total_size(files: List[Path]) -> int:
    """
    Calculates the total size of the given files in bytes.
    Note: Can raise FileNotFoundError if a file is deleted concurrently.
    """
    return sum(f.stat().st_size for f in files if f.exists())


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
        self.base_directory = Path(base_directory).resolve()
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
        return sorted(
            [
                f for f in self.base_directory.rglob("*")
                if f.is_file() and not self._is_protected(f)
            ],
            key=lambda f: f.stat().st_mtime if f.exists() else 0
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
        Cascades upwards until the base_directory is reached or
        a non-empty directory is found.
        """
        parent = file_path.parent
        # Recursively check and remove if empty, up to base_directory
        while parent != self.base_directory and parent.is_relative_to(self.base_directory):
            if not parent.exists():
                parent = parent.parent
                continue

            try:
                # iterdir() raises error if not empty, so we check if list is empty
                if not any(parent.iterdir()):
                    parent.rmdir()
                    print(f"[RingBuffer] Removed empty folder: {parent.name}")
                    parent = parent.parent
                else:
                    break  # Not empty, stop propagating upwards
            except OSError:
                break  # Directory likely not empty or permissions issue

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def enforce_limit(self):
        """
        Deletes the oldest files across ALL subfolders until
        combined total size is below the storage limit.
        """
        all_files_info = []
        total_size = 0

        # Single pass: collect files, mtimes, and sizes to minimize disk I/O
        for f in self.base_directory.rglob("*"):
            if f.is_file():
                try:
                    stat = f.stat()
                    total_size += stat.st_size
                    if not self._is_protected(f):
                        all_files_info.append((f, stat.st_mtime, stat.st_size))
                except FileNotFoundError:
                    # File was deleted concurrently, skip it
                    pass

        # Sort files by mtime (oldest first)
        all_files_info.sort(key=lambda x: x[1])

        # Delete files until we are under the limit
        while total_size > self.max_storage_bytes and all_files_info:
            oldest_file, _, file_size = all_files_info.pop(0)

            try:
                oldest_file.unlink()  # Delete the file
                total_size -= file_size
                print(f"[RingBuffer] Deleted {oldest_file.name} ({file_size / 1024 / 1024:.2f} MB) to free space")

                # Clean up the folder hierarchy if it's now empty
                self._remove_empty_parents(oldest_file)

            except FileNotFoundError:
                # File already deleted concurrently, still subtract its size from our total
                total_size -= file_size
            except Exception as e:
                print(f"[RingBuffer] Error deleting {oldest_file.name}: {e}")
