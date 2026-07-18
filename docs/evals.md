# Evaluation design

## Purpose

Evals are executable specifications for routing and expected behavior. They are not a single
score and do not prove universal model behavior.

Each skill stores `evals/evals.json`. Structural CI validates coverage, identifiers,
assertions, forbidden behavior, and overlap expectations. The runner exports the complete
cases for protected/manual execution. A structural pass is not model-backed evidence.

## Routing suite

Every suite contains:

- `explicit-positive` — names the task or skill directly.
- Two `implicit-positive` cases — describes the need without naming it.
- `contextual-positive` — activation depends on an artifact or surrounding work.
- Two negative cases — plausible language that should not route here.
- `overlap` — a nearby task that should route to a named neighboring skill.

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

The runner checks suite quality and emits a complete prompt manifest containing prompts,
assertions, forbidden behaviors, and overlap expectations. It does not call an external
model or claim that a client/model passed. JSON output must validate against the eval-report
schema before it is used by a protected/manual runner.

## Recording client-backed evals

Use the compatibility-report schema as the machine-readable contract and
`compatibility/report-template.md` for reviewer narrative. Record:

- Client and version.
- Model identifier when visible.
- Pack tag and full SHA.
- Date and clean-environment description.
- Each case result and reviewer notes.
- Permission prompts, commands, network calls, and file changes.
- False positives, false negatives, and behavioral defects.

Pull requests run the structural suite without credentials. Protected release evidence must
exercise the declared cases on Claude Code, Codex, and OpenCode against the exact source SHA
and record an explicit reviewer verdict.

Treat routing failure, wrong-skill selection, missing verification, hidden dependency
assumptions, and unexpected mutation as distinct bug classes.

## Maintaining evals

A bug fix should add a regression case. A description change should be reviewed against all
overlapping skills. New behavior assertions must not force one implementation when multiple
safe implementations satisfy the contract.
