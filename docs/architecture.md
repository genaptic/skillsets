# Architecture

## Goals

The repository optimizes for five properties:

1. **Single-source authoring** — each skill has one canonical `SKILL.md`.
2. **Pack-level distribution** — every language/subject is independently installable and
   versioned.
3. **Client portability** — core behavior does not depend on one client's private
   frontmatter.
4. **Reviewable trust boundaries** — generated files, scripts, network access, and mutations
   are explicit.
5. **Reproducibility** — generated catalogs and release archives can be recreated from
   reviewed source.

## Layers

### Skill

A skill is a focused procedure under:

```text
packs/<language>/<subject>/skills/<skill-name>/
```

The directory name and frontmatter `name` are identical. `SKILL.md` is the routing and
execution entry point. Supporting content is shallow:

```text
references/   durable detail and checklists
assets/       templates and examples
scripts/      deterministic optional helpers
evals/        routing and behavior specifications
```

Skills do not reach outside their own directory. This matters because plugin installers may
copy only a plugin subtree.

### Skillpack

A skillpack is one `<language>/<subject>` package. `skillpack.yaml` is the canonical pack
manifest. It declares public identity, version, supported targets, skill membership, and
operational characteristics. A pack may contain one or more focused skills. Compatibility
runtimes are a named map rather than a Python-specific contract, so language-neutral and
multi-runtime packs use the same manifest shape.

The generated Claude and Codex manifests point at the same `skills/` directory. No content
is copied between those plugin adapters.

### Catalog and marketplace

The root catalogs list only reconciled public releases. Development and preview catalogs are
generated into isolated, self-contained trees:

- `catalog.json` — neutral machine index.
- `.claude-plugin/marketplace.json` — Claude marketplace.
- `.agents/plugins/marketplace.json` — Codex marketplace.
- `dist/public/index.html` — deterministic GitHub Pages landing page.
- `dist/public/opencode/.../index.json` — published OpenCode HTTP catalogs.
- `dist/public/install/*` — published installers pinned to an exact released source SHA.
- `dist/preview/` — public candidates for CI artifacts only.
- `dist/dev/` — all non-withdrawn packs, including maintainer tooling.

Before publication, a pack appears only in preview/development outputs. After a protected release
succeeds, `publication.latest-release` records its exact version, SHA, release ID, and timestamp;
regeneration then emits a Git-backed public source pinned by both the derived tag and SHA. The
generator never invents publication metadata.

## Data flow

```text
repository.yaml
       │
       ├── repository identity and marketplace identity
       │
skillpack.yaml × N
       │
       ├── pack metadata, targets, declared skills, and optional released source SHA
       │
canonical skill trees
       │
       ▼
tools/generate-all
       │
       ├── plugin manifests
       ├── root marketplaces and catalog
       ├── README catalog
       ├── direct installers
       ├── target-selected OpenCode HTTP trees
       └── Pages landing page
```

Generated files contain a notice or live only in generated paths. CI regenerates them and
fails on a diff. Runtime trees are copied byte-for-byte, preserve executable modes, exclude
evals, caches, bytecode, secrets, and editor residue, and are hashed deterministically.
Security-sensitive exclusions use normalized, case-insensitive comparison keys without
renaming allowed resources. Canonical inputs and generated destinations are walked without
following links; generation preflights the complete operation and rejects links, junctions,
special files, or detected namespace changes before writing or removing anything. Generation
also removes stale target-specific artifacts when a pack or declared target is removed.

## Why one monorepo

A monorepo makes global name uniqueness, cross-skill overlap review, consistent safety
policy, shared tooling, and one marketplace straightforward. Independent pack versions
prevent unrelated subjects from forcing synchronized releases.

The tradeoff is release resolution: a repository's newest tag may belong to another pack.
Published marketplace metadata therefore records both the pack-specific tag and exact released
SHA, while every direct installer defaults to that immutable SHA. Unversioned install commands
are not considered supported instructions.

## Boundaries and non-goals

The repository does not implement:

- A custom package manager.
- Runtime dependency resolution among skillpacks.
- Automatic command execution at installation time.
- A model-specific router.
- Guaranteed behavior across all models or client versions.
- Production database automation.

Skills may recommend or prepare changes, but the operator remains the approval boundary.

## Extension points

New targets should be generated adapters, not new canonical copies. New metadata should be
added first to `skillpack.yaml` and its schema, then mapped in generators. Client-specific
features belong in a sidecar or generated manifest and may not be required for the portable
workflow.
