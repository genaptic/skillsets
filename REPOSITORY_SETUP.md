# Repository setup checklist

The local worktree is configured as Genaptic Skillsets. Complete the remote portions of this
checklist in the separate publication plan; this setup does not push, publish, tag, release,
enable Pages, or change GitHub settings.

## Identity

```bash
make bootstrap
.venv/bin/python tools/configure-repository \
  --project-name "Genaptic Skillsets" \
  --project-description "Portable, versioned Agent Skill packs for Claude Code, Codex, and OpenCode." \
  --owner genaptic \
  --repository skillsets \
  --default-branch main \
  --publisher-name Genaptic \
  --copyright-owner Genaptic \
  --maintainer-name "Connor Sanders" \
  --maintainer-github jecsand838 \
  --security-channel github-private-vulnerability-reporting \
  --marketplace-name genaptic-skillsets \
  --marketplace-display-name "Genaptic Skillsets" \
  --marketplace-description "Portable, versioned Agent Skill packs for Claude Code, Codex, and OpenCode." \
  --license Apache-2.0 \
  --initial-year 2026
.venv/bin/python tools/generate-all
```

Review `repository.yaml`, `NOTICE`, `CITATION.cff`, root marketplaces, and generated
installers. Run the command a second time and confirm it makes no changes. PostgreSQL values
in `.env.example` must remain intact.

The default branch must use the repository's portable Git subset: 1–100 ASCII letters, digits,
periods, underscores, slashes, or hyphens. Names such as `main`, `release/v2`, and
`feature/foo-bar_1.2` are valid. Leading dots, dashes, or slashes; trailing dots or slashes;
`HEAD`; doubled dots or slashes; dot-leading path components; and components ending in `.lock`
are rejected before any configuration file is changed.

## GitHub settings

- Set the default branch to `main`.
- Enable private vulnerability reporting.
- Enable secret scanning and push protection.
- Enable code scanning where available.
- Enable Dependabot security updates.
- Require pull requests and dismiss stale approvals after new commits.
- Require `validate`, `eval`, `tests`, and `compatibility-structure` checks.
- Require CODEOWNERS review for workflows, installers, marketplaces, release tooling, and
  pack-owned paths.
- Block force pushes and branch deletion.
- Protect release tags matching `*-v*`.
- Restrict release workflow approval to maintainers.
- Prefer signed commits and signed tags for maintainers.
- Keep Actions permissions read-only by default; grant release write access only to the
  release workflow.
- Use GitHub-hosted ephemeral runners for pull requests from forks.

## Repository features

Enable Issues and, optionally, Discussions. Configure issue forms. Add repository topics such
as `agent-skills`, `claude-code`, `codex`, `opencode`, `python`, and `postgresql`.

## Release preparation

1. Replace all placeholders found by `python3 tools/validate-repository --strict-placeholders`.
2. Run `make generate`, then the non-mutating `make check`.
3. Run protected native-client and model-backed tests for Claude Code, Codex, and OpenCode;
   commit redacted, schema-valid reports for the exact source SHA.
4. Review the pack changelog and version and remove release-candidate wording.
5. Rehearse deterministically with `python3 tools/release-pack PACK_ID --draft`.
6. Complete the remote-publication plan: signed tag, protected workflow, release assets,
   Pages/OpenCode hosting, and repository protections.
7. Record the released SHA as `source-sha`, regenerate published `git-subdir` sources, and
   verify marketplace install, update, and removal from the public tag.
