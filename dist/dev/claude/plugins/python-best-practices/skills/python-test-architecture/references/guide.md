# Python testing strategy guide

## Begin with risk, not file count

A test suite exists to detect meaningful regressions at an acceptable cost. Map important
behaviors and failure impact before choosing test levels. Include correctness, security,
data loss, compatibility, concurrency, operational recovery, and user-facing contracts.

A high test count can still miss the highest-risk path. A low-level test is valuable when it
is the fastest reliable oracle for a behavior, not because every function deserves a test.

## Choose the narrowest trustworthy boundary

Use the least expensive test that can catch the failure:

- **Unit tests** isolate deterministic logic and edge cases.
- **Contract tests** protect public APIs, schemas, protocols, serialized forms, and plugin
  expectations.
- **Integration tests** exercise real boundaries such as a database, filesystem, process, or
  framework integration.
- **End-to-end tests** protect a small set of critical journeys through the assembled
  system.

Do not mock the behavior under test. A mock is useful at a boundary when the contract is
well defined; it becomes harmful when it reproduces internal calls and lets implementation
changes break tests without changing behavior.

## Organize around behavior

Tests should make the scenario, action, and expected result legible. File structure may
mirror public modules, features, or bounded contexts. Avoid one giant miscellaneous test
module and avoid requiring readers to reconstruct state hidden in distant fixtures.

Prefer assertions on public outcomes. Inspect private state only when no stable public
oracle exists and document that coupling.

## Fixture discipline

Fixtures should:

- Have one clear responsibility.
- Use the narrowest scope that meets cost and isolation needs.
- Create and clean up their own resources.
- Expose meaningful domain objects rather than a bag of mutable state.
- Avoid hidden global mutation and broad `autouse` behavior.
- Compose from smaller fixtures rather than branch on many parameters.

A session-scoped mutable fixture can leak order dependence. A function-scoped expensive
fixture can make the suite unusably slow. Measure and explain scope.

Use `yield` or context managers so teardown remains adjacent to setup. Test cleanup failures
rather than suppressing them silently.

## Parameterization and boundaries

Parameterize a behavior table when inputs share the same setup and oracle. Give cases IDs
that explain the boundary. Include:

- Empty, minimum, maximum, and just-outside values.
- Representative equivalence classes.
- Unicode, locale, and time-zone boundaries when relevant.
- Invalid state transitions.
- Backward-compatibility examples.

Do not compress unrelated scenarios into one opaque parameter table.

## Control nondeterminism

Time, randomness, process state, locale, environment variables, filesystem paths, network
availability, and parallel execution can make tests unreliable.

Inject clocks and random generators where the design allows. Seed randomness only when the
seed is reported on failure. Use temporary directories and restore environment changes.
Avoid fixed ports and shared user-home state. Network tests should target a controlled test
service and be separately selected.

A retry is not a fix for a flaky test. Preserve evidence, identify the source, and either fix
it or quarantine it with an owner and deadline.

## Exceptions and warnings

Assert exception type and stable semantic content. Avoid exact full-message assertions when
the text is not a public contract. Use warning-capture tools to verify category, context, and
deprecation behavior.

## Coverage and mutation

Coverage indicates what executed, not whether behavior was checked. Use missing branches to
find gaps, but do not reward assertions that add no discrimination.

Mutation testing or targeted fault injection can assess whether critical assertions detect
plausible defects. Apply it to high-value modules rather than making a slow global gate
without a runtime budget.

## CI design

Keep the default pull-request path fast enough to be used. Split slow or privileged tests by
declared markers. Test the supported Python and platform matrix without multiplying every
dimension unnecessarily.

On failure, retain the seed, environment, logs, captured output, and temporary artifact paths
needed to reproduce the issue, while redacting secrets.

## Definition of done

A strategy is complete when it states:

- Which risks are covered at which level.
- Which real boundaries are exercised.
- How state is isolated and cleaned.
- How nondeterminism is controlled.
- What runs locally, on pull requests, and on a schedule.
- Which gaps remain and who owns them.
