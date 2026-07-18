# Rust CLI grammar and compatibility

Every Rust block in this reference is an **adaptable snippet**, not a complete project. Map syntax to
the repository's parser and public compatibility policy.

## Contents

- [Start from user tasks](#start-from-user-tasks)
- [Commands and subjects](#commands-and-subjects)
- [Arguments and options](#arguments-and-options)
- [Configuration precedence](#configuration-precedence)
- [Help, completion, and deprecation](#help-completion-and-deprecation)
- [Grammar tests](#grammar-tests)

## Start from user tasks

Write representative invocations before parser types. For each, define:

- desired outcome and target object;
- required and optional inputs;
- side effects and confirmation;
- success output, machine output, diagnostics, and exit status;
- compatibility with existing invocations.

Prefer stable, unsurprising vocabulary over exposing internal module names. Avoid broad verbs such as
`do`, `run`, or `manage` when a precise verb exists. Keep `list`, `show`, and `status` distinct when
they represent collection, one object's details, and computed health.

## Commands and subjects

Use one coherent grammar, such as `tool <verb> <subject>` or `tool <subject> <verb>`, based on the
existing CLI and user mental model. Do not mix structures casually.

Adaptable clap snippet:

```rust
#[derive(Debug, clap::Subcommand)]
enum Command {
    Project(ProjectCommand),
}

#[derive(Debug, clap::Args)]
struct ProjectCommand {
    #[command(subcommand)]
    action: ProjectAction,
}

#[derive(Debug, clap::Subcommand)]
enum ProjectAction {
    List,
    Show { id: String },
}
```

Nested enums are useful when they mirror a stable grammar, but one giant enum or deep nesting can
obscure help. Match the repository's current shape. Add a new command only when an existing command,
target, or option cannot express the outcome cleanly.

## Arguments and options

- Use positionals for essential, obvious operands with stable order.
- Use named options for optional, reusable, dangerous, or non-obvious values.
- Use typed enums for closed sets and validated newtypes for constrained values.
- Make conflicting flags parser-visible; avoid resolving contradictory values silently.
- Avoid optional booleans whose absence and `false` are indistinguishable when three states matter.
- Keep short flags conventional and collision-free. Long flags are part of the public API.
- Accept OS paths as `PathBuf`/`OsString`; do not require Unicode merely to parse a path.
- Do not rely on shell glob expansion: it differs across shells and platforms. Define whether the
  program accepts literal globs or multiple path operands.
- Reject non-finite floating values. For money, use integer minor units or a checked decimal type.

Adaptable finite-number parser snippet:

```rust
fn parse_finite(raw: &str) -> Result<f64, String> {
    let value = raw.parse::<f64>().map_err(|error| error.to_string())?;
    value
        .is_finite()
        .then_some(value)
        .ok_or_else(|| "value must be finite".to_owned())
}
```

Prefer a bounded domain newtype when a numeric value also has range or unit constraints.

## Configuration precedence

Document one deterministic precedence order. A common shape is:

```text
command options > explicitly supported environment > project config > user config > defaults
```

The target repository may differ. Parse all sources into immutable configuration, validate once, and
pass it to components. Do not mutate process-global environment to simulate configuration. For child
processes, use the command builder's environment API on that child only.

Make configuration locations discoverable and return an explicit error when platform directories
cannot be determined. Never panic because a home/config directory is unavailable.

## Help, completion, and deprecation

- Make root and nested help useful without initializing runtime services.
- Include concrete usage examples for non-obvious commands and destructive effects.
- Keep help and docs generated from or tested against the parser where possible.
- Generate completions through the parser's supported API and test generation separately from shell
  installation.
- Deprecate public commands/options deliberately: warning on stderr, replacement guidance, migration
  window, and tests. Do not reuse an old flag for unrelated semantics.
- Keep aliases intentional and test which name appears in help and errors.

## Grammar tests

Test parser construction directly when possible:

- root and every nested `--help`;
- `--version` scope;
- missing operands and unknown commands;
- conflicts, requirements, typed values, aliases, and defaults;
- paths with spaces and non-ASCII names;
- non-finite and out-of-range numeric values;
- deprecated grammar and replacement messages;
- no service, filesystem, credential, or network initialization for help/parse errors.
