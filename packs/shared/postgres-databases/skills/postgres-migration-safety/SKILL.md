---
name: postgres-migration-safety
description: >
  Plan and review PostgreSQL production changes for locks, scans, rewrites, compatibility, bounded backfills, constraint validation, concurrent indexes, replication, observability, failure cleanup, and rollback or roll-forward. Use when a target schema or data change is approved for rollout. Do not use to choose the domain model, diagnose a query, or design the backup program.
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

Portable across Claude Code, Codex, and OpenCode. Guidance targets PostgreSQL 18, but verify
lock, rewrite, transaction, partition, and provider behavior on the exact deployed version.
The optional Python 3.11 auditor reads SQL text only and cannot prove safety.

## Use this skill when

- Approved DDL or data changes must be sequenced for a live PostgreSQL system.
- A large table needs columns, types, constraints, indexes, backfills, repartitioning, or destructive cleanup.
- Migration-runner transactions, lock waits, long snapshots, WAL, replicas, mixed application versions, or failure state create risk.
- Operators need preflight, go/no-go, monitoring, abort, cleanup, rollback, and verification steps.

## Do not use this skill when

- The target data model or invariant is not yet designed; use `postgres-schema-design`.
- The performance mechanism or exact index is unresolved; use `postgres-query-performance-review` or `postgres-index-design`.
- The task is a broad review of current deployed objects; use `postgres-schema-review`.
- The task is defining backup, PITR, retention, or recovery exercises; use `postgres-backup-recovery`.

## Inputs

Inspect or obtain:

- Exact PostgreSQL version/provider, extensions, topology, replicas/CDC, storage/WAL headroom, and operational limits.
- Exact proposed DDL/data operations, dependencies, table/index sizes, partitions, row counts, growth, and read/write rates.
- Migration-runner transaction/retry/bookkeeping behavior, execution role, `search_path`, and deployment tooling.
- Old/new application behavior, jobs, reports, feature flags, compatibility window, and downstream consumers.
- Lock/transaction baselines, latency/error budgets, maintenance window, observability, backup/recovery state, and operator authority.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Do not execute production SQL, backfills, or destructive commands without explicit change approval and an authorized operator.
- Check exact target-version documentation and catalog/workload evidence; do not generalize lock or rewrite behavior from development.
- Use bounded lock/statement timeouts and retries, explicit schemas, observable phases, numerical abort criteria, and safe cleanup.
- Treat a down migration that deletes data as destructive, not automatic rollback; state reconciliation and recovery consequences honestly.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. Establish current/target state and compatibility. Record version/provider, objects, sizes/load, dependencies, topology, runner behavior, application versions, invariant, and recovery posture.

2. Decompose the change into statements and data work. For each, identify lock, scan/rewrite, WAL/disk, transaction rule, snapshot wait, replication effect, compatibility, and failure state.

3. Choose expand-and-contract phases. Add compatible structures first, deploy old/new-aware code, backfill/validate, cut over observably, then contract only after proof of disuse.

4. Design bounded data work. Define stable cursor, eligibility, idempotency, batch/commit/throttle, concurrent-write convergence, checkpoints, progress, failure handling, and final sweep.

5. Stage constraints and indexes. Preflight invalid data, use `NOT VALID`/validation where supported, plan unique/index builds and transaction restrictions, and handle invalid or partial objects explicitly.

6. Control execution. Set schema qualification, role, timeouts, runner transaction boundaries, bounded retries, resource windows, and operator commands for pause/resume/cleanup.

7. Define observability and go/no-go. Set baselines and warning/abort thresholds for locks, transactions, CPU/I/O, WAL, lag, storage, errors, latency, vacuum, and progress with named decision owners.

8. Define recovery. State transaction rollback, application rollback switch, invalid-object cleanup, roll-forward, data reconciliation, and when restore/PITR becomes the response.

9. Rehearse and verify. Test representative data/load and mixed application versions, record limitations, then verify catalog validity, invariants, convergence, plans, latency, lag, and residual risk after each phase.

## Verification

Before claiming completion:

- Every statement has documented lock, scan/rewrite, transaction, WAL/disk, replication, compatibility, and failure behavior.
- Application deployment, backfill, validation, cutover, and destructive cleanup are ordered for the mixed-version window.
- Backfills are bounded, restartable, idempotent, observable, and converge under concurrent writes.
- Constraint/index transaction restrictions, invalid-state cleanup, and exact target-version behavior are checked.
- Go/no-go, numerical abort criteria, operator authority, safe stop/resume, rollback or roll-forward, and recovery triggers are explicit.
- Rehearsal and production verification evidence are distinguished, and no unexecuted change is called successful.

## Output contract

Return:

- Change context, risk classification, current/target state, assumptions, dependencies, and compatibility window.
- Statement hazard table covering locks, scans/rewrites, WAL/disk, transactions, failure state, and replication.
- Phased expand/backfill/validate/cutover/contract runbook with exact approvals and operator boundaries.
- Observability dashboard inputs, go/no-go checks, warning/abort thresholds, and safe control actions.
- Failure cleanup, rollback/roll-forward, reconciliation, and restore/PITR trigger.
- Rehearsal results, commands proposed or executed, verification evidence, sign-off, and residual risks.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [migration-plan-template.md](assets/migration-plan-template.md)
- [phased-migration.example.sql](assets/phased-migration.example.sql)
- [audit_migration_sql.py](scripts/audit_migration_sql.py)
- [Routing and behavior evals](evals/evals.json)
