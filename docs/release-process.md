# Release process

Every pack releases independently.

## Preconditions

- `repository.yaml` has no identity placeholders.
- The pack changelog has no unreleased ambiguity.
- The manifest version is the intended Semantic Version.
- All generated files are committed.
- Structural validation, eval validation, tests, lint, and generated-state checks pass.
- Security-sensitive changes have maintainer approval.

Draft rehearsals and publishable releases have deliberately different gates.

Before collecting exact-SHA compatibility evidence, freeze the candidate commit: finalize
the pack changelog, change the canonical pack maturity and every included skill mirror to
`stable`, and replace the pack
README's release-candidate wording with final release wording. Evidence is collected against
that immutable commit. Do not wait for the release workflow to finalize those files—the
workflow intentionally rejects unresolved release state.

## First-release canary and approval checkpoint

`python-best-practices` is the sole first-release canary. Do not prepare another pack for
publication in parallel. Before the checkpoint:

1. Preview `skillpacks prepare-release python-best-practices --release-date YYYY-MM-DD`, review
   its plan digest, and apply that unchanged plan.
2. Land the stable but still unpublished candidate on protected `main`, then run generation and
   the complete check from clean checkouts.
3. Build two local draft rehearsals and require byte-identical ZIPs, metadata, checksums, and
   notes.
4. Collect and ingest fresh exact-SHA Claude Code, Codex, and OpenCode evidence, including exact
   discovery of the three canary skills and every declared routing/behavior case. The OpenCode
   native canary must use released OpenCode v1.18.3 and its `skills.urls` protocol.
5. Verify the evidence envelopes, attestations, workflow/run identities, ancestry, and 45-day
   freshness. Confirm publication reconciliation would expose only this pack.
6. Produce a go/no-go dossier recording the expected tag, exact source SHA, accepted signer
   fingerprint, three evidence run/artifact identities, expected asset inventory, recovery
   readiness, and exact expected publication-update plan.

**Stop immediately after the dossier, before creating or signing the tag.** Preparation does not
authorize `git tag`, a tag push, a draft GitHub release, release publication, or a public Pages
change. Resume only after separate explicit approval.

After approval and publication, verify install/update/remove behavior from clean environments for
all three clients, every HTTP object and checksum, release immutability, and provenance. Keep
`python-best-practices` under observation for at least seven calendar days **and** through at least
one complete reconciliation cycle (whichever finishes later). A P0/P1 fault requires withdrawal
from public adapters and a corrected patch release; never move the tag or replace the release.
Stop before preparing pack two.

## Draft rehearsal

Run `make bootstrap` before the rehearsal to install the hashed Python development graph and
explicitly fetch the locked Rust behavior-harness graph into the repository-local Cargo cache.
Bootstrap uses an already-installed Rust toolchain and never installs or upgrades one.
`make check`/`make rust-check` then exercise that locked graph offline; a missing cache is an
unavailable prerequisite, not permission to fetch during the check.

```bash
make bootstrap
make generate
make check
.venv/bin/python tools/release-pack PACK_ID --draft
```

Draft mode:

- Validates the entire repository.
- Builds a clearly marked, deterministic local rehearsal from an explicit safe allowlist.
- Includes only canonical pack files plus approved license and notice material.
- Embeds a schema-valid deterministic `RELEASE-METADATA.json`; draft metadata makes no signer or
  compatibility claim.
- Writes a SHA-256 checksum and release-note draft.
- Does not create a tag, push, or contact GitHub.
- Does not imply publication or client/model compatibility.

Build each draft twice and require byte-identical archives and checksums. Review files under
`dist/releases/`.

## Publishable build gate

`python3 tools/release-pack PACK_ID --policy-root /path/to/protected-main` is allowed only when
all of these are true. The policy root must be a separate checkout of the current protected
default-branch commit; signer trust, repository identity, reviewer authorization, freshness, and
both compatibility schemas come from that checkout rather than the tag:

- The Git working tree is clean; every allowlisted input is tracked.
- The public pack and all skill mirrors are `stable`, and each mirrored pack ID/version/maturity
  equals the canonical manifest.
- The exact expected annotated, signed `<pack-id>-v<version>` tag points at `HEAD`, and its actual
  full SSH/OpenPGP fingerprint is present in `repository.yaml`.
- Fresh, schema-v2 passing reports cover Claude Code, Codex, and OpenCode for the exact source SHA,
  including native installation and model-backed behavior evidence. Each raw report is paired with
  a workflow-controlled provenance envelope, Sigstore bundle, and exact ingestion run/artifact
  identity.
