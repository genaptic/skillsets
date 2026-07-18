# Repository setup checklist

`main` is the default, deployment, and protected branch for Genaptic Skillsets. The repository
is maintained through squash pull requests; it does not use a separate deployment branch or a
merge queue. This file records the source-controlled contract and the remote settings that must
be read back after configuration.

## Identity

Identity is canonical in `repository.yaml`. Apply a deliberate identity change with:

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
make generate
make check
```

Review `repository.yaml`, the issue contact links, workflow branch guards, `NOTICE`,
`CITATION.cff`, root marketplaces, and generated installers. Run the configuration command a
second time and require an empty change list. PostgreSQL values in `.env.example` must remain
intact.

The default branch must use the repository's portable Git subset: 1–100 ASCII letters, digits,
periods, underscores, slashes, or hyphens. Names such as `main`, `release/v2`, and
`feature/foo-bar_1.2` are valid. Leading dots, dashes, or slashes; trailing dots or slashes;
`HEAD`; doubled dots or slashes; dot-leading path components; and components ending in `.lock`
are rejected before any configuration file is changed.

## Current publication state

The repository contains six independently versioned `1.0.0` release candidates:

- `python-best-practices`
- `python-cli-apps`
- `rust-best-practices`
- `rust-cli-apps`
- `postgres-databases`
- `repository-development`

They remain unpublished until each pack has passing Claude Code, Codex, and OpenCode reports
for its exact candidate SHA. Repository infrastructure setup must not create a pack tag, GitHub
release, native compatibility report, or compatibility claim.

## Required pull-request checks

The active `protect-main` ruleset requires a pull request, an up-to-date head branch, resolved
conversations, linear history, and these exact check contexts:

1. `repository contracts (Python 3.11)`
2. `repository contracts (Python 3.13)`
3. `Rust 1.85+ asset contracts`
4. `ShellCheck 0.9.0 and Actionlint 1.7.12`
5. `PSScriptAnalyzer 1.25.0`
6. `complete structural eval export`
7. `adapters and installers (ubuntu-24.04)`
8. `adapters and installers (macos-15)`
9. `adapters and installers (windows-2025)`
10. `codeql-python`
11. `DCO`
12. `dependency-review`

Required workflows instantiate on every pull request. Do not add pull-request path filters that
can leave one of these contexts pending. The contexts and GitHub Actions integration identity
must be copied from an observed protection-probe run, not guessed.

## GitHub repository settings

- Keep `main` as the default branch and use squash merging with the pull-request title and body.
  Disable merge commits and rebase merging. Enable auto-merge, update-branch, web signoff, and
  post-merge branch deletion.
- Require pull requests with zero approvals for the solo maintainer. Require current branches
  and resolved conversations; block force pushes and branch deletion. Do not enable a main-rule
  bypass or CODEOWNERS approval requirement while the project has one maintainer.
- Allow only GitHub-owned Actions pinned to full commit SHAs. Keep the default workflow token
  read-only, disallow workflow pull-request approval, require approval for every external fork
  contributor, use only GitHub-hosted runners, and retain ordinary artifacts and logs for 30
  days. Native compatibility evidence retains its explicit 90-day period.
- Enable Issues, Discussions, dependency graph, Dependabot alerts and security updates, private
  vulnerability reporting, secret scanning, push protection, and the supported additional
  validity and generic-pattern checks. Keep default CodeQL setup disabled because the advanced
  workflow is canonical.
- Keep the repository free of Actions and environment secrets, PATs, deploy keys, webhooks,
  self-hosted runners, and copied Claude, Codex, or OpenCode credentials.
- Protect `refs/tags/*-v*` from update, deletion, and non-fast-forward changes. The resolved
  organization-administrator role may always bypass the tag-creation restriction so the sole
  maintainer can create the initial signed annotated tag. Enable immutable releases before the
  first publication.

The `compatibility`, `release`, and `github-pages` environments are secret-free, restricted to
`main`, and disallow administrator bypass. Only `release` has a wait timer: five minutes.
See [solo-maintainer governance](docs/solo-maintainer-governance.md),
[maintainer signing](docs/maintainer-signing.md), and [GitHub Pages](docs/github-pages.md).

## Repository features and routing

Use private vulnerability reporting for security disclosures and Discussions Q&A for support,
design, and usage questions. Preserve the standard Announcements, Q&A, Ideas, General, and Show
and Tell discussion categories. Every current pack has an explicit CODEOWNERS path even though
the main ruleset does not require a CODEOWNERS approval.

The maintained labels are `bug`, `enhancement`, `compatibility`, `routing`, `proposal`,
`dependencies`, `python`, `rust`, `github-actions`, `security`, `release`, `breaking-change`,
`skill`, `skillpack`, `needs-eval`, `needs-research`, `blocked`, `good first issue`, and
`help wanted`. Remove surplus default labels only after confirming no issue depends on them.

The repository topics are `agent-skills`, `ai-agents`, `claude-code`, `codex`, `opencode`,
`developer-tools`, `python`, `rust`, `postgresql`, and `open-source`. Wiki, Projects, and
repository-template mode remain disabled. Set the homepage to
`https://genaptic.github.io/skillsets/` only after the first Pages deployment returns HTTP 200.

## Read-back audit

After any bootstrap or policy change, read the repository configuration back through the GitHub
API and audit the corresponding UI-only controls. Confirm metadata, merge policy, Actions
policy, security features, all three environments, Pages, both rulesets, labels, Discussions,
and immutable releases. Also confirm the absence of secrets, tags, releases, deploy keys,
webhooks, package publications, and native compatibility uploads. Save audit results as setup
evidence; do not add generated timestamps to distributable files.

The initial bootstrap has durable, non-release evidence:

- Pull request 1 merged the final `v0.0.1` head `f79901a` into `main` as `4db6d23`; both
  commits resolve to tree `801b67eba5f300403fc03ea2011253326ae97343`.
- Pull request 4 merged the signed infrastructure head `7c55d1a` as `75a1160`; both commits
  resolve to tree `420249e2d1b42e08e4935ed2a1cc18e6ed8fee53` after all twelve intended checks passed.
- Pages workflow run `29660802091` deployed merge `75a1160` through the `github-pages`
  environment. The landing page and all six OpenCode indexes returned HTTP 200.

These short hashes are identifiers for the immutable full commit and tree objects above; they
are not pack versions or release tags. Repeat the read-back audit after ruleset changes and
before every first publication from a pack release line.

Before the first pack release, follow [the release process](docs/release-process.md) and run the
local draft rehearsal twice. Byte-identical ZIPs and checksums prove only build determinism, not
native-client or model compatibility.
