# Changelog

## [Unreleased]

### Added

- Prepared the unpublished `1.0.0` release candidate with
  `genaptic-skillsets-create-skill` and `genaptic-skillsets-create-skillpack`.
- Added complete normalized request contracts, preview-digest scaffold helpers, design and
  completion assets, primary-source references, and routing and behavior evaluations.

### Changed

- Clarified that `genaptic-skillsets-create-skillpack` owns every new independently
  installable pack, including a coherent one-skill pack, while
  `genaptic-skillsets-create-skill` owns one new skill in an existing pack.
- Replaced duplicated per-skill overlap cases with canonical four-outcome root routing
  boundaries and updated both authoring workflows to maintain that shared graph.

<!-- BEGIN RELEASE PREPARATION NOTE -->
`1.0.0` has not been published. Before requesting exact-SHA native/model evidence, freeze
the candidate by moving these notes under `## [1.0.0]` and removing release-candidate
wording. The protected release gate runs only after that frozen commit passes evidence.
<!-- END RELEASE PREPARATION NOTE -->
