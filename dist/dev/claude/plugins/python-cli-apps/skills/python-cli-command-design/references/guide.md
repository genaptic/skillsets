# Python CLI command design guide

## Model user tasks before command syntax

List what users are trying to accomplish, which objects they act on, required identifiers,
and whether each action reads or mutates state. A command tree should mirror that model
without exposing internal classes or API endpoint names.

Keep the root shallow. A noun-oriented group with clear actions is often discoverable:

```text
tool project list
tool project show ID
tool project delete ID
```

A verb-first interface can be appropriate for a small tool. Consistency matters more than a
universal grammar. Avoid two routes for the same task unless one is a documented alias with
a deprecation plan.

## Follow predictable utility syntax

Use one token for each command name. Prefer long options that explain themselves and add
short options only for frequent, unambiguous use. Keep option spelling and meaning consistent
across subcommands.

Use positional arguments for essential, naturally ordered identifiers. Use options when a
value is optional, policy-like, has a default, or benefits from a label. Avoid multiple
optional positionals and do not place arguments after a variadic positional.

Support `--` when values can begin with a hyphen. Treat standard input intentionally rather
than assuming `-` means stdin everywhere. Document whether repeated options append, replace,
or fail.

Boolean flags should have clear positive semantics. When both states are meaningful, use a
paired form such as `--color/--no-color` or a value option. Do not make “false” require a
surprising double negative.

## Define configuration precedence

A common predictable order is:

```text
command-line > environment > configuration file > built-in default
```

The exact order may differ, but it must be documented and inspectable. Avoid environment
variables that silently override an explicit command-line option.

Configuration files need a stable location, format, and merge policy. A `--config` option
should distinguish “file missing,” “file invalid,” and “key unsupported.” Provide a command
or mode that shows effective configuration without revealing secrets.

## Separate human and machine output

Stdout is the successful result stream. Stderr is for diagnostics and progress that should
not corrupt pipelines. A machine-readable mode should emit one documented schema and no
decorative text, color, spinners, or prompts.

TTY detection can improve presentation but must not change semantic results. Support an
explicit color policy and respect common non-interactive conventions. Paging should be
opt-in or safely disabled when stdout is not a terminal.

Stable machine output may need schema versioning. Do not suggest parsing human tables as an
automation contract.

## Design safe mutation

For destructive or expensive actions:

- Make the target and scope explicit.
- Show what will change.
- Require confirmation only in an interactive terminal.
- Provide a documented non-interactive acknowledgment such as `--yes`.
- Consider `--dry-run` when a faithful preview is possible.
- Define idempotency and partial-failure behavior.
- Return enough evidence for audit and recovery.

A prompt must never block unattended automation unexpectedly. Refuse unsafe non-interactive
execution rather than guessing consent.

## Help is part of the interface

Root help should describe purpose and show the command groups. Subcommand help should include
a one-line summary, usage, argument and option semantics, defaults, environment/config
sources, exit behavior, and realistic examples.

Do not hide necessary safety behavior only in external documentation. Ensure `COMMAND --help`
works without requiring valid application configuration or network access.

## Entry points and startup

The installed console entry point should resolve to a small callable. Keep imports and setup
light enough that `--help` and `--version` remain reliable. Avoid reading user configuration,
contacting services, or mutating state at import time.

## Compatibility

Command names, option names, defaults, output schemas, and exit behavior are public API.
Deprecate before removal:

1. Keep the old spelling as an alias.
2. Emit a targeted warning to stderr.
3. Document the replacement.
4. Define the removal version.
5. Test both routes during the migration period.

Do not silently repurpose an existing flag.

## Framework mapping

`argparse`, Click, Typer, and other frameworks differ in parsing, context, help rendering,
and exception behavior. Design the contract first, then map it to the installed framework
version. Do not let framework defaults become accidental product decisions.
