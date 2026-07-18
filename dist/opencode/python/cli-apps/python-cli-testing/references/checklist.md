# Python CLI testing checklist

## Layers

- [ ] In-process tests cover fast parser and callback behavior.
- [ ] Subprocess tests cover installed entry point and process semantics.
- [ ] Module invocation is tested when documented.
- [ ] Shell-specific tests are isolated and platform-labeled.
- [ ] Real integration boundaries are disposable and cannot target production.

## Isolation

- [ ] Working directory is explicit.
- [ ] Home, config, cache, and data paths use temporary locations.
- [ ] Environment changes are restored.
- [ ] Locale, time zone, color, and TTY assumptions are controlled.
- [ ] No real credentials or user configuration are read.
- [ ] Network access is disabled or redirected to an approved test service.
- [ ] Tests are safe under parallel execution.

## Contract assertions

- [ ] Integer exit status is asserted.
- [ ] stdout and stderr are captured separately.
- [ ] Machine output is parsed.
- [ ] Human output assertions avoid accidental snapshot coupling.
- [ ] Tracebacks and secrets are absent by default.
- [ ] Partial output semantics are tested.
- [ ] Stable errors and compatibility aliases are protected.

## Parsing and input

- [ ] Root/subcommand help and version are covered.
- [ ] Required, optional, repeated, variadic, and exclusive inputs are covered.
- [ ] `--` and leading-hyphen values are covered.
- [ ] Spaces, Unicode, empty input, and path differences are covered.
- [ ] stdin success, empty, closed, and malformed cases are covered.
- [ ] Configuration precedence and invalid configuration are covered.
- [ ] TTY and non-TTY paths are covered.

## Mutation and control flow

- [ ] Dry run produces no mutation.
- [ ] Confirmation and non-interactive refusal are covered.
- [ ] Idempotent repeat and partial failure are covered.
- [ ] Cleanup after error and interrupt is verified.
- [ ] Timeout and cancellation are bounded.
- [ ] Signal/broken-pipe tests document platform support.
- [ ] Unexpected failure behavior is covered without leaking internals.

## CI

- [ ] The matrix represents risk rather than every Cartesian combination.
- [ ] Fast tests run on pull requests.
- [ ] Platform/process tests have a runtime budget.
- [ ] Flaky tests are diagnosed, not hidden by unlimited retry.
- [ ] Failure artifacts are useful and redacted.
