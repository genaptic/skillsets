# PostgreSQL backup-and-recovery guide

## Begin with recoverability requirements

“Take backups” is not a recovery design. Define business requirements first:

- **RPO:** maximum acceptable data loss, by system and data class.
- **RTO:** maximum acceptable restoration time to a usable service.
- Failure scenarios: accidental row deletion, bad migration, database loss, host/zone/region
  loss, credential compromise, ransomware, corruption, provider outage, and operator error.
- Recovery scope: one object, one database, one cluster, or an entire application estate.
- Retention, legal hold, erasure, residency, and encryption requirements.
- Dependency order: identity, secrets/KMS, extensions, object storage, DNS, applications,
  queues, search, caches, and downstream consumers.
- Recovery authority, communications, and business validation ownership.

Assign measurable targets to scenarios. A local replica may improve availability but does not
replace an independent backup for corruption, deletion, or compromise.

## Choose logical and physical methods by purpose

### Logical backups

`pg_dump` exports one database as logical SQL or archive content; `pg_dumpall` can capture
cluster-wide objects such as roles and tablespaces. Logical backups are useful for selective
restore, migration, portability, and schema/data inspection.

Important properties:

- The dump represents a consistent snapshot for its scope but can run for a long time.
- Parallel dump/restore depends on archive format and command options.
- Roles, memberships, tablespaces, extensions, large objects, ownership, ACLs, and database
  creation need deliberate handling.
- A logical dump is not a physical cluster/PITR backup.
- Restoring into a different major version requires extension, collation, feature, and
  compatibility testing.
- Restore order, disabled triggers, ownership, and privileged statements must be reviewed.
- Dumps may contain highly sensitive data and SQL capable of changing the target.

Use version-compatible client tools according to PostgreSQL documentation and test the exact
source/target combination.

### Physical base backups

A physical backup captures the cluster files needed for physical recovery. `pg_basebackup`
can take a base backup from a running cluster under replication permissions and can produce
a backup manifest for verification.

Physical recovery is tied more closely to PostgreSQL version, system architecture, tablespace
layout, and configuration. It restores the cluster, not one arbitrary table. Include all
tablespaces and required configuration/keys outside the data directory according to the
deployment model.

Do not treat copying a live data directory with ordinary file tools as a valid backup unless
the documented physical-backup protocol and WAL requirements are satisfied.

### Managed-service snapshots

Provider snapshots can be valuable, but verify:

- Consistency semantics and database coordination.
- Granularity and PITR behavior.
- Retention and deletion protection.
- Cross-account/region copy and restore rights.
- Encryption-key dependency.
- Export/egress options.
- Restore duration and quotas.
- Independence from the compromised production account.
- Evidence/API logs and provider-specific limitations.

Record provider guarantees rather than assuming snapshot behavior.

## Design continuous archiving and PITR as a chain

Point-in-time recovery combines a base backup with a continuous, complete sequence of WAL
needed from the backup start through the recovery target.

Design:

- WAL archiving command/service and positive success semantics.
- Archive destination independence, encryption, access control, immutability, and monitoring.
- Segment continuity and detection of archival delay/failure.
- Base-backup cadence and how it affects restore time and retained WAL.
- Timeline history across promotions/recoveries.
- Retention that never removes WAL still needed by retained base backups or recovery policy.
- Recovery targets: time, transaction ID, named restore point, LSN, or immediate consistency
  according to target-version capabilities.
- Promotion and post-recovery divergence.
- Replication slots and WAL retention risk.
- Time synchronization and time-zone interpretation.

Archiving a segment only after it is complete can influence practical RPO. Additional
mechanisms and operational controls may be needed for tighter targets. Measure effective RPO
rather than inferring it from configuration.

A successful archive command should mean the segment is durably and correctly stored. A
false-positive success can silently break the chain; repeated failure can fill local storage.

## Separate availability from backup

Streaming replicas, failover clusters, and multi-zone services improve availability and may
reduce RTO for some failures. They often replicate accidental deletes, bad DDL, and logical
corruption quickly.

Document:

- Which scenarios use failover versus restore.
- Synchronous/asynchronous data-loss behavior.
- Failure detection and promotion authority.
- Fencing/split-brain prevention.
- Replica lag and delayed-replica purpose.
- Backup source and whether offloading affects validity.
- Post-failover backup and timeline handling.
- Rejoin/rebuild procedure.

A delayed replica can provide a short correction window but remains operationally coupled
and is not a complete backup strategy.

## Protect the backup plane

Backups are concentrated sensitive data and a privileged recovery path.

Use:

