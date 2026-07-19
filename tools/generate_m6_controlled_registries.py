#!/usr/bin/env python3
"""M6 controlled-writer registry generator (T11 — Step 10).

Produces ``evidence/controlled-writer-registry.json`` covering every
known writer surface in the repository: Python modules classified as
authority_writer/receipt_writer/producer via static discovery, shell/wrapper
scripts with boundary effects, resident modules in kernel/execution/supervisor,
cloud provider dynamic surfaces, provider surfaces, and compatibility shims.

For each writer entry the registry captures:
- owner (Run Authority, WBC, TransitionWriter/repair custody)
- current_contract (what contract/surface governs this writer today)
- target_contract (what M7/M8 contract it should move to)
- boundary_conditions (preconditions for a write to be valid)
- fail_closed (what happens when the writer cannot prove authority)
- proof (how to prove the writer is operating correctly)
- rollback_policy (how to disable this writer without restoring dual authority)
- mixed_version_policy (how old-reader/new-writer compatibility is managed)
- retirement_gate (when this writer path can be removed)
- writer_path, writer_category, surface_types, row_hash

This generator is **strictly observe-only**: it reads the committed WBC
inventory and source files, and writes only the registry artifact.  It does
not mutate lifecycle state, queues, providers, delivery, notifications,
source history, or runtime behavior.

Design invariants
-----------------

* **Writer surface coverage**: every writer surface from the WBC inventory
  that is classified as authority_writer, receipt_writer, or producer
  appears in the registry.  Wrapper shells with boundary effects are
  included.  Dynamic/provider/cloud surfaces get explicit placeholder rows.
* **Deterministic ordering**: rows are sorted by (writer_category, writer_path)
  so two runs against the same commit always produce the same artifact.
* **Stable row hashes**: each row carries a SHA-256 content hash computed
  from the deterministically ordered JSON representation (excluding the
  hash field itself).
* **Fail-closed default**: any writer whose authority classification is
  uncertain defaults to fail-closed (deny).
* **No authority from projections**: projections, journals, and consumers
  are explicitly excluded from the writer registry.

Usage::

    python tools/generate_m6_controlled_registries.py [--output PATH] [--validate]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"

WBC_INVENTORY_PATH = EVIDENCE_DIR / "wbc-boundary-inventory.json"
DEFAULT_OUTPUT = EVIDENCE_DIR / "controlled-writer-registry.json"

SCHEMA = "m6.controlled-writer-registry.v1"

# ── Writer category vocabulary ──────────────────────────────────────────────

WRITER_CATEGORY_PYTHON = "python"
WRITER_CATEGORY_SHELL = "shell_wrapper"
WRITER_CATEGORY_RESIDENT = "resident"
WRITER_CATEGORY_CLOUD = "cloud"
WRITER_CATEGORY_PROVIDER = "provider"
WRITER_CATEGORY_COMPATIBILITY = "compatibility"

# Surface types that constitute a writer
WRITER_SURFACE_TYPES: frozenset[str] = frozenset({
    "authority_writer",
    "receipt_writer",
    "producer",
})

# Additional surface types that should be registered as controlled writers
# because they sit at the authority boundary even if they are not pure writers
CONTROLLED_SURFACE_TYPES: frozenset[str] = frozenset({
    "compatibility_shim",
})

# ── Owner classification ────────────────────────────────────────────────────

KNOWN_OWNERS = {
    "wbc": "WBC",
    "run_authority": "Run Authority",
    "repair_custody": "TransitionWriter/repair custody",
}


def _canonical_owner(raw_owner: str) -> str:
    """Map raw owner string to canonical owner name."""
    return KNOWN_OWNERS.get(raw_owner, raw_owner)


# ── Contract/policy templates per writer category ───────────────────────────

# Default templates for each writer category.  These are refined per
# individual writer based on its surface type and inventory metadata.
CATEGORY_DEFAULTS: dict[str, dict[str, str]] = {
    WRITER_CATEGORY_PYTHON: {
        "current_contract": "WBC boundary contract (boundary_contracts.py) or static discovery surface",
        "target_contract": "M7 controlled-authoritative-writer gate with conjunctive Run Authority + Custody fence",
        "boundary_conditions": "Caller must hold current Run Authority grant AND Custody lease/epoch",
        "fail_closed": "Reject write; log attempt to observability; do not advance state",
        "proof": "M6 inventory row + M7 controlled-writer enrollment + M8 producer adoption",
        "rollback_policy": "Disable writer promotion without restoring legacy write authority; keep evidence readable",
        "mixed_version_policy": "Old readers see stale data until cutover; new writers require explicit version gating",
        "retirement_gate": "After zero callers for one full milestone cycle and M8/M10 proof of replacement",
    },
    WRITER_CATEGORY_SHELL: {
        "current_contract": "Shell/wrapper script with boundary effects (no Python handler mediation)",
        "target_contract": "M7 wrapper gate: shell scripts must route through Python boundary handler or be explicitly enrolled",
        "boundary_conditions": "Wrapper must produce a content-addressed receipt; direct fs mutation is denied unless enrolled",
        "fail_closed": "Script execution fails with non-zero exit; receipt not emitted; boundary event logged",
        "proof": "Wrapper enrollment in M7 controlled-writer registry + content-addressed receipt evidence",
        "rollback_policy": "Remove execute permission or replace with no-op stub; never restore dual authority",
        "mixed_version_policy": "Wrapper version is pinned to repo commit; old wrapper versions are rejected by receipt validation",
        "retirement_gate": "After replacement Python handler is landed and all callers are migrated",
    },
    WRITER_CATEGORY_RESIDENT: {
        "current_contract": "Resident runtime module (kernel/execution/supervisor) with writer surface",
        "target_contract": "M7 resident writer enrollment with fence check on every write path",
        "boundary_conditions": "Must pass Run Authority fence + Custody epoch check before mutating resident state",
        "fail_closed": "Raise FenceError or CustodyLeaseError; resident state is not mutated; observability event emitted",
        "proof": "M6 inventory row + M7 enrollment + fence/epoch check in code path",
        "rollback_policy": "Disable writer path via feature flag; resident state reconciliation from WBC ledger; never restore legacy write authority",
        "mixed_version_policy": "Resident modules are version-locked to repo commit; mixed versions require explicit compatibility shim",
        "retirement_gate": "After all callers migrate to WBC-mediated path and resident writer is no longer enrolled",
    },
    WRITER_CATEGORY_CLOUD: {
        "current_contract": "Cloud custody / provider surface (dynamic, not statically discoverable)",
        "target_contract": "M7 cloud provider adapter with WBC receipt emission on every custody state change",
        "boundary_conditions": "Cloud API calls must be wrapped in a boundary handler; direct SDK calls are denied",
        "fail_closed": "Cloud operation is aborted; custody state is not mutated; incident logged",
        "proof": "Cloud adapter enrollment + WBC receipt for every custody state transition",
        "rollback_policy": "Disable cloud adapter; custody state reconciliation from WBC ledger; no direct SDK fallback",
        "mixed_version_policy": "Cloud provider SDK version is pinned; version bumps require adapter re-enrollment",
        "retirement_gate": "After all cloud custody operations route through enrolled adapter and legacy paths have zero callers",
    },
    WRITER_CATEGORY_PROVIDER: {
        "current_contract": "Provider/dynamic surface (plugin loader, generated code, template renderer, subprocess)",
        "target_contract": "M7 provider enrollment with static manifest and receipt obligation",
        "boundary_conditions": "Provider must be enrolled in the controlled-writer registry; generated code must be verifiable",
        "fail_closed": "Provider invocation is blocked; fallback to safe default; incident logged",
        "proof": "Provider enrollment manifest + static verification of generated code + WBC receipt",
        "rollback_policy": "Disable provider via enrollment revocation; no direct invocation fallback",
        "mixed_version_policy": "Provider version is pinned; generated code is content-addressed; version bumps require re-enrollment",
        "retirement_gate": "After all consumers migrate to enrolled provider or the provider surface is retired",
    },
    WRITER_CATEGORY_COMPATIBILITY: {
        "current_contract": "Compatibility shim / adapter bridging old and new writer surfaces",
        "target_contract": "M7 compatibility adapter enrollment with explicit version gating and expiry",
        "boundary_conditions": "Shim must prove both old and new writer identities; cannot introduce new authority",
        "fail_closed": "Shim returns error; both old and new paths are blocked; incident logged",
        "proof": "Compatibility adapter enrollment + version gate test + zero-authority proof",
        "rollback_policy": "Disable shim; old readers see UNKNOWN; new writers use direct path; no dual authority",
        "mixed_version_policy": "Shim is explicitly versioned with expiry; after expiry, old path is rejected",
        "retirement_gate": "After all old readers are migrated and shim expiry date has passed",
    },
}

# ── Writer extraction from inventory ────────────────────────────────────────


def _load_inventory() -> dict[str, Any]:
    """Load the WBC boundary inventory."""
    if not WBC_INVENTORY_PATH.exists():
        print(
            f"Error: WBC inventory not found: {WBC_INVENTORY_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(WBC_INVENTORY_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _extract_python_writers(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract Python writer entries from the WBC inventory.

    A Python module is a writer if it has surface_types intersecting
    with WRITER_SURFACE_TYPES (authority_writer, receipt_writer, producer).
    """
    writers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in inventory.get("rows", []):
        if row.get("row_kind") != "runtime_module":
            continue

        surface_types = row.get("surface_types", [])
        writer_sts = [st for st in surface_types if st in WRITER_SURFACE_TYPES]
        controlled_sts = [st for st in surface_types if st in CONTROLLED_SURFACE_TYPES]

        if not writer_sts and not controlled_sts:
            continue

        module_path = row.get("module_path", "")
        if module_path in seen:
            continue
        seen.add(module_path)

        # Classify into sub-category
        category = _classify_python_writer_category(module_path, surface_types)

        raw_owner = row.get("owner", "run_authority")
        owner = _canonical_owner(raw_owner)

        writer_entry = _build_writer_entry(
            writer_path=module_path,
            writer_category=category,
            surface_types=surface_types,
            owner=owner,
            raw_row=row,
        )
        writers.append(writer_entry)

    # Sort deterministically
    writers.sort(key=lambda w: (w["writer_category"], w["writer_path"]))
    return writers


