# Changelog

## [Unreleased]

### Added

- Prepared the `1.0.0` release-candidate contents for the `rust-best-practices` skillpack.
- Added `rust-core-best-practices`.
- Added `rust-project-architecture`.
- Added `rust-code-structure`.
- Added `rust-abstraction-design`.
- Added `rust-async-concurrency`.
- Added `rust-networking`.
- Added `rust-testing-strategy`.
- Added `rust-dependency-portability`.
- Added `rust-workspace-documentation`.
- Added `rustdoc-maintenance`.

### Changed

- Hardened the bearer-authenticated HTTP template with HTTPS-only transport, disabled redirects,
  URL-sanitized errors, and distinct decode classification.
- Corrected graceful-shutdown guidance so producer admission ends before `TaskTracker` close and a
  timed-out wait is never treated as task termination.

<!-- BEGIN RELEASE PREPARATION NOTE -->
`1.0.0` has not been published. Freeze the candidate and collect exact-SHA
native/model compatibility evidence before creating a release.
<!-- END RELEASE PREPARATION NOTE -->
