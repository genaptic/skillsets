// Adaptable, read-only preview for one application-owned directory removal.
//
// This module deliberately exposes no delete operation. A caller must review the preview, obtain
// explicit authorization, then re-run equivalent containment, ownership, protected-path, and
// symlink checks immediately before using a separately reviewed removal implementation.

use std::{
    ffi::OsStr,
    fmt, fs, io,
    path::{Component, Path, PathBuf},
};

#[derive(Debug)]
struct RemovalPreview {
    resolved_target: PathBuf,
    entries: usize,
}

#[derive(Debug)]
enum RemovalPreviewError {
    InvalidPath,
    OutsideAuthorizedParent,
    ProtectedTarget,
    Symlink,
    NonDirectory,
    NonRegularEntry,
    MissingOwnership,
    OwnershipMismatch,
    Io(io::Error),
}

fn preview_owned_directory(
    target: &Path,
    authorized_parent: &Path,
    protected_paths: &[PathBuf],
    ownership_marker: &OsStr,
    expected_marker: &[u8],
) -> Result<RemovalPreview, RemovalPreviewError> {
    if !is_absolute_normal_path(target)
        || !is_absolute_normal_path(authorized_parent)
        || !is_single_normal_component(ownership_marker)
    {
        return Err(RemovalPreviewError::InvalidPath);
    }

    if target == authorized_parent || !target.starts_with(authorized_parent) {
        return Err(RemovalPreviewError::OutsideAuthorizedParent);
    }

    reject_symlink_components(authorized_parent, target)?;
    let parent = fs::canonicalize(authorized_parent).map_err(RemovalPreviewError::Io)?;
    let resolved_target = fs::canonicalize(target).map_err(RemovalPreviewError::Io)?;
    if resolved_target == parent || !resolved_target.starts_with(&parent) {
        return Err(RemovalPreviewError::OutsideAuthorizedParent);
    }

    for protected in protected_paths {
        if !is_absolute_normal_path(protected) {
            return Err(RemovalPreviewError::InvalidPath);
        }
        let resolved_protected = fs::canonicalize(protected).map_err(RemovalPreviewError::Io)?;
        if resolved_target == resolved_protected || resolved_protected.starts_with(&resolved_target)
        {
            return Err(RemovalPreviewError::ProtectedTarget);
        }
    }

    let target_metadata =
        fs::symlink_metadata(&resolved_target).map_err(RemovalPreviewError::Io)?;
    if !target_metadata.file_type().is_dir() {
        return Err(RemovalPreviewError::NonDirectory);
    }

    let marker = resolved_target.join(ownership_marker);
    let marker_metadata = fs::symlink_metadata(&marker).map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            RemovalPreviewError::MissingOwnership
        } else {
            RemovalPreviewError::Io(error)
        }
    })?;
    if marker_metadata.file_type().is_symlink() {
        return Err(RemovalPreviewError::Symlink);
    }
    if !marker_metadata.file_type().is_file() {
        return Err(RemovalPreviewError::MissingOwnership);
    }
    if fs::read(&marker).map_err(RemovalPreviewError::Io)? != expected_marker {
        return Err(RemovalPreviewError::OwnershipMismatch);
    }

    let entries = inspect_tree(&resolved_target, &marker)?;
    Ok(RemovalPreview {
        resolved_target,
        entries,
    })
}

fn reject_symlink_components(parent: &Path, target: &Path) -> Result<(), RemovalPreviewError> {
    let relative = target
        .strip_prefix(parent)
        .map_err(|_| RemovalPreviewError::OutsideAuthorizedParent)?;
    let mut current = parent.to_path_buf();
    for component in relative.components() {
        let Component::Normal(name) = component else {
            return Err(RemovalPreviewError::InvalidPath);
        };
        current.push(name);
        if fs::symlink_metadata(&current)
            .map_err(RemovalPreviewError::Io)?
            .file_type()
            .is_symlink()
        {
            return Err(RemovalPreviewError::Symlink);
        }
    }
    Ok(())
}

fn inspect_tree(directory: &Path, ownership_marker: &Path) -> Result<usize, RemovalPreviewError> {
    let mut entries = 0_usize;
    let mut pending = vec![directory.to_path_buf()];
    while let Some(current) = pending.pop() {
        for entry in fs::read_dir(current).map_err(RemovalPreviewError::Io)? {
            let entry = entry.map_err(RemovalPreviewError::Io)?;
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path).map_err(RemovalPreviewError::Io)?;
            let file_type = metadata.file_type();
            let is_ownership_marker = path == ownership_marker;
            if file_type.is_symlink() {
                return Err(RemovalPreviewError::Symlink);
            }
            if file_type.is_dir() {
                pending.push(path);
            } else if !file_type.is_file() {
                return Err(RemovalPreviewError::NonRegularEntry);
            }
            if !is_ownership_marker {
                entries = entries
                    .checked_add(1)
                    .ok_or(RemovalPreviewError::InvalidPath)?;
            }
        }
    }
    Ok(entries)
}

fn is_absolute_normal_path(path: &Path) -> bool {
    path.is_absolute()
        && path
            .components()
            .all(|component| !matches!(component, Component::CurDir | Component::ParentDir))
}

fn is_single_normal_component(value: &OsStr) -> bool {
    let path = Path::new(value);
    matches!(path.components().next(), Some(Component::Normal(_))) && path.components().count() == 1
}

impl fmt::Display for RemovalPreviewError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidPath => formatter.write_str("removal preview path is not normalized"),
            Self::OutsideAuthorizedParent => {
                formatter.write_str("target is outside the authorized parent")
            }
            Self::ProtectedTarget => formatter.write_str("target is a protected path"),
            Self::Symlink => formatter.write_str("target tree contains a symlink"),
            Self::NonDirectory => formatter.write_str("target is not a directory"),
            Self::NonRegularEntry => formatter.write_str("target contains a non-regular entry"),
            Self::MissingOwnership => formatter.write_str("ownership marker is missing"),
            Self::OwnershipMismatch => formatter.write_str("ownership marker does not match"),
            Self::Io(error) => write!(formatter, "removal preview failed: {error}"),
        }
    }
}

impl std::error::Error for RemovalPreviewError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(error) => Some(error),
            _ => None,
        }
    }
}
