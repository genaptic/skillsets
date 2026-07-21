# Rust testing sources

Recheck version-sensitive APIs and client rules at execution time against the target lockfile,
enabled features, and current official documentation.

- [Agent Skills specification](https://agentskills.io/specification) — portable skill structure
  and progressive disclosure.
- [Codex skills](https://developers.openai.com/codex/build-skills) — current Codex discovery and
  authoring guidance.
- [Claude Code skills](https://code.claude.com/docs/en/skills) — current Claude Code skill format
  and behavior.
- [OpenCode skills](https://opencode.ai/docs/skills/) — current OpenCode skill discovery and
  frontmatter guidance.

- [Rust Book: writing tests](https://doc.rust-lang.org/book/ch11-00-testing.html) — language test
  facilities and test intent.
- [Rust Book: test organization](https://doc.rust-lang.org/book/ch11-03-test-organization.html) —
  unit/private versus integration/public API boundaries.
- [Cargo `test`](https://doc.rust-lang.org/cargo/commands/cargo-test.html) — target selection,
  doctests, working directories, and harness arguments.
- [rustdoc documentation tests](https://doc.rust-lang.org/rustdoc/documentation-tests.html) —
  executable examples, `no_run`, `compile_fail`, and edition annotations.
- [Tokio testing](https://tokio.rs/tokio/topics/testing) — deterministic I/O testing and paused
  time guidance.
- [Tokio time pause](https://docs.rs/tokio/latest/tokio/time/fn.pause.html) — current-thread
  requirement and auto-advance behavior.
- [Tokio test macro](https://docs.rs/tokio/latest/tokio/attr.test.html) — `start_paused` and runtime
  flavor configuration.
- [Rust 2024 newly unsafe functions](https://doc.rust-lang.org/edition-guide/rust-2024/newly-unsafe-functions.html)
  — process environment mutation risks.
- [Testcontainers for Rust](https://rust.testcontainers.org/) — optional container lifecycle and
  runner model; use only when already approved by the repository.
- [Dev Container specification](https://containers.dev/) — optional isolated development/test
  environment contract.
