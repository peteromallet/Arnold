from __future__ import annotations

import json
import os
import time
from pathlib import Path

from scripts import pipeline_health


def test_health_reports_upload_error_rate(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "workflows": [
                    {"workflow_id": "ok", "summary": {}, "hivemind_upload": {"status": "uploaded"}},
                    {"workflow_id": "bad", "summary": {}, "hivemind_upload": {"status": "error"}},
                ]
            }
        ),
        encoding="utf-8",
    )

    report = pipeline_health.check_health(
        manifest_path=manifest,
        cache_root=tmp_path / "missing-cache",
        max_upload_error_rate=0.1,
    )

    assert report["ok"] is False
    assert "upload_error_rate:0.500" in report["alerts"]


def test_health_reports_stale_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"workflows": []}), encoding="utf-8")
    old = time.time() - 72 * 3600
    os.utime(manifest, (old, old))

    report = pipeline_health.check_health(
        manifest_path=manifest,
        cache_root=tmp_path / "missing-cache",
        max_manifest_age_hours=24,
    )

    assert report["ok"] is False
    assert any(alert.startswith("manifest_stale:") for alert in report["alerts"])
