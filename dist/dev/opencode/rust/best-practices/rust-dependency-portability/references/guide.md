# Rust dependency and portability decision guide

Use this guide only after reading the repository's manifests, toolchain pins, CI, release policy,
and supported target matrix.

## Contents

- [Separate toolchain, edition, and MSRV](#separate-toolchain-edition-and-msrv)
- [Evaluate dependencies](#evaluate-dependencies)
- [Design features and workspace inheritance](#design-features-and-workspace-inheritance)
- [Respect lockfiles and resolution](#respect-lockfiles-and-resolution)
- [Review supply-chain impact](#review-supply-chain-impact)
- [Use target-specific dependencies](#use-target-specific-dependencies)
- [Write portable paths and processes](#write-portable-paths-and-processes)
- [Handle environment safely](#handle-environment-safely)
- [Verify platforms honestly](#verify-platforms-honestly)
- [Failure modes](#failure-modes)

## Separate toolchain, edition, and MSRV

These are independent contracts:

- **toolchain pin/channel** selects the compiler used by contributors and CI;
- **edition** selects language compatibility rules;
- **`package.rust-version`** declares the minimum supported Rust version for a package; and
- **resolver** controls dependency/feature resolution behavior at the workspace level.

Do not set `rust-version` to today's stable version without a support decision. Cargo expects all
package functionality, targets, and feature combinations that are claimed supported to work at the
declared floor. A workspace may have different package MSRVs, but shared dependency resolution can
constrain all members.

Edition 2024 implies resolver 3 for a package, but a virtual workspace still needs an explicit
workspace resolver. Do not change a resolver as an incidental dependency edit; review feature and
MSRV effects.

Verify MSRV using the repository's policy. A build on current stable does not prove MSRV. Do not
silently install or select a toolchain merely to produce a green result.

## Evaluate dependencies

First ask whether `std`, Cargo, or an existing workspace crate already provides the capability.
Avoid adding a crate for a trivial helper, but do not reimplement security-critical parsing,
cryptography, protocols, or platform conventions casually.

Evaluate each candidate for:

- exact API/correctness fit;
- maintenance and release cadence;
- documented MSRV/support policy;
- license compatibility;
- known advisories and repository security policy;
- unsafe code, FFI, proc macros, and build scripts;
- default and optional features;
- transitive dependency and compile-time cost;
- native system libraries/toolchains;
- supported OS/architecture/WASM targets; and
- repository precedent and ownership.

Popular crates are candidates, not universal defaults. Record why the chosen crate and version
fit this repository and why alternatives were rejected.

## Design features and workspace inheritance

Cargo features should be additive: enabling a feature should not remove functionality. Avoid
mutually exclusive features unless the repository has an enforced build strategy and documents the
constraint.

Enable the smallest required feature set. Disabling defaults can improve portability and reduce
surface, but only after identifying which defaults the code depends on. For an optional dependency,
use the explicit `dep:` feature syntax when the public feature name should be controlled.

Workspace dependency features are additive with member features. An inherited dependency cannot
override version/default-features at the member declaration in arbitrary ways; consult the current
Cargo rules. Review the resolved features, not just one manifest line.

Workspace lints do not apply automatically. Members that should inherit them need:

```toml
[lints]
workspace = true
```

Respect the repository's minimum Cargo version before using newer inheritance features.

## Respect lockfiles and resolution

Applications generally use committed lockfiles for reproducibility; libraries may choose to omit
them from publication or source control. The repository decides. `--locked` is correct only when a
lockfile is expected and current.

Do not run `cargo update` as a side effect of an unrelated manifest edit. When dependency updates
are authorized, use the narrowest repository-supported operation and review every changed lockfile
entry, not only the direct package.

`--all-features` can create a combination the product does not support. `--workspace` may include
packages outside the requested scope; a bare command may use `default-members`. `--all-targets` can
compile examples/benches with extra requirements. Discover the intended matrix from CI and policy.

## Review supply-chain impact

Before executing code from a new dependency, review manifest metadata, repository/source,
checksums, licenses, build scripts, proc macros, native compilation, and advisory state. Network
results are time-sensitive; record the source and date.

Use already-approved tools such as `cargo audit`, `cargo deny`, `cargo vet`, or SBOM/license tooling
only when present in repository policy. Do not install them silently. A missing tool is an evidence
gap, not a passing audit.

Lockfile churn can add platform-specific packages not built on the current host. Inspect them
anyway. A crate with no Rust `unsafe` can still execute a build script or invoke native tooling.

## Use target-specific dependencies

Put platform-only dependencies under target tables so other targets do not compile or resolve
unnecessary native surfaces:

```toml
[target.'cfg(unix)'.dependencies]
nix = "0.30"

[target.'cfg(windows)'.dependencies]
windows-sys = { version = "0.61", features = ["Win32_System_Console"] }
```

Adapt versions and features to the target repository. Keep portable interfaces outside small
`cfg` modules so most logic can be tested on any host.

## Write portable paths and processes

Use `Path` and `PathBuf`, not slash-delimited string concatenation. Preserve non-UTF-8 paths where
the platform allows them; do not force every path through `to_str().unwrap()`.

Use a typed platform-directory provider such as `directories::ProjectDirs` only when already
approved. Its constructor can return `None`; convert that into a domain/configuration error rather
than panicking or inventing `~/.config`/`%APPDATA%` paths.

Use `std::process::Command` with one argument per `.arg()` call. Do not build a shell string from
untrusted values. Set the working directory and child environment explicitly. Capture output only
when bounded output is acceptable; avoid leaking command lines containing secrets.

## Handle environment safely

Treat process environment as immutable after threads can start. Rust 2024 marks `set_var` and
`remove_var` unsafe because concurrent environment access is unsound on some platforms.

Prefer, in order:

1. parsed immutable application configuration;
2. function/constructor parameters;
3. child-specific `Command::env`/`env_remove`; and
4. a carefully audited single-threaded bootstrap mutation only when no safer design exists.

Tests should not mutate global environment in a parallel process. Use child processes or an
injected environment map.

## Verify platforms honestly

Evidence levels differ:

- source/static review;
- host compilation and tests;
- cross-compilation for a target;
- native test execution on the target OS/architecture; and
- end-to-end packaging/install behavior.

Cross-compilation needs more than `rustup target add` for many targets; linkers, SDKs, and native
libraries may be required. Do not install them without authority. Report unavailable targets and
do not call a cross-compile a native pass.

Verify only feature combinations the project claims. Add native CI coverage when a platform is a
public support promise and no current evidence exists.

## Failure modes

Reject or redesign changes that:

- raise MSRV implicitly through syntax or dependencies;
- add a crate without checking existing alternatives and transitive impact;
- enable all default/features without need;
- assume workspace lints or dependencies apply automatically;
- rewrite the lockfile broadly without review;
- impose one Cargo command matrix on every repository;
- construct platform paths from HOME/APPDATA strings or panic when directories are unavailable;
- pass untrusted values through a shell string;
- mutate process-global environment after threads start; or
- claim platform support from a single host build.
