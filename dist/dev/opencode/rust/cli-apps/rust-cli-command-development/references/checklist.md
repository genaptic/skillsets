# Single-command development checklist

## Discovery and contract

- [ ] Read instructions, manifests, toolchain, parser, dispatch, runtime, domain, adapters, and CI.
- [ ] Identify the closest neighboring command and its relevant tests/docs.
- [ ] Discover sync/async and dispatch style instead of imposing one.
- [ ] Define exact argv, defaults, conflicts, precedence, streams, exit status, effects, and migration.
- [ ] Preview the vertical diff, authority requirements, generated impact, and tests.

## Implementation

- [ ] Keep parser types limited to typed syntax and parser-owned validation.
- [ ] Extend dispatch exhaustively through the existing coherent mechanism.
- [ ] Keep reusable behavior independent of parser, terminal, logging, and process exit.
- [ ] Use typed requests, results, and errors with redacted context at the CLI boundary.
- [ ] Keep result/machine output on stdout and diagnostics/logs/progress on stderr.
- [ ] Return `ExitCode` only from `main`; lower layers return errors.
- [ ] Preserve unrelated code, commands, public names, and generated boundaries.

## Effects and safety

- [ ] Enumerate every read, write, network request, subprocess, and external effect.
- [ ] Require explicit authority for overwrite, migration, deletion, live credentials, or publishing.
- [ ] For recursive deletion, authorize one exact owned target; reject root, home, repository/worktree,
      ancestors, traversal, symlinks, and changed preimages; preview and confirm.
- [ ] Distinguish atomic visibility, crash durability, metadata preservation, and multi-file recovery.
- [ ] Reject non-finite numeric input and avoid floating-point money.
- [ ] Use immutable config and child-specific environment rather than process-global mutation.

## Verification and report

- [ ] Test parser/help, invalid input, domain behavior, dispatch, streams, exit status, and effects.
- [ ] Test spaces, non-ASCII paths, symlink/collision policy, existing destinations, and interruption.
- [ ] Run focused then broader repository-derived checks without inventing Cargo flags.
- [ ] Update canonical docs and regenerate derived help/completions when applicable.
- [ ] Inspect the final diff and report exact outcomes, skipped tools/platforms, and remaining risks.
- [ ] Do not install, stage, commit, push, publish, expose secrets, suppress failures, or fabricate passes.
