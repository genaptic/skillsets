from __future__ import annotations

import copy
import datetime as dt
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import skillpack_tools.checks as checks
import skillpack_tools.cli as cli
import skillpack_tools.lifecycle as lifecycle
import skillpack_tools.lifecycle_commands as lifecycle_commands
import skillpack_tools.publication as publication
from skillpack_tools.lifecycle_commands import _Snapshot
from skillpack_tools.models import Pack, get_pack
from skillpack_tools.util import SkillpackError, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]


def _pack(**updates: Any) -> Pack:
    base = get_pack(ROOT, "python-best-practices")
    raw = copy.deepcopy(base.raw)
    for key, value in updates.items():
        if key == "visibility":
            raw["distribution"]["visibility"] = value
        elif key == "publication":
            raw["publication"] = value
        elif key == "short_description":
            raw["interface"]["short-description"] = value
        elif key == "prompts":
            raw["interface"]["starter-prompts"] = value
        else:
            raw[key.replace("_", "-")] = value
    return Pack(root=base.root, path=base.path, raw=raw)


def test_cli_lifecycle_preview_apply_and_digest_guard(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_root", lambda _value: ROOT)
    calls: list[tuple[str, dict[str, Any]]] = []

    def preview(_root: Path, pack_id: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((f"preview:{pack_id}", kwargs))
        return {"planDigest": "a" * 64}

    def apply(_root: Path, pack_id: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((f"apply:{pack_id}", kwargs))
        return {"planDigest": kwargs["plan_digest"], "applied": True}

    monkeypatch.setattr(cli, "build_lifecycle_plan", preview)
    monkeypatch.setattr(cli, "apply_lifecycle_plan", apply)
    monkeypatch.setattr(cli, "plan_text", lambda plan: json.dumps(plan) + "\n")

    assert (
        cli.main(
            [
                "prepare-release",
                "python-best-practices",
                "--release-date",
                "2026-07-19",
                "--version",
                "1.0.1",
            ]
        )
        == 0
    )
    assert "No files changed" in capsys.readouterr().out
    assert calls[-1] == (
        "preview:python-best-practices",
        {
            "operation": "prepare-release",
            "release_date": "2026-07-19",
            "version": "1.0.1",
        },
    )

    assert (
        cli.main(
            [
                "begin-development",
                "python-best-practices",
                "--next-version",
                "1.0.2",
                "--apply",
                "--plan-digest",
                "b" * 64,
            ]
        )
        == 0
    )
    assert "No files changed" not in capsys.readouterr().out
    assert calls[-1] == (
        "apply:python-best-practices",
        {
            "operation": "begin-development",
            "plan_digest": "b" * 64,
            "release_date": None,
            "version": "1.0.2",
        },
    )

    assert (
        cli.main(
            [
                "prepare-release",
                "python-best-practices",
                "--release-date",
                "2026-07-19",
                "--plan-digest",
                "c" * 64,
            ]
        )
        == 1
    )
    assert "only valid with --apply" in capsys.readouterr().err


def test_cli_publication_and_check_command_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_root", lambda _value: ROOT)
    record = {"schemaVersion": 1}
    publication_calls: list[tuple[bool, str | None]] = []
    monkeypatch.setattr(cli, "load_publication_record", lambda _root, _path: record)

    def prepare(
        _root: Path,
        actual: dict[str, Any],
        *,
        apply: bool,
        plan_digest: str | None,
    ) -> dict[str, Any]:
        assert actual is record
        publication_calls.append((apply, plan_digest))
        return {"planDigest": plan_digest or "d" * 64, "applied": apply}

    monkeypatch.setattr(cli, "prepare_publication_update", prepare)
    assert cli.main(["prepare-publication-update", "record.json"]) == 0
    assert "No files changed" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "prepare-publication-update",
                "record.json",
                "--apply",
                "--plan-digest",
                "e" * 64,
            ]
        )
        == 0
    )
    assert "No files changed" not in capsys.readouterr().out
    assert publication_calls == [(False, None), (True, "e" * 64)]

    events: list[object] = []
    monkeypatch.setattr(cli, "run_check", lambda root: events.append(("check", root)))
    monkeypatch.setattr(
        cli, "run_check_pack", lambda root, pack: events.append(("check-pack", root, pack))
    )
    monkeypatch.setattr(cli, "run_lint", lambda root: events.append(("lint", root)))
    monkeypatch.setattr(cli, "run_test", lambda root: events.append(("test", root)))
    monkeypatch.setattr(
        cli, "run_lock", lambda root, *, check: events.append(("lock", root, check))
    )
    assert cli.main(["check"]) == 0
    assert "Complete repository check passed" in capsys.readouterr().out
    assert cli.main(["check-pack", "python-best-practices"]) == 0
    assert cli.main(["lint"]) == 0
    assert cli.main(["test"]) == 0
    assert cli.main(["lock"]) == 0
    assert cli.main(["lock", "--check"]) == 0
    assert events == [
        ("check", ROOT),
        ("check-pack", ROOT, "python-best-practices"),
        ("lint", ROOT),
        ("test", ROOT),
        ("lock", ROOT, False),
        ("lock", ROOT, True),
    ]


