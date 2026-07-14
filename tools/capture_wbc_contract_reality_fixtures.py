#!/usr/bin/env python3
"""Capture WBC contract reality fixtures from source plan/run directories.

Reads source plan/run directories and writes checked-in compact bundles ONLY under
``tests/fixtures/workflow_boundary_contracts/``.

Redacts:
* macOS/legacy user paths (``/Users/...``, ``/home/...``)
* Prose bodies (critique text, revised drafts, markdown bodies) while preserving
  schema-significant structure (IDs, hashes, boundary_ids, event kinds, sequences,
  receipt shapes, state keys).

Bundles current sprint artifacts:
* state/history, ``phase_result.json``, step and boundary receipts,
  ``events.ndjson``, ``routing_ledger.jsonl``, ``execution.json``,
  gate/finalize/review artifacts, completion verdict, watchdog outcomes,
  and typed ``unknown`` markers for unavailable standalone categories.

Usage::

    python tools/capture_wbc_contract_reality_fixtures.py [--dry-run]

Design constraints (C1 observe-only):
* NEVER writes outside ``tests/fixtures/workflow_boundary_contracts/``.
* NEVER mutates source directories.
* Always uses deterministic ordering (sorted keys).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_ROOT = Path("tests/fixtures/workflow_boundary_contracts")

# Source directories scanned for artifacts
_SOURCE_ROOTS: list[Path] = [
    Path(".megaplan/runs"),
    Path("docs/arnold/megaplan-native-representation-boundary-fixtures"),
]

# Artifacts we try to capture (relative to a run/plan directory)
_ARTIFACT_GLOBS: list[str] = [
    "state.json",
    "phase_result.json",
    "events.ndjson",
    "*.jsonl",          # routing_ledger.jsonl, events.jsonl
    "execution.json",
    "boundary_receipts/*.json",
]

# Legacy paths to redact
_LEGACY_PATH_RE = re.compile(
    r"(?:/Users/|/home/)[^\s\"',;)\]}>]*",
    re.IGNORECASE,
)

# Prose body patterns to redact (replace bodies with <REDACTED>)
_PROSE_FIELD_NAMES: set[str] = {
    "current_draft",
    "original_draft",
    "revised",
    "critique",
    "critiques",
    "report",
    "final_report",
    "brief",
    "research",
    "prompt",
    "text",
    "body",
    "content",
    "description",
    "notes",
    "summary",
}

# Schema-significant keys we always preserve (even inside prose-like objects)
_PRESERVED_KEYS: set[str] = {
    "schema_version",
    "schema",
    "boundary_id",
    "boundary_ids",
    "workflow_id",
    "run_id",
    "artifact_root",
    "artifact_refs",
    "history_ref",
    "invocation_id",
    "phase_result_ref",
    "receipt_version",
    "row_id",
    "state_observation",
    "outcome",
    "phase",
    "phase_result_contract_version",
    "exit_kind",
    "external_error",
    "blocked_tasks",
    "deviations",
    "cli_provenance",
    "artifacts_written",
    "manifest_hash",
    "_pipeline_manifest_hash",
    "_pipeline_name",
    "_runtime_identity_schema_version",
    "runtime_envelope",
    "trust_state",
    "taint",
    "seq",
    "transaction_id",
    "ts_utc",
    "ts_rel_init_s",
    "kind",
    "payload",
    "store_method",
    "phase",
    "effect",
    "effect_class",
    "state",
    "_inputs",
    "_inputs_original",
    "revision_count",
    "current_draft_path",
    "original_path",
    "perspectives",
    "id",
    "name",
    "driver",
    "entrypoint",
    "capabilities",
    "reentry_ids",
    "policy",
    "topology_overlays",
    "overlay_id",
    "overlay_type",
    "source_ref",
    "target_ref",
    "transition_id",
    "transition_type",
    "trigger_ref",
    "payload_schema_hash",
    "resume_schema_hash",
    "idempotency",
    "required",
    "key_template",
}

# Maximum depth for recursion
_MAX_DEPTH = 32

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_prose_field(key: str) -> bool:
    """Return True if *key* looks like a prose body field that should be redacted."""
    if key in _PRESERVED_KEYS:
        return False
    return key in _PROSE_FIELD_NAMES


def _redact_macos_paths(text: str) -> str:
    """Replace macOS/legacy user paths with ``<REDACTED_PATH>``."""
    return _LEGACY_PATH_RE.sub("<REDACTED_PATH>", text)


def _redact_value(value: Any, depth: int = 0) -> Any:
    """Recursively redact prose bodies and legacy paths while preserving structure."""
    if depth > _MAX_DEPTH:
        return value

    if isinstance(value, str):
        # Redact long prose strings but keep short identifiers
        if len(value) > 512:
            return "<REDACTED_PROSE>"
        return _redact_macos_paths(value)

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if _is_prose_field(k) and isinstance(v, str) and len(v) > 256:
                # Preserve the key but redact the prose body
                result[k] = "<REDACTED_PROSE>"
            elif k == "original_path":
                result[k] = _redact_macos_paths(str(v))
            else:
                result[k] = _redact_value(v, depth + 1)
        return result

    if isinstance(value, list):
        return [_redact_value(item, depth + 1) for item in value]

    return value


def _compact_json(data: Any) -> str:
    """Serialize to compact JSON with sorted keys (deterministic)."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    """Load a JSON file, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_ndjson(path: Path) -> list[dict[str, Any]]:
    """Load an NDJSON file as a list of dicts, returning empty list on error."""
    entries: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append(
                    {"_parse_error": True, "_raw": line[:200]}
                )
    except Exception:
        pass
    return entries


