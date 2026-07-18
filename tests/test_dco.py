from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK_DCO = ROOT / "tools/check-dco"
AUTHOR_NAME = "Test Author"
AUTHOR_EMAIL = "author@example.com"
DEPENDABOT_NAME = "dependabot[bot]"
DEPENDABOT_EMAIL = "49699333+dependabot[bot]@users.noreply.github.com"
DEPENDABOT_TRAILER_EMAIL = "support@github.com"


def _git(repository: Path, *arguments: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _identity_environment(name: str = AUTHOR_NAME, email: str = AUTHOR_EMAIL) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
        }
    )
    return environment


def _commit(
    repository: Path,
    message: str,
    *,
    name: str = AUTHOR_NAME,
    email: str = AUTHOR_EMAIL,
) -> str:
    _git(
        repository,
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "--no-verify",
        "-m",
        message,
        env=_identity_environment(name, email),
    )
    return _git(repository, "rev-parse", "HEAD")


@pytest.fixture()
def repository(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "repository"
    path.mkdir()
    _git(path, "init", "--initial-branch=main")
    base = _commit(path, "base commit")
    return path, base


def _check(
    repository: Path,
    base: str,
    head: str,
    *,
    allow_dependabot: bool = False,
) -> subprocess.CompletedProcess[str]:
    arguments = [sys.executable, os.fspath(CHECK_DCO)]
    if allow_dependabot:
        arguments.append("--allow-dependabot")
    arguments.extend((base, head))
    return subprocess.run(
        arguments,
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )


def _signoff(name: str = AUTHOR_NAME, email: str = AUTHOR_EMAIL) -> str:
    return f"Signed-off-by: {name} <{email}>"


def test_accepts_matching_terminal_trailer(repository: tuple[Path, str]) -> None:
    path, base = repository
    head = _commit(path, f"valid commit\n\n{_signoff()}")

    result = _check(path, base, head)

    assert result.returncode == 0, result.stderr
    assert "passed for 1 commit" in result.stdout


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("missing signoff", "has no Signed-off-by"),
        ("malformed\n\nSigned-off-by: Test Author", "malformed"),
        (
            f"spoofed body\n\n{_signoff()}\n\nThis is still body text.",
            "has no Signed-off-by",
        ),
        (
            "mismatched\n\nSigned-off-by: Different Person <different@example.com>",
            "does not match",
        ),
    ],
)
def test_rejects_absent_malformed_spoofed_and_mismatched_trailers(
    repository: tuple[Path, str],
    message: str,
    reason: str,
) -> None:
    path, base = repository
    head = _commit(path, message)

    result = _check(path, base, head)

    assert result.returncode == 1
    assert head in result.stderr
    assert f"{AUTHOR_NAME} <{AUTHOR_EMAIL}>" in result.stderr
    assert _signoff() in result.stderr
    assert reason in result.stderr
    assert "Remediation:" in result.stderr


def test_reports_every_failure_in_a_mixed_range(repository: tuple[Path, str]) -> None:
    path, base = repository
    first_failure = _commit(path, "unsigned first")
    _commit(path, f"valid middle\n\n{_signoff()}")
    second_failure = _commit(path, "unsigned last")

    result = _check(path, base, second_failure)

    assert result.returncode == 1
    assert "failed for 2 of 3 commit" in result.stderr
    assert first_failure in result.stderr
    assert second_failure in result.stderr


def test_inspects_merge_commits(repository: tuple[Path, str]) -> None:
    path, base = repository
    _git(path, "checkout", "-b", "side")
    _commit(path, f"signed side\n\n{_signoff()}")
    _git(path, "checkout", "main")
    _commit(path, f"signed main\n\n{_signoff()}")
    _git(
        path,
        "-c",
        "commit.gpgsign=false",
        "merge",
        "--no-ff",
        "--no-verify",
        "side",
        "-m",
        "unsigned merge",
        env=_identity_environment(),
    )
    merge_sha = _git(path, "rev-parse", "HEAD")

    result = _check(path, base, merge_sha)

    assert result.returncode == 1
    assert "failed for 1 of 3 commit" in result.stderr
    assert merge_sha in result.stderr


