---
name: rustdoc-maintenance
description: >
  Refresh public Rust API documentation, crate and module narratives, intra-doc links, examples,
  required safety sections, and doctests against the current implementation. Use when one or more
  Rust crates need coordinated rustdoc review or repair. Do not use for repository Markdown-only
  reconciliation, private implementation comments, or a feature implementation disguised as docs.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Deliver accurate, navigable public API documentation whose examples exercise the supported API,
whose safety and failure contracts match the code, and whose verification evidence is reported
without suppressing warnings or fabricating unavailable runs.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Use the target repository's Rust toolchain, MSRV,
edition, enabled targets, features, and rustdoc lint policy; Edition 2024 examples require Rust 1.85
or newer. Network access is optional for checking current rustdoc guidance. If unavailable, rely on
the installed toolchain and report the freshness limitation. Native-client compatibility remains
unverified until a dated report records the client version and exact source commit.

## Use this skill when

- Public `//!` crate/module documentation, `///` item documentation, intra-doc links, or examples
  drift after an API or behavior change.
- A library needs a coordinated public-surface audit across one or more crates.
- Doctests, rustdoc lints, feature-gated docs, or `# Errors`, `# Panics`, or `# Safety` contracts need
  focused review.
- A no-op rustdoc audit must prove the public documentation still matches current code.

## Do not use this skill when

- The deliverable is README, architecture, contributor, operations, or agent-facing Markdown; use
  `rust-workspace-documentation`.
- The task is a private implementation comment or a narrow prose correction with no public contract
  implications.
- The requested behavior does not exist yet. Implement and test the behavior before documenting it.
- The task is general Rust implementation or test strategy rather than public API documentation.

## Inputs

Inspect repository instructions, manifests and toolchain declarations, public and re-exported API
surfaces, feature and platform gates, current rustdoc, relevant tests, examples, and the repository's
documented validation commands. Determine intended audience and semver-sensitive behavior from local
evidence. Record unavailable features, targets, services, credentials, or network access.

## Safety

Start read-only and preserve unrelated source edits. Rustdoc examples are executable code: do not
include secrets, destructive operations, live network calls, uncontrolled filesystem writes, hidden
dependency installation, or process-global environment mutation. Prefer temporary resources and
offline examples. Never stage, commit, push, publish, alter remote state, or loosen lints merely to
make documentation pass.

## Procedure

1. Read repository instructions and identify the exact public surface and audience in scope.
2. Inventory crate/module narratives, exported items, re-exports, features, platform gates, examples,
   intra-doc links, and required contract sections before editing.
3. Trace each claim to signatures, implementations, invariants, tests, and error types. Flag behavior
   that is ambiguous or undocumented in code rather than guessing.
4. Preview the documentation plan: summaries, detailed semantics, examples, links, safety/failure
   sections, and validation commands.
5. Update crate and module framing first, then public items and examples. Keep the first sentence
   concise and user-oriented; avoid restating type signatures.
6. Make examples runnable by default. Use hidden setup lines for clarity, `no_run` only for genuine
   compile-only/environment boundaries, and `ignore` only with a documented reason.
7. Run repository-authoritative rustdoc, doctest, lint, and formatting checks for relevant features
   and targets; never assume a universal all-features command is valid.
8. Inspect rendered or generated documentation when feasible and review the final diff for stale
   names, broken links, misleading feature claims, and unrelated code changes.

Read [Guide](references/guide.md) for the detailed audit and
[Documentation contracts](references/documentation-contracts.md) for section and example rules.

## Verification

- Confirm every public claim against current signatures, behavior, errors, invariants, and features.
- Run the repository-selected documentation and doctest commands. Consider `cargo doc --no-deps`
  and `cargo test --doc` only when they match the package, workspace, feature, and lockfile policy.
- Treat build success, doctest success, rustdoc lint success, link review, and rendered review as
  separate evidence.
- Report exact commands and outcomes. Mark platform, feature, live-service, and native-client checks
  as unavailable or skipped when they did not run.

## Output contract

Return the audited API surface, documentation changes, behavior-to-claim evidence, example strategy,
exact validation results, rendered-review status, unresolved API ambiguity, and any freshness or
environment limitations. For a no-op result, list the inspected surface and supporting checks.

## Resources

- [Guide](references/guide.md) — public-surface inventory and ordered refresh workflow
- [Checklist](references/checklist.md) — rustdoc review and evidence gates
- [Sources](references/sources.md) — primary rustdoc, Cargo, and Rust references
- [Documentation contracts](references/documentation-contracts.md) — item sections and example rules
- [Examples](references/examples.md) — good, risky, feature-gated, and boundary patterns
