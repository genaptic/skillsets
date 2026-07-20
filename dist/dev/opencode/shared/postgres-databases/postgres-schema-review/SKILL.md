---
name: postgres-schema-review
description: >
  Audit an existing PostgreSQL schema and deployed catalog state for integrity, ownership, privileges, search-path exposure, constraints, RLS, partitions, indexes, and operational drift. Use when reviewing current DDL, dumps, migrations, or catalog snapshots. Do not use for greenfield data modeling, one slow-query diagnosis, or applying remediation in production.
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

Portable across Claude Code, Codex, and OpenCode. Catalog guidance targets PostgreSQL 18;
adapt it to the deployed version and provider permissions. The optional renderer requires
Python 3.11, emits SQL only, never connects to a database, and refuses to overwrite output.

## Use this skill when

- An existing database, schema dump, migration history, or catalog snapshot needs a structured audit.
- Ownership, grants, default privileges, `search_path`, role attributes, or RLS behavior may violate a trust boundary.
- Constraints, indexes, partitions, generated values, or dependencies may have drifted from intended DDL.
- Review findings need severity, confidence, evidence, minimal remediation, and rollout implications.

## Do not use this skill when

- The task is to create the target domain model from first principles; use `postgres-schema-design`.
- The task is to diagnose a particular statement from EXPLAIN evidence; use `postgres-query-performance-review`.
- The design decision is complete and only low-risk rollout remains; use `postgres-migration-safety`.
- The task is backup topology or recovery assurance; use `postgres-backup-recovery`.

## Inputs

Inspect or obtain:

- Environment, PostgreSQL major version/provider, database identity, collection time, and review authorization.
- Intended domain invariants, tenant model, owner/runtime/support/reporting roles, and privilege boundary.
- Version-controlled migration history and schema-only dump or DDL.
- Bounded catalog evidence for objects, columns, constraints, indexes, policies, partitions, ACLs, dependencies, sizes, and statistics.
- Representative workload or plan evidence when evaluating performance-related objects.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Default to supplied files or read-only catalog collection under a non-modifying role with bounded timeouts.
- Do not collect business rows, secrets, literal query parameters, or unrestricted role membership data without need and approval.
- Never infer RLS safety, privilege safety, or index usefulness from names or one incomplete snapshot.
- Do not apply remediation; identify lock, rewrite, replication, compatibility, and rollback concerns for a separate approved rollout.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. Define scope and evidence quality. Record environment, version/provider, objects, intended invariants, collection identity/time, exclusions, and known blind spots.

2. Inventory namespaces and dependencies. Reconcile extensions, collations, schemas, relations, routines, types, sequences, triggers, ownership, and migration history.

3. Review roles and privileges. Examine elevated attributes, memberships, schema ACLs, `search_path`, object grants, default privileges, sequence/routine access, and security-definer behavior.

4. Review integrity. Compare keys, tenant-scoped uniqueness, nullability, defaults, generated values, checks, exclusions, foreign keys, actions, validation state, and referencing-side support with intent.

5. Review RLS by effective role. Inspect enabled/forced state, policy commands/roles/modes/expressions, bypass identities, session context, pools, views, functions, and write checks.

6. Review partitions and indexes. Check bounds, default partition, drift, pruning intent, validity/readiness, structural redundancy, constraint purpose, workload evidence, size, and reset-sensitive usage counters.

7. Rank findings. For each, state evidence, intended and observed behavior, consequence, severity, confidence, minimal remediation, and why it matters.

8. Plan verification and remediation. Identify existing-data checks, lock/rewrite behavior, deployment order, replication effects, rollback or roll-forward, role tests, and success criteria.

9. Report confirmed controls, evidence gaps, residual risk, and explicitly deferred query/index/migration/recovery work.

## Verification

Before claiming completion:

- Review scope, collection identity/time, version/provider, intended invariants, and evidence limitations are explicit.
- Ownership, schema privileges, `search_path`, object/default grants, and elevated role behavior are covered.
- Constraints, validation state, RLS, partitions, indexes, dependencies, and operational metadata are reconciled.
- Every material finding includes evidence, consequence, confidence, remediation, rollout concerns, and verification.
- No index removal or security conclusion rests on one ambiguous counter or object name.
- No unapproved database changes or sensitive data collection are represented as performed.

## Output contract

Return:

- Scope, environment, evidence inventory, collection limits, and assumptions.
- Executive summary ordered by consequence rather than style.
- Findings with stable IDs, severity, confidence, object, evidence, failure path, and minimal remediation.
- Confirmed controls and evidence gaps.
- Ordered remediation plan with lock/rewrite, deployment, rollback, and verification notes.
- Commands or catalog queries proposed or executed plus residual risks and referrals to narrower skills.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [schema-review-report-template.md](assets/schema-review-report-template.md)
- [catalog-review-queries.example.sql](assets/catalog-review-queries.example.sql)
- [render_review_queries.py](scripts/render_review_queries.py)
- [Routing and behavior evals](evals/evals.json)
