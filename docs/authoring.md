# Skill authoring guide

## Start with the routing contract

The frontmatter description is not marketing copy. It is the first-stage routing contract.
Write one compact paragraph that includes:

- The outcome the skill produces.
- Strong triggers: artifacts, tasks, or phrases.
- The boundary against neighboring skills.
- A clear “do not use” case.

Example:

```yaml
description: >
  Design or review failure behavior for Python command-line applications, including stderr,
  exit codes, exception mapping, and actionable messages. Use when implementing or auditing
  CLI failures. Do not use for HTTP API error schemas or general logging architecture.
```

Avoid “Helps with Python best practices.” It is broad, weakly observable, and competes with
every Python skill.

## Choose the authoring boundary

Use `$genaptic-skillsets-create-skill` when one focused public skill belongs in an existing
pack. Use `$genaptic-skillsets-create-skillpack` when the request needs a new installation and
release boundary, contains multiple coordinated skills, or has no coherent existing owner. A
one-skill pack is valid only when it has an independent distribution boundary and names an
existing neighboring skill that owns the closest excluded outcome.

Before scaffolding, normalize the request with the selected skill's bundled JSON Schema. Record
public identity, routing examples, nearest neighbors, expected output, success criteria, source
freshness, compatibility, and all four operation dimensions explicitly. For a new pack, its
operation envelope must equal the component-wise maximum of its declared skills.

Run the helper without `--apply` first. Review its repository-relative plan and digest, then
apply the unchanged plan with `--apply --plan-digest <sha256>`. The helper creates structure
only; complete the research, canonical content, evals, generation, validation, and final diff
review afterward.

## Portable metadata

Canonical `SKILL.md` frontmatter uses the portable intersection:

```yaml
---
name: globally-unique-skill-name
description: A routing contract that says what to use this skill for and when not to use it.
license: Apache-2.0
metadata:
  skillpack: "replace-with-pack-id"
  version: "0.1.0"
  maturity: "release-candidate"
---
```

Every `metadata` value must be a string. Put detailed runtime or client requirements in a
concise `Compatibility` section and in `skillpack.yaml`, not in a vendor-specific frontmatter
field.

Every skill also includes `agents/openai.yaml` with a human-readable display name, a 25–64
character short description, and a concise default prompt that explicitly invokes the skill
as `$globally-unique-skill-name`. Do not add icons, brand colors, MCP dependencies, or
invocation restrictions unless the skill actually requires and documents them.

## Write an operational `SKILL.md`

Use this sequence unless the task genuinely needs another structure:

1. **Outcome** — the observable result.
2. **Compatibility** — repository, runtime, and evidence limitations.
3. **Inputs** — information to inspect or ask for.
4. **Safety** — permissions, network, writes, and approval points.
5. **Procedure** — ordered, decision-oriented steps.
6. **Verification** — evidence required before claiming success.
7. **Output contract** — exactly what to return.
8. **Resources** — shallow links to references, assets, and optional helpers.

The frontmatter description always owns concise positive and negative routing clauses. Add
separate “Use this skill when” and “Do not use this skill when” sections only when the body needs
more boundary examples; they do not replace the description contract.

State uncertainty. When an input is missing, make a labeled assumption or request it only
when proceeding would be unsafe or materially misleading.

## Progressive disclosure

Keep the entry point concise enough to route and act. Put durable details in references:

- `guide.md` — rationale, decision tables, and patterns.
- `checklist.md` — review and completion checks.
- `sources.md` — primary sources, target versions, and review provenance.
- Additional focused references when the topic needs them.

Do not create chains such as `SKILL.md → guide.md → another.md → appendix.md`. Link important
resources directly from `SKILL.md` or `guide.md`.

## Procedure language

Prefer explicit verbs:

- Inspect
- Identify
- Compare
- Propose
- Apply after approval
- Verify
- Report

Avoid vague instructions such as “make it robust,” “follow best practices,” or “ensure
quality” without acceptance criteria.

Separate observation from mutation:

```text
Inspect → explain evidence → propose smallest change → obtain approval when needed →
apply → verify → report
```

For database skills, classify the environment and lock/write risk before suggesting an
executable command. For scripts, state whether the helper reads files, writes output,
executes another process, or uses the network.

For Rust skills, inspect `rust-toolchain*`, `Cargo.toml`, `Cargo.lock`, workspace membership,
features, targets, and CI before selecting commands. Honor the repository's MSRV and edition;
do not prescribe a universal `--workspace --all-targets --all-features --locked` invocation.
Repository policy also wins over stylistic heuristics: methods fit behavior with a natural
receiver, free functions remain valid for module-level or stateless algorithms, and type aliases
remain valid when a distinct runtime type is unnecessary.

## Output contracts

A useful output contract removes stylistic ambiguity. It can require:

- Context and assumptions.
- Findings ordered by severity.
- Proposed design or patch.
- Commands not executed.
- Verification performed and not performed.
- Remaining risks and rollback.

Never imply a command ran when it did not. Never call an untested proposal “verified.”

## Sources

Prefer primary specifications and official documentation. Record target versions and review
provenance, then revalidate version-sensitive guidance during release preparation.
Secondary sources may explain operational experience, but distinguish them from normative
behavior.

Rust assets must say whether they are complete copy-ready projects or adaptable snippets.
Complete projects include the manifests and files needed to compile under their documented
toolchain. Snippets identify their surrounding assumptions and are syntax-checked where
practical; they must not be presented as standalone verified projects.

Source citations belong in `references/sources.md`; skill text should link to the source file
when a claim is version-sensitive.

## Helper scripts

A helper earns its place when deterministic code is safer or more reliable than repeatedly
reconstructing an operation. Good examples are static inventory, JSON validation, report
summarization, and template generation.

`assets/` and `scripts/` are optional. Omit empty directories and boilerplate-only README
stubs. When a helper exists, document prerequisites and side effects in `SKILL.md`, its
docstring, and `--help`.

A helper must not:

- Install packages.
- Contact the network by default.
- Discover or print credentials.
- Modify inputs silently.
- Execute user-controlled commands without a conspicuous confirmation flag.
- treat heuristic output as a definitive diagnosis.

Every finding should explain its limitation.

## Review questions

Before submitting:

- Could this description activate for the wrong neighboring skill?
- Does the procedure require unavailable context or hidden assumptions?
- Are approval and rollback boundaries explicit?
- Can the verification detect a false success?
- Does a helper need less privilege?
- Are generated examples safe to paste?
- Are PostgreSQL recommendations conditioned on version and environment?
- Can the skill remain useful when optional tools are absent?
