# Python error-handling guide

## Define the caller contract first

An exception is part of an interface. Decide what the immediate caller can reasonably do:

- Correct input.
- Choose a fallback.
- Retry later.
- Abort one operation.
- Terminate the process.
- Report an internal defect.

Expose distinctions that change caller behavior. Do not create a subtype for every internal
failure when callers cannot act differently.

Expected domain failures should have stable types. Unexpected programmer errors should
usually retain their native traceback rather than being converted into a generic “operation
failed” exception.

## Catch at ownership boundaries

Catch an exception where code can add one of these:

- Recovery.
- Translation to a stable public contract.
- Cleanup not already guaranteed by a context manager.
- Useful context.
- A process or protocol response.

Catching only to log and re-raise often duplicates reporting. Catching `Exception` in every
layer obscures which layer owns the failure.

A top-level worker, request, task, or process boundary may catch broadly to prevent one
failure from escaping the boundary. It should preserve diagnostics, respect cancellation and
termination semantics, and avoid treating all failures as retryable.

Do not routinely catch `BaseException`; it includes interpreter-level control flow such as
`KeyboardInterrupt` and `SystemExit`.

## Translate and chain deliberately

When a lower-level exception would leak an unstable dependency detail, translate it:

```python
try:
    repository.fetch(identifier)
except RepositoryNotFound as exc:
    raise ResourceNotFoundError(identifier) from exc
```

`from exc` preserves the causal chain. `from None` intentionally suppresses displayed
context and should be reserved for a public boundary where the lower-level detail adds no
value and is still available through controlled diagnostics where appropriate.

A bare `raise` preserves the active exception and traceback. Creating a new exception
without a cause can hide why it occurred.

## Messages and data

Exception messages should explain the failed operation and safe identifiers needed for
diagnosis. Do not embed secrets, tokens, connection strings, raw personal data, or large
payloads.

Use exception attributes for structured information a caller must inspect. Keep message
wording stable only when it is explicitly a public contract; otherwise tests should prefer
type and semantic fields.

## Cleanup and resource lifetime

Prefer context managers for files, locks, transactions, temporary state, and other resources.
Use `ExitStack` when the number of resources is dynamic. A `finally` block should contain
cleanup that must run regardless of outcome and should not silently replace the original
exception.

Cleanup itself can fail. Define whether to preserve the primary failure, aggregate failures,
or report cleanup failure separately. Test partial acquisition and cancellation.

## Logging ownership

Log an exception once at the boundary that has the operational context and decides its
disposition. Internal libraries should generally raise, not configure global logging or emit
the same traceback at every layer.

For unexpected failures, include traceback context with `logger.exception(...)` or an
equivalent `exc_info` policy. For expected failures, a concise structured event may be more
appropriate.

Redact sensitive values. Attach correlation, operation, and resource identifiers as
structured fields instead of concatenating uncontrolled objects into messages.

## Warnings and deprecations

Use warnings for conditions where execution can continue and the caller should migrate or
review behavior. Select a specific category. Set `stacklevel` so the warning points to the
caller's code rather than the warning helper.

A deprecation needs an introduction version, replacement, migration path, and planned
removal. Test warning category and location.

## Retry policy

Retry only failures classified as transient and only when the operation is safe to repeat or
has an idempotency mechanism. Bound attempts and total time, add backoff and jitter where
appropriate, respect cancellation and deadlines, and emit observability.

Do not retry validation errors, authorization failures, deterministic bugs, or arbitrary
`Exception`. Do not hide exhaustion; raise a stable failure with the last cause preserved.

## Concurrent and asynchronous failures

Cancellation is control flow, not an ordinary transient error. Preserve it according to the
runtime's semantics. When multiple tasks fail, modern Python may raise an exception group;
review whether callers need selective handling with `except*` rather than flattening all
causes into one message.

## Test the contract

Tests should cover:

- Expected type and structured attributes.
- Chained cause.
- Cleanup on success, failure, and cancellation.
- Logging at one boundary.
- Redaction.
- Warning category and caller location.
- Retry classification and exhaustion.
- Unexpected failures retaining useful tracebacks.
