# Python project layout checklist

## Identity and intent

- [ ] Repository, distribution, and import names are recorded separately.
- [ ] Library, application, plugin, or mixed purpose is explicit.
- [ ] Supported Python versions and platforms are documented.
- [ ] The reason for choosing flat or `src/` layout is tied to an actual failure mode.

## Packaging metadata

- [ ] `pyproject.toml` is valid TOML.
- [ ] `[build-system]` names the intended backend.
- [ ] `[project]` contains name, version source, description, readme, license, and
      `requires-python`.
- [ ] Runtime and development dependencies are not conflated.
- [ ] Dynamic fields have a reproducible source.
- [ ] Entry points resolve to importable callables.

## Discovery and files

- [ ] Package discovery searches the intended directory.
- [ ] Tests, examples, build output, and unrelated folders are excluded.
- [ ] Namespace package behavior is intentional.
- [ ] Package data is declared and accessed through package-resource APIs.
- [ ] Typing markers and stubs are included only when their contract is met.
- [ ] Import-time side effects are minimized.

## Tests and artifacts

- [ ] Tests do not rely on unexplained `sys.path` mutation.
- [ ] A source distribution and wheel build successfully.
- [ ] Artifact contents are inspected.
- [ ] The wheel installs in a clean environment.
- [ ] Imports work from outside the checkout.
- [ ] Tests and console entry points exercise the intended installed code.

## Migration safety

- [ ] File moves are separated from behavioral changes where practical.
- [ ] CI and documentation are updated.
- [ ] Obsolete files are removed only after verification.
- [ ] Rollback is a version-control revert, not an undocumented manual state.
