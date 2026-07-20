# Filesystem, configuration, output, and failure safety

Every Rust block in this reference is an **adaptable snippet**, not a complete project. Filesystem
security depends on the target application's trust model; do not copy a snippet without its tests and
repository-specific authorization rules.

## Contents

- [Paths and platform directories](#paths-and-platform-directories)
- [Exact-target recursive deletion](#exact-target-recursive-deletion)
- [Atomic replacement and durability](#atomic-replacement-and-durability)
- [Configuration and environment](#configuration-and-environment)
- [Numeric and serialized values](#numeric-and-serialized-values)
- [Stdout, stderr, and broken pipes](#stdout-stderr-and-broken-pipes)
- [Errors and exit status](#errors-and-exit-status)
- [Required adversarial tests](#required-adversarial-tests)

## Paths and platform directories

- Preserve paths as `Path`, `PathBuf`, `OsStr`, or `OsString`; stringify only for display.
- Resolve relative paths against an explicit base, not a changing ambient directory.
- Use `join`, not string concatenation or hard-coded separators.
- Define whether symlinks are rejected, treated as leaf entries, or followed. Recursive writes and
  deletion should normally reject symlink components and descendants unless a separately reviewed
  policy proves safe traversal.
- Detect case-fold and Unicode-normalization collisions when creating portable trees.
- Refuse devices, FIFOs, sockets, and other nonregular files unless the command explicitly owns them.
- Return an actionable error when platform project/config/cache/data directories are unavailable.

Adaptable platform-discovery snippet:

```rust
fn project_dirs() -> Result<directories::ProjectDirs, AppError> {
    directories::ProjectDirs::from("org", "Example", "Tool")
        .ok_or(AppError::ProjectDirectoriesUnavailable)
}
```

This is a snippet; use the repository's chosen directory provider and identifiers.

## Exact-target recursive deletion

Recursive deletion is never justified by `--force` alone. Define and test this contract:

1. The request names one exact target; no glob or unresolved environment variable selects it.
2. Resolve lexical normalization and inspect filesystem components without following unexpected
   symlinks. Reject dangling or changing components.
3. Reject the filesystem root, any platform root/prefix, the user's home directory, the repository or
   active worktree root, and every ancestor of those protected paths.
4. Prove the target is contained within an authorized parent after applying the explicit symlink
   policy. A string-prefix check is not containment.
5. Prove application ownership using a marker, manifest, registry entry, or other unforgeable-enough
   local contract. Merely existing beneath a directory is not ownership.
6. Preview the exact resolved target, entry count/summary, symlink finding, and effect. Redact private
   child names when the output contract requires it.
7. Require explicit confirmation or an equally explicit noninteractive authorization flag whose scope
   is documented and tested.
8. Recheck target, containment, ownership, and protected paths immediately before deletion to reduce
   time-of-check/time-of-use exposure.
9. Report partial deletion and recovery steps. Do not claim rollback for an irreversible recursive
   removal unless a real trash/quarantine transaction provides it.

Prefer recoverable quarantine or platform trash where it fits the product. Never recursively delete
the repository root as test cleanup; tests must create and own a unique temporary target.

The adaptable [`removal_preview.rs`](../assets/templates/removal_preview.rs) asset makes the
containment, protected-path, ownership-marker, and no-symlink checks executable without exposing any
delete operation. Treat its result as review evidence, not authorization: obtain explicit approval
and repeat all checks immediately before a separately reviewed mutation.

## Atomic replacement and durability

Writing a temporary file and renaming it can provide atomic *visibility* on some filesystems when
source and destination share a filesystem. It does not automatically provide:

- cross-filesystem replacement;
- crash durability of file data or directory entries;
- preservation of permissions, ownership, ACLs, extended attributes, timestamps, or hard links;
- identical overwrite behavior on all Windows and Unix filesystems;
- multi-file transaction atomicity;
- protection from concurrent writers.

Define the required guarantees explicitly. A robust single-file sequence may include:

1. Validate destination and symlink policy.
2. Create a unique temporary file in the destination directory with restrictive permissions.
3. Write all bytes and flush userspace buffers.
4. If crash durability is required and supported, sync the file.
5. Apply deliberately preserved metadata.
6. Replace the destination using a documented same-filesystem primitive.
7. If crash durability is required and supported, sync the parent directory.
8. Clean up a helper-owned temporary file without deleting concurrent user data.

Adaptable shape only:

```rust
fn replace_config(path: &Path, bytes: &[u8]) -> Result<(), ConfigError> {
    // Use the repository's reviewed same-directory temporary-file abstraction.
    // Its contract must define overwrite, sync, metadata, and cleanup semantics.
    reviewed_atomic_replace(path, bytes)
}
```

Do not invent `reviewed_atomic_replace`; this placeholder deliberately forces selection of an actual
repository abstraction or a fully tested implementation. For multi-file updates, use a journal,
versioned directory swap, database transaction, or explicit recovery protocol as appropriate.

## Configuration and environment

- Parse configuration sources into immutable typed data, validate once, and pass references or owned
  values to components.
- Document precedence and whether empty values differ from missing values.
- Avoid `std::env::set_var`/`remove_var` in a multithreaded application. Do not use process-global
  environment mutation as a test seam.
- Set environment for a child process on `std::process::Command` only; clear or allowlist inherited
  variables when credentials or reproducibility matter.
- Store user configuration with restrictive permissions where appropriate and never echo secrets.
- Use file locking or optimistic preimage checks when concurrent config writers are plausible.

Adaptable child-process snippet:

```rust
let status = std::process::Command::new(program)
    .env("TOOL_MODE", config.mode.as_str())
    .env_remove("UNRELATED_SECRET")
    .status()?;
```

The snippet does not authorize subprocess execution; require explicit product permission and test
argument/environment construction without invoking arbitrary programs.

## Numeric and serialized values

- Reject NaN, positive infinity, and negative infinity at parser and deserialization boundaries.
- Apply domain bounds and units after finiteness checks.
- Do not represent money with `f32` or `f64`; use integer minor units or a checked decimal type chosen
  under repository dependency policy.
- Reject non-finite values during custom deserialization even if the wire format parser accepts them.
- Keep machine output schemas versioned or compatibility-tested; serialize typed output, not debug
  representations.

The adaptable [`finite_bounded_number.rs`](../assets/templates/finite_bounded_number.rs) asset
demonstrates a finite-first, inclusive-bounds parser for non-monetary configuration values.

## Stdout, stderr, and broken pipes

- stdout: command results, requested documents, and machine-readable output.
- stderr: diagnostics, warnings, progress, logs, and deprecation notices.
- Never mix progress or tracing into JSON/JSONL/CSV stdout.
- Make ordering deterministic when scripts compare or consume results.
- Define empty-result output and newline behavior.
- Treat a downstream closed pipe according to CLI policy, commonly a quiet successful termination for
  ordinary listing output. Do not hide unrelated write errors.
- Disable or auto-detect color for non-terminal streams and machine formats.

## Errors and exit status

Use typed error categories internally. At the top-level application boundary:

- redact tokens, authorization headers, credentials, and bounded external response bodies;
- give the user actionable context without printing an internal `Debug` dump as stable output;
- map documented error classes to stable exit codes when automation needs them;
- return `std::process::ExitCode` from `main`;
- never call `std::process::exit` from domain, command, cleanup, or adapter layers.

## Required adversarial tests

For applicable commands, test:

- root, platform prefix/root, home, repository/worktree, and their ancestors;
- exact authorized target versus a sibling with a common string prefix;
- relative traversal, `.`/`..`, case and Unicode collisions;
- symlink component, symlink descendant, dangling symlink, and target swap before mutation;
- missing/invalid ownership marker and concurrently changed preimage;
- preview without mutation, refused confirmation, and explicit noninteractive authorization;
- failure or interruption at every write/replace/delete boundary and truthful recovery reporting;
- same-directory versus cross-filesystem replacement behavior where supported;
- metadata expectations and concurrent writers;
- NaN, infinity, negative infinity, overflow, bounds, and monetary rounding avoidance;
- stdout/stderr separation, invalid UTF-8 paths where the platform permits them, and broken pipes;
- unavailable platform directories and child environment isolation.
