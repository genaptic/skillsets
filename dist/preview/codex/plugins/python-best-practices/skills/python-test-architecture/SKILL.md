---
name: python-test-architecture
description: >-
  Use when—and only when—the requested deliverable explicitly concerns repository-wide Python
  test strategy, multi-level test architecture, suite-wide fixture ownership, global determinism,
  coverage policy, flake elimination, CI selection, or runtime budgets. Do not use when no
  repository-wide or multi-layer Python-test design outcome is requested.
license: Apache-2.0
metadata:
  skillpack: python-best-practices
  version: 1.0.0
  maturity: stable
---
# Outcome

Produce a concrete, reviewable result for the workflow below without overstating what was
observed, executed, or verified.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. The optional inventory helper requires
Python 3.11, parses test files without importing them, and uses no network. Framework-specific
execution remains the repository's responsibility.

## Use this skill when

- A Python project needs a new or substantially revised test strategy.
- A repository-wide strategy also needs a focused CLI test matrix; also use
  `python-cli-testing`.
- A package-layout or import-boundary migration also requires unit, integration, or
  package-install tests to be redesigned; also use `python-project-layout`.
- Tests are slow, flaky, order-dependent, over-mocked, or poorly mapped to risk.
- Fixture scope, test data, markers, parameterization, or CI selection needs review.
- The team needs to choose unit, contract, integration, and end-to-end boundaries.

## Do not use this skill when

- The task is package discovery, `src/` layout, or build artifacts without test-architecture
  changes; use `python-project-layout`.
- The task is only command-line stdout, stderr, exit codes, or shell invocation; use
  `python-cli-testing`.
- The request is to diagnose a single application exception rather than the test architecture.

## Inputs

Inspect or obtain:

- System behaviors, critical journeys, failure impact, and known incident history.
- Current tests, fixtures, markers, configuration, and CI commands.
- Supported Python versions, platforms, and concurrency model.
- External boundaries such as databases, filesystems, processes, APIs, and queues.
- Runtime budget, flake history, coverage reports, and failure artifacts when available.
- Constraints on test services, credentials, data privacy, and parallel execution.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Inventory and plan before changing tests or CI.
- Do not connect to production systems or reuse production credentials or data.
- Do not add automatic retries as a substitute for diagnosing nondeterminism.
- Do not install test tools or start external services without approval.
- The optional inventory helper performs static analysis only and cannot judge correctness.
- Never invent helper or tool flags. Inspect the exact `--help` output, declared plugins, and
  checked-in configuration first; otherwise label the command as pseudocode.
- Do not present unsupported helper flags or an unverified plugin invocation as an executable
  repository command.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. **Map behavior and risk.** List critical outcomes, invalid states, compatibility promises, security boundaries, and expensive failures. Rank them before discussing test counts.

2. **Choose the narrowest trustworthy level.** Assign unit, contract, integration, or end-to-end coverage based on the cheapest boundary that can detect the failure with a reliable oracle.

3. **Review organization and public behavior.** Group tests by behavior or stable surface, reduce assertions on implementation detail, and make scenarios and expected results legible.

4. **Design fixtures and test data.** Give each fixture one responsibility, the narrowest justified scope, explicit ownership, and reliable cleanup. Replace mutable global state and broad hidden `autouse` behavior.

5. **Represent boundaries systematically.** Use parameterization for coherent equivalence classes, edge values, invalid transitions, and compatibility examples, with meaningful case IDs.

6. **Control nondeterminism.** Isolate time, randomness, filesystem, environment, locale, time
   zone, network, process, and parallel state. For flake remediation, always define reproducible
   evidence: preserve seed and execution order, capture the first-failure artifacts, state the
   repetition count, and require an explicit zero-flake or other measured pass threshold before
   removing quarantine or retries.

7. **Define selection and CI.** Always name a bounded fast pull-request subset. Keep
   risk-critical unit, contract, and integration checks there when they fit the measured budget.
   Put repeated or randomized runs, parallel stress, and genuinely slow checks in explicitly
   selected extended or scheduled tiers. Do not defer a risk-critical check merely because it is
   labeled integration. Cover supported versions and platforms without an uncontrolled matrix.

8. **Use quality signals carefully.** Interpret coverage as execution evidence, consider targeted mutation or fault injection for critical logic, and track flake and runtime budgets.

9. **Plan incremental remediation.** Prioritize escaped-risk gaps and high-coupling fixtures, add regression cases before refactors, and remove redundant tests only when equivalent coverage is demonstrated.

10. **Verify the strategy.** Run representative subsets in clean and repeated/parallel conditions, confirm selection commands, and document remaining untested risks.

## Verification

Before claiming completion:

- Every high-impact behavior has a named test level and oracle.
- Real versus replaced boundaries are explicit.
- Fixtures and data have isolation and cleanup ownership.
- Time, randomness, environment, filesystem, network, and concurrency controls are defined.
- Local, pull-request, and scheduled selection commands are documented and exercise intended markers.
- Known flakes reproduce deterministically or have an owner and bounded quarantine.
- Coverage, runtime, and skipped-risk reports are interpreted rather than presented as proof.

## Output contract

Return:

- System/risk context and assumptions.
- Behavior-to-test-level map with rationale.
- Fixture, test-data, and determinism design.
- For flake work, a reproduction and elimination evidence plan with preserved seed/order,
  first-failure artifacts, repetition count, and an explicit measured pass threshold.
- Selection, markers, CI matrix, and runtime budget, including the exact bounded fast
  pull-request tier and the extended or scheduled home for stress checks.
- Prioritized remediation or implementation sequence.
- Verification performed, evidence captured, and remaining coverage gaps.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [test-strategy-template.md](assets/test-strategy-template.md)
- [pytest-config.example.toml](assets/pytest-config.example.toml)
- [inventory_tests.py](scripts/inventory_tests.py) — run with
  `python scripts/inventory_tests.py --help`.
- [Routing and behavior evals](evals/evals.json)
