---
name: postgres-index-design
description: >
  Design, review, consolidate, or retire PostgreSQL indexes using proven constraints and query plans, covering access methods, key order, operator classes, INCLUDE, partial and expression predicates, uniqueness, overlap, total cost, and rollout. Use when an index is the established intervention. Do not use to diagnose an unexplained slow query or to execute a production migration.
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

Portable across Claude Code, Codex, and OpenCode. Guidance targets PostgreSQL 18 and requires
deployed-version, extension, collation, partition, and provider checks. The optional Python
3.11 helper reads an exported JSON inventory only and reports conservative structural signals.

## Use this skill when

- A constraint or representative statement family has established a need for a new or changed index.
- Key order, access method, operator class, collation, sort direction, INCLUDE payload, partial predicate, or expression needs design.
- Potentially duplicate or overlapping indexes need conservative structural and workload review.
- A unique, covering, specialized, partition-local, or concurrently built index needs a verification and cost model.

## Do not use this skill when

- The source of query latency is not established; use `postgres-query-performance-review` first.
- The task is a broad schema or privilege audit; use `postgres-schema-review`.
- The exact index is already approved and only production sequencing remains; use `postgres-migration-safety`.
- The task is greenfield domain modeling without plan evidence; use `postgres-schema-design`.

## Inputs

Inspect or obtain:

- PostgreSQL version/provider, extensions/operator classes, collation, partitioning, and current settings that affect planning.
- Constraint or sanitized statement family, predicates, joins, ordering, projection, limits, parameter classes, and plan evidence.
- Table/partition sizes, distributions, growth, write/update/delete rates, vacuum behavior, and concurrency.
- Complete existing index/constraint definitions, dependencies, validity, size, usage-reset window, and relevant plans.
- Latency/resource target, build window, replication/standby limits, storage budget, deployment tooling, and rollback requirements.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Do not create, rebuild, or drop an index without explicit approval and a migration plan for the exact target.
- Never recommend removal solely from names, prefix shape, size, or zero usage counters.
- Treat unique builds, concurrent operations, invalid indexes, transaction restrictions, WAL, and replication lag as production risks.
- Preserve query semantics and data integrity; verify existing data before enforcing new uniqueness.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. State the workload contract. Name the constraint or statement family, parameters, predicates, joins, ordering, projection, frequency, concurrency, target, and representative evidence.

2. Confirm the intervention. Exclude statistics, query-shape, locking, storage, partition, or existing-index explanations before adding another structure.

3. Inventory existing structures. Compare access method, keys/order, operator classes, collations, directions, predicates, expressions, included columns, uniqueness, validity, dependencies, size, and workload use.

4. Choose method and semantics. Match B-tree, Hash, GiST, SP-GiST, GIN, BRIN, or extension methods to actual operators, data distribution, and maintenance behavior.

5. Design keys and payload. Order B-tree keys from equality/range/order/join needs, separate INCLUDE columns, and account for tenant prefix, visibility, tuple size, and update cost.

6. Design partial, expression, and uniqueness behavior. Prove predicate implication, expression equivalence, function/type requirements, null semantics, partition implications, and existing-data validity.

7. Model total cost. Estimate build resources, storage, WAL, replication, write/HOT, vacuum/analyze, cache, backup, and per-partition burden plus overlap/consolidation options.

8. Plan safe creation or retirement. Choose regular/concurrent operation, define transaction restrictions, duplicate preflight, timeouts, monitoring, invalid-build cleanup, dependencies, application order, and rollback.

9. Verify with representative plans, parameter classes, latency/resource distributions, correctness, write load, maintenance, and regressions before and after rollout.

## Verification

Before claiming completion:

- Candidate maps to a named invariant or representative statement family and proven access-path issue.
- Definition includes method, keys/order, operator class/collation, direction, payload, predicate/expression, uniqueness, and partition scope.
- Existing structures and total read/write/storage/maintenance cost are evaluated.
- Unique data quality, concurrent-build restrictions, invalid-index cleanup, dependencies, and rollback are planned.
- Representative plans, result correctness, concurrency, parameter classes, and write regressions are measured or explicitly pending.
- No index drop or performance claim rests on an incomplete usage window or unrun experiment.

## Output contract

Return:

- Decision and workload/constraint contract with evidence and assumptions.
- Existing index and dependency inventory with structural and workload comparison.
- Exact proposed DDL plus method, key-order, payload, predicate/expression, uniqueness, and collation rationale.
- Cost and redundancy assessment.
- Experiment plan and measured/proposed correctness and performance evidence.
- Production rollout, monitoring, abort threshold, invalid-state cleanup, rollback, and residual risk.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [index-proposal-template.md](assets/index-proposal-template.md)
- [index-inventory.example.json](assets/index-inventory.example.json)
- [review_index_inventory.py](scripts/review_index_inventory.py)
- [Routing and behavior evals](evals/evals.json)
