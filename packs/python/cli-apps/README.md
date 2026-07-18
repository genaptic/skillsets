# Python CLI Applications

Design, failure-contract, and test workflows for reliable Python command-line applications.

## Purpose and boundaries

This pack owns command shape, user-facing failure contracts, and CLI-focused test strategy.
It does not own general package layout, domain exception architecture, HTTP API responses,
or shell implementation. Use the narrower neighboring skill when a request is only about
generic Python testing or exceptions.

## Included skills

| Skill | Focus |
|---|---|
| [`python-cli-command-design`](skills/python-cli-command-design/SKILL.md) | Command trees, arguments, options, configuration precedence, output modes, help, and compatibility. |
| [`python-cli-error-output`](skills/python-cli-error-output/SKILL.md) | Failure classes, stdout/stderr policy, stable exits, machine errors, redaction, signals, and pipes. |
| [`python-cli-testing`](skills/python-cli-testing/SKILL.md) | In-process and subprocess tests for entry points, streams, config, TTYs, signals, pipes, and platforms. |

## Prerequisites

Optional helpers require Python 3.11 or newer and use only the standard library. Guidance is
framework-neutral; inspect the actual argparse, Click, Typer, or other framework version
before relying on framework-specific behavior.

## Tools, network, and side effects

Design and static review are read-only. Applying changes writes project files. One optional
error-contract helper can execute a local command only when passed an explicit
`--confirm-execute` flag; dry validation is the default. No helper uses the network.

## Install, update, and uninstall

This pack is an unpublished release candidate. The generated section below must remain
repository-local until protected Claude Code, Codex, and OpenCode evidence exists for the
exact release SHA.

<!-- BEGIN GENERATED INSTALL COMMANDS -->
The marketplace source is repository-local and unpublished. Clone this repository and run these commands from its root; remote marketplace installation remains unavailable until the post-release source-SHA update. Run strict repository validation immediately before a local install so ignored cache files are not copied.

### Claude Code

```bash
claude plugin marketplace add .
claude plugin install python-cli-apps@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
claude plugin uninstall python-cli-apps@genaptic-skillsets
claude plugin install python-cli-apps@genaptic-skillsets
```

Uninstall:

```bash
claude plugin uninstall python-cli-apps@genaptic-skillsets
```

### Codex

```bash
codex plugin marketplace add .
codex plugin add python-cli-apps@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
codex plugin remove python-cli-apps@genaptic-skillsets
codex plugin add python-cli-apps@genaptic-skillsets
```

Uninstall:

```bash
codex plugin remove python-cli-apps@genaptic-skillsets
```

### OpenCode or optional direct install

The direct installer uses the public-preview `gh skill` interface. It checks the installed CLI before making changes; `--dry-run`/`-DryRun` does not require or probe `gh`.

No executable remote install command is published before a release SHA is recorded. Inspect the future exact-path operations locally:

```bash
bash dist/install/python-cli-apps.sh --dry-run
```

```powershell
.\dist\install\python-cli-apps.ps1 -DryRun
```

The dry run does not install skills or make a compatibility claim.
<!-- END GENERATED INSTALL COMMANDS -->
## Version and compatibility

Release-candidate manifest version: `1.0.0`.

Expected release tag (not yet created): `python-cli-apps-v1.0.0`.

No public installation or native-client/model compatibility is claimed yet.

Guidance applies to argparse, Click, Typer, and similar frameworks. Framework-specific APIs must be confirmed against the version in the target project.

See the root [`COMPATIBILITY.md`](../../../COMPATIBILITY.md) and this pack's compatibility
tests. Paths in this section are relative to the pack location when installed; root links
are intended for the source repository.

## Changelog and migrations

See [`CHANGELOG.md`](CHANGELOG.md). Public skill names are stable API. A rename, removal,
broader permission requirement, or materially changed output contract requires a major
version and migration notes.