@pytest.mark.parametrize(
    ("base_value", "head_value", "expected"),
    [
        ("base-short", "head", "BASE_SHA must be"),
        ("base", "HEAD", "HEAD_SHA must be"),
        ("base", "0" * 40, "HEAD_SHA is not a readable commit"),
    ],
)
def test_rejects_invalid_full_sha_inputs(
    repository: tuple[Path, str],
    base_value: str,
    head_value: str,
    expected: str,
) -> None:
    path, base = repository
    head = _commit(path, f"valid\n\n{_signoff()}")
    resolved_base = base[:12] if base_value == "base-short" else base
    resolved_head = head.upper() if head_value == "HEAD" else head_value

    result = _check(path, resolved_base, resolved_head)

    assert result.returncode == 2
    assert expected in result.stderr


def test_dependabot_exemption_is_narrow_and_requires_pr_opt_in(
    repository: tuple[Path, str],
) -> None:
    path, base = repository
    live_style_message = (
        "dependabot update\n\n"
        "Bumps actions/upload-artifact.\n\n"
        "---\n"
        "updated-dependencies:\n"
        "- dependency-name: actions/upload-artifact\n"
        "  dependency-version: 7.0.1\n"
        "...\n\n"
        f"{_signoff(DEPENDABOT_NAME, DEPENDABOT_TRAILER_EMAIL)}"
    )
    bot_commit = _commit(
        path,
        live_style_message,
        name=DEPENDABOT_NAME,
        email=DEPENDABOT_EMAIL,
    )

    without_opt_in = _check(path, base, bot_commit)
    with_opt_in = _check(path, base, bot_commit, allow_dependabot=True)

    assert without_opt_in.returncode == 1
    assert with_opt_in.returncode == 0, with_opt_in.stderr

    spoofed_bot = _commit(
        path,
        "spoofed dependabot",
        name=DEPENDABOT_NAME,
        email="dependabot@example.com",
    )
    spoofed_result = _check(path, bot_commit, spoofed_bot, allow_dependabot=True)
    assert spoofed_result.returncode == 1
    assert "exact verified noreply identity" in spoofed_result.stderr


def test_human_commit_on_dependabot_branch_still_fails(repository: tuple[Path, str]) -> None:
    path, base = repository
    _commit(
        path,
        f"dependabot update\n\n{_signoff(DEPENDABOT_NAME, DEPENDABOT_TRAILER_EMAIL)}",
        name=DEPENDABOT_NAME,
        email=DEPENDABOT_EMAIL,
    )
    human_commit = _commit(path, "human follow-up")

    result = _check(path, base, human_commit, allow_dependabot=True)

    assert result.returncode == 1
    assert human_commit in result.stderr


@pytest.mark.parametrize(
    "message",
    [
        "dependabot update without trailer",
        f"dependabot update\n\n{_signoff(DEPENDABOT_NAME, DEPENDABOT_EMAIL)}",
        "dependabot update\n\nSigned-off-by: dependabot[bot] <different@example.com>",
        "dependabot update\n\nSigned-off-by: dependabot[bot]",
    ],
)
def test_dependabot_exemption_rejects_missing_malformed_or_different_trailer(
    repository: tuple[Path, str],
    message: str,
) -> None:
    path, base = repository
    head = _commit(
        path,
        message,
        name=DEPENDABOT_NAME,
        email=DEPENDABOT_EMAIL,
    )

    result = _check(path, base, head, allow_dependabot=True)

    assert result.returncode == 1
    assert "exact terminal trailer" in result.stderr


def test_rejects_divergent_commit_range(repository: tuple[Path, str]) -> None:
    path, common = repository
    main_head = _commit(path, f"main commit\n\n{_signoff()}")
    _git(path, "checkout", "-b", "side", common)
    side_head = _commit(path, f"side commit\n\n{_signoff()}")

    result = _check(path, side_head, main_head)

    assert result.returncode == 2
    assert "BASE_SHA is not an ancestor of HEAD_SHA" in result.stderr
