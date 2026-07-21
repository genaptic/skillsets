# Rust testing decision guide

Use this guide to choose proof boundaries after inspecting the target repository. Tests should
protect behavior, not encode an accidental implementation shape.

## Contents

- [Choose the test level](#choose-the-test-level)
- [Place tests correctly](#place-tests-correctly)
- [Design test seams](#design-test-seams)
- [Test binaries and documentation](#test-binaries-and-documentation)
- [Control nondeterminism](#control-nondeterminism)
- [Handle features and platforms](#handle-features-and-platforms)
- [Use live dependencies safely](#use-live-dependencies-safely)
- [Report evidence honestly](#report-evidence-honestly)
- [Failure modes](#failure-modes)

## Choose the test level

| Level | Proves | Typical location | Dependency policy |
|---|---|---|---|
| Unit | local logic, state transitions, owned collaborator contracts | source-local `#[cfg(test)]` | fakes for dependencies you own |
| Integration | public API across crate modules | package `tests/*.rs` | real in-process code; authorized infrastructure when required |
| Doctest | documented public usage compiles/runs | public doc comments | default offline; `no_run` for explicit external examples |
| Binary smoke | executable CLI/process contract | package `tests/*.rs` | compiled binary with isolated env/filesystem |
| End-to-end | external behavior across processes/services | app boundary or dedicated workspace crate | real isolated dependencies with explicit authority |

Prefer the narrowest level that can fail when the contract is broken. Duplicating the same happy
path at every level adds cost without independent evidence. Use higher levels for integration risk,
not to compensate for missing unit seams.

Unit tests can inspect private implementation details, but prefer stable invariants. Integration
tests should use the same public API available to downstream crates. End-to-end tests should assert
external outcomes and diagnostics, not internal call counts.

## Place tests correctly

Keep local unit tests next to the module they exercise. Rust's `cfg(test)` is enabled for the unit
test build, so those tests may access private items through `super`.

Each file under a package's `tests/` directory is a separate crate. It sees only public APIs and is
appropriate for package integration and binary process tests. Share test support through
`tests/common/mod.rs` or a clearly named support crate; avoid a `tests/common.rs` file that Cargo
will also treat as an independent test target.

Place cross-workspace end-to-end coverage at the application boundary or in a dedicated test crate
only when independent packaging improves ownership. Read workspace `default-members` because a
bare `cargo test` at the root may not select the same packages as `--workspace`.

## Design test seams

Use normal production interfaces for dependencies the project owns. Constructor injection, a
small trait, a generic parameter, or a function argument can make behavior testable without adding
a parallel test-only API.

Avoid production-scope items behind `#[cfg(test)]`:

- test-only fields or constructors;
- test-only trait implementations;
- test-only imports needed by production code;
- alternate method signatures; or
- backdoors into invariants.

Such shims mean test and production builds have different shapes. Keep fakes inside a local test
module or support crate and implement the same ordinary interface.

Mock only boundaries the project owns or protocols that a maintained simulator models faithfully.
For third-party databases, brokers, and HTTP services, a handwritten mock can prove that the mock
matches itself. Use contract/integration tests when protocol compatibility matters.

## Test binaries and documentation

Cargo exposes compiled binaries to integration tests through `CARGO_BIN_EXE_<name>`. Use that path
instead of assuming `target/debug`, which varies with target triples, profiles, and configuration.
Set child-specific environment with `Command::env` and give it an isolated working directory.

Binary tests should verify exit status, stdout/stderr separation, stable machine output, error
messages, and absence of secret leakage. Do not call `std::process::exit` from domain code; returning
errors to a thin binary boundary makes testing easier.

Doctests execute examples by default. Use:

- ordinary fences for offline examples that should compile and run;
- `no_run` when an example needs an external service or side effect but should compile;
- `compile_fail` for intentional type-system rejections, with care across compiler versions; and
- `text` for non-Rust snippets.

Prefer `no_run` over `ignore`; ignored code may silently rot. Specify the relevant edition only
when the example intentionally differs from the crate's edition.

## Control nondeterminism

Replace ambient state with owned fixtures:

- temporary directories rather than shared fixed paths;
- OS-assigned ports rather than hard-coded ports;
- readiness channels/health checks rather than sleeps;
- injected clocks or paused Tokio time rather than wall-clock waits;
- deterministic seeds recorded on failure;
- unique database schemas/tenant IDs per test; and
- bounded cleanup scoped to an owned fixture root.

Do not mutate process-global environment in parallel tests. Rust 2024 marks `set_var` and
`remove_var` unsafe because other threads may observe inconsistent state on some platforms. Pass
configuration directly or use `Command::env` for a child process.

When a parser accepts floating-point policy values, include `NaN`, positive/negative infinity,
zero, negative values, and upper bounds. Serialization formats may reject some representations;
test both the parser entry point and programmatic constructors that can still receive them.

## Handle features and platforms

Discover the supported feature combinations and target matrix from manifests, CI, and release
policy. Cargo features are additive and may unify across dependencies, so `--all-features` can
exercise an invalid or intentionally unsupported combination. Test the combinations the project
claims.

Respect lockfile policy. Applications commonly commit a lockfile; libraries may choose differently.
Do not add `--locked` universally. Verify MSRV with the project's pinned command and dependency
resolution strategy rather than silently selecting a new toolchain.

For platform-specific code, separate portable behavior tests from native integration tests. A
cross-compile proves compilation for a target, not runtime behavior. Report those evidence levels
separately.

## Use live dependencies safely

Live tests require a declared authority and an isolated target. Establish:

1. opt-in mechanism and who granted it;
2. local container/test tenant/staging endpoint identity;
3. disposable least-privilege credentials;
4. network, filesystem, and external effects;
5. unique namespace and collision avoidance;
6. total timeout and retry policy;
7. cleanup ownership and exact target; and
8. behavior when prerequisites are unavailable.

Do not make a test pass because Docker, credentials, or the network is missing. Either skip with a
clearly reported prerequisite status according to repository policy or fail the explicitly
requested live-test job. Never convert “not run” into compatibility evidence.

Containers and Compose are options, not implicit dependencies. Pin image identities according to
repository supply-chain policy, avoid mutable production data, and remove only resources labeled
and owned by the test. A generic recursive delete is not cleanup.

## Report evidence honestly

For each claimed level, record:

- exact command;
- toolchain/client/dependency version when material;
- selected package, target, and features;
- environment and permissions;
- network/filesystem/external effects;
- pass/fail/skip result; and
- residue or cleanup result.

Compilation is not execution. A mocked pass is not a live integration pass. A structural client
manifest check is not model-backed behavior evidence. Preserve these distinctions in summaries.

## Failure modes

Reject or redesign tests that:

- sleep for readiness or timing;
- bind a fixed port without isolation;
- mutate global environment in a parallel suite;
- require network or containers without opt-in;
- use production credentials or endpoints;
- add production `cfg(test)` shims;
- assert internal implementation instead of behavior;
- impose unsupported feature combinations;
- leave containers, schemas, or files behind; or
- report unavailable infrastructure as a pass.
