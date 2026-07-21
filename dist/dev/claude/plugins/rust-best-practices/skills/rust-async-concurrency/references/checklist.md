# Async concurrency checklist

## Repository contract

- [ ] Toolchain, edition, MSRV, runtime features, and repository commands are known.
- [ ] No toolchain, dependency, or feature change is hidden in the implementation.
- [ ] Inputs, ordering, resource limits, and side effects are explicit.

## Structure

- [ ] Direct await, join, selection, fan-out, or spawning matches the required lifetime.
- [ ] Every spawned task has a completion and cancellation owner.
- [ ] Fan-out, queues, semaphores, and workers use validated nonzero bounds.
- [ ] Output ordering is preserved or deliberately documented as completion order.
- [ ] Locks are short-lived and do not cross unrelated awaits.

## Blocking and shutdown

- [ ] Blocking work is finite or owned by a dedicated thread.
- [ ] OS-thread joins do not block an async executor worker.
- [ ] Shutdown stops and awaits every producer/registration path, signals cancellation, closes the
  tracker only to enable waiting, and waits for observed completion.
- [ ] Cleanup has a bounded deadline and explicit escalation behavior.
- [ ] A timed-out tracker wait is not reported as task termination; unresolved work is escalated.
- [ ] Timeout/cancellation does not falsely imply an in-flight write was rolled back.

## Tests and evidence

- [ ] Tests cover zero/maximum capacity, ordering, failure, cancellation, and worker exit.
- [ ] A regression test proves `TaskTracker::close` still permits spawning and verifies that the
  service eliminates registration paths before calling it.
- [ ] Timer tests use paused Tokio time or an injected clock without accidental auto-advance.
- [ ] Repository-authoritative format, build, lint, and test commands were executed or skipped
  explicitly.
- [ ] No native/runtime success is claimed without observed evidence.
