---
name: rust-networking
description: >
  Design and review safe Rust HTTP, gRPC, and database clients, including connection reuse, transport/domain boundaries, retries, deadlines, backpressure, bounded error handling, and pool budgets. Use when network protocol behavior or remote-resource limits determine correctness. Do not use when task orchestration, cancellation propagation, or process shutdown is the primary outcome; use rust-async-concurrency instead.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce a reviewable network boundary that reuses clients and pools, validates endpoints, applies
one explicit time budget, retries only safe operations, bounds concurrency and diagnostic data,
keeps secrets out of errors, and derives capacity from deployment limits.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Follow the target repository's Rust toolchain,
MSRV, edition, lockfile, features, TLS policy, and client versions; Edition 2024 examples require
Rust 1.85 or newer. Templates are adaptable snippets for already-approved reqwest, tonic, SQLx,
Tokio, and futures-util APIs. Network research and live service access are optional and require
explicit authority; without current source access, qualify version-sensitive claims. Native-client
compatibility remains unverified until a validated report records the client version and exact
source SHA.

## Use this skill when

- Designing or reviewing HTTP/REST or gRPC clients and their transport error contracts.
- Reusing reqwest clients, tonic channels, or database pools instead of reconnecting per call.
- Defining base-URL rules, connect/request/body deadlines, retryability, idempotency, or
  backpressure.
- Sizing SQL/database pools across replicas and protecting logs from unbounded or sensitive
  response bodies.

## Do not use this skill when

- General task spawning, queues, locks, or graceful process shutdown dominate; use
  `rust-async-concurrency`.
- The request primarily selects crates, Cargo features, MSRV, or platform support; use
  `rust-dependency-portability`.
- The request primarily designs integration or live-dependency tests; use
  `rust-testing-strategy`.
- The task is generic Rust implementation with no material network boundary; use
  `rust-core-best-practices`.

## Inputs

Inspect manifests and lockfiles, service schemas, endpoint configuration, authentication flow,
TLS/proxy policy, client construction, DTO/domain mapping, timeout layers, retry middleware,
idempotency support, concurrency limits, database connection budgets, deployment replica counts,
observability policy, and existing tests. Identify whether remote operations are reads,
idempotent writes, or non-idempotent writes.

## Safety

- Treat endpoints, response bodies, headers, and remote errors as untrusted. Never echo bearer
  tokens, cookies, credentials embedded in URLs, or unbounded bodies into errors or logs.
- Require HTTPS for clients that install bearer credentials as default headers, and disable
  redirects unless an explicit bounded same-origin HTTPS policy has been reviewed. Use a separate
  credential-free client for an authorized local HTTP test endpoint.
- Do not access live services, start containers, install crates, modify dependencies, or use real
  credentials without explicit authority and an isolated environment.
- Do not retry non-idempotent work unless the protocol has an idempotency key or reconciliation
  contract. A timeout can leave an outcome unknown.
- Reject invalid base URLs, zero limits, and non-finite numeric configuration before use.
- Preserve unrelated changes and do not commit, push, publish, or mutate remote state.

## Procedure

1. **Establish repository and protocol policy.** Read toolchain, dependency, TLS, proxy, auth,
   observability, CI, and generated-client conventions. Derive verification commands from the
   repository.
2. **Map the boundary.** Record endpoint ownership, request/response DTOs, domain conversion,
   authentication, secret locations, request classes, side effects, and capacity limits.
3. **Validate and reuse transports.** Construct long-lived reqwest clients, tonic channels, and
   database pools at an owning boundary. Validate URL scheme, authority, userinfo, query,
   fragment, trailing-path, redirect, and credential-forwarding semantics before joining paths.
4. **Define the time budget.** Start with one caller-visible deadline. Allocate remaining time
   across queueing, connection, request, body, retry delay, and cleanup. Distinguish tonic's
   transport connect timeout, local per-request timeout, and `grpc-timeout` metadata.
5. **Define retryability.** Classify methods/statuses/errors, require a bounded attempt count and
   backoff, honor server guidance within policy, and stop when the total deadline is exhausted.
   Validate multipliers and jitter inputs as finite and within declared bounds.
6. **Bound data and load.** Cap concurrent work, response/error bytes, retry queues, and pool
   connections. Derive per-instance database connections from the server limit, reserved
   capacity, number of applications, and worst-case replicas.
7. **Separate transport from domain.** Map wire DTOs and transport failures at the boundary.
   Preserve actionable transport, status, decode/schema, and domain-mapping categories without
   leaking sensitive payloads or coupling domain models to remote schema churn. Do not retry a
   deterministic decode/schema mismatch.
8. **Verify offline first.** Test URL validation, redaction, byte limits, deadline exhaustion,
   retry classification, idempotency, backpressure, and pool-budget arithmetic with fakes. Run
   authorized live tests only in an isolated environment and report unavailable infrastructure.

## Verification

- Run repository-authoritative format, build, lint, and test commands for the affected packages,
  features, and targets; do not impose a universal Cargo flag matrix.
- Test credentialed base URLs with HTTP and unsupported schemes, credentials, query/fragment
  components, ambiguous path bases, redirect responses, and maliciously large or non-UTF-8 error
  bodies.
- Test invalid JSON and wire-schema mismatches as non-retryable decode errors while preserving
  body-stream failures as transport errors.
- Test retry ceilings, non-idempotent refusal, total-deadline exhaustion, non-finite backoff input,
  cancellation, and overload.
- Test database budgets with zero replicas, over-reservation, multiple applications, and
  deployment scaling. Record actual live-service evidence separately from structural tests.

## Output contract

Return the inspected protocol and repository policy, boundary and capacity map, timeout/retry and
redaction contracts, exact files changed, tests and commands actually run, observed results,
authorized live checks or their absence, and remaining outcome-unknown or compatibility risks.

## Resources

- [Decision guide](references/guide.md) — client reuse, transport mapping, time budgets, retries,
  backpressure, and pools.
- [HTTP reliability](references/http-reliability.md) — base URLs, body bounds, redaction, and total
  deadlines.
- [gRPC and database boundaries](references/grpc-database.md) — tonic timeout layers and pool
  budgets.
- [Checklist](references/checklist.md) — implementation and review gate.
- [Sources](references/sources.md) — primary documentation and decisions.
- [`typed_http_client.rs`](assets/templates/typed_http_client.rs),
  [`grpc_client.rs`](assets/templates/grpc_client.rs), and
  [`sqlx_pool.rs`](assets/templates/sqlx_pool.rs) are adaptable snippets, not standalone projects.
