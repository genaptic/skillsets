# Rust CLI Applications

Portable workflows for designing stable Rust CLI applications and safely developing commands
in existing CLIs.

## Purpose and boundaries

Use this pack to design a portable Rust command-line application or to add and change one
command inside an existing Rust CLI. It covers grammar, parser mapping, dispatch and domain
boundaries, paths and configuration, stdout and stderr, output formats, diagnostics, exit
codes, terminal behavior, persistence, completions, tests, and cross-platform behavior.

The pack discovers and preserves the target repository's parser, runtime, dispatch, and
test architecture. It does not require clap, async Rust, a fixed `App` or command-context
pattern, or companion skills from another pack. General Rust engineering work remains in
[`rust-best-practices`](../best-practices/README.md).

## Included skills

| Skill | Focus |
|---|---|
| [`rust-cli-application-design`](skills/rust-cli-application-design/SKILL.md) | Design or review a complete portable Rust CLI contract and architecture, including grammar, parser mapping, domain boundaries, paths, configuration, output streams and formats, errors and exit codes, terminal behavior, completions, persistence, tests, and packaging. |
| [`rust-cli-command-development`](skills/rust-cli-command-development/SKILL.md) | Add or change exactly one command in an existing Rust CLI by discovering its grammar, parser, dispatch, application, domain, filesystem, output, error, test, and documentation conventions and preserving their existing contracts. |

## Prerequisites

- Core instructions are portable across Claude Code, Codex, and OpenCode.
- Inspect the repository's toolchain, MSRV, edition, manifests, lockfile, CLI documentation,
  grammar, dispatch path, output contracts, and tests before proposing a change.
- Bundled Edition 2024 examples require Rust 1.85 or newer and must be adapted to older
  repository policies.
- Clap guidance applies only when the target already uses clap or explicitly selects it.

## Tools, network, and side effects

- Local inspection is read-only until the requested command contract and affected paths are
  understood.
- Network access is optional and limited to current primary documentation. Missing access
  must be reported rather than hidden behind a currentness claim.
- Project-scoped writes and repository-approved Cargo or test commands are optional-explicit.
- Destructive commands require an exact target, root/home/worktree rejection, containment
  and ownership evidence, explicit symlink policy, reviewed preview, confirmation, and
  adversarial tests.
- The pack installs nothing, publishes nothing, performs no remote Git action, and makes no
  external write.

## Install, update, and uninstall

<!-- BEGIN GENERATED INSTALL COMMANDS -->
The marketplace source is repository-local and unpublished. Clone this repository and run these commands from its root; remote marketplace installation remains unavailable until the post-release source-SHA update. Run strict repository validation immediately before a local install so ignored cache files are not copied.

### Claude Code

```bash
claude plugin marketplace add .
claude plugin install rust-cli-apps@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
claude plugin uninstall rust-cli-apps@genaptic-skillsets
claude plugin install rust-cli-apps@genaptic-skillsets
```

Uninstall:

```bash
claude plugin uninstall rust-cli-apps@genaptic-skillsets
```

### Codex

```bash
codex plugin marketplace add .
codex plugin add rust-cli-apps@genaptic-skillsets
```

For local changes, regenerate this repository and reinstall the plugin:

```bash
codex plugin remove rust-cli-apps@genaptic-skillsets
codex plugin add rust-cli-apps@genaptic-skillsets
```

Uninstall:

```bash
codex plugin remove rust-cli-apps@genaptic-skillsets
```

### OpenCode or optional direct install

The direct installer uses the public-preview `gh skill` interface. It checks the installed CLI before making changes; `--dry-run`/`-DryRun` does not require or probe `gh`.

No executable remote install command is published before a release SHA is recorded. Inspect the future exact-path operations locally:

```bash
bash dist/install/rust-cli-apps.sh --dry-run
```

```powershell
.\dist\install\rust-cli-apps.ps1 -DryRun
```

The dry run does not install skills or make a compatibility claim.
<!-- END GENERATED INSTALL COMMANDS -->
## Version and compatibility

Current pack version: `1.0.0`.

Release state: unpublished release candidate.

Expected future tag (not yet created): `rust-cli-apps-v1.0.0`.

Guidance discovers the target parser, dispatch, runtime, output, and test architecture. Clap
examples apply only when clap is already selected.

See the root [`COMPATIBILITY.md`](../../../COMPATIBILITY.md) and this pack's compatibility
tests. Paths in this section are relative to the pack location when installed; root links
are intended for the source repository.

## Changelog and migrations

See [`CHANGELOG.md`](CHANGELOG.md). Public skill names are stable API. A rename, removal,
broader permission requirement, or materially changed output contract requires a major
version and migration notes.
