# Roadmap

The first stable scope covers Python and Rust engineering, their command-line applications,
PostgreSQL databases, and Genaptic Skillsets development workflows for safely adding future
skills and skillpacks. Five reusable public packs remain unpublished release candidates. The
Genaptic Skillsets development pack remains unpublished maintainer tooling and is not a formal
release candidate.

Potential later packs include:

- `python-docs`
- `python-microservices`
- `typescript-best-practices`
- `typescript-cli-apps`
- `typescript-microservices`
- `go-best-practices`
- `go-cli-apps`
- `go-microservices`

A roadmap item is not a compatibility promise. New packs should be added only when there is
a maintainer with domain expertise, one or more non-overlapping focused skills, source-backed
guidance, eval coverage, and a clear distribution owner.

Near-term repository improvements:

- Prepare only `python-best-practices` as the first canary, stop at the documented pre-tag
  go/no-go checkpoint, and publish only after separate approval.
- Observe that canary for at least seven calendar days and one complete reconciliation cycle,
  whichever is longer, then stop for review before preparing pack two.
- Record protected native-client and model-backed reports for later public release candidates
  only after the canary checkpoint succeeds.
- Exercise the Rust skills against repositories with different MSRV, workspace, feature,
  lockfile, target, and CI policies without treating one Cargo command as universal.
- Forward-test the Genaptic Skillsets development routing boundary against real one-skill and
  new-pack proposals without treating structural evals as model evidence.
- Add signed provenance and SBOM generation for release archives.
- Publish the generated OpenCode catalogs only in the separate remote-publication plan.
- Add deprecation metadata and migration automation before the first public rename.
