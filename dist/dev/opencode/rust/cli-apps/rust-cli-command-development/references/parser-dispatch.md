# Parser and dispatch integration

Every Rust block in this reference is an **adaptable snippet**, not a complete project. Discover the
existing parser and dispatch architecture before selecting any shape.

## Contents

- [Discovery](#discovery)
- [Parser change](#parser-change)
- [Dispatch change](#dispatch-change)
- [Domain handoff](#domain-handoff)
- [Output and exit behavior](#output-and-exit-behavior)
- [Patterns to reject](#patterns-to-reject)

## Discovery

Locate parser construction, command values, neighboring commands, dispatch, runtime/context, and tests
using repository-wide symbol and string searches. Determine:

- derive versus builder versus custom parsing;
- central enum versus independent command registration;
- sync versus async execution;
- receiver method, trait, match arm, function, table, or plugin dispatch;
- runtime services and when they initialize;
- domain ownership and adapter boundaries;
- text/machine output and error-to-exit mapping.

Do not infer architecture from one source file. Tests and generated help often expose contracts that
the implementation alone does not make obvious.

## Parser change

Mirror the closest coherent neighbor. Parser data may contain paths, strings, enums, bounded numbers,
and flags. It should not contain initialized clients, locks, loggers, mutable config, or domain state.

Adaptable clap snippet:

```rust
#[derive(Debug, clap::Args)]
struct InspectArgs {
    #[arg(value_name = "PROJECT")]
    project: std::path::PathBuf,

    #[arg(long, value_enum, default_value_t = Format::Text)]
    format: Format,
}
```

If the repository uses another parser, translate the contract rather than adding clap. Test help,
required values, invalid values, conflicts, aliases, and defaults without initializing services.

## Dispatch change

Extend the discovered mechanism exhaustively. Three legitimate shapes follow; choose only the one
already supported by the repository or justified by the task.

Adaptable match-arm snippet:

```rust
match command {
    Command::List(args) => list(args, services),
    Command::Inspect(args) => inspect(args, services),
}
```

Adaptable receiver snippet:

```rust
impl InspectArgs {
    fn execute(&self, context: &CommandContext) -> anyhow::Result<CommandOutput> {
        context.inspector.inspect(self.into_request(context)?)
    }
}
```

Adaptable async-trait-free snippet:

```rust
async fn dispatch(command: Command, services: &Services) -> anyhow::Result<CommandOutput> {
    match command {
        Command::Inspect(args) => inspect(args, services).await,
    }
}
```

Do not migrate sync to async, introduce a trait, or replace receiver methods solely for aesthetic
uniformity. A command addition should not smuggle in an application rewrite.

## Domain handoff

Convert raw parser input at the application/adapter boundary into repository-owned domain types.

Adaptable snippet:

```rust
let project = context.paths.resolve_owned_project(&args.project)?;
let request = InspectProject { project };
let result = context.projects.inspect(request)?;
```

The actual boundary may intentionally accept a path. Do not invent catalogs, IDs, or traits when they
do not improve the existing domain. Preserve the core rule: reusable behavior must not accept parser
matches, print to the terminal, or terminate the process.

## Output and exit behavior

Return a typed output or render through the established CLI adapter. Human and machine formats may
share data but should have deliberate representations. Keep diagnostics and progress on stderr. Map
typed failures to stable exit categories at the existing top-level boundary; only `main` returns
`ExitCode`.

If a command streams data, define broken-pipe behavior. If it is deprecated, place warnings on stderr
without corrupting machine stdout.

## Patterns to reject

- Root enum arm performs domain behavior directly while neighbors delegate coherently.
- Free helper or receiver method is declared invalid merely because another pattern is preferred.
- Parser matches or terminal concepts cross into a library API.
- Command handler combines parsing, service initialization, business logic, persistence, rendering,
  and process termination.
- A new dependency or crate duplicates an existing repository capability.
- Help or parse errors trigger network, credentials, filesystem mutation, or runtime startup.
- `Debug` formatting becomes a public text or machine output contract.
