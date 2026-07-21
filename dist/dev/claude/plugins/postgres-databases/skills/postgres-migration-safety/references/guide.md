# PostgreSQL migration-safety guide

## Treat DDL as a production workload

A PostgreSQL migration competes with application transactions for locks, CPU, I/O, WAL,
storage, vacuum capacity, and replication bandwidth. A statement that is instant on an empty
development table can queue behind a long transaction or rewrite terabytes in production.

Before proposing steps, record:

- Exact PostgreSQL major/minor version and managed-service restrictions.
- Table and index sizes, row count, growth, write/read rate, partitions, and dependencies.
- Transaction duration, lock waits, statement timeouts, and connection-pool behavior.
- Replication topology, lag budget, WAL/storage headroom, and standby usage.
- Deployment topology, mixed-version application window, feature flags, and rollback model.
- Migration runner behavior: transactions, retries, timeouts, connection role, and failure
  semantics.
- Backup/recovery readiness for the change class.
- Maintenance window and operator authority.

Read target-version documentation for the exact statement. PostgreSQL changes implementation
and lock behavior over time, and providers may add restrictions.

## Inventory statement-level hazards

For each statement identify:

- Required table/index/object locks and when they are acquired.
- Whether it scans, rewrites, or validates existing rows.
- Additional disk, temporary space, and WAL.
- Whether it can run inside a transaction block.
- Whether it waits for old snapshots or transactions.
- Effect on replicas and logical decoding.
- Application compatibility before, during, and after.
- Failure state and cleanup.
- Rollback versus roll-forward feasibility.

Lock acquisition time and statement execution time are different risks. A fast DDL can wait
indefinitely for a strong lock while blocking later traffic behind it. Use a short
`lock_timeout` appropriate to the operational plan and avoid uncontrolled retries.

## Use expand-and-contract for incompatible application changes

A safe pattern is:

1. **Expand:** add backward-compatible schema or data path.
2. **Deploy writers/readers that handle both forms.**
3. **Backfill and verify.**
4. **Cut over with observability and a rollback switch.**
5. **Stop old writes/reads.**
6. **Contract:** remove old objects in a later release after evidence and retention windows.

Examples:

- Rename through add/copy/dual-read-or-write/cutover/drop rather than a coordinated hard
  rename when clients cannot deploy atomically.
- Change type through a new column, bounded conversion, verification, and cutover when an
  in-place type change would rewrite or break compatibility.
- Split/merge tables through dual-path logic or change capture where needed.
- Replace a constraint by introducing and validating the new rule before removing the old.

Dual-write designs can create divergence. Define source of truth, idempotency, ordering,
repair, and comparison. Do not recommend dual writes casually when one transactional
database update can preserve both forms.

## Add columns and defaults deliberately

Version and expression semantics matter. Some constant defaults can be stored as metadata
without rewriting every row on supported PostgreSQL versions, while volatile defaults may
require row-by-row evaluation. Large historical backfills still create write load and WAL.

For a required new value on a live table, a common staged approach is:

1. Add a nullable column with a compatible default strategy if needed.
2. Deploy application writes for new rows.
3. Backfill existing rows in bounded, restartable batches.
4. Verify no null/invalid values and application convergence.
5. Add a `CHECK (column IS NOT NULL) NOT VALID` where appropriate.
6. Validate the constraint separately.
7. Set `NOT NULL`, confirming the target version can use the validated proof and exact lock
   behavior.
8. Remove temporary compatibility/default behavior only after the contract is stable.

This is a pattern, not a universal script. Evaluate generated columns, partitions, volatile
expressions, logical replication, and ORM behavior.

## Add constraints in stages when supported

Foreign-key and check constraints can often be introduced with `NOT VALID`, which avoids
checking all existing rows during initial creation while still affecting new writes according
to statement semantics. Later `VALIDATE CONSTRAINT` checks historical rows with its own lock
and resource profile.

Plan:

- Preflight existing violations with bounded queries.
- Add the constraint under a short lock-acquisition budget.
- Monitor application failures for newly enforced writes.
- Validate in an approved window with I/O/CPU and replication monitoring.
- Confirm catalog validation state.
- Retain a remediation strategy for bad historical rows.

Not every constraint type supports `NOT VALID`. Unique/primary enforcement is commonly built
through a unique index, potentially concurrently, followed by an approved constraint
attachment where compatible. Confirm exact restrictions, including expressions, partial
indexes, deferrability, partitioning, and transaction boundaries.

