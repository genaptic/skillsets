# Rustdoc maintenance guide

Use this sequence for public Rust API documentation. Keep the audit scoped to exported behavior and
doctestable examples unless the user explicitly combines it with repository Markdown work.

## Contents

- [Establish the public surface](#establish-the-public-surface)
- [Build a documentation matrix](#build-a-documentation-matrix)
- [Write in dependency order](#write-in-dependency-order)
- [Design executable examples](#design-executable-examples)
- [Validate the contract](#validate-the-contract)
- [Review and report](#review-and-report)

## Establish the public surface

1. Read repository instructions, Cargo manifests, toolchain declarations, feature definitions, lint
   configuration, and existing docs commands.
2. Identify the packages, targets, features, and platforms in scope from the request and local
   evidence. Do not equate default features with all supported features.
3. Inventory public crate roots, modules, items, macros, re-exports, associated items, trait methods,
   error types, unsafe APIs, and feature/platform gates.
4. Inspect implementations and tests to understand invariants, failures, panics, side effects,
   complexity, ordering, cancellation, and resource ownership.
5. Identify semver-sensitive claims. Public names, accepted inputs, outputs, error contracts, panic
   conditions, and safety preconditions must not be guessed.

Useful searches include `pub`, `pub use`, `#[cfg`, `#[doc`, `//!`, `///`, `unsafe`, and exported
macros. Respect repository tooling that produces a more accurate public API inventory.

## Build a documentation matrix

For each public surface, record:

| Surface | Audience outcome | Required details | Example | Evidence |
|---|---|---|---|---|
| crate root | why and how to start | purpose, concepts, features | minimal happy path | manifest + API |
| module | responsibility | boundary, key types | representative flow | module + tests |
| function/method | observable action | errors, panics, side effects | focused call | implementation |
| type/trait | semantic role | invariants, ownership, contracts | construction/use | impls + tests |
| unsafe API | allowed operation | complete safety contract | only if safe to copy | invariants |

Classify each current document as correct, stale, incomplete, misleading, or intentionally absent.
Preview the proposed sections and examples before broad edits.

## Write in dependency order

1. Write crate-level `//!` framing so users understand the crate's role and first successful path.
2. Write public module `//!` docs to explain boundaries and relationships not obvious from names.
3. Write item `///` docs with a concise first sentence, then non-obvious semantics and constraints.
4. Update re-export and feature-gate documentation so discoverability matches compilation behavior.
5. Add standard sections only when the contract requires them:
   - `# Errors` for meaningful failure modes of `Result`-returning operations;
   - `# Panics` for reachable panic conditions callers can avoid;
   - `# Safety` for every unsafe function or trait contract;
   - `# Examples` when an example materially improves correct use.
6. Prefer intra-doc links for public Rust items and verify ambiguous names explicitly.

Avoid duplicating signatures, implementation detail, or promises that tests and code do not support.
Do not hide a public footgun with `#[doc(hidden)]`; fix or accurately document the contract.

## Design executable examples

- Demonstrate one user outcome with the smallest complete context.
- Use `Result` plus hidden setup when it keeps the visible example clear.
- Prefer temporary directories and deterministic local inputs for filesystem examples.
- Avoid external services, credentials, wall-clock timing, nondeterministic ordering, and global
  environment mutation.
- Use `no_run` only when compilation is useful but execution requires a real environment boundary.
- Use `compile_fail` to demonstrate rejected usage when compiler failure is the intended lesson.
- Use `ignore` only when no stable compile path exists, and document why the example cannot be
  tested. Never use it as a quick fix.
- Specify feature prerequisites near the example and make the selected validation feature-aware.

See [Examples](examples.md) for patterns.

## Validate the contract

Discover commands from the repository. Depending on its policies, relevant checks may include:

```bash
cargo fmt --all -- --check
cargo doc --no-deps
cargo test --doc
```

These are candidates, not universal prescriptions. Confirm package selection, workspace behavior,
features, targets, lockfile flags, environment variables, and custom task runners before running
them. `cargo doc` and `cargo test --doc` do not prove identical things.

Where the repository enforces rustdoc lints through `RUSTDOCFLAGS`, `[lints.rustdoc]`, CI, or a task
runner, use that canonical entry point. Do not suppress warnings or add broad `allow` attributes just
to make the gate green.

For examples requiring live services or credentials, require explicit authorization, isolate the
environment, and report unavailability. Never silently reuse developer credentials.

## Review and report

Inspect generated documentation when feasible for navigation, first-sentence summaries, re-export
visibility, link targets, and feature-gated discoverability. Review the source diff for:

- stale names or signatures;
- incomplete `Errors`, `Panics`, or `Safety` sections;
- claims that exceed the implementation;
- unnecessary `no_run` or `ignore` markers;
- examples that modify global or durable state;
- unrelated behavior changes or formatting churn.

Report the surface audited, evidence used, exact commands and outcomes, rendered-review status,
skipped feature/platform matrices, and unresolved API ambiguity. Do not label structural checks as
native-client or model-backed evidence.
