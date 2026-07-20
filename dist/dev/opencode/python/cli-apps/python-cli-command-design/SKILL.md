---
name: python-cli-command-design
description: >
  Design or review a Python command-line interface's command tree, names, arguments, options, configuration precedence, input sources, human and machine output modes, help, destructive-action safeguards, and compatibility policy. Use when shaping how users and automation invoke a CLI. Do not use when only failure messages/exit codes or CLI tests need work.
license: Apache-2.0
metadata:
  skillpack: "python-cli-apps"
  version: "1.0.0"
  maturity: "release-candidate"
---

# Outcome

Produce a concrete, reviewable result for the workflow below without overstating what was
observed, executed, or verified.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. The optional JSON-spec validator requires
Python 3.11, reads one local file, and executes no commands. Map the resulting contract to the
actual argparse, Click, Typer, or other framework version.

## Use this skill when

- A new Python CLI needs a command and option model.
- An existing interface has inconsistent names, deep nesting, ambiguous arguments, or automation-hostile prompts.
- Configuration files, environment variables, stdin, output formats, color, or paging need a documented contract.
- Destructive commands, help, entry points, or deprecation behavior need design review.

## Do not use this skill when

- The command structure is fixed and only diagnostics, stderr, tracebacks, or exit statuses need design; use `python-cli-error-output`.
- The interface is fixed and the outcome is a test suite; use `python-cli-testing`.
- The task is a shell script or HTTP API rather than a Python command interface.

## Inputs

Inspect or obtain:

- Primary user tasks, objects, read/write effects, and automation use cases.
- Existing parser code, help text, examples, command transcripts, and compatibility commitments.
- Supported operating systems, shells, TTY/non-TTY environments, and stdin behavior.
- Configuration sources, precedence, secret handling, and effective-config requirements.
- Human and machine output consumers and schema stability expectations.
- Destructive/expensive actions, idempotency, partial failure, and recovery needs.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Design and validate the contract before modifying parser code.
- Do not place secrets in command-line examples or recommend command-line secret transport by default.
- Do not infer consent from TTY presence; define explicit confirmation and non-interactive behavior.
- Do not let progress, prompts, or color corrupt machine-readable stdout.
- The optional validator checks a declarative JSON model and cannot prove framework behavior.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. **Model user tasks and environments.** Identify human and automation users, objects, actions, required context, mutation, supported shells, and stability needs.

2. **Create a coherent command tree.** Choose consistent noun/verb grammar, keep nesting shallow, remove duplicate routes, and separate global context from command-local options.

3. **Assign arguments and options.** Use positionals for essential naturally ordered identifiers and options for optional/policy values. Define repetition, `--`, stdin, boolean negation, defaults, and validation.

4. **Define configuration precedence.** Document command-line, environment, configuration-file, and built-in ordering; define merge behavior and a safe way to inspect effective configuration.

5. **Design output channels.** Reserve stdout for successful result data and stderr for diagnostics/progress. Define stable machine formats, color/TTY/paging behavior, and streaming semantics.

6. **Make mutation intentional.** Show target and scope, define interactive confirmation and explicit non-interactive acknowledgment, add a truthful dry run where possible, and specify idempotency and partial failure.

7. **Write self-sufficient help.** Include purpose, usage, argument/option semantics, defaults, config/environment sources, examples, and safety behavior. Ensure help/version paths work offline and without full configuration.

8. **Plan compatibility.** Treat command names, options, defaults, output schemas, and behavior as API. Define aliases, warnings, replacement, and removal version for changes.

9. **Map the design to the framework.** Implement only after confirming parser/framework semantics and keeping entry-point startup free of unnecessary side effects.

10. **Verify across invocation modes.** Exercise installed entry points, help, shell quoting, stdin, non-TTY automation, human and JSON output, destructive safeguards, and legacy aliases.

## Verification

Before claiming completion:

- Each important user task has one discoverable command path.
- Arguments, options, repetition, stdin, and configuration precedence are unambiguous.
- Human and machine output remain separable in TTY and non-TTY environments.
- Destructive actions require intentional input and have documented idempotency/partial-failure behavior.
- `--help` and `--version` work offline without unrelated configuration or network access.
- Installed entry points and representative shells parse examples as documented.
- Compatibility changes include aliases/warnings and a removal plan.

## Output contract

Return:

- User/task and environment assumptions.
- Command tree and argument/option specification.
- Configuration, input, output, TTY, and machine-schema contracts.
- Mutation safety, idempotency, and partial-failure policy.
- Help/examples and compatibility/deprecation plan.
- Implementation map plus executed/proposed verification matrix.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [command-spec.example.json](assets/command-spec.example.json)
- [cli-design-review-template.md](assets/cli-design-review-template.md)
- [validate_command_spec.py](scripts/validate_command_spec.py)
- [Routing and behavior evals](evals/evals.json)
