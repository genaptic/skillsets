# Python testing strategy checklist

## Risk and scope

- [ ] Critical behaviors and failure impacts are listed.
- [ ] Historical regressions are represented.
- [ ] Security, compatibility, concurrency, and recovery risks are considered.
- [ ] Every proposed test has a clear behavior and oracle.
- [ ] Test levels are chosen by cost and confidence, not by quota.

## Unit and contract tests

- [ ] Deterministic logic has boundary and invalid-input cases.
- [ ] Public API, schema, serialization, and compatibility contracts are explicit.
- [ ] Tests assert observable behavior rather than call choreography.
- [ ] Mocks remain at defined boundaries.
- [ ] Exact messages or snapshots are asserted only when they are public contracts.

## Integration and end-to-end tests

- [ ] Real boundaries are named.
- [ ] Test services and data are isolated from production.
- [ ] Setup and teardown ownership is explicit.
- [ ] A small set of critical end-to-end journeys is protected.
- [ ] Failure artifacts are retained without secrets.

## Fixtures and parameterization

- [ ] Fixture scope is justified.
- [ ] Mutable state cannot leak between tests.
- [ ] Cleanup runs on both success and failure.
- [ ] `autouse` fixtures are rare and visible.
- [ ] Parameter tables represent coherent equivalence classes and boundaries.
- [ ] Case IDs explain failures.

## Determinism

- [ ] Time, randomness, locale, time zone, and environment state are controlled.
- [ ] Temporary filesystem locations are used.
- [ ] Tests do not require a developer's home directory.
- [ ] Fixed ports and uncontrolled network calls are avoided.
- [ ] Parallel execution is safe or intentionally disabled.
- [ ] Flakes have an owner and corrective plan rather than unlimited retries.

## CI and maintenance

- [ ] Pull-request runtime has a budget.
- [ ] Markers and selection commands are documented.
- [ ] Supported Python/platform versions are covered economically.
- [ ] Coverage is interpreted as a gap signal, not a quality score.
- [ ] Obsolete or redundant tests are removed.
- [ ] Uncovered risks and deferred tests are documented.
