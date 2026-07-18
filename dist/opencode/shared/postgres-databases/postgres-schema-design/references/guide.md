# PostgreSQL schema-design guide

## Start from invariants and workloads

A schema is an executable statement of what the system permits. Begin with domain
invariants, ownership, lifecycle, tenant boundaries, write paths, and dominant reads. Do not
start by translating an object model table-for-class or by adding indexes to every apparent
filter column.

Record:

- The business identity and lifecycle of each entity.
- Relationships and whether they are required, optional, exclusive, or historical.
- Cardinality and expected growth.
- Transaction boundaries and concurrency-sensitive invariants.
- Retention, erasure, audit, and residency requirements.
- Tenant isolation and privilege boundaries.
- Representative queries and write rates.
- PostgreSQL major version, extensions, and managed-service restrictions.

Separate requirements that PostgreSQL can enforce directly from rules that require
serialized application workflows or procedural enforcement.

## Choose keys deliberately

A primary key identifies a row inside the database. A business key identifies the domain
object. They may be the same, but using a surrogate key does not remove the need for a
unique business constraint.

Prefer keys that are:

- Stable for the row lifetime.
- Available at insert time.
- Compact enough for referencing and indexing.
- Unambiguous across the intended scope, including tenant scope.

Identity columns are generally clearer than manually managed sequences for generated integer
keys. UUIDs can be appropriate for distributed creation or opaque public identifiers, but
version, generation locality, index behavior, and exposure policy must be explicit.

For tenant-scoped data, decide whether foreign keys and uniqueness include `tenant_id`.
A single-column surrogate key can remain the primary key while tenant-scoped unique
constraints and relationship checks enforce isolation. Do not assume application filters
alone prevent cross-tenant references.

## Use types that preserve meaning

Select the narrowest type that represents the domain without lossy conversion:

- Use `date` for civil dates and `timestamptz` for instants that cross time zones.
- Store money according to required arithmetic and scale; avoid binary floating point for
  exact decimal amounts.
- Use `text` with explicit constraints for variable strings unless a length limit is itself
  a domain rule.
- Use `jsonb` for genuinely semi-structured attributes, not as a substitute for stable
  relational columns and constraints.
- Use arrays when values are naturally one attribute and relationship operations remain
  simple; use child tables when elements need identity, constraints, references, or frequent
  querying.
- Prefer domain or enum types only when their lifecycle and deployment cost are acceptable.
  A lookup table can be easier to evolve.

Null means unknown or not applicable, not an empty string, zero, or a magic timestamp.
Make nullable columns intentional and document their semantics.

## Encode invariants with constraints

Use `NOT NULL`, `CHECK`, `UNIQUE`, primary keys, exclusion constraints, and foreign keys for
rules the database can evaluate reliably. Constraint names should be stable and diagnostic.

Important nuances:

- A regular unique constraint permits multiple nulls by default. PostgreSQL can use
  `NULLS NOT DISTINCT` when nulls should compare as equal.
- A `CHECK` constraint is evaluated per row and should not depend on other table contents.
- A foreign key does not automatically create an index on the referencing columns. Add one
  when deletes/updates of the referenced row or joins need it.
- Cascade actions encode lifecycle ownership. Use them only when deleting the parent should
  truly delete the dependent rows inside the same transaction.
- Deferrable constraints are useful for specific transaction-ordering problems but make
  error timing and reasoning more complex.

Name constraints for operations and error translation, not merely to satisfy style.

## Model relationships and history

Use join tables for many-to-many relationships and give them constraints that prevent
duplicate edges. Add attributes such as role or validity interval to the relationship rather
than duplicating them on each entity.

For mutable facts that require history, choose deliberately among:

- Current-state row plus append-only audit/event records.
- Effective-dated rows with non-overlap enforcement.
- Separate revisions with an active pointer.
- Event-sourced models where reconstruction is a product requirement.

Do not overload `updated_at` as a complete audit trail. Define who changed what, when, and
under which identity where that matters.

## Establish namespaces and privilege boundaries

Avoid placing application objects in a writable schema that is also trusted through
`search_path`. Qualify administrative SQL and design ownership so application roles do not
own the objects they use.

A typical separation is:

- Migration/owner role: owns schema objects and is not used by the application.
- Application runtime role: has only required DML and sequence privileges.
- Read-only/reporting roles: receive explicit access appropriate to their purpose.
- Separate schemas when they form real lifecycle, privilege, or naming boundaries.

Do not use schemas as a substitute for row-level tenant isolation without analyzing role
behavior.

## Design row-level security as defense in depth

When RLS is required, define:

- Which roles are subject to policies.
- How tenant or actor identity enters the session.
- Separate `USING` and `WITH CHECK` behavior for reads and writes.
- Whether owners, superusers, or roles with `BYPASSRLS` can bypass controls.
- A fail-closed policy for missing or malformed session context.
- Tests for select, insert, update, delete, cross-tenant references, and privileged paths.

RLS does not replace constraints or least-privilege grants. Policy expressions also affect
query planning and must be tested with representative workloads.

## Partition only for a concrete operational reason

Partitioning can help with large-table lifecycle operations, pruning, and maintenance. It
also adds routing, key, constraint, index, and operational complexity.

Before partitioning, document:

- The pruning predicate in representative queries.
- Data volume per partition and expected partition count.
- Retention/drop or load/attach workflow.
- Uniqueness requirements and how the partition key participates.
- Default partition behavior and bounds validation.
- Index and maintenance operations per partition.
- Late-arriving data and key updates.

Do not partition merely because a table may become large. A well-designed unpartitioned
table with appropriate indexes is often simpler.

## Design index intent, not a final index set

Schema design should identify access paths and enforcement needs, but final indexes require
representative data and plans. For each candidate, record:

- Query or constraint it supports.
- Key order and operators.
- Selectivity and expected rows.
- Read benefit versus write, storage, and maintenance cost.
- Whether it must be unique, partial, expression-based, covering, or specialized.

Defer plan-specific tuning to `postgres-index-design` and
`postgres-query-performance-review`.

## Plan evolution

Assume every schema will change. Stable names, explicit defaults, compatible deployment
orders, and clear ownership make migration safer. For large existing tables, a logically
simple DDL statement may still require a rewrite or a strong lock.

A new schema proposal should include migration and rollback considerations even before data
exists: seed/reference data, extension requirements, ownership, grants, and how future
columns can be added without coordinating every client at once.

## Verification

Validate at three levels:

1. **Static DDL review:** parseability for the target version, names, types, constraints,
   ownership, grants, and unsafe assumptions.
2. **Behavioral tests:** valid and invalid inserts/updates, concurrency-sensitive cases,
   cascades, tenant isolation, and role behavior.
3. **Workload tests:** representative query plans, data distribution, write amplification,
   and maintenance operations.

The included helper is a heuristic text scanner. It does not parse PostgreSQL SQL and cannot
prove correctness, lock behavior, privilege safety, or performance.
