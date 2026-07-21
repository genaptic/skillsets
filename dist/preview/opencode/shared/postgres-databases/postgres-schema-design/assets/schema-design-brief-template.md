# PostgreSQL schema design brief

## Context

- PostgreSQL version/provider:
- Extensions and collations:
- Deployment and migration tooling:
- Object owner role:
- Runtime roles:
- Tenant model:
- Data classification:
- RPO/RTO and retention constraints:

## Domain model

For each entity, record its row meaning, lifecycle owner, business identity, generated key,
expected cardinality, write rate, and dominant reads.

| Entity | Row meaning | Business key | Generated key | Growth | Lifecycle owner |
|---|---|---|---|---:|---|

## Invariants

| Invariant | Scope | Enforcement | Concurrency notes | Error contract |
|---|---|---|---|---|

## Relationships

| From | To | Cardinality | Required | Delete/update behavior | Tenant scope |
|---|---|---|---|---|---|

## Type and nullability decisions

| Attribute | PostgreSQL type | Nullable | Default | Units/time zone/format | Rationale |
|---|---|---:|---|---|---|

## Security

- Schema and `search_path` policy:
- Ownership and grants:
- RLS identity source:
- RLS policies and bypass roles:
- Audit requirements:

## Workloads and index intent

| Operation/query | Frequency | Expected rows | Ordering | Consistency | Candidate access path |
|---|---:|---:|---|---|---|

## Partitioning decision

- Decision:
- Justification:
- Partition key and bounds:
- Retention/attach/drop workflow:
- Uniqueness implications:
- Default partition and late-data handling:

## Evolution and verification

- Initial creation/migration sequence:
- Seed/reference data:
- Rollback boundary:
- Constraint and role tests:
- Representative workload tests:
- Open assumptions and residual risks:
