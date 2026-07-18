# Sync worker bridge

Use a dedicated thread when a synchronous resource is long-lived, stateful, and not replaceable
with an async-native API.

## Contract

The bridge should define:

- a nonzero bounded command capacity;
- a closed command enum rather than arbitrary closures when auditability matters;
- typed one-shot replies;
- separate admission and operation-result errors;
- whether each operation is cancellable after admission;
- a shutdown command or channel-close protocol; and
- a nonblocking async join path.

The worker thread owns the resource from construction through destruction. If construction fails,
report the failure before callers receive a usable handle. If the worker panics, close replies and
surface a typed worker-exited error.

## Reads and writes

For a cancellation-safe read, a caller may bound the time spent waiting for the reply and discard
late data. For a write that may commit after admission, do not wrap the reply in a timeout that
claims failure. Return a definitive result, or use an explicit `OutcomeUnknown` error plus an
idempotency/reconciliation mechanism.

Bound admission separately. Waiting for channel capacity is cancellation-safe before a command is
sent. Once `reserve()` succeeds and the command is sent, its documented operation semantics apply.

## Shutdown

Use this order:

1. prevent new handle clones or mark the handle closing;
2. reserve capacity and send `Shutdown`, or drop every sender;
3. let the worker finish or reject queued commands according to policy;
4. move `std::thread::JoinHandle::join` into `tokio::task::spawn_blocking`;
5. map thread panic and blocking-task failure separately; and
6. retain actionable state if shutdown cannot complete.

The bundled template is intentionally small. It does not implement crash recovery, durable queues,
or transactional cancellation. Do not imply those properties in a production integration.
