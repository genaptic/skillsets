// Adaptable platform-directory snippet that returns an error instead of panicking or guessing.

use std::{error::Error, fmt, path::PathBuf};

use directories::ProjectDirs;

#[derive(Debug)]
struct ProjectDirectoryUnavailable;

impl fmt::Display for ProjectDirectoryUnavailable {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("standard project directories are unavailable on this platform")
    }
}

impl Error for ProjectDirectoryUnavailable {}

fn config_dir() -> Result<PathBuf, ProjectDirectoryUnavailable> {
    config_dir_from(ProjectDirs::from(
        "com",
        "Example Organization",
        "Example Application",
    ))
}

fn config_dir_from(
    project_directories: Option<ProjectDirs>,
) -> Result<PathBuf, ProjectDirectoryUnavailable> {
    project_directories
        .map(|directories| directories.config_dir().to_path_buf())
        .ok_or(ProjectDirectoryUnavailable)
}
