# PostgreSQL backup-and-recovery checklist

## Requirements

- [ ] RPO and RTO are defined per system, data class, and failure scenario.
- [ ] Object, database, cluster, region/account, corruption, deletion, and compromise scenarios are covered.
- [ ] Retention, legal hold, erasure, residency, and encryption requirements are explicit.
- [ ] Recovery authority, technical owners, business validators, communications, and dependencies are mapped.
- [ ] Availability/failover and backup/restore responsibilities are distinct.

## Backup architecture

- [ ] Logical, physical, snapshot, replica, and WAL/PITR methods each have a stated purpose.
- [ ] PostgreSQL/tool versions and cross-version constraints are documented.
- [ ] Roles, memberships, tablespaces, extensions, collations, large objects, ownership, ACLs, and configuration are included as needed.
- [ ] Base-backup cadence and complete WAL-chain retention meet targets.
- [ ] Archive success semantics, continuity, timelines, and storage-pressure failure modes are monitored.
- [ ] Provider snapshot guarantees, restore quotas, egress, and key dependencies are verified.
- [ ] Backup source and failover/timeline behavior are defined.

## Security and retention

- [ ] Data is encrypted in transit and at rest.
- [ ] Keys and recovery identities are independent and themselves recoverable.
- [ ] Backup creation, retention/deletion, read, and restore privileges are separated.
- [ ] Immutable/deletion-protected and cross-account/region copies meet threat requirements.
- [ ] Audit logs cover backup and recovery actions.
- [ ] Secrets are absent from artifacts, scripts, logs, and reports.
- [ ] Retention deletion preserves every required dependency chain.
- [ ] Long-term archives retain compatible tools/keys and secure-deletion plans.

## Monitoring and verification

- [ ] Scheduled success, freshness, duration, size, throughput, and anomaly alerts exist.
- [ ] WAL archive delay/failure and local disk risk are monitored.
- [ ] Manifests/checksums and logical archive readability are verified.
- [ ] Effective recovery-point age is measured.
- [ ] Retention jobs, repository capacity, credentials, and keys are monitored.
- [ ] Restore-test age and achieved RPO/RTO are tracked.
- [ ] Verification limitations are stated; a scheduler exit code is not treated as proof.

## Restore runbook

- [ ] Incident authorization, containment, target selection, and legal/security steps are clear.
- [ ] Target infrastructure, version, extensions, locale/collation, tablespaces, isolation, and capacity are specified.
- [ ] Artifact chain and integrity checks are explicit.
- [ ] PITR target and timeline/promotion behavior are understood.
- [ ] Roles, grants, ownership, jobs, replication, and external dependencies are restored in order.
- [ ] Technical and domain/application validation have named owners.
- [ ] Fencing, cutover, rollback, and post-recovery backup baseline are included.
- [ ] Untrusted dumps are restored only in isolated, least-privilege environments.

## Exercises and evidence

- [ ] Restore drills vary backup age, target point, size, scenario, and operator.
- [ ] Object-level, full-cluster, PITR, and region/account scenarios match requirements.
- [ ] Authorization, provisioning, restore, validation, and cutover time are measured separately.
- [ ] Achieved RPO/RTO and data-loss window are calculated.
- [ ] Command/evidence logs are immutable and secrets are redacted.
- [ ] Deviations produce owned, dated remediation and a readiness decision.
- [ ] PostgreSQL starting is not the sole success criterion.