def test_cli_release_forwards_the_explicit_resolved_policy_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_root", lambda _value: ROOT)
    policy_root = tmp_path / "protected-policy"
    report = tmp_path / "codex.json"
    calls: list[dict[str, Any]] = []

    def build(_root: Path, pack_id: str, **kwargs: Any) -> tuple[Path, Path, Path]:
        assert _root == ROOT
        assert pack_id == "python-best-practices"
        calls.append(kwargs)
        output = ROOT / "dist" / "releases"
        return output / "pack.zip", output / "pack.zip.sha256", output / "notes.md"

    monkeypatch.setattr(cli, "build_release", build)
    assert (
        cli.main(
            [
                "release",
                "python-best-practices",
                "--policy-root",
                str(policy_root),
                "--report",
                str(report),
            ]
        )
        == 0
    )
    assert calls == [
        {
            "draft": False,
            "reports": [report.resolve()],
            "policy_root": policy_root.resolve(),
        }
    ]
    assert "Archive: dist/releases/pack.zip" in capsys.readouterr().out


def test_cli_compatibility_eval_warning_and_noop_configuration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_root", lambda _value: ROOT)
    pack = object()
    monkeypatch.setattr(
        cli, "get_pack", lambda _root, pack_id: pack if pack_id == "known" else None
    )
    monkeypatch.setattr(
        cli,
        "validate_compatibility_report",
        lambda _root, _path, **kwargs: ([], {"pack": kwargs["pack"]}),
    )
    assert cli.main(["compatibility", "report.json", "--pack", "known"]) == 0
    assert "validation passed" in capsys.readouterr().out.lower()

    monkeypatch.setattr(
        cli,
        "validate_compatibility_report",
        lambda *_args, **_kwargs: (["first", "second"], None),
    )
    assert cli.main(["compatibility", "report.json"]) == 1
    assert "first" in capsys.readouterr().err

    def missing_pack(_root: Path, _pack_id: str) -> object:
        raise KeyError("Unknown pack fixture")

    monkeypatch.setattr(cli, "get_pack", missing_pack)
    assert cli.main(["compatibility", "report.json", "--pack", "missing"]) == 1
    assert "Unknown pack fixture" in capsys.readouterr().err

    result = SimpleNamespace(ok=True, errors=[], warnings=["review this warning"])
    monkeypatch.setattr(cli, "validate_repository", lambda *_args, **_kwargs: result)
    monkeypatch.setattr(cli, "raise_for_result", lambda actual: actual)
    assert cli.main(["validate"]) == 0
    captured = capsys.readouterr()
    assert "review this warning" in captured.err
    assert "validation passed" in captured.out.lower()

    monkeypatch.setattr(cli, "run_structural_evals", lambda *_args, **_kwargs: ["summary"])
    monkeypatch.setattr(
        cli,
        "eval_report",
        lambda _summaries: {
            "totals": {
                "skills": 1,
                "routingCases": 2,
                "behaviorCases": 3,
                "routingBoundaries": 4,
                "boundaryCases": 5,
            }
        },
    )
    writes: list[tuple[Path, str]] = []
    monkeypatch.setattr(cli, "atomic_write", lambda path, text: writes.append((path, text)))
    assert cli.main(["eval", "--json", "eval.json"]) == 0
    assert writes and writes[0][0] == ROOT / "eval.json"
    capsys.readouterr()

    monkeypatch.setattr(cli, "configure_repository", lambda *_args, **_kwargs: [])
    assert cli.main(["configure"]) == 0
    assert "already current" in capsys.readouterr().out