- Encryption in transit and at rest.
- Keys controlled and recoverable independently of the production database.
- Separate identities for backup creation, retention administration, and restore.
- Least privilege and short-lived credentials where available.
- Immutable/write-once or deletion-protected copies.
- Cross-account/project and, when required, cross-region copies.
- Network and endpoint restrictions.
- Audit logs for backup, read, restore, retention, and deletion actions.
- Secrets excluded from scripts, logs, command history, manifests, and tickets.
- Documented emergency access with tested custody.

Test loss or compromise of the primary identity and encryption key. An encrypted backup
whose key cannot be recovered is not recoverable.

## Define retention as a dependency-aware policy

For each backup class, define cadence, retention, copy locations, legal holds, and deletion
authority. Retention must consider:

- Full/base backup dependencies on WAL.
- Incremental/differential dependencies where the chosen tool/provider supports them.
- Quarterly/yearly archives.
- Recovery test environments and secure deletion.
- Regulatory retention and data-subject erasure.
- Storage growth, compression, deduplication, and egress.
- Old PostgreSQL/tool versions required to read long-term archives.
- Cryptographic key retention.

Do not delete a base backup or WAL segment based only on age without evaluating the retained
recovery chain.

## Monitor backup health and freshness

Monitor end-to-end properties:

- Last successful scheduled backup by scope.
- Duration, bytes, compression, throughput, and change from baseline.
- WAL archive delay, failures, oldest unarchived segment, and local disk consumption.
- Backup manifest/checksum verification.
- Repository/object-store integrity and capacity.
- Retention/deletion jobs.
- Encryption and credential expiry.
- Restore-test age and result.
- Effective recovery-point age.
- Replication-slot WAL retention.
- Provider job and API health.

A green scheduler exit code is only one signal. Confirm expected artifacts exist, are
complete, have plausible size, and are independently readable.

## Verify artifacts without overstating assurance

`pg_verifybackup` can check a base backup against its manifest and verify file/WAL-related
properties within its documented scope. It cannot prove the backup came from the intended
system, that every external dependency exists, that application data is semantically valid,
or that the organization can meet RTO.

For logical archives, use format listing/inspection and restore into an isolated environment.
For any method, retain immutable evidence:

- Backup identifier and source.
- Tool and PostgreSQL versions.
- Start/end time.
- Manifest/checksum result.
- Location and encryption key reference—not secret material.
- Retention class.
- Verification result and limitations.
- Restore-drill linkage.

Verification should not modify production.

## Restore into an isolated, controlled target

A recovery runbook should define:

1. Incident scope, authority, legal/security containment, and recovery target.
2. Source backup chain and integrity checks.
3. Target infrastructure, version, extensions, collation/locale, tablespaces, storage, and
   network isolation.
4. Secrets/KMS restoration without exposing credentials.
5. Restore commands and resource estimates.
6. WAL/PITR target, timeline, recovery signal/configuration, and promotion decision.
7. Roles, ownership, ACLs, extensions, jobs, replication, and external dependencies.
8. Database-level technical checks.
9. Application/domain validation by accountable owners.
10. Data-loss window calculation.
11. Cutover, fencing, DNS/routing, and client reconfiguration.
12. Post-recovery backup baseline and monitoring.
13. Evidence, lessons, and remediation.

Never restore an untrusted dump into a privileged or networked environment without review.
SQL-format dumps can contain arbitrary statements. Use isolated infrastructure and least
privilege.

## Test representative scenarios

A useful program includes:

- Frequent automated artifact verification.
- Regular isolated restore of the primary backup method.
- Periodic PITR to a randomly selected or policy-selected target.
- Selective logical restore when object-level recovery is required.
- Region/account loss exercise where relevant.
- Lost-key or inaccessible-primary-account exercise.
- Corruption/bad-migration scenario.
- Full application validation and cutover rehearsal periodically.

Rotate target times, backup ages, data sizes, operators, and failure injections. A restore
test that always uses yesterday's smallest database does not validate the hardest RTO.

Measure:

- Time to declare and authorize.
- Provisioning and credential time.
- Artifact selection and transfer.
- Restore/replay time.
- Technical and business validation.
- Cutover and stabilization.
- Achieved RPO/RTO.
- Manual steps, errors, and undocumented dependencies.

## Make evidence durable

Every drill should produce a report with:

- Scenario, scope, objectives, and success criteria.
- People and roles.
- Source backup IDs and recovery target.
- Timeline and command log with secrets redacted.
- Integrity and technical checks.
- Business validation.
- Achieved RPO/RTO and data-loss calculation.
- Deviations, incidents, and residual risk.
- Remediation owner and due date.
- Decision on production readiness.

Do not call a restore successful merely because PostgreSQL starts. The recovered application
must meet defined invariants and user-visible acceptance criteria.

The included helper turns a reviewed JSON profile into a drill worksheet. It does not inspect
backups, calculate real recovery capability, execute commands, or validate a provider.
