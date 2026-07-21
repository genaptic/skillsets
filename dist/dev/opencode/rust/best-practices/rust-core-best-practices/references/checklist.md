# Rust core completion checklist

## Authority and scope

- [ ] Read repository instructions, manifests, toolchain files, CI, and neighboring code.
- [ ] Record edition, `rust-version`, package scope, features, targets, lockfile, and lint policy.
- [ ] Confirm this is a general quality task rather than a specialized Rust workflow.
- [ ] Preserve unrelated changes and avoid unrequested public API or dependency expansion.

## Implementation

- [ ] Borrow read-only inputs and move/clone only at justified ownership seams.
- [ ] Keep type, method, free-function, and type-alias choices contextual and documented.
- [ ] Return recoverable errors; reserve panic for bugs or proven invariants.
- [ ] Reject non-finite numeric input where the domain requires finite values.
- [ ] Keep necessary `unsafe` narrow, documented, validated, and safely wrapped.
- [ ] Review build scripts, proc macros, generated code, native code, and dependencies as supply-chain surfaces.
- [ ] Update relevant tests, rustdoc, examples, features, and platform behavior.

## Verification and report

- [ ] Derive Cargo flags and commands from repository evidence rather than a universal command bundle.
- [ ] Run focused checks, then every repository-required completion gate.
- [ ] Report exact commands, results, skipped configurations, and unavailable infrastructure.
- [ ] Inspect the final diff for formatting, warnings, residue, secrets, and unrelated edits.
- [ ] Distinguish observed facts, recommendations, executed work, and remaining risk.
- [ ] Do not claim native-client, model-backed, platform, or feature compatibility without direct evidence.
