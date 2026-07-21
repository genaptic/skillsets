from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<yaml>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


class SkillpackError(RuntimeError):
    """A user-facing repository tooling error."""


def rollback_after_failure(
    failure: BaseException,
    rollback: Callable[[], None],
    *,
    label: str,
) -> None:
    """Run transactional rollback, preserving an actionable dual-failure diagnostic."""

    try:
        rollback()
    except BaseException as rollback_failure:
        raise SkillpackError(
            f"{label} failed ({type(failure).__name__}: {failure}); rollback also failed "
            f"({type(rollback_failure).__name__}: {rollback_failure})."
        ) from rollback_failure


def find_repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "repository.yaml").is_file():
            return candidate
    raise SkillpackError("Could not find repository.yaml in this directory or any parent.")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SkillpackError(f"Required file does not exist: {path}") from exc
    except yaml.YAMLError as exc:
        raise SkillpackError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillpackError(f"Expected a YAML mapping in {path}.")
    return data


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)


def json_text(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def parse_skill_markdown_text(text: str, label: str | Path) -> tuple[dict[str, Any], str]:
    """Parse already-read skill Markdown without choosing a filesystem access policy."""

    match = FRONTMATTER_RE.match(text)
    if not match:
        raise SkillpackError(f"{label} must begin with YAML frontmatter delimited by --- lines.")
    try:
        metadata = yaml.safe_load(match.group("yaml"))
    except yaml.YAMLError as exc:
        raise SkillpackError(f"Invalid frontmatter in {label}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise SkillpackError(f"Frontmatter in {label} must be a mapping.")
    return metadata, match.group("body")


def parse_skill_markdown(path: Path) -> tuple[dict[str, Any], str]:
    return parse_skill_markdown_text(path.read_text(encoding="utf-8"), path)


def markdown_local_links_text(text: str) -> list[str]:
    """Extract repository-local Markdown links from already-read text."""

    links: list[str] = []
    for raw in MARKDOWN_LINK_RE.findall(text):
        target = raw.strip().split(maxsplit=1)[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        links.append(target.split("#", 1)[0])
    return links


def markdown_local_links(path: Path) -> list[str]:
    return markdown_local_links_text(path.read_text(encoding="utf-8"))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, content: bytes, *, mode: int | None = None) -> None:
    """Atomically write arbitrary bytes while retaining a deliberate file mode.

    Generated skill resources are not necessarily UTF-8 text.  Keeping the byte writer
    as the primitive prevents accidental decoding, newline translation, or corruption of
    images and other binary assets.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    prior_mode = path.stat().st_mode if path.exists() else None
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        if mode is not None:
            temp_path.chmod(mode & 0o777)
        elif prior_mode is not None:
            temp_path.chmod(prior_mode & 0o777)
        else:
            temp_path.chmod(0o644)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write(path: Path, content: str, *, executable: bool = False) -> None:
    """Atomically write normalized UTF-8 text.

    This compatibility wrapper remains the text-oriented API used by configuration and
    report generation.  Binary generated content must use :func:`atomic_write_bytes`.
    """

    atomic_write_bytes(
        path,
        content.encode("utf-8"),
        mode=0o755 if executable else None,
    )


def replace_marked_section(text: str, begin: str, end: str, body: str) -> str:
    pattern = re.compile(
        rf"(?ms)^(?P<indent>[ \t]*){re.escape(begin)}\s*$.*?^(?P=indent){re.escape(end)}\s*$"
    )
    match = pattern.search(text)
    if not match:
        raise SkillpackError(f"Could not find generated section markers: {begin} / {end}")
    replacement = f"{match.group('indent')}{begin}\n{body.rstrip()}\n{match.group('indent')}{end}"
    return text[: match.start()] + replacement + text[match.end() :]


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
