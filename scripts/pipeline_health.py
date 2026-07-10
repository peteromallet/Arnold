#!/usr/bin/env python3
"""Health checks for the external workflow ingest/enrich/upload pipeline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "external_workflows" / "manifest.json"
DEFAULT_CACHE_ROOT = Path("~/.cache/vibecomfy/web_search").expanduser()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_health(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    max_manifest_age_hours: float = 48.0,
    max_upload_error_rate: float = 0.05,
    max_unsummarized_rate: float = 0.25,
) -> dict[str, Any]:
    alerts: list[str] = []
    now = time.time()
    rows: list[dict[str, Any]] = []

    if not manifest_path.exists():
        alerts.append(f"manifest_missing:{manifest_path}")
        manifest_age_hours = None
    else:
        manifest_age_hours = (now - manifest_path.stat().st_mtime) / 3600
        if manifest_age_hours > max_manifest_age_hours:
            alerts.append(f"manifest_stale:{manifest_age_hours:.1f}h")
        data = _load_json(manifest_path)
        raw_rows = data.get("workflows") if isinstance(data, dict) else []
        rows = [row for row in raw_rows if isinstance(row, dict)] if isinstance(raw_rows, list) else []

    total = len(rows)
    summarized = len([row for row in rows if isinstance(row.get("summary"), dict)])
    unsummarized = total - summarized
    upload_rows = [row for row in rows if isinstance(row.get("hivemind_upload"), dict)]
    upload_errors = [
        row for row in upload_rows
        if (row.get("hivemind_upload") or {}).get("status") in {"error", "verify_failed"}
    ]
    uploaded_or_skipped = [
        row for row in upload_rows
        if (row.get("hivemind_upload") or {}).get("status") in {"uploaded", "skipped_existing"}
    ]

    unsummarized_rate = (unsummarized / total) if total else 0.0
    upload_error_rate = (len(upload_errors) / len(upload_rows)) if upload_rows else 0.0
    if total and unsummarized_rate > max_unsummarized_rate:
        alerts.append(f"unsummarized_rate:{unsummarized_rate:.3f}")
    if upload_rows and upload_error_rate > max_upload_error_rate:
        alerts.append(f"upload_error_rate:{upload_error_rate:.3f}")

    workflow_cache = cache_root / "workflows"
    cached_workflows = sorted(workflow_cache.glob("*.json")) if workflow_cache.is_dir() else []
    newest_cache_age_hours = None
    if cached_workflows:
        newest_cache_age_hours = (now - max(path.stat().st_mtime for path in cached_workflows)) / 3600
    elif cache_root.exists():
        alerts.append("runtime_cache_has_no_workflows")

    return {
        "ok": not alerts,
        "alerts": alerts,
        "manifest": str(manifest_path),
        "manifest_age_hours": manifest_age_hours,
        "total_workflows": total,
        "summarized": summarized,
        "unsummarized": unsummarized,
        "unsummarized_rate": unsummarized_rate,
        "upload_rows": len(upload_rows),
        "uploaded_or_skipped": len(uploaded_or_skipped),
        "upload_errors": len(upload_errors),
        "upload_error_rate": upload_error_rate,
        "runtime_cache_workflows": len(cached_workflows),
        "runtime_cache_newest_age_hours": newest_cache_age_hours,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--max-manifest-age-hours", type=float, default=48.0)
    parser.add_argument("--max-upload-error-rate", type=float, default=0.05)
    parser.add_argument("--max-unsummarized-rate", type=float, default=0.25)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = check_health(
        manifest_path=args.manifest,
        cache_root=args.cache_root.expanduser(),
        max_manifest_age_hours=args.max_manifest_age_hours,
        max_upload_error_rate=args.max_upload_error_rate,
        max_unsummarized_rate=args.max_unsummarized_rate,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "ok" if report["ok"] else "unhealthy"
        print(f"pipeline health: {status}")
        for alert in report["alerts"]:
            print(f"- {alert}")
        print(f"workflows: {report['total_workflows']}")
        print(f"summarized: {report['summarized']}")
        print(f"upload errors: {report['upload_errors']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
