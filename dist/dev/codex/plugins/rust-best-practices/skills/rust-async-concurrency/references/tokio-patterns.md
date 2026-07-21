# Tokio patterns

Use these patterns as reviewable starting points. Adapt error types, dependencies, features,
ordering, and shutdown policy to the repository.

## Contents

- [Fixed siblings](#fixed-siblings)
- [Bounded ordered fan-out](#bounded-ordered-fan-out)
- [Cancellation-safe selection](#cancellation-safe-selection)
- [Deterministic timer tests](#deterministic-timer-tests)
- [TaskTracker shutdown](#tasktracker-shutdown)
- [Task-set failure policy](#task-set-failure-policy)

## Fixed siblings

Use `try_join!` when a small fixed set of futures can be cancelled by dropping on the first error:

```rust
let (profile, orders) = tokio::try_join!(client.profile(), client.orders())?;
```

Do not use it if one branch performs a non-idempotent side effect whose outcome must be observed.
Run that operation under an explicit protocol and reconcile unknown outcomes.

## Bounded ordered fan-out

`buffer_unordered(limit)` bounds in-flight futures but emits completion order. Attach the input
index and sort after collection when callers require input order. Validate `limit` as
`NonZeroUsize` before construction. See the bundled `bounded_fanout.rs` for a complete adaptable
snippet with cancellation.

Decide whether the first error should stop admission. `try_collect` returns on the first error and
drops the stream, which drops in-flight futures; this is correct only when those futures are
cancellation-safe. To collect all outcomes, return indexed `Result` values as ordinary items and
collect without `try_collect`.

## Cancellation-safe selection

Before placing a future in `select!`, determine what dropping it means. Receiving from Tokio
channels and waiting on a cancellation token are common cancellation-safe operations. A custom
future that mutates state before yielding may not be.

Use a biased selection only when priority is part of the contract and starvation has been
considered. Otherwise Tokio randomizes branch order to improve fairness.

Pin stateful futures when polling the same future across loop iterations. Recreating a sleep or
I/O future on every iteration can reset progress or lose state.

## Deterministic timer tests

Prefer:

```rust
#[tokio::test(start_paused = true)]
async fn timeout_expires() {
    let result = tokio::time::timeout(
        std::time::Duration::from_secs(5),
        std::future::pending::<()>(),
    )
    .await;
    assert!(result.is_err());
}
```

Immediate paused time uses Tokio's current-thread test runtime. Tokio auto-advances to the next
timer when no other work can make progress. An outstanding blocking task or real I/O can inhibit
that behavior, so do not mix paused-time assertions with uncontrolled infrastructure.

If logic uses `std::time::Instant`, Tokio pause does not affect it. Inject a clock or consistently
use `tokio::time::Instant` for the behavior under test.

## TaskTracker shutdown

`TaskTracker::close()` allows `wait()` to complete when the tracker is empty. It does not prevent
later `spawn` calls, including calls through a cloned tracker. A waiter that observes a
closed-and-empty interval can complete even if a surviving clone spawns later. Treat admission as
a separate application protocol:

1. stop listeners, receivers, schedulers, and producer loops;
2. await the producer/supervisor tasks or otherwise prove they cannot register more work;
3. signal tracked tasks with cancellation tokens or closed inputs;
4. close the tracker to enable `wait`; and
5. wait under the process shutdown deadline.

Test the invariant explicitly. One regression should demonstrate that a closed tracker still
accepts a spawned task; another should exercise the service's real admission gate and prove no
registration owner survives the transition. If the wait deadline expires, tracked tasks remain
alive unless separately aborted. Retain the handles needed by the documented escalation policy
and report unresolved cleanup rather than claiming termination.

## Task-set failure policy

For `JoinSet`, observe both layers of failure: joining can report cancellation or panic, and the
task output can report a domain error. A typical owner:

1. stops adding work after the first fatal result;
2. cancels siblings if their work is cancellation-safe;
3. drains all join results;
4. records panics separately from domain failures; and
5. returns partial outputs only if the public contract permits them.

Do not use `expect("task should not panic")` in a reusable owner. Convert `JoinError` into an
explicit process or service error with enough context to identify the failed task, without
including secrets.
