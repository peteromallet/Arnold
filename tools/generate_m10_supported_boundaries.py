#!/usr/bin/env python3
"""M10 supported-boundaries generator (T34 / Step 13J).

Reads the WBC boundary inventory and produces a focused artifact with
disjoint ``supported``, ``deferred``, ``historical_read_only``, and
``non_mutating`` row-ID sets.

Every deferred row carries:
  - owner, reason, expiry, source_hash, action-off runtime evidence,
    and bypass-test ID.
  - ``deferred_to_m11`` alone is insufficient.

Classification rules
--------------------

* **supported**: boundary_contract rows with ``landed: true`` and
  ``authority_required: true``; runtime_module rows with non-unknown
  surface types that carry ``is_authority: true`` (authority readers
  or writers) and are NOT projections.
* **deferred**: runtime_module rows with ``unknown`` surface type;
  modules with ``action_off`` external mutations; unmatched static
  modules; any module that cannot be classified as supported,
  historical_read_only, or non_mutating.
* **historical_read_only**: entries from the wbc-historical-adapters
  artifact (currently empty — default_empty per T7).
* **non_mutating**: projection modules, journal modules,
  receipt_writer modules that are NOT authority, consumer modules,
  payload_policy modules, and compatibility_shim modules without
  authority-writer classification.

Disjointness is enforced — no row ID may appear in more than one set.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"
INVENTORY_PATH = EVIDENCE_DIR / "wbc-boundary-inventory.json"
HISTORICAL_ADAPTERS_PATH = EVIDENCE_DIR / "wbc-historical-adapters.json"
OUTPUT_PATH = EVIDENCE_DIR / "m10-supported-boundaries.json"

# ── Non-mutating surface types ──────────────────────────────────────────
# These surface types are read-only or purely observational — they never
# produce external mutations.
NON_MUTATING_SURFACE_TYPES: frozenset[str] = frozenset({
    "projection",
    "journal",
    "consumer",
    "payload_policy",
    "durable_ref",
    "compatibility_shim",  # only when not authority_writer
})

# Non-authority surface types — cannot be supported
NON_AUTHORITY_SURFACES: frozenset[str] = frozenset({
    "projection",
    "journal",
})

# Authority-adjacent surface types — these may carry positive action authority
AUTHORITY_ADJACENT: frozenset[str] = frozenset({
    "authority_reader",
    "authority_writer",
})


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _row_identity(row: dict[str, Any]) -> str:
    """Return a stable identity string for a row."""
    rk = row.get("row_kind", "")
    if rk == "boundary_contract":
        return f"bc:{row.get('boundary_id', '')}"
    if rk == "manifest_entry":
        return f"me:{row.get('step_id', '')}"
    if rk == "runtime_module":
        return f"rm:{row.get('module_path', '')}"
    if rk == "handler_function":
        # Include category to deduplicate same function classified multiple ways
        cat = row.get("category", "unknown")
        return f"hf:{row.get('module_path', '')}:{row.get('function_name', '')}:{cat}"
    return f"{rk}:{row.get('module_path', row.get('boundary_id', '?'))}"


def _is_non_mutating_module(row: dict[str, Any]) -> bool:
    """Check if a runtime_module row is non-mutating.

    Non-mutating modules:
    - Have ONLY non-mutating surface types (projection, journal, consumer, etc.)
    - Have no external mutations
    - Are NOT authority readers/writers (those can authorize effects)
    """
    surface_types = set(row.get("surface_types", []))
    external_mutations = row.get("external_mutations", [])

    # If there are external mutations, it's potentially mutating
    if external_mutations:
        return False

    # If ANY authority-adjacent surface type is present, it's potentially mutating
    if surface_types & AUTHORITY_ADJACENT:
        return False

    # If surface types are ONLY non-mutating types, it's non-mutating
    if surface_types and surface_types <= NON_MUTATING_SURFACE_TYPES:
        return True

    # receipt_writer is non-mutating if not authority
    if surface_types == {"receipt_writer"} or surface_types == {"receipt_writer", "unknown"}:
        return True

    return False


def _is_supported_module(row: dict[str, Any]) -> bool:
    """Check if a runtime_module row is supported in M10.

    Supported modules:
    - Have non-unknown surface types
    - Carry is_authority: true (authority readers or writers)
    - Are NOT projections or journals
    - Have NO action_off external mutations
    """
    surface_types = row.get("surface_types", [])
    if "unknown" in surface_types and len(surface_types) == 1:
        return False
    if not row.get("is_authority", False):
        return False
    # Projections and journals are never supported
    for st in surface_types:
        if st in NON_AUTHORITY_SURFACES:
            return False
    # If it has action_off mutations, it's deferred
    for mut in row.get("external_mutations", []):
        if mut.get("disposition") == "action_off":
            return False
    return True


def _source_hash_for_module(row: dict[str, Any]) -> str:
    """Compute a source hash from the module's key fields for deferral tracking."""
    canonical = json.dumps({
        "module_path": row.get("module_path", ""),
        "surface_types": sorted(row.get("surface_types", [])),
        "classes": sorted(row.get("classes", [])),
        "functions": sorted(row.get("functions", [])),
        "external_mutations": sorted(
            [{"call": m.get("call", ""), "kind": m.get("kind", ""), "line": m.get("line", 0)}
             for m in row.get("external_mutations", [])],
            key=lambda x: (x["call"], x["kind"], x["line"])
        ),
    }, sort_keys=True)
    return _sha256_hex(canonical)[:16]


