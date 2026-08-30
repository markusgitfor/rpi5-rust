use log::info;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

pub struct RingBufferManager {
    pub base_directory: PathBuf,
    pub max_storage_bytes: u64,
    pub protected_directories: Vec<PathBuf>,
}

impl RingBufferManager {
    pub fn new(
        base_directory: String,
        max_storage_gigabytes: u64,
        protected_directories: Vec<String>,
    ) -> Self {
        let base_directory = Path::new(&base_directory)
            .canonicalize()
            .unwrap_or_else(|_| PathBuf::from(&base_directory));
        fs::create_dir_all(&base_directory).ok();

        let protected_directories = protected_directories
            .into_iter()
            .map(|d| {
                Path::new(&d)
                    .canonicalize()
                    .unwrap_or_else(|_| PathBuf::from(d))
            })
            .collect();

        Self {
            base_directory,
            max_storage_bytes: max_storage_gigabytes * 1024 * 1024 * 1024,
            protected_directories,
        }
    }

    fn is_protected(&self, file_path: &Path) -> bool {
        let resolved_path = file_path
            .canonicalize()
            .unwrap_or_else(|_| file_path.to_path_buf());
        self.protected_directories
            .iter()
            .any(|dir| resolved_path.starts_with(dir))
    }

    fn remove_empty_parents(&self, mut file_path: PathBuf) {
        if let Some(parent) = file_path.parent() {
            file_path = parent.to_path_buf();
        } else {
            return;
        }

        while file_path != self.base_directory && file_path.starts_with(&self.base_directory) {
            if !file_path.exists() {
                if let Some(parent) = file_path.parent() {
                    file_path = parent.to_path_buf();
                    continue;
                } else {
                    break;
                }
            }

            if let Ok(mut entries) = fs::read_dir(&file_path) {
                if entries.next().is_none() {
                    if fs::remove_dir(&file_path).is_ok() {
                        info!(
                            "[RingBuffer] Removed empty folder: {:?}",
                            file_path.file_name().unwrap_or_default()
                        );
                        if let Some(parent) = file_path.parent() {
                            file_path = parent.to_path_buf();
                        } else {
                            break;
                        }
                    } else {
                        break;
                    }
                } else {
                    break;
                }
            } else {
                break;
            }
        }
    }

    #[allow(clippy::collapsible_if)]
    pub fn enforce_limit(&self) {
        let mut all_files_info = Vec::new();
        let mut total_size: u64 = 0;

        let mut dirs_to_visit = vec![self.base_directory.clone()];

        while let Some(dir) = dirs_to_visit.pop() {
            if let Ok(entries) = fs::read_dir(dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.is_dir() {
                        dirs_to_visit.push(path);
                    } else if path.is_file() {
                        if let Ok(metadata) = entry.metadata() {
                            let size = metadata.len();
                            total_size += size;
                            if !self.is_protected(&path) {
                                let mtime = metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH);
                                all_files_info.push((path, mtime, size));
                            }
                        }
                    }
                }
            }
        }

        all_files_info.sort_by_key(|k| k.1);

        let mut files_iter = all_files_info.into_iter();

        while total_size > self.max_storage_bytes {
            if let Some((oldest_file, _, file_size)) = files_iter.next() {
                if fs::remove_file(&oldest_file).is_ok() {
                    total_size = total_size.saturating_sub(file_size);
                    info!(
                        "[RingBuffer] Deleted {:?} ({:.2} MB) to free space",
                        oldest_file.file_name().unwrap_or_default(),
                        file_size as f64 / 1024.0 / 1024.0
                    );
                    self.remove_empty_parents(oldest_file);
                } else {
                    // Try to subtract it anyways
                    total_size = total_size.saturating_sub(file_size);
                }
            } else {
                break;
            }
        }
    }
}
