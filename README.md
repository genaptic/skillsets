# Genaptic Skillsets

Genaptic Skillsets is a portable Agent Skills monorepo: author a skill once, group related
skills by subject, and generate the adapters needed by Claude Code, Codex, and OpenCode.
The canonical repository identity is `genaptic/skillsets` and the marketplace name is
`genaptic-skillsets`.

> **Release-candidate status:** the six initial packs are locally testable but unpublished.
> No pack tag, release, supported public install source, or native-client compatibility claim
> exists yet. The Pages site may expose generated metadata, installer adapters, and OpenCode
> indexes for these unpublished candidates; hosting alone is not publication evidence.
> Publication remains gated on dated Claude Code, Codex, and OpenCode reports for the exact
> release commit.

## Packs

<!-- BEGIN GENERATED PACK CATALOG -->
| Pack | Purpose | Skills | Version | Publication | Claude | Codex | OpenCode |
|---|---|---:|---:|---|---|---|---|
| [`python-best-practices`](packs/python/best-practices/README.md) | Reusable workflows for structuring, testing, and handling failures in production-quality Python projects. | 3 | `1.0.0` | Release candidate | Plugin | Plugin | Installer + HTTP catalog |
| [`python-cli-apps`](packs/python/cli-apps/README.md) | Design, failure-contract, and test workflows for reliable Python command-line applications. | 3 | `1.0.0` | Release candidate | Plugin | Plugin | Installer + HTTP catalog |
| [`rust-best-practices`](packs/rust/best-practices/README.md) | Repository-aware workflows for designing, reviewing, testing, documenting, and maintaining production Rust systems. | 10 | `1.0.0` | Release candidate | Plugin | Plugin | Installer + HTTP catalog |
| [`rust-cli-apps`](packs/rust/cli-apps/README.md) | Portable workflows for designing stable Rust CLI applications and safely developing commands in existing CLIs. | 2 | `1.0.0` | Release candidate | Plugin | Plugin | Installer + HTTP catalog |
| [`postgres-databases`](packs/shared/postgres-databases/README.md) | Schema, query, index, migration, and recovery workflows for safe, evidence-based PostgreSQL engineering. | 6 | `1.0.0` | Release candidate | Plugin | Plugin | Installer + HTTP catalog |
| [`repository-development`](packs/shared/repository-development/README.md) | Research-led workflows for adding complete Agent Skills and independently installable skillpacks while preserving this repository's architecture, safety, eval, generation, and release guarantees. | 2 | `1.0.0` | Release candidate | Plugin | Plugin | Installer + HTTP catalog |

Marketplace: `genaptic-skillsets`. Published sources pin both the pack-specific tag and its full release commit SHA; release candidates use repository-local paths.
<!-- END GENERATED PACK CATALOG -->
The initial inventory contains 26 substantive skills:

- `python-best-practices` — project layout, testing strategy, and error handling
- `python-cli-apps` — command design, error output, and CLI testing
- `postgres-databases` — schema design/review, query performance, indexes, migrations, and recovery
- `repository-development` — one-skill additions and coherent independently installable skillpacks
- `rust-best-practices` — core Rust engineering, architecture, structure, abstractions, async,
  networking, testing, dependencies, workspace documentation, and rustdoc
- `rust-cli-apps` — complete CLI application design and focused command development

[`catalog.json`](catalog.json) is the machine-readable inventory. With no `source-sha` in a pack
manifest, its publication state is `unpublished` and its marketplace source is repository-local.
A protected pack release records the exact released SHA and regenerates pinned `git-subdir`
sources only after publication succeeds.

## Architecture

```text
packs/<language>/<subject>/
├── skillpack.yaml                 canonical pack contract
└── skills/<globally-unique-id>/   canonical SKILL.md and resources
    └── agents/openai.yaml         Codex discovery metadata

                generate
                   │
                   ├── Claude plugin manifests and marketplace
                   ├── Codex plugin manifests and marketplace
                   ├── OpenCode/direct installers and HTTP catalogs
                   ├── deterministic GitHub Pages landing page
                   ├── repository and pack README sections
                   └── byte hashes in dist/generated-files.json
```

Canonical content exists only under `packs/**/skills/`. Do not create authoring copies under
`.claude/skills`, `.agents/skills`, or `.opencode/skills`.

## Local setup and verification

Python 3.11 or newer and an already-installed Rust toolchain at version 1.85.0 or newer are
required. Bootstrap creates an isolated `.venv`, installs the fully pinned and hashed Python
development lock, installs this project with `--no-deps`, and explicitly fetches the committed
Rust behavior-harness lock into an isolated Cargo home under `.venv`. It never installs or
upgrades a Rust toolchain:

```bash
make bootstrap
make generate
make check
```

`make generate` is the only normal write step for derived artifacts. `make check` is
non-mutating: it fails when generated output or either dependency lock is stale and runs the
Rust asset harness locked and offline from the bootstrapped Cargo home. The installed CLI and
repository wrappers expose the same operations:

```bash
.venv/bin/skillpacks configure --help
.venv/bin/skillpacks generate --check
.venv/bin/skillpacks validate --check-generated --strict-placeholders
.venv/bin/skillpacks eval --json eval-report.json
.venv/bin/skillpacks release python-best-practices --draft
```

## Local client installation

Until releases exist, install only from this checkout and treat every pack as a release
candidate. Validate immediately before installation so ignored cache/bytecode residue cannot
be copied into the client's plugin cache:

```bash
.venv/bin/skillpacks validate --check-generated --strict-placeholders
```

For Codex, from the repository root:

```bash
codex plugin marketplace add "$(pwd)"
codex plugin add python-best-practices@genaptic-skillsets
```

After changing or regenerating the local pack, reinstall its snapshot:

```bash
codex plugin remove python-best-practices@genaptic-skillsets
codex plugin add python-best-practices@genaptic-skillsets
```

To remove both the plugin and local marketplace:

```bash
codex plugin remove python-best-practices@genaptic-skillsets
codex plugin marketplace remove genaptic-skillsets
```

The local Claude and Codex plugin marketplace commands are the primary package installation
flow. Generated Bash and PowerShell direct installers are optional adapters for the
public-preview `gh skill` interface. Their dry-run modes work without `gh`; real installs first
probe `gh skill --help` and `gh skill install --help` and report missing or unsupported commands
as unavailable rather than as compatibility passes.

Exact local Claude Code, Codex, OpenCode, Bash, and PowerShell commands are generated into each
pack README. Do not substitute `genaptic/skillsets` into a public install command until the
publication plan creates and verifies the corresponding tag.

## Evidence and release boundary

Three evidence levels are intentionally distinct:

1. **Structural validation** checks schemas, names, links, manifests, installers, placeholders,
   deterministic bytes, and the 182 routing plus 52 behavior definitions.
2. **Native-client smoke testing** records installation, discovery, invocation, permissions,
   and filesystem/network effects for an exact client version and source SHA.
3. **Model-backed behavior testing** records prompts, assertions, forbidden behavior, results,
   and a reviewer verdict. Structural evals are never reported as model passes.

Every pull request can run the first level without credentials. A publishable pack additionally
requires a clean worktree, the expected signed annotated tag, tracked allowlisted inputs, and
validated passing reports for Claude Code, Codex, and OpenCode at the exact release SHA. A draft
release is a deterministic local rehearsal only.

## Authoring

Use [`templates/skill/`](templates/skill/) and [`templates/skillpack/`](templates/skillpack/) as
starting points. Public IDs are globally unique kebab-case API. Keep `SKILL.md` focused, put
durable depth in `references/`, add helpers only when deterministic code improves safety, and
declare every prerequisite and side effect.

Use `$create-new-skill` when exactly one new public skill belongs in an existing pack. Use
`$create-new-skillset` when the work needs a new installation/release boundary, contains several
coordinated skills, or has no coherent existing pack owner. Both workflows require a reviewed
scaffold preview before any structural write.

The main references are:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/authoring.md`](docs/authoring.md)
- [`docs/evals.md`](docs/evals.md)
- [`docs/distribution.md`](docs/distribution.md)
- [`docs/github-pages.md`](docs/github-pages.md)
- [`docs/maintainer-signing.md`](docs/maintainer-signing.md)
- [`docs/release-process.md`](docs/release-process.md)
- [`docs/solo-maintainer-governance.md`](docs/solo-maintainer-governance.md)
- [`docs/threat-model.md`](docs/threat-model.md)
- [`AGENTS.md`](AGENTS.md)

## Identity, security, and license

[`repository.yaml`](repository.yaml) is the sole project, publisher, maintainer, marketplace,
security-channel, branch, and license identity contract. Pack identity and compatibility live in
each `skillpack.yaml`; generated surfaces must never be hand-edited.

Security reports belong exclusively in GitHub private vulnerability reporting. Do not disclose
vulnerabilities in public issues or Discussions; see
[`SECURITY.md`](SECURITY.md).

Licensed under Apache-2.0. See [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
