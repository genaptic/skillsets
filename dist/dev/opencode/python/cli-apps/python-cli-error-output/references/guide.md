# Python CLI error-output guide

## Treat failure behavior as public API

A command failure has several independent channels:

- Process exit status.
- Standard output.
- Standard error.
- Logs or telemetry.
- Machine-readable error fields.
- Optional debug traceback.

Define all of them. A readable message paired with an unstable status can still break
automation. A correct status paired with diagnostics on stdout can corrupt a pipeline.

## Classify failures by caller action

Useful classes often include:

- Invocation or parsing error: fix command syntax.
- Invalid user input: correct a supplied value.
- Missing domain object: choose another object or create it.
- Conflict or precondition failure: refresh state or change the request.
- Permission/authentication failure: obtain access or credentials.
- Temporary dependency failure: retry later under policy.
- Internal defect: report with diagnostic identifier.

Do not expose every internal exception as a new public status. Choose distinctions that let
a human or script act differently.

## Assign exit statuses deliberately

`0` means success. Nonzero values are failures, but specific conventions vary across
programs and shells. Document a compact, stable mapping.

Avoid collisions with shell-level conditions commonly represented as command-not-found,
not-executable, or signal-related statuses. Frameworks may choose their own usage-error
status. Confirm actual behavior before promising compatibility.

Keep statuses in the portable process range. Do not return raw HTTP status codes, database
error numbers, or exception classes without a designed mapping.

Partial success needs an explicit contract: success with warnings, a dedicated nonzero
status, or a machine-readable per-item result. Do not silently return success after dropping
failed items.

## Keep streams clean

For a conventional human mode:

- Successful primary data goes to stdout.
- Diagnostics and corrective guidance go to stderr.
- Progress goes to stderr or a separate structured channel.
- A failure that has no result usually leaves stdout empty.

For machine mode, choose one documented policy. One reasonable design emits a structured
error object on stdout and reserves stderr for local execution diagnostics; another emits all
errors on stderr. The key is consistency and no mixed decorative text. Document the policy
per mode.

Flush and streaming behavior matters when output can be partially written before failure.
State whether partial results are valid and how a consumer detects truncation.

## Write actionable messages

A human diagnostic should answer:

1. What operation failed?
2. What safe, relevant target was involved?
3. Why, at the level the caller can act on?
4. What should the user do next?

Avoid blaming language. Do not repeat a full usage page for every domain failure. Parser
errors can show the relevant usage and correction.

Use stable machine fields such as:

```json
{
  "error": {
    "code": "not_found",
    "message": "Project was not found.",
    "details": {"project_id": "safe-id"}
  }
}
```

Do not expose stack traces, tokens, headers, connection strings, SQL literals, full paths,
or raw service responses by default.

## Debug and logging

Default output should be concise. A deliberate `--debug` or environment-controlled developer
mode may include a traceback, but define its interaction with machine output and redaction.

Log unexpected failures once at the boundary that owns process termination. A user message
can include a correlation identifier without reproducing sensitive logs.

Expected failures usually do not need a traceback in normal logs. Unexpected failures need
diagnostic context, but never unrestricted secrets.

## Interrupts, signals, and broken pipes

Treat keyboard interrupt and cancellation as intentional control flow. Clean up temporary
state, avoid a noisy traceback in normal mode, and return/document the platform-appropriate
status.

When downstream closes a pipe, avoid printing a secondary traceback that hides a successful
pipeline decision. Confirm framework and platform behavior; broken-pipe handling differs.

Signal-based status representation can be shell- and platform-dependent. Test rather than
hard-code assumptions into a cross-platform contract.

## Framework translation

Keep domain exceptions separate from the framework's process-exit exceptions. Use one
adapter at the command boundary to map:

```text
domain exception → public error code/status → stream payload
```

Do not scatter `sys.exit` throughout business logic. A main function can return a status,
while the installed entry point translates it once.

## Verification

Capture stdout and stderr independently. Assert integer status, semantic machine code, and
redaction. Exercise parse errors, domain failures, unexpected exceptions, debug mode,
non-TTY execution, interrupt/timeout where practical, and partial output.

The included helper validates a contract without execution by default. Explicit execution
uses an argv array directly, never a shell, but it can still run arbitrary local programs.
Review the JSON and use a disposable environment.
