# Single-command development guide

Use this guide for one command in an existing Rust CLI. The target repository's architecture is
authoritative; bundled patterns are adaptable and never require another skill at runtime.

## Contents

- [Discover the vertical slice](#discover-the-vertical-slice)
- [Specify the public contract](#specify-the-public-contract)
- [Preview the diff](#preview-the-diff)
- [Implement in layers](#implement-in-layers)
- [Document and generate](#document-and-generate)
- [Validate and report](#validate-and-report)

## Discover the vertical slice

Read repository instructions and locate:

1. Cargo manifests, toolchain/MSRV, binary target, dependency policy, and canonical checks.
2. Root parser plus the closest neighboring command's arguments and help.
3. Root and nested dispatch, runtime/context construction, sync/async behavior, and cancellation.
4. The domain operation or capability that should own reusable behavior.
5. Filesystem, network, config, subprocess, output, logging, and error adapters.
6. Parser, domain, integration, process, scenario, snapshot, and documentation tests.
7. User docs and generated help/completions/catalogs affected by grammar.

Search concepts rather than guessed filenames. Useful patterns include parser derives/builders,
command enums, `match`, `execute`, `dispatch`, `run`, context/service types, `ExitCode`, stdout/stderr,
and the neighboring command's public name.

Select the nearest existing command based on grammar and effects, not merely proximity in a file.
Record which conventions are deliberate and which are defects the new command must not copy.

## Specify the public contract

Write concrete examples before implementation:

```text
tool subject action REQUIRED [--option VALUE]
tool subject action --help
```

Define:

- command, subject, positionals, options, aliases, conflicts, defaults, and precedence;
- human and machine output, stdout/stderr ownership, newline/ordering, and schema stability;
- success and failure exit status;
- filesystem, network, config, subprocess, and external writes;
- idempotency, retries, timeout/cancellation, overwrite, and partial-failure behavior;
- compatibility/deprecation and docs/completion impact;
- success criteria and negative cases.

If several independent commands are required or no established CLI can own the change coherently,
stop and use the application-design workflow rather than hiding an architecture redesign in one task.

## Preview the diff

Preview a repository-relative change matrix:

| Layer | Existing neighbor | Intended change | Evidence/test |
|---|---|---|---|
| parser | discovered type | one new variant/option | parse/help tests |
| dispatch | discovered mechanism | exhaustive route | dispatch test |
| domain | owning API | typed request/result | domain tests |
| adapter | authorized effect | validated operation | adversarial tests |
| renderer | current mode | stable text/machine output | process tests |
| docs/generated | current owner | updated contract | generation/check |

Include dependency additions, migrations, destructive operations, live services, and unavailable tools.
For sensitive mutations, require review/approval according to repository and user policy. Recompute the
plan when source changes before application.

## Implement in layers

1. Add or change parser data with syntax validation only.
2. Extend the discovered dispatch mechanism exhaustively. Do not introduce a command trait or receiver
   pattern merely because an example uses one.
3. Construct a typed domain request at the application boundary. Keep parser types, terminal output,
   and process exits out of reusable libraries.
4. Implement or call the owning domain behavior with typed errors and no hidden effects.
5. Perform authorized filesystem/network/subprocess work through the repository's adapter boundary.
6. Render human or machine output deliberately; keep diagnostics and progress on stderr.
7. Map failures to documented exit status at the established top-level boundary. Only `main` returns
   `ExitCode`; lower layers return errors.

Keep the vertical slice small. Avoid opportunistic renames, formatting churn, dependency upgrades, or
refactors of neighboring commands.

## Document and generate

Update the canonical owner of command grammar, examples, output, effects, compatibility, and recovery.
If help or completions are generated, change parser/canonical source and run the repository generator;
do not hand-edit generated copies. Include migration notes for renamed or removed public grammar.

Examples must not embed credentials, absolute developer paths, destructive shortcuts, or fixed
platform assumptions.

## Validate and report

Use [Testing](testing.md) for focused and process-level coverage. Use
[Filesystem transactions](filesystem-transactions.md) for mutable effects. Run commands selected from
repository instructions, manifests, CI, or task runners; do not assume lockfile, workspace, target, or
feature flags.

Inspect the final diff for exact scope, exhaustive dispatch, parser/domain separation, output stream
purity, path safety, secret exposure, generated-state drift, and unrelated edits.

Report the before/after contract, discovered pattern, implementation by layer, exact tests and results,
manual review, skipped/unavailable matrices, source freshness, and remaining risk. Compilation and
structural checks are not native-client or model-backed evidence.
