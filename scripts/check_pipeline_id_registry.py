from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from arnold.pipeline import (  # noqa: E402
    load_pipeline_id_registries,
    load_pipeline_id_registry,
)
from arnold.workflow import compile_pipeline  # noqa: E402
from arnold_pipelines.discovery import discover_migrated_pipelines, ShippedPipelineInfo  # noqa: E402

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_registry_files(root: Path | None = None) -> list[Path]:
    """Find all source-controlled ``pipeline_ids.json`` files under *root*.

    Legacy duplicate registries under ``arnold/pipelines/`` that have a
    corresponding registry under ``arnold_pipelines/`` are excluded from the
    default aggregate check because they are scheduled for deletion in M6.
    """
    if root is None:
        root = _repo_root()
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", "**/pipeline_ids.json"],
            check=True,
            capture_output=True,
            text=True,
            cwd=root,
        )
    except subprocess.CalledProcessError:
        return _fallback_glob(root)
    paths: list[Path] = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        paths.append(root / line)

    # Drop legacy duplicates that are shadowed by arnold_pipelines survivors.
    survivors = {
        p.relative_to(root / "arnold_pipelines").as_posix()
        for p in paths
        if _is_under(p, root / "arnold_pipelines")
    }
    filtered: list[Path] = []
    for path in paths:
        if _is_under(path, root / "arnold" / "pipelines"):
            suffix = path.relative_to(root / "arnold" / "pipelines").as_posix()
            if suffix in survivors:
                continue
        filtered.append(path)

    if not filtered:
        return _fallback_glob(root)
    return sorted(filtered)


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return Path.cwd()


def _fallback_glob(root: Path) -> list[Path]:
    """Fallback: glob for ``**/pipeline_ids.json`` under root."""
    return sorted(root.glob("**/pipeline_ids.json"))


# ---------------------------------------------------------------------------
# JSON load helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Per-file rename-drift check
# ---------------------------------------------------------------------------


def find_pipeline_id_renames(
    base_registry_path: str | Path,
    current_registry_path: str | Path,
) -> list[str]:
    """Compare a base registry against a current one and flag drift."""
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
                f"pipeline {name!r} changed stable_id from {base_stable_id!r} "
                f"to {current_stable_id!r} without previous_stable_ids metadata"
            )
            continue
        if base_stable_id in current_ids or base_stable_id in aliased_ids:
            continue
        errors.append(
            f"stable_id {base_stable_id!r} from pipeline {name!r} "
            f"disappeared without a migration alias"
        )
    return errors


# ---------------------------------------------------------------------------
# Aggregate uniqueness check
# ---------------------------------------------------------------------------


def check_aggregate_uniqueness(paths: list[Path]) -> list[str]:
    """Run aggregate uniqueness validation across all registry files."""
    errors: list[str] = []
    if not paths:
        return errors
    try:
        load_pipeline_id_registries(paths)
    except Exception as exc:
        errors.append(f"aggregate uniqueness check failed: {exc}")
    return errors


# ---------------------------------------------------------------------------
# Hash and survivor-ref validation
# ---------------------------------------------------------------------------


_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DEFAULT_IDENTITY_REPORT = REPO_ROOT / "docs" / "arnold" / "manifest-identity-report.json"


def _survivor_registry_ids() -> frozenset[str]:
    """Derive survivor IDs from the shipped-pipeline discovery helper."""
    return frozenset(
        info.registry_id
        for info in discover_migrated_pipelines()
        if info.registry_id is not None
    )


def _compile_workflow_manifest(info: ShippedPipelineInfo) -> Any | None:
    """Compile *info* if it exposes a workflow DSL builder; otherwise skip."""
    if info.builder is None:
        return None
    built = info.builder()
    # Import at call time so module reloads in long-lived test processes do
    # not leave a stale class reference cached at script load time.
    from arnold.workflow.dsl import Pipeline as WorkflowPipeline

    if not isinstance(built, WorkflowPipeline):
        return None
    return compile_pipeline(built)


