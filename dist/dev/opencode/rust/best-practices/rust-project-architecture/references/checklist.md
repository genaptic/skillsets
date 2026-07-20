# Rust architecture checklist

## Discover

- [ ] Read repository instructions, manifests, targets, exports, features, tests, and CI.
- [ ] Map dependency direction, consumers, deployment units, platforms, ownership, and releases.
- [ ] Identify the concrete coupling, duplication, ownership, or build problem to solve.

## Decide

- [ ] Give every proposed crate/module one cohesive responsibility.
- [ ] Extend an existing crate unless a real reuse, dependency, deployment, platform, ownership, or release boundary justifies a package.
- [ ] Prefer `src/bin/` for a small additional executable sharing the same domain and dependencies.
- [ ] Keep process setup and exit mapping at thin executable edges.
- [ ] Follow the repository's module-file convention and keep visibility narrow.
- [ ] Borrow internally and move/clone only where an independent owner begins.
- [ ] Place each test at the narrowest boundary that proves the behavior.
- [ ] Plan public-path, package-name, feature, and semver migrations explicitly.

## Verify

- [ ] Inspect Cargo metadata/dependency direction using existing repository tools.
- [ ] Run repository-derived format, check, lint, test, docs, feature, target, and MSRV gates.
- [ ] Confirm binaries retain behavior and no package/module cycle or accidental public API appears.
- [ ] Compile complete templates and label/adapt snippets.
- [ ] Review the final diff for duplicated logic, needless crates, clone-heavy seams, and unrelated edits.
- [ ] Report commands, unavailable checks, compatibility assumptions, and migration risks honestly.
