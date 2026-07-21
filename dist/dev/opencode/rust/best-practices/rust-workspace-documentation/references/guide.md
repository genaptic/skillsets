# Rust workspace documentation reconciliation guide

Use this guide after reading the skill instructions. Adapt the inventory and checks to the target
repository; filenames below are document roles, not required names.

## Contents

- [Establish authority](#establish-authority)
- [Build the inventory](#build-the-inventory)
- [Trace claims](#trace-claims)
- [Preview the change](#preview-the-change)
- [Edit by ownership](#edit-by-ownership)
- [Validate and report](#validate-and-report)

## Establish authority

1. Read all applicable repository instruction files from broadest to narrowest scope.
2. Identify the requested change set. Prefer the user's explicit scope, an available diff, or a
   locally resolvable comparison reference. If none exists, audit the current tree and say so.
3. Inventory Cargo manifests, toolchain files, configuration, workflows, command entry points,
   tests, and generated help that can prove documentation claims.
4. Treat running code, checked-in configuration, and executable tests as stronger evidence than
   prose. A document may describe intent, but it cannot make an absent behavior true.
5. Record network and tool availability before relying on external freshness or command execution.

Do not assume a default branch, workspace member count, crate name, binary name, feature set,
lockfile policy, or validation command.

## Build the inventory

Use repository-native search tools when available. A conservative Markdown inventory is:

```bash
rg --hidden --files -g '*.md' -g '!.git/**' | sort
```

Also locate manifests, instructions, and workflows:

```bash
rg --hidden --files -g 'Cargo.toml' -g 'rust-toolchain*' -g 'AGENTS.md' \
  -g '.cargo/config*' -g '.github/workflows/*.yml' -g '.github/workflows/*.yaml' | sort
```

Classify documents by audience and owner. Typical roles include product overview, architecture,
contributor workflow, operational runbook, command reference, testing guide, security guidance,
agent instructions, and historical record. See [Document roles](document-roles.md).

Create an internal table with:

| Document | Audience | Canonical facts | Evidence | Expected action |
|---|---|---|---|---|
| product overview | users | purpose, supported path | binary help, manifests | update summary |
| architecture | maintainers | crate/module ownership | manifests, source | revise ownership |
| contributor guide | contributors | checks and workflow | CI, task runner | align commands |
| agent instructions | coding agents | operational constraints | policies, tooling | narrow directives |

Include a no-op action when evidence already matches.

## Trace claims

For each potentially stale claim:

1. Extract the exact assertion: a name, path, command, module owner, version, side effect, or policy.
2. Locate the implementation or configuration that governs it.
3. Check tests or generated help when they expose the user-visible contract.
4. Use a primary external source only for language, Cargo, client, or specification behavior not
   owned by the repository.
5. Mark the claim as confirmed, stale, ambiguous, historical, or externally unverified.

Never use a stale document to corroborate another stale document. Do not run a command solely
because old prose says to; confirm its flags against current manifests, configuration, or CI first.

## Preview the change

Before a coordinated rewrite, present or record a concise preview:

- documents to change and their owning facts;
- evidence for each change;
- summaries or links that consume the owning fact;
- documents inspected but intentionally unchanged;
- generated or historical documents excluded from manual edits;
- commands, network requests, and writes that validation would require.

Keep the preview stable long enough for review. If the underlying diff or source changes materially,
reinspect rather than applying a stale plan.

## Edit by ownership

1. Update the canonical owner of each fact.
2. Replace duplicate detail in consumers with a summary and link where practical.
3. Keep product docs outcome-oriented, architecture docs structural, contributor docs procedural,
   runbooks operational, and agent instructions imperative and scoped.
4. Preserve existing heading conventions and stable anchors unless a rename is necessary.
5. Update examples and expected output together with the behavior they demonstrate.
6. Keep generated sections generated. Change their source or generator only when authorized.
7. Do not rewrite unrelated prose merely to impose a different style.

When both Markdown and public rustdoc need work, keep the inventories and validation evidence
separate even if the user authorizes one combined change.

## Validate and report

Validate at three levels:

1. **Structural:** local links, referenced paths, Markdown syntax, generated-state checks, and
   repository-specific documentation tooling.
2. **Behavioral:** command help, examples, configuration descriptions, and workflow claims against
   the current program or tests.
3. **Repository gates:** only the formatting, lint, docs, and tests selected by repository evidence.

Cargo flags are not universally composable. Determine whether the project uses a lockfile,
workspace-wide checks, feature matrices, target-specific code, or custom task runners before
choosing commands.

Finish with a diff review for:

- accidental formatting churn;
- obsolete identifiers or paths;
- contradictions between owner and consumer documents;
- absolute local paths, credentials, or private environment details;
- fixed dates masquerading as perpetual freshness;
- claims of commands or native clients that did not run.

Report the scope, evidence, changed ownership, exact validation results, no-op findings, and remaining
uncertainty. A failed or unavailable check is evidence to report, not a reason to invent success.