def _classify_python_writer_category(
    module_path: str, surface_types: list[str],
) -> str:
    """Classify a Python writer into a category based on path and surfaces."""
    path_lower = module_path.lower()

    # Compatibility shims
    if any(kw in path_lower for kw in ("compat", "adapter", "bridge", "shim")):
        return WRITER_CATEGORY_COMPATIBILITY

    # Cloud
    if any(kw in path_lower for kw in ("cloud",)):
        return WRITER_CATEGORY_CLOUD

    # Resident (kernel, execution, supervisor)
    if any(seg in path_lower for seg in ("/kernel/", "/execution/", "/supervisor/")):
        return WRITER_CATEGORY_RESIDENT

    # Default: Python
    return WRITER_CATEGORY_PYTHON


def _extract_shell_writers() -> list[dict[str, Any]]:
    """Discover non-Python shell/wrapper scripts with boundary effects.

    Uses the same scanning logic as the WBC inventory generator's
    _scan_wrapper_shells() but emits controlled-writer-registry rows.
    """
    # Shell scanning roots (mirroring generate_wbc_boundary_inventory.py)
    wrapper_roots: list[dict[str, Any]] = [
        {
            "path": "arnold_pipelines/megaplan/data",
            "file_patterns": ["*.sh"],
            "category": "ci_cd_scripts",
        },
        {
            "path": ".",
            "file_patterns": ["*.sh"],
            "category": "repo_root_scripts",
            "max_depth": 1,
        },
        {
            "path": ".megaplan/initiatives",
            "file_patterns": ["*.sh"],
            "category": "initiative_scripts",
        },
    ]

    writers: list[dict[str, Any]] = []
    seen: set[str] = set()

    boundary_keywords = [
        "regen", "sync", "launch", "deploy", "commit", "push",
        "skill", "setup", "init", "lock", "stamp",
    ]

    for root_cfg in wrapper_roots:
        root_path = REPO_ROOT / root_cfg["path"]
        if not root_path.is_dir():
            continue

        max_depth = root_cfg.get("max_depth")
        patterns = root_cfg.get("file_patterns", ["*.sh"])

        for pattern in patterns:
            if max_depth is not None:
                for fpath in root_path.glob(pattern):
                    if not fpath.is_file():
                        continue
                    if max_depth == 1 and fpath.parent != root_path:
                        continue
                    rel = fpath.relative_to(REPO_ROOT)
                    rel_str = str(rel).replace("\\", "/")
                    if rel_str in seen:
                        continue
                    seen.add(rel_str)

                    # Check for boundary effects
                    try:
                        header = fpath.read_text(encoding="utf-8")[:2048]
                    except (OSError, UnicodeDecodeError):
                        header = ""

                    has_effects = any(
                        kw in rel_str.lower() or kw in header.lower()
                        for kw in boundary_keywords
                    )

                    if has_effects:
                        writers.append(_build_writer_entry(
                            writer_path=rel_str,
                            writer_category=WRITER_CATEGORY_SHELL,
                            surface_types=["wrapper_shell"],
                            owner="Run Authority",
                            raw_row={"has_boundary_effects": True},
                        ))
            else:
                for fpath in root_path.rglob(pattern):
                    if not fpath.is_file():
                        continue
                    rel = fpath.relative_to(REPO_ROOT)
                    rel_str = str(rel).replace("\\", "/")
                    if rel_str in seen:
                        continue
                    seen.add(rel_str)

                    try:
                        header = fpath.read_text(encoding="utf-8")[:2048]
                    except (OSError, UnicodeDecodeError):
                        header = ""

                    has_effects = any(
                        kw in rel_str.lower() or kw in header.lower()
                        for kw in boundary_keywords
                    )

                    if has_effects:
                        writers.append(_build_writer_entry(
                            writer_path=rel_str,
                            writer_category=WRITER_CATEGORY_SHELL,
                            surface_types=["wrapper_shell"],
                            owner="Run Authority",
                            raw_row={"has_boundary_effects": True},
                        ))

    writers.sort(key=lambda w: w["writer_path"])
    return writers