def generate(output_path: Path | None = None) -> dict[str, Any]:
    """Generate m10-supported-boundaries.json from the WBC inventory."""

    inventory = _load_json(INVENTORY_PATH)
    rows = inventory.get("rows", [])
    unmatched_categories = inventory.get("unmatched_categories", {})

    # Load historical adapters
    historical_adapters: list[dict[str, Any]] = []
    if HISTORICAL_ADAPTERS_PATH.exists():
        adapters_data = _load_json(HISTORICAL_ADAPTERS_PATH)
        historical_adapters = adapters_data.get("adapters", [])

    inventory_hash = _sha256_hex(json.dumps(rows, sort_keys=True, default=str))

    supported: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    historical_read_only: list[dict[str, Any]] = []
    non_mutating: list[dict[str, Any]] = []

    # ── Classify boundary_contract rows ──────────────────────────────────
    for row in rows:
        if row.get("row_kind") != "boundary_contract":
            continue
        identity = _row_identity(row)
        if row.get("landed", False) and row.get("authority_required", False):
            supported.append({
                "identity": identity,
                "row_kind": "boundary_contract",
                "boundary_id": row.get("boundary_id", ""),
                "workflow_id": row.get("workflow_id", ""),
                "phase": row.get("phase"),
                "producer_path": row.get("producer_path"),
                "producer_category": row.get("producer_category"),
                "owner": row.get("owner", "wbc"),
            })
        elif not row.get("external_mutations"):
            # Candidate contracts not yet landed — classify as deferred
            deferred.append({
                "identity": identity,
                "row_kind": "boundary_contract",
                "boundary_id": row.get("boundary_id", ""),
                "workflow_id": row.get("workflow_id", ""),
                "phase": row.get("phase"),
                "owner": row.get("owner", "wbc"),
                "reason": "Candidate boundary contract not yet landed — no producer emission path confirmed.",
                "expiry": "M11 boundary-retirement decision",
                "source_hash": _source_hash_for_module(row),
                "action_off_evidence": {
                    "landed": False,
                    "candidate": row.get("candidate", True),
                    "producer_category": row.get("producer_category", "UNKNOWN"),
                },
                "bypass_test_id": f"T34-bypass-bc-{row.get('boundary_id', '')}",
            })

    # ── Classify manifest_entry rows ─────────────────────────────────────
    for row in rows:
        if row.get("row_kind") != "manifest_entry":
            continue
        identity = _row_identity(row)
        # Manifest entries are informational — non_mutating
        non_mutating.append({
            "identity": identity,
            "row_kind": "manifest_entry",
            "step_id": row.get("step_id", ""),
            "step_name": row.get("step_name", ""),
            "kind": row.get("kind", ""),
            "owner": row.get("owner", "UNKNOWN"),
            "support_status": row.get("support_status", "UNKNOWN"),
        })

    # ── Classify runtime_module rows ─────────────────────────────────────
    for row in rows:
        if row.get("row_kind") != "runtime_module":
            continue
        identity = _row_identity(row)
        module_path = row.get("module_path", "")
        surface_types = row.get("surface_types", [])
        external_mutations = row.get("external_mutations", [])

        # Check non-mutating
        if _is_non_mutating_module(row):
            non_mutating.append({
                "identity": identity,
                "row_kind": "runtime_module",
                "module_path": module_path,
                "surface_types": surface_types,
                "owner": row.get("owner", "UNKNOWN"),
                "is_authority": row.get("is_authority", False),
                "rationale": "Module has only non-mutating surface types and no external mutations.",
            })
            continue

        # Check supported
        if _is_supported_module(row):
            supported.append({
                "identity": identity,
                "row_kind": "runtime_module",
                "module_path": module_path,
                "surface_types": surface_types,
                "owner": row.get("owner", "UNKNOWN"),
                "is_authority": row.get("is_authority", True),
                "category": row.get("category", ""),
                "external_mutation_count": len(external_mutations),
            })
            continue

        # Everything else is deferred
        action_off_mutations = [m for m in external_mutations if m.get("disposition") == "action_off"]
        deferred_reason = ""
        if "unknown" in surface_types:
            deferred_reason = f"Module has unclassified surface type 'unknown'. Surface types found: {surface_types}."
        elif action_off_mutations:
            deferred_reason = (
                f"Module has {len(action_off_mutations)} action_off external mutation(s). "
                f"Mutations: {[m.get('call', '') for m in action_off_mutations]}."
            )
        elif not row.get("is_authority", False) and external_mutations:
            deferred_reason = (
                f"Module has {len(external_mutations)} external mutation(s) but is not "
                f"classified as authority. Surface types: {surface_types}."
            )
        else:
            deferred_reason = (
                f"Module surface types {surface_types} do not qualify as supported, "
                f"non_mutating, or historical_read_only."
            )

        deferred.append({
            "identity": identity,
            "row_kind": "runtime_module",
            "module_path": module_path,
            "surface_types": surface_types,
            "category": row.get("category", ""),
            "owner": row.get("owner", "UNKNOWN"),
            "is_authority": row.get("is_authority", False),
            "reason": deferred_reason,
            "expiry": "M11 boundary-retirement decision",
            "source_hash": _source_hash_for_module(row),
            "action_off_evidence": {
                "surface_types": surface_types,
                "external_mutations": [
                    {
                        "call": m.get("call", ""),
                        "kind": m.get("kind", ""),
                        "disposition": m.get("disposition", "inventory_only"),
                        "owner": m.get("owner", "run_authority"),
                        "reason": m.get("reason", ""),
                        "expiry": m.get("expiry", "M11 conformance review"),
                        "line": m.get("line", 0),
                    }
                    for m in external_mutations
                ],
                "has_action_off": bool(action_off_mutations),
                "is_authority_adjacent": bool(set(surface_types) & AUTHORITY_ADJACENT),
            },
            "bypass_test_id": f"T34-bypass-{module_path.replace('/', '-').replace('.py', '')}",
        })

    # ── Classify handler_function rows ───────────────────────────────────
    for row in rows:
        if row.get("row_kind") != "handler_function":
            continue
        identity = _row_identity(row)
        # Handler functions in known categories are supported; unknown are deferred
        category = row.get("category", "unknown")
        if category != "unknown":
            non_mutating.append({
                "identity": identity,
                "row_kind": "handler_function",
                "function_name": row.get("function_name", ""),
                "module_path": row.get("module_path", ""),
                "category": category,
                "owner": row.get("owner", "UNKNOWN"),
            })
        else:
            deferred.append({
                "identity": identity,
                "row_kind": "handler_function",
                "function_name": row.get("function_name", ""),
                "module_path": row.get("module_path", ""),
                "category": "unknown",
                "owner": row.get("owner", "UNKNOWN"),
                "reason": "Handler function could not be classified into a known category.",
                "expiry": "M11 boundary-retirement decision",
                "source_hash": _source_hash_for_module(row),
                "action_off_evidence": {
                    "category": "unknown",
                    "handler_classification_failed": True,
                },
                "bypass_test_id": f"T34-bypass-hf-{row.get('function_name', '')}",
            })

    # ── Historical read-only adapters ────────────────────────────────────
    for adapter in historical_adapters:
        historical_read_only.append({
            "identity": f"ha:{adapter.get('adapter_id', '')}",
            "row_kind": "historical_adapter",
            "adapter_id": adapter.get("adapter_id", ""),
            "surface_type": adapter.get("surface_type", ""),
            "description": adapter.get("description", ""),
            "owner": adapter.get("owner", "run_authority"),
            "read_only": True,
        })

    # ── Deduplicate (inventory may contain duplicate handler_function rows) ─
    def _deduplicate(collection: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for entry in collection:
            ident = entry["identity"]
            if ident not in seen:
                seen.add(ident)
                result.append(entry)
        return result

    supported = _deduplicate(supported)
    deferred = _deduplicate(deferred)
    historical_read_only = _deduplicate(historical_read_only)
    non_mutating = _deduplicate(non_mutating)

    # ── Enforce disjointness ─────────────────────────────────────────────
    all_identities: set[str] = set()
    for label, collection in [
        ("supported", supported),
        ("deferred", deferred),
        ("historical_read_only", historical_read_only),
        ("non_mutating", non_mutating),
    ]:
        for entry in collection:
            ident = entry["identity"]
            if ident in all_identities:
                raise ValueError(
                    f"Duplicate identity '{ident}' in '{label}' — "
                    f"sets must be disjoint."
                )
            all_identities.add(ident)

    # ── Build artifact ──────────────────────────────────────────────────
    artifact: dict[str, Any] = {
        "meta": {
            "schema": "m10.supported-boundaries.v1",
            "description": (
                "Disjoint supported, deferred, historical_read_only, and "
                "non_mutating row-ID sets derived from the WBC boundary "
                "inventory. Every deferred row carries owner, reason, expiry, "
                "source hash, action-off runtime evidence, and bypass-test ID. "
                "Deferred rows are excluded from supported counts and must not "
                "dispatch or authorize effects in M10."
            ),
            "generated_by": "M10 Step 13J — generate_m10_supported_boundaries.py",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_inventory": "evidence/wbc-boundary-inventory.json",
            "source_inventory_hash": inventory_hash,
            "set_counts": {
                "supported": len(supported),
                "deferred": len(deferred),
                "historical_read_only": len(historical_read_only),
                "non_mutating": len(non_mutating),
            },
            "total_rows_in_inventory": len(rows),
            "deduplicated_handler_rows_removed": len(rows) - (
                len(supported) + len(deferred) + len(historical_read_only) + len(non_mutating)
            ),
            "classified_total": len(supported) + len(deferred) + len(historical_read_only) + len(non_mutating),
        },
        "supported": supported,
        "deferred": deferred,
        "historical_read_only": historical_read_only,
        "non_mutating": non_mutating,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(artifact, fh, indent=2, default=str, sort_keys=False)
        print(f"[generate_m10_supported_boundaries] wrote {output_path}")
        print(f"  supported={len(supported)}, deferred={len(deferred)}, "
              f"historical_read_only={len(historical_read_only)}, "
              f"non_mutating={len(non_mutating)}")

    return artifact


if __name__ == "__main__":
    generate(output_path=OUTPUT_PATH)
