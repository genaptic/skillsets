# GitHub Pages

GitHub Pages serves only the deterministic `dist/public/` tree at
`https://genaptic.github.io/skillsets/`. It is a distribution surface, not a pack release or
native-client compatibility result.

## Generated site

`make generate` creates `dist/public/index.html` from the same public-release selector used for
`catalog.json`. The page lists only published public packs and labels their generated adapter
targets. Generation HTML-escapes
metadata and uses no JavaScript, external resource, timestamp, or other nondeterministic input.
`dist/generated-files.json` records the landing page's mode and checksum.

Each published card uses the authored pack short description and links the derived tag, exact
source commit, immutable release, direct `.zip.sha256` asset, and the repository attestation
verification surface. Those provenance links are absent when the public catalog is empty.

No current pack is published, so the Pages tree contains only the landing page and its “No stable
releases” banner. Unpublished installers and OpenCode catalogs must be absent, not merely unlinked.

## Deployment contract

The Pages workflow runs on pushes to `main` and manual dispatches from `main`. A preflight checks
the exact source ref before any repository code runs. The workflow installs the fully hashed
Python environment, checks generated output and strict repository validation, uploads exactly
`dist/public/`, and deploys through the secret-free `github-pages` environment.

Only the deploy job receives `pages: write` and `id-token: write`; all jobs otherwise need only
`contents: read`. Pages concurrency does not cancel an in-progress production deployment. The
deployment result supplies the environment URL. Configure Pages with workflow builds, no custom
domain, and a deployment branch policy restricted to `main`.

## Verification

Before the first release, require HTTP 200 for `/` and HTTP 404 for every formerly exposed
unpublished installer and OpenCode URL. The versioned denylist in
`tests/fixtures/pages-legacy-public-urls-v1.json` preserves URLs whose pack identity has since
changed, while the workflow adds every currently non-public pack dynamically. For each later
published entry, verify its index and every
declared file return 200. Distribution links stay relative to the Pages root; provenance links
must use the configured GitHub repository and exact release identifiers. The page loads no
external script or resource. Native compatibility still requires a fresh dated report for the
exact release SHA.
