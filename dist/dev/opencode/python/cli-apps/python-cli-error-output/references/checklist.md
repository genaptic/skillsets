# CLI error-output checklist

## Classification

- [ ] Each public failure class corresponds to a caller action.
- [ ] Internal exceptions are not exposed one-for-one.
- [ ] Usage, validation, not-found, conflict, permission, transient, and internal failures are
      distinguished only where useful.
- [ ] Partial success has a defined status and payload.

## Exit status

- [ ] `0` is reserved for success.
- [ ] Nonzero mappings are compact and documented.
- [ ] Framework defaults have been measured.
- [ ] Shell/system reserved conditions are not reused casually.
- [ ] Cross-platform differences are tested.
- [ ] Existing public codes have a migration plan before change.

## Streams and formats

- [ ] Success data and diagnostics use intentional streams.
- [ ] Failure stdout behavior is explicit.
- [ ] Machine mode emits one parseable schema.
- [ ] Progress, color, prompts, and tracebacks do not corrupt machine output.
- [ ] Partial/streamed output semantics are defined.
- [ ] TTY detection changes presentation only.

## Messages and security

- [ ] Diagnostics identify operation, safe context, cause, and next action.
- [ ] Parser errors show relevant usage.
- [ ] Domain errors do not dump full usage unnecessarily.
- [ ] Tokens, credentials, headers, raw payloads, SQL literals, and sensitive paths are absent.
- [ ] Machine error codes are stable.
- [ ] Correlation identifiers are safe to expose.

## Control flow

- [ ] One command boundary maps domain failures to process behavior.
- [ ] Business logic does not scatter process exits.
- [ ] Debug traceback is opt-in and redacted.
- [ ] Unexpected failures are logged once.
- [ ] Interrupt, cancellation, timeout, and broken pipe are handled deliberately.
- [ ] Cleanup and temporary files are protected on failure.

## Verification

- [ ] stdout and stderr are asserted independently.
- [ ] Status is asserted as an integer.
- [ ] Human and machine modes are covered.
- [ ] TTY and non-TTY behavior is covered.
- [ ] Expected and unexpected failure paths are covered.
- [ ] Default output contains no traceback or secret.
