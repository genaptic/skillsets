## Summary

Describe the user-visible change, affected packs/skills, and why it is needed.

## Change classification

- [ ] Canonical skill instructions or resources
- [ ] Routing or behavior evals
- [ ] Optional helper script
- [ ] Pack metadata, compatibility, or version
- [ ] Generator, schema, installer, marketplace, or release tooling
- [ ] CI, security, governance, or documentation only

## Skill routing contract

For every new or materially changed skill:

- [ ] The frontmatter description states what the skill does, **Use when**, and **Do not use**.
- [ ] The name is globally unique, stable, kebab-case, and matches the directory.
- [ ] Boundaries and overlaps with neighboring skills are explicit.
- [ ] Frontmatter uses only `name`, `description`, `license`, and string-valued `metadata`.
- [ ] `agents/openai.yaml` has a 25–64 character summary and a prompt naming `$skill-id`.
- [ ] At least one explicit, two implicit, one contextual, two negative, and one overlap
      routing case are present.
- [ ] At least two behavior cases are present, including one end-to-end case.

## Safety and operations

- [ ] Network access: none / optional / required — explain below.
- [ ] Filesystem writes: none / explicit output / project write / system write — explain below.
- [ ] Command execution: none / optional explicit / required — explain below.
- [ ] External writes or destructive effects: none / optional explicit / required — explain below.
- [ ] Helpers do not install dependencies, download code, execute during installation, expose
      secrets, or overwrite output by default.
- [ ] Genaptic Skillsets development scaffold helpers were previewed first and any apply used
      the unchanged reviewed plan digest.
- [ ] Any database, production, credential, privacy, or supply-chain risk is documented.

Safety notes:

## Evidence

- [ ] `make bootstrap` completed from the hashed dependency lock.
- [ ] `make generate` was run explicitly and the derived changes were reviewed.
- [ ] Non-mutating `make check` passed, including strict placeholders, lock freshness,
      deterministic generation, schemas, structural evals, lint, tests, and coverage.
- [ ] Optional helper happy/error paths were exercised.
- [ ] New request schemas, templates, and examples validate with URI format checking.
- [ ] Canonical skill inventory, OpenAI sidecars, compatibility inventory, and eval counts agree.
- [ ] No canonical copies were added under `.claude/skills`, `.agents/skills`, or
      `.opencode/skills`.
- [ ] Relevant primary sources and target versions were reviewed.
- [ ] Rust examples honor the target toolchain/MSRV and repository-declared Cargo policy;
      complete projects compile, snippets are labeled, and Rust assets pass the applicable
      formatting or syntax checks.
- [ ] Filesystem or recursive-delete examples have exact-target authorization, root/home/worktree
      refusal, containment and symlink policy, preview, confirmation, and adversarial tests.
- [ ] Any native-client or model-backed claim has a schema-valid dated report for the exact SHA;
      structural validation alone is not presented as compatibility evidence.

Commands and results:

## Release impact

- [ ] No version change required
- [ ] Patch
- [ ] Minor
- [ ] Major

Explain compatibility, migration, changelog, and rollback implications. Do not mark a client
as tested unless a dated compatibility report is included.
