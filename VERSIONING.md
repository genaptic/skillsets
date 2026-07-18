# Versioning policy

Each skillpack is versioned independently with Semantic Versioning. The pack version is the
public compatibility contract for its manifest, skill identifiers, expected behavior, and
installation source.

## Version changes

- **Patch**: corrections, clearer routing language, safer procedures, improved references,
  additional compatible evals, or implementation fixes that preserve the public contract.
- **Minor**: a new backward-compatible skill, a new optional helper, or an additive output
  capability.
- **Major**: a removed or renamed skill, a materially changed workflow or output contract,
  broader permissions, new required tooling, or a change that can surprise existing users.

Release tags have the form `<pack-id>-v<version>`, for example
`python-best-practices-v1.0.0`. Direct installers must pin that pack-specific tag or a full
commit SHA. Unpinned installs are intentionally not documented because the latest repository
tag can belong to a different pack.

Skill identifiers are public API. Prefer deprecation and migration notes over renaming.

## Release-candidate and publication state

A manifest version does not prove publication. Before the first protected release, a pack
may carry its intended `1.0.0` manifest version while its catalog publication state remains
`unpublished`; documentation must call it a release candidate and must not imply its tag or
public install source exists.

After a protected release succeeds, record the exact released commit as `source-sha` in the
pack manifest. Regeneration then replaces repository-local marketplace sources with
published `git-subdir` sources pinned by pack tag and full SHA. Never add a guessed SHA or
reuse a released tag.
