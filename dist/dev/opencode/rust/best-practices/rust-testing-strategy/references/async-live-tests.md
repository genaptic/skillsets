# Async and live tests

## Deterministic async tests

Use `#[tokio::test(start_paused = true)]` for timer-driven logic on Tokio's current-thread test
runtime. Tokio auto-advances when no other work can progress. Real I/O or a running blocking task
can inhibit auto-advance, so keep paused-time tests hermetic.

Prefer a readiness channel, bound listener address, or health probe over `sleep`. Wrap every
readiness and external wait in a total timeout so a failure produces a diagnostic rather than a
hung suite. Retain and await server task handles; do not detach them between tests.

If production logic uses `std::time::Instant`, Tokio's paused clock does not control it. Inject a
clock or switch the relevant behavior consistently to Tokio time.

## Authorized live tests

Require an explicit opt-in and record the authority. Verify that endpoint configuration targets a
local disposable service or approved test tenant, never production. Give each test a unique
namespace and least-privilege credential, redact diagnostics, and bound all retries and waits.

Register cleanup when the fixture is created. Cleanup may remove only resources carrying the
test's ownership marker and contained under its exact fixture root/tenant. Report cleanup failure
alongside the original result.

When Docker, a client executable, credentials, or offline images are unavailable, report the test
as unavailable or skipped according to repository policy. Do not install dependencies or download
images implicitly, and do not record a pass.
