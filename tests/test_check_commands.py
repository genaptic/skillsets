from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import skillpack_tools.checks as checks
from skillpack_tools.util import SkillpackError

ROOT = Path(__file__).resolve().parents[1]


def test_complete_check_order_and_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(checks, "lock", lambda _root, *, check: events.append(f"lock:{check}"))
    monkeypatch.setattr(
        checks,
        "_run",
        lambda _root, command, **_kwargs: events.append(
            "rust" if any(part.endswith("check-rust-assets") for part in command) else "subprocess"
        ),
    )
    monkeypatch.setattr(
        checks,
        "apply_generated_files",
        lambda _root, *, check: events.append(f"generate:{check}"),
    )
    monkeypatch.setattr(
        checks,
        "validate_repository",
        lambda *_args, **_kwargs: (
            events.append("validate") or SimpleNamespace(ok=True, errors=[], warnings=[])
        ),
    )
    monkeypatch.setattr(checks, "raise_for_result", lambda _result: events.append("raise"))
    monkeypatch.setattr(checks, "run_structural_evals", lambda _root: events.append("eval"))
    monkeypatch.setattr(checks, "lint", lambda _root: events.append("lint"))
    monkeypatch.setattr(checks, "test", lambda _root: events.append("test"))

    checks.check(ROOT)
    assert events == [
        "lock:True",
        "rust",
        "generate:True",
        "validate",
        "raise",
        "eval",
        "lint",
        "test",
    ]

    events.clear()

    def fail_lock(_root: Path, *, check: bool) -> None:
        events.append(f"lock:{check}")
        raise SkillpackError("stale lock")

    monkeypatch.setattr(checks, "lock", fail_lock)
    with pytest.raises(SkillpackError, match="stale lock"):
        checks.check(ROOT)
    assert events == ["lock:True"]


def test_subprocess_failure_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        checks.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(["fixture"], 7),
    )
    with pytest.raises(SkillpackError, match="exit code 7"):
        checks._run(ROOT, ["fixture", "--check"])


def test_makefile_uses_one_fixed_repository_environment() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "BOOTSTRAP_PYTHON ?= python3" in makefile
    assert "VENV ?=" not in makefile
    assert not any(line.startswith("PYTHON ?=") for line in makefile.splitlines())
    assert "RUST_CARGO_HOME ?=" not in makefile
    assert "$(VENV)" not in makefile
    assert "$(PYTHON)" not in makefile
    assert "$(RUST_CARGO_HOME)" not in makefile

    rendered = subprocess.check_output(
        [
            "make",
            "-n",
            "VENV=/tmp/legacy-venv",
            "PYTHON=/tmp/legacy-python",
            "RUST_CARGO_HOME=/tmp/legacy-cargo",
            "check",
        ],
        cwd=ROOT,
        text=True,
    )
    assert ".venv/bin/python -m skillpack_tools check" in rendered
    assert "/tmp/legacy" not in rendered


def test_lock_writer_and_freshness_checker_share_the_canonical_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invocation: dict[str, object] = {}

    def run(
        root: Path,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> None:
        invocation.update(root=root, command=command, environment=environment)

    monkeypatch.setattr(checks, "_run", run)
    checks.lock(ROOT, check=False)
    environment = invocation["environment"]
    assert isinstance(environment, dict)
    assert environment["CUSTOM_COMPILE_COMMAND"] == "skillpacks lock"
    assert "#    skillpacks lock\n" in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    checker = (ROOT / "tools/check-dependency-lock").read_text(encoding="utf-8")
    assert 'environment["CUSTOM_COMPILE_COMMAND"] = "skillpacks lock"' in checker
    assert "run `skillpacks lock`." in checker


def test_check_pack_retains_global_validation_and_selects_rust_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    monkeypatch.setattr(
        checks,
        "apply_generated_files",
        lambda _root, *, check: events.append(("generate", check)),
    )

    def validate(_root: Path, **kwargs: object) -> SimpleNamespace:
        events.append(("validate", kwargs))
        return SimpleNamespace(ok=True, errors=[], warnings=[])

    monkeypatch.setattr(checks, "validate_repository", validate)
    monkeypatch.setattr(checks, "raise_for_result", lambda _result: events.append("raise"))
    monkeypatch.setattr(
        checks,
        "run_structural_evals",
        lambda _root, *, skill_filter: events.append(("eval", skill_filter)),
    )
    monkeypatch.setattr(
        checks,
        "_run",
        lambda _root, command, **_kwargs: events.append(("run", tuple(command))),
    )

    checks.check_pack(ROOT, "rust-cli-apps")
    validation = next(item for item in events if isinstance(item, tuple) and item[0] == "validate")
    assert validation[1]["pack_filter"] == "rust-cli-apps"
    rust_commands = [item[1] for item in events if isinstance(item, tuple) and item[0] == "run"]
    assert any(
        any(part.endswith("check-rust-assets") for part in command)
        and command[command.index("--pack") + 1] == "rust-cli-apps"
        for command in rust_commands
    )
    assert ("eval", "rust-cli-application-design") in events
    assert ("eval", "rust-cli-command-development") in events


def test_check_pack_rejects_unknown_pack() -> None:
    with pytest.raises(SkillpackError, match="Unknown pack"):
        checks.check_pack(ROOT, "not-a-pack")
