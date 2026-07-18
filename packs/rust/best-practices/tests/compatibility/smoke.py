#!/usr/bin/env python3
"""Offline structural smoke test for one installed or source pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pack_root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[2]),
        help="Pack root containing skillpack.yaml and skills/.",
    )
    args = parser.parse_args()
    pack_root = Path(args.pack_root).resolve()
    expected_path = Path(__file__).with_name("expected-skills.json")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    missing = []
    for skill in expected["skills"]:
        path = pack_root / "skills" / skill / "SKILL.md"
        if not path.is_file():
            missing.append(str(path))
    if missing:
        for path in missing:
            print(f"missing: {path}")
        return 1
    print(f"ok: {expected['pack']} exposes {len(expected['skills'])} expected skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
