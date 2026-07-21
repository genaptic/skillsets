# PostgreSQL schema-review guide

## Review the deployed contract, not only formatted DDL

An effective review reconciles four sources of truth:

1. Intended invariants and role boundaries.
2. Version-controlled migration and DDL history.
3. Deployed catalog state.
4. Observed data and workload behavior.

A pretty schema dump can hide ownership, default privileges, policy roles, invalid indexes,
unvalidated constraints, extension dependencies, sequence privileges, and configuration that
changes name resolution. Conversely, catalog output without product intent cannot tell
whether a nullable column or cascade is correct.

State the review scope, environment, PostgreSQL major version, provider restrictions, sample
time, and whether evidence came from production, staging, a dump, or supplied files.

## Establish a read-only collection boundary

Prefer catalog and information-schema queries under a role that cannot modify application
objects. Set an explicit transaction mode and conservative statement timeout where
appropriate. Do not collect table contents unless a finding requires a bounded, approved
data-quality check.

Useful evidence categories include:

- Databases, extensions, collations, schemas, and object owners.
- Roles, memberships, attributes, grants, default privileges, and schema ACLs.
- Tables, views, materialized views, sequences, functions, types, and dependencies.
- Columns, defaults, generated/identity behavior, nullability, and storage.
- Primary, unique, foreign-key, check, exclusion, and unvalidated constraints.
- Index definitions, validity/readiness, predicates, expressions, size, and usage counters.
- RLS enable/force state and policies by command and role.
- Partitions, bounds, default partitions, inheritance, and detached objects.
- Trigger and rule behavior.
- Statistics freshness, table/index size, tuples, dead tuples, and maintenance signals.

Usage counters are cumulative since a statistics reset and can be incomplete after failover,
restart, role restrictions, or workload seasonality. Never recommend dropping an index from
a single zero-scan snapshot.

## Review ownership, schemas, and privileges first

Security defects can dominate all other findings.

Check:

- Application roles do not own the objects they use.
- Login roles are separated from group roles where practical.
- Superuser, `CREATEDB`, `CREATEROLE`, replication, and `BYPASSRLS` are tightly controlled.
- Untrusted roles cannot create objects in schemas on a trusted `search_path`.
- `public` schema privileges match the threat model.
- Functions have intentional security mode and safe `search_path` when security-definer is
  required.
- Default privileges cover future objects and were set by the correct creating owner.
- Sequences and routines have the privileges the application needs—no broader.
- Managed-service administrative roles are treated according to actual provider semantics.

Object privileges do not automatically imply schema usage, and grants on current objects do
not configure future objects. Review both.

## Review data-model invariants

For each table, compare intended and deployed behavior:

- Primary and business keys.
- Tenant-scoped uniqueness.
- Required values and default semantics.
- Foreign-key columns, actions, match type, validation state, and referenced uniqueness.
- Referencing-side indexes based on parent lifecycle and join workloads.
- Check expressions and whether they rely only on valid row-local assumptions.
- Exclusion constraints for ranges or mutually exclusive state.
- Generated columns and identity/sequence ownership.
- Enum/domain evolution risk.
- JSON or array fields that conceal stable relational structure.
- Cascades that may delete more than their lifecycle owner intends.

A constraint marked not valid can still enforce new writes while leaving historical data
unchecked, depending on type and creation sequence. Report validation state, not just the
definition.

## Review row-level security as role-dependent behavior

Inspect table-level RLS enabled/forced flags and every policy's command, roles, permissive or
restrictive mode, `USING`, and `WITH CHECK`.

Then reason using actual session identities:

- Owners normally bypass RLS unless forced.
- Superusers and `BYPASSRLS` roles bypass it.
- Policy combinations can broaden or narrow access.
- Missing policy behavior can fail closed when RLS applies.
- A policy expression that reads session settings needs a validated, transaction-safe source.
- Views/functions and connection-pool session reuse can change the effective boundary.

Test reads and all write operations under runtime, migration, support, and reporting roles.
Do not infer security from policy text alone.

## Review partitioning as a system

Confirm:

- Every expected child is attached with correct bounds.
- Bounds do not overlap and no gap is accidentally absorbed by a default partition.
- The default partition is monitored and emptied intentionally.
- Constraints, indexes, triggers, grants, and RLS are correct across partitions.
- Unique requirements are compatible with the partition key.
- Retention attach/detach/drop procedures validate bounds safely.
- Query predicates allow pruning.
- Partition count and planning overhead remain reasonable.

Detached or independently modified children can drift from the parent contract.

## Review index and constraint support conservatively

Classify each index by purpose:

- Constraint-enforcing.
- Foreign-key/relationship support.
- Query access path.
- Sort/grouping support.
- Specialized search.
- Unknown/redundant candidate.

Inspect definitions structurally, not only names. Compare key columns, order, operator classes,
collations, predicates, expressions, included columns, uniqueness, validity, and access
method.

Use plan and workload evidence before changing query indexes. Use `postgres-index-design` for
a focused decision and `postgres-query-performance-review` for statement-level diagnosis.

## Rank findings by consequence and confidence

A useful finding contains:

- Stable identifier and severity.
- Evidence and source.
- Affected object and environment.
- Consequence and exploit/failure path.
- Confidence and assumptions.
- Minimal remediation.
- Lock/rewrite/deployment considerations.
- Verification and rollback.

Separate correctness/security defects from maintainability opportunities and style
preferences. Avoid presenting naming conventions as production incidents.

Suggested severity lens:

- **Critical:** credible unauthorized access, unrecoverable data risk, or active integrity loss.
- **High:** likely privilege bypass, cross-tenant exposure, missing core invariant, or unsafe
  destructive behavior.
- **Medium:** bounded correctness, performance, or operational risk requiring planned work.
- **Low:** resilience or clarity improvement with limited immediate consequence.
- **Informational:** inventory or confirmed good practice.

## Verify remediation

Every proposed correction must be checked for:

- Existing violating rows.
- Lock level and lock duration.
- Table rewrite or index build cost.
- Replication and standby effects.
- Application compatibility and deploy order.
- Transaction restrictions.
- Rollback or roll-forward strategy.
- Observability and success criteria.

Pass rollout planning to `postgres-migration-safety` when changes affect deployed objects.

The included helper only emits a versioned, read-only catalog-query bundle. It never connects
to PostgreSQL. Review queries for permissions, provider differences, and collection cost.
