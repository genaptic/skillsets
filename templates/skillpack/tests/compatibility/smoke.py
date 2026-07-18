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
    expected = json.loads(Path(__file__).with_name("expected-skills.json").read_text("utf-8"))
    missing = [
        skill
        for skill in expected["skills"]
        if not (pack_root / "skills" / skill / "SKILL.md").is_file()
    ]
    if missing:
        for skill in missing:
            print(f"missing: skills/{skill}/SKILL.md")
        return 1
    print(f"ok: {expected['pack']} exposes {len(expected['skills'])} expected skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
