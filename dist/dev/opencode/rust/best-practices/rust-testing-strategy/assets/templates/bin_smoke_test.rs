//! Adaptable integration-test snippet for a Cargo-built binary.

use std::{path::Path, process::Command};

fn run_help(binary: &Path) -> std::io::Result<std::process::Output> {
    Command::new(binary)
        .arg("--help")
        .env("NO_COLOR", "1")
        .env_remove("APP_SECRET")
        .output()
}

#[test]
fn help_succeeds_without_secret_output() -> Result<(), Box<dyn std::error::Error>> {
    // Replace `my_cli` with the Cargo binary target name.
    let binary = Path::new(env!("CARGO_BIN_EXE_my_cli"));
    let output = run_help(binary)?;
    let stdout = String::from_utf8(output.stdout)?;
    let stderr = String::from_utf8(output.stderr)?;

    assert!(output.status.success());
    assert!(stdout.contains("Usage:"));
    assert!(!stdout.contains("APP_SECRET"));
    assert!(!stderr.contains("APP_SECRET"));
    Ok(())
}
