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
dist/install/
dist/opencode/
```

Run `python3 tools/generate-all` after any manifest, identity, version, or skill-membership
change. Generation honors each pack's declared targets and removes stale target artifacts.
Do not hand-edit an adapter.

## Publication state

`source-sha` is the publication switch. When it is absent, root marketplaces use the
repository-local source string `./packs/<language>/<subject>` and `catalog.json` records:

```json
{"state": "unpublished", "sourceType": "repo-local"}
```

This is the correct state for local development and release candidates. It must not be
presented as a public installation source.

After a protected pack release succeeds, record its exact 40-character released SHA as
`source-sha` and regenerate. The marketplace source becomes `git-subdir`, pinned by the
pack-specific tag and full SHA, and the catalog state becomes `published`. Never add a SHA
before the corresponding release exists.

## Claude Code

In the unpublished state, the root Claude marketplace resolves each pack locally. The pack
directory is the plugin root, with `.claude-plugin/plugin.json` and `skills/` as siblings.

Published entries use a Git `git-subdir` source with the pack-specific release tag and exact
released SHA. Public add/install/update/uninstall commands are generated only for that state.

## Codex

The root Codex marketplace uses the same local-versus-published source policy but
Codex-specific marketplace metadata. Each pack has `.codex-plugin/plugin.json`; the `skills`
field points to `./skills/`.

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

For a published pack, the default direct-installer pin is the exact released `source-sha`;
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
dist/opencode/<language>/<subject>/
├── index.json
└── <skill-name>/
    ├── <skill-name>.md
    ├── references/
    ├── assets/
    └── scripts/
```

The named Markdown file is a generated copy of canonical `SKILL.md`. Evals are not shipped in
the runtime catalog. Bump the pack version whenever shipped files change.

A static host such as GitHub Pages can expose the pack directory as the catalog base URL.
Hosting and URL activation are deferred to the remote-publication plan. After deployment,
the intended canonical shape is:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "skills": [
    "https://genaptic.github.io/skillsets/opencode/python/best-practices/"
  ]
}
```

Do not use or advertise this URL until it resolves to a directory containing `index.json`
and the hosted paths pass native OpenCode validation.

## Local development

Committed marketplaces remain repository-local while packs are unpublished. Test them from
the repository root so `./packs/<language>/<subject>` resolves correctly. A release
regeneration switches only the released pack to its pinned Git source.

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
