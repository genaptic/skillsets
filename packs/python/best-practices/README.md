# Python Best Practices

Reusable workflows for structuring, testing, and handling failures in production-quality Python projects.

## Purpose and boundaries

This pack owns repository layout, test architecture, and Python exception policy. It does
not own CLI-specific user experience, web/API error schemas, framework architecture, or
deployment topology. Use `python-cli-apps` for command-line interface behavior.

## Included skills

| Skill | Focus |
|---|---|
| [`python-project-layout`](skills/python-project-layout/SKILL.md) | Packaging layout, import boundaries, project metadata, data files, typing markers, and entry points. |
| [`python-testing-strategy`](skills/python-testing-strategy/SKILL.md) | Risk-based test architecture, determinism, fixtures, CI selection, coverage, and flake control. |
| [`python-error-handling`](skills/python-error-handling/SKILL.md) | Exception contracts, translation boundaries, chaining, cleanup, logging ownership, and bounded retries. |

## Prerequisites

The instructions themselves require no dependency. Optional helpers require Python 3.11 or
newer and use only the standard library. Project verification may use the build backend,
test runner, type checker, or linter already selected by the target repository; do not
install tools without approval.

## Tools, network, and side effects

Most work begins read-only. Applying a proposed layout, test, or exception change can modify
project files and may run local build or test commands after explicit approval. The pack
does not require network access and its installers never run helper scripts.

## Install, update, and uninstall

The generated section below reflects the canonical lifecycle and publication metadata.

<!-- BEGIN GENERATED INSTALL COMMANDS -->
The marketplace source is repository-local and unpublished. Clone this repository and run these commands from its root; remote marketplace installation remains unavailable until post-release publication reconciliation. Run strict repository validation immediately before a local install so ignored cache files are not copied.

### Claude Code

```bash
claude plugin marketplace add dist/dev/claude
claude plugin install python-best-practices@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
claude plugin uninstall python-best-practices@genaptic-skillsets
claude plugin install python-best-practices@genaptic-skillsets
```

Uninstall:

```bash
claude plugin uninstall python-best-practices@genaptic-skillsets
```

### Codex

```bash
codex plugin marketplace add dist/dev/codex
codex plugin add python-best-practices@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
codex plugin remove python-best-practices@genaptic-skillsets
codex plugin add python-best-practices@genaptic-skillsets
```

Uninstall:

```bash
codex plugin remove python-best-practices@genaptic-skillsets
```

### OpenCode or optional direct install

The direct installer uses the public-preview `gh skill` interface. It checks the installed CLI before making changes; `--dry-run`/`-DryRun` does not require or probe `gh`.

No executable remote install command is published before a release SHA is recorded. Inspect the future exact-path operations locally:

```bash
bash dist/dev/install/python-best-practices.sh --dry-run
```

```powershell
.\dist\dev\install\python-best-practices.ps1 -DryRun
```

The dry run does not install skills or make a compatibility claim.
<!-- END GENERATED INSTALL COMMANDS -->
## Version and compatibility

<!-- BEGIN GENERATED LIFECYCLE -->
Current source version: `1.0.0`.

Maturity: `release-candidate`. Distribution visibility: `public`. Publication state: `unpublished`.

Current derived tag: `python-best-practices-v1.0.0`.

No public installation or native-client/model compatibility is claimed yet.
<!-- END GENERATED LIFECYCLE -->
Core guidance is framework-neutral. Packaging and test commands must be adapted to the repository's selected build backend and test runner.

See the root [`COMPATIBILITY.md`](../../../COMPATIBILITY.md) and this pack's compatibility
tests. Paths in this section are relative to the pack location when installed; root links
are intended for the source repository.

## Changelog and migrations

See [`CHANGELOG.md`](CHANGELOG.md). Public skill names are stable API. A rename, removal,
broader permission requirement, or materially changed output contract requires a major
version and migration notes.
