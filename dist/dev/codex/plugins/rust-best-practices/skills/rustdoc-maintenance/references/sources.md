# Primary rustdoc sources

Use current primary documentation when network access is permitted. The target repository's declared
toolchain and feature policy remain authoritative for what can actually compile.

## Rustdoc

- [The rustdoc book](https://doc.rust-lang.org/rustdoc/)
- [How to write documentation](https://doc.rust-lang.org/rustdoc/how-to-write-documentation.html)
- [What to include and exclude](https://doc.rust-lang.org/rustdoc/write-documentation/what-to-include.html)
- [Documentation tests](https://doc.rust-lang.org/rustdoc/write-documentation/documentation-tests.html)
- [Intra-doc links](https://doc.rust-lang.org/rustdoc/write-documentation/linking-to-items-by-name.html)
- [Rustdoc lints](https://doc.rust-lang.org/rustdoc/lints.html)
- [`#[doc]` attributes](https://doc.rust-lang.org/rustdoc/write-documentation/the-doc-attribute.html)

## Cargo and language contracts

- [`cargo doc`](https://doc.rust-lang.org/cargo/commands/cargo-doc.html)
- [`cargo test`](https://doc.rust-lang.org/cargo/commands/cargo-test.html)
- [Cargo features](https://doc.rust-lang.org/cargo/reference/features.html)
- [Rust conditional compilation](https://doc.rust-lang.org/reference/conditional-compilation.html)
- [Rust API Guidelines documentation checklist](https://rust-lang.github.io/api-guidelines/documentation.html)

## Skill portability

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex skills](https://developers.openai.com/codex/build-skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [OpenCode skills](https://opencode.ai/docs/skills/)

## Freshness rule

Resolve version-sensitive rustdoc behavior against the repository's toolchain and current primary
pages at execution time. If network access is unavailable, state that online freshness was not
verified; do not silently upgrade the target toolchain or dependencies.
