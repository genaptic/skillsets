# Genaptic Skillsets Development

Research-led workflows for adding complete Agent Skills and independently installable
skillpacks while preserving this repository's architecture, safety, evaluation, generation,
and release guarantees.

## Purpose and boundaries

This pack owns authoring work inside the Genaptic Skillsets monorepo. It creates exactly one
skill in an existing pack or one new skillpack containing an explicitly declared set of
skills. It does not perform the requested domain workflow itself, edit an existing skill,
publish releases, commit or push changes, open remote changes, or bypass repository
validation.

`genaptic-skillsets-create-skill` is the narrower route when an existing pack owns one
proposed skill. `genaptic-skillsets-create-skillpack` owns a new installation and release boundary, a coordinated group of
skills, or a capability with no coherent existing pack. A one-skill pack is valid only when
that independent boundary is real and its nearest excluded outcome belongs to an existing
skill outside the proposed pack.

## Included skills

| Skill | Focus |
|---|---|
| [`genaptic-skillsets-create-skill`](skills/genaptic-skillsets-create-skill/SKILL.md) | Research, design, author, register, and verify exactly one new skill in an existing skillpack. |
| [`genaptic-skillsets-create-skillpack`](skills/genaptic-skillsets-create-skillpack/SKILL.md) | Research, decompose, author, register, and verify one independently installable skillpack and its declared skills. |

## Prerequisites

Read the current checkout's `AGENTS.md` and canonical repository documentation before making
changes. The preview-first scaffold helpers require Python 3.11 or newer, use only the
standard library, perform no network calls or subprocess execution, and create structural
starting points rather than finished skills. Full verification uses the repository's locked
development environment; do not install dependencies implicitly.

Current-source research uses primary official web sources when network access is allowed. If
access is prohibited or unavailable, continue only where repository evidence is sufficient,
record the missing evidence, and do not claim the result is current or complete.

## Tools, network, and side effects

The workflows begin with read-only repository inspection and optional web research. After a
reviewed preview, they may add canonical files under `packs/`, update canonical pack metadata,
run the explicit `make generate` write step, and run non-mutating `make check`. They never
install dependencies, run bundled helpers during installation, create canonical client
duplicates, or perform Git or remote publication actions without a separate request.

The helpers preview by default. Applying a preview requires its exact plan digest, rechecks
the source preimages, refuses existing or unsafe destinations, and has bounded multi-file
crash recovery. Inspect the working tree after any interrupted apply before retrying.

## Install, update, and uninstall

The generated section below reflects the canonical lifecycle and publication metadata.

<!-- BEGIN GENERATED INSTALL COMMANDS -->
The marketplace source is repository-local and unpublished. Clone this repository and run these commands from its root; remote marketplace installation remains unavailable until post-release publication reconciliation. Run strict repository validation immediately before a local install so ignored cache files are not copied.

### Claude Code

```bash
claude plugin marketplace add dist/dev/claude
claude plugin install genaptic-skillsets-development@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
claude plugin uninstall genaptic-skillsets-development@genaptic-skillsets
claude plugin install genaptic-skillsets-development@genaptic-skillsets
```

Uninstall:

```bash
claude plugin uninstall genaptic-skillsets-development@genaptic-skillsets
```

### Codex

```bash
codex plugin marketplace add dist/dev/codex
codex plugin add genaptic-skillsets-development@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
codex plugin remove genaptic-skillsets-development@genaptic-skillsets
codex plugin add genaptic-skillsets-development@genaptic-skillsets
```

Uninstall:

```bash
codex plugin remove genaptic-skillsets-development@genaptic-skillsets
```

### OpenCode or optional direct install

The direct installer uses the public-preview `gh skill` interface. It checks the installed CLI before making changes; `--dry-run`/`-DryRun` does not require or probe `gh`.

No executable remote install command is published before a release SHA is recorded. Inspect the future exact-path operations locally:

```bash
bash dist/dev/install/genaptic-skillsets-development.sh --dry-run
```

```powershell
.\dist\dev\install\genaptic-skillsets-development.ps1 -DryRun
```

The dry run does not install skills or make a compatibility claim.
<!-- END GENERATED INSTALL COMMANDS -->
## Version and compatibility

<!-- BEGIN GENERATED LIFECYCLE -->
Current source version: `1.0.0`.

Maturity: `release-candidate`. Distribution visibility: `maintainers`. Publication state: `unpublished`.

Current derived tag: `genaptic-skillsets-development-v1.0.0`.

This maintainer-only pack is ineligible for formal public release.
<!-- END GENERATED LIFECYCLE -->
See the root [`COMPATIBILITY.md`](../../../COMPATIBILITY.md) and this pack's structural
compatibility fixture. Paths in this section are relative to the pack location when installed;
root links are intended for the source repository.

## Changelog and migrations

See [`CHANGELOG.md`](CHANGELOG.md). Public skill names and normalized request contracts are
API. Renames, removals, broader permission requirements, or incompatible output contracts
require a major version and migration notes.
