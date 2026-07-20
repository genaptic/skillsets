# PostgreSQL query-performance review

## Workload context

- Environment and PostgreSQL version/provider:
- Statement identifier and sanitized SQL:
- Parameter classes:
- Call rate and concurrency:
- Client latency distribution:
- Target budget:
- Transaction/isolation context:
- Plan collection method/time:
- Cache, load, and data-distribution notes:

## Safety and evidence limits

- Statement side effects:
- Collection role and transaction:
- Timeouts:
- Redactions:
- Unavailable evidence:

## Plan synopsis

- Planning time:
- Execution time:
- Root estimated/actual rows:
- Dominant work path:
- Estimate errors:
- Repeated work:
- Buffers/temp/WAL:
- Sort/hash/parallel notes:
- Lock or system evidence:

## Findings and hypotheses

### PERF-001 — Title

- Evidence:
- Interpretation:
- Hypothesis:
- Confidence:
- Correctness constraints:
- Minimal experiment:
- Success metric:
- Regression/cost:
- Rollback:

## Experiment matrix

| Variant | Parameters/load | Runs | p50 | p95 | p99 | Rows/results equal | Notes |
|---|---|---:|---:|---:|---:|---:|---|

## Recommendation and residual risk
