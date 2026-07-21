# Guide: creating a complete skillpack

Use this guide for decomposition and package-level decisions; follow the ordered procedure
in `SKILL.md` for execution.

## 1. Define an installation boundary, not a folder theme

A skillpack is justified when its skills form a useful package users may install, version,
and review together. Cohesion normally comes from:

- One language and subject, or one shared operational domain.
- A common audience and vocabulary.
- Related compatibility and permission expectations.
- A release lifecycle that makes sense as one package.
- Enough value when installed independently from other packs.

Do not create a package merely because several ideas were listed together. Conversely, do
not split a coherent workflow family into many tiny packs that users must install one by
one.

Skill count does not decide which authoring workflow owns a request. Use
`genaptic-skillsets-create-skill` when exactly one new public skill belongs in an existing
pack. Use `genaptic-skillsets-create-skillpack` whenever the requested result is a new
independently installable and versioned pack, including a coherent one-skill pack. For that
one-skill package, document the independent installation and release value and name the
nearest existing skill outside the proposed pack that owns the closest excluded outcome.

## 2. Required request model

The normalized request should contain:

```text
skillpackName
packId
displayName
language
subject
description
details
scope
version
targets
category
keywords
compatibility.runtimes and compatibility.notes
operations
sourceRequirements
skills[]:
  name
  details
  scope
  examples
  expectedOutput
  successCriteria
  nearestNeighbor
  constraints
  operations
  sourceRequirements
  openai
```

The conversation may begin with fewer fields, but every public identity, version, runtime,
target, routing, source, interface, and permission decision must be resolved before the
normalized request is validated or scaffolded. Label evidence used to propose a value and
obtain approval when it materially changes the requested API. Do not hide these decisions
behind helper defaults.

## 3. Map identity consistently

Use lowercase kebab-case. Normal conventions are:

| Language | Subject | Path | Public pack ID |
|---|---|---|---|
| `python` | `microservices` | `packs/python/microservices` | `python-microservices` |
| `typescript` | `docs` | `packs/typescript/docs` | `typescript-docs` |
| `shared` | `postgres-databases` | `packs/shared/postgres-databases` | `postgres-databases` |

Treat the public ID and skill names as stable API. A stylistic rename later may require a
major release and migration notes.

## 4. Research the whole repository before decomposition

Inventory every existing manifest, pack description, skill name, and skill description.
Read full neighboring skills when vocabulary or outcome overlaps. Check:

- Whether a requested skill already exists under another name.
- Whether one requested skill belongs in an existing pack.
- Whether the proposed pack duplicates an existing package boundary.
- Whether new names collide globally after normalization.
- Whether permissions or compatibility make the package misleadingly broad.
- Whether repository schema or tests assume a minimum or exact inventory.

Read current source rather than relying on the previous release, generated catalog, or
memory.

## 5. Research at two levels

### Package-level evidence

Research the common domain, supported clients, distribution behavior, shared security
model, and version scope. This evidence shapes pack description, compatibility, operations,
and install documentation.

### Skill-level evidence

Each skill needs sources specific enough to support its procedure, verification, and safety
limits. A single generic domain homepage is not sufficient for every skill in a pack.

Create a source coverage matrix:

| Skill | Normative source | Operational source | Security source | Version-sensitive decisions |
|---|---|---|---|---|
|  |  |  |  |  |

Use primary official documentation where available and record access dates.

## 6. Decompose with a boundary matrix

For each skill, define:

1. One observable outcome.
2. Realistic positive user intents and artifacts.
3. Closest negative outcomes.
4. Expected skills for the A-only, B-only, both, and neither boundary outcomes.
5. Minimum inputs.
6. Operational permissions and approval points.
7. Verification evidence.
8. Output contract.
9. Required references, assets, helper, and evals.

Then compare every pair of skills. A strong decomposition has low routing ambiguity and does
not require users to know internal implementation stages.

### Signals that two items should merge

- Users almost always request them together.
- They share one result and one verification path.
- Separating them creates circular references or incomplete outputs.
- The distinction is implementation detail rather than user intent.

### Signals that one item should split

- It has independent results users request separately.
- It mixes read-only review with high-impact mutation.
- Different environments or audiences need different instructions.
- Its description needs multiple unrelated trigger families.
- One procedure or reference dominates only a minority of uses.

