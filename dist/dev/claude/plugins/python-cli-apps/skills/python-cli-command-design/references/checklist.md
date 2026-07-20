# CLI command design checklist

## User model

- [ ] Primary users and automation environments are identified.
- [ ] User tasks are mapped before commands.
- [ ] Read-only and mutating actions are distinguished.
- [ ] Command names describe user concepts rather than internal implementation.
- [ ] The command tree is shallow and discoverable.

## Syntax

- [ ] Commands are one token and use consistent grammar.
- [ ] Long option names are present for public options.
- [ ] Short options are unambiguous and worth memorizing.
- [ ] Required identifiers are positionals only when order is natural.
- [ ] Optional or policy values are named options.
- [ ] No required positional follows a variadic positional.
- [ ] Repetition, `--`, stdin, and values beginning with `-` are defined.
- [ ] Boolean flags have clear positive/negative semantics.

## Configuration

- [ ] Precedence among command line, environment, file, and defaults is documented.
- [ ] Effective configuration can be inspected safely.
- [ ] Secret values are not required on the command line.
- [ ] Missing, invalid, and unsupported configuration are distinguishable.
- [ ] Configuration loading does not break `--help` or `--version`.

## Output and automation

- [ ] Success data uses stdout.
- [ ] Diagnostics and progress use stderr.
- [ ] Machine output has a documented schema.
- [ ] Machine output contains no color, prompts, spinners, or decorative text.
- [ ] TTY detection affects presentation, not semantic results.
- [ ] Color and paging can be controlled explicitly.
- [ ] Shell quoting assumptions are documented.

## Mutation and safety

- [ ] Target and scope are visible before mutation.
- [ ] Interactive confirmation has a non-interactive policy.
- [ ] Dry run is provided when it can be truthful.
- [ ] Idempotency and partial failure are defined.
- [ ] Interrupt behavior and cleanup are defined.
- [ ] Audit/recovery evidence is produced.

## Help and compatibility

- [ ] Root and subcommand help work offline.
- [ ] Examples are realistic and safe.
- [ ] Defaults, environment variables, and config sources are visible.
- [ ] Public command/option/output changes follow a deprecation path.
- [ ] Installed entry points and startup behavior are verified.
