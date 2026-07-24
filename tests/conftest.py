from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_COPY_IGNORED_NAMES = {
    ".coverage",
    ".DS_Store",
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "releases",
    "tmp",
}


@dataclass(frozen=True)
class _ReusableRepository:
    root: Path
    base_sha: str
    hooks: Path
    environment: dict[str, str]
    config_bytes: bytes
    config_mode: int
    head_bytes: bytes
    head_mode: int


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = _COPY_IGNORED_NAMES & set(names)
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


def _isolated_git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _configure_fixture_repository(root: Path, hooks: Path, environment: dict[str, str]) -> None:
    for key, value in (
        ("user.name", "Fixture"),
        ("user.email", "fixture@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
        ("core.hooksPath", str(hooks)),
        ("core.longpaths", "true"),
    ):
        subprocess.run(
            ["git", "-C", str(root), "config", key, value],
            check=True,
            env=environment,
        )


def _repository_head_and_status(
    root: Path,
    environment: dict[str, str],
) -> tuple[str, str]:
    """Read one stable repository HEAD and its complete working-tree status."""

    command = ["git", "-c", "core.longpaths=true", "-C", str(root)]
    head_before = subprocess.run(
        [*command, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    status = subprocess.run(
        [*command, "status", "--porcelain=v1", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout
    head_after = subprocess.run(
        [*command, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    if head_before != head_after:
        raise AssertionError("fixture source HEAD changed while its state was inspected")
    return head_before, status


def _ignored_source_requires_copy(root: Path, environment: dict[str, str]) -> bool:
    """Return whether ignored content would be retained by the copy fallback."""

    completed = subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "-z",
            "--ignored=matching",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        env=environment,
    )
    for record in completed.stdout.split(b"\0"):
        if not record.startswith(b"!! "):
            continue
        relative = (
            record.removeprefix(b"!! ")
            .rstrip(b"/")
            .decode(
                "utf-8",
                errors="surrogateescape",
            )
        )
        parts = relative.split("/")
        safely_excluded = any(
            part in _COPY_IGNORED_NAMES or part.endswith((".pyc", ".pyo")) for part in parts
        )
        if not safely_excluded:
            return True
    return False


def _clone_clean_generated_source(
    source: Path,
    destination: Path,
    hooks: Path,
    environment: dict[str, str],
) -> str | None:
    """Clone an exact clean source commit, or return ``None`` for a dirty source tree."""

    source_head, source_status = _repository_head_and_status(source, environment)
    if source_status or _ignored_source_requires_copy(source, environment):
        return None
    subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "clone",
            "-q",
            "--shared",
            "--no-checkout",
            "--",
            str(source),
            str(destination),
        ],
        check=True,
        env=environment,
    )
    _configure_fixture_repository(destination, hooks, environment)
    subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-C",
            str(destination),
            "checkout",
            "-q",
            "--detach",
            source_head,
        ],
        check=True,
        env=environment,
    )
    cloned_head, cloned_status = _repository_head_and_status(destination, environment)
    final_source_head, final_source_status = _repository_head_and_status(source, environment)
    if (
        final_source_head != source_head
        or final_source_status
        or _ignored_source_requires_copy(source, environment)
    ):
        raise AssertionError("fixture source changed while its clean commit was cloned")
    if cloned_head != source_head or cloned_status:
        raise AssertionError("clean fixture clone does not match its source commit")
    return source_head


def _restore_metadata_file(path: Path, content: bytes, mode: int) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix="fixture-reset-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _delete_fixture_refs(root: Path, environment: dict[str, str]) -> None:
    command = ["git", "-c", "core.longpaths=true", "-C", str(root)]
    refs = subprocess.run(
        [*command, "for-each-ref", "--format=%(refname)"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.splitlines()
    for ref in refs:
        subprocess.run(
            [*command, "update-ref", "-d", ref],
            check=True,
            env=environment,
        )


def _restore_reusable_repository(repository: _ReusableRepository) -> None:
    """Restore a worker checkout without paying for another full clone."""

    command = ["git", "-c", "core.longpaths=true", "-C", str(repository.root)]
    git_dir = repository.root / ".git"
    _restore_metadata_file(
        git_dir / "config",
        repository.config_bytes,
        repository.config_mode,
    )
    _restore_metadata_file(
        git_dir / "HEAD",
        repository.head_bytes,
        repository.head_mode,
    )
    _delete_fixture_refs(repository.root, repository.environment)
    subprocess.run(
        [*command, "checkout", "-q", "-f", "--detach", repository.base_sha],
        check=True,
        env=repository.environment,
    )
    subprocess.run(
        [*command, "clean", "-q", "-ffdx"],
        check=True,
        env=repository.environment,
    )
    _restore_metadata_file(
        git_dir / "config",
        repository.config_bytes,
        repository.config_mode,
    )
    _restore_metadata_file(git_dir / "HEAD", repository.head_bytes, repository.head_mode)
    remaining_refs = subprocess.run(
        [*command, "for-each-ref", "--format=%(refname)"],
        check=True,
        capture_output=True,
        text=True,
        env=repository.environment,
    ).stdout
    if remaining_refs:
        raise AssertionError("reusable repository fixture retained local refs:\n" + remaining_refs)
    status_command = [*command, "status", "--porcelain=v1", "--untracked-files=all"]
    status = subprocess.run(
        status_command,
        check=True,
        capture_output=True,
        text=True,
        env=repository.environment,
    ).stdout
    if status:
        raise AssertionError(f"reusable repository fixture was not restored:\n{status}")


@contextmanager
def _exclusive_file_lock(path: Path, *, timeout_seconds: float = 120.0) -> Iterator[None]:
    """Hold a cross-platform advisory lock for cross-worker fixture setup."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        deadline = time.monotonic() + timeout_seconds
        if os.name == "nt":
            import msvcrt

            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"timed out waiting for fixture lock {path}") from error
                    time.sleep(0.05)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as error:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"timed out waiting for fixture lock {path}") from error
                    time.sleep(0.05)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _materialize_generated_repository_template(fixture_root: Path) -> Path:
    """Build the immutable generated template under an already-owned directory."""

    from skillpack_tools.generate import apply_generated_files

    root = fixture_root / "w"
    environment = _isolated_git_environment()
    empty_hooks = fixture_root / "h"
    empty_hooks.mkdir()
    clean_source_head = _clone_clean_generated_source(
        ROOT,
        root,
        empty_hooks,
        environment,
    )
    if clean_source_head is None:
        shutil.copytree(ROOT, root, ignore=_copy_ignore)
        subprocess.run(
            ["git", "-c", "core.longpaths=true", "init", "-q", str(root)],
            check=True,
            env=environment,
        )
        _configure_fixture_repository(root, empty_hooks, environment)
        subprocess.run(
            ["git", "-c", "core.longpaths=true", "-C", str(root), "add", "-A"],
            check=True,
            env=environment,
        )
        source_index = subprocess.run(
            [
                "git",
                "-c",
                "core.longpaths=true",
                "-C",
                str(ROOT),
                "ls-files",
                "--stage",
                "-z",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        ).stdout
        executable_paths = [
            entry.split("\t", 1)[1]
            for entry in source_index.split("\0")
            if entry.startswith("100755 ") and "\t" in entry
        ]
        if executable_paths:
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.longpaths=true",
                    "-C",
                    str(root),
                    "update-index",
                    "--chmod=+x",
                    "--",
                    *executable_paths,
                ],
                check=True,
                env=environment,
            )
        apply_generated_files(root)
        subprocess.run(
            ["git", "-c", "core.longpaths=true", "-C", str(root), "add", "-A"],
            check=True,
            env=environment,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "core.longpaths=true",
                "-C",
                str(root),
                "commit",
                "-q",
                "--no-gpg-sign",
                "-m",
                "generated repository fixture",
            ],
            check=True,
            env=environment,
        )
    else:
        apply_generated_files(root, check=True)
        final_source_head, final_source_status = _repository_head_and_status(
            ROOT,
            environment,
        )
        if (
            final_source_head != clean_source_head
            or final_source_status
            or _ignored_source_requires_copy(ROOT, environment)
        ):
            raise AssertionError("fixture source changed while generated state was verified")
    return root


def _template_head(root: Path) -> str:
    environment = _isolated_git_environment()
    return subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()


def _require_ready_generated_template(fixture_root: Path) -> Path:
    root = fixture_root / "w"
    expected_head = (fixture_root / ".ready").read_text(encoding="utf-8").strip()
    actual_head = _template_head(root)
    if not expected_head or actual_head != expected_head:
        raise AssertionError("shared generated repository template does not match its ready marker")
    status = subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_isolated_git_environment(),
    ).stdout
    if status:
        raise AssertionError(f"shared generated repository template is dirty:\n{status}")
    return root


def _materialize_shared_generated_template(fixture_root: Path) -> Path:
    """Build once, publish readiness last, and reject later template mutation."""

    ready = fixture_root / ".ready"
    if ready.is_file():
        return _require_ready_generated_template(fixture_root)
    if fixture_root.exists():
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True)
    try:
        root = _materialize_generated_repository_template(fixture_root)
        temporary_ready = fixture_root / ".ready.tmp"
        temporary_ready.write_text(_template_head(root) + "\n", encoding="utf-8")
        os.replace(temporary_ready, ready)
    except BaseException:
        shutil.rmtree(fixture_root, ignore_errors=True)
        raise
    return _require_ready_generated_template(fixture_root)


@pytest.fixture(scope="session")
def generated_repository_template(
    tmp_path_factory: pytest.TempPathFactory,
    worker_id: str,
) -> Path:
    """Materialize one immutable template across all pytest workers."""

    if worker_id == "master":
        fixture_root = tmp_path_factory.mktemp("g")
        return _materialize_shared_generated_template(fixture_root)

    shared_root = tmp_path_factory.getbasetemp().parent
    fixture_root = shared_root / "g-shared"
    with _exclusive_file_lock(shared_root / "g-shared.lock"):
        return _materialize_shared_generated_template(fixture_root)


@pytest.fixture(scope="session")
def reusable_generated_repository(
    tmp_path_factory: pytest.TempPathFactory,
    generated_repository_template: Path,
    worker_id: str,
) -> _ReusableRepository:
    """Create one isolated checkout per pytest worker."""

    fixture_root = tmp_path_factory.mktemp(f"r-{worker_id}")
    root = fixture_root / "w"
    empty_hooks = fixture_root / "h"
    empty_hooks.mkdir()
    environment = _isolated_git_environment()
    subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "clone",
            "-q",
            "--shared",
            "--",
            str(generated_repository_template),
            str(root),
        ],
        check=True,
        env=environment,
    )
    _configure_fixture_repository(root, empty_hooks, environment)
    base_sha = subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout.strip()
    subprocess.run(
        [
            "git",
            "-c",
            "core.longpaths=true",
            "-C",
            str(root),
            "checkout",
            "-q",
            "--detach",
            base_sha,
        ],
        check=True,
        env=environment,
    )
    _delete_fixture_refs(root, environment)
    config = root / ".git/config"
    head = root / ".git/HEAD"
    return _ReusableRepository(
        root=root,
        base_sha=base_sha,
        hooks=empty_hooks,
        environment=environment,
        config_bytes=config.read_bytes(),
        config_mode=stat.S_IMODE(config.stat().st_mode),
        head_bytes=head.read_bytes(),
        head_mode=stat.S_IMODE(head.stat().st_mode),
    )


@pytest.fixture()
def generated_repo_copy(
    reusable_generated_repository: _ReusableRepository,
) -> Path:
    """Return a clean checkout while amortizing setup across one pytest worker."""

    _restore_reusable_repository(reusable_generated_repository)
    return reusable_generated_repository.root
