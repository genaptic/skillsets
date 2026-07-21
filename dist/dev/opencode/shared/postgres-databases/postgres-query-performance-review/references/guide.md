# PostgreSQL query-performance review guide

## Diagnose an observed workload, not an isolated SQL string

A statement is slow in a particular environment, data distribution, concurrency level,
cache state, parameter set, and transaction context. Before proposing a rewrite or index,
record:

- PostgreSQL major/minor version, provider, instance shape, storage, and relevant settings.
- Exact statement shape with sensitive literals parameterized.
- Call frequency, concurrency, latency distribution, timeout, and business budget.
- Parameter classes and whether a prepared statement uses generic or custom plans.
- Relation sizes, row-count estimates, data skew, correlation, and recent growth.
- Blocking, lock waits, I/O saturation, CPU pressure, temp spill, checkpoints, and vacuum state.
- Whether the plan came from production, staging, a representative clone, or synthetic data.
- Plan format and options, collection time, and cache/warm-up conditions.

A single fast or slow execution is not a latency distribution. A plan without operational
context can explain mechanics but not end-to-end impact.

## Collect plans safely

`EXPLAIN` without `ANALYZE` plans but does not execute the statement. `EXPLAIN ANALYZE`
executes it and adds timing and row evidence.

Safety rules:

- Never use `EXPLAIN ANALYZE` on `INSERT`, `UPDATE`, `DELETE`, `MERGE`, DDL, or a volatile
  statement against production merely to inspect it. Use a representative sandbox or an
  explicitly reviewed transaction/rollback strategy, understanding that side effects,
  locks, sequences, external calls, and volatile functions may not be fully undone.
- Even a `SELECT` can be expensive, block, invoke volatile functions, or reveal sensitive
  literals in plan output.
- Use conservative `statement_timeout` and `lock_timeout`, the intended role, and an approved
  environment.
- Prefer `FORMAT JSON` for machine analysis and add `BUFFERS` when actual execution is safe.
- Avoid publishing plan text with literal predicates, relation names, tenant identifiers,
  paths, or provider metadata without redaction.
- Timing overhead can vary; collect only the options needed.

A useful approved form for a read-only statement is conceptually:

```sql
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '500ms';
EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, SUMMARY, FORMAT JSON)
SELECT ...;
ROLLBACK;
```

Do not copy this blindly. `WAL` and some options only help when relevant; a read-only
transaction cannot contain every statement shape.

## Read plans from the outside in and the inside out

Start with the root:

- Execution time versus planning time.
- Estimated total cost and rows.
- Actual rows and loops when present.
- Rows removed by filters or join filters.
- Shared/local/temp block activity.
- Sort/hash memory, batches, and disk spill.
- WAL records/bytes for writes when safely collected.
- Parallel workers planned/launched.

Then follow the path that dominates actual work. Total node time may include children, so do
not naively add every node's time. Look for high loops multiplied by per-loop work, large row
flows, repeated inner scans, and late filtering.

For each important node, compare:

```text
estimated rows ↔ actual rows per loop
planned operation ↔ work actually performed
rows entering ↔ rows emitted
memory expected ↔ spill/batches observed
index condition ↔ residual filter
```

A node with a large estimate error near a join can cause a poor join order or algorithm.
Estimate ratios need context: zero versus nonzero, per-loop reporting, and tiny absolute row
counts can make ratios misleading.

## Interpret common signals

### Sequential scans

A sequential scan is not inherently wrong. It can be optimal when a large fraction of a
table is needed, the table is small, visibility/order needs do not favor an index, or random
access is expensive.

Investigate when a large scan returns very few rows, repeats many times, or violates the
latency budget. Confirm predicate selectivity, type/operator compatibility, expression form,
statistics, and candidate indexes.

### Index scans

An index scan can still be slow because it:

- Visits many heap pages.
- Uses a weak leading key.
- Applies a large residual filter.
- Repeats under a nested loop.
- Has low physical locality.
- Performs many random reads.
- Cannot use an index-only scan due to columns or visibility.
- Uses an index whose predicate/collation/operator class does not match the query.

Do not equate “index used” with “good plan.”

### Nested loops

Nested loops are effective for small outer inputs and selective indexed inner lookups.
They become problematic when estimates understate outer rows or the inner path is repeated
many times. Multiply actual rows/loops and examine the inner access path.

### Hash and merge joins

Hash joins need suitable equality conditions and memory. Multiple batches or temp I/O can
signal spill, but increasing memory globally is not a default fix because memory is consumed
per operation and concurrency matters.

Merge joins can be excellent on already ordered inputs. Expensive sorts or wide row flows
may dominate. Confirm key compatibility and whether ordering serves additional requirements.

### Sorts and aggregation

Inspect sort key, method, space, disk use, input rows, width, and whether ordering is
avoidable or index-supported. For aggregation, compare group estimates, hash batches,
parallel phases, and output cardinality.

### Parallelism

Parallel plans add setup and coordination cost and may launch fewer workers than planned.
Check worker output, skew, concurrency limits, function safety, and whether each worker
repeats excessive work.

## Diagnose cardinality before forcing access paths

Common estimate problems include:

- Stale or insufficient statistics.
- Skewed values hidden by averages.
- Correlated columns modeled as independent.
- Expressions without useful statistics.
- Parameter-sensitive predicates and generic plans.
- Cross-table dependencies the planner cannot know.
- Type casts or functions that alter selectivity and index matching.
- Rapidly changing or partitioned data with uneven distributions.

Consider targeted `ANALYZE`, higher per-column statistics targets, expression statistics,
and extended statistics where supported by the query pattern. Every statistics change has
collection and planning cost; verify on representative statements.

Avoid disabling planner methods or inserting hint-like rewrites as a first-line permanent
fix. Such experiments can help isolate a hypothesis, but the durable correction should
address data, statistics, query shape, schema, or access path.

## Review query shape and semantics

Preserve correctness while simplifying:

- Select only required columns.
- Make predicate types and collation semantics align with columns/indexes.
- Replace accidental row multiplication and late deduplication with correct joins.
- Use `EXISTS` when the requirement is existence, not joined payload.
- Avoid functions/casts on indexed columns unless an expression index is intentional.
- Apply selective predicates before expensive expansion when semantics allow.
- Review pagination; large offsets often perform increasing discarded work.
- Keep transaction scope small and avoid holding locks during remote work.
- Verify CTE, subquery, and view behavior on the target version rather than relying on old
  optimization folklore.
- Treat ORM-generated SQL as SQL: capture the real statement and bind behavior.

A rewrite that is faster but changes null, duplicate, ordering, locking, or isolation
semantics is not a valid optimization.

## Connect the plan to system evidence

Query latency may be dominated by:

- Lock waits or long transactions.
- I/O queueing or storage throttling.
- CPU saturation.
- Connection queuing.
- Temp file pressure.
- Checkpoints or WAL flush.
- Vacuum debt and table/index growth.
- Replication/standby conflicts.
- Network/client fetch time.
- Plan compilation or JIT.
- Application retries.

Plan execution time is not necessarily client-observed time. Correlate with statement
statistics, wait events, logs, system metrics, and traces within an approved observation
window.

## Test one hypothesis at a time

For every recommendation, write:

1. Evidence.
2. Hypothesis.
3. Minimal experiment.
4. Correctness checks.
5. Success metric and regression guard.
6. Production rollout and rollback.

Use representative parameter classes, cold/warm conditions where relevant, and concurrency.
Compare more than one run and report distribution, not just the best result.

The included helper summarizes JSON plans offline. It cannot determine whether the source
query was safe, representative, blocked, parameter-sensitive, or semantically correct.
