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
the pack changelog, change each included skill's maturity to `stable`, and replace the pack
README's release-candidate wording with final release wording. Evidence is collected against
that immutable commit. Do not wait for the release workflow to finalize those files—the
workflow intentionally rejects unresolved release state.

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
- Writes a SHA-256 checksum and release-note draft.
- Does not create a tag, push, or contact GitHub.
- Does not imply publication or client/model compatibility.

Build each draft twice and require byte-identical archives and checksums. Review files under
`dist/releases/`.

## Publishable build gate

`python3 tools/release-pack PACK_ID` is allowed only when all of these are true:

- The Git working tree is clean; every allowlisted input is tracked.
- The exact expected annotated, signed `<pack-id>-v<version>` tag points at `HEAD`.
- Dated, schema-valid passing reports cover Claude Code, Codex, and OpenCode for the exact
  source SHA, including native installation and model-backed behavior evidence.
- No unresolved release placeholders or release-candidate claims remain.
- Generated files are current and the archive contains only the explicit canonical, generated
  plugin, compatibility-inventory, and root-policy allowlist; it contains no arbitrary ignored or
  untracked input, cache, secret, or editor residue.

The tool must reject a build when any condition is absent. It does not create or push the
tag and does not contact GitHub.

## Tag and final local build

After exact-SHA compatibility evidence passes, create the signed annotated tag locally and
run the evidence-gated build:

```bash
git tag -s PACK_ID-vX.Y.Z -m "PACK_ID vX.Y.Z"
python3 tools/release-pack PACK_ID
```

Do not push the tag during local preparation. Tag push and release publication belong to the
remote-publication plan.

Do not try to place the commit's own SHA in the tagged commit: Git object identifiers are
content-derived, so that would be self-referential. The release workflow records the exact
checked-out SHA in the release notes. After publication, a two-step catalog update records
that already-known 40-character SHA as `source-sha`, regenerates the marketplaces as
published `git-subdir` sources, and commits the pin on the default branch. The pack-specific
tag remains the primary source reference in the tagged release.

## Publish

The protected manual release workflow verifies the tag signature, derives and validates any
pack ID rather than using a hard-coded allowlist, requires exact-SHA compatibility evidence,
runs all checks, rebuilds the archive, and creates a GitHub release using the repository
token with contents write permission. It never publishes from a pull request.

Attach:

- Pack ZIP.
- `.sha256` checksum.
- Release notes.
- Exact-SHA compatibility reports.

## Verify after publication

Remote publication, Pages activation, tag push, release creation, and repository protection
changes are deferred to the next plan. When that plan runs, verify from a clean environment:

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

If verification fails, do not move or overwrite the tag. Correct the issue in a new patch
release. Revoke or mark a compromised release clearly and follow `SECURITY.md`.
