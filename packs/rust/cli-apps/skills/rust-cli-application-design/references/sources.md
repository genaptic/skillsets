# Primary sources for Rust CLI applications

Use the target repository's pinned versions and policies. Recheck version-sensitive APIs against
current primary documentation when network access is allowed; otherwise report the freshness gap.

## Rust and Cargo

- [Rust command-line applications](https://www.rust-lang.org/what/cli/)
- [Command Line Applications in Rust](https://rust-cli.github.io/book/)
- [`std::process::ExitCode`](https://doc.rust-lang.org/std/process/struct.ExitCode.html)
- [`std::path`](https://doc.rust-lang.org/std/path/)
- [`std::fs::rename`](https://doc.rust-lang.org/std/fs/fn.rename.html)
- [Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html)
- [Cargo features](https://doc.rust-lang.org/cargo/reference/features.html)
- [Cargo `rust-version`](https://doc.rust-lang.org/cargo/reference/rust-version.html)

## Common ecosystem interfaces

These are references, not dependency requirements:

- [clap derive reference](https://docs.rs/clap/latest/clap/_derive/)
- [clap command-line UX guidance](https://docs.rs/clap/latest/clap/_cookbook/)
- [clap completion generation](https://docs.rs/clap_complete/latest/clap_complete/)
- [thiserror](https://docs.rs/thiserror/latest/thiserror/)
- [anyhow](https://docs.rs/anyhow/latest/anyhow/)
- [tracing-subscriber](https://docs.rs/tracing-subscriber/latest/tracing_subscriber/)
- [directories](https://docs.rs/directories/latest/directories/)
- [assert_cmd](https://docs.rs/assert_cmd/latest/assert_cmd/)
- [assert_fs](https://docs.rs/assert_fs/latest/assert_fs/)

## Skill portability

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex skills](https://developers.openai.com/codex/build-skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [OpenCode skills](https://opencode.ai/docs/skills/)

Do not silently upgrade a target repository or introduce any listed crate. Confirm current local
versions, licenses, MSRV, features, and repository authorization before dependency changes.
