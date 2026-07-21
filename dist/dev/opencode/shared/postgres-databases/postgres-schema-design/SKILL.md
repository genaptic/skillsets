---
name: postgres-schema-design
description: >
  Design a new PostgreSQL schema from domain invariants and workloads, covering keys, types, nullability, constraints, relationships, tenancy, ownership, RLS, partitioning, index intent, and evolution. Use when creating or substantially reshaping a data model. Do not use for auditing an already deployed schema, diagnosing one slow query, or executing a production migration.
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

Portable across Claude Code, Codex, and OpenCode. Guidance targets PostgreSQL 18; check it
against the deployed major version, extensions, collations, and managed-service limits. The
optional DDL scanner requires Python 3.11, reads local text only, and is heuristic.

## Use this skill when

- A new PostgreSQL-backed product, service, or bounded context needs a relational model.
- Domain invariants, tenant boundaries, lifecycle rules, or retention requirements must become database constraints.
- Keys, types, nullability, relationships, RLS, partitioning, and index intent need one coherent proposal.
- An existing model is being substantially reshaped and the target design must be stated before migration planning.

## Do not use this skill when

- The task is to rank defects in an already deployed schema or DDL snapshot; use `postgres-schema-review`.
- The task is to interpret a plan for one or more slow statements; use `postgres-query-performance-review`.
- The desired index follows from measured query plans; use `postgres-index-design`.
- The target schema is already decided and the problem is safe rollout; use `postgres-migration-safety`.

## Inputs

Inspect or obtain:

- PostgreSQL major version, provider, extensions, collations, and operational constraints.
- Domain entities, business identities, invariants, lifecycle ownership, and concurrency-sensitive rules.
- Tenant model, security roles, data classification, audit, retention, erasure, and residency requirements.
- Expected cardinality, growth, read/write rates, representative statements, ordering, and transaction boundaries.
- Existing naming, migration, backup, observability, and deployment conventions.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Begin with a design and verification plan; do not connect to a database or apply DDL without explicit approval.
- Treat production data, catalog output, query samples, and tenant identifiers as potentially sensitive.
- Do not claim a constraint, RLS policy, partitioning choice, or index is correct until tested on the target version and roles.
- Call out operations that can lock, rewrite, scan, or expose data and defer rollout mechanics to migration safety.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. Establish context. Record the target PostgreSQL version/provider, ownership model, tenant boundary, data classification, lifecycle, scale, and representative workloads.

2. Translate the domain into invariants. Define the row meaning, business identity, generated identity, cardinality, optionality, and lifecycle owner for each entity and relationship.

3. Choose keys and types. Separate primary and business keys, include tenant scope where required, define time/decimal/identifier semantics, and justify JSON, array, enum, domain, or lookup choices.

4. Encode enforceable rules. Add named `NOT NULL`, `CHECK`, uniqueness, foreign-key, exclusion, and deferrability rules while identifying cross-row rules that need another mechanism.

5. Design namespaces and authorization. Separate owner and runtime roles, control schemas and `search_path`, assign least-privilege grants, and define RLS identity, `USING`, `WITH CHECK`, and bypass behavior when needed.

6. Evaluate partitioning. Adopt it only for a concrete pruning, retention, load, or maintenance workflow and specify bounds, default handling, uniqueness, indexes, and late data.

7. Connect index intent to workloads. Name the query or invariant behind each candidate and defer plan-specific confirmation to the index and performance skills.

8. Plan evolution and operations. State migration ordering, extension/seed dependencies, rollback boundaries, audit and retention behavior, and backup/restore implications.

9. Verify on the target version. Test valid and invalid data, constraint timing, cascades, roles, RLS, concurrency-sensitive cases, representative plans, and generated artifacts in an isolated environment.

## Verification

Before claiming completion:

- Every table and relationship has an explicit meaning, key strategy, lifecycle, and tenant scope.
- Types, nullability, defaults, and constraints preserve stated domain semantics.
- Ownership, schema privileges, `search_path`, grants, and RLS behavior are defined and tested under real roles.
- Partitioning and index candidates have named operational or workload justifications.
- DDL parseability and behavior are exercised on the target PostgreSQL version without claiming unrun checks.
- Migration, rollback, backup, and residual performance/security risks are documented.

## Output contract

Return:

- Context, constraints, deployed-version assumptions, and unresolved questions.
- Entity/relationship model, keys, types, nullability, and named invariants.
- Proposed DDL organized by schema plus ownership, grants, and optional RLS policy.
- Workload-to-index intent and an explicit partitioning decision.
- Evolution, migration, rollback, and operational notes.
- Verification cases, commands proposed or executed, evidence, and residual risks.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [schema-design-brief-template.md](assets/schema-design-brief-template.md)
- [schema.example.sql](assets/schema.example.sql)
- [audit_schema_sql.py](scripts/audit_schema_sql.py)
- [Routing and behavior evals](evals/evals.json)
