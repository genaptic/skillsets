# Cargo policy decisions

## Discover before choosing commands

Read `rust-toolchain*`, root/member `Cargo.toml`, `.cargo/config*`, lockfiles, Make/task scripts, and
CI/release workflows. Determine workspace default members, supported features, targets, MSRV, and
whether dependencies may be fetched.

Do not assume this universal command is correct:

```text
cargo test --locked --workspace --all-targets --all-features
```

Each flag has a contract: `--locked` requires an authoritative current lockfile; `--workspace`
changes package selection; `--all-targets` may add examples/benches; and `--all-features` may create
unsupported additive combinations. Use the repository's actual matrix.

## Review a dependency change

Record direct manifest edits and every changed lockfile package. Check source, checksum, version,
features, license, MSRV, build script, proc macro, native dependency, platform conditions, and
known advisory state. If network/tooling is unavailable, mark those fields unverified.

For a workspace dependency, inspect member-added features because they unify additively. Confirm
members explicitly inherit workspace lints when intended. Preserve the existing resolver unless a
separate reviewed migration requires it.

## MSRV

Treat `rust-version` as a support promise, not a formatting hint. Verify claimed targets and
features on the floor using the repository's approved toolchain workflow. A dependency requirement
can support versions both below and above the package MSRV; the selected resolution must include a
compatible version under the repository's resolver/lockfile policy.
