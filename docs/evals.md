# Evaluation design

## Purpose

Evals are executable specifications for routing and expected behavior. They are not a single
score and do not prove universal model behavior.

Each skill stores `evals/evals.json`. The repository-wide
`evals/routing-boundaries.json` declares the reviewed neighbor graph once. Structural CI
validates coverage, identifiers, assertions, forbidden behavior, and all four outcomes at
each boundary. The runner exports the complete cases for protected/manual execution. A
structural pass is not model-backed evidence.

## Routing suite

Every suite contains:

- `explicit-positive` — names the task or skill directly.
- Two `implicit-positive` cases — describes the need without naming it.
- `contextual-positive` — activation depends on an artifact or surrounding work.
- Two negative cases — plausible language that should not route here.

Neighbor comparisons do not live in per-skill suites. They use the shared boundary matrix so
both sides see the exact same prompts and can express one skill, both skills, or neither.

A case declares:

```json
{
  "id": "implicit-positive-missing-src-layout",
  "kind": "implicit-positive",
  "prompt": "Our editable install imports files from the checkout root...",
  "shouldTrigger": true,
  "reason": "The task is package layout and import isolation."
}
```

Negative cases should be hard, not random. “Write a poem” gives little evidence about a
Python testing skill. Prefer a realistic near-neighbor such as test design versus test
execution debugging.

## Reviewed routing-boundary matrix

<!-- BEGIN GENERATED ROUTING BOUNDARY MATRIX -->
This table is generated from `evals/routing-boundaries.json`. `A` and `B` follow the
lexicographically sorted skill IDs in each boundary.

| Boundary | Shared vocabulary | A only | B only | Both | Neither |
|---|---|---|---|---|---|
| `genaptic-skillsets-create-skill-vs-genaptic-skillsets-create-skillpack`<br>A: `$genaptic-skillsets-create-skill`<br>B: `$genaptic-skillsets-create-skillpack` | `authoring request`, `skill boundary`, `skillpack` | `$genaptic-skillsets-create-skill` | `$genaptic-skillsets-create-skillpack` | both | none |
| `postgres-backup-recovery-vs-postgres-migration-safety`<br>A: `$postgres-backup-recovery`<br>B: `$postgres-migration-safety` | `recovery`, `rollback`, `runbook` | `$postgres-backup-recovery` | `$postgres-migration-safety` | both | none |
| `postgres-index-design-vs-postgres-migration-safety`<br>A: `$postgres-index-design`<br>B: `$postgres-migration-safety` | `index`, `locking`, `production change` | `$postgres-index-design` | `$postgres-migration-safety` | both | none |
| `postgres-index-design-vs-postgres-query-performance-review`<br>A: `$postgres-index-design`<br>B: `$postgres-query-performance-review` | `execution plan`, `index`, `query latency` | `$postgres-index-design` | `$postgres-query-performance-review` | both | none |
| `postgres-migration-safety-vs-postgres-schema-review`<br>A: `$postgres-migration-safety`<br>B: `$postgres-schema-review` | `constraints`, `existing schema`, `production rollout` | `$postgres-migration-safety` | `$postgres-schema-review` | both | none |
| `postgres-schema-design-vs-postgres-schema-review`<br>A: `$postgres-schema-design`<br>B: `$postgres-schema-review` | `constraints`, `data model`, `schema` | `$postgres-schema-design` | `$postgres-schema-review` | both | none |
| `python-cli-command-design-vs-python-cli-error-output`<br>A: `$python-cli-command-design`<br>B: `$python-cli-error-output` | `command contract`, `exit status`, `user interface` | `$python-cli-command-design` | `$python-cli-error-output` | both | none |
| `python-cli-error-output-vs-python-error-handling`<br>A: `$python-cli-error-output`<br>B: `$python-error-handling` | `exceptions`, `failure contract`, `logging` | `$python-cli-error-output` | `$python-error-handling` | both | none |
| `python-cli-testing-vs-python-testing-strategy`<br>A: `$python-cli-testing`<br>B: `$python-testing-strategy` | `fixtures`, `integration tests`, `test matrix` | `$python-cli-testing` | `$python-testing-strategy` | both | none |
| `python-project-layout-vs-python-testing-strategy`<br>A: `$python-project-layout`<br>B: `$python-testing-strategy` | `package boundaries`, `repository layout`, `test placement` | `$python-project-layout` | `$python-testing-strategy` | both | none |
| `rust-abstraction-design-vs-rust-code-structure`<br>A: `$rust-abstraction-design`<br>B: `$rust-code-structure` | `error types`, `ownership`, `type design` | `$rust-abstraction-design` | `$rust-code-structure` | both | none |
| `rust-abstraction-design-vs-rust-project-architecture`<br>A: `$rust-abstraction-design`<br>B: `$rust-project-architecture` | `dependency direction`, `public api`, `runtime selection` | `$rust-abstraction-design` | `$rust-project-architecture` | both | none |
| `rust-async-concurrency-vs-rust-networking`<br>A: `$rust-async-concurrency`<br>B: `$rust-networking` | `cancellation`, `retries`, `timeouts` | `$rust-async-concurrency` | `$rust-networking` | both | none |
| `rust-cli-application-design-vs-rust-cli-command-development`<br>A: `$rust-cli-application-design`<br>B: `$rust-cli-command-development` | `command grammar`, `dispatch`, `output contract` | `$rust-cli-application-design` | `$rust-cli-command-development` | both | none |
| `rust-core-best-practices-vs-rust-project-architecture`<br>A: `$rust-core-best-practices`<br>B: `$rust-project-architecture` | `crate boundaries`, `idiomatic rust`, `repository policy` | `$rust-core-best-practices` | `$rust-project-architecture` | both | none |
| `rust-dependency-portability-vs-rust-project-architecture`<br>A: `$rust-dependency-portability`<br>B: `$rust-project-architecture` | `crate ownership`, `dependencies`, `platform support` | `$rust-dependency-portability` | `$rust-project-architecture` | both | none |
| `rust-testing-strategy-vs-rustdoc-maintenance`<br>A: `$rust-testing-strategy`<br>B: `$rustdoc-maintenance` | `doctests`, `examples`, `verification` | `$rust-testing-strategy` | `$rustdoc-maintenance` | both | none |
| `rust-workspace-documentation-vs-rustdoc-maintenance`<br>A: `$rust-workspace-documentation`<br>B: `$rustdoc-maintenance` | `documentation drift`, `examples`, `rust workspace` | `$rust-workspace-documentation` | `$rustdoc-maintenance` | both | none |

