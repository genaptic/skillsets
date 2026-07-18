# Dependency and portability sources

Recheck registry, crate, advisory, version-sensitive API, and client data at execution time against
current official documentation and the target lockfile.

- [Agent Skills specification](https://agentskills.io/specification) — portable skill structure
  and progressive disclosure.
- [Codex skills](https://developers.openai.com/codex/build-skills) — current Codex discovery and
  authoring guidance.
- [Claude Code skills](https://code.claude.com/docs/en/skills) — current Claude Code skill format
  and behavior.
- [OpenCode skills](https://opencode.ai/docs/skills/) — current OpenCode skill discovery and
  frontmatter guidance.

- [Cargo `rust-version`](https://doc.rust-lang.org/cargo/reference/rust-version.html) — MSRV field,
  resolver interaction, and support expectations.
- [Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html) — members, default
  members, shared lockfile, dependency inheritance, and lint inheritance.
- [Cargo features](https://doc.rust-lang.org/cargo/reference/features.html) — additive features,
  optional dependencies, and feature unification.
- [Cargo dependency specification](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html)
  — version, workspace, optional, feature, and target-specific declarations.
- [Cargo resolver](https://doc.rust-lang.org/cargo/reference/resolver.html) — dependency and feature
  resolution behavior.
- [Rust 2024 Cargo resolver](https://doc.rust-lang.org/edition-guide/rust-2024/cargo-resolver.html)
  — resolver 3 and rust-version-aware fallback.
- [Rust 2024 newly unsafe functions](https://doc.rust-lang.org/edition-guide/rust-2024/newly-unsafe-functions.html)
  — `set_var`/`remove_var` multithreading constraints.
- [Rust conditional compilation](https://doc.rust-lang.org/reference/conditional-compilation.html) —
  target `cfg` behavior.
- [Rust `Path`](https://doc.rust-lang.org/std/path/struct.Path.html) — platform path semantics.
- [Rust `Command`](https://doc.rust-lang.org/std/process/struct.Command.html) — argument-based child
  process construction and child environment.
- [rustup cross-compilation](https://rust-lang.github.io/rustup/cross-compilation.html) — target
  standard libraries and external linker/SDK requirements.
- [`directories::ProjectDirs`](https://docs.rs/directories/latest/directories/struct.ProjectDirs.html)
  — optional typed application directory discovery; use only when repository-approved.
- [RustSec advisory database](https://rustsec.org/) — time-sensitive Rust ecosystem advisories.
