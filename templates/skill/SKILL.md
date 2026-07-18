---
name: replace-with-globally-unique-skill-name
description: >
  Describe the focused outcome, strongest triggers, and artifacts. Use when the user needs
  this exact workflow. Do not use for the closest neighboring workflow; name that boundary.
license: Apache-2.0
metadata:
  skillpack: "replace-with-pack-id"
  version: "0.1.0"
  maturity: "draft"
---

## Outcome

State the observable result.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. State optional tools, minimum versions,
network behavior, and operating constraints here. Native-client compatibility remains
unverified until a validated report records the client version and exact source commit.

## Inputs

Inspect or obtain the minimum inputs. Label assumptions.

## Safety

State reads, writes, commands, network access, credentials, confirmation, and rollback.

## Procedure

1. Inspect before changing.
2. Explain evidence and tradeoffs.
3. Propose the smallest safe action.
4. Obtain explicit approval where required.
5. Apply and verify only within the agreed scope.

## Verification

List evidence required before claiming success.

## Output contract

Return assumptions, findings, proposal or patch, verification, and remaining risks.

## Resources

- [Guide](references/guide.md)
- [Checklist](references/checklist.md)
- [Sources](references/sources.md)
