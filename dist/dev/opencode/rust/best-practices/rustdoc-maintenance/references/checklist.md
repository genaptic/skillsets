# Rustdoc maintenance checklist

## Inventory

- [ ] Read repository instructions, manifests, toolchain, features, lints, and canonical commands.
- [ ] Define packages, targets, features, platforms, and public audience in scope.
- [ ] Inventory crate/module docs, public items, re-exports, macros, examples, and intra-doc links.
- [ ] Trace errors, panics, safety preconditions, side effects, and invariants to code and tests.
- [ ] Preview the documentation matrix before broad edits.

## Authoring

- [ ] Give crate and module docs clear roles and a supported first path.
- [ ] Start item docs with a concise outcome rather than a restated signature.
- [ ] Add accurate `# Errors`, `# Panics`, and `# Safety` sections where applicable.
- [ ] Keep feature and platform claims aligned with actual `cfg` and manifest behavior.
- [ ] Prefer resolvable intra-doc links to fragile paths or plain text references.
- [ ] Make examples deterministic, minimal, safe, and runnable by default.
- [ ] Justify every `no_run`, `compile_fail`, or `ignore` fence.
- [ ] Preserve unrelated source and avoid hidden behavior/API changes.

## Safety and evidence

- [ ] Keep credentials, live services, durable user data, and destructive operations out of doctests.
- [ ] Avoid process-global environment mutation and platform-specific assumptions in portable examples.
- [ ] Discover package, feature, target, lockfile, and lint flags from repository evidence.
- [ ] Run relevant doc build, doctest, formatting, and rustdoc lint checks separately.
- [ ] Inspect rendered docs when feasible and record whether that review occurred.
- [ ] Report failed, skipped, unavailable, and manual checks explicitly.
- [ ] Never stage, publish, push, install tools, disable lints, or fabricate compatibility evidence.
