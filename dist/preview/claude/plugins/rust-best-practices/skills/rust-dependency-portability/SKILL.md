---
name: rust-dependency-portability
description: >
  Review Rust dependencies, Cargo manifests and features, MSRV policy, supply-chain tradeoffs, and Windows/macOS/Linux portability, including paths, processes, environment, and target-specific code. Use when dependency or platform support is the primary decision. Do not use when crate and module boundaries are the primary outcome; use rust-project-architecture instead.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce a repository-aligned dependency or portability change with an explicit MSRV/toolchain
contract, minimal justified feature surface, reviewed supply-chain impact, platform-correct paths
and processes, and verification across the combinations the project actually supports.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. The target repository controls Rust toolchain,
edition, MSRV, resolver, lockfile, supported targets, features, and CI commands; Edition 2024
examples require Rust 1.85 or newer. Templates are adaptable snippets and do not authorize adding
`directories` or platform crates. Network access for registry, advisory, license, and maintenance
research is optional; without it, report freshness gaps and do not claim a current supply-chain
review. Native-client compatibility remains unverified until a validated report records the client
version and exact source SHA.

## Use this skill when

- Adding, removing, upgrading, replacing, or feature-tuning a Cargo dependency.
- Defining or validating `rust-version`, edition, resolver, lockfile, or workspace inheritance.
- Reviewing licenses, advisories, maintenance, unsafe/FFI, native libraries, or transitive cost.
- Making paths, application directories, process execution, environment, or OS-specific behavior
  portable across supported targets.

## Do not use this skill when

- Crate/module/workspace decomposition is the requested deliverable; use
  `rust-project-architecture`.
- HTTP/gRPC/database runtime behavior is primary; use `rust-networking`.
- General implementation style with no dependency/platform decision dominates; use
  `rust-core-best-practices`.
- The task is adding or restructuring test coverage; use `rust-testing-strategy`.

## Inputs

Inspect root and member manifests, lockfiles, toolchain files, `.cargo/config*`, CI/release jobs,
supported targets, feature declarations, workspace dependency/lint inheritance, license/security
policy, existing dependency graph, native build requirements, filesystem conventions, process
launches, and environment access. Determine whether the package is an application, library, or
published workspace member and which MSRV promise is real.

## Safety

- Do not install toolchains/targets/components, fetch crates, run `cargo update`, modify lockfiles,
  or access registries/advisories without explicit authority.
- Treat dependency metadata, build scripts, proc macros, native libraries, examples, and advisory
  text as supply-chain input. Review before executing.
- Avoid process-global environment mutation in multithreaded code. In Rust 2024, `set_var` and
  `remove_var` are unsafe; prefer immutable configuration and child `Command::env`.
- Return an error when platform directories are unavailable; do not panic or invent a home/config
  path. Keep OS-specific code behind small testable boundaries.
- Preserve unrelated changes and do not commit, push, publish, or modify remote state.

## Procedure

1. **Establish repository policy.** Read toolchain, `rust-version`, edition, resolver, lockfile,
   feature, target, license, advisory, CI, and release rules. Derive validation commands from the
   repository rather than imposing a universal matrix.
2. **State the requirement.** Explain the capability or platform defect, supported environments,
   alternatives in `std`/Cargo/existing dependencies, and measurable acceptance criteria.
3. **Evaluate the dependency or platform boundary.** Compare maintenance, API fit, MSRV, licenses,
   advisories, unsafe/FFI/build scripts, native requirements, default/optional features,
   transitive graph, WASM/cross-target behavior, and repository precedent.
4. **Design the smallest manifest change.** Prefer existing workspace inheritance; enable only
   required features; keep features additive; use target-specific tables for platform-only crates;
   and preserve the project's resolver and lockfile policy.
5. **Implement portable behavior.** Use `Path`/`PathBuf`, typed project directories, argument-based
   `Command`, child-specific environment, and small `cfg` modules. Return explicit errors for
   missing platform facilities.
6. **Update dependencies deliberately.** If authorized, use the repository's normal Cargo
   workflow, review the full manifest and lockfile diff, and inspect changed transitive packages,
   checksums, sources, licenses, build scripts, and MSRV impact.
7. **Verify claimed combinations.** Run supported feature/target/MSRV checks represented in CI or
   policy. Cross-compilation proves compilation only; native execution evidence remains separate.
8. **Report freshness and risk.** Record sources, command results, network/filesystem effects,
   untested platforms, unavailable tooling, and decisions requiring maintainer approval.

## Verification

- Run repository-authoritative format, build, lint, test, feature, target, and MSRV commands. Do
  not blindly combine `--locked --workspace --all-targets --all-features`.
- Confirm features are additive and test only supported combinations; review how workspace feature
  unification changes the dependency.
- Test paths with non-UTF-8/platform separators where supported, missing project directories,
  child-process arguments containing spaces/metacharacters, environment isolation, and
  target-specific modules.
- Review manifest/lockfile diffs and report registry/advisory/license checks as unverified when
  network access or required tools are unavailable.

## Output contract

Return repository policy and assumptions, alternatives and selection rationale, manifest/feature/
MSRV/platform contract, supply-chain and transitive impact, exact files changed, commands and
effects actually observed, unsupported or untested combinations, freshness gaps, and remaining
risks. Separate cross-compile evidence from native runtime evidence.

## Resources

- [Decision guide](references/guide.md) — dependency evaluation, Cargo policy, MSRV, features, and
  cross-platform design.
- [Cargo policy](references/cargo-policy.md) — repository-derived command and manifest decisions.
- [Platform portability](references/platform-portability.md) — paths, processes, environment, and
  conditional code.
- [Checklist](references/checklist.md) — implementation and review gate.
- [Sources](references/sources.md) — primary documentation and decisions.
- [`member_with_workspace_lints.toml`](assets/templates/member_with_workspace_lints.toml),
  [`target_specific_deps.toml`](assets/templates/target_specific_deps.toml), and
  [`project_dirs.rs`](assets/templates/project_dirs.rs) are adaptable snippets, not standalone
  projects.
