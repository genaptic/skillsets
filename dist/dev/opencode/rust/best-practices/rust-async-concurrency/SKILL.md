---
name: rust-async-concurrency
description: >
  Design and review bounded, cancellable async Rust systems, including task ownership, joins and selection, channels, locks, timeouts, graceful shutdown, local tasks, and sync-to-async bridges. Use when Tokio, futures, streams, spawned work, cancellation, or concurrency limits determine correctness. Do not use when HTTP, gRPC, retry, or database-pool behavior is the primary outcome; use rust-networking instead.
license: Apache-2.0
metadata:
  skillpack: "rust-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

## Outcome

Produce async Rust whose concurrency is explicitly bounded, whose tasks and resources have
clear owners, whose cancellation and shutdown behavior is observable, and whose verification
matches the target repository rather than an assumed Cargo layout.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Follow the target repository's pinned Rust
toolchain, edition, MSRV, runtime, features, and CI policy; Edition 2024 examples require Rust
1.85 or newer. The templates are adaptable snippets and may require already-approved Tokio,
Tokio-util, or futures features; the `TaskTracker` template specifically requires Tokio-util's
`rt` feature. Network research is optional, but without it mark version-sensitive API claims
unverified. Native-client compatibility remains unverified until a validated report records the
client version and exact source SHA.

## Use this skill when

- Choosing between direct `.await`, `join!`, `select!`, streams, `JoinSet`, or owner tasks.
- Bounding fan-out, queues, worker capacity, or access to a finite resource.
- Fixing blocking calls, locks held across `.await`, detached tasks, or clone-heavy ownership.
- Designing cancellation, graceful shutdown, time budgets, `LocalSet`, or a sync/async bridge.

## Do not use this skill when

- HTTP/gRPC semantics, retryability, request deadlines, or connection pools dominate; use
  `rust-networking`.
- The primary task is test placement or test-suite design; use `rust-testing-strategy`.
- The request is general Rust review without a material concurrency concern; use
  `rust-core-best-practices`.
- The user only wants crate/module boundaries or a runtime dependency choice; use
  `rust-project-architecture` or `rust-dependency-portability` respectively.

## Inputs

Inspect the workspace manifests, toolchain files, lockfile policy, CI commands, enabled runtime
features, entry points, task graph, resource limits, failure semantics, and existing tests.
Identify which operations can block, which side effects are cancellable, ordering requirements,
and the maximum acceptable shutdown time. Label missing limits and inferred invariants.

## Safety

- Read repository policy and code before changing it; preserve unrelated worktree changes.
- Do not install a toolchain, add a crate, enable a feature, access a network, start a service,
  or mutate remote state without explicit authority.
- Bound queues and fan-out with validated nonzero capacities. Treat cancellation as a protocol,
  not proof that an in-flight side effect stopped.
- Do not treat `TaskTracker::close` as an admission gate. Stop and await every producer or
  supervisor that can register tracked tasks before closing the tracker to enable its waiter.
- Never report a timed-out write as safely aborted when it may still commit. Do not detach work
  merely to make shutdown appear complete.
- Run only repository-authoritative commands. Do not commit, push, publish, or change Git state.

## Procedure

1. **Establish repository policy.** Read manifests, toolchain pins, CI, features, and existing
   concurrency conventions. Determine the actual verification commands before proposing a
   generic Cargo command.
2. **Map the concurrency shape.** Record producers, consumers, spawned tasks, shared resources,
   ordering, capacities, deadlines, cancellation sources, and task owners.
3. **Choose the least complex primitive.** Prefer direct awaits for sequential work, structured
   joins for fixed siblings, bounded streams for homogeneous fan-out, and owner tasks plus
   messages for long-lived resources. Spawn only work with an explicit lifetime owner.
4. **Design failure and cancellation.** Decide whether sibling failures cancel remaining work,
   whether partial results are valid, and how callers distinguish cancellation, timeout,
   overload, worker exit, panic, and domain errors.
5. **Place blocking boundaries.** Prefer async-native APIs. Use `spawn_blocking` for finite,
   unavoidable blocking work; use a dedicated thread for a long-lived synchronous resource.
   Never block an async executor thread while joining a worker.
6. **Implement shutdown before happy-path polish.** Detect shutdown; stop listeners, receivers,
   schedulers, and every other producer; await supervisors that can still register work; propagate
   cancellation; then close trackers to enable waiting. Drain or abort according to policy under
   one bounded shutdown deadline with an explicit escalation path. Remember that timing out a
   tracker wait does not terminate its tasks.
7. **Verify deterministically.** Test capacities, ordering, first-error behavior, cancellation,
   worker exit, shutdown timeout, and paused-time behavior. Use `#[tokio::test(start_paused =
   true)]` only with the current-thread runtime and account for Tokio time auto-advance.
8. **Review the final diff.** Check for detached tasks, unbounded collections, await-while-locked,
   nested runtimes, ambiguous timeouts, hidden dependencies, and claims unsupported by executed
   checks.

## Verification

- Run the repository's established format, build, lint, and test commands for the affected
  packages and feature sets; do not manufacture a universal `--workspace --all-targets
  --all-features --locked` matrix.
- Add focused tests for zero/maximum capacity, stable output ordering where promised, failure
  propagation, cancellation before and during work, and nonblocking worker shutdown.
- Prove dynamic shutdown eliminates all task-registration paths before closing a `TaskTracker`;
  include a regression test showing that `close()` itself still permits spawning. Test deadline
  escalation with a task that ignores cooperative cancellation and do not report it as stopped.
- For timer logic, use paused Tokio time or an injected clock instead of wall-clock sleeps, then
  verify the test does not depend on unrelated I/O preventing auto-advance.
- Record every command executed, result observed, unavailable check, and remaining runtime risk.

## Output contract

Return the inspected policy and assumptions, concurrency map, chosen primitives and bounds,
cancellation/shutdown contract, files changed, tests and commands actually run, observed results,
and any unverified client/runtime behavior. Separate verified behavior from recommendations.

## Resources

- [Decision guide](references/guide.md) — concurrency shapes, ownership, synchronization, and
  shutdown.
- [Tokio patterns](references/tokio-patterns.md) — corrected fan-out, cancellation, and paused-time
  examples.
- [Sync worker bridge](references/sync-worker-bridge.md) — safe long-lived synchronous ownership.
- [Checklist](references/checklist.md) — implementation and review gate.
- [Sources](references/sources.md) — current primary documentation and decisions.
- [`bounded_fanout.rs`](assets/templates/bounded_fanout.rs),
  [`graceful_shutdown.rs`](assets/templates/graceful_shutdown.rs),
  [`localset_spawn_local.rs`](assets/templates/localset_spawn_local.rs), and
  [`sync_worker_bridge.rs`](assets/templates/sync_worker_bridge.rs) are adaptable snippets, not
  standalone projects.
