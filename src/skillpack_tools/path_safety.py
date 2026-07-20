from __future__ import annotations

import contextlib
import errno
import os
import secrets
import stat
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .util import SkillpackError, atomic_write_bytes

_REPARSE_POINT = 0x0400
_EXPECTED_UNSET = object()
_DIRECTORY_METADATA_STABLE = os.name != "nt"
_DIRENTRY_IDENTITY_STABLE = os.name != "nt"
_RUNTIME_EXCLUDED_PARTS = {
    ".git",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "cache",
    ".history",
    ".fleet",
    ".zed",
    "__pycache__",
    "evals",
    "secrets",
    "credentials",
}
_RUNTIME_EXCLUDED_NAMES = {
    ".ds_store",
    ".env",
    ".pgpass",
    ".netrc",
    ".npmrc",
    "thumbs.db",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
}
_RUNTIME_EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".swp",
    ".swo",
    ".tmp",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}


@dataclass(frozen=True)
class TreeSnapshot:
    """A deterministic, no-follow snapshot of an existing directory tree."""

    files: tuple[tuple[Path, os.stat_result], ...]
    directories: tuple[tuple[Path, os.stat_result], ...]


def security_name_key(value: str) -> str:
    """Return a portable comparison key for security-sensitive path filtering."""

    normalized = unicodedata.normalize("NFKC", value)
    return unicodedata.normalize("NFKC", normalized.casefold())


def runtime_resource_is_allowed(relative: Path) -> bool:
    """Apply the shared, normalized runtime-resource distribution allowlist."""

    normalized_parts = tuple(security_name_key(part) for part in relative.parts)
    if any(part in _RUNTIME_EXCLUDED_PARTS for part in normalized_parts):
        return False
    return not security_sensitive_path(relative, allow_env_example_file=True)


def security_sensitive_path(
    relative: Path,
    *,
    allow_env_example_file: bool = False,
) -> bool:
    """Classify cache, editor, environment, and credential residue by normalized name."""

    normalized_parts = tuple(security_name_key(part) for part in relative.parts)
    normalized_name = security_name_key(relative.name)
    security_parts = _RUNTIME_EXCLUDED_PARTS - {"evals"}
    if any(part in security_parts for part in normalized_parts):
        return True
    for index, (raw_part, normalized_part) in enumerate(
        zip(relative.parts, normalized_parts, strict=True)
    ):
        if normalized_part.startswith(".env.") and not (
            allow_env_example_file
            and index == len(relative.parts) - 1
            and raw_part == ".env.example"
        ):
            return True
    if normalized_name in _RUNTIME_EXCLUDED_NAMES or normalized_name.endswith("~"):
        return True
    return Path(normalized_name).suffix in _RUNTIME_EXCLUDED_SUFFIXES


def repository_relative(path: Path, root: Path) -> Path:
    """Return a lexical repository-relative path without resolving filesystem links."""

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    path_absolute = Path(os.path.abspath(os.fspath(path)))
    try:
        return path_absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise SkillpackError("Unsafe repository path escapes the repository boundary.") from exc


def repository_label(path: Path, root: Path) -> str:
    relative = repository_relative(path, root)
    return relative.as_posix() if relative.parts else "."


def _is_reparse_point(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT)


def _kind_error(path: Path, root: Path, detail: str) -> SkillpackError:
    return SkillpackError(f"Unsafe repository path `{repository_label(path, root)}`: {detail}.")


def _check_not_link(path: Path, root: Path, metadata: os.stat_result) -> None:
    if stat.S_ISLNK(metadata.st_mode) or _is_reparse_point(metadata):
        raise _kind_error(path, root, "symlinks and filesystem reparse points are not allowed")