def test_checks_wrappers_and_non_rust_pack_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        checks,
        "_run",
        lambda _root, command, **_kwargs: commands.append(tuple(command)),
    )
    checks.lock(ROOT, check=True)
    checks.lint(ROOT)
    checks.test(ROOT)
    assert any(command[-1] == "tools/check-dependency-lock" for command in commands)
    assert any(command[-3:] == ("ruff", "check", ".") for command in commands)
    assert any(command[-2:] == ("-m", "pytest") for command in commands)

    pack = SimpleNamespace(
        id="python-fixture",
        skills=["first", "second"],
        relative_path="packs/python/fixture",
        language="python",
    )
    events: list[object] = []
    monkeypatch.setattr(checks, "get_pack", lambda _root, _pack_id: pack)
    monkeypatch.setattr(
        checks, "apply_generated_files", lambda _root, *, check: events.append(("generated", check))
    )
    monkeypatch.setattr(
        checks,
        "validate_repository",
        lambda *_args, **kwargs: (
            events.append(("validate", kwargs)) or SimpleNamespace(ok=True, errors=[], warnings=[])
        ),
    )
    monkeypatch.setattr(checks, "raise_for_result", lambda _result: events.append("raised"))
    monkeypatch.setattr(
        checks,
        "run_structural_evals",
        lambda _root, *, skill_filter: events.append(("eval", skill_filter)),
    )
    commands.clear()
    checks.check_pack(ROOT, "python-fixture")
    assert not any("check-rust-assets" in command for command in commands)
    assert ("eval", "first") in events and ("eval", "second") in events
    assert "Full `skillpacks check` remains mandatory" in capsys.readouterr().out


def test_checks_run_success_prints_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        checks.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(["fixture"], 0),
    )
    checks._run(ROOT, ["fixture", "--ok"])
    assert "+ fixture --ok" in capsys.readouterr().out


def test_lifecycle_validation_collects_all_cross_field_errors() -> None:
    invalid = _pack(
        maturity="unknown",
        visibility="unexpected",
        publication={"state": "invalid", "latest-release": {"version": "bad"}},
        release_gates=["rust-assets"],
        short_description="Replace with placeholder",
        prompts=[
            {"skill": "unknown-skill", "prompt": "TODO use the wrong skill"},
            {"skill": "unknown-skill", "prompt": "TODO use the wrong skill"},
        ],
    )
    errors = "\n".join(lifecycle.validate_pack_lifecycle(invalid))
    for expected in (
        "unsupported maturity",
        "unsupported distribution visibility",
        "unsupported publication state",
        "release-gates must be",
        "sentence punctuation",
        "contains boilerplate",
        "Invalid Semantic Version",
        "is undeclared",
        "must reference",
        "starter prompt text must be unique",
    ):
        assert expected in errors

    unpublished_with_release = _pack(
        publication={"state": "unpublished", "latest-release": {"version": "1.0.0"}}
    )
    assert "must not declare latest-release" in "\n".join(
        lifecycle.validate_pack_lifecycle(unpublished_with_release)
    )

    maintainer_published = _pack(
        visibility="maintainers",
        publication={"state": "published", "latest-release": {"version": "1.0.0"}},
        maturity="stable",
    )
    assert "must remain unpublished" in "\n".join(
        lifecycle.validate_pack_lifecycle(maintainer_published)
    )

    behind = _pack(
        version="1.0.0",
        maturity="stable",
        publication={"state": "published", "latest-release": {"version": "2.0.0"}},
    )
    assert "cannot precede" in "\n".join(lifecycle.validate_pack_lifecycle(behind))

    equal_candidate = _pack(
        publication={"state": "published", "latest-release": {"version": "1.0.0"}}
    )
    assert "requires stable or deprecated" in "\n".join(
        lifecycle.validate_pack_lifecycle(equal_candidate)
    )
    with pytest.raises(ValueError, match="Invalid Semantic Version"):
        lifecycle.semantic_version_key("not-semver")
    with pytest.raises(ValueError, match="Unknown distribution channel"):
        lifecycle.select_packs([_pack()], cast(Any, "unknown"))


def test_clean_worktree_guard_covers_non_git_and_git_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert lifecycle_commands._require_clean_worktree(tmp_path) is None
    (tmp_path / ".git").mkdir()

    monkeypatch.setattr(
        lifecycle_commands.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "status failed"),
    )
    with pytest.raises(SkillpackError, match="Could not inspect"):
        lifecycle_commands._require_clean_worktree(tmp_path)

    monkeypatch.setattr(
        lifecycle_commands.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "dirty\n", ""),
    )
    with pytest.raises(SkillpackError, match="clean Git worktree"):
        lifecycle_commands._require_clean_worktree(tmp_path)

    results = iter(
        (
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "not-a-sha\n", ""),
        )
    )
    monkeypatch.setattr(
        lifecycle_commands.subprocess, "run", lambda *_args, **_kwargs: next(results)
    )
    with pytest.raises(SkillpackError, match="resolvable Git HEAD"):
        lifecycle_commands._require_clean_worktree(tmp_path)


