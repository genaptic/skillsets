# Interrupted release recovery

Use the `Recover an interrupted skillpack release` workflow only after the normal release workflow
has stopped. It shares the pack-specific release concurrency group, and resume publication is
gated by the existing `release` environment. Inspection and removal guidance are read-only.

## Decide from the observed state

| Observed state | Action |
|---|---|
| Workflow failed before creating a draft | Correct the cause and rerun the normal release workflow. |
| Mutable draft contains only absent or byte-identical expected assets | Inspect, then use `resume-verified-draft`. |
| Verified mutable draft has an unexpected asset, mismatched digest/size, or no original release-workflow ZIP attestation | Do not resume. Generate a read-only removal dossier and use a separately authorized manual break-glass procedure. |
| Title, tag, source, target, or signer cannot pass protected inspection | This workflow performs no mutation. Preserve the inspection failure and use a separately reviewed incident procedure; do not weaken the recovery guard. |
| Release is published or immutable | Never resume or delete it. Preserve it, document the incident, and issue a corrected patch release. |

The normal workflow's failure-stage transitions are intentionally narrow:

| Failure stage | Expected remote state | Permitted next step |
|---|---|---|
| Evidence validation or ZIP-attestation verification | No draft | Correct the cause and rerun normally. |
| Draft-creation request | No known draft, or an uncertain API outcome | Inspect by numeric ID before any rerun; never assume creation failed. |
| Asset-free draft or partial upload | Mutable draft | Resume only after every source, signer, evidence, attestation, and byte check passes; otherwise prepare manual removal guidance. |
| Publish request failed before state changed | Mutable complete draft | Re-inspect and resume, or prepare manual removal guidance; never replace an asset. |
| Publish request succeeded but immutability verification failed | Published release | Preserve it and the tag; open an incident and use a corrected patch release. |
| Post-publication verification or reconciliation failed | Immutable release | Preserve it and the tag; finish read-only verification/reconciliation separately. |

GitHub's immutable-release sequence creates the ZIP attestation before the asset-free draft. A
recoverable draft must therefore already have a valid attestation for the rebuilt byte-identical
ZIP, signed by `.github/workflows/release.yml` from the protected default branch. Recovery never
creates a substitute attestation.

## Inspect first

Dispatch with:

- `mode=inspect-only`;
- exact pack ID and signed annotated tag;
- the numeric release ID, not only the tag.

Using only tooling installed from the exact protected dispatch-main commit, the workflow checks
out the requested tag as inert data, verifies that it is annotated, checks GitHub's signature
signal, and verifies the full signer fingerprint against the protected allowlist. It parses the
tagged lifecycle with protected code; it does not install or execute tagged code. The workflow
then retrieves `/releases/{release_id}`, compares the returned ID and tag, and uploads a
deterministic JSON inventory containing:

- the tag-object SHA, exact source SHA, signature type and full fingerprint;
- release title, body, target commitish, draft/prerelease/immutable state;
- the exact expected asset-name set; and
- observed asset IDs, names, sizes, upload states, server SHA-256 digests, and uploaders.

Inspection changes nothing.

## Resume a verified draft

Supply the three protected native-evidence run IDs and select `resume-verified-draft`. Recovery is
split across two jobs so tagged repository code never receives a write-capable token.

The read-only `resume-build` job runs before the release-environment gate. It has only
`actions: read`, `attestations: read`, and `contents: read`; it:

1. checks out protected dispatch-main policy and the exact tag into separate directories;
2. installs only protected policy tooling, then verifies tag/source identity, GitHub signature
   status, lifecycle, and the full repository signer allowlist before any tagged code runs;
3. installs the signed tag tooling only after those trust checks and reruns every immutable-source
   repository check from the release-source directory;
4. retrieves each evidence artifact by exact workflow run and artifact ID, validates provenance,
   verifies report and envelope attestations, rechecks freshness, and proves the ancestry chain
   `release source -> evidence commit -> protected dispatch main`;
5. rebuilds the deterministic archive, checksum, release notes, and expected evidence assets;
6. verifies the rebuilt ZIP against the original release-workflow attestation;
7. requires exact draft title/body and refuses unknown, incomplete, or digest/size-mismatched
   existing assets; and
8. seals the archive, checksum, release notes, evidence files, inspection, and resume plan in an
   exact-inventory, hash-manifested workflow artifact.

Only then can the `resume` mutation job enter the protected `release` environment. It receives
`contents: write`, but never installs or executes the tagged package. Using tooling from the exact
protected dispatch-main commit, it:

1. downloads the one same-run `resume-build` artifact by exact ID and name;
2. compares the upload action's digest with the REST artifact digest and the downloaded ZIP bytes,
   then safely extracts only the expected regular files;
3. revalidates protected-main ancestry, GitHub's signature signal, the full signer fingerprint,
   tagged lifecycle identity, every sealed file hash, the original ZIP attestation, and the exact
   release title/body;
4. re-reads the draft by numeric ID immediately before mutation and recomputes the resume plan, so
   an intervening asset or state change fails closed;
5. uploads only still-missing assets, without `--clobber`, then requires an exact complete
   inventory and uploads a sealed release intent before publication; and
6. publishes by numeric release ID and requires the immutable release, metadata, and complete
   asset inventory to equal that sealed intent.

After a successful resume, `publication-handoff.yml` independently re-verifies the immutable
release and prepares the publication record, reviewed update patch, and marker-bound tracking
issue. The handoff can be retried without rerunning or modifying the release.

Any failed comparison in either job is a stop condition. Do not work around it by replacing an
asset or by moving tagged execution into the mutation job.

## Prepare manual removal guidance

Select `prepare-draft-removal`. The workflow requires the same successful protected inspection,
then emits deterministic JSON and Markdown dossiers containing the numeric release ID, verified
tag identity, mutable-draft state, and exact observed assets. It has read-only permissions and does
not authorize or perform deletion.

GitHub does not document an `If-Match` or other compare-and-swap precondition for release deletion.
An automated inspect-then-delete sequence therefore cannot prove the release remained a draft
between those calls. Any removal is a separately authorized human break-glass action: re-read the
numeric release immediately before acting, confirm it is still the same mutable draft, preserve the
signed tag, and retain the dossier with the incident record. Published or immutable releases are
never removal candidates.

## Governance boundary

Recovery does not authorize publishing a new version, moving a tag, overwriting an asset, relaxing
evidence freshness, changing signer trust, or editing a published release. Those are separate
security/release decisions. Preserve the inspection and recovery-plan artifacts with incident
notes whenever a draft is suspicious.
