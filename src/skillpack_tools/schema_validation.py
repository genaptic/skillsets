from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .path_safety import read_regular_bytes
from .util import SkillpackError

MAX_SCHEMA_BYTES = 1024 * 1024
MAX_SCHEMA_NESTING = 64


class _DuplicateKeyError(ValueError):
    pass


class _NonFiniteNumberError(ValueError):
    pass


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise _NonFiniteNumberError(f"non-finite number {value!r} is not permitted")
    return number


def _reject_constant(value: str) -> None:
    raise _NonFiniteNumberError(f"non-finite number {value!r} is not permitted")


def _nesting_exceeds(value: Any, maximum: int) -> bool:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if not isinstance(current, (dict, list)):
            continue
        if depth > maximum:
            return True
        children = current.values() if isinstance(current, dict) else current
        stack.extend((child, depth + 1) for child in children)
    return False


def _is_uri(value: object) -> bool:
    """Provide deterministic URI checking when optional format extras are absent."""

    if not isinstance(value, str):
        return True
    if not value or any(character.isspace() or ord(character) < 0x20 for character in value):
        return False
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {"http", "https"} and not parsed.netloc:
            return False
    except ValueError:
        return False
    return not re.search(r"%(?![0-9A-Fa-f]{2})", value)


def _is_email(value: object) -> bool:
    """Apply the repository's deterministic plausible-address contract."""

    if not isinstance(value, str):
        return True
    atom = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    label = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    return (
        re.fullmatch(rf"{atom}(?:\.{atom})*@{label}(?:\.{label})+", value) is not None
        and len(value) <= 254
    )


def format_checker() -> FormatChecker:
    """Return the repository's deterministic JSON Schema format checker."""

    checker = FormatChecker()
    checker.checkers["uri"] = (_is_uri, ())
    checker.checkers["email"] = (_is_email, ())
    return checker


def schema_errors(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    """Return stable, path-qualified Draft 2020-12 validation errors."""

    validator = Draft202012Validator(schema, format_checker=format_checker())
    found = sorted(
        validator.iter_errors(instance),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            tuple(str(part) for part in error.absolute_schema_path),
            error.message,
        ),
    )
    errors: list[str] = []
    for error in found:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label}:{location}: {error.message}")
    return errors


def load_json_schema(
    path: Path,
    *,
    label: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Load and meta-validate a JSON Schema without mutating repository state."""

    display = label or path.as_posix()
    try:
        content = read_regular_bytes(path, root) if root is not None else path.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"{display}: schema does not exist") from exc
    except SkillpackError as exc:
        raise ValueError(f"{display}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"{display}: schema could not be read: {exc}") from exc
    if len(content) > MAX_SCHEMA_BYTES:
        raise ValueError(f"{display}: schema exceeds the {MAX_SCHEMA_BYTES}-byte limit")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{display}: schema is not valid UTF-8: {exc}") from exc
    try:
        data = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_finite_float,
            parse_constant=_reject_constant,
        )
    except (_DuplicateKeyError, _NonFiniteNumberError) as exc:
        raise ValueError(f"{display}: invalid JSON schema: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{display}: invalid JSON schema: {exc}") from exc
    except RecursionError as exc:
        raise ValueError(
            f"{display}: schema exceeds {MAX_SCHEMA_NESTING} container levels"
        ) from exc
    if _nesting_exceeds(data, MAX_SCHEMA_NESTING):
        raise ValueError(f"{display}: schema exceeds {MAX_SCHEMA_NESTING} container levels")
    if not isinstance(data, dict):
        raise ValueError(f"{display}: JSON schema must be an object")
    try:
        Draft202012Validator.check_schema(data)
    except SchemaError as exc:
        raise ValueError(f"{display}: invalid Draft 2020-12 schema: {exc.message}") from exc
    return data


def validate_schema_instance(
    instance: Any,
    schema: dict[str, Any],
    *,
    label: str,
) -> None:
    """Raise one user-facing error containing every deterministic validation failure."""

    errors = schema_errors(instance, schema, label)
    if errors:
        raise ValueError("configuration validation failed:\n" + "\n".join(errors))
