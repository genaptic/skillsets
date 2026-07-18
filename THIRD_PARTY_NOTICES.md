# Third-party notices

This repository contains original skill instructions and tooling. It relies on or references
external specifications and documentation but does not vendor those projects' code unless a
future change explicitly records it here.

## Standards and documentation referenced

- Agent Skills specification and reference guidance, maintained at `agentskills.io`.
- Anthropic Claude Code plugin, marketplace, and skills documentation.
- OpenAI Codex plugin and skills documentation.
- OpenCode skills documentation, including its HTTP catalog format.
- Python documentation and the Python Packaging User Guide.
- pytest documentation.
- Click documentation.
- Rust, Cargo, rustup, rustdoc, and Clippy documentation.
- clap, Tokio, reqwest, tonic, and SQLx documentation.
- PostgreSQL documentation.
- GitHub Actions and repository-security documentation.

Links, target versions, and review provenance are listed in `SOURCES.md` and in each skill's
`references/sources.md`. Revalidate version-sensitive claims during release preparation.

## Development dependencies

- Python development dependencies and their exact versions/hashes are declared in
  `requirements-dev.in` and `requirements-dev.txt`; each dependency retains its own license.
- Ruff — MIT License.
- ShellCheck — GNU General Public License, version 3.
- PSScriptAnalyzer — MIT License.
- actionlint — MIT License.

These tools are used to develop or validate the repository and are not bundled into pack
release archives. Before redistributing a development environment, generate and review a
complete dependency license report.

## Trademarks

Claude, Anthropic, Codex, OpenAI, OpenCode, GitHub, Python, pytest, Click, Rust, Cargo, clap,
Tokio, reqwest, tonic, SQLx, PostgreSQL, and other names belong to their respective owners.
Their appearance describes compatibility or sources and does not imply endorsement.
