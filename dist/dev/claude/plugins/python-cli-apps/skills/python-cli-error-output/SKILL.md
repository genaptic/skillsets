---
name: python-cli-error-output
description: >
  Design or review failure behavior for Python command-line applications, including public failure classes, stderr/stdout policy, stable exit statuses, machine-readable errors, debug tracebacks, redaction, interrupts, broken pipes, and exception-to-process mapping. Use when implementing or auditing CLI failures. Do not use for internal library exception architecture or command-tree design.
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

Portable across Claude Code, Codex, and OpenCode. The optional contract helper requires Python
3.11 and validates JSON without execution by default. `--confirm-execute` runs reviewed argv
arrays locally without a shell and never uses the network itself.

## Use this skill when

- A CLI needs a stable mapping from domain failures to process behavior.
- Diagnostics, results, progress, or tracebacks are written to the wrong stream.
- Exit statuses are inconsistent or too coarse for automation.
- Human and machine-readable error modes, debug output, interrupts, or broken pipes need a contract.

## Do not use this skill when

- The task is internal exception taxonomy, cleanup, retries, and logging without a CLI boundary; use `python-error-handling`.
- The task is command names, options, configuration precedence, or help structure; use `python-cli-command-design`.
- The task is only to implement tests for an already agreed contract; use `python-cli-testing`.

## Inputs

Inspect or obtain:

- Existing command transcripts, parser/framework version, and installed entry-point behavior.
- Domain exception classes and which failures callers can act on.
- Current exit statuses, stdout/stderr usage, logging, debug mode, and machine schemas.
- Supported platforms, shells, TTY/non-TTY environments, signals, and streaming behavior.
- Sensitive fields and redaction rules.
- Compatibility commitments and automation consumers.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Do not echo secrets, raw service responses, connection strings, SQL literals, or unredacted payloads.
- Do not expose tracebacks by default or treat a TTY as consent for sensitive diagnostics.
- Do not execute the contract helper unless `--confirm-execute` is intentionally supplied after reviewing every argv.
- Use a disposable environment for executable scenarios; a command can have side effects even though no shell is used.
- Do not claim a signal or framework status is portable until it is measured on supported targets.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. **Identify caller actions and compatibility.** Classify failures only where a person or script can respond differently, and record existing public codes and machine fields.

2. **Observe actual behavior.** Capture status, stdout, stderr, logs, traceback, TTY/non-TTY, human/machine mode, interrupt, timeout, broken pipe, and partial-output behavior before changing it.

3. **Define a compact status map.** Reserve success, assign stable nonzero values to actionable failure classes, account for framework/shell conventions, and define partial success explicitly.

4. **Define stream contracts per mode.** Keep successful result data separate from diagnostics and progress. Ensure machine output is one parseable schema without prompts, color, or decorative text.

5. **Design actionable and safe messages.** State the failed operation, safe context, caller-relevant reason, and next action. Use stable machine codes and redact sensitive values.

6. **Centralize exception translation.** Map domain exceptions to public process results at one command boundary rather than scattering process exits through business logic.

7. **Handle diagnostic depth.** Keep normal output concise, make traceback/debug behavior explicit and redacted, log unexpected failures once, and expose only a safe correlation identifier.

8. **Define control-flow edge cases.** Specify cleanup and status/output behavior for interrupts, cancellation, timeout, downstream pipe closure, and failures after partial output.

9. **Protect compatibility.** Version machine schemas and deprecate changed statuses/messages deliberately. Keep old behavior during a migration window where practical.

10. **Verify independently.** Capture stdout and stderr separately, assert integer status and semantic machine code, inspect redaction, and exercise human/machine and TTY/non-TTY paths.

## Verification

Before claiming completion:

- Every public failure class has a caller action and stable status/machine code.
- Success data, diagnostics, progress, and logs are separated intentionally.
- Machine output parses without color, prompts, tracebacks, or extra text.
- Default messages contain no secrets or internal traceback.
- One boundary owns exception-to-process mapping and unexpected logging.
- Interrupt, timeout, broken pipe, and partial output have tested behavior or documented platform gaps.
- Compatibility tests cover existing statuses and schemas before release.

## Output contract

Return:

- Observed failure matrix by scenario and output mode.
- Public failure classes, exit statuses, and machine error schema.
- stdout/stderr/progress/logging/debug/redaction policy.
- Exception-boundary mapping and control-flow edge cases.
- Compatibility/deprecation plan.
- Executable contract cases, evidence, skipped platforms, and residual risks.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [cli-error-contract.example.json](assets/cli-error-contract.example.json)
- [cli-failure-contract-template.md](assets/cli-failure-contract-template.md)
- [check_cli_contract.py](scripts/check_cli_contract.py)
- [Routing and behavior evals](evals/evals.json)
