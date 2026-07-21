# Primary sources for Rust CLI command development

Resolve version-sensitive details against the target repository's pinned toolchain and dependencies.
Use current primary documentation when network access is allowed; otherwise state the freshness gap.

## Rust, Cargo, and CLI behavior

- [Command Line Applications in Rust](https://rust-cli.github.io/book/)
- [Rust command-line applications](https://www.rust-lang.org/what/cli/)
- [`std::process::ExitCode`](https://doc.rust-lang.org/std/process/struct.ExitCode.html)
- [`std::path`](https://doc.rust-lang.org/std/path/)
- [`std::fs::rename`](https://doc.rust-lang.org/std/fs/fn.rename.html)
- [Cargo command reference](https://doc.rust-lang.org/cargo/commands/index.html)
- [Cargo features](https://doc.rust-lang.org/cargo/reference/features.html)
- [Cargo `rust-version`](https://doc.rust-lang.org/cargo/reference/rust-version.html)

## Common parser and test interfaces

These sources do not authorize adding or upgrading dependencies:

- [clap derive reference](https://docs.rs/clap/latest/clap/_derive/)
- [clap command-line UX guidance](https://docs.rs/clap/latest/clap/_cookbook/)
- [clap completion generation](https://docs.rs/clap_complete/latest/clap_complete/)
- [assert_cmd](https://docs.rs/assert_cmd/latest/assert_cmd/)
- [assert_fs](https://docs.rs/assert_fs/latest/assert_fs/)
- [predicates](https://docs.rs/predicates/latest/predicates/)
- [trycmd](https://docs.rs/trycmd/latest/trycmd/)

## Skill portability

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex skills](https://developers.openai.com/codex/build-skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [OpenCode skills](https://opencode.ai/docs/skills/)

Inspect local versions, features, licenses, MSRV, and repository policy before dependency changes. Do
not silently upgrade the project or treat current online examples as compatible with older pins.
