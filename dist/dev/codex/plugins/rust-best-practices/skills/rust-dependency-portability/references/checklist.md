# Dependency and portability checklist

## Repository policy

- [ ] Toolchain, edition, MSRV, resolver, lockfile, features, targets, CI, and release rules are known.
- [ ] The need cannot be met more safely by `std`, Cargo, or an existing dependency.
- [ ] No toolchain, target, component, crate, or audit tool is installed implicitly.

## Dependency review

- [ ] Maintenance, MSRV, licenses, advisories, unsafe/FFI, build scripts, proc macros, and native
  requirements are reviewed.
- [ ] Default/optional features and transitive dependency changes are justified.
- [ ] Workspace inheritance and feature unification have been checked.
- [ ] Manifest and lockfile changes are narrow and every changed package is accounted for.

## Portability and evidence

- [ ] Paths use typed path APIs and platform-directory failure returns an error.
- [ ] Processes use argument-based `Command`; secrets are absent from command/log output.
- [ ] Environment is immutable after threading or passed only to a child process.
- [ ] Platform code is isolated behind a small portable interface.
- [ ] Cross-compilation and native runtime evidence are reported separately.
- [ ] Unavailable network, advisory, toolchain, or target checks remain explicit gaps.
