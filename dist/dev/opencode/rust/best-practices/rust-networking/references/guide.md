# Rust networking decision guide

Use this guide after reading the target repository and service contracts. Concrete crate versions,
features, TLS backends, retry middleware, and deployment budgets remain repository decisions.

## Contents

- [Own and reuse clients](#own-and-reuse-clients)
- [Validate endpoints](#validate-endpoints)
- [Separate wire and domain types](#separate-wire-and-domain-types)
- [Budget time](#budget-time)
- [Retry safely](#retry-safely)
- [Apply backpressure](#apply-backpressure)
- [Bound errors and observability](#bound-errors-and-observability)
- [Budget database pools](#budget-database-pools)
- [Failure modes](#failure-modes)

## Own and reuse clients

Construct a reqwest `Client`, tonic `Channel`, or database `Pool` once at a service/application
boundary and pass cheap clones or typed wrappers. These handles normally share connection state;
putting them behind `Arc<Mutex<_>>` adds serialization without improving safety.

Create a distinct client only when configuration or security isolation is intentionally distinct,
such as separate trust roots, proxy policy, credentials, or tenant boundaries. A local plaintext
test endpoint must not reuse a client that installs production bearer credentials as defaults.
Record the owner that closes or drains the resource during shutdown.

Do not connect for every request. Per-call construction loses connection reuse, repeats DNS/TLS
work, complicates backpressure, and makes timeout behavior harder to reason about.

## Validate endpoints

Parse endpoint configuration into `Url` or the transport's typed endpoint before use. For an HTTP
API base URL, decide and enforce:

- accepted schemes and whether the client carries credentials;
- whether username/password userinfo is always rejected;
- whether query and fragment components are forbidden;
- whether the URL is a hierarchical base;
- whether a trailing slash is required to preserve path joining semantics; and
- whether the base path may contain a deployment prefix.

The bundled bearer-authenticated template intentionally accepts only `https`, sets reqwest's
`https_only` defense, and disables redirects. This prevents a default authorization header from
being sent over cleartext or forwarded after an unexpected redirect. If a protocol genuinely
requires redirects, define a bounded custom policy that rejects downgrade and cross-origin hops;
the custom policy must enforce its own hop limit. If an authorized integration test requires
loopback `http`, construct a separate credential-free test client instead of adding a casual
`allow_http` switch to the production client.

URL `join` follows RFC-style path replacement: a base path without a trailing slash can replace its
last segment. Validate or normalize this once during client construction rather than concatenating
strings on every call.

Do not include credentials in endpoint URLs. Store auth material in a secret provider or injected
configuration and mark sensitive header values where the HTTP library supports it.

## Separate wire and domain types

Transport DTOs model the remote schema, including its nullable fields, strings, and compatibility
quirks. Domain types model validated local meaning. Convert at the boundary with explicit errors.

Keep these categories distinct:

- configuration/build errors;
- connect/DNS/TLS errors;
- local deadline or cancellation;
- remote status with a bounded diagnostic summary;
- decode/schema mismatch;
- domain mapping/validation failure; and
- outcome unknown after a side-effectful request.

Do not store a raw unbounded response body in the error. Do not collapse every category into a
string if callers need retry or user-facing decisions. Reqwest's `Response::json` can fail because
the body is invalid JSON, the JSON does not match the target type, or body transport fails. Use
`Error::is_decode` to preserve deterministic decode/schema failures separately and keep other
response failures in the transport category. Strip full URLs from retained reqwest errors when
path or query data may be sensitive.

## Budget time

Begin with a total operation deadline. At each phase, compute remaining time rather than stacking
independent full-duration timeouts. Account for:

1. waiting for local concurrency or a pool connection;
2. DNS and transport connection;
3. TLS and protocol negotiation;
4. request upload;
5. server processing and response headers;
6. response body consumption;
7. retry delay and subsequent attempts; and
8. bounded cleanup.

Reqwest's builder `timeout` is a total request timeout from connection start through body
completion; `connect_timeout` covers only connection. Confirm the current crate behavior and
WASM/platform limitations for the repository's pinned version.

Tonic's `Endpoint::connect_timeout` covers connection. `Endpoint::timeout` applies locally to each
request but does not add `grpc-timeout` metadata. Use `Request::set_timeout` when the server should
receive the request deadline. These layers solve different problems and should not receive
unrelated full budgets.

Timeout is not rollback. If a non-idempotent request may have reached the server, surface
`OutcomeUnknown` or reconcile using an operation identifier.

## Retry safely

Define a retry policy as data, not an ad hoc loop:

- retryable request classes;
- retryable transport failures and statuses;
- maximum attempts;
- bounded delay and jitter;
- total deadline;
- server `Retry-After` handling;
- idempotency-key behavior; and
- telemetry that excludes secrets.

Reads are often retryable, but not always: a read may consume a queue item or trigger remote work.
Writes are not automatically unsafe: an idempotent PUT or a POST with a server-enforced idempotency
key can be safe. Classify the actual protocol.

Do not retry authentication/authorization failures, most validation errors, or deterministic
decode/schema failures. A response-body I/O failure can remain transport-classified and is
retryable only when the request protocol permits it. Avoid synchronized exponential retry storms
by using bounded jitter and a concurrency limit. Stop retries when the remaining total deadline
cannot support another attempt.

If configuration uses floating-point multipliers or jitter factors, reject `NaN`, positive or
negative infinity, nonpositive values, and values outside the documented envelope before
calculating delays. Prefer integer durations and ratios when they express the policy.

## Apply backpressure

Protect both the remote service and the local process:

- bound request concurrency per upstream;
- bound queued requests or fail fast with overload;
- bound streaming frame/message sizes;
- bound response body consumption;
- bound retry concurrency separately from first attempts; and
- coordinate with the global task limits from `rust-async-concurrency` when needed.

A semaphore limits concurrent fungible work. A bounded worker queue may also enforce ordering and
admission policy. Avoid an unbounded task per incoming item.

For gRPC streaming, consider both application-level message flow and HTTP/2 transport buffering.
Do not assume transport flow control alone protects application memory.

## Bound errors and observability

Before recording a remote body:

1. consume at most a small configured byte limit;
2. record whether truncation occurred;
3. decode lossily or represent non-UTF-8 safely;
4. redact tokens, cookies, known secret fields, and user data according to policy; and
5. attach a safe request/correlation identifier when available.

Content-Length is only a hint and cannot enforce a limit on chunked or dishonest responses. Enforce
the limit while streaming. Stop after `limit + 1` bytes so truncation can be reported without
holding the complete body.

Treat headers as sensitive by default. Never include `Authorization`, `Cookie`, `Set-Cookie`, proxy
credentials, database URLs, or full query parameters in debug output. Make high-cardinality labels
and raw response logging opt-in and policy-reviewed.

## Budget database pools

Do not select `max_connections` in isolation. A conservative per-instance budget is:

```text
(database connection limit - reserved/admin capacity - other application budgets)
/ maximum replicas of this application
```

Round down and reject a result below one. Account for multiple pools in one process, blue/green
deployments, autoscaling bursts, migration jobs, background workers, and read replicas. The
database pool limit is a deployment contract, not merely a code default.

Set acquisition timeout based on the caller's total deadline. A high minimum connection count can
create a startup stampede. Idle and lifetime policies should reflect database/proxy behavior and
must not churn healthy connections needlessly.

Prefer the client's native pool. Build a custom pool only when the dependency lacks a correct one
and the repository accepts the lifecycle complexity.

## Failure modes

Reject or redesign code that:

- constructs a reqwest client, tonic channel, or SQL connection per operation;
- concatenates base URLs as strings;
- accepts URL userinfo or logs secret-bearing URLs;
- permits cleartext HTTP on a client with default bearer credentials;
- follows redirects for a credentialed client without a bounded, same-origin HTTPS policy;
- reads an arbitrary error body into memory;
- maps deterministic JSON/schema decode failures into a retryable transport bucket;
- retries every error or every POST;
- gives every timeout layer the full caller budget;
- treats a timed-out write as definitely failed;
- accepts `NaN`/infinite retry configuration;
- sizes a pool without replicas and other consumers; or
- claims a live service passed when only mocks or structural checks ran.
