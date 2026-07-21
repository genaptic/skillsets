# Python error-handling checklist

## Contract

- [ ] The caller and actions it can take are identified.
- [ ] Expected failures have stable, actionable types.
- [ ] Unexpected programming errors are not flattened indiscriminately.
- [ ] Public exception messages and attributes avoid secrets and unnecessary payloads.
- [ ] Exception names describe conditions, not implementation layers.

## Catching and translation

- [ ] Each catch block recovers, translates, adds context, or owns a boundary.
- [ ] Broad catches are limited to documented top-level boundaries.
- [ ] `BaseException`, interrupts, exits, and cancellation are respected.
- [ ] Translation uses an explicit cause when the lower-level failure is diagnostically useful.
- [ ] A bare `raise` is used when preserving the same exception.
- [ ] Suppressed context with `from None` is intentional.

## Cleanup and partial failure

- [ ] Resource lifetime uses context managers where practical.
- [ ] Cleanup runs after success, error, and cancellation.
- [ ] Cleanup failure does not silently erase the primary failure.
- [ ] Partial acquisition and compensating actions are tested.
- [ ] Transactions have a defined rollback boundary.

## Logging and observability

- [ ] One layer owns authoritative logging.
- [ ] Unexpected failures include traceback context.
- [ ] Expected failures are not logged repeatedly.
- [ ] Structured context is safe and useful.
- [ ] Sensitive values are redacted.
- [ ] Retry attempts and exhaustion are observable.

## Warnings and retries

- [ ] Warnings use a specific category and useful `stacklevel`.
- [ ] Deprecations define replacement and removal policy.
- [ ] Only transient failures are retried.
- [ ] Retried operations are idempotent or protected.
- [ ] Retry count, elapsed time, deadlines, and cancellation are bounded.

## Verification

- [ ] Tests cover type, cause, message/attributes, and caller action.
- [ ] Tests cover cleanup and failure paths.
- [ ] Tests cover warning behavior.
- [ ] Tests prove secrets are not exposed.
- [ ] Unhandled unexpected failures retain diagnostic tracebacks.