def inspect_path(
    path: Path,
    root: Path,
    *,
    leaf_kind: str = "any",
    allow_missing: bool = False,
) -> os.stat_result | None:
    """Inspect every component with ``lstat`` and never follow a filesystem link.

    ``leaf_kind`` is one of ``any``, ``file``, or ``directory``. Missing leaf or parent
    components are allowed only when ``allow_missing`` is true.
    """

    if leaf_kind not in {"any", "file", "directory"}:  # pragma: no cover - internal contract
        raise ValueError(f"Unsupported leaf kind: {leaf_kind}")

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    path_absolute = Path(os.path.abspath(os.fspath(path)))
    relative = repository_relative(path_absolute, root_absolute)

    if root_absolute == Path(root_absolute.anchor):  # pragma: no cover - repository roots vary
        raise SkillpackError("The filesystem anchor cannot be used as a repository root.")
    current_root_component = Path(root_absolute.anchor)
    root_metadata: os.stat_result | None = None
    for part in root_absolute.parts[1:]:
        current_root_component /= part
        try:
            root_metadata = os.lstat(current_root_component)
        except FileNotFoundError as exc:
            raise SkillpackError("The repository root does not exist.") from exc
        if stat.S_ISLNK(root_metadata.st_mode) or _is_reparse_point(root_metadata):
            raise SkillpackError(
                "The repository root contains a symlink or filesystem reparse-point component."
            )
        if not stat.S_ISDIR(root_metadata.st_mode):
            raise SkillpackError("The repository root contains a non-directory component.")
    assert root_metadata is not None

    if not relative.parts:
        if leaf_kind == "file":
            raise _kind_error(root_absolute, root_absolute, "expected a regular file")
        return root_metadata

    current = root_absolute
    for index, part in enumerate(relative.parts):
        current /= part
        is_leaf = index == len(relative.parts) - 1
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if allow_missing:
                return None
            raise _kind_error(current, root_absolute, "required path does not exist") from None
        _check_not_link(current, root_absolute, metadata)
        if not is_leaf and not stat.S_ISDIR(metadata.st_mode):
            raise _kind_error(current, root_absolute, "an ancestor is not a directory")
        if is_leaf:
            if leaf_kind == "file" and not stat.S_ISREG(metadata.st_mode):
                raise _kind_error(current, root_absolute, "expected a regular file")
            if leaf_kind == "directory" and not stat.S_ISDIR(metadata.st_mode):
                raise _kind_error(current, root_absolute, "expected a directory")
            if leaf_kind == "any" and not (
                stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode)
            ):
                raise _kind_error(
                    current, root_absolute, "special filesystem nodes are not allowed"
                )
            return metadata
    raise AssertionError("unreachable")  # pragma: no cover


def _metadata_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _object_identity(metadata: os.stat_result) -> tuple[int, int, int]:
    return (metadata.st_dev, metadata.st_ino, stat.S_IFMT(metadata.st_mode))


def same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return _metadata_identity(left) == _metadata_identity(right)


def _same_directory_identity(left: os.stat_result, right: os.stat_result) -> bool:
    """Compare directory identity without unstable Windows size/time metadata."""

    if not _DIRECTORY_METADATA_STABLE:
        return _object_identity(left) == _object_identity(right)
    return same_identity(left, right)


def _require_expected_preimage(
    path: Path,
    root: Path,
    actual: os.stat_result | None,
    expected: os.stat_result | None | object,
) -> None:
    if expected is _EXPECTED_UNSET:
        return
    if expected is None:
        if actual is not None:
            raise _kind_error(path, root, "destination appeared after preflight")
        return
    assert isinstance(expected, os.stat_result)
    if actual is None or not same_identity(actual, expected):
        raise _kind_error(path, root, "destination changed after preflight")


def verify_preimage(
    path: Path,
    root: Path,
    expected: os.stat_result | None,
) -> os.stat_result | None:
    """Recheck one optional regular-file destination against a prior preflight snapshot."""

    actual = inspect_path(path, root, leaf_kind="file", allow_missing=True)
    _require_expected_preimage(path, root, actual, expected)
    return actual