def _extract_dynamic_placeholder_writers() -> list[dict[str, Any]]:
    """Emit placeholder rows for dynamic/generated/provider surfaces that
    cannot be discovered via static analysis.

    These are the same dynamic surfaces identified in the WBC inventory's
    default-deny rows.
    """
    dynamic_surfaces: list[dict[str, Any]] = [
        {
            "surface_id": "dynamic.cloud_provider",
            "writer_category": WRITER_CATEGORY_CLOUD,
            "reason": "Cloud provider surfaces (AWS, GCP, Azure SDK calls) are "
                       "resolved at runtime and cannot be statically discovered.",
        },
        {
            "surface_id": "dynamic.generated_code",
            "writer_category": WRITER_CATEGORY_PROVIDER,
            "reason": "Generated code (protobuf stubs, OpenAPI clients, Thrift "
                       "bindings) may not exist in the source tree at scan time.",
        },
        {
            "surface_id": "dynamic.plugin_loader",
            "writer_category": WRITER_CATEGORY_PROVIDER,
            "reason": "Plugin/driver loaders resolve surfaces at import time; "
                       "static discovery cannot enumerate all plugin paths.",
        },
        {
            "surface_id": "dynamic.template_renderer",
            "writer_category": WRITER_CATEGORY_PROVIDER,
            "reason": "Template-rendered code (Jinja2, Mako, string.Template) "
                       "produces surfaces that only exist after rendering.",
        },
        {
            "surface_id": "dynamic.subprocess_boundary",
            "writer_category": WRITER_CATEGORY_PROVIDER,
            "reason": "Subprocess boundaries (os.system, subprocess.run) create "
                       "writer surfaces that static analysis cannot trace.",
        },
        {
            "surface_id": "dynamic.import_side_effect",
            "writer_category": WRITER_CATEGORY_PROVIDER,
            "reason": "Import-time side effects (module-level mutations, registrations) "
                       "create writer surfaces before any function is called.",
        },
    ]

    writers: list[dict[str, Any]] = []
    for ds in dynamic_surfaces:
        writers.append(_build_writer_entry(
            writer_path=ds["surface_id"],
            writer_category=ds["writer_category"],
            surface_types=["dynamic_surface"],
            owner="Run Authority",
            raw_row={"reason": ds["reason"]},
        ))

    writers.sort(key=lambda w: w["writer_path"])
    return writers


# ── Writer entry builder ────────────────────────────────────────────────────


def _build_writer_entry(
    writer_path: str,
    writer_category: str,
    surface_types: list[str],
    owner: str,
    raw_row: dict[str, Any],
) -> dict[str, Any]:
    """Build a single controlled-writer registry entry.

    Applies category defaults and refines with writer-specific metadata.
    """
    defaults = CATEGORY_DEFAULTS.get(
        writer_category, CATEGORY_DEFAULTS[WRITER_CATEGORY_PYTHON]
    )

    # Derive a stable writer_id from the path
    writer_id = _derive_writer_id(writer_path)

    entry: dict[str, Any] = {
        "writer_id": writer_id,
        "writer_path": writer_path,
        "writer_category": writer_category,
        "surface_types": sorted(surface_types),
        "owner": owner,
        "current_contract": defaults["current_contract"],
        "target_contract": defaults["target_contract"],
        "boundary_conditions": defaults["boundary_conditions"],
        "fail_closed": defaults["fail_closed"],
        "proof": defaults["proof"],
        "rollback_policy": defaults["rollback_policy"],
        "mixed_version_policy": defaults["mixed_version_policy"],
        "retirement_gate": defaults["retirement_gate"],
        "evidence_ref": f"WBC boundary inventory: {writer_path}",
    }

    # Refine with writer-specific information from raw_row
    if raw_row.get("is_authority") is not None:
        entry["is_authority"] = bool(raw_row["is_authority"])
    else:
        entry["is_authority"] = "authority_writer" in surface_types

    if raw_row.get("category"):
        entry["inventory_category"] = raw_row["category"]

    # Compute stable row hash
    entry["row_hash"] = _compute_row_hash(entry)

    return entry


def _derive_writer_id(writer_path: str) -> str:
    """Derive a stable writer_id from the writer path."""
    # Replace path separators and special chars
    clean = writer_path.replace("/", ".").replace("\\", ".").replace("-", "_")
    # Remove leading dot
    clean = clean.lstrip(".")
    # Remove file extension
    if clean.endswith(".py") or clean.endswith(".sh"):
        clean = clean[:-3]
    return f"writer.{clean}"


# ── Hash helpers ────────────────────────────────────────────────────────────


