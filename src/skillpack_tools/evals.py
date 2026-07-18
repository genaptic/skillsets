from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .models import discover_packs
from .path_safety import read_regular_text, repository_relative
from .util import SkillpackError


@dataclass(frozen=True)
class EvalSummary:
    skill: str
    routing: tuple[dict[str, Any], ...]
    behavior: tuple[dict[str, Any], ...]

    @property
    def routing_cases(self) -> int:
        return len(self.routing)

    @property
    def behavior_cases(self) -> int:
        return len(self.behavior)


def load_eval_schema(root: Path) -> dict[str, Any]:
    return json.loads(read_regular_text(root / "schemas" / "evals.schema.json", root))


def validate_eval_file(
    root: Path, path: Path, *, all_skill_names: set[str]
) -> tuple[list[str], EvalSummary | None]:
    errors: list[str] = []
    try:
        try:
            repository_relative(path, root)
            document_root = root
        except SkillpackError:
            document_root = Path(path.absolute()).parent
        data = json.loads(read_regular_text(path, document_root))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SkillpackError) as exc:
        return [f"{path}: invalid JSON: {exc}"], None

    schema = load_eval_schema(root)
    for error in sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{path}:{location}: {error.message}")

    if errors:
        return errors, None

    expected_skill = path.parents[1].name
    if data["skill"] != expected_skill:
        errors.append(
            f"{path}: skill is {data['skill']!r}, expected directory name {expected_skill!r}."
        )

    routing = data["routing"]
    ids = [case["id"] for case in routing]
    if len(ids) != len(set(ids)):
        errors.append(f"{path}: routing case IDs must be unique.")

    kinds = [case["kind"] for case in routing]
    if kinds.count("explicit-positive") < 1:
        errors.append(f"{path}: at least one explicit-positive routing case is required.")
    if kinds.count("implicit-positive") < 2:
        errors.append(f"{path}: at least two implicit-positive routing cases are required.")
    if kinds.count("contextual-positive") < 1:
        errors.append(f"{path}: at least one contextual-positive routing case is required.")
    if kinds.count("negative") < 2:
        errors.append(f"{path}: at least two negative routing cases are required.")
    if kinds.count("overlap") < 1:
        errors.append(f"{path}: at least one overlap routing case is required.")

    for case in routing:
        positive = case["kind"] in {"explicit-positive", "implicit-positive", "contextual-positive"}
        if case["shouldTrigger"] is not positive:
            errors.append(f"{path}: {case['id']} shouldTrigger does not match kind {case['kind']}.")
        if case["kind"] == "overlap":
            preferred = case.get("preferredSkill")
            if not preferred:
                errors.append(f"{path}: overlap case {case['id']} needs preferredSkill.")
            elif preferred not in all_skill_names:
                errors.append(
                    f"{path}: overlap case {case['id']} names unknown skill {preferred!r}."
                )
            elif preferred == data["skill"]:
                errors.append(
                    f"{path}: overlap case {case['id']} cannot prefer the skill under test."
                )

    behavior = data["behavior"]
    behavior_ids = [case["id"] for case in behavior]
    if len(behavior_ids) != len(set(behavior_ids)):
        errors.append(f"{path}: behavior case IDs must be unique.")
    if not any(case["kind"] == "end-to-end" for case in behavior):
        errors.append(f"{path}: at least one end-to-end behavior case is required.")

    return errors, EvalSummary(
        data["skill"],
        tuple(dict(case) for case in routing),
        tuple(dict(case) for case in behavior),
    )


def run_structural_evals(root: Path, *, skill_filter: str | None = None) -> list[EvalSummary]:
    packs = discover_packs(root)
    all_skill_names = {skill for pack in packs for skill in pack.skills}
    if skill_filter and skill_filter not in all_skill_names:
        raise SkillpackError(f"Unknown skill for eval filter: {skill_filter}")

    errors: list[str] = []
    summaries: list[EvalSummary] = []
    for pack in packs:
        for skill in pack.skills:
            if skill_filter and skill != skill_filter:
                continue
            path = pack.path / "skills" / skill / "evals" / "evals.json"
            current_errors, summary = validate_eval_file(
                root, path, all_skill_names=all_skill_names
            )
            errors.extend(current_errors)
            if summary:
                summaries.append(summary)

    if errors:
        raise SkillpackError("Eval validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    return summaries


def eval_report(summaries: list[EvalSummary]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "skills": [
            {
                "skill": summary.skill,
                "routingCases": summary.routing_cases,
                "behaviorCases": summary.behavior_cases,
                "routing": list(summary.routing),
                "behavior": list(summary.behavior),
            }
            for summary in summaries
        ],
        "totals": {
            "skills": len(summaries),
            "routingCases": sum(item.routing_cases for item in summaries),
            "behaviorCases": sum(item.behavior_cases for item in summaries),
        },
    }
