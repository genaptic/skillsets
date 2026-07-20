from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .models import Pack, discover_packs
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


@dataclass(frozen=True)
class RoutingBoundarySummary:
    id: str
    skills: tuple[str, str]
    shared_vocabulary: tuple[str, ...]
    outcome_explanations: dict[str, str]
    cases: tuple[dict[str, Any], ...]

    def as_report(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "skills": list(self.skills),
            "sharedVocabulary": list(self.shared_vocabulary),
            "outcomeExplanations": dict(self.outcome_explanations),
            "cases": [dict(case) for case in self.cases],
        }


class EvalSummaries(list[EvalSummary]):
    """List-compatible structural results with their reviewed boundary matrices."""

    def __init__(
        self,
        skills: list[EvalSummary],
        boundaries: tuple[RoutingBoundarySummary, ...],
    ) -> None:
        super().__init__(skills)
        self.boundaries = boundaries


def load_eval_schema(root: Path) -> dict[str, Any]:
    return json.loads(read_regular_text(root / "schemas" / "evals.schema.json", root))


def load_routing_boundary_schema(root: Path) -> dict[str, Any]:
    return json.loads(read_regular_text(root / "schemas" / "routing-boundaries.schema.json", root))


def _strict_json_document(path: Path, root: Path) -> dict[str, Any]:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate object key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite number {value!r}")

    data = json.loads(
        read_regular_text(path, root),
        object_pairs_hook=reject_duplicate,
        parse_constant=reject_constant,
    )
    if not isinstance(data, dict):
        raise ValueError("root must be a JSON object")
    return data


def validate_routing_boundaries(
    root: Path,
    *,
    packs: list[Pack] | None = None,
) -> tuple[list[str], tuple[RoutingBoundarySummary, ...]]:
    path = root / "evals" / "routing-boundaries.json"
    errors: list[str] = []
    try:
        data = _strict_json_document(path, root)
        schema = load_routing_boundary_schema(root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SkillpackError, ValueError) as exc:
        return [f"{path}: invalid routing-boundary JSON: {exc}"], ()

    for error in sorted(
        Draft202012Validator(schema).iter_errors(data), key=lambda item: list(item.path)
    ):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{path}:{location}: {error.message}")
    if errors:
        return errors, ()

    discovered = packs if packs is not None else discover_packs(root)
    all_skills = {skill for pack in discovered for skill in pack.skills}
    public_skills = {
        skill for pack in discovered if pack.visibility == "public" for skill in pack.skills
    }
    seen_boundary_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_case_ids: set[str] = set()
    seen_prompts: set[str] = set()
    participating: set[str] = set()
    summaries: list[RoutingBoundarySummary] = []
    previous_pair: tuple[str, str] | None = None
    expected_outcomes = ("a-only", "b-only", "both", "neither")

    for boundary in data["boundaries"]:
        boundary_id = boundary["id"]
        skills = tuple(boundary["skills"])
        if skills != tuple(sorted(skills)):
            errors.append(f"{path}: {boundary_id} skills must be lexicographically sorted.")
        if len(skills) != 2:
            continue
        pair = (skills[0], skills[1])
        expected_id = f"{pair[0]}-vs-{pair[1]}"
        if boundary_id != expected_id:
            errors.append(f"{path}: boundary ID {boundary_id!r} must be {expected_id!r}.")
        if boundary_id in seen_boundary_ids:
            errors.append(f"{path}: duplicate boundary ID {boundary_id!r}.")
        seen_boundary_ids.add(boundary_id)
        if pair in seen_pairs:
            errors.append(f"{path}: duplicate unordered boundary pair {pair!r}.")
        seen_pairs.add(pair)
        if previous_pair is not None and pair <= previous_pair:
            errors.append(f"{path}: boundaries must be sorted by their two skill IDs.")
        previous_pair = pair
        unknown = sorted(set(pair) - all_skills)
        if unknown:
            errors.append(f"{path}: {boundary_id} names unknown skills {unknown!r}.")
        participating.update(pair)

        vocabulary = boundary["sharedVocabulary"]
        if vocabulary != sorted(vocabulary):
            errors.append(f"{path}: {boundary_id} sharedVocabulary must be sorted.")

        expected_by_outcome = {
            "a-only": [pair[0]],
            "b-only": [pair[1]],
            "both": [pair[0], pair[1]],
            "neither": [],
        }
        for index, case in enumerate(boundary["cases"]):
            outcome = expected_outcomes[index]
            case_id = f"{boundary_id}-{outcome}"
            if case["outcome"] != outcome:
                errors.append(
                    f"{path}: {boundary_id} case {index + 1} must use outcome {outcome!r}."
                )
            if case["id"] != case_id:
                errors.append(f"{path}: case ID {case['id']!r} must be {case_id!r}.")
            if case["expectedSkills"] != expected_by_outcome[outcome]:
                errors.append(
                    f"{path}: {case_id} expectedSkills must be {expected_by_outcome[outcome]!r}."
                )
            if case["id"] in seen_case_ids:
                errors.append(f"{path}: duplicate boundary case ID {case['id']!r}.")
            seen_case_ids.add(case["id"])
            prompt_key = " ".join(case["prompt"].casefold().split())
            if prompt_key in seen_prompts:
                errors.append(f"{path}: duplicate boundary prompt in {case['id']!r}.")
            seen_prompts.add(prompt_key)

        summaries.append(
            RoutingBoundarySummary(
                id=boundary_id,
                skills=pair,
                shared_vocabulary=tuple(vocabulary),
                outcome_explanations=dict(boundary["outcomeExplanations"]),
                cases=tuple(dict(case) for case in boundary["cases"]),
            )
        )

    orphaned = sorted(public_skills - participating)
    if orphaned:
        errors.append(f"{path}: public skills without a reviewed boundary: {orphaned!r}.")
    return errors, tuple(summaries)


