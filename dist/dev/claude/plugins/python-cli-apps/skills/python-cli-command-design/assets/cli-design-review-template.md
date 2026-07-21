# CLI command design review

## Users and environments

- Primary users:
- Human versus automation use:
- Supported operating systems and shells:
- Interactive/non-interactive environments:
- Stability and compatibility requirements:

## Task model

| User task | Command | Required input | Optional policy | Output | Mutates |
|---|---|---|---|---|---|
| | | | | | |

## Command tree

```text
program
└── noun
    ├── list
    └── delete ID
```

## Naming and syntax decisions

- Nouns and verbs:
- Long and short options:
- Positional arguments:
- Boolean negation:
- Repeated/list values:
- Standard input:
- `--` handling:
- Configuration precedence:

## Output modes

- Human-readable stdout:
- Machine-readable stdout:
- Diagnostics on stderr:
- Color/TTY behavior:
- Paging:
- Stable schema/version:

## Safety

- Destructive command confirmation:
- Non-interactive override:
- Dry run:
- Idempotency:
- Partial failure:
- Retry/resume:
- Audit evidence:

## Help and compatibility

- Root help:
- Subcommand help:
- Examples:
- Deprecation path:
- Completion/version behavior:

## Verification

- [ ] Every task has one discoverable route.
- [ ] Help is readable without external documentation.
- [ ] Automation works without prompts or TTY assumptions.
- [ ] Machine output is isolated from diagnostics.
- [ ] Destructive behavior requires intentional input.
