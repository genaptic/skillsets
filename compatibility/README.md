# Compatibility reports

This directory stores dated, redacted evidence from real client installations and eval runs.
The machine-readable compatibility-report schema is the release-gate contract;
`report-template.md` supplies the human reviewer narrative.

No client-backed report exists yet because the initial packs are unpublished release
candidates. Structural validation runs in CI, but it is not native-client or model-backed
evidence. Runtime claims begin only after dated, schema-valid reports identify the exact
released source SHA.

A publishable pack release requires passing evidence for Claude Code, Codex, and OpenCode.
Pull requests do not receive credentials and run structural checks only.
