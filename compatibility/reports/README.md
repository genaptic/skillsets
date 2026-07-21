# Compatibility reports

Commit redacted, timestamped schema-version-2 reports here only after running the corresponding release candidate
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
full source SHA, installation command, discovered skills, every executed per-skill case, and
every routing boundary incident to the selected pack. Boundary entries identify their
`internal-pack` or `cross-pack` scope, exact canonical `boundarySkills`, exact owning
`installedPacks`, expected selection, observed selection, and verdict. Cross-pack boundaries
must come from separate clean multi-pack runs and cannot be omitted. Also record permissions,
network/filesystem effects, failures, canonical UTC `testedAt`, and the reviewer's GitHub login
plus immutable numeric user ID. Dispatch protected ingestion with the exact full commit SHA
containing the report; never use a floating branch or tag. Never include credentials, private
repository URLs, customer data, or proprietary prompts.
