---
name: postgres-backup-recovery
description: >
  Design and assess PostgreSQL backup, WAL archiving, point-in-time recovery, retention, encryption, immutability, monitoring, restore runbooks, and recovery exercises against scenario-specific RPO and RTO. Use when recoverability or backup assurance is the goal. Do not use for routine high-availability tuning, query diagnosis, schema modeling, or migration sequencing.
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

Portable across Claude Code, Codex, and OpenCode. Guidance targets PostgreSQL 18; adapt it to
deployed versions, tools, providers, tablespaces, extensions, and key systems. The optional
Python 3.11 helper renders a local worksheet only and never accesses backups or credentials.

## Use this skill when

- A system needs scenario-specific PostgreSQL RPO, RTO, backup, PITR, retention, and restore requirements.
- Logical dumps, physical backups, snapshots, replicas, WAL archives, encryption, immutability, or copy locations need an architecture review.
- Backup freshness, integrity, dependency chains, credentials, keys, or restore evidence may be inadequate.
- Teams need an isolated recovery drill, achieved-RPO/RTO measurement, business validation, and remediation record.

## Do not use this skill when

- The task is only replica failover, routing, or availability tuning without backup/recovery scope.
- The task is a query, index, schema, or privilege review; use the corresponding PostgreSQL skill.
- The task is sequencing an approved production schema/data change; use `postgres-migration-safety`.
- The request is to execute a restore or access sensitive backup material without explicit authorization and operational controls.

## Inputs

Inspect or obtain:

- Systems/data classes, failure scenarios, recovery scope, RPO/RTO, retention, legal, residency, erasure, and security requirements.
- PostgreSQL/tool/provider versions, topology, databases, tablespaces, extensions, collations, roles, large objects, and external dependencies.
- Logical/physical/snapshot/replica/WAL methods, schedules, locations, manifests, monitoring, retention, and effective recovery-point evidence.
- Encryption and key custody, backup/read/retention/restore identities, immutability, cross-account/region copies, audit logs, and incident access.
- Restore runbooks, target capacity/isolation, drill history, stage timings, technical checks, business validation, deviations, and remediation.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Do not access, copy, decrypt, delete, or restore backup data without explicit authorization, least privilege, isolation, and audited handling.
- Treat dumps, manifests, commands, logs, role definitions, paths, keys, and recovered data as sensitive; never expose credentials or literal customer data.
- Do not equate replication, job success, checksum verification, or PostgreSQL startup with complete recoverability.
- Restore untrusted artifacts only in isolated environments and review SQL/ownership/privileged effects before execution.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. Define scenarios and targets. Map deletion, corruption, database/cluster/region loss, compromise, and operator error to scope, RPO, RTO, authority, dependencies, and validation owners.

2. Inventory data and platform dependencies. Record versions, databases, roles, tablespaces, extensions, collations, configuration, keys, provider services, and application/downstream order.

3. Choose backup methods by purpose. Assign logical, physical, snapshot, replica, and WAL/PITR methods to scenarios and state consistency, granularity, portability, and restore limitations.

4. Design the recovery chain. Define base cadence, archive success/continuity, timelines, retention dependencies, recovery targets, replication/failover interaction, and effective RPO monitoring.

5. Protect the backup plane. Separate identities, encrypt, control and recover keys independently, use immutable and cross-boundary copies as required, restrict networks, and audit reads/restores/deletions.

6. Define retention and monitoring. Preserve dependent chains, legal/erasure obligations, compatible tools/keys, freshness, artifact integrity, WAL delay, capacity, credentials, and restore-test age.

7. Write restore runbooks. Cover incident authority, source selection, isolated target, integrity checks, restore/replay/promotion, roles/extensions/tablespaces, technical/business validation, fencing, cutover, and post-recovery baseline.

8. Design representative drills. Vary scenario, backup age, recovery point, size, operator, account/region, and failure injection; measure every stage and calculate achieved RPO/RTO.

9. Report readiness. Preserve redacted evidence, limitations, deviations, residual risk, owned remediation, due dates, and an explicit production-readiness decision.

## Verification

Before claiming completion:

- RPO/RTO and recovery scope are defined for each material failure scenario.
- Backup methods, WAL chain, versions, dependencies, retention, encryption, identities, immutability, and monitoring form a complete architecture.
- Artifact verification is paired with isolated restore and application/domain validation.
- Restore runbooks cover source selection, target capacity/isolation, PITR/timeline, roles/extensions/tablespaces, cutover, fencing, and post-recovery backup.
- Drills measure achieved data-loss window and stage-by-stage RTO with durable redacted evidence.
- No availability mechanism or unexecuted verification is represented as proven backup recoverability.

## Output contract

Return:

- Scenario matrix with recovery scope, RPO, RTO, authority, dependencies, and validation owner.
- Backup architecture and dependency-aware schedule/retention plan by method and location.
- WAL/PITR, failover interaction, security/key/identity, immutability, audit, and monitoring design.
- Stepwise isolated restore runbook with technical and business acceptance criteria.
- Exercise calendar, worksheet/report, stage measurements, evidence policy, and readiness decision.
- Gaps, risks, remediation owners/dates, and clearly labeled observed, tested, proposed, and unverified capability.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [recovery-profile.example.json](assets/recovery-profile.example.json)
- [recovery-drill-report-template.md](assets/recovery-drill-report-template.md)
- [build_recovery_drill.py](scripts/build_recovery_drill.py)
- [Routing and behavior evals](evals/evals.json)
