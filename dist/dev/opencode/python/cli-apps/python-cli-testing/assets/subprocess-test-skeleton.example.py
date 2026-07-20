"""Adapt this skeleton to the selected framework and public contract."""

from __future__ import annotations

import json
import subprocess
import sys


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "example_cli", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_help_is_offline_and_successful() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert result.stderr == ""


def test_machine_output_is_clean_json() -> None:
    result = run_cli("--output", "json", "list")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    assert result.stderr == ""
