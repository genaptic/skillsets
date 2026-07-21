from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs/shared/genaptic-skillsets-development"
SKILLPACK = PACK / "skills/genaptic-skillsets-create-skillpack"
SKILL = PACK / "skills/genaptic-skillsets-create-skill"

ONE_SKILL_PACK_PROMPT = (
    "Add a new independently installable rust-unsafe-code-audit pack containing exactly one "
    "skill, rust-unsafe-boundary-review. Security reviewers need that focused installation "
    "and release boundary; rust-core-best-practices owns the nearest excluded general Rust "
    "review outcome. Research and integrate the complete pack."
)
EXPECTED_SKILLPACK_DESCRIPTION = (
    "Create one complete, researched, independently installable skillpack and every declared "
    "skill in this Genaptic repository, including boundaries, resources, evals, compatibility "
    "fixtures, generated adapters, and verification. Use when the user supplies a new "
    "repository pack identity, scope, and detailed list of one or more skills, including a "
    "coherent one-skill pack with a genuine independent installation and release boundary. Do "
    "not use for generic or personal skill bundles outside this repository, an existing-skill "
    "edit, exactly one new skill that belongs in an existing pack, release/publishing work, or "
    "remote Git operations; use genaptic-skillsets-create-skill only for that existing-pack "
    "case."
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


def test_pack_identity_lifecycle_and_interface_are_final() -> None:
    manifest = yaml.safe_load((PACK / "skillpack.yaml").read_text(encoding="utf-8"))
    assert manifest["schema-version"] == 2
    assert manifest["id"] == manifest["subject"] == "genaptic-skillsets-development"
    assert manifest["display-name"] == "Genaptic Skillsets Development"
    assert manifest["version"] == "1.0.0"
    assert manifest["maturity"] == "release-candidate"
    assert manifest["distribution"] == {"visibility": "maintainers"}
    assert manifest["publication"] == {"state": "unpublished"}
    assert manifest["release-gates"] == ["native-evidence", "deterministic-archive"]
    assert manifest["skills"] == [
        "genaptic-skillsets-create-skill",
        "genaptic-skillsets-create-skillpack",
    ]
    starters = manifest["interface"]["starter-prompts"]
    assert [starter["skill"] for starter in starters] == manifest["skills"]
    for starter in starters:
        assert f"${starter['skill']}" in starter["prompt"]


def test_skillpack_description_routes_by_installation_boundary() -> None:
    description = _frontmatter(SKILLPACK / "SKILL.md")["description"]
    assert isinstance(description, str)
    assert description.strip() == EXPECTED_SKILLPACK_DESCRIPTION
    assert "use genaptic-skillsets-create-skill only" in str(description).lower()

    guide = (SKILLPACK / "references/guide.md").read_text(encoding="utf-8")
    checklist = (SKILLPACK / "references/checklist.md").read_text(encoding="utf-8")
    assert "Skill count does not decide which authoring workflow owns a request." in guide
    assert "genuine independent installation and versioning boundary" in checklist


def test_one_skill_pack_prompt_is_preserved_in_reviewed_boundary_matrix() -> None:
    skillpack_evals = _evals(SKILLPACK)
    skillpack_routing = skillpack_evals["routing"]
    assert isinstance(skillpack_routing, list)

    positive = _case(skillpack_routing, "implicit-positive-independent-one-skill-pack")
    boundaries = json.loads((ROOT / "evals/routing-boundaries.json").read_text(encoding="utf-8"))[
        "boundaries"
    ]
    boundary = _case(
        boundaries,
        "genaptic-skillsets-create-skill-vs-genaptic-skillsets-create-skillpack",
    )
    cases = boundary["cases"]
    assert isinstance(cases, list)
    create_skill = _case(
        cases,
        "genaptic-skillsets-create-skill-vs-genaptic-skillsets-create-skillpack-a-only",
    )
    create_pack = _case(
        cases,
        "genaptic-skillsets-create-skill-vs-genaptic-skillsets-create-skillpack-b-only",
    )
    assert positive["prompt"] == create_pack["prompt"] == ONE_SKILL_PACK_PROMPT
    assert positive["kind"] == "implicit-positive"
    assert positive["shouldTrigger"] is True
    assert create_skill["expectedSkills"] == ["genaptic-skillsets-create-skill"]
    assert create_pack["expectedSkills"] == ["genaptic-skillsets-create-skillpack"]


def test_genaptic_skillsets_development_eval_shape_uses_global_boundaries() -> None:
    expected_kinds = {
        "explicit-positive": 1,
        "implicit-positive": 2,
        "contextual-positive": 1,
        "negative": 2,
    }
    for skill_dir in (SKILL, SKILLPACK):
        evals = _evals(skill_dir)
        routing = evals["routing"]
        behavior = evals["behavior"]
        assert isinstance(routing, list)
        assert isinstance(behavior, list)
        assert len(routing) == 6
        assert len(behavior) == 2
        assert {
            kind: sum(case["kind"] == kind for case in routing) for kind in expected_kinds
        } == expected_kinds