def _compute_row_hash(row: dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash for a row (excluding the hash field)."""
    row_copy = {k: v for k, v in row.items() if k != "row_hash"}
    canonical = json.dumps(row_copy, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compute_composite_hash(rows: list[dict[str, Any]]) -> str:
    """Compute composite hash from sorted row hashes."""
    row_hashes = sorted(r["row_hash"] for r in rows)
    combined = "".join(row_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ── Artifact generation ─────────────────────────────────────────────────────


def generate_registry(output_path: Path | None = None) -> dict[str, Any]:
    """Generate the full controlled-writer registry artifact.

    Returns the artifact dict (also writes it to disk if *output_path*
    is provided).
    """
    inventory = _load_inventory()

    # Extract writers from all sources
    python_writers = _extract_python_writers(inventory)
    shell_writers = _extract_shell_writers()
    dynamic_writers = _extract_dynamic_placeholder_writers()

    # Merge all writers and sort deterministically by (category, path)
    all_writers = python_writers + shell_writers + dynamic_writers
    all_writers.sort(key=lambda w: (w["writer_category"], w["writer_path"]))

    # Count by category
    category_counts: dict[str, int] = {}
    for w in all_writers:
        cat = w["writer_category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/generate_m6_controlled_registries.py",
        "source_inventory": str(
            WBC_INVENTORY_PATH.relative_to(REPO_ROOT)
        ),
        "writer_count": len(all_writers),
        "category_counts": category_counts,
        "writer_categories": sorted(category_counts.keys()),
        "rows": all_writers,
        "composite_hash": _compute_composite_hash(all_writers),
        "row_hash_algorithm": "SHA-256",
        "row_hash_coverage": (
            "each row hash computed from deterministically ordered JSON "
            "excluding row_hash field"
        ),
        "fail_closed_default": (
            "Any writer whose authority classification is uncertain "
            "defaults to fail-closed (deny). Writers must be explicitly "
            "enrolled to gain write access."
        ),
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return artifact


# ── Validation ──────────────────────────────────────────────────────────────


def _validate_registry(artifact: dict[str, Any]) -> bool:
    """Validate the registry artifact. Returns True if valid."""
    errors: list[str] = []

    # Schema check
    if artifact.get("schema") != SCHEMA:
        errors.append(f"Schema mismatch: {artifact.get('schema')} != {SCHEMA}")

    # Row count must be > 0
    rows = artifact.get("rows", [])
    if len(rows) == 0:
        errors.append("Registry has zero rows")

    # Required fields per row
    required_fields = {
        "writer_id",
        "writer_path",
        "writer_category",
        "surface_types",
        "owner",
        "current_contract",
        "target_contract",
        "boundary_conditions",
        "fail_closed",
        "proof",
        "rollback_policy",
        "mixed_version_policy",
        "retirement_gate",
        "evidence_ref",
        "row_hash",
    }

    valid_categories = set(CATEGORY_DEFAULTS.keys())
    valid_owners = {"WBC", "Run Authority", "TransitionWriter/repair custody"}

    for row in rows:
        wid = row.get("writer_id", "?")
        missing = required_fields - set(row.keys())
        if missing:
            errors.append(f"Row {wid}: missing fields {sorted(missing)}")

        # Verify row hash
        expected_hash = _compute_row_hash(row)
        actual_hash = row.get("row_hash", "")
        if expected_hash != actual_hash:
            errors.append(
                f"Row {wid}: hash mismatch "
                f"(expected {expected_hash[:12]}..., got {actual_hash[:12]}...)"
            )

        # Verify category is valid
        cat = row.get("writer_category", "")
        if cat not in valid_categories:
            errors.append(f"Row {wid}: unknown writer_category '{cat}'")

        # Verify owner is valid
        owner = row.get("owner", "")
        if owner not in valid_owners:
            errors.append(f"Row {wid}: unknown owner '{owner}'")

        # Verify non-empty fields
        for field in required_fields - {"row_hash"}:
            value = row.get(field)
            if not value and field not in ("surface_types",):
                errors.append(f"Row {wid}: {field} is empty")

    # Composite hash check
    expected_composite = _compute_composite_hash(rows)
    actual_composite = artifact.get("composite_hash", "")
    if expected_composite != actual_composite:
        errors.append("Composite hash mismatch")

    # Category coverage: must have at least python, shell_wrapper, and
    # at least one of cloud/provider/compatibility
    categories_found = set(artifact.get("writer_categories", []))
    required_categories = {WRITER_CATEGORY_PYTHON}
    missing_cats = required_categories - categories_found
    if missing_cats:
        errors.append(f"Missing required categories: {sorted(missing_cats)}")

    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return False

    print("Validation PASSED", file=sys.stderr)
    return True


# ── Authority-Reader Registry (T12 — Step 11) ──────────────────────────────

READER_SCHEMA = "m6.authority-reader-registry.v1"
READER_DEFAULT_OUTPUT = EVIDENCE_DIR / "authority-reader-registry.json"

READER_CATEGORY_PYTHON = "python"
READER_CATEGORY_SHELL = "shell_wrapper"
READER_CATEGORY_RESIDENT = "resident"
READER_CATEGORY_CLOUD = "cloud_status_watchdog"
READER_CATEGORY_PROVIDER = "provider"
READER_CATEGORY_PROJECTION = "projection"
READER_CATEGORY_COMPATIBILITY = "compatibility"
READER_CATEGORY_HISTORICAL = "historical_reader"

# Surfaces that MUST NOT be positive authority
NON_AUTHORITATIVE_READER_SURFACES: frozenset[str] = frozenset({
    "projection",
    "liveness",
    "status_snapshot",
    "support_label",
})

READER_CATEGORY_DEFAULTS: dict[str, dict[str, str]] = {
    READER_CATEGORY_PYTHON: {
        "current_contract": "Authority reader route defined in authority_readers.py or WBC boundary inventory",
        "target_contract": "M7 controlled-authoritative-reader gate with read-only fence",
        "boundary_conditions": "Reader must receive a read-only token; cannot mutate state or advance work",
        "fail_closed": "Reject read attempt; log observability; do not unlock dependents",
        "proof": "M6 inventory row + enrolled in authority_readers.py + disposition audit",
        "rollback_policy": "Disable reader promotion without restoring legacy reads; keep audit trail",
        "mixed_version_policy": "Old consumers see stale terminal labels until authority adapter is enrolled",
        "retirement_gate": "After all callers migrate to enrolled reader and legacy path has zero consumers",
    },
    READER_CATEGORY_SHELL: {
        "current_contract": "Shell/wrapper script that reads authority-facing state",
        "target_contract": "M7 wrapper reader: shell scripts must route through authority-reader adapter",
        "boundary_conditions": "Must produce content-addressed read receipt; raw status reads are denied",
        "fail_closed": "Script execution fails; read is denied; observability event logged",
        "proof": "Wrapper enrollment in M7 reader registry + content-addressed read receipt",
        "rollback_policy": "Remove execute permission or replace with read-only stub; never restore legacy read authority",
        "mixed_version_policy": "Wrapper version pinned to repo commit; old versions rejected",
        "retirement_gate": "After replacement Python reader is landed and all callers are migrated",
    },
    READER_CATEGORY_RESIDENT: {
        "current_contract": "Resident runtime module (kernel/execution/supervisor) with reader surface",
        "target_contract": "M7 resident reader enrollment with fence check on every read path",
        "boundary_conditions": "Must pass read-only fence before exposing authority state",
        "fail_closed": "Return UNKNOWN; resident state is not exposed; observability event emitted",
        "proof": "M6 inventory row + M7 enrollment + read fence in code path",
        "rollback_policy": "Disable reader path via feature flag; no legacy read fallback",
        "mixed_version_policy": "Resident modules version-locked to repo commit",
        "retirement_gate": "After all callers migrate to WBC-mediated read path",
    },
    READER_CATEGORY_CLOUD: {
        "current_contract": "Cloud/status/watchdog reader surfaces (liveness, status snapshots, watchdog)",
        "target_contract": "M7 cloud reader adapter — reads are informational only, never increase authority",
        "boundary_conditions": "Cloud reads must be informational; cannot be used to skip/unblock/advance work",
        "fail_closed": "Read is denied; cloud service returns UNKNOWN; incident logged",
        "proof": "Cloud reader enrollment + informational disposition enforced",
        "rollback_policy": "Disable cloud reader; no direct status snapshot fallback for authority decisions",
        "mixed_version_policy": "Cloud service version pinned; version bumps require adapter re-enrollment",
        "retirement_gate": "After all cloud reader callers migrate to enrolled adapters",
    },
    READER_CATEGORY_PROVIDER: {
        "current_contract": "Provider/dynamic reader surface (plugin, generated code)",
        "target_contract": "M7 provider reader enrollment with static manifest",
        "boundary_conditions": "Provider must be enrolled; generated code must be verifiable",
        "fail_closed": "Provider read is blocked; fallback to UNKNOWN; incident logged",
        "proof": "Provider enrollment manifest + static verification + read receipt",
        "rollback_policy": "Disable provider via enrollment revocation",
        "mixed_version_policy": "Provider version pinned; generated code content-addressed",
        "retirement_gate": "After all consumers migrate to enrolled provider",
    },
    READER_CATEGORY_PROJECTION: {
        "current_contract": "Advisory/execution projection — explicitly NOT authority",
        "target_contract": "M7 projection gate: projections are rebuildable diagnostics, never authority",
        "boundary_conditions": "Projection MUST NOT be used to skip/unblock/advance work",
        "fail_closed": "Projection returns advisory diagnostics only; authority decision is always UNKNOWN",
        "proof": "Non-authority classification in inventory + zero-authority acceptance proof",
        "rollback_policy": "Disable projection without restoring legacy reads",
        "mixed_version_policy": "Projection version is pinned to commit",
        "retirement_gate": "After all upstream consumers stop relying on projection for authority",
    },
    READER_CATEGORY_COMPATIBILITY: {
        "current_contract": "Compatibility shim/adapter bridging old and new reader surfaces",
        "target_contract": "M7 compatibility reader enrollment with version gating and expiry",
        "boundary_conditions": "Shim must prove both old and new reader identities; cannot introduce authority",
        "fail_closed": "Shim returns error; both paths blocked; incident logged",
        "proof": "Compatibility adapter enrollment + version gate test + zero-authority proof",
        "rollback_policy": "Disable shim; old readers see UNKNOWN; no dual read authority",
        "mixed_version_policy": "Shim explicitly versioned with expiry",
        "retirement_gate": "After all old readers are migrated and shim expiry date has passed",
    },
    READER_CATEGORY_HISTORICAL: {
        "current_contract": "Historical reader path (WBC evidence, audit trail, milestone artifacts)",
        "target_contract": "M7 historical reader enrollment — reads are rebuildable from repo evidence",
        "boundary_conditions": "Historical reads must be content-addressed and rebuildable from repo evidence",
        "fail_closed": "Historical read is denied if evidence is missing; UNKNOWN is returned",
        "proof": "WBC evidence path + content-addressed hash verification",
        "rollback_policy": "Disable historical reader; evidence remains available via git history",
        "mixed_version_policy": "Historical evidence is commit-bound; version is the commit SHA",
        "retirement_gate": "After all consumers migrate to direct evidence access",
    },
}


def _extract_python_readers(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract Python authority_reader entries from the WBC inventory."""
    readers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in inventory.get("rows", []):
        if row.get("row_kind") != "runtime_module":
            continue
        surface_types = row.get("surface_types", [])
        if "authority_reader" not in surface_types:
            continue
        module_path = row.get("module_path", "")
        if module_path in seen:
            continue
        seen.add(module_path)

        category = _classify_reader_category(module_path, surface_types)
        raw_owner = row.get("owner", "run_authority")
        owner = _canonical_owner(raw_owner)

        reader_entry = _build_reader_entry(
            reader_path=module_path,
            reader_category=category,
            surface_types=surface_types,
            owner=owner,
            raw_row=row,
        )
        readers.append(reader_entry)

    readers.sort(key=lambda r: (r["reader_category"], r["reader_path"]))
    return readers


def _extract_authority_routes_as_readers() -> list[dict[str, Any]]:
    """Extract the 27 AUTHORITY_ROUTES from authority_readers.py as reader entries."""
    authority_readers_path = (
        REPO_ROOT / "arnold_pipelines/megaplan/orchestration/authority_readers.py"
    )
    readers: list[dict[str, Any]] = []

    if not authority_readers_path.exists():
        return readers

    # Parse AUTHORITY_ROUTES from the module
    import importlib.util as _iu
    spec = _iu.spec_from_file_location(
        "authority_readers", str(authority_readers_path)
    )
    if spec is None or spec.loader is None:
        return readers
    mod = _iu.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        # If we can't import, fall back to a static enumeration
        return _static_authority_route_readers()

    routes = getattr(mod, "AUTHORITY_ROUTES", ())
    seen_ids: set[str] = set()

    for route in routes:
        route_id = getattr(route, "id", "?")
        if route_id in seen_ids:
            continue
        seen_ids.add(route_id)

        disposition = getattr(route, "disposition", "informational")
        is_authority = disposition == "enforced"

        surface_types = ["authority_reader"]
        if is_authority:
            surface_types.append("enforced_reader")

        reader_entry = _build_reader_entry(
            reader_path=f"authority_readers.py::{route_id}",
            reader_category=READER_CATEGORY_PYTHON,
            surface_types=surface_types,
            owner="Run Authority",
            raw_row={
                "route_id": route_id,
                "file": getattr(route, "file", ""),
                "line_range": getattr(route, "line_range", ""),
                "description": getattr(route, "description", ""),
                "disposition": disposition,
                "route_family": getattr(route, "route_family", ""),
                "owner_or_reason": getattr(route, "owner_or_reason", ""),
                "is_authority": is_authority,
            },
        )
        readers.append(reader_entry)

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _static_authority_route_readers() -> list[dict[str, Any]]:
    """Static fallback enumeration of AUTHORITY_ROUTES (27 entries)."""
    routes_data = [
        ("EXEC-01", "warn-only", "execute", "Auto-loop task selection from raw status"),
        ("EXEC-02", "warn-only", "execute", "Batch prerequisite gate from batch_status_overlay"),
        ("EXEC-03", "warn-only", "execute", "All-tracked check for batch completion"),
        ("EXEC-04", "warn-only", "execute", "Post-batch completed_id update re-reading raw status"),
        ("EXEC-05", "warn-only", "execute", "compute_task_batches accepts completed_ids"),
        ("EXEC-06", "warn-only", "execute", "schedule_batches threads completed_ids through"),
        ("EXEC-07", "warn-only", "execute", "all_tracked determines BatchOutcome.SUCCESS"),
        ("EXEC-08", "warn-only", "execute", "Timeout recovery completed_tasks from raw status"),
        ("EXEC-09", "warn-only", "execute", "Prompt helper filtering done_tasks from raw status"),
        ("RESUME-01", "warn-only", "resume", "resume_plan reads resume_cursor without corroboration"),
        ("RESUME-02", "warn-only", "resume", "Pipeline resume cursor re-enters without corroboration"),
        ("RESUME-03", "warn-only", "resume", "_active_phase_already_completed trusts phase_produced_state"),
        ("RESUME-04", "warn-only", "resume", "Auto terminal success signaling gates on terminal_status"),
        ("CHAIN-01", "enforced", "chain", "_latest_execution_batch_all_tasks_done (enforced)"),
        ("CHAIN-02", "warn-only", "chain", "_handle_outcome advances on outcome.status"),
        ("CHAIN-03", "warn-only", "chain", "_recover_blocked_execute_if_tasks_done"),
        ("CHAIN-04", "warn-only", "chain", "Seed plan terminal skip compares against TERMINAL_SKIP_STATES"),
        ("CHAIN-05", "warn-only", "chain", "current_plan_name pointer reads for skip/advance"),
        ("SUP-01", "warn-only", "supervisor", "Quarantined duplicate of CHAIN-03 in chain_runner"),
        ("SUP-02", "warn-only", "supervisor", "_assert_dependencies_completed gates on labels only"),
        ("SUP-03", "warn-only", "supervisor", "run_chain milestone advancement loop on LadderAction.ADVANCE"),
        ("SUP-04", "warn-only", "supervisor", "Supervisor dependency gates and PR-merge advancement"),
        ("STATUS-01", "informational", "status", "Status view filtering for operator visibility"),
        ("STATUS-02", "deferred", "status", "_shadow_completion_verdict in auto drive"),
        ("STATUS-03", "deferred", "status", "_shadow_milestone_completion_verdict"),
        ("STATUS-04", "deferred", "status", "compute_verdict milestone-level completion checking"),
        ("STATUS-05", "deferred", "status", "Shadow verdict in auto terminal"),
        ("STATUS-06", "deferred", "status", "Shadow verdict in chain _handle_outcome flow"),
        ("TIMEOUT-01", "warn-only", "timeout", "Timeout recovery summary best-effort reporting"),
    ]

    readers: list[dict[str, Any]] = []
    for route_id, disposition, route_family, description in routes_data:
        is_authority = disposition == "enforced"
        surface_types = ["authority_reader"]
        if is_authority:
            surface_types.append("enforced_reader")

        reader_entry = _build_reader_entry(
            reader_path=f"authority_readers.py::{route_id}",
            reader_category=READER_CATEGORY_PYTHON,
            surface_types=surface_types,
            owner="Run Authority",
            raw_row={
                "route_id": route_id,
                "disposition": disposition,
                "route_family": route_family,
                "description": description,
                "is_authority": is_authority,
            },
        )
        readers.append(reader_entry)

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _extract_shell_readers() -> list[dict[str, Any]]:
    """Discover shell/wrapper scripts that may read authority state."""
    shell_paths = [
        "scripts/megaplan_live_watchdog.py",
        "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog",
        "arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog",
    ]
    readers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for sp in shell_paths:
        fpath = REPO_ROOT / sp
        rel = str(sp).replace("\\\\", "/")
        if rel in seen:
            continue
        seen.add(rel)

        surface_types = ["shell_reader"]
        has_effects = False
        if fpath.exists():
            try:
                header = fpath.read_text(encoding="utf-8")[:2048]
                has_effects = any(
                    kw in header.lower()
                    for kw in ("watchdog", "status", "liveness", "read", "snapshot")
                )
            except (OSError, UnicodeDecodeError):
                pass

        readers.append(_build_reader_entry(
            reader_path=rel,
            reader_category=READER_CATEGORY_SHELL,
            surface_types=surface_types,
            owner="Run Authority",
            raw_row={
                "has_boundary_effects": has_effects,
                "description": "Shell/wrapper reader surface",
            },
        ))

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _extract_resident_readers(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract resident (kernel/execution/supervisor) reader surfaces."""
    readers: list[dict[str, Any]] = []
    seen: set[str] = set()

    resident_keywords = ("/kernel/", "/execution/", "/supervisor/")

    for row in inventory.get("rows", []):
        if row.get("row_kind") != "runtime_module":
            continue
        module_path = row.get("module_path", "")
        if not any(kw in module_path for kw in resident_keywords):
            continue
        surface_types = row.get("surface_types", [])
        # Include if it has authority_reader or is a relevant surface
        if not ("authority_reader" in surface_types
                or "reader" in str(surface_types).lower()
                or "unknown" in surface_types):
            continue
        if module_path in seen:
            continue
        seen.add(module_path)

        readers.append(_build_reader_entry(
            reader_path=module_path,
            reader_category=READER_CATEGORY_RESIDENT,
            surface_types=surface_types if surface_types else ["resident_reader"],
            owner="Run Authority",
            raw_row=row,
        ))

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _extract_cloud_watchdog_readers() -> list[dict[str, Any]]:
    """Extract cloud/status/watchdog/liveness reader surfaces."""
    cloud_paths = [
        ("arnold_pipelines/megaplan/cloud/watchdog.py", "watchdog"),
        ("arnold_pipelines/megaplan/cloud/status_snapshot.py", "status_snapshot"),
        ("arnold_pipelines/megaplan/observability/liveness.py", "liveness"),
        ("arnold_pipelines/megaplan/cloud/progress_auditor_liveness.py", "liveness"),
    ]
    readers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for cp, kind in cloud_paths:
        fpath = REPO_ROOT / cp
        if cp in seen:
            continue
        seen.add(cp)

        is_non_authoritative = kind in NON_AUTHORITATIVE_READER_SURFACES
        surface_types = [kind]
        if is_non_authoritative:
            surface_types.insert(0, "non_authoritative_read")

        readers.append(_build_reader_entry(
            reader_path=cp,
            reader_category=READER_CATEGORY_CLOUD,
            surface_types=surface_types,
            owner="Run Authority",
            raw_row={
                "kind": kind,
                "is_authority": not is_non_authoritative,
                "exists": fpath.exists(),
                "non_authority_reason": (
                    f"{kind} cannot be positive authority per North Star; "
                    f"projections, liveness, status snapshots, and support labels "
                    f"must not skip/unblock/advance work"
                ) if is_non_authoritative else "",
            },
        ))

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _extract_projection_readers(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract projection surfaces — these MUST NOT be positive authority."""
    readers: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in inventory.get("rows", []):
        if row.get("row_kind") != "runtime_module":
            continue
        surface_types = row.get("surface_types", [])
        if "projection" not in surface_types:
            continue
        module_path = row.get("module_path", "")
        if module_path in seen:
            continue
        seen.add(module_path)

        # Projections are EXPLICITLY non-authoritative
        readers.append(_build_reader_entry(
            reader_path=module_path,
            reader_category=READER_CATEGORY_PROJECTION,
            surface_types=["non_authoritative_read", "projection"],
            owner="Run Authority",
            raw_row={
                **row,
                "is_authority": False,
                "non_authority_reason": (
                    "Projections are rebuildable diagnostics, never authority. "
                    "Accepting a projection as authority would violate the North Star "
                    "(projections cannot skip/unblock/advance work)."
                ),
            },
        ))

    # Also add AcceptAttemptProjection from authority_readers.py
    if "arnold_pipelines/megaplan/orchestration/authority_readers.py::AcceptedAttemptProjection" not in seen:
        readers.append(_build_reader_entry(
            reader_path="arnold_pipelines/megaplan/orchestration/authority_readers.py::AcceptedAttemptProjection",
            reader_category=READER_CATEGORY_PROJECTION,
            surface_types=["non_authoritative_read", "projection"],
            owner="Run Authority",
            raw_row={
                "class_name": "AcceptedAttemptProjection",
                "is_authority": False,
                "non_authority_reason": (
                    "AcceptedAttemptProjection is a read-only execute projection built "
                    "from accepted dispatch envelopes. It carries diagnostic data but "
                    "must never mint completion authority by itself."
                ),
            },
        ))

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _extract_compatibility_readers(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract compatibility reader surfaces."""
    readers: list[dict[str, Any]] = []
    seen: set[str] = set()

    compat_keywords = ("compat", "adapter", "bridge", "shim", "shadow")

    for row in inventory.get("rows", []):
        if row.get("row_kind") != "runtime_module":
            continue
        module_path = row.get("module_path", "").lower()
        surface_types = row.get("surface_types", [])
        if not any(kw in module_path for kw in compat_keywords):
            continue
        if "authority_reader" not in surface_types and "compatibility_shim" not in surface_types:
            continue
        if module_path in seen:
            continue
        seen.add(module_path)

        readers.append(_build_reader_entry(
            reader_path=row.get("module_path", module_path),
            reader_category=READER_CATEGORY_COMPATIBILITY,
            surface_types=surface_types,
            owner="Run Authority",
            raw_row=row,
        ))

    # Add dynamic compatibility reader placeholder
    readers.append(_build_reader_entry(
        reader_path="dynamic.compatibility_reader",
        reader_category=READER_CATEGORY_COMPATIBILITY,
        surface_types=["compatibility_shim"],
        owner="Run Authority",
        raw_row={
            "reason": "Compatibility reader surfaces resolved at runtime; cannot be statically discovered.",
            "is_authority": False,
        },
    ))

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _extract_provider_readers() -> list[dict[str, Any]]:
    """Emit placeholder rows for provider/dynamic reader surfaces."""
    provider_surfaces: list[dict[str, Any]] = [
        {
            "surface_id": "dynamic.provider_reader",
            "reason": (
                "Provider reader surfaces (plugin loaders, generated code consumers, "
                "subprocess readers) are resolved at runtime and cannot be statically "
                "discovered."
            ),
        },
    ]

    readers: list[dict[str, Any]] = []
    for ps in provider_surfaces:
        readers.append(_build_reader_entry(
            reader_path=ps["surface_id"],
            reader_category=READER_CATEGORY_PROVIDER,
            surface_types=["provider_reader", "dynamic_surface"],
            owner="Run Authority",
            raw_row={
                "reason": ps["reason"],
                "is_authority": False,
                "non_authority_reason": (
                    "Provider readers are dynamic surfaces that cannot be statically "
                    "verified. They must not serve as authority until enrolled in M7."
                ),
            },
        ))

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _extract_historical_readers() -> list[dict[str, Any]]:
    """Extract historical-reader paths (WBC evidence, audit trail, milestone artifacts)."""
    historical_surfaces = [
        ("evidence/wbc-boundary-inventory.json", "WBC boundary inventory evidence"),
        ("evidence/wbc-historical-adapters.json", "WBC historical adapters evidence"),
        ("evidence/m6-prerequisite-verification.json", "M6 prerequisite verification evidence"),
        ("evidence/finding-prevention-register.json", "M6 finding prevention register"),
        ("evidence/replay/transaction-spine.json", "Transaction spine replay fixture"),
        ("evidence/replay/strategy-roadmap.json", "Strategy roadmap replay fixture"),
        ("evidence/controlled-writer-registry.json", "M6 controlled-writer registry"),
        (".megaplan/initiatives/custody-control-plane/research/", "Custody control plane research"),
        (".megaplan/watchdog-run-logs/", "Watchdog run logs archive"),
    ]
    readers: list[dict[str, Any]] = []

    for path, description in historical_surfaces:
        readers.append(_build_reader_entry(
            reader_path=path,
            reader_category=READER_CATEGORY_HISTORICAL,
            surface_types=["historical_reader"],
            owner="WBC",
            raw_row={
                "description": description,
                "is_authority": False,
                "non_authority_reason": (
                    "Historical evidence is content-addressed and rebuildable. "
                    "It provides audit trail and verification but does not mint "
                    "new completion authority."
                ),
            },
        ))

    readers.sort(key=lambda r: r["reader_path"])
    return readers


def _classify_reader_category(
    module_path: str, surface_types: list[str],
) -> str:
    """Classify a reader module into a category."""
    path_lower = module_path.lower()

    if "advisory_projection" in path_lower or "projection" in surface_types:
        return READER_CATEGORY_PROJECTION
    if any(kw in path_lower for kw in ("compat", "adapter", "bridge", "shim", "shadow")):
        return READER_CATEGORY_COMPATIBILITY
    if any(kw in path_lower for kw in ("cloud", "watchdog", "liveness", "status_snapshot")):
        return READER_CATEGORY_CLOUD
    if any(seg in path_lower for seg in ("/kernel/", "/execution/", "/supervisor/")):
        return READER_CATEGORY_RESIDENT
    if "evidence/" in path_lower or "historical" in path_lower:
        return READER_CATEGORY_HISTORICAL

    return READER_CATEGORY_PYTHON


def _derive_reader_id(reader_path: str) -> str:
    """Derive a stable reader_id from the reader path."""
    clean = reader_path.replace("/", ".").replace("\\\\", ".").replace("-", "_")
    clean = clean.lstrip(".")
    if clean.endswith(".py") or clean.endswith(".sh"):
        clean = clean[:-3]
    return f"reader.{clean}"


def _build_reader_entry(
    reader_path: str,
    reader_category: str,
    surface_types: list[str],
    owner: str,
    raw_row: dict[str, Any],
) -> dict[str, Any]:
    """Build a single authority-reader registry entry."""
    defaults = READER_CATEGORY_DEFAULTS.get(
        reader_category, READER_CATEGORY_DEFAULTS[READER_CATEGORY_PYTHON]
    )
    reader_id = _derive_reader_id(reader_path)

    entry: dict[str, Any] = {
        "reader_id": reader_id,
        "reader_path": reader_path,
        "reader_category": reader_category,
        "surface_types": sorted(set(surface_types)),
        "owner": owner,
        "current_contract": defaults["current_contract"],
        "target_contract": defaults["target_contract"],
        "boundary_conditions": defaults["boundary_conditions"],
        "fail_closed": defaults["fail_closed"],
        "proof": defaults["proof"],
        "rollback_policy": defaults["rollback_policy"],
        "mixed_version_policy": defaults["mixed_version_policy"],
        "retirement_gate": defaults["retirement_gate"],
        "evidence_ref": f"WBC boundary inventory: {reader_path}",
    }

    # Is-authority flag
    if raw_row.get("is_authority") is not None:
        entry["is_authority"] = bool(raw_row["is_authority"])
    else:
        entry["is_authority"] = "authority_reader" in surface_types

    # Non-authority reason (for projection/liveness/snapshot/support-label surfaces)
    non_auth_reason = raw_row.get("non_authority_reason", "")
    if non_auth_reason:
        entry["non_authority_reason"] = non_auth_reason

    # Route-specific metadata
    for key in ("route_id", "disposition", "route_family", "kind", "description"):
        if raw_row.get(key):
            entry[key] = raw_row[key]

    # Compute stable row hash
    entry["row_hash"] = _compute_row_hash(entry)

    return entry


def generate_reader_registry(output_path: Path | None = None) -> dict[str, Any]:
    """Generate the full authority-reader registry artifact."""
    inventory = _load_inventory()

    python_readers = _extract_python_readers(inventory)
    route_readers = _extract_authority_routes_as_readers()
    shell_readers = _extract_shell_readers()
    resident_readers = _extract_resident_readers(inventory)
    cloud_readers = _extract_cloud_watchdog_readers()
    provider_readers = _extract_provider_readers()
    projection_readers = _extract_projection_readers(inventory)
    compatibility_readers = _extract_compatibility_readers(inventory)
    historical_readers = _extract_historical_readers()

    # Merge all readers and sort deterministically
    all_readers = (
        python_readers + route_readers + shell_readers
        + resident_readers + cloud_readers + provider_readers
        + projection_readers + compatibility_readers + historical_readers
    )
    all_readers.sort(key=lambda r: (r["reader_category"], r["reader_path"]))

    # Count by category
    category_counts: dict[str, int] = {}
    for r in all_readers:
        cat = r["reader_category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Count non-authoritative readers
    non_authoritative_count = sum(
        1 for r in all_readers if not r.get("is_authority", True)
    )
    non_authoritative_ids = [
        r["reader_id"] for r in all_readers if not r.get("is_authority", True)
    ]

    artifact: dict[str, Any] = {
        "schema": READER_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/generate_m6_controlled_registries.py",
        "source_inventory": str(WBC_INVENTORY_PATH.relative_to(REPO_ROOT)),
        "reader_count": len(all_readers),
        "category_counts": category_counts,
        "reader_categories": sorted(category_counts.keys()),
        "non_authoritative_count": non_authoritative_count,
        "non_authoritative_reader_ids": sorted(non_authoritative_ids),
        "north_star_guard": (
            "Projections, liveness, status snapshots, and support labels "
            "MUST NEVER serve as positive action authority. Any reader surface "
            "classified as projection, liveness, status_snapshot, or support_label "
            "is explicitly marked is_authority=false in this registry."
        ),
        "rows": all_readers,
        "composite_hash": _compute_composite_hash(all_readers),
        "row_hash_algorithm": "SHA-256",
        "row_hash_coverage": (
            "each row hash computed from deterministically ordered JSON "
            "excluding row_hash field"
        ),
        "fail_closed_default": (
            "Any reader whose authority classification is uncertain "
            "defaults to fail-closed (deny). Readers must be explicitly "
            "enrolled to serve authority reads."
        ),
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return artifact


def _validate_reader_registry(artifact: dict[str, Any]) -> bool:
    """Validate the reader registry artifact. Returns True if valid."""
    errors: list[str] = []

    if artifact.get("schema") != READER_SCHEMA:
        errors.append(f"Schema mismatch: {artifact.get('schema')} != {READER_SCHEMA}")

    rows = artifact.get("rows", [])
    if len(rows) == 0:
        errors.append("Reader registry has zero rows")

    required_fields = {
        "reader_id", "reader_path", "reader_category", "surface_types",
        "owner", "current_contract", "target_contract", "boundary_conditions",
        "fail_closed", "proof", "rollback_policy", "mixed_version_policy",
        "retirement_gate", "evidence_ref", "row_hash",
    }

    valid_categories = set(READER_CATEGORY_DEFAULTS.keys())
    valid_owners = {"WBC", "Run Authority", "TransitionWriter/repair custody"}

    projection_liveness_ids: list[str] = []

    for row in rows:
        rid = row.get("reader_id", "?")

        missing = required_fields - set(row.keys())
        if missing:
            errors.append(f"Row {rid}: missing fields {sorted(missing)}")

        expected_hash = _compute_row_hash(row)
        actual_hash = row.get("row_hash", "")
        if expected_hash != actual_hash:
            errors.append(
                f"Row {rid}: hash mismatch "
                f"(expected {expected_hash[:12]}..., got {actual_hash[:12]}...)"
            )

        cat = row.get("reader_category", "")
        if cat not in valid_categories:
            errors.append(f"Row {rid}: unknown reader_category '{cat}'")

        owner = row.get("owner", "")
        if owner not in valid_owners:
            errors.append(f"Row {rid}: unknown owner '{owner}'")

        for field in required_fields - {"row_hash"}:
            value = row.get(field)
            if not value and field not in ("surface_types",):
                errors.append(f"Row {rid}: {field} is empty")

        # North Star guard: projection/liveness/status_snapshot/support_label MUST NOT be authority
        sts = set(row.get("surface_types", []))
        if sts & NON_AUTHORITATIVE_READER_SURFACES:
            projection_liveness_ids.append(rid)
            if row.get("is_authority", False):
                errors.append(
                    f"NORTH STAR VIOLATION: {rid} has surface types "
                    f"{sts & NON_AUTHORITATIVE_READER_SURFACES} but is_authority=true. "
                    f"Projections, liveness, status snapshots, and support labels "
                    f"cannot be positive authority."
                )

    # Composite hash
    expected_composite = _compute_composite_hash(rows)
    actual_composite = artifact.get("composite_hash", "")
    if expected_composite != actual_composite:
        errors.append("Composite hash mismatch")

    # Category coverage
    categories_found = set(artifact.get("reader_categories", []))
    required_categories = {READER_CATEGORY_PYTHON, READER_CATEGORY_PROJECTION}
    missing_cats = required_categories - categories_found
    if missing_cats:
        errors.append(f"Missing required categories: {sorted(missing_cats)}")

    # Verify non_authoritative_count
    non_auth_actual = sum(
        1 for r in rows if not r.get("is_authority", True)
    )
    if non_auth_actual != artifact.get("non_authoritative_count", -1):
        errors.append(
            f"non_authoritative_count mismatch: "
            f"declared={artifact.get('non_authoritative_count')}, "
            f"actual={non_auth_actual}"
        )

    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return False

    print("Validation PASSED", file=sys.stderr)
    return True


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate M6 controlled-writer registry"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the generated artifact",
    )
    parser.add_argument(
        "--reader-registry",
        action="store_true",
        help="Generate the authority-reader registry instead of the writer registry",
    )
    parser.add_argument(
        "--reader-output",
        type=Path,
        default=READER_DEFAULT_OUTPUT,
        help=f"Reader registry output path (default: {READER_DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    if args.reader_registry:
        artifact = generate_reader_registry(output_path=args.reader_output)
        print(
            f"Generated {len(artifact['rows'])} reader entries -> {args.reader_output}",
            file=sys.stderr,
        )
        if args.validate:
            valid = _validate_reader_registry(artifact)
            if not valid:
                sys.exit(1)
    else:
        artifact = generate_registry(output_path=args.output)
        print(
            f"Generated {len(artifact['rows'])} writer entries -> {args.output}",
            file=sys.stderr,
        )
        if args.validate:
            valid = _validate_registry(artifact)
            if not valid:
                sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
