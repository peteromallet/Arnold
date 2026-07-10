"""Fetch and cache Hugging Face LFS metadata referenced by ready templates."""
from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = REPO_ROOT / "out" / "cache" / "hf_metadata.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    existing = _load_cache(args.cache)
    urls = sorted(_template_hf_urls())
    results = dict(existing.get("urls") or {})
    for url in urls:
        canonical = canonical_hf_url(url)
        if canonical in results and results[canonical].get("sha256") and results[canonical].get("size_bytes"):
            continue
        results[canonical] = fetch_url_metadata(canonical)
    payload = {"captured_at": datetime.now(timezone.utc).isoformat(), "urls": results}
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.cache} ({len(results)} urls)")
    return 0


def fetch_url_metadata(url: str) -> dict[str, Any]:
    parsed = parse_hf_url(url)
    if parsed is None:
        return {"url": url, "status": "not_huggingface"}
    repo_id, revision, filename = parsed
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        info = api.model_info(repo_id=repo_id, revision=revision)
        path_infos = api.get_paths_info(repo_id=repo_id, paths=[filename], revision=revision, expand=True)
        if path_infos:
            path_info = path_infos[0]
            lfs = getattr(path_info, "lfs", None) or {}
            sha256 = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
            size = getattr(path_info, "size", None) or (lfs.get("size") if isinstance(lfs, dict) else getattr(lfs, "size", None))
            return {
                "url": url,
                "repo_id": repo_id,
                "filename": filename,
                "hf_revision": getattr(info, "sha", None) or revision,
                "sha256": sha256,
                "size_bytes": size,
                "status": "ok" if sha256 and size is not None else "missing_lfs_metadata",
            }
        return {"url": url, "repo_id": repo_id, "filename": filename, "hf_revision": revision, "status": "missing_file"}
    except Exception as exc:
        status = "gated" if "gated" in str(exc).lower() or "401" in str(exc) or "403" in str(exc) else "unavailable"
        return {"url": url, "repo_id": repo_id, "filename": filename, "hf_revision": "gated" if status == "gated" else revision, "status": status, "error": str(exc)}


def parse_hf_url(url: str) -> tuple[str, str, str] | None:
    parsed = urlparse(url)
    if parsed.netloc != "huggingface.co":
        return None
    parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
    if len(parts) < 5 or "resolve" not in parts:
        return None
    resolve_idx = parts.index("resolve")
    repo_id = "/".join(parts[:resolve_idx])
    revision = parts[resolve_idx + 1]
    filename = "/".join(parts[resolve_idx + 2 :])
    if not repo_id or not revision or not filename:
        return None
    return repo_id, revision, filename


def canonical_hf_url(url: str) -> str:
    parsed = parse_hf_url(url)
    if parsed is None:
        return url
    repo_id, revision, filename = parsed
    return f"https://huggingface.co/{repo_id}/resolve/{revision}/{filename}"


def _template_hf_urls() -> set[str]:
    urls: set[str] = set()
    for path in (REPO_ROOT / "ready_templates").glob("**/*.py"):
        text = path.read_text(encoding="utf-8")
        urls.update(re.findall(r"https://huggingface\\.co/[^'\"\\s)]+", text))
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "url" and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                if "huggingface.co" in node.value.value:
                    urls.add(node.value.value)
    return urls


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