## Build indexes with the correct operational mode

A regular index build can block writes. A concurrent build allows ordinary writes but:

- Cannot run in a transaction block.
- Performs multiple phases and waits for transactions/snapshots.
- Takes longer and uses additional resources.
- Can leave an invalid index if it fails.
- Has nuanced behavior for unique builds.
- Needs cleanup and retry logic that recognizes object state.

Preflight name conflicts and duplicates, set resource and lag abort thresholds, observe
`pg_stat_progress_create_index` where available, and verify validity/readiness and query use.
Do not wrap every migration in one transaction if it contains statements forbidden in a
transaction block; split phases explicitly.

## Backfill in bounded, observable batches

A production backfill is an application workload. Design:

- Stable key/range cursor; avoid unbounded offsets.
- Deterministic eligibility predicate.
- Idempotent update and safe restart checkpoint.
- Batch-size and pause controls.
- `lock_timeout` and bounded statement duration.
- Commit between batches where appropriate.
- Rows/second, remaining rows, failures, deadlocks, WAL, lag, storage, and vacuum monitoring.
- Throttling tied to system signals.
- Verification by counts, invariants, samples, and application comparison.
- Handling of concurrent writes and late-arriving rows.
- A final convergence sweep.

Avoid one unbounded `UPDATE` on a large live table. `SKIP LOCKED` may help worker-style
backfills but changes selection semantics and requires careful convergence. Do not assume a
specific batching pattern fits every key, partition, or replication setup.

## Remove or change objects only after proving disuse

Dropping a column, table, index, constraint, type value, or API-visible default is difficult
to roll back when code or data still depends on it.

Before destructive work:

- Stop all reads/writes through application versions, jobs, reports, and ad hoc consumers.
- Inspect dependencies and representative query/usage evidence.
- Preserve required data according to retention/security policy.
- Test rollback or restore path.
- Separate logical disablement from physical removal.
- Use an observation window long enough for rare workloads.
- Coordinate replicas, CDC, caches, and downstream schemas.
- Avoid `CASCADE` unless every dependent object is enumerated and approved.

Column/table drops can hold strong locks even when data removal is internally optimized.

## Control transactions and retries

Understand the migration runner:

- Does it wrap each file or all files in a transaction?
- Can individual steps opt out?
- Does it retry automatically after lock timeout or connection loss?
- Does retry duplicate non-transactional work?
- What role and `search_path` does it use?
- How does it record applied state if a concurrent operation succeeds but bookkeeping fails?

Use explicit schema qualification and a controlled `search_path`. Set timeouts locally where
transaction boundaries allow. Retries should be bounded with jitter and operator-visible
state, not a tight loop that repeatedly queues a disruptive lock.

Long transactions prevent cleanup and can amplify lock/snapshot effects. Keep phases small,
but preserve atomicity where it is the safer property.

## Define observability and abort criteria before execution

At minimum consider:

- Lock waits, blocked/blocking sessions, and transaction age.
- Statement progress and duration.
- Database/host CPU and I/O.
- WAL generation, replication lag, slot retention, and standby replay.
- Storage and temporary space.
- Application errors, timeout rate, latency, and connection utilization.
- Dead tuples, vacuum/analyze activity, and table/index growth.
- Backfill progress, retries, and invalid-object state.

Write numerical or condition-based stop criteria, an authorized operator, and the exact
safe stop/cleanup action. “Monitor closely” is not a runbook.

## Choose rollback honestly

Rollback may mean:

- Transaction rollback before commit.
- Drop/disable the newly expanded object.
- Switch application reads/writes back while retaining new data.
- Roll forward with a corrective migration.
- Restore/replay to a recovery point, which is a major operational event.

A down migration that drops data is not a safe rollback. Test the chosen recovery path in a
representative environment and state data-loss or reconciliation consequences.

## Rehearse and verify

Rehearse on a representative copy with production-like row count, distribution, partitions,
constraints, and transaction load. Capture timings and resource peaks, but treat rehearsal
as an estimate—not a guarantee.

Before completion verify:

- Catalog/object state and constraint/index validity.
- Data invariants and backfill convergence.
- Old and new application versions during the intended compatibility window.
- Query plans and latency for critical paths.
- No sustained lock, lag, storage, or error regression.
- Backup/recovery posture remains valid.
- Contract cleanup occurs only after the observation window.

The included SQL auditor is lexical and conservative. It cannot parse SQL, infer target
version behavior, or prove a migration is safe.
