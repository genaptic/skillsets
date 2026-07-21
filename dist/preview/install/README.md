# Generated direct installers

These optional adapters are generated from `skillpack.yaml`. They install each declared
skill by exact path with the public-preview `gh skill install` interface and require an
immutable full commit SHA.

They probe both `gh skill --help` and `gh skill install --help` before changing files.
A missing or unsupported command is reported as unavailable; it is never a compatibility
pass. Dry runs neither require nor probe `gh`.

Each probe and install invocation sets `GH_TELEMETRY=false`, `GH_PROMPT_DISABLED=1`,
and `GH_NO_UPDATE_NOTIFIER=1` in its process environment. PowerShell restores any prior
values after the transaction. These controls do not imply broader network isolation.

The installers do not run bundled helper scripts. Review a dry run before execution.

| Pack | Bash | PowerShell | Publication / default pin |
|---|---|---|---|
| `python-best-practices` | `python-best-practices.sh` | `python-best-practices.ps1` | `development; explicit SHA required` |
| `python-cli-apps` | `python-cli-apps.sh` | `python-cli-apps.ps1` | `development; explicit SHA required` |
| `rust-best-practices` | `rust-best-practices.sh` | `rust-best-practices.ps1` | `development; explicit SHA required` |
| `rust-cli-apps` | `rust-cli-apps.sh` | `rust-cli-apps.ps1` | `development; explicit SHA required` |
| `postgres-databases` | `postgres-databases.sh` | `postgres-databases.ps1` | `development; explicit SHA required` |

Default repository: `genaptic/skillsets`.

Review generated commands and the release before using `--force`.
