from __future__ import annotations

import json
import os
import runpy
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "tools" / "bootstrap"
PORTABLE_LINT = ROOT / "tools" / "lint-portable"


def _bootstrap_namespace() -> dict[str, Any]:
    return runpy.run_path(str(BOOTSTRAP), run_name="skillsets_bootstrap")


def _identity_probe(venv: Path, *, version: tuple[int, int] = (3, 11)) -> str:
    return json.dumps(
        {
            "basePrefix": os.fspath(venv.parent / "base-python"),
            "executable": os.fspath(venv / "bin" / "python"),
            "installPaths": {
                "data": os.fspath(venv),
                "platlib": os.fspath(venv / "lib/python3.11/site-packages"),
                "purelib": os.fspath(venv / "lib/python3.11/site-packages"),
                "scripts": os.fspath(venv / "bin"),
            },
            "prefix": os.fspath(venv),
            "version": list(version),
        }
    )


def test_virtual_environment_interpreter_paths_are_platform_specific(tmp_path: Path) -> None:
    namespace = _bootstrap_namespace()
    path = namespace["venv_python_path"]

    assert path(tmp_path / ".venv", platform="posix") == tmp_path / ".venv/bin/python"
    assert path(tmp_path / ".venv", platform="nt") == tmp_path / ".venv/Scripts/python.exe"


def test_bootstrap_refuses_non_directory_and_symlink_targets(tmp_path: Path) -> None:
    namespace = _bootstrap_namespace()
    check = namespace["_check_venv_target"]
    error = namespace["BootstrapError"]
    venv = tmp_path / ".venv"

    venv.write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(error, match="not a directory"):
        check(tmp_path, venv)
    venv.unlink()

    target = tmp_path / "elsewhere"
    target.mkdir()
    try:
        venv.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("this host does not permit directory symlink creation")
    with pytest.raises(error, match="symbolic link"):
        check(tmp_path, venv)


def test_bootstrap_preserves_incomplete_or_outdated_existing_environments(tmp_path: Path) -> None:
    namespace = _bootstrap_namespace()
    bootstrap = namespace["bootstrap"]
    error = namespace["BootstrapError"]
    venv = tmp_path / ".venv"
    marker = venv / "user-data.txt"
    venv.mkdir()
    marker.write_text("preserve me\n", encoding="utf-8")

    with pytest.raises(error, match="has no interpreter"):
        bootstrap(tmp_path)
    assert marker.read_text(encoding="utf-8") == "preserve me\n"

    python_path = namespace["venv_python_path"](venv)
    python_path.parent.mkdir(parents=True)
    python_path.touch()

    def old_version(
        command: list[str], *, root: Path, capture_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        assert command[0] == os.fspath(python_path)
        assert root == tmp_path
        assert capture_output
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=_identity_probe(venv, version=(3, 10)),
        )

    bootstrap.__globals__["_run"] = old_version
    with pytest.raises(error, match=r"uses Python 3\.10"):
        bootstrap(tmp_path)
    assert marker.read_text(encoding="utf-8") == "preserve me\n"


def test_bootstrap_rejects_interpreter_identity_outside_environment(tmp_path: Path) -> None:
    namespace = _bootstrap_namespace()
    check = namespace["_check_existing_interpreter"]
    error = namespace["BootstrapError"]
    venv = tmp_path / ".venv"
    python_path = namespace["venv_python_path"](venv)
    python_path.parent.mkdir(parents=True)
    python_path.touch()

    probe = json.loads(_identity_probe(venv))
    probe["prefix"] = os.fspath(tmp_path / "system-python")
    check.__globals__["_run"] = lambda command, **_kwargs: subprocess.CompletedProcess(
        command, 0, stdout=json.dumps(probe)
    )
    with pytest.raises(error, match="not isolated"):
        check(python_path, root=tmp_path, venv=venv)

    probe["prefix"] = os.fspath(venv)
    probe["executable"] = os.fspath(tmp_path / "system-python/bin/python")
    with pytest.raises(error, match="outside"):
        check(python_path, root=tmp_path, venv=venv)


def test_bootstrap_rejects_windows_reparse_points_and_redirected_cargo_cache(
    tmp_path: Path,
) -> None:
    namespace = _bootstrap_namespace()
    is_redirect = namespace["_is_link_or_reparse"]
    check_cargo = namespace["_check_cargo_home_target"]
    error = namespace["BootstrapError"]

    class ReparseMetadata:
        st_mode = stat.S_IFDIR
        st_file_attributes = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    class ReparsePath:
        def lstat(self) -> ReparseMetadata:
            return ReparseMetadata()

    assert is_redirect(ReparsePath())

    venv = tmp_path / ".venv"
    venv.mkdir()
    target = tmp_path / "redirected-cache"
    target.mkdir()
    cargo_home = venv / "rust-cargo-home"
    try:
        cargo_home.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("this host does not permit directory symlink creation")
    with pytest.raises(error, match="symbolic link or reparse point"):
        check_cargo(tmp_path, venv, cargo_home)