def walk_tree(
    directory: Path,
    root: Path,
    *,
    allow_missing: bool = False,
    prune_directory: Callable[[Path], bool] | None = None,
) -> TreeSnapshot:
    """Walk a real directory deterministically without following links or special nodes."""

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    directory_absolute = Path(os.path.abspath(os.fspath(directory)))
    metadata = inspect_path(
        directory_absolute,
        root_absolute,
        leaf_kind="directory",
        allow_missing=allow_missing,
    )
    if metadata is None:
        return TreeSnapshot(files=(), directories=())

    files: list[tuple[Path, os.stat_result]] = []
    directories: list[tuple[Path, os.stat_result]] = []

    def scan_directory(
        parent: Path,
        expected: os.stat_result,
    ) -> list[tuple[str, os.stat_result]]:
        current = inspect_path(parent, root_absolute, leaf_kind="directory")
        assert current is not None
        if not _same_directory_identity(current, expected):
            raise _kind_error(parent, root_absolute, "directory changed during inspection")

        try:
            if os.name != "nt" and hasattr(os, "O_DIRECTORY"):
                flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(parent, flags)
                try:
                    opened = os.fstat(descriptor)
                    if not stat.S_ISDIR(opened.st_mode) or not _same_directory_identity(
                        opened, expected
                    ):
                        raise _kind_error(
                            parent,
                            root_absolute,
                            "directory changed during inspection",
                        )
                    with os.scandir(descriptor) as iterator:
                        entries = [
                            (entry.name, entry.stat(follow_symlinks=False)) for entry in iterator
                        ]
                    after = os.fstat(descriptor)
                    if not _same_directory_identity(after, opened):
                        raise _kind_error(
                            parent,
                            root_absolute,
                            "directory changed during inspection",
                        )
                finally:
                    os.close(descriptor)
            else:  # pragma: no cover - exercised by Windows CI
                with os.scandir(parent) as iterator:
                    entries = [
                        (entry.name, entry.stat(follow_symlinks=False)) for entry in iterator
                    ]
                after = inspect_path(parent, root_absolute, leaf_kind="directory")
                assert after is not None
                if not _same_directory_identity(after, expected):
                    raise _kind_error(
                        parent,
                        root_absolute,
                        "directory changed during inspection",
                    )
        except FileNotFoundError:
            raise _kind_error(
                parent, root_absolute, "directory changed during inspection"
            ) from None
        except OSError as exc:
            raise _kind_error(
                parent, root_absolute, "directory could not be inspected safely"
            ) from exc
        return sorted(entries, key=lambda entry: entry[0])

    def visit(parent: Path, expected: os.stat_result) -> None:
        entries = scan_directory(parent, expected)

        portable_names: dict[str, str] = {}
        for name, child_metadata in entries:
            key = security_name_key(name)
            previous = portable_names.get(key)
            if previous is not None and previous != name:
                raise _kind_error(
                    parent,
                    root_absolute,
                    f"portable name collision between {previous!r} and {name!r}",
                )
            portable_names[key] = name

            path = parent / name
            if not _DIRENTRY_IDENTITY_STABLE:
                refreshed = inspect_path(path, root_absolute, leaf_kind="any")
                assert refreshed is not None
                child_metadata = refreshed
            _check_not_link(path, root_absolute, child_metadata)
            if stat.S_ISDIR(child_metadata.st_mode):
                if prune_directory is not None and prune_directory(path):
                    continue
                directories.append((path, child_metadata))
                visit(path, child_metadata)
            elif stat.S_ISREG(child_metadata.st_mode):
                files.append((path, child_metadata))
            else:
                raise _kind_error(path, root_absolute, "special filesystem nodes are not allowed")

    visit(directory_absolute, metadata)
    return TreeSnapshot(files=tuple(files), directories=tuple(directories))


