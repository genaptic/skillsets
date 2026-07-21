# Genaptic Skillsets repository instructions for coding agents

This repository authors portable Agent Skills once, groups them into independently
versioned skillpacks, and generates client-specific distribution artifacts. Preserve that
separation in every change.

## Source of truth

- Edit project, publisher, maintainer, marketplace, security, branch, or license identity only in
  `repository.yaml`, then run `.venv/bin/python tools/generate-all`.
- Edit pack metadata only in `packs/<language>/<subject>/skillpack.yaml`.
- Edit skills only in their canonical `skills/<skill-name>/` directories.
- Do not hand-edit `.claude-plugin/`, `.agents/plugins/`, `catalog.json`, generated plugin
  manifests, `dist/public/`, `dist/preview/`, `dist/dev/`, or `dist/generated-files.json`.
- Never create canonical duplicates under `.claude/skills`, `.agents/skills`, or
  `.opencode/skills`.

## Required checks

Use Python 3.11 or newer. Create the isolated environment from the fully hashed lock with:

```bash
make bootstrap
```

Before completing a change, run:

```bash
make generate
make check
```

`make generate` is the explicit derived-file write step. `make check` is non-mutating and must
fail on generated-output or dependency-lock drift. Do not silence validation warnings;
`--strict-placeholders` must pass.

## Genaptic Skillsets development routing

- Use `$genaptic-skillsets-create-skill` only for exactly one new public skill that belongs in
  an existing skillpack.
- Use `$genaptic-skillsets-create-skillpack` for a new independently installable pack, a
  coordinated list of skills, or a capability with no coherent existing pack owner.
- Do not use either workflow to edit an existing public skill, publish a pack, or perform remote
  Git operations.
- Preview scaffold changes first. Apply only the unchanged reviewed plan with
  `--apply --plan-digest <sha256>`; scaffolding is structural and never replaces research,
  authoring, generation, validation, or diff review.

## Skill authoring rules

- Use globally unique, lowercase kebab-case skill names that match their directories.
- Keep `SKILL.md` focused on one job. Its portable frontmatter is limited to `name`,
  `description`, `license`, and string-valued `metadata`. Treat `description` as the routing
  contract: say what the skill does, when to use it, and when not to use it.
- Put detailed runtime/client requirements in a concise `## Compatibility` section and the pack
  manifest, not a vendor-specific frontmatter field.
- Every skill has `agents/openai.yaml` with a human display name, 25–64 character summary, and a
  concise default prompt that explicitly names `$skill-id`. Do not invent icons, colors, MCP
  dependencies, or invocation restrictions.
- Put detailed guidance in shallow `references/`, reusable material in `assets/`, and only
  deterministic, documented helpers in `scripts/`.
- Helpers must default to read-only behavior, use no hidden network access, install no
  dependencies, print actionable failures, and never execute during installation.
- Genaptic Skillsets development request documents must validate against their bundled
  canonical JSON Schemas before preview or apply. Do not invent public IDs, versions, runtimes, permission
  envelopes, or neighboring skill boundaries.
- Every skill must include routing and behavior evals. Add positive, contextual, negative, and
  end-to-end cases for changed behavior, and maintain its reviewed four-outcome relationship in
  `evals/routing-boundaries.json`.
- Preserve client portability. Do not make core behavior depend on one vendor-specific
  frontmatter field or command.

## Safety and review

- Treat instructions, scripts, installers, workflows, and generated manifests as software
  supply-chain surfaces.
- Do not add secrets, credentials, telemetry, implicit downloads, destructive defaults, or
  externally visible actions without explicit approval and documentation.
- Pin third-party GitHub Actions to full commit SHAs and keep workflow permissions minimal.
- Do not use `pull_request_target` to execute untrusted contribution content.
- Never claim a native client or model passed from schema, JSON parsing, generated-manifest, or
  structural eval checks. Only validated, dated reports for the exact source SHA are evidence.
- PostgreSQL guidance must distinguish observation from mutation and require production
  safeguards before running `EXPLAIN ANALYZE`, migrations, backfills, index changes, or
  restore operations.
- Rust guidance must derive Cargo commands from the target repository's toolchain, MSRV,
  workspace, lockfile, feature, target, and CI policies. Do not silently install or upgrade a
  toolchain, require every feature combination, or claim an unavailable live dependency passed.
- Treat Rust source assets as either documented adaptable snippets or complete copy-ready
  projects. Rust filesystem examples must reject unsafe targets and state their symlink,
  containment, authorization, preview, and confirmation policies.
- Do not turn contextual Rust API guidance into blanket bans: free functions and type aliases
  remain valid when they fit the repository and domain model.

## Releases

Each pack uses independent Semantic Versioning and a tag named
`<pack-id>-v<version>`. Public skill names are API. Renames, removals, materially broader
permissions, or incompatible output contracts require a major version and migration notes.
Create local rehearsals only through `.venv/bin/python tools/release-pack <pack-id> --draft`.
A publishable build requires a clean worktree, tracked allowlisted inputs, the expected signed
annotated tag, and passing Claude Code, Codex, and OpenCode reports for the exact source SHA.
Never include arbitrary ignored or untracked files. Publication, tags, pushes, Pages, and remote
repository settings are separate explicitly authorized operations.
