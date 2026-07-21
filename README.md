# Genaptic Skillsets

Genaptic Skillsets authors portable Agent Skills once, groups them into independently
versioned packs, and generates adapters for Claude Code, Codex, and OpenCode. Canonical skill
content lives only under `packs/**/skills/`; generated client surfaces are checked for drift.

## Published packs

<!-- BEGIN GENERATED PACK CATALOG -->
**No stable releases are currently published.** Public installation commands will appear here after an immutable release is reconciled.
<!-- END GENERATED PACK CATALOG -->
Only published packs appear above. Candidate previews and repository-maintainer tooling are
excluded from public catalogs, installers, and Pages. See [distribution](docs/distribution.md)
for the public, preview, and development boundaries.

## Contributor setup

Use Python 3.11 or newer and an already-installed Rust toolchain compatible with the repository.
Activation is optional; the bootstrap resolves the platform-specific virtual-environment
interpreter and installs only hash-locked dependencies.

```bash
python tools/bootstrap
make generate
make check
```

`make generate` is the explicit derived-file write step. `make check` is non-mutating and is
required before merge or release. Windows contributors can use `scripts/bootstrap.ps1` and
`scripts/check.ps1`; the installed `skillpacks` CLI exposes the same checks.

Maintainer-only authoring workflows are documented in [authoring](docs/authoring.md) and the
[`genaptic-skillsets-development`](packs/shared/genaptic-skillsets-development/README.md) pack.

## Documentation

- [Architecture and canonical-source rules](docs/architecture.md)
- [Skill and skillpack authoring](docs/authoring.md)
- [Routing and behavior evaluations](docs/evals.md)
- [Distribution channels and client adapters](docs/distribution.md)
- [Compatibility evidence](compatibility/README.md)
- [Release process](docs/release-process.md)
- [Draft release recovery](docs/release-recovery.md)
- [Publication reconciliation](docs/publication-reconciliation.md)
- [Maintainer signing](docs/maintainer-signing.md)
- [Threat model](docs/threat-model.md)
- [Contributor instructions](CONTRIBUTING.md)

## Security and license

Report vulnerabilities only through GitHub private vulnerability reporting; do not disclose
them in public issues or Discussions. See [SECURITY.md](SECURITY.md).

Licensed under Apache-2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
