# Python project layout guide

## Separate three names

A Python project often has three related but different identifiers:

- The **repository** name used by source control.
- The **distribution** name installed by a package installer.
- One or more **import package** names used by Python code.

Record them separately. Hyphens are valid in distribution names but not in normal import
statements. A review that assumes all three names are identical can misdiagnose package
discovery and entry points.

## Choose layout from failure modes

A `src/` layout creates a useful boundary: running Python from the checkout root does not
automatically make the package importable merely because the directory is present. This
helps detect missing packaging configuration and tests that accidentally exercise the
working tree rather than an installed artifact.

A flat layout can be reasonable for a small private application or a repository whose
execution model never produces a distribution. The decision should be explicit. Do not
recommend a migration solely because one layout is fashionable; identify the concrete
failure it prevents.

Avoid mixing import packages at the root and under `src/` unless the build configuration and
migration state make the intent clear.

## Make `pyproject.toml` authoritative

Review these layers independently:

1. `[build-system]` identifies the backend and the dependencies needed to invoke it.
2. `[project]` provides standardized package metadata.
3. Backend-specific tables define package discovery and package data.
4. Tool tables configure test, type, lint, and other development tools.

Do not copy backend-specific keys between setuptools, Hatchling, Flit, PDM, Poetry, or other
backends. Confirm the selected backend's documentation.

Declare `requires-python` from the supported runtime contract, not from the maintainer's
local interpreter. Keep runtime dependencies separate from optional development groups.

Use dynamic metadata only when a build-time source is intentional and reproducible. Review
where a dynamic version comes from and whether an isolated build has access to it.

## Package discovery must match the tree

Confirm:

- The backend searches the intended root, such as `src/`.
- Include and exclude patterns do not capture tests, examples, generated files, or unrelated
  top-level directories.
- Namespace package behavior is intentional.
- A single-module distribution is configured differently from a package directory where
  necessary.
- Editable installation and wheel installation resolve the same import package.

Do not treat a successful import from the repository root as packaging evidence.

## Keep public and internal code boundaries visible

A package root should expose only the stable public surface it intends to support. Internal
modules can use a leading underscore, but the stronger contract is documentation and tests
against public imports.

Avoid large `__init__.py` files that trigger expensive imports or create circular
dependencies. Re-export deliberately. Use `__all__` only when it serves a defined public
surface; it does not by itself create API stability.

## Tests and non-code files

Keep tests outside the import package unless tests are intentionally distributed. Test
through public behavior and verify whether the suite runs against an installed artifact or
the checkout.

Load packaged data with `importlib.resources` rather than paths relative to the current
working directory. Check both source-distribution and wheel contents. Include `py.typed`
only when the package meets the typing marker's contract.

## Entry points

Console scripts should point to a small callable that returns or maps to a process status.
Keep import-time side effects out of entry-point modules. Exercise the installed command,
not only `python path/to/script.py`.

## Migration strategy

Prefer a staged migration:

1. Establish an authoritative `pyproject.toml`.
2. Move or identify one import package at a time.
3. Update package discovery.
4. Update test imports without adding checkout-only path hacks.
5. Build and inspect artifacts.
6. Install into a clean environment.
7. Run tests and entry points from outside the checkout.
8. Remove obsolete configuration only after equivalence is demonstrated.

Do not combine a layout migration with unrelated API refactors when separation is possible.

## Verification commands

Commands depend on the selected backend and existing toolchain. Typical evidence includes:

```bash
python -m build
python -m pip install --no-deps --force-reinstall dist/*.whl
python -c "import package_name; print(package_name.__file__)"
python -m pytest
```

These are examples, not authorization to install dependencies or modify a shared
environment. Use a disposable virtual environment and the repository's documented commands.
