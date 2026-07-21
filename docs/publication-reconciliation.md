# Publication reconciliation

GitHub's immutable release is the external publication event. The canonical pack manifest is
updated only in a later reviewed commit, so a successful release deliberately creates a short,
observable reconciliation interval.

The release and recovery workflows seal and upload a strict release-intent artifact before
publishing, then stop only after the exact immutable release matches that intent.
`publication-handoff.yml` runs from protected main on completion of either workflow, regardless of
its conclusion. It can also be dispatched manually with an exact pack, tag, and numeric release ID
when an upstream artifact expired or a prior handoff failed. The handoff independently verifies
the current signer and evidence policy, tagged lifecycle, exact release and assets, archive
metadata, checksums, and attestations before producing:

- a deterministic publication-update plan bound to the exact protected-default-branch
  `baseCommit`, manifest preimage, complete generated-output digest set, changed-file preimage and
  postimage digests, and exact full-index binary patch;
- that exact reviewed patch as a separate artifact for ordinary branch application and review.

The workflow never pushes that patch and never opens a pull request. A separate least-privilege
job with `issues: write` creates, refreshes, or closes one idempotent tracking issue keyed by
numeric release ID and tag. If the exact publication record is already canonical, the handoff
emits `already-reconciled` and closes the issue. A maintainer otherwise reviews the artifact,
applies it on a branch, runs the required repository checks, and uses the normal protected review
and merge path. The tagged changelog is final and must not be edited during reconciliation.

The plan is read-only by default. Applying it requires the exact digest printed by the unchanged
preview:

```bash
python -m skillpack_tools.publication prepare \
  --root . --record /trusted/path/publication-record.json \
  --output /tmp/publication-plan.json

python -m skillpack_tools.publication prepare \
  --root . --record /trusted/path/publication-record.json \
  --output /tmp/applied-plan.json --apply --plan-digest SHA256_FROM_PREVIEW
```

Preview and apply require a clean worktree whose HEAD exactly equals the record's `baseCommit`,
with generated outputs already current. The record must identify this repository, a non-draft
non-prerelease immutable release, the exact tag source SHA, and a canonical UTC publication
timestamp. Its tag and URL are derived from the record's released version. That version may be
older than the current candidate, but it may not be newer than the candidate or precede an
existing `latest-release`; this preserves a newer candidate while recording the release that
actually occurred.

Preview generates and validates the update in an isolated checkout of `baseCommit`. Apply
recomputes the unchanged plan, requires its digest, regenerates and validates the repository,
then compares the actual patch and every generated-output digest with the reviewed plan. A
generation, validation, digest, or patch mismatch restores the manifest and all planned generated
files to their pre-apply bytes and modes before returning failure.

`publication-reconcile.yml` independently runs on a schedule or manual dispatch. Automatic
post-publication work uses `workflow_run` in the handoff because events created with the release
workflow's `GITHUB_TOKEN` do not reliably trigger another release-event workflow. The durable
reconciler has `contents: read` only. It compares normalized GitHub release records with pack
manifests, uploads a machine-readable drift report, and fails when either side is missing or when
release ID, source SHA, timestamp, publication state, prerelease state, tag verification, or
immutability disagrees. Reconciliation matches the recorded `latest-release` tag independently
from a newer current candidate tag, so advancing a candidate does not make published history look
missing. A remotely published current candidate is reported separately until its record is
reconciled. The workflow does not modify manifests, releases, Pages, issues, or pull requests.
