# Repository tools

All commands run from a source checkout without requiring an editable install. The
`skillpacks` console command is also available after `make bootstrap` installs the project
into the isolated `.venv` with `--no-deps`.

| Command | Purpose |
|---|---|
| `configure-repository` | Set owner and maintainer identity, then regenerate |
| `generate-all` | Regenerate every client adapter and catalog |
| `generate-catalogs` | Compatibility alias for atomic generation |
| `generate-installers` | Compatibility alias for atomic generation |
| `generate-readme` | Compatibility alias for atomic generation |
| `validate-repository` | Validate schemas, skills, links, scripts, evals, and generated files |
| `check-rust-assets` | Format-check, compile, and behavior-test classified Rust assets |
| `run-evals` | Validate routing and behavior eval specifications |
| `release-pack` | Rehearse a draft or build an evidence-gated deterministic pack release |

Generation aliases intentionally regenerate the complete derived graph. A partial generator
could leave marketplaces, installers, or checksums inconsistent after a manifest change.

Generation, validation, eval, and release tools do not contact the network. Dependency-lock
compilation and freshness checks may resolve packages through the configured package index.
`check-rust-assets --bootstrap` is the explicit exception: it fetches only the committed Cargo
lock's test-harness dependencies into the selected isolated Cargo home and never installs a Rust
toolchain. Ordinary `check-rust-assets` runs Cargo offline/frozen, builds only in temporary
directories, and verifies that canonical asset bytes and modes remain unchanged.
`release-pack --draft` produces a clearly marked local rehearsal; publishable mode validates,
but never creates, a signed tag and never pushes or publishes anything.
