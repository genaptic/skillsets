# Changelog

All notable repository-level changes are documented here. Individual pack changes are
recorded in each pack's `CHANGELOG.md`.

The format follows Keep a Changelog principles, and pack versions follow Semantic Versioning.

## [Unreleased]

### Added

- Genaptic Skillsets identity and independently versioned monorepo architecture.
- Canonical skillpack manifest and JSON Schema.
- Claude Code and Codex plugin/marketplace generation.
- Direct and OpenCode installation adapters.
- Repository validation, structural eval, compatibility, and release tooling.
- Python and Rust best-practices and CLI packs, plus the PostgreSQL database pack.
- Twelve repository-aware Rust skills covering implementation, architecture, code structure,
  abstractions, async systems, networking, testing, dependencies, documentation, rustdoc, and
  command-line application development.
- Repository-development workflows for creating one skill in an existing pack or a complete,
  independently installable skillpack.
- Validated repository-local request contracts and preview-first scaffold helpers.
- GitHub Pages generation and deployment, DCO and dependency review, hardened release
  publication with provenance verification, and solo-maintainer repository protection.

### Changed

- Hardened optional `gh skill` installers with capability preflights and scoped telemetry,
  prompting, and update-notifier controls.
- Enforced Rust asset classification and executable checks through the locked, offline behavior
  harness without installing or upgrading a Rust toolchain.
- Made generation, validation, and release resource handling fail closed on links, junctions,
  special files, unsafe ancestors, and detected namespace changes.
- Normalized cache and credential filename filtering across case and Unicode compatibility
  variants while preserving allowed resource names and bytes.
- Validated complete repository configuration and portable Git branch names before the first
  configuration write.
- Redirected CI bytecode compilation to runner-owned temporary storage and clarified the
  one-skill versus independently installable one-skill-pack routing boundary.
- Made every required workflow instantiate on every pull request and documented the stable
  twelve-check protection contract without changing any pack version or publication state.

No repository-wide version has been released. Each pack maintains its own changelog and
Semantic Version.
