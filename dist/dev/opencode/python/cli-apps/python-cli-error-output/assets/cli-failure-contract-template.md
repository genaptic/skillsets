# CLI failure contract

## Context

- Program:
- Framework and version:
- Human output modes:
- Machine output modes:
- Supported platforms/shells:
- Existing public exit codes:
- Debug/traceback policy:

## Failure classes

| Failure class | Example | Exit code | stdout | stderr | Retry/caller action |
|---|---|---:|---|---|---|
| Usage/parse error | Missing required argument | | Empty | Usage + correction | Fix invocation |
| Domain not found | Missing resource | | | | |
| Dependency unavailable | Temporary service failure | | | | |
| Internal defect | Unexpected exception | | | | |

## Message shape

- Stable machine code:
- Human summary:
- Safe context:
- Suggested next action:
- Documentation/help reference:
- Redaction rules:

## Control-flow policy

- `--debug`:
- Interrupt:
- Broken pipe:
- Timeout:
- Partial output:
- Cleanup:
- Logging boundary:

## Compatibility

- Codes reserved:
- Deprecated code/message behavior:
- Machine schema version:
- Tests that protect the contract:

## Verification evidence

- [ ] stdout and stderr captured independently.
- [ ] Exit status checked by integer value.
- [ ] TTY and non-TTY paths checked.
- [ ] Human and machine modes checked.
- [ ] Tracebacks excluded by default.
- [ ] Secrets and raw payloads absent.
