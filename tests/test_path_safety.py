from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from skillpack_tools import generate as generate_module
from skillpack_tools import path_safety as path_safety_module
from skillpack_tools import release as release_module
from skillpack_tools.generate import apply_generated_files, build_generated_files
from skillpack_tools.models import Pack, get_pack
from skillpack_tools.path_safety import (
    ensure_directory,
    inspect_path,
    read_regular_bytes,
    safe_atomic_write_bytes,
    security_name_key,
    walk_tree,
)
from skillpack_tools.release import build_release
from skillpack_tools.util import SkillpackError
from skillpack_tools.validate import validate_repository

ROOT = Path(__file__).resolve().parents[1]


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".DS_Store",
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "releases",
    } & set(names)
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


@pytest.fixture()
def repo_copy(tmp_path: Path) -> Path:
    target = tmp_path / "skillsets"
    shutil.copytree(ROOT, target, ignore=_copy_ignore)
    apply_generated_files(target)
    return target


def _symlink_or_skip(target: Path, link: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:  # pragma: no cover - depends on Windows developer-mode privileges
        pytest.skip(f"This platform cannot create the required test symlink: {exc}")


def test_pruned_walk_checks_the_directory_node_before_skipping_descendants(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    ignored = root / ".venv"
    ignored.mkdir(parents=True)
    external = tmp_path / "outside"
    external.mkdir()
    _symlink_or_skip(external, ignored / "internal-link", directory=True)

    snapshot = walk_tree(
        root,
        root,
        prune_directory=lambda path: security_name_key(path.name) == ".venv",
    )
    assert snapshot.files == ()
    assert snapshot.directories == ()

    shutil.rmtree(ignored)
    _symlink_or_skip(external, ignored, directory=True)
    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points"):
        walk_tree(
            root,
            root,
            prune_directory=lambda path: security_name_key(path.name) == ".venv",
        )


def test_walk_rejects_portable_name_collisions_before_pruning(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ignored").mkdir()
    (root / "ｉｇｎｏｒｅｄ").mkdir()

    with pytest.raises(SkillpackError, match="portable name collision"):
        walk_tree(root, root, prune_directory=lambda _path: True)


def test_repository_root_with_symlink_ancestor_is_rejected(tmp_path: Path) -> None:
    actual_parent = tmp_path / "actual"
    repository = actual_parent / "repository"
    repository.mkdir(parents=True)
    alias = tmp_path / "alias"
    _symlink_or_skip(actual_parent, alias, directory=True)

    with pytest.raises(SkillpackError, match="repository root contains a symlink"):
        walk_tree(alias / "repository", alias / "repository")


def test_walk_rejects_directory_replaced_between_listing_and_recursion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "canonical.txt").write_bytes(b"canonical\n")
    external = tmp_path / "outside"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_bytes(b"outside must not be enumerated\n")
    before = (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns)
    parked = root / "parked"
    original_check = path_safety_module._check_not_link
    replaced = False

    def replace_after_entry_check(
        path: Path,
        repository: Path,
        metadata: os.stat_result,
    ) -> None:
        nonlocal replaced
        original_check(path, repository, metadata)
        if path == nested and not replaced:
            nested.rename(parked)
            nested.symlink_to(external, target_is_directory=True)
            replaced = True

    monkeypatch.setattr(path_safety_module, "_check_not_link", replace_after_entry_check)
    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points"):
        walk_tree(root, root)

    assert replaced
    assert (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns) == before


def test_windows_directory_identity_ignores_unstable_size_and_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()
    before = directory.stat()
    values = list(before)
    values[6] += 4096
    values[8] += 1
    after = os.stat_result(values)

    assert not path_safety_module.same_identity(before, after)
    monkeypatch.setattr(path_safety_module, "_DIRECTORY_METADATA_STABLE", False)
    assert path_safety_module._same_directory_identity(before, after)


@pytest.mark.skipif(os.name == "nt", reason="dir-fd race fixture is POSIX-specific")
def test_directory_creation_refuses_parent_replaced_with_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    parent = root / "parent"
    parent.mkdir(parents=True)
    parked = root / "parked"
    external = tmp_path / "outside"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_bytes(b"outside must not change\n")
    before = (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns)
    original_open = path_safety_module.os.open
    replaced = False

    def racing_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal replaced
        if path == "parent" and not replaced:
            parent.rename(parked)
            parent.symlink_to(external, target_is_directory=True)
            replaced = True
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(path_safety_module.os, "open", racing_open)
    with pytest.raises(SkillpackError, match="expected a real directory"):
        ensure_directory(parent / "created", root)

    assert replaced
    assert not (external / "created").exists()
    assert (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns) == before


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions require Windows")
def test_walk_rejects_windows_directory_junction_without_touching_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    external = tmp_path / "outside"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_bytes(b"outside must not change\n")
    before = (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns)
    junction = root / "linked-directory"

    command = [
        os.environ.get("COMSPEC", "cmd.exe"),
        "/d",
        "/s",
        "/c",
        "mklink",
        "/J",
        str(junction),
        str(external),
    ]
    created = subprocess.run(command, capture_output=True, text=True, check=False)
    if created.returncode != 0:  # pragma: no cover - depends on Windows filesystem policy
        pytest.skip(
            "This Windows environment cannot create the required directory junction: "
            f"{created.stderr.strip() or created.stdout.strip()}"
        )

    try:
        with pytest.raises(
            SkillpackError,
            match="symlinks and filesystem reparse points are not allowed",
        ) as caught:
            walk_tree(root, root)

        assert str(external) not in str(caught.value)
        assert (
            sentinel.read_bytes(),
            sentinel.stat().st_mode,
            sentinel.stat().st_mtime_ns,
        ) == before
    finally:
        # RemoveDirectory removes the junction itself and never traverses its target.
        if os.path.lexists(junction):
            junction.rmdir()

    assert (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns) == before


def test_safe_atomic_write_refuses_changed_or_new_destination_preimages(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    existing = root / "generated.json"
    existing.write_bytes(b"reviewed\n")
    reviewed = inspect_path(existing, root, leaf_kind="file")
    assert reviewed is not None
    existing.write_bytes(b"concurrent edit\n")

    with pytest.raises(SkillpackError, match="destination changed after preflight"):
        safe_atomic_write_bytes(existing, b"generated\n", root, mode=0o644, expected=reviewed)
    assert existing.read_bytes() == b"concurrent edit\n"

    appeared = root / "appeared.json"
    appeared.write_bytes(b"concurrent creation\n")
    with pytest.raises(SkillpackError, match="destination appeared after preflight"):
        safe_atomic_write_bytes(appeared, b"generated\n", root, mode=0o644, expected=None)
    assert appeared.read_bytes() == b"concurrent creation\n"


@pytest.mark.parametrize("dangling", [False, True])
@pytest.mark.parametrize("check", [False, True])
def test_generated_root_symlink_fails_before_any_repair(
    repo_copy: Path,
    tmp_path: Path,
    dangling: bool,
    check: bool,
) -> None:
    marketplace = repo_copy / ".claude-plugin" / "marketplace.json"
    marketplace.write_bytes(b"stale but must remain unchanged\n")
    before = marketplace.read_bytes()

    generated_root = repo_copy / "dist" / "opencode"
    shutil.rmtree(generated_root)
    external = tmp_path / "outside"
    if not dangling:
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_bytes(b"outside must not change\n")
        sentinel_mode = sentinel.stat().st_mode
        sentinel_mtime = sentinel.stat().st_mtime_ns
    _symlink_or_skip(external, generated_root, directory=True)

    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points") as caught:
        apply_generated_files(repo_copy, check=check)

    assert str(external) not in str(caught.value)
    assert marketplace.read_bytes() == before
    if not dangling:
        assert sentinel.read_bytes() == b"outside must not change\n"
        assert sentinel.stat().st_mode == sentinel_mode
        assert sentinel.stat().st_mtime_ns == sentinel_mtime


def test_generation_refuses_destination_changed_after_global_preflight(
    repo_copy: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marketplace = repo_copy / ".claude-plugin" / "marketplace.json"
    original_walk = generate_module.walk_tree
    changed = False

    def racing_walk(directory: Path, root: Path, **kwargs: object):
        nonlocal changed
        snapshot = original_walk(directory, root, **kwargs)
        if directory == repo_copy / "dist" / "opencode" and not changed:
            marketplace.write_bytes(b"concurrent edit\n")
            changed = True
        return snapshot

    monkeypatch.setattr(generate_module, "walk_tree", racing_walk)
    with pytest.raises(SkillpackError, match="destination changed after preflight"):
        apply_generated_files(repo_copy)

    assert changed
    assert marketplace.read_bytes() == b"concurrent edit\n"


def test_generation_refuses_canonical_source_changed_during_preflight(
    repo_copy: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marketplace = repo_copy / ".claude-plugin" / "marketplace.json"
    before = marketplace.read_bytes()
    source = (
        repo_copy
        / "packs"
        / "python"
        / "best-practices"
        / "skills"
        / "python-project-layout"
        / "references"
        / "guide.md"
    )
    original_build = generate_module.build_generated_files

    def racing_build(root: Path):
        generated = original_build(root)
        source.write_bytes(source.read_bytes() + b"\nConcurrent edit.\n")
        return generated

    monkeypatch.setattr(generate_module, "build_generated_files", racing_build)
    with pytest.raises(SkillpackError, match="Canonical pack content changed"):
        apply_generated_files(repo_copy)

    assert marketplace.read_bytes() == before


def test_stale_cleanup_refuses_file_replaced_after_preflight(
    repo_copy: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = repo_copy / "dist" / "opencode" / "stale.txt"
    stale.write_bytes(b"stale generated content\n")
    external = tmp_path / "outside.txt"
    external.write_bytes(b"outside must not change\n")
    before = (external.read_bytes(), external.stat().st_mode, external.stat().st_mtime_ns)
    original_unlink = generate_module.unlink_regular
    replaced = False

    def racing_unlink(
        path: Path,
        root: Path,
        *,
        expected: os.stat_result | None = None,
    ) -> None:
        nonlocal replaced
        if path == stale and not replaced:
            stale.unlink()
            stale.symlink_to(external)
            replaced = True
        original_unlink(path, root, expected=expected)

    monkeypatch.setattr(generate_module, "unlink_regular", racing_unlink)
    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points"):
        apply_generated_files(repo_copy)

    assert replaced
    assert (external.read_bytes(), external.stat().st_mode, external.stat().st_mtime_ns) == before


def test_runtime_resource_symlink_is_rejected_before_external_content_is_read(
    repo_copy: Path,
    tmp_path: Path,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    skill = pack.path / "skills" / "python-project-layout"
    assets = skill / "assets"
    shutil.rmtree(assets)
    external = tmp_path / "outside-assets"
    external.mkdir()
    secret = external / "not-a-resource.txt"
    secret.write_bytes(b"external secret\n")
    before = (secret.read_bytes(), secret.stat().st_mode, secret.stat().st_mtime_ns)
    _symlink_or_skip(external, assets, directory=True)

    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points") as caught:
        build_generated_files(repo_copy)

    assert "packs/python/best-practices/skills/python-project-layout/assets" in str(caught.value)
    assert str(external) not in str(caught.value)
    assert (secret.read_bytes(), secret.stat().st_mode, secret.stat().st_mtime_ns) == before


def test_runtime_resource_file_symlink_and_safe_reader_are_rejected(
    repo_copy: Path,
    tmp_path: Path,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    skill = pack.path / "skills" / "python-project-layout"
    external = tmp_path / "outside.txt"
    external.write_bytes(b"do not package\n")
    link = skill / "assets" / "linked.txt"
    _symlink_or_skip(external, link)

    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points"):
        walk_tree(skill / "assets", repo_copy)
    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points"):
        read_regular_bytes(link, repo_copy)
    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points"):
        build_generated_files(repo_copy)


def test_validator_reports_canonical_symlink_without_disclosing_external_target(
    repo_copy: Path,
    tmp_path: Path,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    external = tmp_path / "outside.txt"
    external.write_bytes(b"do not inspect\n")
    link = pack.path / "skills" / "python-project-layout" / "assets" / "linked.txt"
    _symlink_or_skip(external, link)

    result = validate_repository(repo_copy)

    assert not result.ok
    combined = "\n".join(result.errors)
    assert "packs/python/best-practices/skills/python-project-layout/assets/linked.txt" in combined
    assert "symlinks and filesystem reparse points are not allowed" in combined
    assert str(external) not in combined


def test_draft_release_output_symlink_cannot_redirect_archive_writes(
    repo_copy: Path,
    tmp_path: Path,
) -> None:
    releases = repo_copy / "dist" / "releases"
    if releases.exists():
        shutil.rmtree(releases)
    external = tmp_path / "outside-releases"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_bytes(b"outside must not change\n")
    before = (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns)
    _symlink_or_skip(external, releases, directory=True)

    with pytest.raises(SkillpackError, match="symlinks and filesystem reparse points") as caught:
        build_release(repo_copy, "python-best-practices", draft=True)

    assert str(external) not in str(caught.value)
    assert (sentinel.read_bytes(), sentinel.stat().st_mode, sentinel.stat().st_mtime_ns) == before
    assert sorted(path.name for path in external.iterdir()) == ["sentinel.txt"]


def test_draft_release_refuses_source_changed_after_allowlist_preflight(
    repo_copy: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    source = pack.path / "skillpack.yaml"
    original_safe_files = release_module._safe_release_files
    changed = False

    def racing_safe_files(root: Path, selected_pack: Pack):
        nonlocal changed
        files = original_safe_files(root, selected_pack)
        source.write_bytes(source.read_bytes() + b"# concurrent edit\n")
        changed = True
        return files

    monkeypatch.setattr(release_module, "_safe_release_files", racing_safe_files)
    with pytest.raises(SkillpackError, match="source changed after preflight"):
        build_release(repo_copy, pack.id, draft=True)

    assert changed
    releases = repo_copy / "dist" / "releases"
    assert not releases.exists() or not any(releases.iterdir())


@pytest.mark.skipif(os.name == "nt", reason="Windows does not provide os.mkfifo")
def test_runtime_special_node_is_rejected(repo_copy: Path) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    fifo = pack.path / "skills" / "python-project-layout" / "assets" / "runtime.fifo"
    os.mkfifo(fifo)

    with pytest.raises(SkillpackError, match="special filesystem nodes are not allowed"):
        build_generated_files(repo_copy)


def test_runtime_security_filter_is_unicode_normalized_and_case_insensitive(
    repo_copy: Path,
) -> None:
    pack = get_pack(repo_copy, "python-best-practices")
    assets = pack.path / "skills" / "python-project-layout" / "assets"
    exact_example = assets / ".env.example"
    exact_example.write_bytes(b"TOKEN=\n")
    (assets / "résumé.txt").write_bytes(b"allowed unicode resource\n")

    allowed = build_generated_files(repo_copy)
    prefix = "dist/opencode/python/best-practices/python-project-layout/assets/"
    allowed_resources = {path.removeprefix(prefix) for path in allowed if path.startswith(prefix)}
    assert ".env.example" in allowed_resources
    assert "résumé.txt" in allowed_resources

    # Case-insensitive filesystems cannot hold both spellings at once, so test the
    # rejected compatibility spelling after proving the exact allowlist exception.
    exact_example.unlink()
    env_example_directory = assets / ".env.example"
    env_example_directory.mkdir()
    (env_example_directory / "hidden.txt").write_bytes(b"TOKEN=nope\n")
    directory_generated = build_generated_files(repo_copy)
    assert not any(path.endswith(".env.example/hidden.txt") for path in directory_generated)
    shutil.rmtree(env_example_directory)

    excluded = {
        "Secrets/hidden.txt": b"secret directory\n",
        "CREDENTIALS.JSON": b"credentials\n",
        "ID_ED25519": b"private key\n",
        ".ENV.production": b"TOKEN=nope\n",
        ".ENV.EXAMPLE": b"TOKEN=nope\n",
        "PRIVATE.PEM": b"private key\n",
        "__PyCache__/module.PYC": b"bytecode\n",
    }
    for relative, content in excluded.items():
        path = assets / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    generated = build_generated_files(repo_copy)
    generated_resources = {
        path.removeprefix(prefix) for path in generated if path.startswith(prefix)
    }

    assert "résumé.txt" in generated_resources
    assert not generated_resources.intersection(excluded)

    (assets / "CREDENTIALS.JSON").unlink()
    compatibility_name = "ＣＲＥＤＥＮＴＩＡＬＳ.json"
    (assets / compatibility_name).write_bytes(b"compatibility spelling\n")
    compatibility_generated = build_generated_files(repo_copy)
    assert not any(path.endswith(compatibility_name) for path in compatibility_generated)
    assert security_name_key("ＣＲＥＤＥＮＴＩＡＬＳ.JSON") == "credentials.json"
    assert security_name_key("Straße") == security_name_key("STRASSE")


@pytest.mark.parametrize(
    "relative",
    (
        "docs/__PyCache__/module.PYC",
        "docs/Secrets/hidden.txt",
        "docs/ＣＲＥＤＥＮＴＩＡＬＳ/hidden.txt",
    ),
)
def test_repository_validation_reports_normalized_residue_directories(
    repo_copy: Path,
    relative: str,
) -> None:
    residue = repo_copy / relative
    residue.parent.mkdir(parents=True, exist_ok=True)
    residue.write_bytes(b"must not be distributed\n")

    result = validate_repository(repo_copy)

    assert not result.ok
    combined = "\n".join(result.errors)
    assert residue.parent.relative_to(repo_copy).as_posix() in combined
    assert "must not be committed" in combined
