# ADR 0001: Monorepo with generated client adapters

- Status: Accepted
- Date: 2026-07-17

## Context

The same skills must be installable in Claude Code, Codex, and OpenCode. Each client has
different package or catalog metadata, while all consume a `SKILL.md`-centered skill model.
Maintaining client-specific copies would invite drift.

## Decision

Keep one canonical skill tree per pack. Treat each language/subject as an independent
skillpack. Generate client manifests, marketplaces, installers, and HTTP catalogs from
`repository.yaml` and `skillpack.yaml`.

## Consequences

Positive:

- One reviewed source for behavior.
- Global naming and overlap checks.
- Independent pack versions in one marketplace.
- Client adapters can evolve without rewriting skills.

Negative:

- Generator correctness becomes supply-chain-sensitive.
- Independent tags require mandatory pinning for direct installs.
- Generated trees increase repository size.
- Client smoke tests remain necessary because schemas cannot prove runtime compatibility.

## Alternatives rejected

- Separate repository per pack: stronger release isolation but high governance and tooling
  duplication.
- Canonical copies in each client directory: simple initially but unsafe drift.
- One giant pack: easy install but weak routing and excessive context.
- Custom package manager: unnecessary before native distribution paths are exhausted.
