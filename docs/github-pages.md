# GitHub Pages

GitHub Pages serves the deterministic `dist/` tree at
`https://genaptic.github.io/skillsets/`. It is a distribution surface, not a pack release or
native-client compatibility result.

## Generated site

`make generate` creates `dist/index.html` from the same discovered pack model used for
`catalog.json`. The page lists every pack's display name, ID, version, description, publication
state, supported targets, and repository-relative OpenCode index. Generation HTML-escapes
metadata and uses no JavaScript, external resource, timestamp, or other nondeterministic input.
`dist/generated-files.json` records the landing page's mode and checksum.

All six current packs are version `1.0.0` and unpublished. The page must describe that state
accurately; a hosted index does not create a pack tag or release and does not establish that a
native client or model passed.

## Deployment contract

The Pages workflow runs on pushes to `main` and manual dispatches from `main`. A preflight checks
the exact source ref before any repository code runs. The workflow installs the fully hashed
Python environment, checks generated output and strict repository validation, uploads all of
`dist/`, and deploys through the secret-free `github-pages` environment.

Only the deploy job receives `pages: write` and `id-token: write`; all jobs otherwise need only
`contents: read`. Pages concurrency does not cancel an in-progress production deployment. The
deployment result supplies the environment URL. Configure Pages with workflow builds, no custom
domain, and a deployment branch policy restricted to `main`.

## Verification

After deployment, require HTTP 200 for `/` and valid JSON at:

- `/opencode/python/best-practices/index.json`
- `/opencode/python/cli-apps/index.json`
- `/opencode/rust/best-practices/index.json`
- `/opencode/rust/cli-apps/index.json`
- `/opencode/shared/postgres-databases/index.json`
- `/opencode/shared/repository-development/index.json`

Also confirm that the landing page names all six packs, contains only relative repository links,
and loads no external script or resource. Set the repository homepage only after this verification
succeeds. A future OpenCode publication still requires a dated passing report for the exact pack
source SHA.
