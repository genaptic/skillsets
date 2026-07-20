# HTTP reliability boundary

## Base URLs

Validate the base once during client construction. A credentialed service-client contract should
accept only `https`, reject userinfo/query/fragment, require a host and trailing slash, and permit
only a declared deployment prefix. Pair this with the HTTP client's HTTPS-only setting. Disable
redirects by default; an allowed redirect policy must be bounded and reject cross-origin or HTTPS
downgrade hops. Use a separate credential-free client for an explicitly authorized loopback HTTP
test rather than weakening the production client. Do not silently rewrite an ambiguous URL if
doing so can redirect requests.

## Decode and transport errors

Keep invalid JSON and response-schema mismatches in a non-retryable decode category. A body I/O
failure encountered while decoding remains a transport error and is eligible for retry only when
the operation itself is retry-safe. Reqwest errors can retain full URLs, so remove URL context
before propagating an error when paths or queries can contain sensitive data.

## Diagnostic bodies

Enforce a byte limit while streaming. Content-Length cannot be trusted. Keep at most `limit` bytes,
read one extra byte to identify truncation, decode lossily if text is required, then run a
repository-specific redactor. Prefer a status, safe correlation ID, and small sanitized summary to
the raw body.

Do not call `.text().await` before enforcing a bound. Do not derive `Debug` for wrappers that expose
secrets unless sensitive fields are custom-redacted.

## Deadlines and retries

Track a total deadline from the caller. Each attempt receives the remaining duration after local
queueing and backoff. Refuse another retry when no useful budget remains.

Retry only errors classified by the protocol. Never retry a deterministic decode/schema mismatch.
Preserve an explicit `OutcomeUnknown` category for a timed-out non-idempotent request. An
idempotency key helps only when the server guarantees its scope, retention, and response behavior.

Backoff configuration must have finite, positive, bounded values. Clamp calculated delays to both
the policy maximum and remaining total deadline, and use bounded jitter to avoid synchronized
retry storms.
