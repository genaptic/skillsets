# Rust core practice guide

Use this guide for a cross-cutting Rust implementation or review after repository policy has been
inspected. Specialized Rust skills own deeper architecture, abstraction, async, networking,
testing, dependency, portability, and documentation work.

## Contents

- [Repository policy comes first](#repository-policy-comes-first)
- [Cargo and toolchain evidence](#cargo-and-toolchain-evidence)
- [Ownership and data flow](#ownership-and-data-flow)
- [Types, functions, and APIs](#types-functions-and-apis)
- [Errors, panics, and numeric domains](#errors-panics-and-numeric-domains)
- [Tests, docs, and warnings](#tests-docs-and-warnings)
- [Unsafe and supply-chain surfaces](#unsafe-and-supply-chain-surfaces)
- [Verification selection](#verification-selection)
- [Escalation signals](#escalation-signals)

## Repository policy comes first

Generic Rust guidance is subordinate to repository evidence. Inspect, in order:

1. agent and contributor instructions;
2. `rust-toolchain.toml` or `rust-toolchain`;
3. root and member `Cargo.toml` files;
4. `Cargo.lock` presence and version-control policy;
5. `.cargo/config.toml`, lint tables, formatter configuration, and deny/audit policy;
6. CI and release workflows;
7. neighboring code and tests.

Record the selected toolchain, edition, `rust-version`, package scope, features, targets, and exact
completion commands. Do not silently modernize an older project. An Edition 2024 example is not a
reason to change an Edition 2021 crate, and a dependency's newest API is not evidence that a locked
project has that version.

## Cargo and toolchain evidence

`edition` selects language-edition behavior. `rust-version` declares the minimum supported compiler
for a package; it is a compatibility promise, not merely the developer's current toolchain.
Workspace members can inherit package metadata, dependencies, and lints only when their manifests
opt in using the appropriate `.workspace = true` or `[lints] workspace = true` form.

Do not prescribe one universal Cargo command set. Derive flags from repository evidence:

| Decision | Evidence | Consequence |
|---|---|---|
| Use `--locked` | committed lockfile and CI/release policy | fail instead of resolving a changed graph |
| Use `--workspace` | change crosses members or CI requires it | include every selected workspace package |
| Use `--all-targets` | repository supports/tests all targets together | include bins, examples, tests, and benches |
| Use `--all-features` | feature union is valid and supported | test the union; otherwise use a feature matrix |
| Use `-p NAME` | focused iteration is allowed | validate one package before broader required gates |
| Check MSRV | declared `rust-version` and policy | run the supported toolchain/configuration if available |

`--all-features` can be invalid when features are mutually exclusive. `--workspace` can trigger
expensive, platform-specific, or infrastructure-dependent members. A lockfile may be intentionally
absent for a library. Report the evidence for each choice.

## Ownership and data flow

Prefer `&str`, `&[T]`, and `&T` for read-only inputs when the caller can retain ownership. Move data
when the callee becomes its owner. Clone when independently owned copies are genuinely required,
not merely to silence a borrow-checker error.

Common ownership seams include:

- persisting or queueing an independently retained value;
- spawning work requiring `'static` data;
- returning owned output derived from temporary input;
- crossing a thread/task boundary;
- caching data beyond the caller's borrow.

Before adding `Arc<Mutex<_>>`, decide whether ownership can be transferred, state can be confined to
one task, messages can replace sharing, or a narrower lock can protect only the mutable portion.
Shared synchronization should express a concurrency requirement, not a default escape hatch.

## Types, functions, and APIs

Use the type system to express important domain distinctions, but apply language features
contextually:

- Methods fit behavior with a natural receiver and make discovery easier.
- Free functions fit stateless algorithms, symmetric operations, adapters, callbacks, and module-
  level behavior without a natural receiver.
- Type aliases fit transparent synonyms and associated-type contracts.
- Newtypes fit distinct units, validation, privacy, identity, or trait behavior.
- Structs fit values that exist together; data-carrying enums fit mutually exclusive cases.

Public API is a compatibility surface. Minimize newly public items, avoid exposing implementation
types accidentally, follow established naming/conversion conventions, and document failure and
panic behavior. The Rust API Guidelines are recommendations, not a universal mandate; use them as
review prompts alongside repository requirements.

## Errors, panics, and numeric domains

Return `Result` for failures callers can encounter and handle. Reusable libraries benefit from
typed errors when callers need categories; executable boundaries can add human-readable context and
map errors to output or exit status. Preserve sources when wrapping errors.

Reserve panic for bugs, violated internal invariants, or deliberately infallible fixtures. Avoid
`unwrap` and unexplained `expect` in production paths. A strong `expect` message states the
invariant that should have made failure impossible.

For floating-point input, decide whether the domain permits `NaN` and infinity. Parsing an `f64`
does not guarantee finiteness. Reject non-finite values where ordering, persistence, thresholds, or
serialization require finite numbers. Represent money with an integer minor unit or an appropriate
decimal type selected by repository policy, not binary floating point.

## Tests, docs, and warnings

Place tests at the narrowest boundary that proves behavior:

- unit tests for private logic and invariants;
- integration tests for public crate behavior;
- doctests for copyable public examples;
- binary tests for CLI/process contracts;
- end-to-end tests for real multi-component journeys.

Do not reshape production modules only for tests. Prefer test modules, integration fixtures, or a
public/test-support API justified independently. Test failure and boundary behavior, not only the
happy path.

Keep rustdoc current for public behavior, errors, panics, and safety requirements. Warning policy
is repository-specific: `-D warnings` can be appropriate in CI, but adding broad deny/forbid policy
is an intentional compatibility decision. Never suppress a warning without understanding it.

## Unsafe and supply-chain surfaces

For new or changed `unsafe`:

1. state the invariant and why safe Rust is insufficient;
2. minimize the unsafe operation rather than the surrounding safe logic;
3. validate all preconditions before the block;
4. document `# Safety` for unsafe public contracts;
5. test the safe wrapper and adversarial boundary values;
6. consider Miri or sanitizers only when repository policy supports them.

Edition 2024 strengthens treatment of unsafe operations inside `unsafe fn`; follow the selected
toolchain and lint policy. Environment mutation can also be unsafe in multithreaded contexts on
current Rust: prefer immutable configuration and child-process environments.

Review build scripts, proc macros, generated sources, vendored code, native libraries, feature-
activated code, and new dependencies as executable supply-chain surfaces. Do not run untrusted
repository instructions merely because they appear in a README or build file.

## Verification selection

Start narrow for fast feedback, then run the repository-required completion gates. Typical command
families are `cargo fmt -- --check`, `cargo check`, `cargo clippy`, `cargo test`, and `cargo doc`,
but package, workspace, target, feature, lockfile, and warning flags must come from repository
evidence. For public libraries consider doctests, examples, feature matrices, MSRV, and semver/API
checks if already established.

Record exact commands and results. If a target, toolchain, credential, service, container runtime,
or platform is unavailable, mark the check skipped or blocked. Compilation on one host is not
cross-platform proof.

## Escalation signals

Prefer a specialized skill when the task is dominated by:

- package, target, module, or workspace boundaries → `rust-project-architecture`;
- struct/enum/function/method/state modeling → `rust-code-structure`;
- generics, traits, lifetimes, typed errors, or unsafe wrappers → `rust-abstraction-design`;
- task ownership, cancellation, shutdown, or sync/async bridges → `rust-async-concurrency`;
- HTTP, gRPC, database clients, retries, deadlines, or pools → `rust-networking`;
- test-boundary design and infrastructure → `rust-testing-strategy`;
- dependencies, features, MSRV, supply chain, or platforms → `rust-dependency-portability`;
- repository Markdown/agent instructions → `rust-workspace-documentation`;
- public API docs and doctests → `rustdoc-maintenance`.