def _discover_source_dirs(root: Path) -> list[Path]:
    """Discover run/plan directories under a source root.

    Returns directories that contain at least one recognized artifact.
    """
    dirs: list[Path] = []
    if not root.exists():
        return dirs

    for entry in sorted(root.rglob("*")):
        if not entry.is_dir():
            continue
        # Check if directory has any recognized artifact
        for glob_pat in _ARTIFACT_GLOBS:
            if list(entry.glob(glob_pat)):
                dirs.append(entry)
                break
    return dirs


def _typed_unknown(category: str, reason: str = "source_missing") -> dict[str, str]:
    """Build a typed unknown marker for an unavailable standalone category."""
    return {"category": category, "reason": reason}


def _capture_dir(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Capture a single source directory into a compact bundle.

    Returns a dict suitable for the fixture bundle entries list.
    """
    bundle: dict[str, Any] = {
        "source": str(source_dir),
        "artifacts": {},
        "unknown_markers": [],
    }

    # --- state.json ---
    state_path = source_dir / "state.json"
    if state_path.exists():
        state_data = _load_json(state_path)
        if state_data is not None:
            bundle["artifacts"]["state"] = _redact_value(state_data)
    else:
        bundle["unknown_markers"].append(_typed_unknown("state"))

    # --- phase_result.json ---
    pr_path = source_dir / "phase_result.json"
    if pr_path.exists():
        pr_data = _load_json(pr_path)
        if pr_data is not None:
            bundle["artifacts"]["phase_result"] = _redact_value(pr_data)
    else:
        bundle["unknown_markers"].append(_typed_unknown("phase_result"))

    # --- events.ndjson ---
    events_path = source_dir / "events.ndjson"
    if events_path.exists():
        entries = _load_ndjson(events_path)
        # Trim to max 20 entries, keeping schema-significant fields
        trimmed: list[dict[str, Any]] = []
        for entry in entries[:20]:
            redacted = _redact_value(entry)
            if isinstance(redacted, dict):
                trimmed.append(redacted)
        bundle["artifacts"]["events"] = {
            "total_count": len(entries),
            "captured_count": len(trimmed),
            "entries": trimmed,
        }
    else:
        bundle["unknown_markers"].append(_typed_unknown("events"))

    # --- boundary receipts ---
    receipts_dir = source_dir / "boundary_receipts"
    if receipts_dir.exists() and receipts_dir.is_dir():
        receipts: dict[str, Any] = {}
        for receipt_file in sorted(receipts_dir.glob("*.json")):
            receipt_data = _load_json(receipt_file)
            if receipt_data is not None:
                receipts[receipt_file.name] = _redact_value(receipt_data)
        if receipts:
            bundle["artifacts"]["boundary_receipts"] = receipts
    else:
        bundle["unknown_markers"].append(_typed_unknown("boundary_receipts"))

    # --- routing_ledger.jsonl (specific) ---
    rl_path = source_dir / "routing_ledger.jsonl"
    if rl_path.exists():
        rl_entries = _load_ndjson(rl_path)
        if rl_entries:
            trimmed_rl: list[dict[str, Any]] = []
            for entry in rl_entries[:10]:
                redacted = _redact_value(entry)
                if isinstance(redacted, dict):
                    trimmed_rl.append(redacted)
            bundle["artifacts"]["routing_ledger"] = {
                "total_count": len(rl_entries),
                "captured_count": len(trimmed_rl),
                "entries": trimmed_rl,
            }
    else:
        bundle["unknown_markers"].append(_typed_unknown("routing_ledger"))

    # --- events.jsonl (generic .jsonl fallback) ---
    for jsonl_file in sorted(source_dir.glob("*.jsonl")):
        if jsonl_file.name == "routing_ledger.jsonl":
            continue  # already handled above
        jsonl_entries = _load_ndjson(jsonl_file)
        if jsonl_entries:
            trimmed_jsonl: list[dict[str, Any]] = []
            for entry in jsonl_entries[:10]:
                redacted = _redact_value(entry)
                if isinstance(redacted, dict):
                    trimmed_jsonl.append(redacted)
            bundle["artifacts"][jsonl_file.name] = {
                "total_count": len(jsonl_entries),
                "captured_count": len(trimmed_jsonl),
                "entries": trimmed_jsonl,
            }

    # --- execution.json ---
    exec_path = source_dir / "execution.json"
    if exec_path.exists():
        exec_data = _load_json(exec_path)
        if exec_data is not None:
            bundle["artifacts"]["execution"] = _redact_value(exec_data)
    else:
        bundle["unknown_markers"].append(_typed_unknown("execution"))

    # --- semantic_health.json ---
    sh_path = source_dir / "semantic_health.json"
    if sh_path.exists():
        sh_data = _load_json(sh_path)
        if sh_data is not None:
            bundle["artifacts"]["semantic_health"] = _redact_value(sh_data)

    # --- manifest.json ---
    manifest_path = source_dir / "manifest.json"
    if manifest_path.exists():
        manifest_data = _load_json(manifest_path)
        if manifest_data is not None:
            bundle["artifacts"]["manifest"] = _redact_value(manifest_data)

    # --- gate / finalize / review artifacts ---
    gate_files: dict[str, Any] = {}
    for gate_pat in ["gate_*.json", "finalize_*.json", "review_*.json"]:
        for gate_file in sorted(source_dir.glob(gate_pat)):
            gate_data = _load_json(gate_file)
            if gate_data is not None:
                gate_files[gate_file.name] = _redact_value(gate_data)
    if gate_files:
        bundle["artifacts"]["gate_review_artifacts"] = gate_files
    else:
        bundle["unknown_markers"].append(_typed_unknown("gate_review_artifacts"))

    # --- completion verdict ---
    comp_captured = False
    for comp_file in sorted(source_dir.glob("completion*.json")):
        comp_data = _load_json(comp_file)
        if comp_data is not None:
            bundle["artifacts"]["completion"] = _redact_value(comp_data)
            comp_captured = True
    if not comp_captured:
        bundle["unknown_markers"].append(_typed_unknown("completion"))

    # --- watchdog outcomes ---
    wd_captured = False
    for wd_file in sorted(source_dir.glob("watchdog*.json")):
        wd_data = _load_json(wd_file)
        if wd_data is not None:
            bundle["artifacts"]["watchdog"] = _redact_value(wd_data)
            wd_captured = True
    if not wd_captured:
        bundle["unknown_markers"].append(_typed_unknown("watchdog"))

    # --- verdict artifacts (standalone) ---
    verdict_captured = False
    for verdict_file in sorted(source_dir.glob("verdict*.json")):
        verdict_data = _load_json(verdict_file)
        if verdict_data is not None:
            bundle["artifacts"]["verdict"] = _redact_value(verdict_data)
            verdict_captured = True
    if not verdict_captured:
        bundle["unknown_markers"].append(_typed_unknown("verdict"))

    # If no useful artifacts were captured, mark as empty
    if not bundle["artifacts"]:
        bundle["status"] = "empty"

    return bundle


def _build_bundle_index(bundles: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    """Build the top-level index for all captured bundles."""
    return {
        "schema_version": "arnold.workflow.boundary_contracts.captured_fixtures.v1",
        "description": (
            "Captured fixture bundles from source plan/run directories. "
            "Prose bodies and legacy paths have been redacted. "
            "Schema-significant structure is preserved for replay compatibility."
        ),
        "captured_at": None,  # filled by caller
        "output_root": str(output_dir),
        "total_bundles": len(bundles),
        "bundles": bundles,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def capture(
    source_roots: list[Path] | None = None,
    output_root: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the full capture pipeline.

    Args:
        source_roots: Directories to scan for plan/run data.
        output_root: Where to write fixture bundles (default: ``_FIXTURE_ROOT``).
        dry_run: If True, return the data dict without writing files.

    Returns:
        The top-level index dict that would be (or was) written.
    """
    if source_roots is None:
        source_roots = _SOURCE_ROOTS
    if output_root is None:
        output_root = _FIXTURE_ROOT

    # --- Discover source directories ---
    all_source_dirs: list[Path] = []
    for root in source_roots:
        all_source_dirs.extend(_discover_source_dirs(root))

    # Deduplicate and sort
    all_source_dirs = sorted(set(all_source_dirs))

    # --- Capture each directory ---
    bundles: list[dict[str, Any]] = []
    for source_dir in all_source_dirs:
        bundle = _capture_dir(source_dir, output_root)
        if bundle["artifacts"]:
            bundles.append(bundle)

    # --- Build index ---
    index = _build_bundle_index(bundles, output_root)

    # --- Write (or dry-run) ---
    if not dry_run:
        output_root.mkdir(parents=True, exist_ok=True)

        # Write individual bundles
        for i, bundle in enumerate(bundles):
            source_name = Path(bundle["source"]).name
            bundle_file = output_root / f"captured_bundle_{i:03d}_{source_name}.json"
            bundle_file.write_text(_compact_json(bundle), encoding="utf-8")

        # Write index
        index_path = output_root / "captured_bundles_index.json"
        index_path.write_text(_compact_json(index), encoding="utf-8")

    return index


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Capture WBC contract reality fixtures for C1 reconciliation."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing files.",
    )
    parser.add_argument(
        "--source-root",
        action="append",
        dest="source_roots",
        default=None,
        help="Additional source root to scan (can be repeated).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory for fixtures (default: tests/fixtures/workflow_boundary_contracts/).",
    )
    args = parser.parse_args(argv)

    source_roots = _SOURCE_ROOTS[:]
    if args.source_roots:
        source_roots.extend(Path(p) for p in args.source_roots)

    output_root = Path(args.output) if args.output else _FIXTURE_ROOT

    result = capture(
        source_roots=source_roots,
        output_root=output_root,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        print(f"Captured {result['total_bundles']} bundles to {output_root}")
        for bundle in result["bundles"]:
            source = bundle["source"]
            artifact_count = len(bundle["artifacts"])
            unknown = len(bundle.get("unknown_markers", []))
            print(f"  {source}: {artifact_count} artifacts, {unknown} unknown markers")

    return 0


if __name__ == "__main__":
    sys.exit(main())