def _expected_manifest_hashes() -> dict[str, str]:
    """Compute expected manifest hashes from compiled workflow builders."""
    expected: dict[str, str] = {}
    for info in discover_migrated_pipelines():
        if info.registry_id is None:
            continue
        manifest = _compile_workflow_manifest(info)
        if manifest is None:
            continue
        expected[info.registry_id] = manifest.manifest_hash or ""
    return expected


def _load_registry_data(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_registry_hashes(paths: list[Path]) -> list[str]:
    """Validate manifest_hash format and value for every survivor registry entry."""
    errors: list[str] = []
    expected = _expected_manifest_hashes()
    for path in paths:
        data = _load_registry_data(path)
        pipelines = data.get("pipelines") or []
        for index, item in enumerate(pipelines, start=1):
            if not isinstance(item, dict):
                continue
            stable_id = item.get("stable_id")
            if not isinstance(stable_id, str) or not stable_id:
                errors.append(f"[{path}] row {index}: missing stable_id")
                continue
            manifest_hash = item.get("manifest_hash")
            if manifest_hash is None:
                errors.append(
                    f"[{path}] {stable_id!r}: missing manifest_hash after Phase 4"
                )
                continue
            if not isinstance(manifest_hash, str) or not _HASH_RE.match(manifest_hash):
                errors.append(
                    f"[{path}] {stable_id!r}: invalid manifest_hash {manifest_hash!r}"
                )
                continue
            if stable_id in expected and manifest_hash != expected[stable_id]:
                errors.append(
                    f"[{path}] {stable_id!r}: manifest_hash mismatch "
                    f"(registry={manifest_hash!r}, computed={expected[stable_id]!r})"
                )
    return errors


def check_survivor_only_refs(paths: list[Path]) -> list[str]:
    """Ensure every active stable_id belongs to the survivor set."""
    survivors = _survivor_registry_ids()
    errors: list[str] = []
    for path in paths:
        data = _load_registry_data(path)
        pipelines = data.get("pipelines") or []
        for item in pipelines:
            if not isinstance(item, dict):
                continue
            stable_id = item.get("stable_id")
            if isinstance(stable_id, str) and stable_id not in survivors:
                errors.append(
                    f"[{path}] stable_id {stable_id!r} is not a survivor registry ID"
                )
    return errors


def check_composed_rule_refs(root: Path | None = None) -> list[str]:
    """Validate composed rule pipeline/pattern refs against survivors only."""
    if root is None:
        root = _repo_root()
    survivors = _survivor_registry_ids()
    errors: list[str] = []
    composed_dir = root / "arnold_pipelines" / "megaplan" / "data" / "_composed"
    if not composed_dir.exists():
        return errors
    for path in sorted(composed_dir.rglob("*")):
        if path.suffix not in {".json", ".yaml", ".yml"}:
            continue
        try:
            if path.suffix == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                import yaml

                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path}: could not parse composed rule: {exc}")
            continue
        refs = _collect_refs(payload)
        for ref in refs:
            if ref not in survivors:
                errors.append(f"{path}: ref {ref!r} is not a survivor registry ID")
    return errors


def _collect_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, sub in value.items():
            if key in {"pipeline", "pattern", "pipeline_id", "stable_id"} and isinstance(sub, str):
                refs.add(sub)
            else:
                refs.update(_collect_refs(sub))
    elif isinstance(value, list):
        for item in value:
            refs.update(_collect_refs(item))
    return refs


