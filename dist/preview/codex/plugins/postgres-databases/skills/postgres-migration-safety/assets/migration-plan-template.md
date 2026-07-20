# PostgreSQL migration plan

## Change record

- Change ID:
- Owner/reviewer/operator:
- Environment:
- PostgreSQL version/provider:
- Migration tool and transaction behavior:
- Requested window:
- Application versions:
- Risk classification:

## Target and current state

- Current schema/data behavior:
- Target behavior:
- Affected objects and dependencies:
- Table/index sizes and write/read rates:
- Partitions:
- Replication/CDC/downstream:
- Invariants and compatibility window:

## Statement hazard table

| Step | Statement/operation | Lock | Scan/rewrite | WAL/disk | Transaction rule | Failure state |
|---:|---|---|---|---|---|---|

## Phased rollout

### Phase 0 — Preflight

- Existing-data checks:
- Long transaction/blocker checks:
- Capacity and lag checks:
- Backup/recovery confirmation:
- Go/no-go criteria:

### Phase 1 — Expand

- Commands:
- Timeouts:
- Application compatibility:
- Monitoring:
- Abort/cleanup:

### Phase 2 — Backfill/validate

- Cursor and eligibility:
- Batch/commit/throttle:
- Concurrent-write handling:
- Progress and convergence:
- Validation:

### Phase 3 — Cut over

- Feature/config switch:
- Success metrics:
- Rollback switch:
- Observation window:

### Phase 4 — Contract

- Proof of disuse:
- Retention/export:
- Destructive commands:
- Final verification:

## Observability and abort criteria

| Signal | Baseline | Warning | Abort | Action/owner |
|---|---:|---:|---:|---|

## Failure and recovery

- Transaction rollback:
- Invalid or partial object cleanup:
- Application rollback:
- Roll-forward:
- Data reconciliation:
- Restore/PITR trigger:
- Communication/escalation:

## Evidence and sign-off
