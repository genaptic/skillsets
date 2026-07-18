# Distribution artifacts

This directory separates generated client adapters from local release archives.

- `install/`: generated Bash and PowerShell direct installers. Each installs the exact skill
  paths declared by one pack. Published packs pin their tag/SHA; unpublished packs require an
  explicit reviewed repository ref.
- `opencode/`: generated OpenCode V2 HTTP catalogs and canonical runtime-resource copies.
- `generated-files.json`: hashes for every generated artifact.
- `releases/`: ignored local ZIP archives, checksums, and notes produced by
  `python3 tools/release-pack PACK_ID --draft`. A publishable build has additional clean-tree,
  signed-tag, tracked-input, and exact-SHA compatibility-evidence gates.

Run `make generate` after changing `repository.yaml`, a pack manifest, or
canonical skill content. CI uses `--check` and rejects stale generated output. Do not edit
`install/`, `opencode/`, plugin manifests, marketplaces, `catalog.json`, or generated README
sections by hand.
