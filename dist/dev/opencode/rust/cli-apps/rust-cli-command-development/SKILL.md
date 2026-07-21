---
name: rust-cli-command-development
description: >
  Add or change exactly one command in an existing Rust CLI by extending its discovered grammar,
  dispatch, domain boundary, effects, output, documentation, and tests. Use when the application
  architecture and installation boundary already exist and one command is the focused public change.
  Do not use for a new CLI, a multi-command redesign, publishing, or generic Rust library work.
license: Apache-2.0
metadata:
  skillpack: "rust-cli-apps"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Deliver one coherent Rust CLI command change that preserves the application's established grammar and
boundaries, implements authorized effects safely, updates the user-visible contract, and reports
focused and end-to-end verification without disturbing unrelated work.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Follow the target repository's parser, sync/async
dispatch, Rust toolchain, MSRV, edition, lockfile, features, targets, and CI policy; Edition 2024
examples require Rust 1.85 or newer. Network access for current primary sources is optional; when it
is unavailable, report the freshness gap. Native-client compatibility remains unverified until a
dated report records the client version and exact source commit.

## Use this skill when

- Adding one new command, subcommand, subject, option, or command behavior to an established Rust CLI.
- Changing one command's grammar, dispatch, domain request, filesystem/network effect, rendering,
  exit behavior, docs, and tests as one vertical slice.
- Repairing a single command whose parser-to-domain integration or public process contract is broken.

## Do not use this skill when

- Designing a new CLI or coordinating a multi-command architecture, output, config, or grammar
  redesign; use `rust-cli-application-design`.
- The task is solely a reusable Rust library operation with no command-line change.
- The requested change spans several independent commands or lacks a coherent existing CLI owner.
- The task is publishing, packaging a release, staging, committing, pushing, or remote Git work.

## Inputs

Inspect repository instructions, manifests, toolchain and CI policy, parser declarations, root and
neighboring command types, dispatch, runtime/context construction, owning domain API, adapters,
renderers, error/exit policy, tests, fixtures, help/docs, and relevant generated surfaces. Extract the
exact invocation, compatibility constraints, inputs, effects, outputs, errors, and success criteria.
Do not assume clap, an `AppCommand` trait, async receivers, fixed paths, or fixed crate names.

## Safety

Start read-only, preview the vertical command diff, and preserve unrelated changes. Do not install
dependencies or toolchains, make hidden network calls, disclose credentials, publish, or alter remote
state. Treat filesystem mutation, overwrite, recursive deletion, migrations, subprocesses, and live
services as explicit effects requiring user authority and repository safeguards. Recheck destructive
targets immediately before mutation. Return `ExitCode` only from `main`; never terminate inside a
domain or command layer.

## Procedure

1. Discover the existing CLI rather than following guessed file paths: parser, grammar, neighboring
   commands, dispatch, runtime, domain owner, output/error adapters, tests, docs, and validation.
2. Write the exact before/after command contract: argv examples, defaults, conflicts, precedence,
   stdout, stderr, exit status, side effects, compatibility, and migration/deprecation behavior.
3. Choose the closest neighboring command and mirror its established shape where that shape remains
   safe. Preview every file/layer to change, required authority, tests, and generated consequences.
4. Extend parser data only. Keep business behavior, clients, and mutable services out of parser types.
5. Extend the discovered dispatch mechanism exhaustively and route through the owning domain or
   adapter boundary with typed input/output/error contracts.
6. Implement authorized effects with explicit path, symlink, ownership, overwrite, interruption,
   credential, timeout, and recovery policies as applicable.
7. Render stable results on stdout and diagnostics on stderr; map errors to exit status at the
   established application boundary.
8. Add parser, domain, integration, process, filesystem, documentation, and E2E coverage proportional
   to the public change. Run repository-authoritative checks and inspect the final diff.

Read [Parser and dispatch](references/parser-dispatch.md),
[Filesystem transactions](references/filesystem-transactions.md),
[Command diff shapes](references/command-diff-shapes.md), and
[Testing](references/testing.md) as needed.

## Verification

- Test the exact invocation, root/nested help, conflicts, defaults, invalid inputs, success/failure
  exit status, stdout/stderr, and output formats.
- Test domain behavior and every authorized filesystem/network/subprocess effect at its owning layer.
- For destructive paths, test root, home, repository/worktree, ancestors, traversal, symlinks,
  ownership, preview, confirmation, concurrent target change, interruption, and recovery.
- Discover focused and broader Cargo/task commands from repository evidence; report exact outcomes and
  unavailable matrices. Never treat structural checks as native/model compatibility evidence.

## Output contract

Return the discovered neighboring pattern, before/after CLI contract, affected layers, safety and
compatibility decisions, implemented change, tests and exact results, documentation/generated impact,
remaining risks, and any skipped source, platform, tool, or live-service evidence.

## Resources

- [Guide](references/guide.md) — end-to-end single-command workflow
- [Checklist](references/checklist.md) — command integration and safety gates
- [Sources](references/sources.md) — primary Rust, Cargo, clap, and testing references
- [Parser and dispatch](references/parser-dispatch.md) — discovery and integration patterns
- [Filesystem transactions](references/filesystem-transactions.md) — mutation and recovery contracts
- [Command diff shapes](references/command-diff-shapes.md) — good and bad vertical slices
- [Testing](references/testing.md) — focused through process-level verification