def test_skill_update_and_changelog_failure_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_root = tmp_path / "pack"
    skill_file = pack_root / "skills" / "fixture" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("fixture\n", encoding="utf-8")
    pack = SimpleNamespace(root=tmp_path, path=pack_root, id="fixture-pack", skills=["fixture"])

    monkeypatch.setattr(
        lifecycle_commands,
        "parse_skill_markdown_text",
        lambda *_args: ({"metadata": "not-a-mapping"}, "body\n"),
    )
    with pytest.raises(SkillpackError, match="metadata must be a mapping"):
        lifecycle_commands._skill_updates(pack, version="1.0.1", maturity="stable")

    monkeypatch.setattr(
        lifecycle_commands,
        "parse_skill_markdown_text",
        lambda *_args: ({"metadata": {"skillpack": "other"}}, "body\n"),
    )
    with pytest.raises(SkillpackError, match=r"metadata\.skillpack does not match"):
        lifecycle_commands._skill_updates(pack, version="1.0.1", maturity="stable")

    finalize = lifecycle_commands._finalize_changelog
    with pytest.raises(SkillpackError, match="exactly one"):
        finalize("", old_version="1.0.0", version="1.0.1", release_date="2026-07-19")
    with pytest.raises(SkillpackError, match="already contains"):
        finalize(
            "## [Unreleased]\n\n- Change\n\n## [1.0.1]\n",
            old_version="1.0.0",
            version="1.0.1",
            release_date="2026-07-19",
        )
    with pytest.raises(SkillpackError, match="Could not isolate"):
        finalize(
            "Inline ## [Unreleased] only",
            old_version="1.0.0",
            version="1.0.1",
            release_date="2026-07-19",
        )
    with pytest.raises(SkillpackError, match="block is empty"):
        finalize(
            "## [Unreleased]\n\n## [0.9.0]\n",
            old_version="1.0.0",
            version="1.0.1",
            release_date="2026-07-19",
        )
    with pytest.raises(SkillpackError, match="malformed"):
        finalize(
            "## [Unreleased]\n\n<!-- BEGIN RELEASE PREPARATION NOTE -->\n- Change\n",
            old_version="1.0.0",
            version="1.0.1",
            release_date="2026-07-19",
        )
    with pytest.raises(SkillpackError, match="unresolved"):
        finalize(
            "## [Unreleased]\n\n- This has not been published.\n",
            old_version="1.0.0",
            version="1.0.1",
            release_date="2026-07-19",
        )

    rendered = finalize(
        "## [Unreleased]\n\n"
        "<!-- BEGIN RELEASE PREPARATION NOTE -->\nremove me\n"
        "<!-- END RELEASE PREPARATION NOTE -->\n"
        "- Ship release-candidate `1.0.0`.\n",
        old_version="1.0.0",
        version="1.0.1",
        release_date="2026-07-19",
    )
    assert "remove me" not in rendered
    assert "Ship release `1.0.1`" in rendered


def test_prepare_transition_rejects_invalid_state_dates_and_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def attempt(pack: Pack, operation: str, **kwargs: Any) -> str:
        monkeypatch.setattr(lifecycle_commands, "get_pack", lambda *_args: pack)
        with pytest.raises(SkillpackError) as raised:
            lifecycle_commands._prepare_canonical_changes(
                ROOT,
                pack.id,
                operation=cast(Any, operation),
                **kwargs,
            )
        return str(raised.value)

    assert "Withdrawn" in attempt(
        _pack(publication={"state": "withdrawn", "latest-release": {"version": "1.0.0"}}),
        "prepare-release",
        release_date="2026-07-19",
    )
    assert "explicit release date" in attempt(_pack(), "prepare-release")
    assert "YYYY-MM-DD" in attempt(_pack(), "prepare-release", release_date="not-a-date")
    assert "future" in attempt(
        _pack(),
        "prepare-release",
        release_date=(dt.date.today() + dt.timedelta(days=1)).isoformat(),
    )
    assert "cannot lower" in attempt(
        _pack(version="2.0.0"),
        "prepare-release",
        release_date=dt.date.today().isoformat(),
        version="1.0.0",
    )
    assert "existing published release" in attempt(_pack(), "begin-development", version="1.0.1")
    published = _pack(
        maturity="stable",
        publication={"state": "published", "latest-release": {"version": "1.0.0"}},
    )
    assert "requires --next-version" in attempt(published, "begin-development")
    assert "exceed the latest release" in attempt(published, "begin-development", version="1.0.0")
    advanced = _pack(
        version="1.1.0",
        publication={"state": "published", "latest-release": {"version": "1.0.0"}},
    )
    assert "already ahead of latest-release" in attempt(
        advanced, "begin-development", version="1.1.0"
    )


