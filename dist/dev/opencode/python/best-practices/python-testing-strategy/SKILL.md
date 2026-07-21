---
name: python-testing-strategy
description: >
  Design or review a risk-based Python test suite, including unit, contract, integration, and end-to-end boundaries; fixtures; parametrization; determinism; markers; CI selection; coverage; and flake control. Use when creating or restructuring test architecture. Do not use for package layout changes or a CLI-only test matrix.
license: Apache-2.0
metadata:
  skillpack: "python-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
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
- Tests are slow, flaky, order-dependent, over-mocked, or poorly mapped to risk.
- Fixture scope, test data, markers, parameterization, or CI selection needs review.
- The team needs to choose unit, contract, integration, and end-to-end boundaries.

## Do not use this skill when

- The task is package discovery, `src/` layout, or build artifacts; use `python-project-layout`.
- The task is specifically command-line stdout, stderr, exit codes, or shell invocation; use `python-cli-testing`.
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

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. **Map behavior and risk.** List critical outcomes, invalid states, compatibility promises, security boundaries, and expensive failures. Rank them before discussing test counts.

2. **Choose the narrowest trustworthy level.** Assign unit, contract, integration, or end-to-end coverage based on the cheapest boundary that can detect the failure with a reliable oracle.

3. **Review organization and public behavior.** Group tests by behavior or stable surface, reduce assertions on implementation detail, and make scenarios and expected results legible.

4. **Design fixtures and test data.** Give each fixture one responsibility, the narrowest justified scope, explicit ownership, and reliable cleanup. Replace mutable global state and broad hidden `autouse` behavior.

5. **Represent boundaries systematically.** Use parameterization for coherent equivalence classes, edge values, invalid transitions, and compatibility examples, with meaningful case IDs.

6. **Control nondeterminism.** Isolate time, randomness, filesystem, environment, locale, time zone, network, process, and parallel state. Preserve seeds and artifacts needed to reproduce failures.

7. **Define selection and CI.** Establish a fast default suite, declared slow/integration markers, supported version/platform coverage, and scheduled extended checks without an uncontrolled matrix.

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
- Selection, markers, CI matrix, and runtime budget.
- Prioritized remediation or implementation sequence.
- Verification performed, evidence captured, and remaining coverage gaps.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [test-strategy-template.md](assets/test-strategy-template.md)
- [pytest-config.example.toml](assets/pytest-config.example.toml)
- [inventory_tests.py](scripts/inventory_tests.py)
- [Routing and behavior evals](evals/evals.json)
