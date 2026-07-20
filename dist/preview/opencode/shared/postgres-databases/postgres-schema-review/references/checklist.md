# PostgreSQL schema-review checklist

## Scope and evidence

- [ ] Environment, database, PostgreSQL version, provider, and collection time are recorded.
- [ ] Intended invariants and role model are available or missing context is labeled.
- [ ] Migration history, DDL, catalog state, and workload evidence are distinguished.
- [ ] Collection uses a read-only role and bounded statements.
- [ ] No sensitive table contents are collected without a documented need and approval.

## Roles, schemas, and privileges

- [ ] Object owners are separate from runtime roles.
- [ ] Elevated role attributes and memberships are justified.
- [ ] Schema `USAGE` and `CREATE` privileges match the trust boundary.
- [ ] Trusted `search_path` schemas are not writable by untrusted roles.
- [ ] Object grants and default privileges are both reviewed.
- [ ] Sequence, routine, and type privileges are included.
- [ ] Security-definer functions have a deliberate, safe `search_path`.
- [ ] Provider-specific administrative roles are understood.

## Tables and constraints

- [ ] Every table has a primary or intentionally documented alternate identity.
- [ ] Business and tenant-scoped uniqueness are enforced.
- [ ] Required fields, defaults, and generated values match domain semantics.
- [ ] Foreign keys, actions, validation state, and referenced uniqueness are correct.
- [ ] Referencing-side index requirements are assessed.
- [ ] Check/exclusion constraints encode valid assumptions.
- [ ] Cascades have bounded, intentional lifecycle consequences.
- [ ] Invalid or unvalidated constraints and indexes are surfaced.

## RLS and partitioning

- [ ] RLS enabled and forced state is reviewed per table.
- [ ] Policy roles, commands, permissive/restrictive mode, `USING`, and `WITH CHECK` are explicit.
- [ ] Owner, superuser, and `BYPASSRLS` behavior is tested.
- [ ] Pool/session context handling fails closed.
- [ ] Partition bounds, default partition, indexes, grants, constraints, and policies are consistent.
- [ ] Pruning and retention workflows are evidenced.

## Indexes and operations

- [ ] Each index has an identified purpose or is marked unknown.
- [ ] Key order, expressions, predicates, included columns, method, validity, and uniqueness are compared.
- [ ] Usage statistics include reset/failover/seasonality caveats.
- [ ] Table/index size, dead tuples, analyze/vacuum signals, and bloat hypotheses are not conflated.
- [ ] Extensions, collations, functions, triggers, sequences, and dependencies are inventoried.
- [ ] Backup/recovery and replication implications of findings are considered.

## Findings and remediation

- [ ] Findings include evidence, consequence, confidence, remediation, and verification.
- [ ] Security/correctness issues are separated from style preferences.
- [ ] Remediation identifies lock, rewrite, deploy-order, replication, and rollback risk.
- [ ] Existing invalid data is checked before adding or validating constraints.
- [ ] Unexecuted tests are not represented as passed.
