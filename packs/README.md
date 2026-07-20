# Skillpacks

`packs/<language>/<subject>/` is the canonical source layout. Every materialized subject is
an independently versioned, installable pack. Each pack contains:

- `skillpack.yaml`: canonical pack metadata.
- `skills/<globally-unique-name>/SKILL.md`: portable Agent Skill instructions.
- Focused references, examples, optional standard-library helpers, and evals beside each skill.
- Generated Claude Code and Codex manifests.
- A pack README, changelog, and offline compatibility fixture.

The initial reusable release-candidate set intentionally contains five complete public packs:

- `python/best-practices`
- `python/cli-apps`
- `rust/best-practices`
- `rust/cli-apps`
- `shared/postgres-databases`

Repository maintainers also use the private, unpublished
`shared/genaptic-skillsets-development` pack. It is generated only into development surfaces and
cannot enter a formal public release.

Do not add empty language or subject placeholders. Start from `templates/skillpack/`, author
one or more focused skills, add routing and behavior evals, and run the repository checks.
Use `$genaptic-skillsets-create-skill` for one new skill in an existing pack and
`$genaptic-skillsets-create-skillpack` for a new installation/release boundary or coordinated
skill list.
Client-specific installation copies are generated under `dist/`; never duplicate canonical
skills under `.claude/skills`, `.agents/skills`, or `.opencode/skills` in source control.

A manifest version is not a publication claim. Working `version` and `maturity` mirror into each
skill; `publication.latest-release` separately records the last immutable public version, exact
source SHA, release ID, and timestamp. `publication.state: unpublished` forbids that snapshot.
Public installation appears only after post-release publication reconciliation, while a newer
candidate can continue development without changing the last public snapshot.
