# Completion checklist for one new skill

## Request and boundary

- [ ] Every required request field validates, including expected pack version, nearest neighbor, operations, source requirements, and OpenAI interface.
- [ ] The normalized name and every naming change are recorded.
- [ ] One existing pack coherently owns the skill.
- [ ] The outcome is singular, observable, and independently useful.
- [ ] Positive, negative, and overlap boundaries are written before implementation.
- [ ] User-provided examples and constraints are preserved.

## Repository research

- [ ] Root instructions, architecture, authoring, eval, threat, and contribution rules were read.
- [ ] Current schemas, templates, generators, validators, tests, and required commands were inspected.
- [ ] Target pack manifest, README, changelog, compatibility fixture, and all skill descriptions were read.
- [ ] Neighboring skill bodies, helpers, assets, references, and evals were inspected where overlap exists.
- [ ] Global skill names and descriptions were searched for collisions.
- [ ] Working-tree state and unrelated changes were recorded and preserved.

## Web and domain research

- [ ] Current Agent Skills and relevant client documentation were checked when format behavior matters.
- [ ] Domain claims use primary official sources where available.
- [ ] Each source has a canonical URL, relevant version or date, access date, and decision informed.
- [ ] Secondary sources are labeled as non-normative.
- [ ] Missing web access or unresolved version behavior is explicitly reported.
- [ ] No source, command result, or version was invented.

## Skill content

- [ ] Directory, frontmatter name, and manifest entry match exactly.
- [ ] Description states the outcome, high-signal triggers, `Use when`, and `Do not use` boundary.
- [ ] `SKILL.md` contains every repository-required section and remains focused.
- [ ] Inputs, assumptions, permissions, network use, writes, commands, confirmation, and rollback are explicit.
- [ ] Procedure is ordered, decision-oriented, and separates observation from mutation.
- [ ] Verification can detect false success.
- [ ] Output contract distinguishes observed, inferred, proposed, executed, and verified work.
- [ ] Detailed material is in shallow references and all links stay inside the skill directory.
- [ ] Sources are current, specific, and access-dated.
- [ ] Assets are complete, adaptable, secret-free, and documented.
- [ ] Any helper is justified, standard-library-only unless declared otherwise, preview/read-only by default, and documented.
- [ ] `agents/openai.yaml` has the approved display name, 25–64 character summary, and prompt naming the skill.
- [ ] No generic scaffold prose or placeholder identifiers remain.

## Evals

- [ ] At least one explicit positive routing case exists.
- [ ] At least two varied implicit positive cases exist.
- [ ] At least one contextual positive case exists.
- [ ] At least two realistic near-neighbor negatives exist.
- [ ] Every affected root routing boundary has A-only, B-only, both, and neither cases.
- [ ] Boundary skill IDs, expected selections, shared vocabulary, and explanations are canonical.
- [ ] Focused and end-to-end behavior cases have observable assertions.
- [ ] Forbidden actions cover scope expansion, false verification, and material safety risks.
- [ ] Every discovered routing or behavioral regression has a case.

## Registration and verification

- [ ] `skillpack.yaml` lists the skill exactly once.
- [ ] Pack README and `[Unreleased]` changelog are updated.
- [ ] Compatibility expected-skills inventory agrees with the manifest.
- [ ] Generated files were refreshed only through repository tooling.
- [ ] The reviewed preview digest matches the applied plan and source preimages did not drift.
- [ ] `make generate` completed before non-mutating `make check`.
- [ ] Repository validation passes with generated-state checking.
- [ ] Structural evals pass for the new skill.
- [ ] Full automated tests pass, or exact failures are reported.
- [ ] Optional external validators are reported as run or skipped, never implied.
- [ ] Final diff contains no unrelated edits, committed client copies, secrets, or generated drift.
- [ ] Completion report lists exact evidence, remaining risks, and skipped checks.
