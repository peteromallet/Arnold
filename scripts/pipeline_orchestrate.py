#!/usr/bin/env python3
"""Run the external workflow discovery -> ingest -> enrich/upload pipeline.

The runtime agent can discover concrete workflow JSON during web research and
cache it under ``~/.cache/vibecomfy/web_search/workflows``. This orchestrator
promotes that cache into the same scanner manifest shape as Discord/GitHub
collectors, then runs ingest and enrichment/upload as one resumable command.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = Path("~/.cache/vibecomfy/web_search").expanduser()
DEFAULT_PIPELINE_DIR = REPO_ROOT / "external_workflows" / ".pipeline"
DEFAULT_MANIFEST = REPO_ROOT / "external_workflows" / "manifest.json"
DEFAULT_CORPUS_DIR = REPO_ROOT / "external_workflows" / "corpus"

def _github_blob_raw_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.casefold() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[2] != "blob":
        return None
    owner, repo, _, ref, *path_parts = parts
    if not path_parts:
        return None
    path = "/".join(path_parts)
    if not path.casefold().endswith((".json", ".workflow")):
        return None
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def _classify_source_workflow(raw: Any) -> tuple[str, list[str]] | None:
    if not isinstance(raw, dict):
        return None
    nodes = raw.get("nodes")
    if isinstance(nodes, list):
        classes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type") or node.get("class_type")
            if node_type or "inputs" in node or "widgets_values" in node:
                classes.append(str(node_type or "unknown"))
        if len(classes) >= 2:
            return "comfy_ui", classes
    api_classes = []
    numeric_keys = 0
    for key, node in raw.items():
        if str(key).isdigit():
            numeric_keys += 1
        if isinstance(node, dict) and "class_type" in node and "inputs" in node:
            api_classes.append(str(node.get("class_type") or "unknown"))
    if len(api_classes) >= 2 and numeric_keys >= max(1, len(api_classes) // 2):
        return "comfy_api", api_classes
    for key in ("workflow", "prompt"):
        nested = raw.get(key)
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except json.JSONDecodeError:
                nested = None
        nested_result = _classify_source_workflow(nested) if isinstance(nested, dict) else None
        if nested_result:
            workflow_format, classes = nested_result
            return f"nested_{key}_{workflow_format}", classes
    return None


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _runtime_cache_source_map(cache_root: Path) -> dict[str, dict[str, str]]:
    """Map workflow-cache digest stems to source URLs from web search caches."""
    mapping: dict[str, dict[str, str]] = {}
    for path in sorted(cache_root.glob("*.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("href") or item.get("link") or "")
            raw_url = _github_blob_raw_url(url) or url
            if not raw_url:
                continue
            import hashlib

            digest = hashlib.sha256(raw_url.encode("utf-8")).hexdigest()
            mapping[digest] = {
                "url": url,
                "source_url": url,
                "raw_url": raw_url,
                "title": str(item.get("title") or item.get("name") or Path(url).name),
            }
    return mapping


def promote_runtime_workflow_cache(
    *,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    out: Path,
) -> dict[str, Any]:
    """Write an ingest-compatible scan JSON for cached runtime workflows."""
    workflow_dir = cache_root / "workflows"
    source_map = _runtime_cache_source_map(cache_root)
    results: list[dict[str, Any]] = []
    if workflow_dir.is_dir():
        for path in sorted(workflow_dir.glob("*.json")):
            try:
                raw = _read_json(path)
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "status": "json_parse_error",
                    "filename": path.name,
                    "saved_path": str(path),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue
            classified = _classify_source_workflow(raw)
            if not classified:
                results.append({
                    "status": "json_non_comfy",
                    "filename": path.name,
                    "saved_path": str(path),
                })
                continue
            workflow_format, classes = classified
            source = source_map.get(path.stem, {})
            results.append({
                "status": "comfy_workflow",
                "source_kind": "runtime_web_search_cache",
                "authority_tier": "community",
                "filename": source.get("title") or path.name,
                "url": source.get("source_url"),
                "source_url": source.get("source_url"),
                "raw_url": source.get("raw_url"),
                "saved_path": str(path),
                "workflow_format": workflow_format,
                "node_count": len(classes),
                "node_classes": sorted(set(classes)),
            })
    payload = {
        "summary": {
            "source": "runtime-web-search-cache",
            "workflow_rows": len([r for r in results if r.get("status") == "comfy_workflow"]),
            "result_rows": len(results),
            "cache_root": str(cache_root),
            "generated_at": _utcnow(),
        },
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def merge_scan_jsons(paths: list[Path], out: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        data = _read_json(path)
        scan_results = data.get("results") if isinstance(data, dict) else data
        if isinstance(scan_results, list):
            results.extend(row for row in scan_results if isinstance(row, dict))
        if isinstance(data, dict) and isinstance(data.get("summary"), dict):
            summaries.append({"path": str(path), **data["summary"]})
    payload = {
        "summary": {
            "source": "pipeline-orchestrate",
            "scan_files": [str(path) for path in paths],
            "input_summaries": summaries,
            "result_rows": len(results),
            "workflow_rows": len([
                row for row in results
                if row.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}
            ]),
            "generated_at": _utcnow(),
        },
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _run(cmd: list[str], *, dry_run: bool) -> None:
    print("$ " + " ".join(cmd), flush=True)
    if dry_run:
        return
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-json", action="append", type=Path, default=[], help="Existing scanner JSON to include")
    parser.add_argument("--github-repo", action="append", default=[], help="owner/repo to enumerate before ingest; repeatable")
    parser.add_argument("--discord-scan", action="store_true", help="Run the Banodoco Discord scanner before ingest")
    parser.add_argument("--include-runtime-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--pipeline-dir", type=Path, default=DEFAULT_PIPELINE_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--model", default=None, help="Optional model for LLM summaries")
    parser.add_argument("--upload", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Limit ingest candidates")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--upload-workers", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.pipeline_dir.mkdir(parents=True, exist_ok=True)

    scan_paths: list[Path] = [path.resolve() for path in args.scan_json]
    if args.github_repo:
        github_scan = args.pipeline_dir / "github_scan.json"
        _run([
            sys.executable,
            "scripts/enumerate_github_workflows.py",
            *args.github_repo,
            "--out",
            str(github_scan),
        ], dry_run=args.dry_run)
        scan_paths.append(github_scan)

    if args.discord_scan:
        discord_scan = args.pipeline_dir / "discord_scan.json"
        _run([
            sys.executable,
            "scripts/scan_banodoco_discord_workflows.py",
            "--out",
            str(discord_scan),
            "--save-files",
            str(REPO_ROOT / "external_workflows" / ".shadow" / "source"),
        ], dry_run=args.dry_run)
        scan_paths.append(discord_scan)

    if args.include_runtime_cache:
        runtime_scan = args.pipeline_dir / "runtime_web_search_cache.json"
        if not args.dry_run:
            promote_runtime_workflow_cache(cache_root=args.cache_root.expanduser(), out=runtime_scan)
        else:
            print(f"$ promote runtime cache {args.cache_root.expanduser()} -> {runtime_scan}", flush=True)
        scan_paths.append(runtime_scan)

    combined_scan = args.pipeline_dir / "combined_scan.json"
    if not args.dry_run:
        merged = merge_scan_jsons(scan_paths, combined_scan)
        if merged["summary"]["workflow_rows"] == 0:
            print("No workflow rows found in scan inputs; stopping before ingest.", file=sys.stderr)
            return 1
    else:
        print(f"$ merge scans -> {combined_scan}", flush=True)

    ingest_cmd = [
        sys.executable,
        "scripts/ingest_external_workflows.py",
        "--scan-json",
        str(combined_scan),
        "--source",
        "pipeline-orchestrate",
        "--discovered-by",
        "scripts/pipeline_orchestrate.py",
        "--manifest",
        str(args.manifest),
        "--out-dir",
        str(args.corpus_dir),
        "--skip-errors",
    ]
    if args.limit is not None:
        ingest_cmd.extend(["--limit", str(args.limit)])
    _run(ingest_cmd, dry_run=args.dry_run)

    enrich_cmd = [
        sys.executable,
        "scripts/enrich_workflow_summaries.py",
        "--manifest",
        str(args.manifest),
        "--corpus-dir",
        str(args.corpus_dir),
        "--workers",
        str(args.workers),
        "--upload-workers",
        str(args.upload_workers),
    ]
    if args.model:
        enrich_cmd.extend(["--model", args.model])
    if args.upload:
        enrich_cmd.append("--upload")
    _run(enrich_cmd, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
