# Python exception policy

## Scope

- Package or service:
- Public callers:
- Process boundaries:
- Logging boundary:
- User-facing boundary:
- Retry boundary:

## Exception taxonomy

| Exception | Meaning | Caller action | Retryable | Public API |
|---|---|---|---|---|
| `DomainError` | Base for expected domain failures | Inspect subtype | No | Yes |
| | | | | |

## Translation boundaries

| Lower-level failure | Boundary | Public exception | Chaining policy | Logged here |
|---|---|---|---|---|
| | | | `raise ... from exc` | No |

## Logging policy

- Expected failures:
- Unexpected failures:
- Correlation/context fields:
- Sensitive fields to redact:
- One authoritative logging boundary:

## Warning and deprecation policy

- Warning categories:
- `stacklevel` convention:
- Deprecation introduction:
- Removal version:
- Test expectations:

## Cleanup and partial failure

- Context managers:
- Compensating actions:
- Idempotency:
- Cancellation/interrupt behavior:

## Verification

- [ ] Each public exception has tests.
- [ ] Original causes are preserved where useful.
- [ ] Cleanup occurs on failure and cancellation.
- [ ] Errors are logged once with safe context.
- [ ] Retry behavior is bounded and observable.
