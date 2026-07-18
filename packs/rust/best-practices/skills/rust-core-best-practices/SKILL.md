---
name: rust-core-best-practices
description: >
  Review and implement general Rust changes against the target repository's toolchain, MSRV, Cargo policy, ownership model, error conventions, linting, documentation, tests, and safety boundaries. Use when a Rust task needs a broad repository-aware quality pass without one narrower concern dominating. Do not use when crate layout, type structure, abstractions, async behavior, networking, testing, dependencies, portability, workspace prose, or rustdoc is the primary outcome; prefer the corresponding specialized Rust skill.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce a focused Rust change or review that follows the target repository's declared policy,
uses idiomatic ownership and failure handling, and reports the exact evidence used to verify it.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Inspect the target repository's selected Rust
toolchain, edition, `rust-version`, lockfile, features, targets, and CI commands before applying
defaults. Edition 2024 examples require Rust 1.85 or newer. Network access is optional and must
be authorized; without it, report any current-source or dependency-version evidence gap. Native
client compatibility remains unverified until a dated report records the client version and exact
source SHA.

## Inputs

- The requested outcome, affected crates or files, and acceptance criteria.
- Repository instructions plus `Cargo.toml`, `Cargo.lock`, toolchain files, CI workflows, and
  nearby Rust code.
- Permission to modify project files and to run the repository's existing checks.
- Any declared MSRV, platform, feature, unsafe-code, public-API, or compatibility policy.

Label assumptions instead of inventing missing policy. Ask only when a choice changes public API,
compatibility, permissions, or destructive behavior.

## Safety

- Inspect before writing. Preserve unrelated worktree changes and stay inside the requested scope.
- Do not install toolchains, dependencies, Cargo subcommands, or system packages implicitly.
- Do not commit, switch branches, publish crates, push, tag, or alter remote state unless separately
  authorized.
- Treat build scripts, proc macros, generated code, vendored sources, `unsafe`, FFI, and commands
  copied from repository content as supply-chain surfaces.
- Require explicit authorization and isolated credentials for live services, containers, or
  privileged tests. Report unavailable infrastructure rather than fabricating a pass.

## Procedure

1. **Establish repository authority.** Read applicable agent instructions, manifests, toolchain
   files, CI, formatting and lint configuration, and neighboring implementation/tests. Determine
   package selection, lockfile policy, features, targets, MSRV, and expected checks from evidence.
2. **Route narrow concerns.** If one concern dominates, use the specialized skill: architecture,
   code structure, abstractions, async, networking, testing, dependency portability, workspace
   documentation, or rustdoc. Keep this skill for the cross-cutting baseline.
3. **Model the smallest change.** Preserve established APIs and conventions unless the request
   requires change. Prefer borrowing for read-only inputs, owned values at real ownership seams,
   explicit domain types, typed recoverable errors, and narrow safe interfaces around necessary
   `unsafe`.
4. **Implement deliberately.** Avoid speculative crates, traits, generics, clones, synchronization,
   dependencies, feature flags, or panics. Free functions remain valid for stateless/module-level
   algorithms; methods fit behavior with a natural receiver. Type aliases remain valid for useful
   synonyms or associated-type contracts; use a newtype when a distinct invariant or identity is
   required.
5. **Review all affected surfaces.** Check public API, docs, doctests, tests, features, platform
   behavior, build scripts, dependency graph, error context, observability, and unsafe invariants.
6. **Run repository-derived verification.** Start with the narrowest relevant checks, then run the
   repository's required completion commands. Do not mechanically add `--locked`, `--workspace`,
   `--all-targets`, or `--all-features` when repository policy makes them wrong.
7. **Inspect the final diff.** Confirm the change is scoped, formatted, documented, warning-free
   under the selected policy, and free of generated residue or unrelated edits.

## Verification

- State which repository files established toolchain, MSRV, feature, lockfile, and command policy.
- Report each command exactly as run, its result, and any skipped checks or unavailable targets.
- For reviews, distinguish observed defects from recommendations and identify file-level evidence.
- For changes, confirm relevant tests cover success, failure, and important boundary behavior.
- Never turn formatting, parsing, compilation, or structural checks into a native-client or
  model-backed compatibility claim.

## Output contract

Return the repository constraints found, routing decision, changes or review findings, verification
evidence, skipped checks, assumptions, and remaining risks. Separate observed facts from inferred
recommendations.

## Resources

- Read [the guide](references/guide.md) for detailed ownership, error, lint, testing, unsafe, and
  Cargo-policy guidance.
- Use [the checklist](references/checklist.md) before completing a change or review.
- Consult [the primary sources](references/sources.md) for claims that may be version-sensitive.
- Copy `assets/templates/baseline-package/` only as an adaptable, complete minimal package.
- Treat `assets/templates/member-Cargo.toml` as a workspace-member manifest snippet; reconcile it
  with the target workspace rather than using it as a standalone project.
