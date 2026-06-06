from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from arnold.pipeline import load_pipeline_id_registry


def _load_registry_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"pipeline registry at {path!s} must be a JSON object")
    return data


def _pipeline_aliases(item: dict[str, Any]) -> set[str]:
    aliases = set()
    for value in item.get("previous_stable_ids", []):
        if isinstance(value, str) and value:
            aliases.add(value)
    return aliases


def find_pipeline_id_renames(
    base_registry_path: str | Path,
    current_registry_path: str | Path,
) -> list[str]:
    base_registry = load_pipeline_id_registry(base_registry_path)
    current_registry = load_pipeline_id_registry(current_registry_path)
    current_data = _load_registry_json(current_registry_path)

    current_pipelines = {
        str(item.get("name")): dict(item)
        for item in current_data.get("pipelines", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    current_ids = {
        item["stable_id"]
        for item in current_registry.pipelines
        if isinstance(item.get("stable_id"), str) and item["stable_id"]
    }
    aliased_ids = set()
    for item in current_pipelines.values():
        aliased_ids.update(_pipeline_aliases(item))

    errors: list[str] = []
    for name, base_item in base_registry.by_name.items():
        base_stable_id = base_item.get("stable_id")
        if not isinstance(base_stable_id, str) or not base_stable_id:
            continue
        current_item = current_pipelines.get(name)
        if current_item is not None:
            current_stable_id = current_item.get("stable_id")
            if current_stable_id == base_stable_id:
                continue
            if base_stable_id in _pipeline_aliases(current_item):
                continue
            errors.append(
                f"pipeline {name!r} changed stable_id from {base_stable_id!r} to {current_stable_id!r} without previous_stable_ids metadata"
            )
            continue
        if base_stable_id in current_ids or base_stable_id in aliased_ids:
            continue
        errors.append(
            f"stable_id {base_stable_id!r} from pipeline {name!r} disappeared without a migration alias"
        )
    return errors


def _git_show_file(rev: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _write_temp_text(text: str) -> Path:
    import tempfile

    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
    with handle:
        handle.write(text)
    return Path(handle.name)


def _resolve_base_registry_from_git(merge_base_ref: str, registry_path: Path) -> Path:
    merge_base = subprocess.run(
        ["git", "merge-base", "HEAD", merge_base_ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not merge_base:
        raise RuntimeError(f"git merge-base returned no result for {merge_base_ref!r}")
    return _write_temp_text(_git_show_file(merge_base, registry_path.as_posix()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when an existing pipeline stable_id disappears or changes without alias metadata."
    )
    parser.add_argument(
        "--registry",
        default="arnold/pipelines/megaplan/_pipeline/pipeline_ids.json",
        help="Path to the current pipeline_ids.json file.",
    )
    parser.add_argument(
        "--base-registry",
        help="Optional explicit base registry JSON path. When omitted, git merge-base is used.",
    )
    parser.add_argument(
        "--merge-base-ref",
        default="origin/main",
        help="Git ref used to compute merge-base when --base-registry is omitted.",
    )
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    base_registry_path: Path | None = None
    try:
        if args.base_registry:
            base_registry_path = Path(args.base_registry)
        else:
            base_registry_path = _resolve_base_registry_from_git(args.merge_base_ref, registry_path)
        errors = find_pipeline_id_renames(base_registry_path, registry_path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if args.base_registry is None and base_registry_path is not None and base_registry_path.exists():
            base_registry_path.unlink()

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("pipeline ID registry rename check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
