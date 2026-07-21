# Repository tools

Repository tools run from a source checkout without requiring an editable install. Start with
`python3 tools/bootstrap` on POSIX or `scripts/bootstrap.ps1` on Windows. Bootstrap creates the
isolated `.venv`, installs the hash-locked dependencies and local project, and populates the
isolated Rust harness cache. The `skillpacks` console command and `python -m skillpack_tools`
interface are then available through the virtual-environment interpreter.

| Command | Purpose |
|---|---|
| `bootstrap` | Create the cross-platform `.venv` and populate its locked Rust harness cache |
| `configure-repository` | Set owner and maintainer identity, then regenerate |
| `generate-all` | Regenerate every client adapter and catalog |
| `generate-catalogs` | Compatibility alias for atomic generation |
| `generate-installers` | Compatibility alias for atomic generation |
| `generate-readme` | Compatibility alias for atomic generation |
| `validate-repository` | Validate schemas, skills, links, scripts, evals, and generated files |
| `check-dco` | Validate terminal DCO signoffs for every commit in a Git range |
| `check-rust-assets [--pack PACK_ID]` | Check the full Rust workspace or one Rust pack member |
| `run-evals` | Validate routing and behavior eval specifications |
| `release-pack` | Rehearse a draft or build an evidence-gated deterministic pack release |

PowerShell contributors can use `scripts/check.ps1` for the full repository check and
`scripts/check-pack.ps1 PACK_ID` for a targeted development check. A targeted check never
replaces the full check before merge or release.

Generation aliases intentionally regenerate the complete derived graph. A partial generator
could leave marketplaces, installers, or checksums inconsistent after a manifest change.

Generation, validation, eval, and release tools do not contact the network. Dependency-lock
compilation and freshness checks may resolve packages through the configured package index.
`check-rust-assets --bootstrap` is the explicit exception: it fetches only the committed Cargo
lock's test-harness dependencies into the selected isolated Cargo home and never installs a Rust
toolchain. Ordinary `check-rust-assets` runs Cargo offline/frozen, builds only in temporary
directories, and verifies that canonical asset bytes and modes remain unchanged. Its default
scope checks the complete behavior workspace. `check-rust-assets --pack rust-cli-apps` checks
only that Rust pack's canonical assets, complete projects, and workspace member while retaining
the repository-wide inventory, workspace-mapping, Cargo-policy, mutation, and residue invariants.
Unknown and non-Rust pack IDs are rejected. Selection never installs or upgrades a toolchain.
`release-pack --draft` produces a clearly marked local rehearsal; publishable mode validates,
but never creates, a signed tag and never pushes or publishes anything.
