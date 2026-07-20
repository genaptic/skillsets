# Rust project architecture guide

Use this reference when designing or restructuring Cargo packages, crates, modules, targets,
ownership seams, or test boundaries.

## Contents

- [Start from the current graph](#start-from-the-current-graph)
- [Use Cargo's target model](#use-cargos-target-model)
- [Keep binaries thin](#keep-binaries-thin)
- [Choose modules by responsibility](#choose-modules-by-responsibility)
- [Choose package boundaries deliberately](#choose-package-boundaries-deliberately)
- [Design workspaces intentionally](#design-workspaces-intentionally)
- [Place tests at the narrowest boundary](#place-tests-at-the-narrowest-boundary)
- [Design ownership seams](#design-ownership-seams)
- [Plan migrations](#plan-migrations)
- [Worked decisions](#worked-decisions)

## Start from the current graph

Before proposing a tree, map:

- packages, targets, modules, public exports, and feature gates;
- dependency direction, optional dependencies, build scripts, and native dependencies;
- executable/deployment units and platform constraints;
- consumers of public types and paths;
- test placement and CI package/feature selection;
- ownership, review, release, and versioning boundaries.

Architecture should solve demonstrated coupling or ownership problems. A visually symmetric tree is
not evidence of a good boundary.

## Use Cargo's target model

Cargo recognizes conventional targets without explicit manifest entries:

```text
package/
├── Cargo.toml
├── src/
│   ├── lib.rs          # library target
│   ├── main.rs         # default binary target
│   └── bin/
│       └── admin.rs    # additional binary
├── tests/              # public integration tests
├── examples/           # executable examples
└── benches/            # benchmark targets
```

Use explicit `[[bin]]`, `[[example]]`, or target configuration when names, paths, required features,
or build behavior differ from the conventions. Do not add configuration that only restates Cargo's
defaults.

## Keep binaries thin

A binary edge normally owns:

- argument/environment/config parsing;
- logging and runtime initialization;
- construction of adapters and application services;
- signal and shutdown wiring;
- presentation of errors and mapping to `ExitCode`.

Reusable domain behavior belongs in a library when it needs direct tests, multiple frontends, or
independent reuse. This is a design heuristic, not a mandate to create a separate library package:
one Cargo package can expose both `src/lib.rs` and `src/main.rs`.

```rust
use std::process::ExitCode;

fn main() -> ExitCode {
    match example_app::run(std::env::args_os().skip(1)) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
```

Do not call `process::exit` from domain layers; it bypasses normal unwinding and makes library
behavior hard to test and reuse.

## Choose modules by responsibility

Prefer module names that state a domain or behavior: `config`, `order`, `storage`, `render`,
`transport`. Vague buckets such as `utils`, `common`, `helpers`, or `misc` often hide unrelated
responsibilities.

Both common Rust module layouts are valid:

```text
src/order.rs + src/order/validation.rs
```

and:

```text
src/order/mod.rs + src/order/validation.rs
```

Follow existing repository policy. Do not create a mass move merely to prefer one style. Keep
visibility as narrow as possible and use intentional re-exports to define a public facade.

Separate interface from implementation where that improves substitution or dependency direction,
but do not create one module per trait/type. A shared contract module should depend only on the
domain concepts its consumers need; concrete integrations should own their protocol and dependency
details.

## Choose package boundaries deliberately

Extend an existing package when:

- the behavior belongs to its established domain;
- dependencies and platform support remain compatible;
- consumers, release cadence, deployment, and ownership are shared;
- a module boundary is sufficient for visibility and cohesion.

Create a package when at least one durable boundary exists:

- independent external or workspace reuse;
- a distinct deployable/executable artifact;
- dependency or build-time isolation;
- platform-specific compilation;
- separate ownership or release cadence;
- a deliberate public API/semver boundary;
- prevention of an otherwise unavoidable dependency cycle.

Package count is a cost: manifests, versions, features, CI matrix, dependency edges, documentation,
and release coordination. Avoid pseudo-layer packages that contain only re-exports or one trivial
type.

For an extra executable sharing the same library and dependencies, prefer `src/bin/name.rs`. Use a
separate package when the binary has materially different dependencies, platform constraints,
deployment, ownership, or release lifecycle.

## Design workspaces intentionally

A virtual workspace needs an explicit resolver because there is no root package edition from which
Cargo can infer it. Workspace inheritance reduces drift but is opt-in for member package fields,
dependencies, and lints.

```toml
[workspace]
members = ["apps/tool", "crates/app-core"]
default-members = ["apps/tool"]
resolver = "3"

[workspace.package]
edition = "2024"
rust-version = "1.85"
license = "Apache-2.0"
version = "0.1.0"

[workspace.lints.rust]
unsafe_op_in_unsafe_fn = "deny"
```

Use `default-members` when unqualified commands should intentionally exclude costly,
platform-specific, experimental, or infrastructure-dependent packages. Do not hide required
validation this way; CI should select its intended packages explicitly.

Centralize a dependency in `[workspace.dependencies]` only when members should share its source and
compatible requirement. Features remain additive across the resolved graph, so verify that shared
feature choices do not accidentally broaden downstream builds.

## Place tests at the narrowest boundary

| Test need | Placement |
|---|---|
| private helper or invariant | `#[cfg(test)] mod tests` beside the module |
| public crate contract | package `tests/*.rs` |
| shared integration fixture | `tests/common/mod.rs` or a non-target submodule |
| copyable user workflow | rustdoc or `examples/` |
| process/CLI behavior | binary integration test |
| multi-package/live journey | explicit end-to-end package or harness |

Files directly under `tests/` are independent crates. Use `tests/common/mod.rs`, not
`tests/common.rs`, when `common` is support code rather than another integration-test target.

Do not expose private internals solely for integration tests. Test through public behavior or keep
implementation-focused tests beside the code. A reusable test-support crate is justified only when
multiple packages genuinely need it and its dependency cost is acceptable.

## Design ownership seams

Borrow through validation and synchronous internal processing when the caller retains ownership.
Move data once where an independent owner begins. Examples include storage, queued work, spawned
tasks, caches, and returned aggregates.

```rust
#[derive(Debug)]
pub struct User {
    email: String,
}

pub fn email_views(users: &[User]) -> impl Iterator<Item = &str> {
    users.iter().map(|user| user.email.as_str())
}
```

Returning borrowed views avoids allocation when their lifetime naturally follows the input. Return
owned data when the result must outlive it. Do not clone early to make boundaries disappear; an
ownership error often reveals an unclear lifecycle or API.

## Plan migrations

For moves that affect public paths or packages:

1. inventory internal and downstream callers;
2. decide whether a compatibility re-export is required and for how long;
3. avoid dependency cycles while introducing the new direction;
4. update docs, examples, features, tests, CI, and release notes;
5. validate old and new paths if a transition period is promised;
6. remove shims only under the repository's compatibility policy.

Preview file moves and manifest edits. Distinguish source-compatible re-exports from binary or
semantic compatibility; do not claim more than tests establish.

## Worked decisions

### Two binaries duplicate domain logic

Keep both binaries as thin targets and move shared behavior into the package library. If their
dependency/platform needs later diverge, reconsider separate packages with concrete evidence.

### One module has many files

Split by cohesive sub-responsibility, not by type category. Keep a stable facade in the parent
module and narrow child visibility. File count alone does not require a new crate.

### A provider family needs runtime selection

If the family is closed, an enum with exhaustive dispatch can keep supported variants visible. If
external implementations must be open, design a narrow trait at the consumer boundary. Concrete
provider implementations should own protocol-specific dependencies; shared domain contracts should
not import them.

### A platform-specific backend grows native dependencies

Consider a separate package or target gated by an explicit feature/platform boundary. Verify that
the workspace still loads on supported toolchains and that default commands do not accidentally
build unsupported targets.
