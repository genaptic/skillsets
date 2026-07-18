# Async concurrency decision guide

Use this reference after inspecting the target repository. Repository policy, runtime features,
MSRV, and operational limits override generic examples.

## Contents

- [Concurrency shapes](#concurrency-shapes)
- [Task ownership](#task-ownership)
- [Synchronization and backpressure](#synchronization-and-backpressure)
- [Blocking boundaries](#blocking-boundaries)
- [Cancellation and time budgets](#cancellation-and-time-budgets)
- [Graceful shutdown](#graceful-shutdown)
- [Local tasks and runtime boundaries](#local-tasks-and-runtime-boundaries)
- [Failure modes](#failure-modes)

## Concurrency shapes

Choose the smallest primitive that states the required relationship:

| Requirement | Prefer | Avoid |
|---|---|---|
| One operation after another | direct `.await` | spawning then immediately awaiting |
| Small fixed sibling set | `join!` or `try_join!` | a task registry with no lifecycle need |
| First event wins | `select!` with cancellation-safe branches | assuming losing branches completed |
| Dynamic owned task set | `JoinSet` or `TaskTracker` | detached `spawn` handles |
| Many homogeneous operations | bounded stream fan-out | collecting unbounded futures |
| One long-lived resource | owner task/thread plus messages | mutex-wrapping every operation by default |

`join!` polls its branches concurrently on one task; it does not provide parallel execution.
`try_join!` returns on the first error and drops the remaining futures, so use it only when that
cancellation behavior is safe. `select!` also drops losing branches unless they are separately
owned; audit every branch for cancellation safety.

Dynamic fan-out needs three explicit decisions:

1. a validated nonzero concurrency limit;
2. whether results preserve input order or completion order; and
3. whether one error stops admission, cancels in-flight work, or permits partial results.

The bundled fan-out template preserves input order after bounded completion and propagates a
shared cancellation token. If completion order is the public contract, remove the sorting step
and document the change.

## Task ownership

Every spawned task needs an owner that observes completion. Record:

- who starts it;
- who cancels it;
- who awaits it;
- what happens if it panics;
- which values it owns; and
- whether it may outlive the initiating request.

Convert borrowed data to owned data at the task boundary, not far upstream. Cheap handle clones
are normal when the underlying type documents shared internals; cloning arbitrary payloads to
satisfy `'static` often signals a poor task boundary.

Use structured concurrency where practical: a parent owns child handles, stops admission after a
failure, requests cancellation, and waits for children before returning. If a background task is
intentionally process-lived, register it in process startup/shutdown rather than discarding its
handle.

Do not interpret dropping a `JoinHandle` as cancellation. Tokio detaches the task when its handle
is dropped. Abort only when abrupt cancellation is safe, then still observe the join result.

## Synchronization and backpressure

Prefer ownership and messages over shared mutable state when one task naturally owns a resource.
When shared state is appropriate:

- use `std::sync::Mutex` for short, non-async critical sections when contention is low;
- recover or propagate poison errors according to repository policy instead of unconditional
  `expect` in reusable code;
- use `tokio::sync::Mutex` only when the protected operation genuinely crosses `.await`;
- never hold either guard across unrelated network or disk work; and
- document lock ordering when more than one lock can be held.

A bounded channel states overload policy. Validate capacity before constructing Tokio channels,
because a zero capacity panics. Decide what producers do when full: wait, fail fast, shed work, or
coalesce. An unbounded channel transfers the memory bound to the process and is rarely an
acceptable default for externally driven traffic.

Semaphores are suitable for a fungible capacity such as concurrent requests. An owner queue is
usually clearer for a single stateful resource because it also owns ordering and lifecycle.

## Blocking boundaries

Prefer an async-native API. For remaining work:

- keep short CPU work synchronous if it cannot starve the executor;
- chunk cooperative CPU loops and yield only when measurement justifies it;
- use `spawn_blocking` for finite blocking calls;
- bound CPU-heavy `spawn_blocking` work separately because Tokio may create many blocking threads;
- use a dedicated OS thread for a long-lived synchronous engine; and
- communicate through bounded commands and typed replies.

`spawn_blocking` work generally cannot be cancelled after it starts. Runtime shutdown may wait for
it indefinitely unless the runtime itself has a timeout policy. Do not run infinite worker loops
inside `spawn_blocking`.

Never call `std::thread::JoinHandle::join` directly from an async task. Move the join into
`spawn_blocking` or finish it after leaving the runtime. A worker shutdown sequence should stop
admission, send a shutdown command or close the channel, then await the blocking join without
occupying an executor worker.

`block_in_place` is multi-thread-runtime-only and suspends the current task's other branches. Use
it only for a narrow documented bridge. `Runtime::block_on` belongs at a synchronous entry point,
not inside an active runtime.

## Cancellation and time budgets

Cancellation is cooperative. A token tells code to stop; each task must select on or periodically
check that signal and release resources. Treat these cases differently:

- cancellation before admission: no side effect started;
- cancellation while waiting for a permit: no side effect started;
- cancellation during a cancellation-safe read: dropping may stop interest safely;
- cancellation after a non-idempotent write starts: outcome may be unknown.

Define one total operation deadline, then allocate remaining time to queueing, connection,
request, body, and cleanup phases. Layered independent timeouts can otherwise exceed the caller's
budget. Preserve a typed distinction among deadline exceeded, caller cancellation, overload, and
transport failure.

Do not return a timeout that implies rollback when a write may continue in another task or worker.
Either wait for its definitive result, return an explicit outcome-unknown error, or design an
idempotency/reconciliation protocol.

## Graceful shutdown

Tokio's documented model has three parts: detect shutdown, tell tasks, and wait for completion.
A robust process sequence is:

1. combine authorized shutdown sources at one boundary;
2. stop listeners, receivers, schedulers, and other admission paths;
3. await each producer or supervisor that can still register tracked work, or otherwise prove its
   registration path is gone;
4. cancel child tokens or close receivers used by the tracked tasks;
5. close the task tracker only to enable its waiter;
6. drain in-flight work within a declared deadline;
7. escalate according to policy if the deadline expires; and
8. surface panics and cleanup failures.

`TaskTracker::close` does not prevent `spawn` or otherwise close admission; new tasks can still be
registered through any surviving clone. It only allows `wait` to complete once the tracker is
empty. A waiter that observes a closed-and-empty interval can complete even if a surviving clone
spawns later. Therefore eliminate every registration path before closing. Closing is not
cancellation, and cancelling a token is not waiting. A complete design needs all three phases. Do
not discard join errors merely to print a clean shutdown message.

Timing out `tracker.wait()` drops only the wait future; it neither aborts nor proves completion of
tracked tasks. Define escalation in advance: retain abort handles for tasks whose abrupt
cancellation is safe, terminate the process when unresolved work makes continued execution unsafe,
or report the remaining tasks and cleanup obligations to the owner. Never print a successful
shutdown result merely because the deadline elapsed.

If a task must flush buffered data, state whether the flush is bounded, whether data may be lost,
and what an operator can do after failure. Avoid hidden infinite cleanup waits.

## Local tasks and runtime boundaries

Use `LocalSet` and `spawn_local` for futures that intentionally use `Rc`, `RefCell`, or another
non-`Send` value. Keep the local executor boundary obvious and avoid forcing local state into
`Arc<Mutex<_>>` only to satisfy `tokio::spawn`.

Prefer one process-owned runtime. Libraries should normally expose async functions rather than
constructing runtimes. A synchronous wrapper may own a runtime only when its threading,
reentrancy, shutdown, and call-context restrictions are documented.

Native `async fn` in traits is useful when the repository MSRV supports it and dynamic dispatch is
not required. Public traits need deliberate `Send` and semver analysis; do not add `async-trait`
automatically to preserve an unexamined design.

## Failure modes

Reject or redesign code that:

- spawns and immediately awaits;
- drops task handles without an explicit process-lifetime owner;
- holds a lock across unrelated `.await` points;
- creates an unbounded queue for external load;
- accepts zero concurrency or worker capacity;
- loses promised ordering through unordered fan-out;
- starts a nested runtime inside async code;
- treats cancellation as transactional rollback;
- blocks an executor thread while joining a worker;
- uses `TaskTracker::close` as though it prevents new task registration;
- times out a tracker wait and reports the tracked tasks as terminated;
- uses wall-clock sleeps in deterministic timer tests; or
- claims shutdown success without observing child completion.
