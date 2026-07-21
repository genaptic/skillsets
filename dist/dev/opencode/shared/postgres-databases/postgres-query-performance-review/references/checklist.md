# PostgreSQL query-performance review checklist

## Problem definition

- [ ] PostgreSQL version/provider, instance/storage context, and relevant settings are recorded.
- [ ] Statement identity, normalized SQL shape, and parameter classes are captured safely.
- [ ] Call rate, concurrency, latency distribution, timeout, and target budget are known.
- [ ] Production/staging/synthetic provenance and collection time are explicit.
- [ ] Lock, CPU, I/O, temp, checkpoint, vacuum, network, and queueing evidence is considered.
- [ ] Prepared-statement generic/custom plan behavior is considered where relevant.

## Plan collection safety

- [ ] `EXPLAIN` versus `EXPLAIN ANALYZE` is chosen deliberately.
- [ ] Mutating or volatile statements are not executed in production for diagnosis.
- [ ] Role, transaction mode, statement timeout, and lock timeout are bounded.
- [ ] Plan options are no broader than needed.
- [ ] Sensitive literals, identifiers, paths, and provider details are redacted.
- [ ] The collection itself is not represented as harmless without evidence.

## Plan interpretation

- [ ] Root planning and execution time are compared with client-observed latency.
- [ ] Estimated and actual rows are compared with loop semantics understood.
- [ ] Dominant row flow and repeated work are identified.
- [ ] Rows removed by filters and join filters are reviewed.
- [ ] Buffer, temp, sort, hash batch, WAL, and parallel-worker evidence is interpreted.
- [ ] Node inclusive timing is not naively summed.
- [ ] Sequential scans and index scans are judged by workload rather than labels.
- [ ] Join algorithm is evaluated against actual outer/inner cardinality.
- [ ] Partition pruning behavior is checked when relevant.

## Root-cause analysis

- [ ] Statistics freshness, target, skew, correlation, expressions, and extended stats are considered.
- [ ] Type casts, functions, collations, and operator classes are checked.
- [ ] Query semantics, duplicate behavior, nulls, ordering, locking, and isolation are preserved.
- [ ] ORM-generated SQL and actual bind behavior are reviewed.
- [ ] Index candidates are tied to a specific plan and workload.
- [ ] Planner-method toggles are experiments, not unexplained permanent fixes.
- [ ] System waits and transaction behavior are separated from plan mechanics.

## Experiment and report

- [ ] Each recommendation states evidence, hypothesis, experiment, and success metric.
- [ ] Correctness tests accompany performance tests.
- [ ] Representative parameters and concurrency are used.
- [ ] Multiple runs and latency distributions are compared.
- [ ] Write, storage, maintenance, and regression costs are included.
- [ ] Applied, executed, and merely proposed work are distinguished.
