---
name: postgres-query-performance-review
description: >
  Diagnose PostgreSQL statement latency using sanitized SQL, EXPLAIN evidence, cardinality, buffers, temp work, joins, statistics, waits, parameters, and representative experiments. Use when a query or workload is slow, unstable, or regressed. Do not use for greenfield schema design, broad schema audits, or choosing an index without statement-level evidence.
license: Apache-2.0
metadata:
  skillpack: "postgres-databases"
  version: "1.0.0"
  maturity: "release-candidate"
---

# Outcome

Produce a concrete, reviewable result for the workflow below without overstating what was
observed, executed, or verified.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. Plan interpretation targets PostgreSQL 18;
check it against the deployed version and provider. The optional Python 3.11 helper parses
local EXPLAIN JSON only and never connects to PostgreSQL or executes SQL.

## Use this skill when

- A statement or normalized query family misses a latency, throughput, or resource budget.
- An EXPLAIN or EXPLAIN ANALYZE plan needs safe, evidence-based interpretation.
- Parameter skew, generic/custom plans, stale statistics, join choice, spills, or repeated work may explain instability.
- A performance recommendation needs a correctness-preserving experiment and success metric.

## Do not use this skill when

- The task is greenfield modeling, constraints, tenancy, or RLS design; use `postgres-schema-design`.
- The task is a broad deployed-schema audit; use `postgres-schema-review`.
- The bottleneck is established and the deliverable is an exact index proposal; use `postgres-index-design`.
- The deliverable is rollout mechanics for an approved query/schema change; use `postgres-migration-safety`.

## Inputs

Inspect or obtain:

- PostgreSQL version/provider, instance/storage context, relevant planner and memory settings, and observation window.
- Sanitized SQL shape, statement identifier, parameter classes, transaction/isolation context, and prepared-statement behavior.
- Call frequency, concurrency, client latency distribution, timeout, target budget, and result-size expectations.
- Safe EXPLAIN JSON plus collection options, environment, role, timeouts, and cache/load conditions.
- Relation sizes, statistics freshness/distribution, statement statistics, wait events, locks, I/O, CPU, temp, vacuum, and application traces as available.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- `EXPLAIN ANALYZE` executes the statement; never use it casually on mutating, volatile, or expensive production work.
- Use approved roles/environments, bounded timeouts, sensitive-literal redaction, and explicit transaction/side-effect analysis.
- Do not change planner settings, memory, schema, indexes, or SQL in production before a representative correctness and performance experiment.
- Never claim one run, one parameter, or one plan proves a population-wide improvement.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. Define the performance problem. Record environment, statement family, parameter classes, call rate, concurrency, latency distribution, target, data scale, and collection provenance.

2. Assess collection safety. Choose `EXPLAIN` versus `EXPLAIN ANALYZE`, identify side effects and sensitivity, set approved role/environment and timeouts, and redact the artifact.

3. Read the root and dominant path. Compare planning/execution and client time, estimated/actual rows, loops, row flow, removed rows, buffers, temp, WAL, sorts, hashes, and parallel workers.

4. Identify estimate and access-path mismatches. Evaluate skew, correlation, statistics, prepared plans, type/operator/collation alignment, partition pruning, sequential/index scans, and repeated inner work.

5. Review query semantics and transaction behavior. Preserve null, duplicate, ordering, locking, and isolation semantics while checking joins, existence tests, projections, expressions, pagination, and ORM output.

6. Correlate system evidence. Separate plan execution from lock waits, I/O, CPU, connection queues, checkpoints, vacuum debt, network/client fetch, and retries.

7. Form ranked hypotheses. Connect each to concrete evidence, confidence, expected mechanism, and possible regressions or write/maintenance cost.

8. Design minimal experiments. Change one factor at a time, use representative parameters and concurrency, verify result equivalence, collect multiple runs, and define success/rollback criteria.

9. Report recommendation, evidence limits, follow-up index/schema/migration work, and exactly which checks were executed.

## Verification

Before claiming completion:

- Statement identity, parameter classes, workload distribution, target, environment, and plan provenance are explicit.
- Plan collection safety and sensitive-data handling are documented.
- Actual rows, loops, dominant work, filters, buffers, temp, joins, sorts, hashes, and parallelism are interpreted correctly where present.
- Statistics, prepared-plan, query-shape, transaction, and system-wait hypotheses are considered.
- Every proposed change preserves results and has a representative experiment, metric, regression check, and rollback.
- No unexecuted SQL or one-off observation is represented as production proof.

## Output contract

Return:

- Sanitized workload context, target budget, evidence provenance, and safety limits.
- Plan synopsis with dominant path, row/loop interpretation, estimate errors, buffers/temp, and wait/system correlation.
- Ranked findings and hypotheses with confidence.
- Minimal experiment matrix including correctness, representative parameters, load, measurements, and regressions.
- Recommendation, index/schema/migration referrals, rollout considerations, and residual risks.
- Commands or queries proposed or executed and clearly labeled evidence.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [query-performance-review-template.md](assets/query-performance-review-template.md)
- [explain-plan.example.json](assets/explain-plan.example.json)
- [summarize_explain_json.py](scripts/summarize_explain_json.py)
- [Routing and behavior evals](evals/evals.json)
