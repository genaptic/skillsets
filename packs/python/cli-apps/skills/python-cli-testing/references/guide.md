# Python CLI testing guide

## Test the public process contract

A CLI is more than a Python function. Its public behavior includes:

- Installed command discovery.
- Argument parsing.
- Exit status.
- stdout and stderr.
- stdin and TTY behavior.
- Environment and configuration.
- Filesystem and process effects.
- Signals, interrupts, timeouts, and broken pipes.
- Shell quoting and platform differences.

Use in-process tests for fast command logic and framework integration, but include subprocess
tests for behavior that only exists at the process boundary.

## Choose in-process versus subprocess deliberately

An in-process runner is useful for:

- Parser and command callback behavior.
- Fast option combinations.
- Framework context and exception mapping.
- Isolated filesystem/environment fixtures supplied by the framework.

A subprocess is necessary to verify:

- The installed console entry point.
- Actual process status.
- OS-level stdout/stderr buffering.
- Environment inheritance.
- signals and interrupts.
- shell-free argv fidelity.
- startup/import behavior.
- Python module invocation versus installed script.

Do not invoke through a shell merely to make the test concise. Pass an argv array. Shell
integration tests, when necessary, should be a separate, explicitly platform-specific layer.

## Isolate process state

Each test should control:

- Working directory.
- Home/config/cache/data directories.
- Environment variables.
- Locale and time zone.
- Color/TTY indicators.
- Temporary files.
- Network and service endpoints.

Use temporary directories and environment overlays. Do not read or alter the developer's
real home directory, credentials, or configuration. Ensure tests cannot target production by
default.

## Assert all channels

Capture stdout and stderr separately and assert the integer return status. Do not concatenate
streams before asserting; ordering across streams is not a stable general contract.

For text output, prefer semantic lines and fields over full snapshots. Snapshot only stable,
intentional help/table output and review snapshots as public API changes.

For machine output, parse it. Assert schema and semantic fields rather than whitespace. Also
assert that decorative text, color codes, progress, or tracebacks are absent.

## Cover invocation and parsing boundaries

Include:

- Root and subcommand help.
- Version.
- Required, optional, repeated, variadic, and mutually exclusive inputs.
- `--` for values beginning with a hyphen.
- Empty strings, whitespace, Unicode, and path separators.
- stdin input and closed/empty stdin.
- Configuration precedence and invalid configuration.
- TTY and non-TTY behavior.
- Human and machine output.

Property-based or table-driven tests can cover parsing boundaries, but keep failure IDs
readable.

## Test effects and cleanup

For mutating commands:

- Verify dry run changes nothing.
- Verify confirmation and non-interactive refusal.
- Verify exact target/scope.
- Verify idempotent repeat behavior.
- Inject partial failure.
- Verify temporary files, locks, and transactions clean up.
- Verify interruption does not leave an undocumented state.

Use fakes only at a defined service boundary. Integration tests should exercise a disposable
real boundary when behavior depends on it.

## Signals, timeouts, and pipes

Signal tests can be timing-sensitive. Start a subprocess with a deterministic readiness
signal, send the platform-supported interrupt, and bound the wait. Record platform
exclusions explicitly.

Test broken-pipe behavior with a real downstream process or controlled pipe where supported.
Do not assume one status is portable across operating systems and shells.

## Help and completion

Help should run without valid business configuration or network access. Verify root and
subcommand discovery, defaults, environment/config references, and examples.

Completion scripts may be framework-generated and shell-specific. Test generation and a
small smoke case for supported shells; do not snapshot large generated scripts unless their
text is intentionally stable.

## CI matrix

Test representative combinations rather than every Cartesian product. Common dimensions:

- Installed entry point and module invocation.
- Human and machine output.
- TTY and non-TTY.
- Supported Python versions.
- Supported operating systems.
- Success, expected failure, unexpected failure.

Put fast in-process tests on every change. Keep process/platform integration focused on
public risk. Preserve failure artifacts without secrets.

## Avoid common false confidence

- Calling the command callback directly does not test parsing or process behavior.
- Asserting only output does not test status.
- Asserting only status does not test stream corruption.
- A passing framework runner does not prove the installed entry point works.
- Retrying signal tests does not prove they are deterministic.
