from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import yaml

CACHE_PATH = Path("~/.cache/vibecomfy/hf_hashes.json").expanduser()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Populate registry model hash pins from Hugging Face metadata.")
    parser.add_argument("registry", type=Path, nargs="?", default=Path("vibecomfy/registry/models.yaml"))
    parser.add_argument("--cache", type=Path, default=CACHE_PATH)
    parser.add_argument("--refresh", action="store_true", help="Ignore cached Hugging Face metadata and refresh entries.")
    parser.add_argument("--write", action="store_true", help="Rewrite the registry with discovered sha256/size pins.")
    args = parser.parse_args(argv)

    payload = yaml.safe_load(args.registry.read_text(encoding="utf-8")) or {}
    models = payload.get("models", payload) if isinstance(payload, dict) else payload
    if not isinstance(models, list):
        raise SystemExit(f"{args.registry}: expected a models list")

    cache = _load_cache(args.cache)
    changed = False
    for model in models:
        if not isinstance(model, dict) or model.get("gated") is True:
            continue
        source = model.get("source")
        if not isinstance(source, dict) or source.get("kind") != "huggingface":
            continue
        repo = source.get("repo")
        revision = source.get("revision")
        if not isinstance(repo, str) or not repo or not isinstance(revision, str) or not revision:
            continue
        files = model.get("files")
        if isinstance(files, list) and files:
            for file in files:
                if not isinstance(file, dict) or file.get("sha256") and file.get("size_bytes") is not None:
                    continue
                filename = file.get("path")
                if not isinstance(filename, str) or not filename:
                    continue
                metadata = _hf_file_metadata(repo, filename, revision, cache=cache, refresh=args.refresh)
                changed |= _apply_file_metadata(file, metadata)
            continue
        filename = source.get("filename")
        if not isinstance(filename, str) or not filename:
            continue
        metadata = _hf_file_metadata(repo, filename, revision, cache=cache, refresh=args.refresh)
        changed |= _apply_file_metadata(model, metadata)

    _write_cache(args.cache, cache)
    if args.write and changed:
        args.registry.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(json.dumps({"registry": str(args.registry), "cache": str(args.cache), "changed": changed}, sort_keys=True))
    return 0


def _load_cache(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def _write_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hf_file_metadata(repo: str, filename: str, revision: str, *, cache: dict[str, dict[str, Any]], refresh: bool) -> dict[str, Any]:
    key = f"{repo}@{revision}:{filename}"
    if not refresh and key in cache:
        return cache[key]
    from huggingface_hub import HfApi

    info = HfApi().model_info(repo, revision=revision, files_metadata=True)
    for sibling in info.siblings:
        if getattr(sibling, "rfilename", None) != filename:
            continue
        lfs = getattr(sibling, "lfs", None)
        sha256 = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
        metadata = {
            "sha256": sha256,
            "size_bytes": getattr(sibling, "size", None),
        }
        cache[key] = {key: value for key, value in metadata.items() if value is not None}
        return cache[key]
    raise FileNotFoundError(f"{repo}@{revision}:{filename}")


def _apply_file_metadata(target: dict[str, Any], metadata: dict[str, Any]) -> bool:
    changed = False
    if metadata.get("sha256") and not target.get("sha256"):
        target["sha256"] = metadata["sha256"]
        changed = True
    if metadata.get("size_bytes") is not None and target.get("size_bytes") is None:
        target["size_bytes"] = metadata["size_bytes"]
        changed = True
    return changed


if __name__ == "__main__":
    raise SystemExit(main())