def test_bootstrap_rejects_redirected_python_installation_descendants(tmp_path: Path) -> None:
    namespace = _bootstrap_namespace()
    check = namespace["_check_install_targets"]
    error = namespace["BootstrapError"]
    venv = tmp_path / ".venv"
    site_parent = venv / "lib/python3.11"
    site_parent.mkdir(parents=True)
    target = tmp_path / "external-site-packages"
    target.mkdir()
    site_packages = site_parent / "site-packages"
    try:
        site_packages.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("this host does not permit directory symlink creation")

    probe = json.loads(_identity_probe(venv))["installPaths"]
    with pytest.raises(error, match=r"redirected \.venv installation target"):
        check(tmp_path, venv, probe)

    probe["purelib"] = os.fspath(tmp_path / "outside")
    probe["platlib"] = os.fspath(tmp_path / "outside")
    with pytest.raises(error, match=r"outside the repository \.venv"):
        check(tmp_path, venv, probe)


def test_bootstrap_rejects_redirected_cargo_cache_descendants(tmp_path: Path) -> None:
    namespace = _bootstrap_namespace()
    check = namespace["_check_cargo_home_target"]
    error = namespace["BootstrapError"]
    venv = tmp_path / ".venv"
    cargo_home = venv / "rust-cargo-home"
    registry = cargo_home / "registry"
    registry.mkdir(parents=True)
    external = tmp_path / "external-index"
    external.mkdir()
    redirected = registry / "index"
    try:
        redirected.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("this host does not permit directory symlink creation")

    with pytest.raises(error, match="redirected Rust dependency cache entry"):
        check(tmp_path, venv, cargo_home)


def test_bootstrap_uses_hashes_explicit_interpreter_and_isolated_rust_cache(
    tmp_path: Path,
) -> None:
    namespace = _bootstrap_namespace()
    bootstrap = namespace["bootstrap"]
    python_path = namespace["venv_python_path"](tmp_path / ".venv")
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], *, root: Path, capture_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        assert root == tmp_path
        commands.append(command)
        if command[1:3] == ["-m", "venv"]:
            python_path.parent.mkdir(parents=True)
            python_path.touch()
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=_identity_probe(tmp_path / ".venv") if capture_output else "",
        )

    bootstrap.__globals__["_run"] = fake_run
    bootstrap(tmp_path)

    assert commands[0][1:3] == ["-m", "venv"]
    assert commands[1][0:2] == [os.fspath(python_path), "-c"]
    assert commands[2] == [
        os.fspath(python_path),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--require-hashes",
        "-r",
        "requirements-dev.txt",
    ]
    assert commands[3][0] == os.fspath(python_path)
    assert commands[3][-4:] == ["--no-deps", "--no-build-isolation", "-e", "."]
    assert commands[4][0:2] == [os.fspath(python_path), "-c"]
    assert commands[5] == [
        os.fspath(python_path),
        os.fspath(tmp_path / "tools/check-rust-assets"),
        "--bootstrap",
        "--cargo-home",
        os.fspath(tmp_path / ".venv/rust-cargo-home"),
    ]


def test_powershell_wrappers_are_location_independent_and_propagate_native_failures() -> None:
    wrappers = {
        "bootstrap.ps1": "tools/bootstrap",
        "check.ps1": "-m skillpack_tools --root $repository check",
        "check-pack.ps1": "-m skillpack_tools --root $repository check-pack $PackId",
    }
    for name, invocation in wrappers.items():
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "$PSScriptRoot" in text
        assert "$LASTEXITCODE" in text
        assert "exit $exitCode" in text
        assert invocation in text

    check_pack = (ROOT / "scripts/check-pack.ps1").read_text(encoding="utf-8")
    assert "ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')" in check_pack


def test_portable_lint_treats_missing_host_tools_as_optional_unless_required(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    namespace = runpy.run_path(str(PORTABLE_LINT), run_name="skillsets_portable_lint")
    main = namespace["main"]
    monkeypatch.setattr(namespace["shutil"], "which", lambda _tool: None)

    monkeypatch.setattr(sys, "argv", ["lint-portable"])
    assert main() == 0
    assert "optional host lint tools unavailable" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["lint-portable", "--require-tools"])
    assert main() == 1
    assert "optional host lint tools unavailable" in capsys.readouterr().err


def test_portable_lint_probes_exact_powershell_analyzer_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(PORTABLE_LINT), run_name="skillsets_portable_lint")
    probe = namespace["powershell_analyzer_available"]
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(namespace["subprocess"], "run", fake_run)
    assert probe("pwsh")
    assert commands[0][:4] == ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive"]
    assert "[version]'1.25.0'" in commands[0][-1]