### Signals an item belongs elsewhere

- An existing pack already owns its subject and audience.
- It requires a different release lifecycle or permission envelope.
- It would make this package's name or description misleading.

Never alter the user's detailed list silently. Present a change ledger with original item,
proposed change, evidence, impact, and approval state.

## 7. Aggregate operational metadata conservatively

A pack's `operations` summary must not understate any included skill. Aggregate to the most
permissive required value, then keep each skill's own safety posture precise.

Example:

| Skill | Network | Filesystem | Commands | External writes |
|---|---|---|---|---|
| review-a | none | read-only | optional-explicit | none |
| create-b | required | project-write | required | none |
| Pack | required | project-write | required | none |

A broad pack envelope does not grant automatic permission. Each procedure still requires
appropriate approval.

## 8. Author installed skills as self-contained units

Marketplace or direct installers may copy only the pack or an individual skill subtree.
Therefore:

- Keep a skill's critical procedure and references inside its directory.
- Do not depend on a root-only file for essential behavior without restating the necessary
  invariant.
- Do not use shared symlinks in this repository.
- Keep common terminology consistent, but avoid a hidden cross-skill execution dependency.
- Use shallow relative links and no path escapes.

Pack README content explains the collection; it does not replace skill instructions.

## 9. Design cross-skill evals

Every skill needs its own minimum routing and behavior suite. In addition, declare each likely
competitor pair once in the canonical root matrix:

```text
A-only prompt using shared vocabulary
B-only prompt using shared vocabulary
Both-skills prompt with two genuine deliverables
Neither-skill prompt that remains a realistic near neighbor
```

Review all descriptions in one view. Discovery budgets reward concise, distinct frontmatter.
A generic skill should not shadow a specialized one.

## 10. Scaffold only after design approval

The included helper validates the complete normalized request, identities, pack path,
operation aggregation, one-skill external-neighbor rule, OpenAI prompts, and existing
collisions, then previews or creates:

```text
skillpack.yaml
README.md
CHANGELOG.md
tests/compatibility/expected-skills.json
skills/<name>/... for every declared skill
```

Preview is byte-stable and read-only. Apply requires the reviewed plan digest, rechecks
preimages under an exclusive repository lock, and refuses stale or unsafe destinations. The
helper uses no network or subprocesses, and its multi-file crash recovery is bounded. It
intentionally does not:

- Browse or select sources.
- Decide whether the package is coherent.
- Rewrite the user's skill list.
- Author final skill content.
- Run generators, tests, clients, or release commands.

Those actions require agent judgment and transparent evidence.

## 11. Verify from narrow to broad

Recommended order:

1. Validate request and boundary matrix.
2. Compile or exercise each helper.
3. Run structural eval checks per new skill.
4. Generate all distribution artifacts.
5. Run repository validation with generated-state checking.
6. Run the full eval suite.
7. Run automated tests.
8. Review the complete diff and generated hash manifest.
9. Optionally run already-installed official format validators without publishing.
10. Optionally run client-backed tests in clean sessions.

A passing schema does not prove good routing, and a routed skill does not prove good
behavior. Report evidence layers separately.

## 12. Common failure modes

### False cohesion

Symptom: the pack name is broad and each skill targets a different audience. Fix: split by
installation value and release lifecycle.

### One catch-all skill plus thin satellites

Symptom: a “best practices” skill overlaps every specialized skill. Fix: remove the catch-all
or give it a distinct orchestration outcome and hard boundaries.

### Understated operations

Symptom: manifest says read-only while one skill creates files or runs commands. Fix:
aggregate conservatively and document per-skill approval.

### Shared root dependency

Symptom: installed skills link to root docs not present in their copied subtree. Fix: move
essential references into each skill.

### Mechanical completeness without research

Symptom: every file exists but contains generic advice and stale commands. Fix: require the
source coverage matrix and source-to-decision notes before final authoring.

### Hand-edited adapters

Symptom: marketplace entries pass locally but drift from manifests. Fix: modify canonical
source and regenerate.

### Unapproved list changes

Symptom: the final pack omits or renames user-requested skills without a decision record.
Fix: maintain a visible change ledger and obtain approval for material public changes.