- No unresolved release placeholders or release-candidate claims remain.
- Generated files are current and the archive contains only the explicit canonical, generated
  plugin, compatibility-inventory, and root-policy allowlist; it contains no arbitrary ignored or
  untracked input, cache, secret, or editor residue.

The tool must reject a build when any condition is absent. It does not create or push the
tag and does not contact GitHub.

## Tag and final local build

After exact-SHA compatibility evidence passes, create the signed annotated tag locally and
run the evidence-gated build. Repository-specific SSH signing must already be configured as
described in `docs/maintainer-signing.md`:

```bash
git tag -s PACK_ID-vX.Y.Z -m "PACK_ID vX.Y.Z"
python3 tools/release-pack PACK_ID --policy-root /path/to/protected-main
```

Do not push the tag during local preparation. Tag push and release publication belong to the
remote-publication plan.

Do not try to place the commit's own SHA in the tagged commit: Git object identifiers are
content-derived, so that would be self-referential. The release workflow records the exact
checked-out SHA in the release notes. After publication, the generated publication record drives
a protected-main update of `publication.state` and `publication.latest-release`, including that
already-known 40-character SHA, release ID, and timestamp. Generation then materializes public
`git-subdir` sources from the exact released Git snapshot. The pack-specific tag remains the
primary source reference in the tagged release.

## Publish

Dispatch the protected manual workflow only from `main`. The candidate SHA referenced by its
signed tag may legitimately predate the current `main`, but the workflow definition and dispatch
must come from the protected default branch. The workflow derives and validates the pack ID,
verifies both GitHub and local tag signatures, requires exact-SHA compatibility evidence, runs
all checks, and rebuilds the allowlisted archive. The five-minute `release` environment applies
only to the publication job; exact-tag Rust validation does not consume a second wait.

Publication is fail-closed and ordered:

1. Refuse to continue if any release already exists for the tag.
2. Create an asset-free draft with tag verification enabled.
3. Upload the pack ZIP, `.sha256` checksum, and exact Claude Code, Codex, and OpenCode report,
   provenance-envelope, and attestation-bundle trios without overwriting an existing asset.
4. Re-read the draft by numeric release ID, seal its exact metadata and asset inventory in a
   strict release-intent artifact, and preserve that artifact before publication.
5. Publish through the numeric release-ID REST endpoint.
6. Retry for bounded immutable-release attestation availability, then require the published
   release and paginated asset inventory to match the sealed intent exactly.
7. Verify every local asset, the ZIP provenance, and the immutable-release attestation again.
8. Let `publication-handoff.yml` independently reverify current policy and the immutable release,
   then create the publication record, reviewed patch, and marker-bound tracking issue. This
   handoff is retryable without modifying or rerunning the release.

The publication job alone receives `contents: write`, `id-token: write`, and
`attestations: write`. Only the handoff notification job receives `issues: write`; it has no
content or attestation mutation permission. The ZIP attestation must bind the repository, signer
workflow, and a GitHub-hosted runner. A failure after draft creation deliberately leaves an
unpublished draft. Follow [`release-recovery.md`](release-recovery.md): inspect by numeric release
ID, resume only a mutable draft whose existing assets and original release-workflow ZIP
attestation verify exactly, or prepare a read-only manual-removal dossier. No workflow deletes a
release, overwrites an asset, or changes a tag. Immutable releases must be enabled before the first
pack publication.

Publication metadata is reconciled in a separate protected commit using the generated record and
patch. See [`publication-reconciliation.md`](publication-reconciliation.md). The scheduled
read-only reconciliation workflow reports release/manifest drift but never mutates either side.
The released record can legitimately be older than a newer candidate in the manifest; it cannot
supersede an already newer `latest-release`.

## Verify after publication

After publication, verify from a clean environment:

- Add the Claude marketplace and install the pack.
- Add the Codex marketplace and install the pack.
- When `gh skill --help` and `gh skill install --help` are available, run the optional generated
  direct installer for OpenCode. Otherwise record the adapter as unavailable and use the
  separately authorized native OpenCode installation path; never convert unavailability into
  a pass.
- Confirm exact discovered skill names.
- Exercise at least one positive and one negative routing case.
- Confirm update and uninstall instructions.
- Verify the downloaded archive checksum.
- Run `gh release verify`, `gh release verify-asset` for every asset, and
  `gh attestation verify` for the ZIP.

If verification fails, do not move or overwrite the tag. Correct the issue in a new patch
release. Revoke or mark a compromised release clearly and follow `SECURITY.md`.

Repository infrastructure setup does not publish a pack. Five reusable public `1.0.0` packs are
currently unpublished release candidates; the separate maintainer-only development pack is also
unpublished but is ineligible for formal release.
