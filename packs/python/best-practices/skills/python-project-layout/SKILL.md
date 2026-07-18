---
name: python-project-layout
description: >
  Design or review Python repository and packaging layout, including pyproject.toml, src versus flat layout, package discovery, tests, data files, typing markers, and entry points. Use when imports, builds, editable installs, or publication structure are in question. Do not use for test-case architecture or CLI user-interface design.
license: Apache-2.0
metadata:
  skillpack: "python-best-practices"
  version: "1.0.0"
  maturity: "release-candidate"
---

# Outcome

Produce a concrete, reviewable result for the workflow below without overstating what was
observed, executed, or verified.

## Compatibility

Portable across Claude Code, Codex, and OpenCode. The optional inspector requires Python 3.11
and reads local files only. Packaging commands depend on the project's selected build backend
and are never installed or run implicitly.

## Use this skill when

- A new Python library or application needs an intentional repository and package layout.
- Imports behave differently in the checkout, editable install, wheel, or test environment.
- Legacy packaging files need consolidation into an authoritative `pyproject.toml`.
- Package discovery, data files, type markers, namespace packages, or entry points may be wrong.

## Do not use this skill when

- The repository layout is settled and the task is to design unit, integration, or end-to-end tests; use `python-testing-strategy`.
- The task is command names, flags, help, or CLI configuration precedence; use `python-cli-command-design`.
- The task is runtime service architecture, deployment topology, or framework selection.

## Inputs

Inspect or obtain:

- Relevant repository tree, excluding secrets and generated environments.
- `pyproject.toml` and any `setup.py`, `setup.cfg`, manifest, lock, or tool configuration.
- Repository, distribution, and import package names.
- Library/application purpose, supported Python versions, build backend, and publication target.
- Namespace-package, entry-point, packaged-data, and typing requirements.
- Current build, install, import, and test commands plus observed failures.

When an input is unavailable, label the assumption and explain how it affects confidence.
Ask for clarification only when proceeding would create a material safety or correctness
risk.

## Safety posture

- Begin with read-only inspection; do not move or delete files before presenting a migration map.
- Do not install build tools, change an environment, or contact a package index without approval.
- Use a disposable virtual environment for build/install verification and avoid shared interpreter state.
- Treat the helper's findings as heuristics; it does not execute the backend or resolve namespace packages.

Use the sequence **inspect → explain → propose → approve when required → apply → verify**.
Never describe a proposed or unexecuted check as successful.

## Procedure

1. **Establish identity and purpose.** Record repository, distribution, and import names separately. Classify the project as a library, application, plugin, namespace distribution, or mixed repository and state the supported Python range.

2. **Inventory the actual tree and configuration.** Inspect packaging files, import roots, tests, scripts, data, generated output, and path manipulation. Note contradictions before proposing a target.

3. **Choose the import boundary.** Compare flat and `src/` layouts against concrete risks such as accidental checkout imports, publication, multiple packages, and operational simplicity. State why the selected layout fits.

4. **Make packaging metadata authoritative.** Define the build backend, standardized project metadata, version source, Python requirement, dependencies, optional groups, entry points, and backend-specific discovery without copying keys from another backend.

5. **Define package discovery and API boundaries.** Identify package roots, namespace behavior, single-module cases, public imports, internal modules, and import-time side effects. Exclude tests and unrelated directories.

6. **Place tests and resources intentionally.** Keep undistributed tests outside the package, avoid unexplained path injection, declare package data, use package-resource APIs, and include typing markers only when valid.

7. **Plan a small migration.** Separate moves from behavior changes, update discovery and imports in stages, preserve a version-control rollback, and remove obsolete packaging files only after equivalent artifacts pass.

8. **Verify the artifact rather than the checkout alone.** Build source and wheel artifacts with the repository's approved toolchain, inspect contents, install in a clean environment, import from outside the checkout, and exercise tests and entry points.

9. **Report evidence and residual risk.** Identify checks executed, checks only proposed, backend/version assumptions, and any namespace or platform behavior still requiring confirmation.

## Verification

Before claiming completion:

- The target tree and package-discovery rules agree.
- Standardized metadata and backend-specific configuration are valid for the selected backend.
- A source distribution and wheel can be built, or the exact reason this was not run is stated.
- Artifact contents include intended modules, data, typing files, and entry points and exclude unintended files.
- A clean installation imports from the installed location outside the checkout.
- Tests and entry points pass against the intended code path, or remaining failures are reported.

## Output contract

Return:

- Context, names, constraints, and labeled assumptions.
- Observed tree/configuration findings ordered by consequence.
- Target layout and packaging configuration with rationale.
- Staged migration sequence and rollback point.
- Commands proposed or executed, with environment boundaries.
- Verification evidence, skipped checks, and remaining risks.

Distinguish **observed**, **inferred**, **proposed**, **executed**, and **verified** work.

## Resources

- [Detailed guide](references/guide.md)
- [Review checklist](references/checklist.md)
- [Primary sources](references/sources.md)
- [pyproject-src-layout.example.toml](assets/pyproject-src-layout.example.toml)
- [layout-review-template.md](assets/layout-review-template.md)
- [inspect_layout.py](scripts/inspect_layout.py)
- [Routing and behavior evals](evals/evals.json)
