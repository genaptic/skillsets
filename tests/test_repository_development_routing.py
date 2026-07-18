from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs/shared/repository-development"
SKILLSET = PACK / "skills/create-new-skillset"
SKILL = PACK / "skills/create-new-skill"

ONE_SKILL_PACK_PROMPT = (
    "Add a new independently installable rust-unsafe-code-audit pack containing exactly one "
    "skill, rust-unsafe-boundary-review. Security reviewers need that focused installation "
    "and release boundary; rust-core-best-practices owns the nearest excluded general Rust "
    "review outcome. Research and integrate the complete pack."
)
EXPECTED_SKILLSET_DESCRIPTION = (
    "Create one complete, researched, independently installable skillpack and every declared "
    "skill in this Genaptic repository, including boundaries, resources, evals, compatibility "
    "fixtures, generated adapters, and verification. Use when the user supplies a new "
    "repository pack identity, scope, and detailed list of one or more skills, including a "
    "coherent one-skill pack with a genuine independent installation and release boundary. Do "
    "not use for generic or personal skill bundles outside this repository, an existing-skill "
    "edit, exactly one new skill that belongs in an existing pack, release/publishing work, or "
    "remote Git operations; use create-new-skill only for that existing-pack case."
)


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter, _body = text[4:].split("\n---\n", maxsplit=1)
    loaded = yaml.safe_load(frontmatter)
    assert isinstance(loaded, dict)
    return loaded


def _evals(skill_dir: Path) -> dict[str, object]:
    return json.loads((skill_dir / "evals/evals.json").read_text(encoding="utf-8"))


def _case(cases: list[dict[str, object]], case_id: str) -> dict[str, object]:
    return next(case for case in cases if case["id"] == case_id)


def test_skillset_description_routes_by_installation_boundary() -> None:
    description = _frontmatter(SKILLSET / "SKILL.md")["description"]
    assert isinstance(description, str)
    assert description.strip() == EXPECTED_SKILLSET_DESCRIPTION
    assert "use create-new-skill for the one-skill case" not in str(description).lower()

    guide = (SKILLSET / "references/guide.md").read_text(encoding="utf-8")
    checklist = (SKILLSET / "references/checklist.md").read_text(encoding="utf-8")
    assert "Skill count does not decide which authoring workflow owns a request." in guide
    assert "genuine independent installation and versioning boundary" in checklist


def test_one_skill_pack_prompt_has_opposite_paired_routing_expectations() -> None:
    skillset_evals = _evals(SKILLSET)
    skill_evals = _evals(SKILL)
    skillset_routing = skillset_evals["routing"]
    skill_routing = skill_evals["routing"]
    assert isinstance(skillset_routing, list)
    assert isinstance(skill_routing, list)

    positive = _case(skillset_routing, "implicit-positive-independent-one-skill-pack")
    negative = _case(skill_routing, "overlap-new-skillset")
    assert positive["prompt"] == negative["prompt"] == ONE_SKILL_PACK_PROMPT
    assert positive["kind"] == "implicit-positive"
    assert positive["shouldTrigger"] is True
    assert negative["kind"] == "overlap"
    assert negative["shouldTrigger"] is False
    assert negative["preferredSkill"] == "create-new-skillset"

    existing_pack = _case(skillset_routing, "overlap-one-skill")
    assert existing_pack["shouldTrigger"] is False
    assert existing_pack["preferredSkill"] == "create-new-skill"


def test_repository_development_eval_shape_is_unchanged() -> None:
    expected_kinds = {
        "explicit-positive": 1,
        "implicit-positive": 2,
        "contextual-positive": 1,
        "negative": 2,
        "overlap": 1,
    }
    for skill_dir in (SKILL, SKILLSET):
        evals = _evals(skill_dir)
        routing = evals["routing"]
        behavior = evals["behavior"]
        assert isinstance(routing, list)
        assert isinstance(behavior, list)
        assert len(routing) == 7
        assert len(behavior) == 2
        assert {
            kind: sum(case["kind"] == kind for case in routing) for kind in expected_kinds
        } == expected_kinds
