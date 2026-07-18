# Guide: creating one skill in this repository

Use this guide for design rationale and edge cases. The ordered workflow remains in
`SKILL.md`.

## 1. Interpret the public API before writing files

A skill name, description, permission envelope, and output contract are public behavior.
Treat them as interface design rather than convenient prose.

### Required request model

| Field | Required | Meaning | Reject or clarify when |
|---|---:|---|---|
| `skillName` | yes | Resolved lowercase kebab-case public identity | A proposed normalization has not been approved |
| `details` | yes | Outcome, domain, artifacts, examples, quality bar | It describes only a topic, not an observable job |
| `scope` | yes | Positive, negative, operational, and environmental boundaries | It permits unsafe or contradictory behavior |
| `packId` and `expectedPackVersion` | yes | Existing owner and stale-request precondition | No existing pack coherently owns the work |
| `examples` and `nearestNeighbor` | yes | Positive, negative, and overlap evidence | Examples are generic or the neighbor is unresolved |
| `constraints` and `operations` | yes | Versions, tools, network, writes, commands, external effects | A material boundary is unknown |
| `sourceRequirements` | yes | Freshness and required primary authorities | Current claims cannot be verified or qualified |
| `openai` | yes | Display name, 25–64 character summary, prompt naming the skill | The interface does not match the routing contract |

Do not convert a vague topic such as “Kubernetes” into a broad skill. Identify a single
outcome such as “review Kubernetes rollout safety,” then name and route that job.

## 2. Research in two independent tracks

### Repository research

The repository is the authority for local shape and policy. Inspect:

1. Root instructions and contribution rules.
2. Architecture, authoring, eval, threat, compatibility, and versioning documentation.
3. Schemas and canonical templates.
4. Generator, validator, eval runner, and release entry points.
5. Target manifest, README, changelog, compatibility fixture, and every declared skill.
6. Neighboring packs and descriptions that could compete for the same prompts.
7. Existing tests and current generated state.
8. Working-tree changes that must be preserved.

A keyword search alone is insufficient. Read the source files that define the contract.

### Web research

Use current primary sources for:

- The open Agent Skills format and skill-description behavior.
- Claude Code, Codex, and OpenCode discovery or packaging behavior when relevant.
- The requested domain's normative specification, official documentation, supported
  versions, and security guidance.
- Tool or library behavior that can change over time.

For each source, record:

```text
Title | canonical URL | authority | relevant version/date | accessed date | decision informed
```

Prefer a specification or official manual over a blog. A secondary operational source may
supplement primary documentation, but label it as experience rather than normative truth.
Do not cite a search-result snippet as though it were the full source.

### Research stop condition

Research is sufficient when you can answer:

- What exact outcome belongs to this skill?
- Which prompts should and should not activate it?
- What version-sensitive facts shape the procedure?
- What can it read, write, execute, or send?
- How can success and false success be distinguished?
- Why does no existing skill already own the outcome?

## 3. Decide whether the unit is coherent

A coherent skill has one outcome and one dominant verification story. Split or route to
`create-new-skillset` when the proposed skill:

- Has independent outcomes that users request separately.
- Needs unrelated permission envelopes.
- Has multiple distinct neighboring skills.
- Requires a long list of conditional procedures most users will never need.
- Cannot be described without broad topic words such as “all,” “complete platform,” or
  “best practices” standing in for boundaries.

Do not split merely because the domain is complex. One workflow may legitimately need
several ordered steps when they all produce the same result.

## 4. Design the routing contract

The frontmatter description is loaded before the body and must do most routing work.
Front-load user intent and high-signal artifacts. Include:

1. Imperative or outcome language.
2. Strong task and artifact triggers.
3. `Use when` with realistic context.
4. `Do not use` with the closest neighboring result.

Check the description against a prompt matrix:

