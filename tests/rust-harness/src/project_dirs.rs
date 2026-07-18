include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../packs/rust/best-practices/skills/rust-dependency-portability/assets/templates/project_dirs.rs"
));

#[cfg(test)]
mod tests {
    use super::{ProjectDirectoryUnavailable, config_dir, config_dir_from};

    #[test]
    fn discovery_returns_a_result_instead_of_panicking() {
        let result = config_dir();
        assert!(result.is_ok() || matches!(result, Err(ProjectDirectoryUnavailable)));
    }

    #[test]
    fn unavailable_error_is_actionable() {
        assert!(matches!(
            config_dir_from(None),
            Err(ProjectDirectoryUnavailable)
        ));
        assert_eq!(
            ProjectDirectoryUnavailable.to_string(),
            "standard project directories are unavailable on this platform"
        );
    }
}
