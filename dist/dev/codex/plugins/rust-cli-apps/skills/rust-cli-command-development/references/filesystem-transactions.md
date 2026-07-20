# Filesystem command transactions

Every Rust block in this reference is an **adaptable snippet**, not a complete project. A mutation is
safe only when the target application's authority, ownership, and recovery contract is explicit.

## Contents

- [Classify effects](#classify-effects)
- [Validate paths](#validate-paths)
- [Recursive deletion](#recursive-deletion)
- [Replacement and multi-file updates](#replacement-and-multi-file-updates)
- [Configuration and subprocesses](#configuration-and-subprocesses)
- [Failure and interruption](#failure-and-interruption)
- [Test matrix](#test-matrix)

## Classify effects

Record every read, create, overwrite, rename, remove, permission change, process invocation, network
request, and external write. For each effect define:

- required authority and confirmation;
- exact target and allowed parent;
- ownership proof;
- symlink and nonregular-file policy;
- collision and overwrite behavior;
- concurrency/preimage check;
- rollback, recovery, or irreversible partial-failure report;
- logs/output with credential and path redaction.

## Validate paths

Use `Path`/`PathBuf` and explicit bases. Reject lexical traversal, reserved targets, unexpected symlink
components/descendants, devices, FIFOs, sockets, and case/Unicode collisions as the product requires.
Do not use string-prefix containment: `/safe/project-old` starts with `/safe/project` as text but is not
inside it.

Return an error when platform project directories cannot be discovered. Never panic because home,
config, cache, or data directories are unavailable.

## Recursive deletion

Before any recursive removal:

1. Require one exact target selected without globs or unresolved environment variables.
2. Reject root/platform roots, home, repository/worktree root, and every ancestor of protected paths.
3. Verify resolved containment within an authorized parent under an explicit symlink policy.
4. Verify application ownership from a marker, manifest, or registry contract.
5. Preview resolved target and effects; require confirmation or explicit noninteractive authorization.
6. Recheck path identity, protected targets, containment, symlinks, ownership, and preimage immediately
   before mutation.
7. Use quarantine/trash when the product promises recoverability; otherwise report irreversibility and
   partial deletion accurately.

Never present a bare `remove_dir_all(user_path)` or `--force` as safe. Test root, home,
repository/worktree, ancestors, sibling prefixes, traversal, symlinks, dangling links, ownership
failure, target swaps, and interruption.

## Replacement and multi-file updates

Same-directory temporary write plus replacement may provide atomic visibility on a supported local
filesystem. It does not itself guarantee cross-filesystem behavior, crash durability, parent-directory
durability, metadata preservation, multi-file atomicity, or concurrency control.

Define these separately:

- overwrite behavior on supported platforms;
- file and parent-directory synchronization when durability is required;
- permissions, owner, ACL, extended attributes, timestamps, and link semantics;
- preimage hash/version or lock for concurrent writers;
- cleanup of only helper-owned temporary files;
- journal or recovery protocol for multi-file changes.

Adaptable interface shape:

```rust
trait StateWriter {
    fn preview(&self, change: &StateChange) -> Result<Preview, StateError>;
    fn apply(&self, change: StateChange, reviewed: PreviewDigest) -> Result<(), StateError>;
    fn recover(&self) -> Result<RecoveryStatus, StateError>;
}
```

The types are placeholders. A digest must bind all relevant preimages and normalized effects; it is
not a substitute for locks or immediate rechecks.

## Configuration and subprocesses

Parse all configuration into immutable typed data. Do not call process-global environment mutation in
a multithreaded application or use it as a test seam. When subprocess execution is explicitly
authorized, set or remove environment variables on the child builder, avoid shell interpolation, pass
arguments separately, bound output, and redact credentials.

Reject NaN and infinity at input/deserialization boundaries. Do not store monetary values in binary
floating point; use integer minor units or a reviewed decimal representation.

## Failure and interruption

Inject failure before and after every mutation boundary. Roll back only helper-owned postimages that
still match; never overwrite a concurrent edit during recovery. Catch interruption where the runtime
allows cleanup, but document that process kill or system crash can bypass it.

Return actionable recovery details: exact repository-relative or user-approved target, transaction
state, safe inspection step, and whether retry is allowed. Do not claim full rollback when external or
irreversible effects have occurred.

## Test matrix

- preview makes no write or metadata change;
- confirmation refusal and explicit noninteractive authorization;
- protected targets, containment, ownership, symlink and nonregular-file policy;
- existing/dangling destination and concurrent preimage change;
- failure/interruption at every write, replace, journal, and delete boundary;
- same-filesystem and supported cross-filesystem behavior;
- metadata and durability claims separately;
- immutable config and child-only environment;
- non-finite numeric input and money representation;
- stdout/stderr redaction and exact exit status.