| Prompt class | Minimum | Purpose |
|---|---:|---|
| Explicit positive | 1 | Direct invocation and exact name |
| Implicit positive | 2 | Distinct phrasings and artifacts |
| Contextual positive | 1 | Activation from supplied project evidence |
| Near-neighbor negative | 2 | Shared vocabulary, different outcome |
| Overlap | 1 | Names the narrower preferred skill |

Avoid repeated synonyms that consume discovery context without improving discrimination.

## 5. Design permission and safety boundaries

Create an operation table before authoring:

| Capability | Default | Approval point | Verification | Rollback |
|---|---|---|---|---|
| Read project files | allowed in scope | none | list inspected paths | not applicable |
| Web research | official reads | before auth/private source | source log | not applicable |
| Write canonical files | preview first | before material/destructive change | diff + validator | version control |
| Execute local checks | existing toolchain only | before installs/elevation | exit code + output | environment-specific |
| External writes | prohibited | separate request | remote evidence | service-specific |

The skill must never hide network use inside a helper. Do not ask for credentials in prompt
text, command arguments, fixtures, or examples.

## 6. Choose supporting resources deliberately

### References

Use references for durable detail, decisions, and version-qualified facts. Keep links shallow.
A reader should not need to follow a chain of references to understand a required step.

### Assets

Use assets for templates or safe examples that improve consistency. Every asset must state
what users must adapt and must not include realistic secrets or production identifiers.

### Scripts

Include a script only when deterministic code is safer or more repeatable than regenerating
an operation in natural language. A helper must:

- Work with Python 3.11 and the standard library unless the pack explicitly declares more.
- Support `--help`.
- Default to inspection or preview.
- Refuse implicit overwrite.
- Validate paths and names.
- Avoid network and subprocess execution unless that behavior is conspicuous and approved.
- Return nonzero with actionable errors.
- Describe heuristic limitations.

The included scaffold helper intentionally creates structure and metadata only. It reads the
request, repository identity, target manifest, current compatibility inventory, and canonical
template; it previews repository-relative paths and preimage hashes without writing. Applying
requires the reviewed plan digest. The helper uses no network or subprocesses, and its
multi-file crash recovery is bounded. Research and final authoring remain agent
responsibilities.

## 7. Register source, then generate adapters

Canonical edits for one skill normally include:

```text
packs/<language>/<subject>/skillpack.yaml
packs/<language>/<subject>/README.md
packs/<language>/<subject>/CHANGELOG.md
packs/<language>/<subject>/tests/compatibility/expected-skills.json
packs/<language>/<subject>/skills/<skill-name>/...
```

Derived files are generated. Never directly repair a generated marketplace or catalog to
make validation pass. Change canonical source and rerun the generator.

## 8. Build evidence before calling it complete

Use four evidence layers:

1. **Structural:** schema, required files, links, names, safe script patterns.
2. **Routing:** positive, negative, contextual, and overlap eval specifications.
3. **Behavioral:** observable assertions and forbidden actions.
4. **Repository:** deterministic generation, full validation, tests, and clean diff review.

Optional client-backed evaluation should use fresh sessions and compare with-skill and
without-skill behavior. Structural evals alone do not prove a model will route correctly.

## 9. Common failure modes

### Writing before researching

Symptom: generic instructions, outdated commands, duplicate scope. Fix: complete the
project and source evidence tables first.

### Treating the template as content

Symptom: “State the observable result” survives in final files. Fix: scan for scaffold
phrases and placeholders before generation.

### Broad routing

Symptom: the new skill activates for every task in its domain. Fix: name the closest
negative and add hard near-neighbor evals.

### Duplicate canonical copies

Symptom: the same skill is committed under a pack and client-specific hidden directory.
Fix: keep the pack source canonical and perform any project-scope installation smoke test in
an isolated disposable repository.

### Unsafe helper ambition

Symptom: the helper installs tools, contacts services, or mutates many files to “automate”
authoring. Fix: limit it to deterministic preview-first scaffolding and let the agent perform
researched edits transparently.

### False verification

Symptom: a report says “all checks pass” from proposed commands. Fix: record exact commands,
exit status, and skipped checks separately.
