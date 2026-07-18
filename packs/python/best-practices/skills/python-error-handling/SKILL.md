---
name: python-error-handling
description: >
  Design or review Python exception taxonomy, catch and translation boundaries, causal chaining, cleanup, logging ownership, warnings, and bounded retries for libraries and application internals. Use when callers need a stable failure contract or broad catches hide causes. Do not use for CLI stderr and exit-code design or HTTP error response schemas.
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

Portable across Claude Code, Codex, and OpenCode. The optional auditor requires Python 3.11,
performs static AST analysis without importing code, and uses no network. Confirm framework
cancellation and exception-group semantics for the target runtime.

## Use this skill when

- A library or application needs a deliberate public exception hierarchy.
- Broad catches, silent failures, duplicate logging, or lost tracebacks need review.
- Lower-level dependency errors need translation into domain contracts.
- Cleanup, warnings, deprecations, cancellation, or retry behavior is unclear.

## Do not use this skill when

- The outcome is user-facing CLI messages, stdout/stderr, debug mode, and exit status; use `python-cli-error-output`.
- The outcome is an HTTP, RPC, or message-protocol error schema.
- The task is merely to add one test without changing the error contract.

## Inputs

Inspect or obtain:

- Public callers and the actions they can take for each failure.
- Current exception classes, catch blocks, logging calls, context managers, and retries.
- Process, task, request, transaction, and external-dependency boundaries.
- Cancellation, timeout, idempotency, and partial-failure semantics.
- Sensitive data and structured context that must not appear in messages or logs.
- Current tests, incident examples, and compatibility commitments.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Review statically before changing catch behavior; an exception change can be a public API break.
- Do not expose credentials, raw payloads, connection strings, or personal data in messages or logs.
- Do not add broad retries or catch interpreter control flow as ordinary failure handling.
- Do not suppress a cause or cleanup failure merely to make output shorter.
- The optional auditor reports heuristics and cannot determine whether a broad catch is justified.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. **Identify callers and actions.** For each failure boundary, state who receives the error and whether they can correct, retry, fallback, abort, or only report it.

2. **Inventory current behavior.** Trace raised types, broad catches, translations, cleanup, logging, warnings, retry loops, cancellation, and where context disappears or is duplicated.

3. **Define a minimal taxonomy.** Create stable types only for distinctions that change caller behavior. Preserve unexpected programmer errors and dependency details internally.

4. **Place catch boundaries deliberately.** Catch only where code can recover, translate, add safe context, clean up, or turn failure into a process/protocol result. Limit broad catches to documented top-level boundaries.

5. **Preserve causal evidence.** Use bare re-raise for the same exception and explicit `raise ... from exc` for translations. Use context suppression only with a documented public-facing reason.

6. **Guarantee resource cleanup.** Prefer context managers and define behavior for partial acquisition, transaction rollback, cancellation, and cleanup failure without erasing the primary failure.

7. **Assign logging ownership.** Log once at the operational boundary with safe structured context and traceback for unexpected failures. Avoid global logging configuration in reusable libraries.

8. **Separate warnings and retries.** Use specific warning categories and caller-facing stack levels. Retry only transient, safely repeatable operations with bounded attempts/time, backoff, deadlines, cancellation, and exhaustion evidence.

9. **Update tests and compatibility notes.** Cover type, attributes, cause, cleanup, redaction, warning, retry, cancellation, and unexpected tracebacks. Treat public type or semantic changes as versioned API changes.

10. **Report what remains uncertain.** Name framework-specific cancellation, exception-group, or logging behavior that was not executed and how to verify it.

## Verification

Before claiming completion:

- Public callers can distinguish failures they handle differently.
- Catch blocks have a stated ownership purpose and broad catches are constrained.
- Translated exceptions preserve useful causes and safe context.
- Resources and transactions clean up on success, failure, and cancellation.
- Unexpected failures are logged once with traceback and without sensitive data.
- Warnings point to callers and deprecations include migration expectations.
- Retries are transient-only, bounded, observable, and safe to repeat.
- Tests demonstrate the contract rather than only executing branches.

## Output contract

Return:

- Caller/action matrix and current failure-flow findings.
- Proposed exception hierarchy and translation map.
- Cleanup, logging, warning, cancellation, and retry policy.
- Compatibility impact and staged code changes.
- Tests or verification commands executed or proposed.
- Unverified framework behavior and remaining operational risks.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [exception-policy-template.md](assets/exception-policy-template.md)
- [exception-hierarchy.example.py](assets/exception-hierarchy.example.py)
- [audit_exception_handlers.py](scripts/audit_exception_handlers.py)
- [Routing and behavior evals](evals/evals.json)
