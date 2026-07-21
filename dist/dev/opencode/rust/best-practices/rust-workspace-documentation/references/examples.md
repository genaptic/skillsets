# Documentation reconciliation examples

## Coordinated behavior refresh

Request: a workspace moves configuration discovery into a library crate, renames a binary flag, and
changes CI to test a feature matrix.

Expected approach:

1. Inspect manifests, the configuration API, parser/help output, tests, workflows, and instructions.
2. Map architecture ownership to the architecture document, the user-visible flag to command docs,
   the feature matrix to contributor/testing guidance, and operational implications to the runbook.
3. Preview those owners plus README summaries that link to them.
4. Edit owners first, validate links/help/commands, then review all consumers for contradictions.

## No-op audit

Request: determine whether a refactor created documentation drift.

Expected approach:

- Establish the change set without assuming a branch name.
- Inspect every plausible consumer of the changed code.
- Return a no-op only after matching each relevant claim to current evidence.
- List inspected documents and evidence; do not create churn to make the task appear productive.

## Public rustdoc boundary

Request: refresh `//!` crate docs, `///` item docs, and doctests without changing Markdown.

Expected approach: route to `rustdoc-maintenance`. Report incidental Markdown drift separately unless
the user expands the scope.

## Combined documentation request

Request: update both public API docs and repository Markdown after an API redesign.

Expected approach: maintain two explicit inventories and two validation tracks. Coordinate shared
terminology, but do not make either skill a runtime dependency of the other.

## Unsafe evidence pattern

Avoid:

> The old contributor guide says to run every feature with `--locked`, so that must remain correct.

Prefer:

> The workflow and task runner select these packages, features, targets, and lockfile flags; the
> contributor guide is updated to match. Any unrun platform matrix remains explicitly unverified.
