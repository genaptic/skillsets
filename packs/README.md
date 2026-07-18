# Skillpacks

`packs/<language>/<subject>/` is the canonical source layout. Every materialized subject is
an independently versioned, installable pack. Each pack contains:

- `skillpack.yaml`: canonical pack metadata.
- `skills/<globally-unique-name>/SKILL.md`: portable Agent Skill instructions.
- Focused references, examples, optional standard-library helpers, and evals beside each skill.
- Generated Claude Code and Codex manifests.
- A pack README, changelog, and offline compatibility fixture.

The initial release-candidate set intentionally contains six complete packs:

- `python/best-practices`
- `python/cli-apps`
- `rust/best-practices`
- `rust/cli-apps`
- `shared/postgres-databases`
- `shared/repository-development`

Do not add empty language or subject placeholders. Start from `templates/skillpack/`, author
one or more focused skills, add routing and behavior evals, and run the repository checks.
Use `$create-new-skill` for one new skill in an existing pack and `$create-new-skillset` for
a new installation/release boundary or coordinated skill list.
Client-specific installation copies are generated under `dist/`; never duplicate canonical
skills under `.claude/skills`, `.agents/skills`, or `.opencode/skills` in source control.

A manifest version is not a publication claim. Skill metadata remains `release-candidate`
until exact-SHA compatibility evidence passes. Separately, an absent `source-sha` means the
marketplace source is repository-local and `catalog.json` reports `unpublished`; that remains
true for the signed release commit until the post-release catalog update records its now-known
SHA. Public install instructions appear only after that update.
