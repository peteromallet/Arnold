"""CLI entry point for the intent-oracle metric report.

Usage:
    python vibecomfy/intent/report.py --family image --runtime structural
    python vibecomfy/intent/report.py --family video --runtime embedded

Prints a JSON FamilyReport to stdout.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def _main() -> None:
    parser = argparse.ArgumentParser(description="Run intent-oracle edit_correctness and print JSON FamilyReport.")
    parser.add_argument("--family", required=True, choices=["image", "edit", "video"])
    parser.add_argument("--runtime", required=True, choices=["structural", "embedded"])
    args = parser.parse_args()

    from vibecomfy.intent._fixture import load_fixture
    from vibecomfy.intent.metric import edit_correctness

    fixture_dir = Path(__file__).parent.parent.parent / "tests" / "intent" / "fixtures" / args.family
    paths = sorted(fixture_dir.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"No fixtures found under {fixture_dir}")

    fixtures = [load_fixture(p) for p in paths]
    report = edit_correctness(fixtures, family=args.family, runtime=args.runtime)

    def _serialise(obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    print(json.dumps(report.__dict__, default=_serialise, indent=2))


if __name__ == "__main__":
    _main()
