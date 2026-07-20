# Good and bad single-command diff shapes

Every Rust block in this reference is an **adaptable snippet**, not a complete project. The examples
show responsibility flow, not required names, clap usage, or crate layout.

## Contents

- [Good vertical slice](#good-vertical-slice)
- [Good parser and dispatch](#good-parser-and-dispatch)
- [Good domain and rendering](#good-domain-and-rendering)
- [Bad diff shapes](#bad-diff-shapes)
- [Good final report](#good-final-report)

## Good vertical slice

A focused command diff typically changes only:

1. parser grammar and help;
2. exhaustive dispatch;
3. a typed domain operation or existing capability call;
4. one authorized adapter/effect path;
5. human/machine rendering and error mapping;
6. focused and process-level tests;
7. canonical command documentation plus generated derivatives.

Not every repository separates these into files or crates. Responsibility separation matters more
than file count.

## Good parser and dispatch

Adaptable parser snippet:

```rust
#[derive(Debug, clap::Args)]
struct ArchiveArgs {
    project: std::path::PathBuf,
    #[arg(long)]
    destination: std::path::PathBuf,
}
```

Adaptable dispatch snippet:

```rust
match command {
    Command::Archive(args) => archive(args, services, output).await,
    other => dispatch_existing(other, services, output).await,
}
```

In a real exhaustive enum match, retain explicit arms rather than a catch-all if that is the existing
compile-time completeness contract. A sync repository should not use `async` merely to match this
snippet.

## Good domain and rendering

Adaptable typed boundary:

```rust
pub struct ArchiveProject {
    pub project: ProjectId,
    pub destination: ArchiveDestination,
}

pub struct ArchiveResult {
    pub files: usize,
    pub archive: ArchiveId,
}
```

The CLI adapter resolves OS paths, validates target/ownership/overwrite policy, constructs the domain
request, persists through an authorized adapter, and renders `ArchiveResult`. The domain does not
accept parser matches, print, log to stdout, or exit.

Adaptable renderer snippet:

```rust
match format {
    Format::Text => writeln!(stdout, "archived {} files", result.files)?,
    Format::Json => serde_json::to_writer(&mut stdout, &result)?,
}
```

Add the required newline and broken-pipe behavior according to the repository's output contract.
Machine fields must be stable and deliberately serialized.

## Bad diff shapes

### Parser owns behavior

Adaptable anti-pattern:

```rust
impl ArchiveArgs {
    fn parse_and_delete_source(self) {
        std::fs::remove_dir_all(self.project).unwrap();
    }
}
```

This mixes parser data, unchecked destructive behavior, panic, and implicit semantics.

### Domain depends on CLI

Adaptable anti-pattern:

```rust
pub fn archive(matches: &clap::ArgMatches) -> anyhow::Result<()> {
    println!("{matches:?}");
    Ok(())
}
```

Parser and terminal behavior now contaminate the reusable domain contract.

### Exit below main

Adaptable anti-pattern:

```rust
fn execute_archive() {
    if operation_failed() {
        std::process::exit(2);
    }
}
```

Lower-layer exit skips normal error propagation and centralized cleanup. Return a typed error; map it
to `ExitCode` only at `main`.

### Unreviewed replacement

Adaptable anti-pattern:

```rust
std::fs::write(path, bytes)?;
```

This may be acceptable for an explicitly disposable file, but it is not an atomic/durable config or
state transaction. Select guarantees and tests deliberately.

### Scope smuggling

- New command also renames unrelated commands.
- Dependency upgrade is mixed in without need or authorization.
- Output changes from stable serialization to `Debug` formatting.
- Generic architecture replaces coherent existing dispatch.
- Generated help/completion files are hand-edited.
- Tests mutate global environment or use developer credentials.

## Good final report

Report:

- discovered neighboring command and architecture;
- exact before/after invocation, output, exit, and effects;
- files/layers changed and why;
- safety controls and authority for external effects;
- focused, process, generated-state, and broader checks exactly as run;
- failed, skipped, unavailable, and manual evidence;
- migration notes and remaining risk.

Do not call compilation a native CLI discovery pass or claim model behavior from structural evals.
