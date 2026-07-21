# PostgreSQL schema-design checklist

## Context and boundaries

- [ ] PostgreSQL major version, extensions, provider, and deployment model are recorded.
- [ ] Domain invariants, lifecycle, cardinality, growth, and representative workloads are listed.
- [ ] Tenant, security, audit, retention, and residency requirements are explicit.
- [ ] Repository names, database names, schemas, owners, and runtime roles are distinguished.
- [ ] Unknowns and assumptions are labeled.

## Tables, keys, and types

- [ ] Every table has a clear row meaning and lifecycle owner.
- [ ] Primary and business keys are both considered.
- [ ] Tenant scope is represented in relevant uniqueness and relationship rules.
- [ ] Generated-key strategy is intentional.
- [ ] Dates, instants, decimals, identifiers, and text use semantically appropriate types.
- [ ] `jsonb`, arrays, enums, domains, and lookup tables are chosen for stated reasons.
- [ ] Nullable columns have documented semantics.
- [ ] Defaults do not hide missing required input.

## Constraints and relationships

- [ ] Required values use `NOT NULL`.
- [ ] Business invariants use named constraints where PostgreSQL can enforce them.
- [ ] Unique-null semantics are explicit.
- [ ] Foreign-key actions match lifecycle ownership.
- [ ] Referencing-side index needs are assessed.
- [ ] Many-to-many edges prevent duplicates.
- [ ] Deferrable or exclusion constraints are used only with a concrete need.
- [ ] Cross-row or cross-table rules are not incorrectly placed in `CHECK` constraints.

## Security and tenancy

- [ ] Object ownership is separate from the runtime role.
- [ ] Schema privileges and `search_path` are designed safely.
- [ ] Grants follow least privilege.
- [ ] RLS role bypass behavior is understood.
- [ ] `USING` and `WITH CHECK` policies are tested separately.
- [ ] Missing tenant/session context fails closed where required.
- [ ] Cross-tenant relationships are constrained and tested.

## Scale and operations

- [ ] Partitioning has a measurable pruning, lifecycle, or maintenance justification.
- [ ] Partition key, bounds, uniqueness, default partition, and late data are planned.
- [ ] Index candidates name the query or invariant they support.
- [ ] Write, storage, vacuum, and maintenance costs are considered.
- [ ] Extension and collation dependencies are explicit.
- [ ] Backup, restore, migration, and rollback implications are recorded.

## Verification

- [ ] DDL is tested against the target PostgreSQL major version.
- [ ] Valid and invalid data cases are automated.
- [ ] Role and RLS behavior is exercised under the actual roles.
- [ ] Representative plans and write paths are measured with realistic distributions.
- [ ] Executed checks are distinguished from proposed checks.