def validate_eval_file(root: Path, path: Path) -> tuple[list[str], EvalSummary | None]:
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

    for case in routing:
        positive = case["kind"] in {"explicit-positive", "implicit-positive", "contextual-positive"}
        if case["shouldTrigger"] is not positive:
            errors.append(f"{path}: {case['id']} shouldTrigger does not match kind {case['kind']}.")

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


def run_structural_evals(root: Path, *, skill_filter: str | None = None) -> EvalSummaries:
    packs = discover_packs(root)
    all_skill_names = {skill for pack in packs for skill in pack.skills}
    if skill_filter and skill_filter not in all_skill_names:
        raise SkillpackError(f"Unknown skill for eval filter: {skill_filter}")

    errors: list[str] = []
    summaries: list[EvalSummary] = []
    boundary_errors, boundaries = validate_routing_boundaries(root, packs=packs)
    errors.extend(boundary_errors)
    for pack in packs:
        for skill in pack.skills:
            if skill_filter and skill != skill_filter:
                continue
            path = pack.path / "skills" / skill / "evals" / "evals.json"
            current_errors, summary = validate_eval_file(root, path)
            errors.extend(current_errors)
            if summary:
                summaries.append(summary)

    if errors:
        raise SkillpackError("Eval validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    selected_boundaries = tuple(
        boundary
        for boundary in boundaries
        if skill_filter is None or skill_filter in boundary.skills
    )
    return EvalSummaries(summaries, selected_boundaries)


def eval_report(summaries: list[EvalSummary]) -> dict[str, Any]:
    boundaries = tuple(getattr(summaries, "boundaries", ()))
    return {
        "schemaVersion": 2,
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
        "routingBoundaries": [boundary.as_report() for boundary in boundaries],
        "totals": {
            "skills": len(summaries),
            "routingCases": sum(item.routing_cases for item in summaries),
            "behaviorCases": sum(item.behavior_cases for item in summaries),
            "routingBoundaries": len(boundaries),
            "boundaryCases": sum(len(item.cases) for item in boundaries),
        },
    }
