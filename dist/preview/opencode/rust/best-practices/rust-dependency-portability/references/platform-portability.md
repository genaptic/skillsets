# Platform portability patterns

## Paths and directories

Accept `&Path`/`PathBuf`, join components, and avoid converting to UTF-8 merely for convenience.
Use an approved platform-directory provider for configuration/cache/data locations and return an
explicit error when discovery is unavailable. Never fall back silently to root, home, current
working directory, or a hand-built platform path.

## Child processes

Use `Command::arg` for each argument, set `current_dir` explicitly, and pass child configuration
with `env`/`env_remove`. Avoid shell parsing unless the shell language itself is the explicit,
trusted input contract. Redact secrets from diagnostics and bound captured output.

## Conditional implementation

Keep `#[cfg]` at narrow module/adapter boundaries. Expose one portable interface and test shared
behavior independently. Put platform-only crates in Cargo target tables. Avoid scattering platform
branches through domain logic.

## Environment

Parse environment during single-threaded bootstrap into immutable configuration. After threads can
exist, do not call `set_var`/`remove_var`; Rust 2024 correctly requires an unsafe block because the
operation can be unsound. Tests should inject a map or set a child process environment instead.

## Evidence

A host test proves host behavior. A cross-compile proves compilation with the available target
standard library/linker/SDK. Only a native run proves runtime behavior on that target. Report these
levels separately and identify missing platforms.
