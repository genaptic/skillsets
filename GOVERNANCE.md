# Governance

## Project model

Genaptic Skillsets is maintainer-led and contribution-friendly. Maintainers are responsible
for safety, compatibility, release integrity, and coherent scope. Consensus is preferred,
but maintainers may make a documented decision when consensus is not practical.

## Roles

### Contributors

Anyone who submits issues, reviews, documentation, skills, tests, or tooling.

### Reviewers

Trusted contributors who can review in an area of demonstrated expertise. Review approval
does not imply merge authority.

### Maintainers

People with merge or release authority. Maintainers:

- Triage security and conduct reports.
- Protect public identifiers and compatibility contracts.
- Review sensitive paths.
- Manage releases and signing.
- Define supported clients and tooling.
- Resolve disputes and document significant decisions.

### Pack owners

Maintainers or reviewers listed in `CODEOWNERS` for a language/domain pack. They are expected
to understand that ecosystem and to review technical claims and operational hazards.

## Decision process

Routine changes use pull-request review. Significant decisions use an issue or an
architecture decision record under `docs/decisions/`, including context, alternatives,
tradeoffs, and consequences.

The following require explicit maintainer approval:

- New top-level pack or distribution target.
- Public identifier rename or removal.
- New network access, credential requirement, or external write behavior.
- Changes to release, installer, workflow, schema, or security machinery.
- License or governance changes.

## Becoming a reviewer or maintainer

Candidates should show sustained, constructive contributions; reliable reviews; sound
security judgment; and respect for project norms. Existing maintainers decide openly unless
privacy or security requires a private discussion.

## Inactivity and succession

Access may be reduced after extended inactivity to limit supply-chain risk, without
diminishing past credit. Returning contributors can regain access after renewed
participation. Maintainers should keep at least two people able to perform a release when the
community grows enough to support it.

## Conflicts of interest

Disclose financial, employment, or personal interests that could reasonably affect a
decision. Recusal is required when impartial review is not credible.

## Project changes and archival

A major governance change requires a public proposal and a reasonable comment period. If the
project is archived, maintainers should mark releases and marketplaces clearly, disable
unnecessary credentials, and document the last supported state.
