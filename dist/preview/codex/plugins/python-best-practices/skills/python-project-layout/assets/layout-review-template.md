# Python layout review

## Context

- Distribution name:
- Import package name(s):
- Package or application:
- Supported Python versions:
- Build backend and version:
- Namespace package:
- Entry points:
- Non-code package data:

## Observed tree

```text
Paste the relevant tree; omit build output and secrets.
```

## Findings

| Severity | Evidence | Consequence | Recommendation |
|---|---|---|---|
| | | | |

## Proposed target layout

```text
project/
├── pyproject.toml
├── src/
│   └── package_name/
└── tests/
```

## Migration sequence

1. <!-- Describe the first migration step. -->
2. <!-- Describe the second migration step. -->
3. <!-- Describe the third migration step. -->

## Verification evidence

- [ ] Source distribution built.
- [ ] Wheel built.
- [ ] Artifact installed in a clean environment.
- [ ] Import tested from outside the checkout.
- [ ] Tests run against the intended installed code.
- [ ] Console entry points exercised.
- [ ] Wheel contents inspected.

## Unverified assumptions and risks

-
