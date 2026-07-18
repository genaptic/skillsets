# PostgreSQL index-design checklist

## Evidence and purpose

- [ ] Candidate names a constraint or normalized statement family.
- [ ] PostgreSQL version/provider, table size, write rate, and workload window are recorded.
- [ ] Predicate, joins, ordering, projection, limit, parameters, and result cardinality are known.
- [ ] Representative before-plan and system evidence identify an access-path problem.
- [ ] Statistics/query-shape/system bottlenecks were considered before adding an index.
- [ ] Existing index definitions and dependencies are inventoried.

## Definition

- [ ] Access method and operator class support the actual operators.
- [ ] Key order reflects equality, range, ordering, join, and tenant-prefix requirements.
- [ ] Collation, casts, expression identity, direction, and null ordering are explicit.
- [ ] Included columns are payload only and size/visibility tradeoffs are understood.
- [ ] Partial predicate is stable and provably implied by actual query forms.
- [ ] Expression functions and types meet index requirements.
- [ ] Uniqueness, null semantics, and partition-key implications are correct.
- [ ] Index and constraint naming is stable and meaningful.

## Cost and overlap

- [ ] Build time, I/O, CPU, WAL, storage, replication, and backup cost are estimated.
- [ ] Insert/update/delete, HOT, vacuum, analyze, and cache effects are measured or bounded.
- [ ] Existing prefix/overlap candidates are compared structurally.
- [ ] Constraint-backed and rare operational uses are protected.
- [ ] Usage counters include reset, failover, seasonality, and coverage caveats.
- [ ] No drop decision rests on `idx_scan = 0` alone.

## Rollout

- [ ] Existing duplicates or invalid data are checked before a unique build.
- [ ] Regular versus concurrent build is chosen deliberately.
- [ ] Transaction-block restrictions and invalid-index cleanup are planned.
- [ ] Lock/statement timeouts, resource guardrails, replication lag, and observability are defined.
- [ ] Application compatibility and deploy ordering are explicit.
- [ ] Rollback DDL and rollback thresholds exist.
- [ ] Drop dependencies and concurrent-drop restrictions are reviewed.

## Verification

- [ ] Result correctness is unchanged.
- [ ] Representative plans and latency distributions improve.
- [ ] Multiple parameter classes and concurrency are tested.
- [ ] Write and maintenance regressions are measured.
- [ ] Other high-value statement families are checked for plan regression.
- [ ] Executed and proposed evidence are clearly separated.
