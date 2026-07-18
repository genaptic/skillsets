# Compatibility

## Compatibility levels

This repository distinguishes three kinds of evidence:

1. **Structural validation** — schemas, generated artifacts, manifests, eval definitions,
   installers, and repository invariants pass local or CI checks. This verifies shape and
   consistency, not client behavior.
2. **Native-client smoke evidence** — a named client and version installs the exact pack SHA
   in an isolated environment, discovers the expected skills, and completes update and
   removal checks.
3. **Model-backed behavior evidence** — a named client/model combination runs declared
   routing and behavior cases, with assertions, forbidden behaviors, side effects, and
   reviewer verdicts recorded.

Genaptic Skillsets provides structural validation and protected/manual workflows for
collecting the other two evidence classes. It does not claim a client or model passed unless
a dated, schema-valid report under `compatibility/reports/` identifies the exact source SHA.

## Designed targets

| Target | Distribution adapter | Canonical skill format |
|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` and per-pack plugin | `skills/<name>/SKILL.md` |
| Codex | `.agents/plugins/marketplace.json` and per-pack plugin | `skills/<name>/SKILL.md` |
| OpenCode | generated HTTP catalog plus optional Bash/PowerShell `gh skill` preview adapters | `skills/<name>/SKILL.md` |
| OpenCode V2 | generated HTTP `index.json` and file tree | Named skill Markdown plus resources |

Vendor clients evolve. Review the current primary sources in `SOURCES.md`, run the protected
compatibility workflow for every pack release, and update both the source record and adapter
tests when a format changes.

## Tooling baseline

- Repository tools: Python 3.11 or newer.
- Skill helper scripts: Python 3.11 or newer unless a skill states otherwise.
- PostgreSQL skills: principles apply broadly, with current references written for
  PostgreSQL 18. Confirm syntax, lock behavior, managed-service restrictions, and extension
  availability against the deployed major version.
- Rust skills: use the target repository's selected toolchain, declared MSRV, edition,
  workspace, lockfile, feature, target, and CI policies. Edition 2024 examples require Rust
  1.85 or newer; no skill silently upgrades a target project or installs a toolchain.
- Rust behavior harness: `make bootstrap` explicitly fetches its locked dependency graph into
  an isolated repository-local Cargo cache using an already-installed toolchain; it never
  installs Rust. `make check` and `make rust-check` reuse that graph with Cargo locked and
  offline.
- Shell installers: Bash 3.2 or newer, including the system Bash shipped with macOS.
- PowerShell installers: PowerShell 7 or newer.
- Direct installs: generated Bash and PowerShell installers are optional adapters for the
  public-preview `gh skill` interface. They require both `gh skill --help` and
  `gh skill install --help` to succeed. Missing or unsupported commands are reported as
  unavailable rather than passed and do not block the primary Claude/Codex local-plugin or
  generated OpenCode HTTP-catalog paths.

## Portability rules

Portable behavior cannot depend on client-specific frontmatter. Canonical skill frontmatter
uses standard fields only. Client-specific metadata belongs in generated plugin manifests
or sidecars.

Optional helper scripts are not run during installation. A client may lack a tool named in a
skill; the skill must detect that condition, explain the limitation, and provide a manual or
read-only fallback when practical.

## Recording a compatibility run

Create the machine-readable report required by the compatibility-report schema and use
`compatibility/report-template.md` for reviewer narrative. Name reports with the date,
client, client version, pack, and tag. The release-gate report uses `.json`; an optional
narrative with the same stem uses `.md`. Record:

- Clean environment and operating system.
- Client and model versions plus the exact install command.
- Pack version, release tag, and full 40-character source SHA.
- Discovered skill names.
- Every executed case, assertion, forbidden behavior, and overlap expectation.
- Permissions, network endpoints, filesystem effects, and unexpected behavior.
- Reviewer identity and explicit pass/fail verdict.

Never include access tokens, local paths containing user names, or proprietary prompts.

## Release policy

Pull requests require structural validation, deterministic generation, structural evals,
tests, lint, and installer/manifest checks. They do not require credentials or live-client
runs.

A publishable pack release requires dated passing native-client and model-backed evidence
for Claude Code, Codex, and OpenCode against the exact release SHA. Draft release rehearsals
may be built without that evidence but are not publishable compatibility claims. The initial
six `1.0.0` pack manifests remain release candidates until this protected gate passes.