The 18 reviewed boundaries contain 72 cases: exactly one A-only, B-only, both, and neither prompt per boundary.
<!-- END GENERATED ROUTING BOUNDARY MATRIX -->
Each canonical boundary has stable IDs, two sorted skill IDs, shared vocabulary, an explanation
for every outcome, and exactly four prompts. `expectedSkills` is empty for neither, contains one
skill for an exclusive outcome, and contains both sorted skills for a combined outcome. The
validator rejects unknown or duplicate relationships, mismatched expected selections,
undeclared legacy overlap cases, and public skills orphaned from the reviewed graph. It does not
generate unrelated all-pairs tests.

## Behavior suite

Behavior cases specify observable requirements:

```json
{
  "id": "end-to-end-layout-review",
  "kind": "end-to-end",
  "prompt": "Review this repository layout...",
  "assertions": [
    "Inspects pyproject.toml and package discovery",
    "Separates observed facts from recommendations",
    "Includes verification commands"
  ],
  "forbidden": [
    "Deletes or moves files without approval",
    "Claims an editable install passed without running it"
  ]
}
```

Assertions should be semantic and reviewable. Do not require exact prose unless the output is
a machine format.

## Running structural evals

```bash
python3 tools/run-evals
python3 tools/run-evals --skill python-project-layout
python3 tools/run-evals --json eval-report.json
```

The runner checks suite quality and emits a complete prompt manifest containing per-skill
prompts, assertions, forbidden behaviors, and the applicable boundary matrices. It does not
call an external model or claim that a client/model passed. JSON output must validate against
the eval-report schema before it is used by a protected/manual runner.

## Recording client-backed evals

Use the compatibility-report schema as the machine-readable contract and
`compatibility/report-template.md` for reviewer narrative. Record:

- Client and version.
- Model identifier when visible.
- Pack tag and full SHA.
- Date and clean-environment description.
- Each case result and reviewer notes.
- For every boundary incident to the selected pack, its internal- or cross-pack scope, exact
  canonical skill pair, installed owning packs, expected selection, and observed zero-, one-,
  or two-skill selection. Cross-pack cases use a separate clean multi-pack run.
- Permission prompts, commands, network calls, and file changes.
- False positives, false negatives, and behavioral defects.

The report contract is schema version 2. Record `testedAt` as second-precision canonical UTC
(`YYYY-MM-DDTHH:MM:SSZ`) and identify the reviewer with both GitHub login and immutable numeric
GitHub user ID. `repository.yaml` defines the authorized reviewer set, maximum age, permitted
future clock skew, and whether review must be independent of pack maintainers. Evidence is
accepted only from an exact full evidence commit SHA under `compatibility/reports/`; ingestion
proves both that the evaluated source is an ancestor of that evidence commit and that the
evidence commit is an ancestor of protected dispatch-time `main`.

The protected ingestion artifact contains three files named `<client>.json`,
`<client>.envelope.json`, and `<client>.attestation.jsonl`. The first preserves the committed raw
report bytes. The second binds repository/workflow/run identity, actor identity, source and
evidence commits, report path and digest, client, pack, and tested time. The third is the GitHub
Actions Sigstore bundle attesting both JSON files. A release must recheck freshness and reviewer
policy and verify the bundle against the exact ingestion workflow identity; a successful
workflow conclusion alone is insufficient provenance.

Pull requests run the structural suite without credentials. Protected release evidence must
exercise the declared cases on Claude Code, Codex, and OpenCode against the exact source SHA
and record an explicit reviewer verdict.

Treat routing failure, wrong-skill selection, missing verification, hidden dependency
assumptions, and unexpected mutation as distinct bug classes.

## Maintaining evals

A bug fix should add a regression case. A description change should be reviewed against every
declared neighbor. New behavior assertions must not force one implementation when multiple safe
implementations satisfy the contract. Add a new pair only after reviewing its A-only, B-only,
both, and neither distinctions; do not generate an all-pairs graph.
