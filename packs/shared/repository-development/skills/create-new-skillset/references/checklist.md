# Completion checklist for a new skillset

## Request and identity

- [ ] Every required package request field validates; no identity, version, runtime, target, source, or operation decision is hidden in a helper default.
- [ ] Every listed skill has a complete scope, examples, neighbor, output, criteria, constraints, operations, sources, and OpenAI interface.
- [ ] Language, subject, path, pack ID, display name, version, targets, category, and keywords are defined.
- [ ] Every normalization or inference is recorded.
- [ ] Destination pack and all skill names are globally unused.
- [ ] User list order and meaning are preserved unless an explicit change is approved.

## Repository research

- [ ] Root instructions and architecture, authoring, eval, threat, compatibility, versioning, and contribution policies were read.
- [ ] Schemas, templates, generators, validators, release tooling, tests, and required commands were inspected.
- [ ] Every existing pack manifest, pack description, skill name, and skill description was inventoried.
- [ ] Complete neighboring packs were read for likely overlaps.
- [ ] Current working-tree state and unrelated changes are recorded and preserved.
- [ ] Any exact-inventory or minimum-cardinality assumptions in schema and tests are identified.

## Web and domain research

- [ ] Current Agent Skills and relevant client distribution/discovery rules were checked.
- [ ] Package-level normative, security, and version sources are mapped to decisions.
- [ ] Every skill has sufficient domain-specific primary sources.
- [ ] Source title, canonical URL, version/date, access date, and decision informed are recorded.
- [ ] Secondary sources are labeled as non-normative.
- [ ] Missing web capability or unresolved behavior is explicitly reported.
- [ ] No citation, version, result, or compatibility claim is invented.

## Cohesion and decomposition

- [ ] The pack has a coherent audience, subject, installation value, and release lifecycle.
- [ ] No filler skill exists solely to satisfy a numeric minimum.
- [ ] Every skill has one observable outcome and independent value.
- [ ] Merge, split, move, rename, add, and remove signals were evaluated.
- [ ] A change ledger accounts for every difference from the user's list.
- [ ] Material list changes have explicit approval.
- [ ] A complete pairwise boundary matrix exists.
- [ ] Existing packs and new skills have no unresolved conceptual duplication.
- [ ] Aggregate operations conservatively cover every skill.
- [ ] Aggregate operations exactly equal the component-wise maximum of included skill operations.
- [ ] A one-skill pack documents its genuine independent installation and versioning boundary.
- [ ] A one-skill pack names an existing nearest neighbor outside the proposed pack.

## Pack content

- [ ] `skillpack.yaml` satisfies schema and lists skills in intended order.
- [ ] README states purpose, boundaries, included skills, prerequisites, operations, installation, version, and migration policy.
- [ ] Changelog records the initial pack and every skill.
- [ ] Compatibility expected-skills fixture matches manifest order and version.
- [ ] Maintainer and repository placeholders follow current repository identity rules.

## Every skill

- [ ] Name, directory, frontmatter, and manifest entry match exactly.
- [ ] Description is concise, intent-focused, and explicitly bounded against neighbors.
- [ ] Every repository-required `SKILL.md` section is complete.
- [ ] Inputs, assumptions, network, writes, commands, external effects, approval, and rollback are explicit.
- [ ] Procedure is evidence-led and verification can detect false success.
- [ ] Output contract distinguishes observed, inferred, proposed, executed, and verified work.
- [ ] References are focused, shallow, and source-backed.
- [ ] Assets are complete, adaptable, documented, and secret-free.
- [ ] Helpers are justified, safe by default, standard-library-only unless declared, documented, and tested.
- [ ] Every skill has an approved `agents/openai.yaml` with a 25–64 character summary and prompt naming that skill.
- [ ] No placeholder or generic scaffold text remains.

## Routing and behavior evals

- [ ] Every skill has explicit, implicit, contextual, negative, and overlap routing cases.
- [ ] Every skill has focused and end-to-end behavior cases.
- [ ] Assertions are observable and forbidden actions cover material risk.
- [ ] Pairwise hard cases challenge likely competitors inside the new pack.
- [ ] Existing neighboring skills are named as preferred overlap owners where appropriate.
- [ ] Full discovery descriptions remain concise and discriminating as a group.

## Generation and verification

- [ ] Helper previews were reviewed before apply and no existing destination was overwritten.
- [ ] Each apply used the exact reviewed plan digest and refused stale source preimages.
- [ ] Hard-coded inventory and helper tests were updated only as required.
- [ ] Plugin manifests, marketplaces, catalog, installers, OpenCode catalogs, README catalog, and hashes were generated, not hand-edited.
- [ ] Per-skill structural evals pass.
- [ ] Full repository validation passes with generated-state checking.
- [ ] Full eval suite passes.
- [ ] Automated tests pass, or exact failures are reported.
- [ ] `make generate` completed before non-mutating `make check`.
- [ ] Optional format and client-backed checks are reported as executed or skipped; none is implied by structural validation.
- [ ] Final diff has one canonical copy, no client-install copies, no secrets, no unrelated edits, and no generated drift.
- [ ] Final report lists exact files, list changes, source evidence, command results, skipped checks, and residual risks.
