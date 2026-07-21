# Compatibility reports

This directory stores timestamped, redacted evidence from real client installations and eval runs.
The machine-readable compatibility-report schema is the release-gate contract;
`report-template.md` supplies the human reviewer narrative.

No client-backed report exists yet because the initial packs are unpublished release
candidates. Structural validation runs in CI, but it is not native-client or model-backed
evidence. Runtime claims begin only after fresh, schema-valid reports identify the exact
released source SHA.

Reports cover every per-skill routing and behavior case plus every reviewed routing boundary
incident to the selected pack. They record canonical `expectedSkills` and the client/model's
`observedSkills`. Each boundary case also binds the canonical two `boundarySkills`, exact
`installedPacks`, and an `internal-pack` or `cross-pack` scope. Cross-pack cases require a
separate clean multi-pack run; omitting them makes the selected pack's report incomplete.

A publishable pack release requires fresh schema-version-2 passing evidence for Claude Code,
Codex, and OpenCode. The protected ingestion workflow accepts only a full evidence commit SHA,
preserves the report's exact bytes, proves its ancestry from the evaluated source and into
dispatch-time `main`, authenticates the reviewer against `repository.yaml`, and emits a signed
provenance envelope. Its artifact contains `<client>.json`, `<client>.envelope.json`, and
`<client>.attestation.jsonl`; all three must be retained as release assets.
Pull requests do not receive credentials and run structural checks only.
