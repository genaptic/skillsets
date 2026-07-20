# Rust CLI application design guide

Use this guide to coordinate the focused references without imposing a generic crate layout or
framework. Repository evidence decides the concrete parser, runtime, sync/async model, and commands.

## Contents

- [Discover before designing](#discover-before-designing)
- [Define the user contract](#define-the-user-contract)
- [Choose boundaries](#choose-boundaries)
- [Design effects and failures](#design-effects-and-failures)
- [Preview and implement](#preview-and-implement)
- [Validate and report](#validate-and-report)

## Discover before designing

Read applicable instructions and inventory:

- `Cargo.toml`, workspace membership, binary/library targets, toolchain, MSRV, edition, features,
  lockfile policy, `.cargo` configuration, and CI/task-runner commands;
- parser declarations and parser tests;
- command enumeration, dispatch, runtime initialization, services, and domain entry points;
- errors, output renderers, logging/progress, configuration, platform-directory discovery, and
  filesystem helpers;
- integration/E2E fixtures, docs, completion generation, and packaging assumptions.

Use search patterns, not guessed paths:

```text
derive(Parser|Subcommand|Args), get_matches, parse_from, enum .*Command,
execute|dispatch|run, ExitCode|Termination|process::exit, stdout|stderr,
remove_dir_all|rename|persist, ProjectDirs|BaseDirs, assert_cmd|trycmd
```

Determine whether dispatch is synchronous or asynchronous, receiver-based or free-function based,
centralized or decentralized. Preserve a coherent existing pattern unless evidence justifies a
migration. Do not require any neighboring skill at runtime.

## Define the user contract

Before code, record:

| Concern | Decision |
|---|---|
| Audience | interactive users, automation, or both |
| Grammar | executable, verbs, nouns, positionals, options, aliases |
| Stability | public names, output fields, exit meanings, deprecation window |
| Inputs | argv, stdin, config, environment, files, network |
| Precedence | CLI, environment, project config, user config, defaults |
| Outputs | text, machine format, files, stdout, stderr |
| Effects | reads, writes, deletion, subprocesses, network, external services |
| Failure | error categories, messages, exit status, partial-state handling |
| Portability | paths, encodings, terminals, shells, OS behavior |

Examples in bundled references are adaptable snippets unless explicitly called a complete project.
No bundled reference is a drop-in project; map every pattern to the discovered repository.

## Choose boundaries

Separate responsibilities even when a small binary keeps them in one crate:

1. **Parser:** validate syntax and produce typed input.
2. **Application/runtime:** initialize shared resources after parsing and coordinate a command.
3. **Domain:** implement reusable behavior with typed requests, outputs, and errors.
4. **Adapters:** own filesystem, network, config, terminal, and process boundaries.
5. **Renderer:** deliberately produce human or machine output.
6. **Main:** translate final success/failure into `ExitCode` and top-level diagnostics.

See [Architecture](architecture.md). Do not store service clients in parser types, pass parser matches
into libraries, print from domain code, or call `process::exit` below `main`.

## Design effects and failures

- Keep stdout reserved for command results and machine-readable data; send diagnostics, warnings,
  progress, and logs to stderr.
- Give machine output a documented schema and deterministic ordering where consumers depend on it.
- Use typed library errors; attach user-facing context at application boundaries without exposing
  credentials, tokens, raw response bodies, or internal debug state.
- Treat path traversal, symlinks, case/normalization collisions, overwrite, recursive deletion,
  partial transactions, and interruption as design inputs.
- Model configuration as immutable data passed into components. Set environment only on a child
  process builder; do not mutate process-global environment in a multithreaded program.
- Parse numeric values into bounded domain types. Reject NaN and positive/negative infinity. Represent
  money with integer minor units or a checked decimal type, never binary floating point.

See [Filesystem and output safety](filesystem-output-safety.md) for testable contracts. The
[`finite_bounded_number.rs`](../assets/templates/finite_bounded_number.rs) adaptable asset makes the
non-monetary numeric boundary executable. The
[`removal_preview.rs`](../assets/templates/removal_preview.rs) adaptable asset implements a strictly
read-only removal preview; it intentionally provides no deletion operation.

## Preview and implement

Preview a matrix of commands and layers before broad changes:

| Command | Parser type | Domain operation | Effects | Output | Tests |
|---|---|---|---|---|---|

Include migration/deprecation decisions, dependency changes, generated surfaces, destructive effects,
and verification commands. Reinspect if the repository changes after review.

Implement vertically in small slices: grammar, dispatch, domain request, adapter/effect, renderer,
focused tests, then E2E contract. Reuse existing dependencies and abstractions when they remain fit.
Do not add a framework or crate merely because a bundled example uses one.

## Validate and report

Use [Testing](testing.md) to cover parser/help, domain, command, streams, exit status, filesystem,
configuration, and cross-platform behavior. Discover canonical Cargo invocations from the repository;
`--locked`, `--workspace`, `--all-targets`, and `--all-features` are policies, not universal defaults.

Review the final diff for:

- accidental grammar or machine-schema changes;
- `Debug` output on public surfaces;
- path-to-string conversions and Unix-only assumptions;
- hidden globals or environment mutation;
- unchecked deletion or overclaimed atomicity;
- unrelated refactors, new dependencies, generated-file edits, or suppressed warnings.

Report exact commands and results, manual reviews, unavailable platforms/tools/services, and remaining
risks. Do not claim native-client or model-backed evidence from compilation or structural validation.
