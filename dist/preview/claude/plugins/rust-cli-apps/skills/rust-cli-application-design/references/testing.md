# Rust CLI testing strategy

Every Rust block in this reference is an **adaptable snippet**, not a complete project. Use the target
repository's test framework, binary discovery, feature matrix, and platform policy.

## Contents

- [Test layers](#test-layers)
- [Parser and help](#parser-and-help)
- [Domain and command behavior](#domain-and-command-behavior)
- [Process contract](#process-contract)
- [Filesystem and portability](#filesystem-and-portability)
- [Live dependencies](#live-dependencies)
- [Validation selection](#validation-selection)

## Test layers

| Layer | Proves | Does not prove |
|---|---|---|
| parser unit | grammar, defaults, conflicts | runtime or effects |
| domain unit | business invariants and errors | CLI rendering |
| command integration | dispatch and adapter coordination | installed binary behavior |
| process integration | argv, streams, exit status, files | every platform |
| E2E scenario | user workflow across layers | model/native-client behavior |
| live integration | authorized external dependency | offline determinism |

Keep failures attributable. One giant E2E test cannot replace focused parser, domain, and safety tests.

## Parser and help

Use parser APIs that accept explicit argv so tests do not read the real process environment. Cover:

- root and nested help;
- required and optional operands;
- defaults and config/env precedence;
- conflicts, aliases, deprecated forms, and unknown input;
- closed enums and bounded values, including non-finite rejection;
- paths with spaces and non-ASCII names;
- no runtime initialization, filesystem write, network, or credential lookup for help/parse failure.

## Domain and command behavior

Test domain behavior through typed requests with fake or temporary adapters. Cover invariants, error
classification, ordering, cancellation, and partial-failure policy. Test command dispatch separately
when it maps grammar to domain operations or output modes.

Do not mutate the process-global environment to vary configuration. Construct immutable config for
the application or set environment only on an invoked child command under test.

## Process contract

Run the built binary for public behavior. Assert exit status, stdout, stderr, and durable effects.

Adaptable process-test snippet:

```rust
#[test]
fn json_output_is_machine_only() {
    let mut command = assert_cmd::Command::cargo_bin("tool").expect("binary is built");
    command
        .args(["project", "list", "--format", "json"])
        .assert()
        .success()
        .stdout(predicates::str::starts_with("["))
        .stderr(predicates::str::is_empty());
}
```

Adapt the binary discovery API to installed crate versions. Do not make empty stderr a universal
rule if the command deliberately emits warnings; assert the documented contract.

Test broken-pipe handling when commands stream ordinary output. Keep logs/progress off machine stdout.
Avoid snapshots for unstable debug strings, absolute temp paths, random IDs, or timestamps unless
normalized by a reviewed contract.

## Filesystem and portability

Use uniquely owned temporary directories; never hard-code `/tmp` or a Windows drive. Cover:

- spaces, non-ASCII names, and non-UTF-8 paths on supporting platforms;
- existing, missing, read-only, and concurrently changed destinations;
- path containment, symlink policy, collisions, ownership markers, and overlap;
- exact-target deletion refusal for root, home, repository/worktree, ancestors, sibling prefixes,
  traversal, dangling symlinks, and target swaps;
- preview and confirmation behavior;
- interruption and recovery at every mutation boundary;
- atomic replacement guarantees separately from sync/durability and metadata expectations.

Do not follow a symlink in test cleanup. Let the temporary-directory owner remove only its exact test
root after verifying that it remains the same owned directory.

## Live dependencies

Network, containers, databases, and credentials require explicit authorization and isolated test
identity. Use offline fakes for ordinary pull-request checks. When a live executable or service is
unavailable, report the test as unavailable; never turn absence into success or silently install it.

Keep secrets out of argv, snapshots, logs, stdout/stderr assertions, fixture files, and failure text.

## Validation selection

Discover canonical commands from manifests, CI, task runners, and instructions. Candidate checks may
include formatting, compilation, Clippy, tests, docs, and platform matrices, but flags such as
`--locked`, `--workspace`, `--all-targets`, and `--all-features` are not universal defaults.

Run focused tests first. Then run broader checks that the repository defines and the environment can
support. Report exact commands, tool versions when relevant, outcomes, skipped matrices, and manual
review. Compilation is structural evidence, not a native-client or model-backed pass.
