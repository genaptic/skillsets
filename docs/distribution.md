# Distribution

## Canonical and generated content

Canonical pack content:

```text
packs/<language>/<subject>/
├── skillpack.yaml
├── README.md
├── CHANGELOG.md
└── skills/
```

Generated adapters:

```text
pack/.claude-plugin/plugin.json
pack/.codex-plugin/plugin.json
.claude-plugin/marketplace.json
.agents/plugins/marketplace.json
catalog.json
dist/public/
dist/preview/
dist/dev/
```

Run `python3 tools/generate-all` after any manifest, identity, version, or skill-membership
change. Generation honors each pack's declared targets and removes stale target artifacts.
Do not hand-edit an adapter.

## Publication state

The manifest separates current development from the last immutable public release. Current
`version` and `maturity` describe the source tree; `distribution.visibility` controls public or
maintainer use; and `publication.latest-release` preserves the last released version, SHA,
release ID, and timestamp. The legacy top-level `source-sha` is invalid.

One selector feeds every adapter. Root marketplaces and `catalog.json` contain only public packs
whose publication state is `published`. `dist/preview/` contains current public candidates for CI
artifacts, while `dist/dev/` contains all non-withdrawn packs in self-contained trees. Pages
uploads only `dist/public/`. With no published release, all root marketplaces are empty and the
Pages artifact contains no installer or remote skill catalog.

Published Pages cards use `interface.short-description`, while Codex also receives the full pack
description and the authored starter prompts. A published card links the release tag, exact source
commit, checksum asset, and repository attestation-verification surface.

## Claude Code

Published entries use a Git `git-subdir` source with the derived release tag and exact released
SHA. Development and preview marketplaces use contained `./plugins/<pack-id>` sources, so no
relative path escapes its generated channel root.

## Codex

The root Codex marketplace uses the same published-only policy but Codex-specific marketplace
metadata. Each pack has `.codex-plugin/plugin.json`; the `skills` field points to `./skills/`.

The marketplace declares installation availability and the required authentication policy.
These entries use `ON_INSTALL`, matching the documented Git-backed marketplace example. The
skill-only packs define no connector, MCP server, credential field, or external account, so
installation does not grant the skill content any credential by itself.

## Direct and OpenCode installs

Generated Bash and PowerShell scripts are optional adapters for GitHub CLI's public-preview
`gh skill` interface. They install every skill explicitly by exact path. Exact paths avoid a
repository-wide discovery traversal and prevent another pack from being selected. Claude and
Codex local plugin marketplaces remain the primary package installation flow; generated
OpenCode HTTP catalogs do not depend on GitHub CLI.

The installer accepts:

- Repository override.
- Agent target.
- User or project scope.
- Ref/SHA override.
- `--force`/`-Force`.
- `--dry-run`/`-DryRun`.

For a published pack, the default direct-installer pin is the exact latest-release source SHA;
marketplace metadata separately retains the pack-specific tag. An unpublished release candidate
has no public default install claim: use dry-run and explicit repository/ref overrides only in a
controlled fixture. A dry run validates arguments and prints exact commands without finding or
probing `gh`.

Before a real install, each adapter distinguishes a missing `gh` executable from an installed
version that lacks `gh skill` or `gh skill install`. It probes `gh skill --help` and
`gh skill install --help` once before writing anything; capability results, rather than a
parsed version number, control availability because the interface remains preview-only. An
unavailable command is not a failed primary installation path and is never compatibility
evidence.

Every probe and install invocation uses `GH_TELEMETRY=false`, `GH_PROMPT_DISABLED=1`, and
`GH_NO_UPDATE_NOTIFIER=1`. Bash scopes the values to each invocation. PowerShell snapshots the
presence and value of all three process variables and restores or removes them in `finally`.
These controls cover the documented GitHub CLI behavior only; they do not claim broader
telemetry or network isolation. The installers neither change authentication/configuration
variables nor install or upgrade GitHub CLI, and they never run skill helper scripts.

## OpenCode HTTP catalogs

Each pack generates:

```text
dist/<channel>/opencode/<language>/<subject>/
├── index.json
└── <skill-name>/
    ├── SKILL.md
    ├── references/
    ├── assets/
    └── scripts/
```

The literal `SKILL.md` is a generated copy of canonical content. Every index entry lists that
exact filename followed by its runtime resources; only `name`, `version`, and `files` are emitted.
Evals are not shipped. Increment a public pack version whenever remotely cached content changes.

The `pages.yml` workflow publishes only `dist/public/` from `main`. Configure released OpenCode
v1.18.3 or newer with this canonical shape:

```jsonc
{
  "skills": {
    "urls": [
      "https://genaptic.github.io/skillsets/opencode/python/best-practices/"
    ]
  }
}
```

The HTTP protocol is pinned in tests to OpenCode v1.18.3 commit
`127bdb30784d508cc556c71a0f32b508a3061517`. Structural conformance is not native compatibility;
the exact released client still needs a fresh exact-SHA canary report. See `docs/github-pages.md`.

## Local development

Use the self-contained `dist/dev/claude` and `dist/dev/codex` marketplaces for local adapter
testing. Candidate previews under `dist/preview/` are CI artifacts and never Pages content.

Current Codex CLI commands for a configured published marketplace are explicit:

```bash
codex plugin marketplace upgrade genaptic-skillsets
codex plugin remove PACK_ID@genaptic-skillsets
codex plugin add PACK_ID@genaptic-skillsets
```

Codex has no separate plugin-update subcommand; refresh the marketplace and reinstall the
plugin. Remove a plugin with `codex plugin remove PACK_ID@genaptic-skillsets`, and remove the
marketplace itself with `codex plugin marketplace remove genaptic-skillsets`.

## Updates and removals

Never reuse a released tag. Publish a new pack version. For a renamed or removed skill:

1. Add a major-version changelog and migration guide.
2. Keep the old identifier during a deprecation period when possible.
3. Add marketplace rename/removal metadata when the client supports it.
4. Add negative routing evals to prevent both old and new skills from competing.
5. Test clean install and update paths.