def read_regular_bytes(
    path: Path,
    root: Path,
    *,
    expected: os.stat_result | None = None,
) -> bytes:
    """Read a verified regular file and reject link swaps or concurrent source changes."""

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    path_absolute = Path(os.path.abspath(os.fspath(path)))
    before = inspect_path(path_absolute, root_absolute, leaf_kind="file")
    assert before is not None
    if expected is not None and not same_identity(before, expected):
        raise _kind_error(path_absolute, root_absolute, "source changed after preflight")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path_absolute, flags)
    except OSError as exc:
        raise _kind_error(
            path_absolute, root_absolute, "could not open a regular file safely"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not same_identity(before, opened):
            raise _kind_error(path_absolute, root_absolute, "file changed during inspection")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    try:
        after_path = os.lstat(path_absolute)
    except FileNotFoundError:
        raise _kind_error(path_absolute, root_absolute, "file changed during inspection") from None
    _check_not_link(path_absolute, root_absolute, after_path)
    if not same_identity(before, after_open) or not same_identity(before, after_path):
        raise _kind_error(path_absolute, root_absolute, "file changed while it was being read")
    return b"".join(chunks)


def read_regular_text(path: Path, root: Path, *, encoding: str = "utf-8") -> str:
    return read_regular_bytes(path, root).decode(encoding)


def ensure_directory(path: Path, root: Path, *, mode: int = 0o755) -> None:
    """Create missing repository directories one component at a time with no-follow checks."""

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    path_absolute = Path(os.path.abspath(os.fspath(path)))
    relative = repository_relative(path_absolute, root_absolute)
    root_metadata = inspect_path(root_absolute, root_absolute, leaf_kind="directory")
    assert root_metadata is not None
    if os.name != "nt" and hasattr(os, "O_DIRECTORY"):
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(root_absolute, flags)
        try:
            if _object_identity(os.fstat(descriptor)) != _object_identity(root_metadata):
                raise _kind_error(root_absolute, root_absolute, "root changed after preflight")
            current = root_absolute
            for part in relative.parts:
                current /= part
                try:
                    child_descriptor = os.open(part, flags, dir_fd=descriptor)
                except FileNotFoundError:
                    with contextlib.suppress(FileExistsError):
                        os.mkdir(part, mode, dir_fd=descriptor)
                    child_descriptor = os.open(part, flags, dir_fd=descriptor)
                except OSError as exc:
                    raise _kind_error(current, root_absolute, "expected a real directory") from exc
                os.close(descriptor)
                descriptor = child_descriptor
        finally:
            os.close(descriptor)
    else:  # pragma: no cover - exercised by Windows CI
        current = root_absolute
        for part in relative.parts:
            parent_before = inspect_path(current, root_absolute, leaf_kind="directory")
            assert parent_before is not None
            current /= part
            try:
                metadata = os.lstat(current)
            except FileNotFoundError:
                with contextlib.suppress(FileExistsError):
                    os.mkdir(current, mode)
                metadata = os.lstat(current)
            _check_not_link(current, root_absolute, metadata)
            if not stat.S_ISDIR(metadata.st_mode):
                raise _kind_error(current, root_absolute, "expected a directory")
            parent_after = inspect_path(current.parent, root_absolute, leaf_kind="directory")
            assert parent_after is not None
            if _object_identity(parent_before) != _object_identity(parent_after):
                raise _kind_error(current.parent, root_absolute, "parent changed after preflight")


def safe_atomic_write_bytes(
    path: Path,
    content: bytes,
    root: Path,
    *,
    mode: int,
    expected: os.stat_result | None | object = _EXPECTED_UNSET,
) -> None:
    """Preflight a generated destination and atomically replace only a regular file."""

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    path_absolute = Path(os.path.abspath(os.fspath(path)))
    initial = inspect_path(path_absolute, root_absolute, leaf_kind="file", allow_missing=True)
    _require_expected_preimage(path_absolute, root_absolute, initial, expected)
    ensure_directory(path_absolute.parent, root_absolute)
    parent_before = inspect_path(path_absolute.parent, root_absolute, leaf_kind="directory")
    current = inspect_path(path_absolute, root_absolute, leaf_kind="file", allow_missing=True)
    _require_expected_preimage(path_absolute, root_absolute, current, initial)
    assert parent_before is not None

    if os.name != "nt" and hasattr(os, "O_DIRECTORY"):
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        try:
            directory_fd = os.open(path_absolute.parent, directory_flags)
        except OSError as exc:
            raise _kind_error(
                path_absolute.parent,
                root_absolute,
                "parent could not be opened safely",
            ) from exc
        temporary_name = f".{path_absolute.name}.{secrets.token_hex(12)}"
        temporary_created = False
        try:
            if _object_identity(os.fstat(directory_fd)) != _object_identity(parent_before):
                raise _kind_error(
                    path_absolute.parent, root_absolute, "parent changed after preflight"
                )
            temporary_flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(temporary_name, temporary_flags, 0o600, dir_fd=directory_fd)
            temporary_created = True
            try:
                view = memoryview(content)
                written = 0
                while written < len(view):
                    written += os.write(descriptor, view[written:])
                os.fchmod(descriptor, mode & 0o777)
            finally:
                os.close(descriptor)

            current = inspect_path(
                path_absolute,
                root_absolute,
                leaf_kind="file",
                allow_missing=True,
            )
            _require_expected_preimage(path_absolute, root_absolute, current, initial)
            parent_current = inspect_path(
                path_absolute.parent,
                root_absolute,
                leaf_kind="directory",
            )
            assert parent_current is not None
            if _object_identity(parent_current) != _object_identity(os.fstat(directory_fd)):
                raise _kind_error(
                    path_absolute.parent, root_absolute, "parent changed after preflight"
                )
            os.replace(
                temporary_name,
                path_absolute.name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            temporary_created = False
        finally:
            if temporary_created:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(temporary_name, dir_fd=directory_fd)
            os.close(directory_fd)
    else:  # pragma: no cover - exercised by Windows CI
        parent_current = inspect_path(path_absolute.parent, root_absolute, leaf_kind="directory")
        assert parent_current is not None
        if not _same_directory_identity(parent_current, parent_before):
            raise _kind_error(path_absolute.parent, root_absolute, "parent changed after preflight")
        atomic_write_bytes(path_absolute, content, mode=mode)

    inspect_path(path_absolute, root_absolute, leaf_kind="file")


def unlink_regular(
    path: Path,
    root: Path,
    *,
    expected: os.stat_result | None = None,
) -> None:
    """Delete a stale regular file only if it still matches its inspected preimage."""

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    path_absolute = Path(os.path.abspath(os.fspath(path)))
    metadata = inspect_path(path_absolute, root_absolute, leaf_kind="file")
    assert metadata is not None
    if expected is not None and not same_identity(metadata, expected):
        raise _kind_error(path_absolute, root_absolute, "stale file changed after preflight")
    parent = path_absolute.parent
    parent_metadata = inspect_path(parent, root_absolute, leaf_kind="directory")
    assert parent_metadata is not None
    if os.name != "nt" and hasattr(os, "O_DIRECTORY"):
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(parent, flags)
        try:
            if _object_identity(os.fstat(descriptor)) != _object_identity(parent_metadata):
                raise _kind_error(parent, root_absolute, "parent changed after preflight")
            current = os.stat(path_absolute.name, dir_fd=descriptor, follow_symlinks=False)
            _check_not_link(path_absolute, root_absolute, current)
            if not stat.S_ISREG(current.st_mode) or not same_identity(current, metadata):
                raise _kind_error(
                    path_absolute, root_absolute, "stale file changed after preflight"
                )
            os.unlink(path_absolute.name, dir_fd=descriptor)
        finally:
            os.close(descriptor)
    else:  # pragma: no cover - exercised by Windows CI
        current = inspect_path(path_absolute, root_absolute, leaf_kind="file")
        assert current is not None
        if not same_identity(current, metadata):
            raise _kind_error(path_absolute, root_absolute, "stale file changed after preflight")
        path_absolute.unlink()


def remove_empty_directory(
    path: Path,
    root: Path,
    *,
    expected: os.stat_result | None = None,
) -> None:
    """Remove an empty real directory only if its identity still matches preflight."""

    root_absolute = Path(os.path.abspath(os.fspath(root)))
    path_absolute = Path(os.path.abspath(os.fspath(path)))
    metadata = inspect_path(path_absolute, root_absolute, leaf_kind="directory")
    assert metadata is not None
    if expected is not None and _object_identity(metadata) != _object_identity(expected):
        raise _kind_error(path_absolute, root_absolute, "directory changed after preflight")
    parent = path_absolute.parent
    parent_metadata = inspect_path(parent, root_absolute, leaf_kind="directory")
    assert parent_metadata is not None
    try:
        if os.name != "nt" and hasattr(os, "O_DIRECTORY"):
            flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(parent, flags)
            try:
                if _object_identity(os.fstat(descriptor)) != _object_identity(parent_metadata):
                    raise _kind_error(parent, root_absolute, "parent changed after preflight")
                current = os.stat(path_absolute.name, dir_fd=descriptor, follow_symlinks=False)
                _check_not_link(path_absolute, root_absolute, current)
                if not stat.S_ISDIR(current.st_mode) or _object_identity(
                    current
                ) != _object_identity(metadata):
                    raise _kind_error(
                        path_absolute, root_absolute, "directory changed after preflight"
                    )
                os.rmdir(path_absolute.name, dir_fd=descriptor)
            finally:
                os.close(descriptor)
        else:  # pragma: no cover - exercised by Windows CI
            current = inspect_path(path_absolute, root_absolute, leaf_kind="directory")
            assert current is not None
            if _object_identity(current) != _object_identity(metadata):
                raise _kind_error(path_absolute, root_absolute, "directory changed after preflight")
            path_absolute.rmdir()
    except OSError as exc:
        if exc.errno in {errno.ENOTEMPTY, errno.EEXIST}:
            return
        raise
