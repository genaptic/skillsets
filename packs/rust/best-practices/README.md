# Rust Best Practices

Repository-aware workflows for designing, reviewing, testing, documenting, and maintaining
production Rust systems.

## Purpose and boundaries

Use this pack for repository-aware Rust implementation and review across project structure,
types and abstractions, async behavior, networking, testing, Cargo dependencies,
cross-platform behavior, workspace documentation, and public rustdoc. The target
repository's toolchain, MSRV, edition, features, lockfile, architecture, and CI commands
remain authoritative.

Use [`rust-cli-apps`](../cli-apps/README.md) when command-line grammar, application-wide CLI
design, or development of one command is the controlling outcome. This pack does not own
publishing, remote Git operations, production infrastructure mutation, or automatic
dependency and toolchain installation.

## Included skills

| Skill | Focus |
|---|---|
| [`rust-core-best-practices`](skills/rust-core-best-practices/SKILL.md) | Review or implement a general Rust change against repository policy, toolchain constraints, idiomatic ownership, errors, documentation, formatting, linting, and proportionate tests while routing specialized concerns to narrower skills. |
| [`rust-project-architecture`](skills/rust-project-architecture/SKILL.md) | Design or review Rust package, crate, target, module, library and binary boundaries, workspace membership, dependency direction, and test placement without imposing a fixed project layout. |
| [`rust-code-structure`](skills/rust-code-structure/SKILL.md) | Structure Rust code around cohesive structs, data-carrying enums, functions, methods, constructors, builders, state transitions, and meaningful domain types without banning valid free functions or type aliases universally. |
| [`rust-abstraction-design`](skills/rust-abstraction-design/SKILL.md) | Choose and review concrete code, generics, traits, trait objects, enums, lifetimes, conversions, error types, and abstraction boundaries while avoiding both premature abstraction and duplicated contracts. |
| [`rust-async-concurrency`](skills/rust-async-concurrency/SKILL.md) | Design or review async Rust task ownership, bounded concurrency, cancellation safety, graceful shutdown, streams, synchronization, LocalSet usage, and sync-to-async bridges without blocking executor threads. |
| [`rust-networking`](skills/rust-networking/SKILL.md) | Design or review Rust HTTP, gRPC, and database client boundaries, connection reuse, timeouts, deadlines, retries, backpressure, pools, transport data, error bodies, redaction, and deployment budgets. |
| [`rust-testing-strategy`](skills/rust-testing-strategy/SKILL.md) | Plan, implement, or review Rust unit, integration, doctest, binary-smoke, CLI, live-dependency, and end-to-end tests with correct placement, realistic boundaries, safe fixtures, and honest environment requirements. |
| [`rust-dependency-portability`](skills/rust-dependency-portability/SKILL.md) | Review or change Cargo dependencies, versions, features, workspace inheritance, lockfile policy, MSRV, supply-chain controls, and portable path, process, environment, and target-specific behavior across platforms. |
| [`rust-workspace-documentation`](skills/rust-workspace-documentation/SKILL.md) | Reconcile a Rust workspace's human-facing and agent-facing Markdown documentation with the current code, manifests, validation commands, ownership boundaries, and actual skill or instruction inventory. |
| [`rustdoc-maintenance`](skills/rustdoc-maintenance/SKILL.md) | Refresh and verify public Rust crate, module, item, error, panic, safety, and example documentation across discovered public APIs, including runnable doctests and repository-authoritative rustdoc lints. |

## Prerequisites

- Core instructions are portable across Claude Code, Codex, and OpenCode.
- Inspect `rust-toolchain.toml`, `rust-toolchain`, `Cargo.toml`, `Cargo.lock`, repository
  instructions, and CI before choosing commands or language features.
- Bundled Edition 2024 examples require Rust 1.85 or newer. Adapt them to the target
  repository's declared edition and MSRV rather than upgrading the project implicitly.
- Crate-specific examples are adaptable material, not permission to add or update a
  dependency. Confirm APIs against the locked crate versions.

## Tools, network, and side effects

- Local source inspection is the default first step.
- Network access is optional and limited to current primary documentation or dependency
  metadata when the task requires it. Without access, report the resulting freshness gap.
- Skills may propose or make project-scoped edits when requested. Review target paths and
  preserve unrelated changes.
- Cargo, rustfmt, Clippy, rustdoc, test, and audit commands are optional-explicit. Discover
  the repository's authoritative command and feature matrix first.
- The pack performs no external writes, hidden downloads, dependency installation,
  publication, or remote Git action.

## Install, update, and uninstall

<!-- BEGIN GENERATED INSTALL COMMANDS -->
The marketplace source is repository-local and unpublished. Clone this repository and run these commands from its root; remote marketplace installation remains unavailable until the post-release source-SHA update. Run strict repository validation immediately before a local install so ignored cache files are not copied.

### Claude Code

```bash
claude plugin marketplace add .
claude plugin install rust-best-practices@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
claude plugin uninstall rust-best-practices@genaptic-skillsets
claude plugin install rust-best-practices@genaptic-skillsets
```

Uninstall:

```bash
claude plugin uninstall rust-best-practices@genaptic-skillsets
```

### Codex

```bash
codex plugin marketplace add .
codex plugin add rust-best-practices@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
codex plugin remove rust-best-practices@genaptic-skillsets
codex plugin add rust-best-practices@genaptic-skillsets
```

Uninstall:

```bash
codex plugin remove rust-best-practices@genaptic-skillsets
```

### OpenCode or optional direct install

The direct installer uses the public-preview `gh skill` interface. It checks the installed CLI before making changes; `--dry-run`/`-DryRun` does not require or probe `gh`.

No executable remote install command is published before a release SHA is recorded. Inspect the future exact-path operations locally:

```bash
bash dist/install/rust-best-practices.sh --dry-run
```

```powershell
.\dist\install\rust-best-practices.ps1 -DryRun
```

The dry run does not install skills or make a compatibility claim.
<!-- END GENERATED INSTALL COMMANDS -->
## Version and compatibility

Current pack version: `1.0.0`.

Release state: unpublished release candidate.

Expected future tag (not yet created): `rust-best-practices-v1.0.0`.

Guidance honors repository-declared editions, features, lockfiles, targets, and CI.
Crate-specific APIs must be checked against locked versions.

See the root [`COMPATIBILITY.md`](../../../COMPATIBILITY.md) and this pack's compatibility
tests. Paths in this section are relative to the pack location when installed; root links
are intended for the source repository.

## Changelog and migrations

See [`CHANGELOG.md`](CHANGELOG.md). Public skill names are stable API. A rename, removal,
broader permission requirement, or materially changed output contract requires a major
version and migration notes.
