# Distribution artifacts

This directory separates public, preview, and maintainer/development adapters from local
release archives.

- `public/`: the complete and only GitHub Pages upload root. It contains the landing page and,
  once releases exist, published installers and released OpenCode HTTP catalogs.
- `preview/`: current public candidates for CI artifacts only; Pages never uploads this tree.
- `dev/`: self-contained Claude, Codex, installer, catalog, and OpenCode development trees,
  including maintainer tooling.
- `generated-files.json`: hashes for every generated artifact.
- `releases/`: ignored local ZIP archives, checksums, and notes produced by
  `python3 tools/release-pack PACK_ID --draft`. A publishable build has additional clean-tree,
  signed-tag, tracked-input, and exact-SHA compatibility-evidence gates.

Run `make generate` after changing `repository.yaml`, a pack manifest, or
canonical skill content. CI uses `--check` and rejects stale generated output. Do not edit
`public/`, `preview/`, `dev/`, plugin manifests, marketplaces, `catalog.json`, or generated
README sections by hand.
