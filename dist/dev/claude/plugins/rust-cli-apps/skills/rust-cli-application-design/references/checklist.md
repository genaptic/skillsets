# Rust CLI application checklist

## Discovery and contract

- [ ] Read instructions, manifests, toolchain, parser, dispatch, domain, adapters, docs, tests, and CI.
- [ ] Discover sync/async and parser/dispatch architecture instead of imposing one.
- [ ] Define users, grammar, compatibility, config precedence, streams, exit status, and effects.
- [ ] Preview command/layer/test ownership and migration impact before broad implementation.
- [ ] Preserve unrelated changes and existing public names unless migration is authorized.

## Architecture and UX

- [ ] Keep parser types as typed syntax, not service containers or business objects.
- [ ] Keep domain code independent of parser, terminal, logging, and process-exit concerns.
- [ ] Use typed requests, outputs, and library errors with context added at boundaries.
- [ ] Reserve stdout for results; send diagnostics, logs, warnings, and progress to stderr.
- [ ] Make machine output intentional, deterministic where required, and free of `Debug` formatting.
- [ ] Return `ExitCode` from `main`; never exit from domain or command layers.
- [ ] Avoid process-global environment mutation; pass immutable config and child-specific env.

## Filesystem, config, and numeric safety

- [ ] Use `Path`/`PathBuf`/`OsStr` rather than string concatenation for OS paths.
- [ ] Define symlink, overwrite, collision, ownership, interruption, and recovery policy.
- [ ] For recursive deletion, authorize one exact target; reject root, home, repository/worktree, and
      ancestors; verify containment and ownership; preview and confirm; test adversarial paths.
- [ ] Distinguish atomic replacement from cross-device behavior, crash durability, and metadata.
- [ ] Reject non-finite numbers and avoid floating-point monetary values.
- [ ] Return an explicit error when platform directories cannot be discovered.

## Verification

- [ ] Test root/nested help, parse failures, aliases, conflicts, defaults, and precedence.
- [ ] Test success/failure exit status, stdout/stderr, machine formats, and broken-pipe behavior.
- [ ] Test spaces, non-ASCII paths, symlinks, collisions, existing destinations, and interruption.
- [ ] Run repository-derived formatting, lint, tests, and checks without assuming feature/lock flags.
- [ ] Report exact results and separate structural, native smoke, and model-backed evidence.
- [ ] Do not install, publish, push, expose credentials, suppress failures, or fabricate results.
