---
name: python-cli-testing
description: >
  Design or implement Python CLI tests across in-process runners and real subprocesses, covering installed entry points, parsing, exit status, stdout/stderr, stdin, configuration, filesystem isolation, TTY behavior, machine output, signals, pipes, shell quoting, mutation, and cross-platform CI. Use when verifying a command interface. Do not use for repository-wide test strategy or for choosing the failure contract itself.
license: Apache-2.0
metadata:
  skillpack: "python-cli-apps"
  version: "1.0.0"
  maturity: "release-candidate"
---

# Outcome

Produce a concrete, reviewable result for the workflow below without overstating what was
observed, executed, or verified.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. The optional matrix generator requires
Python 3.11, reads JSON, writes only an explicit output path, and runs no commands. Adapt
process and signal tests to the supported operating systems and CLI framework.

## Use this skill when

- An existing or new Python CLI needs a focused test architecture.
- Framework-runner tests miss installed entry-point, process, stream, signal, or platform behavior.
- Tests need safe isolation for home/config, environment, stdin, filesystem, TTY, or external boundaries.
- A risk-based CLI CI matrix and stable output assertions are required.

## Do not use this skill when

- The task is the full Python project's unit/integration strategy; use `python-testing-strategy`.
- The task is to define exit statuses, stream policy, or error schema; use `python-cli-error-output` first.
- The task is to redesign commands/options/help rather than verify them; use `python-cli-command-design`.

## Inputs

Inspect or obtain:

- Public command, help, input, output, error, mutation, and compatibility contracts.
- Framework and version, installed entry points, and supported module invocation.
- Current tests, runner fixtures, subprocess helpers, and CI matrix.
- Supported Python versions, operating systems, shells, TTY/non-TTY contexts, and signals.
- Configuration, home/cache/data paths, stdin, filesystem, network, and service boundaries.
- Known flakes, runtime budget, and failure artifacts.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Never point tests at production or the real user's home, configuration, credentials, or data.
- Use argv arrays rather than a shell for ordinary subprocess tests.
- Make writes occur only in temporary or disposable resources.
- Bound subprocess, signal, pipe, and network tests with deterministic readiness and timeouts.
- Do not turn retries into the primary remedy for a race or flake.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. **Restate the public contract.** List invocation routes, inputs, statuses, streams, output modes, mutations, compatibility aliases, and platform promises before choosing test mechanics.

2. **Partition test layers.** Assign fast parser/callback cases to an in-process runner and reserve subprocess tests for installed entry points, process status, buffering, environment, signals, and startup behavior.

3. **Build an isolated harness.** Control working directory, temporary home/config/cache/data paths, environment, locale, time zone, color, TTY behavior, stdin, and disposable external services.

4. **Cover parsing and help.** Test root/subcommand help, version, required/optional/repeated/variadic/exclusive inputs, `--`, leading hyphens, spaces, Unicode, stdin, and configuration precedence.

5. **Assert each channel.** Check integer status, stdout, and stderr independently. Parse machine output and use selective snapshots only for intentionally stable human output.

6. **Exercise effects and failure.** Verify dry run, confirmation, non-interactive refusal, exact mutation scope, idempotent repeat, partial failure, cleanup, expected errors, and unexpected defects.

7. **Add process edge cases.** Use deterministic readiness and bounded waits for interrupt, timeout, signal, broken-pipe, and streaming cases, with explicit platform exclusions.

8. **Verify installed packaging.** Test the installed console script and documented `python -m` route from outside the checkout, without relying on path injection.

9. **Select a risk-based CI matrix.** Cover representative invocation/output/terminal/platform/result combinations, keep the pull-request path fast, and schedule expensive cases deliberately.

10. **Diagnose failures.** Preserve safe argv, status, streams, environment summary, seeds, and temporary artifact references; fix nondeterminism rather than masking it.

## Verification

Before claiming completion:

- The suite includes both in-process and subprocess coverage for their appropriate boundaries.
- Tests use isolated home/config/environment/filesystem state and cannot target production.
- Status, stdout, stderr, and parsed machine output are asserted independently.
- Installed entry points work outside the checkout.
- Mutation, dry run, confirmation, partial failure, cleanup, and idempotency are exercised.
- Signals, timeouts, pipes, TTY behavior, and platform exclusions are bounded and documented.
- The CI matrix covers supported risk without uncontrolled Cartesian growth.

## Output contract

Return:

- Public CLI test surface and assumptions.
- In-process versus subprocess layer map.
- Isolation harness and fixtures.
- Scenario/dimension matrix with exact assertions.
- CI selection, platform coverage, and runtime/flakiness controls.
- Implemented/proposed tests, executed evidence, skipped cases, and residual risks.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [cli-test-surface.example.json](assets/cli-test-surface.example.json)
- [subprocess-test-skeleton.example.py](assets/subprocess-test-skeleton.example.py)
- [generate_cli_test_matrix.py](scripts/generate_cli_test_matrix.py)
- [Routing and behavior evals](evals/evals.json)
