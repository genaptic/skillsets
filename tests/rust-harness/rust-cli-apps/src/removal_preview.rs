include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../packs/rust/cli-apps/skills/rust-cli-application-design/assets/templates/removal_preview.rs"
));

#[cfg(test)]
mod tests {
    use std::{
        ffi::OsStr,
        fs,
        path::{Path, PathBuf},
        sync::atomic::{AtomicU64, Ordering},
    };

    use super::{RemovalPreviewError, preview_owned_directory};

    static NEXT_ID: AtomicU64 = AtomicU64::new(0);
    const MARKER: &str = ".genaptic-owned";
    const EXPECTED: &[u8] = b"owned-by-test\n";

    struct Scratch(PathBuf);

    impl Scratch {
        fn new() -> Self {
            let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "genaptic-removal-preview-{}-{id}",
                std::process::id()
            ));
            fs::create_dir(&path).expect("create isolated scratch root");
            Self(path)
        }

        fn owned_target(&self, name: &str) -> (PathBuf, PathBuf) {
            let parent = self.0.join("authorized");
            let target = parent.join(name);
            fs::create_dir_all(&target).expect("create target");
            fs::write(target.join(MARKER), EXPECTED).expect("write ownership marker");
            (parent, target)
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).expect("remove exact test-created scratch root");
        }
    }

    fn preview(target: &Path, parent: &Path) -> Result<super::RemovalPreview, RemovalPreviewError> {
        preview_owned_directory(target, parent, &[], OsStr::new(MARKER), EXPECTED)
    }

    #[test]
    fn valid_owned_target_is_previewed_without_deletion() {
        let scratch = Scratch::new();
        let (parent, target) = scratch.owned_target("target");
        fs::write(target.join("payload.txt"), b"payload").expect("write payload");
        let result = preview(&target, &parent).expect("preview succeeds");
        assert_eq!(
            result.resolved_target,
            fs::canonicalize(&target).expect("canonical target")
        );
        assert_eq!(result.entries, 1);
        assert!(target.is_dir());
    }

    #[test]
    fn parent_outside_and_missing_ownership_are_rejected() {
        let scratch = Scratch::new();
        let (parent, target) = scratch.owned_target("owned");
        assert!(matches!(
            preview(&parent, &parent),
            Err(RemovalPreviewError::OutsideAuthorizedParent)
        ));

        let outside = scratch.0.join("outside");
        fs::create_dir(&outside).expect("create outside directory");
        assert!(matches!(
            preview(&outside, &parent),
            Err(RemovalPreviewError::OutsideAuthorizedParent)
        ));

        fs::remove_file(target.join(MARKER)).expect("remove marker");
        assert!(matches!(
            preview(&target, &parent),
            Err(RemovalPreviewError::MissingOwnership)
        ));
    }

    #[test]
    fn protected_targets_and_protected_descendants_are_rejected() {
        let scratch = Scratch::new();
        let (parent, target) = scratch.owned_target("protected");
        let direct = preview_owned_directory(
            &target,
            &parent,
            std::slice::from_ref(&target),
            OsStr::new(MARKER),
            EXPECTED,
        );
        assert!(matches!(direct, Err(RemovalPreviewError::ProtectedTarget)));

        let protected_child = target.join("active-worktree");
        fs::create_dir(&protected_child).expect("create protected child");
        let ancestor = preview_owned_directory(
            &target,
            &parent,
            &[protected_child],
            OsStr::new(MARKER),
            EXPECTED,
        );
        assert!(matches!(
            ancestor,
            Err(RemovalPreviewError::ProtectedTarget)
        ));
    }

    #[test]
    fn traversal_and_ownership_mismatch_are_rejected() {
        let scratch = Scratch::new();
        let (parent, target) = scratch.owned_target("owned");
        let traversal = target.join("..").join("owned");
        assert!(matches!(
            preview(&traversal, &parent),
            Err(RemovalPreviewError::InvalidPath)
        ));

        fs::write(target.join(MARKER), b"owned-by-someone-else\n")
            .expect("replace marker contents");
        assert!(matches!(
            preview(&target, &parent),
            Err(RemovalPreviewError::OwnershipMismatch)
        ));
    }

    #[test]
    fn canonical_asset_exposes_no_removal_operation() {
        let source = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../packs/rust/cli-apps/skills/rust-cli-application-design/assets/templates/removal_preview.rs"
        ));
        assert!(!source.contains("fs::remove_"));
    }

    #[cfg(unix)]
    #[test]
    fn symlink_components_markers_and_dangling_entries_are_rejected() {
        use std::os::unix::fs::symlink;

        let scratch = Scratch::new();
        let parent = scratch.0.join("authorized");
        let real_component = parent.join("real-component");
        let target = real_component.join("target");
        fs::create_dir_all(&target).expect("create real target");
        fs::write(target.join(MARKER), EXPECTED).expect("write marker");
        symlink(&real_component, parent.join("linked-component"))
            .expect("create component symlink");
        let linked_target = parent.join("linked-component").join("target");
        assert!(matches!(
            preview(&linked_target, &parent),
            Err(RemovalPreviewError::Symlink)
        ));

        fs::remove_file(target.join(MARKER)).expect("remove regular marker");
        let marker_source = scratch.0.join("marker-source");
        fs::write(&marker_source, EXPECTED).expect("write marker source");
        symlink(&marker_source, target.join(MARKER)).expect("create marker symlink");
        assert!(matches!(
            preview(&target, &parent),
            Err(RemovalPreviewError::Symlink)
        ));

        fs::remove_file(target.join(MARKER)).expect("remove marker symlink");
        fs::write(target.join(MARKER), EXPECTED).expect("restore regular marker");
        symlink(target.join("missing"), target.join("dangling")).expect("create dangling symlink");
        assert!(matches!(
            preview(&target, &parent),
            Err(RemovalPreviewError::Symlink)
        ));
    }
}
