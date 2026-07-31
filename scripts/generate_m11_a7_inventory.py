#!/usr/bin/env python3
"""Generate the deterministic M11 A7 legacy-bypass inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from arnold_pipelines.megaplan.orchestration.m11_a7_inventory import (
    write_a7_inventory,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evidence/a7-legacy-bypass-inventory.json"),
    )
    args = parser.parse_args(argv)
    inventory = write_a7_inventory(args.repo_root.resolve(), args.out)
    print(json.dumps({
        "status": inventory["status"],
        "content_sha256": inventory["content_sha256"],
        "static_callsite_count": len(inventory["static_call_sites"]),
        "runtime_trace_count": len(inventory["runtime_trace_coverage"]),
        "legacy_candidate_count": len(inventory["legacy_candidates"]),
        "failure_count": len(inventory["failures"]),
    }, sort_keys=True))
    return 0 if inventory["status"] == "satisfied" else 1


if __name__ == "__main__":
    raise SystemExit(main())
