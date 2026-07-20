# PostgreSQL migration-safety checklist

## Context

- [ ] Exact PostgreSQL version/provider and migration-runner behavior are recorded.
- [ ] Object sizes, row counts, partitions, growth, read/write rates, and dependencies are known.
- [ ] Transaction age, lock traffic, replication topology/lag, WAL, and storage headroom are known.
- [ ] Application versions, mixed-version window, jobs, reports, CDC, and downstream consumers are mapped.
- [ ] Maintenance window, operator roles, change approval, and recovery readiness are explicit.

## Statement analysis

- [ ] Every statement has lock, scan, rewrite, WAL, disk, transaction, and failure analysis.
- [ ] Exact target-version documentation was checked.
- [ ] Strong-lock acquisition uses a bounded timeout and no uncontrolled retry.
- [ ] Explicit schema qualification and controlled `search_path` are used.
- [ ] Non-transactional statements are split from transaction-wrapped phases.
- [ ] Provider and extension restrictions are included.

## Compatibility and data

- [ ] Expand-and-contract ordering supports old and new application versions.
- [ ] Source of truth and convergence are defined for dual-path changes.
- [ ] Backfills are bounded, idempotent, restartable, and observable.
- [ ] Concurrent writes and late rows cannot escape the final invariant.
- [ ] Existing violations are preflighted before new constraints or uniqueness.
- [ ] Constraint validation is separated where supported and catalog state is checked.
- [ ] Destructive cleanup follows a sufficient disuse/retention window.

## Index and constraint operations

- [ ] Regular versus concurrent index build is deliberate.
- [ ] Concurrent-build transaction restrictions and invalid-object cleanup are planned.
- [ ] Unique-build duplicate behavior and application errors are considered.
- [ ] `NOT VALID` support and new-write semantics are confirmed for the exact constraint.
- [ ] Validation resource/lock cost is rehearsed.
- [ ] Constraint attachment requirements are checked.
- [ ] Partition-by-partition behavior is explicit.

## Observability and control

- [ ] Lock waits/blockers, progress, CPU/I/O, WAL, lag, storage, errors, and latency are monitored.
- [ ] Abort thresholds and authorized decision maker are named.
- [ ] Safe stop, cleanup, resume, and retry procedures are written.
- [ ] Migration bookkeeping is reconciled with non-transactional object state.
- [ ] Communication and incident escalation are prepared.

## Verification and recovery

- [ ] Representative rehearsal results and limitations are documented.
- [ ] Catalog validity, data invariants, app compatibility, and critical query plans are checked.
- [ ] Rollback versus roll-forward path is honest and tested.
- [ ] Data loss/reconciliation implications are explicit.
- [ ] Backup/recovery coverage is confirmed for destructive or high-risk changes.
- [ ] Executed checks are distinguished from proposed checks.
