# Networking checklist

## Boundary

- [ ] Toolchain, client versions/features, TLS/proxy/auth policy, and repository commands are known.
- [ ] Clients, channels, and pools have long-lived owners and documented shutdown behavior.
- [ ] Wire DTOs, domain types, and error categories are separated deliberately.

## Reliability and safety

- [ ] Base URL scheme, authority, userinfo, query, fragment, and path semantics are validated.
- [ ] Credentialed clients require HTTPS; redirects are disabled or use a bounded, reviewed,
  same-origin HTTPS policy, and local HTTP tests use a separate credential-free client.
- [ ] One total deadline covers queue, connect, request, body, retry, and cleanup phases.
- [ ] Retryability is protocol-specific, bounded, jittered, and safe for side effects.
- [ ] Non-finite or out-of-range numeric policy values are rejected.
- [ ] Concurrency, queues, response bodies, messages, and retry work are bounded.
- [ ] Error text is truncated and redacted; secret headers and URLs never reach logs.
- [ ] Invalid JSON/schema is a non-retryable decode error; response-body I/O remains transport.

## Pools and evidence

- [ ] Pool capacity derives from server limits, reservations, all consumers, and maximum replicas.
- [ ] Tests cover cleartext and redirect refusal, hostile URLs/bodies, decode classification,
  deadlines, retry ceilings, outcome unknown, and overload.
- [ ] Live network/container tests have explicit authority, isolation, and disposable credentials.
- [ ] Unavailable infrastructure and unexecuted checks are reported rather than passed.
