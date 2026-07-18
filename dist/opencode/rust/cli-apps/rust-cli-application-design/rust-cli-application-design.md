---
name: rust-cli-application-design
description: >
  Design, implement, review, or refactor a portable Rust command-line application across grammar,
  runtime architecture, domain boundaries, paths, configuration, output, errors, completions, and
  tests. Use when the overall CLI contract or several cross-cutting command concerns are in scope.
  Do not use for adding or changing exactly one command in an established CLI or for non-CLI Rust.
license: Apache-2.0
metadata:
  skillpack: "rust-cli-apps"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce a repository-aligned CLI design or change whose user-visible grammar is intentional, whose
runtime and domain boundaries are clear, whose filesystem and output behavior is safe for scripts and
humans, and whose verification evidence matches what actually ran.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Use the target repository's Rust toolchain, MSRV,
edition, lockfile, feature, target, and CI policy; Edition 2024 examples require Rust 1.85 or newer.
The workflow may use current primary documentation when network access is allowed, but must continue
with an explicit freshness gap when it is not. Native-client compatibility remains unverified until a
dated report records the client version and exact source commit.

## Use this skill when

- Designing a new Rust CLI or restructuring its parser, application runtime, command dispatch, domain
  boundary, configuration, or output model.
- Reviewing or refactoring several commands for consistent grammar, errors, paths, logging,
  completions, automation output, or cross-platform behavior.
- Establishing a testable CLI contract across help, exit status, stdout/stderr, filesystem effects,
  configuration precedence, and end-to-end behavior.

## Do not use this skill when

- The task is to add or change exactly one command in an existing CLI with an established design; use
  `rust-cli-command-development`.
- The task is a generic Rust library, service, GUI, or build-system change without a CLI surface.
- The user asks only for a parser syntax explanation or a narrow copyedit to help text.
- The requested operation is publishing, packaging a release, or performing remote Git actions.

## Inputs

Inspect repository instructions; all Cargo, toolchain, and configuration files; existing binary and
library targets; parser and dispatch code; output and error adapters; filesystem and configuration
layers; tests, fixtures, docs, and CI. Extract users, automation consumers, grammar, compatibility,
side effects, destructive operations, output formats, exit semantics, and migration constraints from
the request. Never assume clap, async dispatch, a crate layout, or a command vocabulary before
discovering the existing architecture.

## Safety

Begin read-only and preserve unrelated changes. Commands and examples must not install toolchains or
dependencies, use hidden network access, expose credentials, publish, or alter remote state. Treat
deletion, overwrite, migration, shell execution, config mutation, and live integration tests as
explicitly authorized effects. Use exact target containment, previews, confirmations, rollback or
recovery design, and adversarial tests for destructive paths. Never imply that rename alone provides
cross-platform crash durability or metadata preservation.

## Procedure

1. Discover repository authority: instructions, toolchain/MSRV, manifests, existing grammar, parser,
   dispatch, domain ownership, output/error policy, tests, and validation commands.
2. Define the CLI contract before code: users, verbs/nouns, inputs, defaults, precedence, stdout,
   stderr, exit status, filesystem/network effects, stability, and compatibility.
3. Preview the architecture and command matrix, including parser-to-domain flow, destructive effects,
   migration impact, and proof for each major choice.
4. Keep parsing separate from runtime initialization and business behavior. Extend the repository's
   existing parser and dispatch pattern instead of imposing a generic `App` or command trait.
5. Keep domain APIs independent from parser types, terminal rendering, process exits, and global
   mutable state. Prefer typed requests, outputs, and library errors.
6. Implement path, config, output, logging, and failure behavior with explicit platform and automation
   contracts. Return `ExitCode` from `main`; never exit inside domain or command layers.
7. Add layered tests for parsing/help, domain behavior, command execution, streams/exit codes,
   filesystem effects, and portable end-to-end scenarios.
8. Run repository-authoritative checks, inspect the final diff, and report skipped features,
   platforms, tools, or live services without converting absence into a pass.

Use [Architecture](references/architecture.md), [Grammar](references/grammar.md),
[Filesystem and output safety](references/filesystem-output-safety.md),
[Testing](references/testing.md), and [End-to-end example](references/end-to-end-example.md) as
independent, shallow references.

## Verification

- Exercise root and nested help, parse failures, success/failure exit status, stdout/stderr separation,
  machine output, path edge cases, configuration precedence, and authorized filesystem effects.
- Run the narrowest repository-defined checks first, then broader package/workspace checks when safe.
  Discover package, feature, target, and lockfile flags rather than imposing all-target/all-feature
  combinations.
- Verify destructive-path refusal against root, home, repository/worktree, ancestors, symlinks,
  dangling paths, and ownership mismatches when relevant.
- Report exact commands and outcomes. Structural validation, native CLI smoke, and model-backed
  behavior evidence are separate claims.

## Output contract

Return discovered architecture and constraints, the user-visible command/output contract, decisions
and alternatives, affected layers, safety controls, implemented or proposed changes, tests and exact
results, compatibility gaps, migration notes, and remaining risks.

## Resources

- [Guide](references/guide.md) — ordered design and review workflow
- [Checklist](references/checklist.md) — architecture, safety, UX, and verification gates
- [Sources](references/sources.md) — primary Rust, Cargo, clap, and CLI documentation
- [Architecture](references/architecture.md) — parser/runtime/domain boundaries
- [Grammar](references/grammar.md) — verbs, options, precedence, help, and compatibility
- [Filesystem and output safety](references/filesystem-output-safety.md) — paths, replacement,
  deletion, streams, config, and recovery
- [Finite bounded number](assets/templates/finite_bounded_number.rs) — executable non-monetary
  parser that rejects invalid bounds and non-finite values
- [Removal preview](assets/templates/removal_preview.rs) — executable read-only containment,
  ownership, protected-path, and symlink checks with no deletion API
- [Testing](references/testing.md) — layered and cross-platform test strategy
- [End-to-end example](references/end-to-end-example.md) — adaptable thin CLI design
