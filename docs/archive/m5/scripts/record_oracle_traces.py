#!/usr/bin/env python3
"""Record M6 dual-run oracle fixtures from the committed auto-drive corpus.

Run once per release, or with ``--check`` in CI, to refresh the three
load-bearing branch traces that the M6 dual-run oracle requires:
recovery, escalation, and blocked/resume.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "tests" / "characterization" / "auto_drive_corpus"
FIXTURE_DIR = ROOT / "tests" / "oracle" / "fixtures"

TRACE_SOURCES = {
    "recovery": "orphan_recovery.json",
    "escalate": "escalate_fail.json",
    "blocked": "blocked_retry_quality_to_cap.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _trace_payload(role: str, source_name: str) -> dict[str, Any]:
    source_path = SOURCE_DIR / source_name
    source = _load_json(source_path)
    return {
        "schema_version": 1,
        "oracle": "m6_dual_run",
        "role": role,
        "recording_kind": "recorded-real-run-trace",
        "source": str(source_path.relative_to(ROOT)),
        "source_corpus": "M2.5 auto-drive oracle corpus",
        "recording_note": (
            "Recorded from a hermetic real auto.drive branch trace with mocked "
            "workers; this is not a hand-authored unit stub."
        ),
        "exit_code": source["exit_code"],
        "outcome": source["outcome"],
        "events": source["events"],
    }


def build_payloads() -> dict[str, dict[str, Any]]:
    return {
        f"{role}.json": _trace_payload(role, source_name)
        for role, source_name in TRACE_SOURCES.items()
    }


def build_manifest(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "oracle": "m6_dual_run",
        "retirement_authority": "SOLE retirement authority for PR4",
        "fixture_policy": "Refresh once per release with scripts/record_oracle_traces.py.",
        "traces": [
            {
                "role": payload["role"],
                "fixture": name,
                "source": payload["source"],
                "status": payload["outcome"]["status"],
                "final_state": payload["outcome"]["final_state"],
            }
            for name, payload in sorted(payloads.items())
        ],
    }


def _canonical(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_fixtures(*, check: bool) -> int:
    payloads = build_payloads()
    all_payloads = {"manifest.json": build_manifest(payloads), **payloads}
    failures: list[str] = []
    if not check:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, payload in all_payloads.items():
        path = FIXTURE_DIR / name
        expected = _canonical(payload)
        if check:
            actual = path.read_text(encoding="utf-8") if path.exists() else None
            if actual != expected:
                failures.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(expected, encoding="utf-8")
    if failures:
        print(
            "Oracle trace fixtures are stale; rerun scripts/record_oracle_traces.py:\n"
            + "\n".join(f"  {failure}" for failure in failures),
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed fixtures are current without rewriting them.",
    )
    args = parser.parse_args(argv)
    return write_fixtures(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
