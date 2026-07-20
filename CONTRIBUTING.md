# Contributing

Contributions are welcome when they keep skills portable, narrowly routed, verifiable, and
unsurprising.

## Start here

1. Read `CODE_OF_CONDUCT.md`, `docs/architecture.md`, `docs/authoring.md`, and
   `docs/threat-model.md`.
2. Search existing issues and skills for overlap.
3. Use `$genaptic-skillsets-create-skill` for one new skill in an existing pack. Use
   `$genaptic-skillsets-create-skillpack` for a new independently installable pack, several
   coordinated skills, or a capability with no coherent existing owner.
4. Validate the selected workflow's normalized request, review its scaffold preview, and
   apply only the unchanged plan digest. For a new pack or broad behavioral change, open a
   proposal issue before a large pull request.
5. Bootstrap from the repository root with `python3 tools/bootstrap` on POSIX or
   `./scripts/bootstrap.ps1` in PowerShell on Windows. The standard-library bootstrap creates an
   isolated Python 3.11-or-newer `.venv`, installs the fully pinned and hashed development lock,
   installs this project with `--no-deps`, and explicitly fetches the locked Rust behavior-harness
   dependency graph into the repository-local Cargo cache. It uses an already-installed Rust
   toolchain and never installs or upgrades one.
6. Run `.venv/bin/python -m skillpack_tools generate` after source changes on POSIX; use
   `.venv\Scripts\python.exe -m skillpack_tools generate` on Windows. Before opening the pull
   request, run `.venv/bin/python -m skillpack_tools check` on POSIX or
   `./scripts/check.ps1` on Windows. The full check uses the populated Cargo cache offline.
   `./scripts/check-pack.ps1 PACK_ID` is a faster Windows development check, but never replaces
   the full check before merge or release.

## Naming

Use lowercase kebab-case.

- Pack: `<language-or-domain>-<subject>`, such as `python-cli-apps`.
- Skill: globally unique, outcome-oriented, and specific, such as
  `postgres-query-performance-review`.
- Directory name: exactly equal to the skill's frontmatter `name`.
- Public names are API. Do not rename them for style alone.

Avoid vague names such as `testing`, `docs`, `review`, or `best-practices`.

## Skill requirements

Every skill must include:

```text
SKILL.md
agents/openai.yaml
references/guide.md
references/checklist.md
references/sources.md
evals/evals.json
```

Add `assets/` only for reusable templates or examples and `scripts/` only for deterministic,
documented helpers. Do not add empty directories or placeholder README files.

`SKILL.md` must:

- Use only the portable frontmatter fields `name`, `description`, `license`, and
  string-valued `metadata`.
- Define what it does, when it should activate, and when it should not activate.
- Identify necessary inputs and state assumptions.
- Prefer inspection and reversible steps before mutation.
- Distinguish recommendations from verified facts.
- Define an output contract and verification procedure.
- Link to focused references rather than becoming a long handbook.
- Avoid hidden downloads, package installation, credential requests, and implicit
  destructive actions.
- Put detailed runtime/client requirements in a concise `Compatibility` section and the
  pack manifest, not in vendor-specific frontmatter.

`agents/openai.yaml` must provide a human-readable display name, a 25–64 character short
description, and a concise default prompt that explicitly invokes `$<skill-name>`. Do not
invent icons, brand colors, MCP dependencies, or invocation restrictions.

## Eval requirements

Every new skill needs at least:

- One explicit positive routing prompt.
- Two implicit positive prompts.
- One contextual positive prompt.
- Two negative controls.
- A reviewed root routing boundary with A-only, B-only, both, and neither cases for every
  neighboring skill pair affected by the change.
- Two behavior cases, including one end-to-end case.
- Assertions for verification and prohibited side effects.

Evals are test specifications, not claims that every model/client has passed. Structural CI
checks their completeness and exports the full prompts, assertions, forbidden behaviors, and
shared boundary expectations. Native-client and model-backed runs must record client, model,
version, exact source SHA, case outcomes, side effects, and reviewer in a schema-valid report
without secrets.

## Scripts and assets

Scripts must be deterministic, narrowly scoped, and safe by default.

- Read-only is preferred.
- Writes require an explicit output path.
- Refuse overwrite unless `--force` is supplied.
- External execution requires an explicit confirmation flag.
- Network access must be documented and off by default.
- Do not install dependencies.
- Use environment variables, service files, or standard credential helpers rather than
  command-line secrets.
- Print actionable errors and return nonzero on failure.
- Include `--help` and tests for important behavior.

Assets are templates or examples. They must not contain secrets, production identifiers, or
commands that appear safe while omitting necessary warnings.

Rust contributions must derive Cargo commands from the target repository's toolchain, MSRV,
workspace, lockfile, feature, target, and CI policies. Label each Rust asset as a complete
copy-ready project or an adaptable snippet. Complete projects must compile with their documented
toolchain; snippets must state their dependencies and surrounding assumptions. Destructive
filesystem examples require exact-target authorization, protected-path refusal, containment,
ownership, symlink, preview, confirmation, and adversarial-test contracts.

## Generated files

Do not hand-edit files marked as generated. Change `repository.yaml`, `skillpack.yaml`, or
canonical skill content, then run:

```bash
python3 tools/generate-all
```

`skillpacks check` and CI verify generated state without rewriting it. Generation drift is a
failure; run generation explicitly and review every generated change.

## Commit and pull-request scope

Keep each pull request reviewable. Separate mechanical regeneration from unrelated content
changes when possible. Explain:

- The routing change.
- Permissions, commands, network access, and file writes.
- Database or external-system effects.
- Compatibility impact.
- Eval evidence.
- Version and changelog impact.

Changes to `.github/workflows/`, installers, marketplaces, schemas, release tooling, or
security policy require a maintainer review.

## Developer certificate of origin

By contributing, you certify that you have the right to submit the contribution under the
project license. Each commit must end in a terminal `Signed-off-by` trailer whose name and email
match that commit's author. Sign off commits with:

```bash
git commit --signoff
```

If a commit is already present, amend it rather than placing signoff-looking text in the message
body. Before pushing, check the complete pull-request range with:

```bash
tools/check-dco BASE_SHA HEAD_SHA
```

The check reports every missing, malformed, spoofed, or mismatched trailer in one run, including
merge commits. Its Dependabot exemption is reserved for the verified bot identity and does not
apply to human commits added to a Dependabot branch.

The sign-off records the Developer Certificate of Origin statement:

> I certify that I have the right to submit this contribution under the open-source license
> indicated in the repository.

DCO signoff is not a cryptographic signature. Maintainer-authored local commits additionally use
the repository-specific SSH signing policy in `docs/maintainer-signing.md`.

## Review criteria

Maintainers review correctness, scope, activation boundaries, portability, operational
safety, quality of sources, testability, and maintenance cost. A technically valid
contribution may be declined when it duplicates an existing skill or creates a broad,
fragile abstraction.