# ---------------------------------------------------------------------------
# Manifest identity report
# ---------------------------------------------------------------------------


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _registry_entries_by_stable_id(
    paths: list[Path], root: Path
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = _load_registry_data(path)
        for item in data.get("pipelines") or []:
            if not isinstance(item, dict):
                continue
            stable_id = item.get("stable_id")
            if not isinstance(stable_id, str) or not stable_id:
                continue
            entry = dict(item)
            entry["_registry_path"] = _relative_path(path, root)
            entries[stable_id] = entry
    return entries


def _docs_ref(path_text: str | None, root: Path) -> dict[str, Any] | None:
    if not path_text:
        return None
    path = root / path_text
    return {"path": path_text, "exists": path.exists()}


def _example_docs_ref(pipeline_id: str, root: Path) -> dict[str, Any]:
    slug = pipeline_id.replace("_", "-")
    path = root / "docs" / "arnold" / "examples" / f"{slug}.md"
    return {"path": _relative_path(path, root), "exists": path.exists()}


def build_manifest_identity_report(
    *,
    root: Path | None = None,
    registry_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Derive the generated manifest identity coverage report.

    The report intentionally recomputes manifest hashes from discovered
    ``build_pipeline`` callables instead of storing hand-maintained expected
    values in the checker.
    """

    if root is None:
        root = _repo_root()
    if registry_paths is None:
        registry_paths = discover_registry_files(root)

    registry_entries = _registry_entries_by_stable_id(registry_paths, root)
    identities: list[dict[str, Any]] = []
    for info in discover_migrated_pipelines():
        if info.registry_id is None:
            continue
        manifest = _compile_workflow_manifest(info)
        registry_entry = registry_entries.get(info.registry_id)
        registry_manifest_hash = None
        registry_path = None
        if registry_entry is not None:
            registry_entry = dict(registry_entry)
            registry_path = registry_entry.pop("_registry_path", None)
            registry_manifest_hash = registry_entry.get("manifest_hash")
        identities.append(
            {
                "registry_id": info.registry_id,
                "pipeline_id": info.id,
                "package_path": info.package_path,
                "package_exists": (root / info.package_path).exists(),
                "compiled_manifest_hash": (
                    manifest.manifest_hash or "" if manifest is not None else ""
                ),
                "registry_path": registry_path,
                "registry_manifest_hash": registry_manifest_hash,
                "registry_entry": registry_entry,
                "skill_docs": _docs_ref(info.docs_path, root),
                "example_docs": _example_docs_ref(info.id, root),
                "generated_asset_path": info.generated_asset_path,
                "disposition": info.disposition,
            }
        )

    identities.sort(key=lambda item: (item["registry_id"], item["package_path"]))
    return {
        "version": 1,
        "generated_by": "scripts/check_pipeline_id_registry.py --write-identity-report",
        "source": (
            "Derived from arnold_pipelines.discovery, discovered pipeline_ids.json "
            "files, generated docs/skill paths, and compile_pipeline(builder())."
        ),
        "registry_files": [_relative_path(path, root) for path in sorted(registry_paths)],
        "identity_count": len(identities),
        "identities": identities,
    }


def render_manifest_identity_report(report: dict[str, Any]) -> str:
    """Render a deterministic manifest identity report."""

    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def check_manifest_identity_report(report_path: Path, expected: dict[str, Any]) -> list[str]:
    """Return errors when the generated identity report is missing or stale."""

    expected_text = render_manifest_identity_report(expected)
    try:
        current_text = report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"{report_path}: missing manifest identity report"]
    if current_text != expected_text:
        return [
            f"{report_path}: stale manifest identity report; "
            "run `python scripts/check_pipeline_id_registry.py --write-identity-report`"
        ]
    return []


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


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


def _resolve_base_registry_from_git(
    merge_base_ref: str, registry_path: Path
) -> Path | None:
    """Return a temp-file path for the base version of *registry_path*, or
    ``None`` when the file does not exist at the merge-base commit."""
    try:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", merge_base_ref],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None
    if not merge_base:
        return None
    try:
        text = _git_show_file(merge_base, registry_path.as_posix())
    except subprocess.CalledProcessError:
        return None
    return _write_temp_text(text)


def _relative_to_root(path: Path) -> str:
    """Return *path* relative to the git repo root for git-show compatibility."""
    try:
        root = _repo_root()
        return str(path.relative_to(root))
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover all source-controlled pipeline ID registries, compare "
            "rename drift per file against a git merge-base (or explicit base), "
            "and enforce aggregate uniqueness across the full current set."
        ),
    )
    parser.add_argument(
        "--registry",
        action="append",
        default=None,
        help=(
            "Path to a current pipeline_ids.json file.  May be repeated.  "
            "When omitted, all source-controlled pipeline_ids.json files are "
            "discovered automatically."
        ),
    )
    parser.add_argument(
        "--base-registry",
        help="Optional explicit base registry JSON path (applied to all current files).",
    )
    parser.add_argument(
        "--merge-base-ref",
        default="origin/main",
        help="Git ref used to compute merge-base when --base-registry is omitted.",
    )
    parser.add_argument(
        "--no-drift",
        action="store_true",
        help="Skip per-file rename-drift comparison; run only aggregate uniqueness.",
    )
    parser.add_argument(
        "--identity-report",
        default=str(DEFAULT_IDENTITY_REPORT),
        help="Path to the generated manifest identity coverage report.",
    )
    parser.add_argument(
        "--write-identity-report",
        action="store_true",
        help=(
            "Write the generated manifest identity coverage report derived from "
            "discovery, registry JSON, docs paths, and compiled manifests."
        ),
    )
    parser.add_argument(
        "--check-identity-report",
        action="store_true",
        help="Fail when the generated manifest identity coverage report is stale.",
    )
    args = parser.parse_args(argv)

    # Resolve current registry paths
    if args.registry:
        registry_paths = [Path(p) for p in args.registry]
    else:
        registry_paths = discover_registry_files()

    if not registry_paths:
        print("error: no pipeline ID registry files discovered", file=sys.stderr)
        return 2

    all_errors: list[str] = []

    identity_report = build_manifest_identity_report(registry_paths=registry_paths)
    identity_report_path = Path(args.identity_report)
    if args.write_identity_report:
        identity_report_path.parent.mkdir(parents=True, exist_ok=True)
        identity_report_path.write_text(
            render_manifest_identity_report(identity_report),
            encoding="utf-8",
        )
        print(f"wrote manifest identity report: {identity_report_path}")
    if args.check_identity_report:
        all_errors.extend(check_manifest_identity_report(identity_report_path, identity_report))

    # 1. Per-file rename-drift (when history is available)
    if not args.no_drift:
        for current_path in registry_paths:
            if not current_path.exists():
                all_errors.append(f"missing current registry file: {current_path}")
                continue

            base_path: Path | None = None
            try:
                if args.base_registry:
                    base_path = Path(args.base_registry)
                else:
                    resolved = _resolve_base_registry_from_git(
                        args.merge_base_ref, current_path
                    )
                    base_path = resolved

                if base_path is None or not base_path.exists():
                    # No base available; skip drift check for this file
                    continue

                drift_errors = find_pipeline_id_renames(base_path, current_path)
                for err in drift_errors:
                    all_errors.append(f"[{_relative_to_root(current_path)}] {err}")
            except Exception as exc:
                all_errors.append(
                    f"[{_relative_to_root(current_path)}] drift check error: {exc}"
                )
            finally:
                if (
                    args.base_registry is None
                    and base_path is not None
                    and base_path.exists()
                ):
                    try:
                        base_path.unlink()
                    except OSError:
                        pass

    # 2. Aggregate uniqueness
    uniqueness_errors = check_aggregate_uniqueness(registry_paths)
    for err in uniqueness_errors:
        all_errors.append(f"[aggregate] {err}")

    # 3. Hash format validation (requires manifest_hash once regenerated)
    hash_errors = check_registry_hashes(registry_paths)
    for err in hash_errors:
        all_errors.append(f"[hash] {err}")

    # 4. Survivor-only stable_id references
    survivor_errors = check_survivor_only_refs(registry_paths)
    for err in survivor_errors:
        all_errors.append(f"[survivor] {err}")

    # 5. Composed rule refs
    composed_errors = check_composed_rule_refs()
    for err in composed_errors:
        all_errors.append(f"[composed] {err}")

    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        return 1

    n_files = len(registry_paths)
    print(
        f"pipeline ID registry check passed ({n_files} file{'s' if n_files != 1 else ''})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
