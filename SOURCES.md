# Research sources

Primary documentation used to design this repository and author the initial skills. Vendor
formats are version-sensitive: each skill records target versions and review provenance in
`references/sources.md`, and maintainers refresh the relevant sources whenever an adapter or
compatibility claim changes.

## Agent skill and client formats

- Agent Skills specification: https://agentskills.io/specification
- Agent Skills overview: https://agentskills.io
- Agent Skills description optimization:
  https://agentskills.io/skill-creation/optimizing-descriptions
- Claude Code skills: https://code.claude.com/docs/en/skills
- Claude Code plugins: https://code.claude.com/docs/en/plugins
- Claude Code plugin marketplaces: https://code.claude.com/docs/en/plugin-marketplaces
- Codex skills: https://developers.openai.com/codex/build-skills
- Codex plugins: https://developers.openai.com/codex/build-plugins
- Codex developer commands: https://developers.openai.com/codex/developer-commands
- OpenCode skills: https://opencode.ai/docs/skills/
- OpenCode V2 skills catalogs: https://v2.opencode.ai/skills
- GitHub CLI skills preview: https://cli.github.com/manual/gh_skill
- GitHub CLI skill install: https://cli.github.com/manual/gh_skill_install
- GitHub CLI skill publish: https://cli.github.com/manual/gh_skill_publish
- GitHub CLI 2.90.0 release (`gh skill` public preview):
  https://github.com/cli/cli/releases/tag/v2.90.0
- GitHub CLI 2.91.0 release (expanded agent support):
  https://github.com/cli/cli/releases/tag/v2.91.0
- GitHub CLI environment variables:
  https://cli.github.com/manual/gh_help_environment
- GitHub CLI telemetry and opt-out behavior:
  https://docs.github.com/en/github-cli/github-cli/github-cli-telemetry
- JSON Schema Draft 2020-12: https://json-schema.org/draft/2020-12

## Python and testing

- Python Packaging User Guide, `pyproject.toml`:
  https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- Python packaging `pyproject.toml` specification:
  https://packaging.python.org/en/latest/specifications/pyproject-toml/
- Python packaging discussion of source and flat layouts:
  https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- Python `argparse`: https://docs.python.org/3/library/argparse.html
- Python exceptions: https://docs.python.org/3/tutorial/errors.html
- Python `contextlib`: https://docs.python.org/3/library/contextlib.html
- Python logging: https://docs.python.org/3/library/logging.html
- Python warnings: https://docs.python.org/3/library/warnings.html
- Python subprocesses: https://docs.python.org/3/library/subprocess.html
- Python `compileall`: https://docs.python.org/3/library/compileall.html
- Python `PYTHONPYCACHEPREFIX`:
  https://docs.python.org/3/using/cmdline.html#envvar-PYTHONPYCACHEPREFIX
- Python `os` filesystem interfaces, including `lstat` and `scandir`:
  https://docs.python.org/3/library/os.html
- Python `pathlib` symlink behavior: https://docs.python.org/3/library/pathlib.html
- Python file-type and Windows reparse-point constants:
  https://docs.python.org/3/library/stat.html
- Python Unicode normalization: https://docs.python.org/3/library/unicodedata.html
- Python case folding: https://docs.python.org/3/library/stdtypes.html#str.casefold
- Python jsonschema validation API:
  https://python-jsonschema.readthedocs.io/en/stable/validate/
- pytest good practices: https://docs.pytest.org/en/stable/explanation/goodpractices.html
- pytest fixtures: https://docs.pytest.org/en/stable/how-to/fixtures.html
- pytest parametrization: https://docs.pytest.org/en/stable/how-to/parametrize.html
- Click testing: https://click.palletsprojects.com/en/stable/testing/
- Click exceptions: https://click.palletsprojects.com/en/stable/exceptions/
- POSIX utility syntax guidelines:
  https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap12.html

## PostgreSQL

The initial database skills use PostgreSQL 18 documentation:

- Data definition: https://www.postgresql.org/docs/18/ddl.html
- Constraints: https://www.postgresql.org/docs/18/ddl-constraints.html
- Schemas: https://www.postgresql.org/docs/18/ddl-schemas.html
- Row security: https://www.postgresql.org/docs/18/ddl-rowsecurity.html
- Partitioning: https://www.postgresql.org/docs/18/ddl-partitioning.html
- Indexes: https://www.postgresql.org/docs/18/indexes.html
- Multicolumn indexes: https://www.postgresql.org/docs/18/indexes-multicolumn.html
- Index-only scans: https://www.postgresql.org/docs/18/indexes-index-only-scans.html
- Partial indexes: https://www.postgresql.org/docs/18/indexes-partial.html
- `CREATE INDEX`: https://www.postgresql.org/docs/18/sql-createindex.html
- Explicit locking: https://www.postgresql.org/docs/18/explicit-locking.html
- `EXPLAIN`: https://www.postgresql.org/docs/18/using-explain.html
- `ANALYZE`: https://www.postgresql.org/docs/18/sql-analyze.html
- Backup and restore: https://www.postgresql.org/docs/18/backup.html
- Continuous archiving and point-in-time recovery:
  https://www.postgresql.org/docs/18/continuous-archiving.html
- `pg_dump`: https://www.postgresql.org/docs/18/app-pgdump.html
- `pg_basebackup`: https://www.postgresql.org/docs/18/app-pgbasebackup.html
- `pg_verifybackup`: https://www.postgresql.org/docs/18/app-pgverifybackup.html

## Rust and Cargo

Rust guidance is repository-relative: recheck version-sensitive APIs against the target
toolchain and dependency versions instead of silently upgrading them.

- Rust Reference: https://doc.rust-lang.org/reference/
- Rust standard library: https://doc.rust-lang.org/std/
- Rust Edition Guide: https://doc.rust-lang.org/edition-guide/
- Rust 2024 newly unsafe environment functions:
  https://doc.rust-lang.org/edition-guide/rust-2024/newly-unsafe-functions.html
- Rust API Guidelines: https://rust-lang.github.io/api-guidelines/
- `std::process::ExitCode`: https://doc.rust-lang.org/std/process/struct.ExitCode.html
- Cargo reference: https://doc.rust-lang.org/cargo/reference/
- Cargo workspaces: https://doc.rust-lang.org/cargo/reference/workspaces.html
- Cargo features: https://doc.rust-lang.org/cargo/reference/features.html
- Cargo `rust-version`: https://doc.rust-lang.org/cargo/reference/rust-version.html
- rustup toolchains and overrides: https://rust-lang.github.io/rustup/overrides.html
- rustdoc book: https://doc.rust-lang.org/rustdoc/
- rustdoc lints: https://doc.rust-lang.org/rustdoc/lints.html
- Clippy documentation: https://doc.rust-lang.org/clippy/
- clap documentation: https://docs.rs/clap/latest/clap/
- Tokio documentation: https://docs.rs/tokio/latest/tokio/
- Tokio graceful shutdown: https://tokio.rs/tokio/topics/shutdown
- Tokio paused time: https://docs.rs/tokio/latest/tokio/time/fn.pause.html
- reqwest documentation: https://docs.rs/reqwest/latest/reqwest/
- reqwest `ClientBuilder`: https://docs.rs/reqwest/latest/reqwest/struct.ClientBuilder.html
- tonic documentation: https://docs.rs/tonic/latest/tonic/
- tonic request metadata and timeout API: https://docs.rs/tonic/latest/tonic/struct.Request.html
- SQLx documentation: https://docs.rs/sqlx/latest/sqlx/
- SQLx pool options: https://docs.rs/sqlx/latest/sqlx/pool/struct.PoolOptions.html

## Repository and workflow security

- GitHub Actions secure use:
  https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions
- GitHub Actions runner context and temporary directory:
  https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#runner-context
- Git reference-name validation: https://git-scm.com/docs/git-check-ref-format
- Default community health files:
  https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file