def test_candidate_validation_restore_and_controlled_path_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _pack()
    monkeypatch.setattr(lifecycle_commands, "load_json_schema", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        lifecycle_commands, "validate_schema_instance", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        lifecycle_commands, "validate_pack_lifecycle", lambda _pack: ["fixture drift"]
    )
    with pytest.raises(SkillpackError, match="fixture drift"):
        lifecycle_commands._candidate_pack(candidate, candidate.raw)

    root = tmp_path / "repository"
    existing = root / "existing.txt"
    created = root / "nested" / "created.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("changed", encoding="utf-8")
    created.parent.mkdir(parents=True)
    created.write_text("created", encoding="utf-8")
    lifecycle_commands._restore(
        root,
        {
            "existing.txt": _Snapshot(content=b"original", mode=0o640),
            "nested/created.txt": _Snapshot(content=None, mode=0o644),
        },
    )
    assert existing.read_bytes() == b"original"
    assert existing.stat().st_mode & 0o777 == 0o640
    assert not created.exists() and not created.parent.exists()

    (root / "dist").mkdir(exist_ok=True)
    (root / "dist/index.html").write_text("legacy", encoding="utf-8")
    monkeypatch.setattr(
        lifecycle_commands, "build_generated_files", lambda _root: {"one.txt": b"x"}
    )
    monkeypatch.setattr(
        lifecycle_commands,
        "walk_tree",
        lambda *_args, **_kwargs: SimpleNamespace(files=[]),
    )
    controlled = lifecycle_commands._controlled_paths(root, ["canonical.txt"])
    assert {"canonical.txt", "one.txt", "dist/index.html"} <= controlled


def test_applied_plan_verifier_rejects_each_drift_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = {
        "generatedOutputs": [{"path": "generated"}],
        "generatedOutputSetSha256": sha256_bytes(
            json.dumps([{"path": "generated"}], sort_keys=True, separators=(",", ":")).encode()
        ),
        "changedFiles": [
            {
                "path": "file.txt",
                "afterSha256": "a" * 64,
                "afterMode": "100644",
            }
        ],
        "unifiedPatch": "patch",
    }
    monkeypatch.setattr(publication, "_generated_output_records", lambda _root: [])
    with pytest.raises(SkillpackError, match="Generated outputs differ"):
        lifecycle_commands._verify_applied_plan(ROOT, plan)

    monkeypatch.setattr(
        publication, "_generated_output_records", lambda _root: plan["generatedOutputs"]
    )
    bad_digest = {**plan, "generatedOutputSetSha256": "0" * 64}
    with pytest.raises(SkillpackError, match="digest differs"):
        lifecycle_commands._verify_applied_plan(ROOT, bad_digest)

    monkeypatch.setattr(publication, "_git_patch_and_paths", lambda *_args: ("other", ["file.txt"]))
    with pytest.raises(SkillpackError, match="patch differs"):
        lifecycle_commands._verify_applied_plan(ROOT, plan)

    monkeypatch.setattr(publication, "_git_patch_and_paths", lambda *_args: ("patch", []))
    with pytest.raises(SkillpackError, match="changed-file set differs"):
        lifecycle_commands._verify_applied_plan(ROOT, plan)

    monkeypatch.setattr(publication, "_git_patch_and_paths", lambda *_args: ("patch", ["file.txt"]))
    monkeypatch.setattr(publication, "_path_record", lambda *_args: ("b" * 64, "100644"))
    with pytest.raises(SkillpackError, match="Applied file"):
        lifecycle_commands._verify_applied_plan(ROOT, plan)

    with pytest.raises(SkillpackError, match="64-character plan digest"):
        lifecycle_commands.apply_lifecycle_plan(
            ROOT,
            "python-best-practices",
            operation="prepare-release",
            release_date="2026-07-19",
            plan_digest="BAD",
        )
