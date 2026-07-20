# PostgreSQL Databases

Schema, query, index, migration, and recovery workflows for safe, evidence-based PostgreSQL engineering.

## Purpose and boundaries

This pack owns PostgreSQL schema design and review, execution-plan diagnosis, index design,
migration safety, and backup/recovery planning. It does not replace a database operator,
provider runbook, incident commander, or application-domain owner. High-impact commands are
always proposals until an authorized operator approves and executes them.

## Included skills

| Skill | Focus |
|---|---|
| [`postgres-schema-design`](skills/postgres-schema-design/SKILL.md) | Domain-driven keys, types, constraints, relationships, tenancy, RLS, partitioning, and evolution. |
| [`postgres-schema-review`](skills/postgres-schema-review/SKILL.md) | Deployed DDL and catalog audit for integrity, ownership, privileges, RLS, indexes, and drift. |
| [`postgres-query-performance-review`](skills/postgres-query-performance-review/SKILL.md) | Evidence-led diagnosis using plans, cardinality, buffers, temp work, statistics, waits, and parameters. |
| [`postgres-index-design`](skills/postgres-index-design/SKILL.md) | Access methods, key order, operator classes, partial/expression indexes, overlap, and rollout cost. |
| [`postgres-migration-safety`](skills/postgres-migration-safety/SKILL.md) | Lock-aware, compatible production rollout with bounded backfills, validation, observability, and recovery. |
| [`postgres-backup-recovery`](skills/postgres-backup-recovery/SKILL.md) | Backup, WAL/PITR, retention, encryption, monitoring, restore runbooks, and RPO/RTO exercises. |

## Prerequisites

Offline helpers require Python 3.11 or newer and use only the standard library. Live analysis
requires separately supplied PostgreSQL access and client tools. Use least-privilege,
read-only credentials for inspection. Confirm the deployed major version, extensions,
replication topology, and managed-service limitations.

## Tools, network, and side effects

Offline helpers read files and print reports or write only an explicit output path. The
skills may propose SQL or operational commands, but they never authorize production
execution. Any lock-taking DDL, write query, restore, promotion, or external-system change
requires an explicit operator decision, a rollback/recovery plan, and environment-specific
review.

## Install, update, and uninstall

The generated section below reflects the canonical lifecycle and publication metadata.

<!-- BEGIN GENERATED INSTALL COMMANDS -->
The marketplace source is repository-local and unpublished. Clone this repository and run these commands from its root; remote marketplace installation remains unavailable until post-release publication reconciliation. Run strict repository validation immediately before a local install so ignored cache files are not copied.

### Claude Code

```bash
claude plugin marketplace add dist/dev/claude
claude plugin install postgres-databases@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
claude plugin uninstall postgres-databases@genaptic-skillsets
claude plugin install postgres-databases@genaptic-skillsets
```

Uninstall:

```bash
claude plugin uninstall postgres-databases@genaptic-skillsets
```

### Codex

```bash
codex plugin marketplace add dist/dev/codex
codex plugin add postgres-databases@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
codex plugin remove postgres-databases@genaptic-skillsets
codex plugin add postgres-databases@genaptic-skillsets
```

Uninstall:

```bash
codex plugin remove postgres-databases@genaptic-skillsets
```

### OpenCode or optional direct install

The direct installer uses the public-preview `gh skill` interface. It checks the installed CLI before making changes; `--dry-run`/`-DryRun` does not require or probe `gh`.

No executable remote install command is published before a release SHA is recorded. Inspect the future exact-path operations locally:

```bash
bash dist/dev/install/postgres-databases.sh --dry-run
```

```powershell
.\dist\dev\install\postgres-databases.ps1 -DryRun
```

The dry run does not install skills or make a compatibility claim.
<!-- END GENERATED INSTALL COMMANDS -->
## Version and compatibility

<!-- BEGIN GENERATED LIFECYCLE -->
Current source version: `1.0.0`.

Maturity: `release-candidate`. Distribution visibility: `public`. Publication state: `unpublished`.

Current derived tag: `postgres-databases-v1.0.0`.

No public installation or native-client/model compatibility is claimed yet.
<!-- END GENERATED LIFECYCLE -->
Confirm syntax, lock behavior, extensions, and managed-service restrictions against the deployed PostgreSQL major version and provider.

See the root [`COMPATIBILITY.md`](../../../COMPATIBILITY.md) and this pack's compatibility
tests. Paths in this section are relative to the pack location when installed; root links
are intended for the source repository.

## Changelog and migrations

See [`CHANGELOG.md`](CHANGELOG.md). Public skill names are stable API. A rename, removal,
broader permission requirement, or materially changed output contract requires a major
version and migration notes.
