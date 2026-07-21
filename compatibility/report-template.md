# Compatibility report

## Provenance

- Tested at (canonical UTC `YYYY-MM-DDTHH:MM:SSZ`):
- Reviewer GitHub login:
- Reviewer numeric GitHub user ID:
- Reviewer verdict: pass / fail
- Operating system:
- Shell:
- Client:
- Client version:
- Model provider:
- Model identifier and version, when visible:
- Pack:
- Pack version:
- Release tag:
- Full 40-character source SHA:
- Installation method:
- Clean environment description:
- Machine-readable report path:
- Full 40-character evidence commit SHA containing that report:
- Protected ingestion workflow run ID:

## Structural result

- Repository validation:
- Generated-state validation:
- Structural eval manifest:
- Native vendor manifest validation:
- Exceptions or skipped checks:

## Native-client smoke result

- Marketplace/catalog added:
- Pack installed:
- Exact discovered skills:
- Update tested:
- Removal tested:
- Residual files:
- Files written:
- Network endpoints contacted:
- Permission prompts:
- Unexpected behavior:

## Model-backed per-skill routing cases

| Case ID | Prompt reference | Expected skill | Observed skill | Pass | Notes |
|---|---|---|---|---|---|
| | | | | | |

## Model-backed routing-boundary cases

Record every canonical boundary incident to any skill in the selected pack. For an
`internal-pack` case, install the selected pack and make exactly the canonical `boundarySkills`
pair available to the model-backed run. For a `cross-pack` case, perform a separate clean run
with every canonical `installedPacks` entry and make the exact two `boundarySkills` available.
The selected pack's primary discovery result remains in `installation.discoveredSkills`; the
per-boundary fields describe the additional boundary environment.

| Boundary ID | Case ID | Scope | Boundary skills | Installed packs | Expected skills | Observed skills | Pass | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

## Model-backed behavior cases

| Case ID | Assertions met | Forbidden behavior absent | Permissions/effects as expected | Pass | Notes |
|---|---|---|---|---|---|
| | | | | | |

## Effects summary

- Filesystem reads/writes:
- Commands executed:
- Network effects:
- External-system effects:
- Secrets or credentials used (identify source, never value):
- Unexpected permissions or side effects:

## Conclusion

Do not mark compatible when a required check was skipped, the source SHA differs, a forbidden
behavior occurred, or an unexpected effect remains unexplained. Describe every skipped check
and failure. The corresponding machine-readable report is the release-gate source of truth.
