# PostgreSQL index proposal

## Decision

- Proposed index name:
- Table/partition scope:
- PostgreSQL version/provider:
- Decision: create / replace / retain / remove / defer
- Owner and review date:

## Workload contract

- Constraint or statement identifier:
- Sanitized SQL shape:
- Predicates and parameter classes:
- Joins:
- Ordering/limit:
- Selected columns:
- Calls/concurrency:
- Current latency/resource evidence:
- Table size/growth/write rate:

## Existing structures

| Index/constraint | Definition | Purpose | Size | Window/usage caveat | Dependency |
|---|---|---|---:|---|---|

## Candidate definition

```sql
-- Exact reviewed DDL goes here.
```

- Access method/operator class:
- Key-order rationale:
- Included columns:
- Predicate/expression:
- Uniqueness and null semantics:
- Collation/direction:
- Partition implications:

## Cost model

- Build duration/resource estimate:
- WAL/replication effect:
- Storage/backup effect:
- Write/HOT/vacuum effect:
- Cache/maintenance effect:
- Redundancy assessment:

## Experiment

- Data/parameter classes:
- Concurrency:
- Correctness checks:
- Before/after plans:
- Latency/resource success metric:
- Regression guard:

## Production rollout

- Preflight:
- Transaction restrictions:
- Lock/statement timeout:
- Monitoring and abort threshold:
- Invalid-index cleanup:
- Application ordering:
- Rollback/drop DDL:
- Post-deploy observation:
