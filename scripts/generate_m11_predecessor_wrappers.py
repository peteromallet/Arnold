#!/usr/bin/env python3
"""Derive M11 predecessor wrappers from milestone-native source evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from arnold_pipelines.megaplan.orchestration.m11_predecessor_wrappers import (
    SATISFIED,
    write_predecessor_wrappers,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate content-addressed, fail-closed M11 predecessor wrappers"
    )
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument("--owner", default="T7")
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=Path("evidence/m11-predecessor-artifacts.json"),
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    wrappers = write_predecessor_wrappers(repo_root, owner=args.owner)
    family_mapping = {
        "m10_handoff": "m10_handoff",
        "c_family": "m10_c01_c20",
        "m5_family": "m5",
        "a7_family": "a7",
    }
    manifest = {
        "schema": "m11.predecessor-artifact-manifest.v1",
        "artifacts": {
            aggregate_family: (
                wrappers[wrapper_family]["content_sha256"]
                if wrappers[wrapper_family]["status"] == SATISFIED
                else None
            )
            for aggregate_family, wrapper_family in family_mapping.items()
        },
        "wrapper_status": {
            aggregate_family: {
                "status": wrappers[wrapper_family]["status"],
                "content_sha256": wrappers[wrapper_family]["content_sha256"],
            }
            for aggregate_family, wrapper_family in family_mapping.items()
        },
    }
    # Keep direct family keys for the existing aggregate manifest reader.
    manifest.update(manifest["artifacts"])

    output_path = args.manifest_out
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    statuses = {
        family: wrapper["status"] for family, wrapper in wrappers.items()
    }
    print(json.dumps({"manifest": str(output_path), "statuses": statuses}, sort_keys=True))
    return 0 if all(status == SATISFIED for status in statuses.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
