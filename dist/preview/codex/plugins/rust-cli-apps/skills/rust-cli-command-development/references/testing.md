# Testing one Rust CLI command

Every Rust block in this reference is an **adaptable snippet**, not a complete project. Match the
repository's binary test tools, feature matrix, fixture format, and platform support.

## Contents

- [Parser and help](#parser-and-help)
- [Domain and dispatch](#domain-and-dispatch)
- [Process contract](#process-contract)
- [Effects and failure injection](#effects-and-failure-injection)
- [Documentation and generated surfaces](#documentation-and-generated-surfaces)
- [Validation evidence](#validation-evidence)

## Parser and help

Test the exact new or changed grammar:

- success examples and nested help;
- missing values, unknown values, conflicts, and requirements;
- defaults, aliases, deprecations, and precedence;
- path operands including spaces and non-ASCII names;
- closed enums, numeric bounds, NaN, and infinity;
- parse/help paths do not initialize services or mutate state.

## Domain and dispatch

Unit-test the typed domain operation for invariants, error categories, ordering, and idempotency. Test
dispatch mapping when it transforms parser data or selects an output/effect path. Use explicit config
and fake adapters rather than mutating process-global environment.

For async commands, test cancellation and resource cleanup using the repository runtime. Do not add a
runtime merely for testing a synchronous command.

## Process contract

Invoke the built binary and assert status, stdout, stderr, and effects.

Adaptable process-test snippet:

```rust
#[test]
fn inspect_json_has_clean_stdout() {
    let mut command = assert_cmd::Command::cargo_bin("tool").expect("binary is available");
    command
        .args(["cache", "inspect", "--format", "json"])
        .assert()
        .success()
        .stdout(predicates::str::contains("\"entries\""))
        .stderr(predicates::str::is_empty());
}
```

Use exact JSON parsing when field/value semantics matter; a substring alone is illustrative. Assert
documented warnings on stderr instead of universally requiring silence. Cover failure exit status and
ensure secrets or unbounded external bodies never appear.

## Effects and failure injection

For filesystem commands, use one uniquely owned temporary root. Cover existing/missing/read-only
targets, spaces, non-ASCII, non-UTF-8 where supported, traversal, case/Unicode collisions, symlinks,
and concurrent change.

For deletion, test exact target authorization, protected root/home/repository/worktree and ancestors,
containment, ownership, preview, confirmation, target swap, every mutation boundary, partial failure,
interruption, and recovery reporting. Cleanup must never follow a symlink or delete outside the owned
temporary root.

For replacement, test visibility, cross-filesystem refusal/fallback, synchronization/durability,
metadata, concurrency, and temporary cleanup according to the promised contract. Do not conflate them.

Network, container, database, subprocess, and credential tests require explicit authorization and
isolated identities. If unavailable, report them as unavailable and keep offline fakes deterministic.

## Documentation and generated surfaces

Verify root/nested help and canonical docs agree. Regenerate help, completions, catalogs, or snapshots
through the repository tool; never hand-edit derived copies. Test migration/deprecation wording and
machine-schema compatibility when the public interface changes.

## Validation evidence

Run focused tests first, then repository-authoritative formatting, lint, compilation, docs, and broader
tests that the environment supports. Derive package, feature, target, and lockfile flags from local
instructions/manifests/CI. Record exact commands and outcomes.

Separate:

- structural/parser validation;
- process/native binary smoke;
- live dependency evidence;
- platform matrix evidence;
- model-backed behavior evidence.

Never turn a missing executable or service into a pass, silently install it, or claim compatibility
from a different source SHA.
