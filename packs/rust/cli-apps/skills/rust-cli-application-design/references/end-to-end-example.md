# Adaptable end-to-end Rust CLI example

This is a **connected set of adaptable snippets, not a complete or copy-ready project**. It
demonstrates a thin CLI boundary without prescribing crate names, clap, synchronous dispatch, or a
dependency set. Map each concept to the target repository and add its required error types and tests.

## Contents

- [Example contract](#example-contract)
- [Parser data](#parser-data)
- [Application and domain boundary](#application-and-domain-boundary)
- [Rendering and entrypoint](#rendering-and-entrypoint)
- [Safe removal design](#safe-removal-design)
- [Verification matrix](#verification-matrix)

## Example contract

The illustrative tool exposes:

```text
tool project create <PATH> [--name <NAME>]
tool project list [--format text|json]
tool project show <PATH> [--format text|json]
tool project remove <PATH> [--confirm]
```

This grammar is illustrative. Discover existing verbs, nouns, aliases, precedence, and migration
constraints before proposing it. The remove command is intentionally not implemented below; recursive
deletion requires an application-specific ownership and authorization contract.

## Parser data

Adaptable snippet using clap derive:

```rust
use std::path::PathBuf;

use clap::{Args, Parser, Subcommand, ValueEnum};

#[derive(Debug, Parser)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    Project(ProjectArgs),
}

#[derive(Debug, Args)]
struct ProjectArgs {
    #[command(subcommand)]
    action: ProjectAction,
}

#[derive(Debug, Subcommand)]
enum ProjectAction {
    Create {
        path: PathBuf,
        #[arg(long)]
        name: Option<String>,
    },
    List {
        #[arg(long, value_enum, default_value_t = OutputFormat::Text)]
        format: OutputFormat,
    },
    Show {
        path: PathBuf,
        #[arg(long, value_enum, default_value_t = OutputFormat::Text)]
        format: OutputFormat,
    },
    Remove {
        path: PathBuf,
        #[arg(long)]
        confirm: bool,
    },
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum OutputFormat {
    Text,
    Json,
}
```

Parser data owns syntax only. Do not initialize a project directory provider, storage client, logger,
or configuration inside these derived values.

## Application and domain boundary

Adaptable domain contracts:

```rust
#[derive(Debug)]
pub struct CreateProject {
    pub destination: ProjectDestination,
    pub name: Option<String>,
}

#[derive(Debug, serde::Serialize)]
pub struct ProjectSummary {
    pub id: ProjectId,
    pub name: String,
}

pub trait ProjectRepository {
    fn create(&self, request: CreateProject) -> Result<ProjectSummary, ProjectError>;
    fn list(&self) -> Result<Vec<ProjectSummary>, ProjectError>;
    fn show(&self, id: &ProjectId) -> Result<ProjectSummary, ProjectError>;
}
```

`ProjectDestination`, `ProjectId`, and `ProjectError` are placeholders for repository-owned domain
types. A path adapter may validate and convert an OS path before constructing the request.

Adaptable application dispatch:

```rust
fn execute(
    action: ProjectAction,
    services: &Services,
    output: &mut dyn Output,
) -> anyhow::Result<()> {
    match action {
        ProjectAction::Create { path, name } => {
            let destination = services.paths.authorize_create(path)?;
            let result = services.projects.create(CreateProject { destination, name })?;
            output.project_created(&result)
        }
        ProjectAction::List { format } => {
            let projects = services.projects.list()?;
            output.projects(format, &projects)
        }
        ProjectAction::Show { path, format } => {
            let id = services.paths.resolve_owned_project(path)?;
            let project = services.projects.show(&id)?;
            output.project(format, &project)
        }
        ProjectAction::Remove { path, confirm } => {
            services.removal.preview_and_remove_owned_project(path, confirm, output)
        }
    }
}
```

The application calls repository abstractions and coordinates effects. The placeholder removal API is
not permission to delete; it must implement the exact-target contract in
[Filesystem and output safety](filesystem-output-safety.md).

## Rendering and entrypoint

Adaptable renderer interface:

```rust
trait Output {
    fn project_created(&mut self, value: &ProjectSummary) -> anyhow::Result<()>;
    fn projects(&mut self, format: OutputFormat, values: &[ProjectSummary])
        -> anyhow::Result<()>;
    fn project(&mut self, format: OutputFormat, value: &ProjectSummary)
        -> anyhow::Result<()>;
}
```

A concrete renderer writes results to stdout. Logs, warnings, deprecations, and diagnostics go to
stderr. JSON should serialize typed output with stable fields, not `Debug` strings.

Adaptable entrypoint:

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

Keep cleanup and error translation above `main` so no domain or command layer needs
`std::process::exit`.

## Safe removal design

Before implementing `remove`, define:

- the one authorized parent and exact target identity;
- ownership marker or registry proof;
- protected root, home, repository/worktree, and ancestor checks;
- lexical and resolved containment;
- explicit symlink-component and descendant policy;
- preview content and confirmation/noninteractive authorization;
- immediate pre-mutation recheck;
- interruption, partial deletion, quarantine, and recovery reporting.

Do not use a bare `remove_dir_all(path)` example. A `--confirm` flag alone does not make the target
safe, and a string prefix does not prove containment.

## Verification matrix

| Surface | Required examples |
|---|---|
| Parser | root/nested help, missing args, format enum, paths |
| Domain | create/list/show invariants and typed failures |
| Adapter | containment, ownership, symlinks, collisions, replacement |
| Process | exit status, stdout/stderr, text and JSON |
| Removal | protected paths, preview, confirmation, target swap, interruption |
| Portability | spaces, non-ASCII, platform directories, Windows/Unix CI when available |

Run repository-authoritative checks and record unavailable matrices honestly. These snippets do not
prove dependency versions, compile as a standalone project, or authorize adding any crate.
