# PostgreSQL index-design guide

## Begin with a proven access or enforcement need

An index is a persistent data structure paid for by every relevant write, vacuum cycle,
backup, restore, cache, and maintenance operation. Do not begin from a column list. Begin
from one of these needs:

- Enforce uniqueness or exclusion.
- Support a demonstrated predicate/join/order/group access path.
- Reduce parent-row foreign-key maintenance cost.
- Support specialized search operators.
- Enable a bounded operational workflow.

For each candidate, record the normalized statement family, parameter classes, selected
columns, predicates, joins, ordering, limit, result cardinality, concurrency, write rate,
table size, existing indexes, and representative plan evidence. A proposal without its
workload contract is difficult to review or retire safely.

## Confirm whether an index is the correct intervention

Before adding an index, test competing hypotheses:

- The statement returns so much of the table that a scan is appropriate.
- Cardinality estimates are wrong because statistics are stale or insufficient.
- A cast, function, collation, or operator prevents matching an existing index.
- The query is semantically or structurally inefficient.
- Blocking, I/O, CPU, temp work, or transaction scope—not access—is the bottleneck.
- An existing index already covers the same leading keys and predicate.
- Partitioning, clustering, materialization, or data lifecycle is the actual design issue.
- The desired uniqueness/invariant belongs in a constraint.

Use `postgres-query-performance-review` to establish the mechanism first when evidence is
incomplete.

## Choose access method and operator semantics

B-tree is the default for equality, ranges, and ordered access, but not a universal answer.
PostgreSQL also supports Hash, GiST, SP-GiST, GIN, and BRIN, plus extension-provided methods
and operator classes.

Select based on actual operators and data:

- **B-tree:** equality/range, sorting, prefix-like patterns under compatible operator and
  collation semantics.
- **Hash:** equality-only cases; compare with B-tree operationally before choosing.
- **GIN:** composite values such as arrays, `jsonb`, and text-search tokens; writes and
  pending-list behavior matter.
- **GiST/SP-GiST:** operator-class-specific spatial, range, nearest-neighbor, and partitioned
  search structures.
- **BRIN:** very large tables where values correlate with physical block order; tiny size but
  coarse summaries and potential rechecks.

Operator class, collation, null ordering, and expression identity determine whether a query
can use the structure. Confirm with the exact target version and extension.

## Order multicolumn B-tree keys from the workload

For a B-tree index, leading columns determine how much of the index can be skipped. Equality
conditions on leading columns followed by a range or ordered column are a common useful
shape, but the correct order depends on the query family.

Consider:

- Equality predicates that sharply define a key range.
- First inequality/range predicate.
- Required ordering and direction.
- Join lookup keys.
- Tenant prefix and whether every relevant statement includes it.
- Parameter skew and selectivity.
- Skip-scan behavior on the target version, while avoiding designs that rely on it without
  evidence.
- Multiple important query families that may need different access paths.

“Most selective first” is not a complete rule. Selectivity, ordering, operator support, and
prefix usability must be evaluated together.

Additional key columns may filter within an index but can enlarge the structure and may not
reduce the scanned portion. Keep broad indexes justified.

## Separate key columns from included payload

`INCLUDE` columns are non-key payload. They can enable index-only plans without changing
search or uniqueness semantics. They also increase index size, write cost, and the chance
that large values exceed index tuple limits.

Index-only scans require:

- Every needed column available from the index.
- An access method that supports returning values.
- Heap pages sufficiently all-visible for the visibility map to avoid many heap visits.

A covering index may provide little benefit on frequently updated tables or broad scans.
Measure heap fetches and visibility behavior under realistic maintenance.

## Use partial indexes for stable, provable subsets

A partial index stores rows satisfying its predicate. It is useful when a stable subset is
queried disproportionately, such as active/unprocessed rows.

The planner must be able to prove at plan time that the query condition implies the index
predicate. Semantically related but syntactically incompatible conditions, parameters, or
generic plans can prevent use.

Before choosing a partial index, document:

- Fraction and growth of indexed rows.
- Query forms and parameterization.
- Predicate stability and lifecycle.
- How rows entering/leaving the subset affect writes.
- Uniqueness semantics inside versus outside the predicate.
- Monitoring for subset growth and plan drift.

Do not use partial indexes as a substitute for partitioning or to exclude arbitrary common
values whose distribution changes unpredictably.

## Use expression indexes when the expression is the API

An expression index can support a stable transformation such as normalized case or extracted
JSON value. The query must use an equivalent expression with compatible type/collation.

Confirm:

- Function immutability requirements.
- Exact casts, collation, and operator.
- Update cost.
- Whether a generated column improves clarity and reuse.
- Uniqueness semantics of transformed values.
- Application behavior and locale requirements.

Do not index a function merely to compensate for avoidable type mismatch.

## Treat uniqueness as data integrity

Prefer a `UNIQUE` constraint when expressing a table-level key. Use a unique index directly
when needed for an expression or predicate not expressible by a regular constraint.

Define null semantics explicitly. PostgreSQL can use `NULLS NOT DISTINCT` where nulls should
collide. For partitioned tables, global uniqueness has partition-key restrictions; design
the key and lifecycle together.

Before creating a unique structure on existing data, detect duplicates safely and decide
which record is authoritative. Do not rely on build failure as a data-quality plan.

## Review redundant and overlapping indexes structurally

Potential redundancy requires comparing:

- Access method.
- Key expressions and order.
- Operator classes and collations.
- Sort direction and null ordering.
- Predicate.
- Included columns.
- Uniqueness/exclusion/constraint ownership.
- Validity and readiness.
- Workload plans and usage across a representative window.

A prefix relationship does not automatically make the shorter index redundant. A smaller
index may be cheaper for a frequent query, preserve uniqueness, use different semantics, or
remain valuable for writes/cache.

Usage counters reset and do not show every purpose, especially constraint enforcement and
rare operational queries. Never drop solely on `idx_scan = 0`.

## Model total cost

Estimate:

- Build duration and peak I/O/CPU/WAL.
- Additional storage and backup/restore size.
- Insert/update/delete latency.
- HOT-update eligibility changes.
- Vacuum and analyze work.
- Cache displacement.
- Replication lag and standby replay.
- Ongoing reindex/maintenance burden.
- Per-partition multiplication.

An index that makes one query faster can make the system worse under write load.

## Plan production creation and removal safely

A regular `CREATE INDEX` can block writes while it builds. `CREATE INDEX CONCURRENTLY`
reduces blocking but:

- Cannot run inside a transaction block.
- Performs more work and takes longer.
- Waits for transactions/snapshots.
- Can leave an invalid index after failure.
- Has special uniqueness behavior during phases.
- Still needs lock and resource monitoring.

Verify exact target-version behavior. Use a unique, deterministic name and preflight
duplicate checks for uniqueness.

Before dropping an index, confirm dependencies and production plans, retain rollback DDL,
and consider `DROP INDEX CONCURRENTLY` restrictions. Coordinate one index change at a time
when practical so effects can be attributed.

Use `postgres-migration-safety` for the complete rollout.

## Verify the candidate

Validation should include:

- Correctness and uniqueness tests.
- Representative query plans before/after.
- Multiple parameter classes and data distributions.
- Latency/resource measurements under realistic concurrency.
- Write-path and maintenance impact.
- Index size and build/replay effects.
- Plan regression checks for other important statements.
- Observation after rollout with a rollback threshold.

The included inventory helper identifies only simple warning signals in exported JSON. It
cannot prove semantic redundancy, workload value, or safe removal.
