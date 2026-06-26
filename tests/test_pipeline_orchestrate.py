from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import pipeline_orchestrate as orchestrate


def test_promote_runtime_workflow_cache_writes_ingest_scan(tmp_path: Path) -> None:
    cache_root = tmp_path / "web_search"
    workflow_dir = cache_root / "workflows"
    workflow_dir.mkdir(parents=True)
    raw_url = "https://raw.githubusercontent.com/acme/repo/main/hotshot.json"
    digest = hashlib.sha256(raw_url.encode("utf-8")).hexdigest()
    (workflow_dir / f"{digest}.json").write_text(
        json.dumps(
            {
                "last_node_id": 2,
                "nodes": [
                    {"id": 1, "type": "CheckpointLoaderSimple", "inputs": []},
                    {"id": 2, "type": "KSampler", "inputs": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    (cache_root / "hotshot_query.json").write_text(
        json.dumps(
            {
                "query": "Hotshot ComfyUI workflow",
                "results": [
                    {
                        "title": "hotshot.json",
                        "url": "https://github.com/acme/repo/blob/main/hotshot.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "runtime_scan.json"
    payload = orchestrate.promote_runtime_workflow_cache(cache_root=cache_root, out=out)

    assert payload["summary"]["workflow_rows"] == 1
    row = payload["results"][0]
    assert row["status"] == "comfy_workflow"
    assert row["saved_path"].endswith(f"{digest}.json")
    assert row["source_url"] == "https://github.com/acme/repo/blob/main/hotshot.json"
    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted["results"][0]["workflow_format"] == "comfy_ui"


def test_merge_scan_jsons_combines_results(tmp_path: Path) -> None:
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    first.write_text(json.dumps({"results": [{"status": "comfy_workflow"}]}), encoding="utf-8")
    second.write_text(json.dumps({"results": [{"status": "json_non_comfy"}]}), encoding="utf-8")

    merged = orchestrate.merge_scan_jsons([first, second], tmp_path / "combined.json")

    assert merged["summary"]["result_rows"] == 2
    assert merged["summary"]["workflow_rows"] == 1
