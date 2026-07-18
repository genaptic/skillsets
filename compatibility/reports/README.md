# Compatibility reports

Commit redacted, dated reports here only after running the corresponding release candidate
at its exact proposed release SHA on a real client. Validate the machine-readable report
against the compatibility-report schema, use `../report-template.md` for reviewer narrative,
and name machine-readable gate reports with a `.json` suffix:

```text
YYYY-MM-DD__CLIENT__VERSION__PACK__TAG.json
```

An optional reviewer narrative may use the same filename stem with `.md`; the JSON report
is the validated workflow input and release-gate artifact.

A structural CI pass is neither a native-client nor a model-backed compatibility claim.
Reports must record client/model versions, operating system, pack version and proposed tag,
full source SHA, installation command, discovered skills, every executed case and verdict,
permissions, network/filesystem effects, failures, and artifact links. Never include
credentials, private repository URLs, customer data, or proprietary prompts.
