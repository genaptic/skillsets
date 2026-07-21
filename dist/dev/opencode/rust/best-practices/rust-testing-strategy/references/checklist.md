# Rust testing checklist

## Contract and placement

- [ ] Repository toolchain, workspace selection, features, lockfile, CI, and commands are known.
- [ ] Each test states the user-visible invariant or regression it protects.
- [ ] The narrowest trustworthy unit/integration/doctest/binary/e2e level is selected.
- [ ] Integration tests use public APIs; unit helpers stay in test-only modules/support code.
- [ ] Production code does not gain a test-only shape or invariant bypass.

## Determinism and safety

- [ ] Time, ports, paths, environment, randomness, concurrency, and external state are controlled.
- [ ] Tokio timer tests use paused time correctly or an injected clock, not arbitrary sleeps.
- [ ] Numeric inputs include zero, bounds, `NaN`, and infinities where applicable.
- [ ] Cleanup is exact, owned, bounded, and cannot delete outside the fixture.
- [ ] Process-global environment is not mutated while other threads can run.

## Live evidence

- [ ] Network/container/service access has explicit authority and isolated credentials.
- [ ] Live endpoints cannot resolve to production and side effects are documented.
- [ ] Missing infrastructure is reported as unavailable/skipped according to policy, never passed.
- [ ] Exact commands, versions, permissions, effects, results, and cleanup are recorded.
