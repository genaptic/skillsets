# Rust CLI architecture

Every Rust block in this reference is an **adaptable snippet**, not a complete project. Preserve the
target repository's crate boundaries, parser, sync/async model, names, and dependency policy.

## Contents

- [Responsibility layers](#responsibility-layers)
- [Parser boundary](#parser-boundary)
- [Application and dispatch](#application-and-dispatch)
- [Domain and adapters](#domain-and-adapters)
- [Errors and exit status](#errors-and-exit-status)
- [Patterns to reject](#patterns-to-reject)

## Responsibility layers

Use conceptual layers even if a small program stores them in one crate:

```text
argv/stdin/config -> parser -> application/dispatch -> domain -> adapters
                                              |-> renderer -> stdout/stderr
                                              `-> top-level error -> ExitCode
```

- Parser: syntax, required values, conflicts, typed enums, and help.
- Application: runtime initialization, command coordination, cancellation, and shared resources.
- Domain: reusable operations and invariants expressed through typed requests/results.
- Adapters: filesystem, network, database, config, clock, terminal, and subprocess effects.
- Renderer: stable human and machine output.
- Entrypoint: final diagnostic policy and `ExitCode`.

Crates are optional boundaries. Add one only when ownership, reuse, compile-time isolation, or release
needs justify it. Dependency direction should point from the CLI adapter toward domain libraries, not
from domain libraries toward parser or terminal crates.

## Parser boundary

Parser-derived values should contain user input, not initialized clients or mutable application state.

Adaptable snippet:

```rust
#[derive(Debug, clap::Parser)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, clap::Subcommand)]
enum Command {
    Inspect(InspectArgs),
    Update(UpdateArgs),
}
```

Before using this shape, discover whether the repository uses clap derive, clap builder APIs, lexopt,
pico-args, a custom parser, or another interface. Do not pass `ArgMatches` or parser structs into a
reusable domain library.

## Application and dispatch

Initialize resources after successful parsing so `--help`, `--version`, and syntax errors do not open
databases, read credentials, or make network calls. Follow the repository's established dispatch
shape: match arms, receiver methods, a command trait, functions, or another coherent abstraction.

Adaptable synchronous snippet:

```rust
fn run(cli: Cli, services: &Services) -> anyhow::Result<CommandOutput> {
    match cli.command {
        Command::Inspect(args) => inspect(args, services),
        Command::Update(args) => update(args, services),
    }
}
```

An async repository may await each arm; a synchronous repository should not acquire a runtime solely
to copy an example. Avoid giant dispatch functions that also parse, perform domain work, persist,
format, and print.

## Domain and adapters

Domain operations accept typed concepts rather than terminal or parser objects. Paths may remain in an
adapter when the domain can operate on bytes, catalogs, handles, or logical identifiers. Conversely,
do not force an artificial catalog abstraction where the repository's domain genuinely owns paths.

Adaptable snippet:

```rust
pub struct InspectRequest {
    pub project: ProjectId,
}

pub struct InspectResult {
    pub status: ProjectStatus,
}

pub trait ProjectStore {
    fn inspect(&self, request: InspectRequest) -> Result<InspectResult, StoreError>;
}
```

Use concrete types until multiple implementations or test seams justify a trait. Keep terminal color,
stdout/stderr, completion generation, parser types, and process termination outside the domain.

## Errors and exit status

Libraries should expose actionable typed errors appropriate to their public contract. The application
layer may add context and translate errors into stable diagnostics and exit categories.

Adaptable entrypoint snippet:

```rust
use std::process::ExitCode;

fn main() -> ExitCode {
    match try_main() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error:#}");
            ExitCode::FAILURE
        }
    }
}
```

Use repository-defined exit codes if they exist. Do not call `std::process::exit` in command, domain,
or cleanup layers: it skips normal unwinding and central policy. Redact secrets and bounded response
content before rendering errors.

## Patterns to reject

- Treating the parser's `Command` builder as the runtime application.
- Storing initialized clients or config mutation inside parser-derived types.
- Requiring receiver methods or a command trait when existing free-function dispatch is already clear.
- Passing parser matches into domain libraries.
- Printing, logging, coloring, or exiting inside domain code.
- Using `anyhow::Error` as a stable public library error contract without deliberate justification.
- Hiding shared mutable globals behind lazy initialization.
- Adding new crates or dependencies before inspecting existing ownership and capabilities.
