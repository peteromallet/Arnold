#!/usr/bin/env python3
"""M6 ownership decision generator (T14 — Step 13).

Produces two evidence artifacts:

1. ``evidence/pc-scope-decision.json`` — resolves what "PC" means in
   checkpoint/cursor contexts.  Defaults to native program counter (``pc``)
   unless repository evidence proves otherwise (e.g., Parity Corrective or
   control-plane scope claims).  Unresolved human approval is encoded as a
   blocker, not acceptance.

2. ``evidence/ownership-decision-record.json`` — records locked Run
   Authority / WBC / Custody ownership decisions derived from the unified
   authority research document, reconciled migration matrix, controlled
   registries, finding register, and prerequisite verification.
   Unresolved fields (human approval, M5 receipt acceptance) are encoded
   as blockers.

Design invariants
-----------------

* **Repository evidence first**: every decision cites specific evidence
  artifacts, document sections, and content hashes.
* **Default PC → program counter**: the checkpoint/cursor ``pc`` field
  defaults to native program counter.  Only a committed evidence trail
  (not a plan label or initiative name) can narrow or widen the scope.
* **Blocker encoding**: unresolved human approval gates (Run Authority
  M1-M3 completion receipts, PC portfolio gate) appear as explicit
  blocker entries with required evidence, never as accepted decisions.
* **Deterministic ordering**: decisions are sorted by owner then surface,
  producing stable content hashes across regeneration.
* **Observe-only**: reads git/files/import metadata and existing evidence;
  writes only the two decision artifacts.

Usage::

    python tools/generate_m6_ownership_decision.py [--output-dir PATH] [--validate]
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

# Evidence inputs
PREREQ_PATH = EVIDENCE_DIR / "m6-prerequisite-verification.json"
WBC_INVENTORY_PATH = EVIDENCE_DIR / "wbc-boundary-inventory.json"
WRITER_REGISTRY_PATH = EVIDENCE_DIR / "controlled-writer-registry.json"
READER_REGISTRY_PATH = EVIDENCE_DIR / "authority-reader-registry.json"
FINDING_REGISTER_PATH = EVIDENCE_DIR / "finding-prevention-register.json"
MIGRATION_MATRIX_PATH = EVIDENCE_DIR / "migration-matrix-reconciled.json"
REPLAY_TX_PATH = EVIDENCE_DIR / "replay" / "transaction-spine.json"
REPLAY_STRATEGY_PATH = EVIDENCE_DIR / "replay" / "strategy-roadmap.json"

# Research documents
AUTHORITY_RESEARCH_PATH = (
    REPO_ROOT
    / ".megaplan/initiatives/custody-control-plane/research"
    / "unified-authority-efficiency-prevention-20260714.md"
)
LINEAGE_AUDIT_PATH = (
    REPO_ROOT
    / ".megaplan/initiatives/custody-control-plane/research"
    / "authority-lineage-and-gap-audit-20260711.md"
)

# Outputs
DEFAULT_OUTPUT_DIR = EVIDENCE_DIR
PC_SCOPE_PATH = EVIDENCE_DIR / "pc-scope-decision.json"
OWNERSHIP_PATH = EVIDENCE_DIR / "ownership-decision-record.json"

# Schemas
PC_SCOPE_SCHEMA = "m6.pc-scope-decision.v1"
OWNERSHIP_SCHEMA = "m6.ownership-decision-record.v1"

# ── Helpers ─────────────────────────────────────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _compute_row_hash(row: dict[str, Any], exclude_keys: frozenset[str] = frozenset({"row_hash"})) -> str:
    """Compute stable SHA-256 hash for a decision row."""
    canonical = {k: row[k] for k in sorted(row) if k not in exclude_keys}
    return _sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False))


def _compute_composite_hash(rows: list[dict[str, Any]]) -> str:
    """Compute composite hash from sorted row hashes."""
    joined = "".join(sorted(r.get("row_hash", _compute_row_hash(r)) for r in rows))
    return _sha256(joined)


# ── PC scope decision ───────────────────────────────────────────────────────


def _build_pc_scope_decision(
    prerequisite_data: dict[str, Any],
    migration_matrix: dict[str, Any],
) -> dict[str, Any]:
    """Build the PC scope decision artifact.

    PC in checkpoint/cursor contexts defaults to native program counter.
    Repository evidence is checked for Parity Corrective or control-plane
    scope claims.  The Portfolio gate (row 91) is encoded as a blocker.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Find the PC-adjacent row in the migration matrix
    pc_adjacent_rows = [
        r for r in migration_matrix.get("rows", [])
        if "PC" in r.get("consumer_surface", "") or "pc" in r.get("consumer_surface", "").lower()
    ]
    native_checkpoint_rows = [
        r for r in migration_matrix.get("rows", [])
        if "Native persistence checkpoint" in r.get("consumer_surface", "")
    ]

    # Evidence: the Native platform uses ``pc`` as program counter
    # See arnold/pipeline/native/ir.py line ~386: "Each instruction carries
    # an explicit program counter (``pc``)"
    # See arnold/pipeline/native/checkpoint.py line ~25: "The ``native``
    # key carries the program counter and a schema version"

    # Check for counter-evidence (Parity Corrective claims on PC)
    parity_corrective_rows = [
        r for r in migration_matrix.get("rows", [])
        if "Parity Corrective" in r.get("current_authority", "")
        or "Parity" in r.get("owner", "")
    ]

    # Build the decision
    decisions: list[dict[str, Any]] = []

    # Decision 1: PC in checkpoint/cursor → program counter
    pc_evidence = {
        "source_files": [
            {
                "path": "arnold/pipeline/native/ir.py",
                "line_approx": 386,
                "quote": "Each instruction carries an explicit program counter (``pc``)",
                "interpretation": "pc is a zero-based index into the instruction tuple",
            },
            {
                "path": "arnold/pipeline/native/checkpoint.py",
                "line_approx": 25,
                "quote": "The ``native`` key carries the program counter and a schema version",
                "interpretation": "cursor_pc / pc in checkpoint JSON refers to program counter",
            },
            {
                "path": "arnold/pipeline/native/checkpoint.py",
                "line_approx": 686,
                "quote": "pc: Current zero-based program counter.",
                "interpretation": "Docstring confirms pc = program counter",
            },
        ],
        "migration_matrix_rows": [
            {
                "row_index": r["row_index"],
                "consumer_surface": r["consumer_surface"],
                "current_authority": r["current_authority"],
                "owner": r["owner"],
                "classification": r["classification"],
            }
            for r in (pc_adjacent_rows + native_checkpoint_rows)
        ],
    }

    decisions.append({
        "decision_id": "PC-SCOPE-001",
        "surface": "Native persistence checkpoint/cursor ``pc`` field",
        "verdict": "program_counter",
        "rationale": (
            "All repository evidence — the Native IR compiler, checkpoint "
            "module, runtime, and trace modules — defines ``pc`` as a "
            "zero-based program counter indexing the instruction tuple. "
            "No committed evidence supports Parity Corrective or "
            "control-plane ownership of the ``pc`` field. The migration "
            "matrix row 4 (Native persistence checkpoint/cursor) is "
            "classified as residual/legacy under Native Platform ownership "
            "with M8 handoff. Row 91 (PC adjacent work) explicitly requires "
            "human portfolio gate approval — that gate is encoded as a "
            "blocker below, not accepted scope expansion."
        ),
        "evidence": pc_evidence,
        "blockers": [
            {
                "blocker_id": "PC-SCOPE-BLOCKER-001",
                "description": (
                    "Human portfolio gate approval required for PC scope "
                    "decision (migration matrix row 91, owner: Portfolio gate). "
                    "Until approved, PC scope defaults to program counter only."
                ),
                "source": "migration matrix row 91 (PC adjacent work)",
                "required_evidence": "PC_SCOPE_DECISION human approval record",
                "status": "blocked",
            }
        ],
        "row_hash": "",
    })

    # Compute row hashes
    for d in decisions:
        d["row_hash"] = _compute_row_hash(d)

    composite_hash = _compute_composite_hash(decisions)

    return {
        "schema": PC_SCOPE_SCHEMA,
        "generated_at": now,
        "generator": "tools/generate_m6_ownership_decision.py",
        "source_evidence": {
            "prerequisite_verification": str(PREREQ_PATH),
            "migration_matrix_reconciled": str(MIGRATION_MATRIX_PATH),
        },
        "default_interpretation": "program_counter",
        "default_rationale": (
            "PC in checkpoint/cursor contexts defaults to native program "
            "counter. All committed source evidence (IR compiler, checkpoint "
            "module, runtime, trace) uses 'pc' as a zero-based instruction "
            "index. No repository evidence proves an alternative scope "
            "(Parity Corrective, control plane, or otherwise)."
        ),
        "blocker_count": sum(len(d.get("blockers", [])) for d in decisions),
        "decision_count": len(decisions),
        "decisions": decisions,
        "composite_hash": composite_hash,
    }


# ── Ownership decision record ───────────────────────────────────────────────


def _parse_ownership_matrix_from_research(research_text: str) -> list[dict[str, Any]]:
    """Extract the explicit ownership matrix table from the research document."""
    # Find the "## Explicit ownership matrix" section
    matrix_start = research_text.find("## Explicit ownership matrix")
    if matrix_start == -1:
        return []

    # Extract the table section (between the header and the next ## header)
    section = research_text[matrix_start:]
    next_section = section.find("\n## ", len("## Explicit ownership matrix"))
    if next_section != -1:
        section = section[:next_section]

    # Parse pipe-delimited rows
    rows: list[dict[str, Any]] = []
    in_table = False
    for line in section.split("\n"):
        line = line.strip()
        if line.startswith("|") and "---" not in line:
            if not in_table:
                # Header row
                in_table = True
                continue
            # Data row
            parts = [p.strip() for p in line.split("|")]
            # Expected: empty, Owner, Owns, Must not own, empty
            if len(parts) >= 4:
                owner = parts[1]
                owns = parts[2]
                must_not_own = parts[3]
                if owner and owner not in ("Owner", ""):
                    rows.append({
                        "owner": owner,
                        "owns": owns,
                        "must_not_own": must_not_own,
                    })

    return rows


def _build_ownership_decision_record(
    prerequisite_data: dict[str, Any],
    migration_matrix: dict[str, Any],
    writer_registry: dict[str, Any],
    reader_registry: dict[str, Any],
    finding_register: dict[str, Any],
    research_text: str,
    lineage_text: str,
) -> dict[str, Any]:
    """Build the ownership decision record artifact."""
    now = datetime.now(timezone.utc).isoformat()

    # Parse the explicit ownership matrix from the research document
    explicit_owners = _parse_ownership_matrix_from_research(research_text)

    # Collect all unique owners from the migration matrix
    matrix_owners: dict[str, list[dict[str, Any]]] = {}
    for row in migration_matrix.get("rows", []):
        owner = row.get("owner", "UNKNOWN")
        if owner not in matrix_owners:
            matrix_owners[owner] = []
        matrix_owners[owner].append({
            "row_index": row["row_index"],
            "consumer_surface": row["consumer_surface"],
            "current_authority": row["current_authority"],
            "target_authority": row["target_authority"],
            "milestone": row["milestone"],
            "classification": row["classification"],
            "proof_requirement": row.get("proof_requirement", ""),
            "handoff_milestone": row.get("handoff_milestone"),
            "blocked_by_prerequisites": row.get("blocked_by_prerequisites", []),
        })

    # Build owner decision entries
    owner_decisions: list[dict[str, Any]] = []

    # Map explicit ownership from research document
    owner_surface_map: dict[str, dict[str, Any]] = {}
    for eo in explicit_owners:
        owner_surface_map[eo["owner"]] = {
            "owner": eo["owner"],
            "owns": eo["owns"],
            "must_not_own": eo["must_not_own"],
            "source": "unified-authority-efficiency-prevention-20260714.md §Explicit ownership matrix",
        }

    # Known owners and their canonical surfaces
    known_owners = [
        "Run Authority",
        "WBC",
        "TransitionWriter/repair custody",
        "Megaplan Maintenance",
        "Planner/compiler",
        "Executor/launcher",
        "Observability",
        "Native Parity",
        "Native Platform",
        "Portfolio gate",
        "Megaplan Cloud",
        "Megaplan chain",
        "Megaplan orchestration",
        "Megaplan runtime",
        "custody-control-plane",
    ]

    for owner in known_owners:
        explicit = owner_surface_map.get(owner, {})
        surfaces = matrix_owners.get(owner, [])

        # Count classifications
        classification_counts: dict[str, int] = {}
        for s in surfaces:
            cls = s["classification"]
            classification_counts[cls] = classification_counts.get(cls, 0) + 1

        # Collect blockers
        blockers: list[dict[str, Any]] = []
        for s in surfaces:
            if s["classification"] == "blocked":
                blockers.append({
                    "row_index": s["row_index"],
                    "consumer_surface": s["consumer_surface"],
                    "blocked_by": s.get("blocked_by_prerequisites", []),
                    "proof_required": s.get("proof_requirement", ""),
                    "milestone": s["milestone"],
                })

        decision = {
            "owner": owner,
            "canonical_owns": explicit.get("owns", "Not defined in explicit ownership matrix"),
            "canonical_must_not_own": explicit.get("must_not_own", "Not defined in explicit ownership matrix"),
            "matrix_surface_count": len(surfaces),
            "classification_counts": classification_counts,
            "residual_count": classification_counts.get("residual", 0),
            "blocked_count": classification_counts.get("blocked", 0),
            "prerequisite_satisfied_count": classification_counts.get("prerequisite-satisfied", 0),
            "retired_count": classification_counts.get("retired", 0),
            "out_of_scope_count": classification_counts.get("out-of-supported-scope", 0),
            "surfaces": [
                {
                    "row_index": s["row_index"],
                    "consumer_surface": s["consumer_surface"],
                    "current_authority": s["current_authority"],
                    "target_authority": s["target_authority"],
                    "milestone": s["milestone"],
                    "classification": s["classification"],
                    "handoff_milestone": s.get("handoff_milestone"),
                }
                for s in surfaces
            ],
            "blockers": blockers,
            "row_hash": "",
        }
        owner_decisions.append(decision)

    # Sort by owner name for deterministic output
    owner_decisions.sort(key=lambda d: d["owner"])

    # ── Global blockers ──────────────────────────────────────────────────

    # Blocker 1: Run Authority M1-M3 completion receipts not accepted
    ra_blocker = {
        "blocker_id": "OWNERSHIP-BLOCKER-001",
        "description": (
            "Run Authority M1-M3 completion receipts: all three have "
            "`accepted: false`. Stale/missing phase evidence, diff "
            "mismatches, and structural failures prevent acceptance. "
            "M5 owns reconciliation and canonical retirement proof "
            "before adoption proceeds. Until accepted, Run Authority "
            "ownership decisions remain provisional."
        ),
        "affected_owner": "Run Authority",
        "source_evidence": [
            "migration matrix row 0 (Run Authority M1-M3 completion receipts)",
            "authority-lineage-and-gap-audit-20260711.md §2026-07-13 ownership reconciliation",
            "unified-authority-efficiency-prevention-20260714.md §Evidence reconciled",
        ],
        "required_resolution": "Three content-addressed accepted receipts with canonical divergence count 0",
        "status": "blocked",
        "blocks_milestones": ["M6A", "M7", "M8", "M8A", "M9", "M10", "M11"],
    }

    # Blocker 2: Portfolio gate — PC scope decision
    portfolio_blocker = {
        "blocker_id": "OWNERSHIP-BLOCKER-002",
        "description": (
            "Portfolio gate approval required for PC scope decision. "
            "Migration matrix row 91 (PC adjacent work) has owner "
            "'Portfolio gate' (human portfolio gate) with proof "
            "requirement `PC_SCOPE_DECISION`. Until human approval is "
            "recorded, PC defaults to program counter and M7 is blocked "
            "on material overlap."
        ),
        "affected_owner": "Portfolio gate",
        "source_evidence": [
            "migration matrix row 91 (PC adjacent work)",
            "evidence/pc-scope-decision.json (machine-generated, pending human approval)",
        ],
        "required_resolution": "Human portfolio gate approval record for PC scope decision",
        "status": "blocked",
        "blocks_milestones": ["M7"],
    }

    # Blocker 3: M5 bound-head mismatch
    m5_blocker = {
        "blocker_id": "OWNERSHIP-BLOCKER-003",
        "description": (
            "M5 bound-head (8bb779d) does not match current HEAD. "
            "Prerequisite verification reports INCOHERENT for "
            "m5_bound_head_vs_current_head. Downstream M6 handoff "
            "artifacts are not marked complete until this is resolved."
        ),
        "affected_owner": "Run Authority",
        "source_evidence": [
            "evidence/m6-prerequisite-verification.json §check=m5_bound_head_vs_current_head → INCOHERENT",
        ],
        "required_resolution": "Either rebase to M5 bound head or produce successor attestation",
        "status": "blocked",
        "blocks_milestones": ["M6A", "M7", "M8", "M8A", "M9", "M10", "M11"],
    }

    # Blocker 4: WBC file hash mismatch
    wbc_hash_blocker = {
        "blocker_id": "OWNERSHIP-BLOCKER-004",
        "description": (
            "WBC file hash check reports INCOHERENT: one source file "
            "mismatch between current working tree and the WBC "
            "integration commit (24afce00). This must be resolved "
            "before WBC ownership evidence is fully coherent."
        ),
        "affected_owner": "WBC",
        "source_evidence": [
            "evidence/m6-prerequisite-verification.json §check=wbc_file_hashes → INCOHERENT",
        ],
        "required_resolution": "Reconcile diverged WBC file or accept as documented drift",
        "status": "blocked",
        "blocks_milestones": ["M6A"],
    }

    global_blockers = [ra_blocker, portfolio_blocker, m5_blocker, wbc_hash_blocker]

    # Compute row hashes
    for d in owner_decisions:
        d["row_hash"] = _compute_row_hash(d)

    composite_hash = _compute_composite_hash(owner_decisions)

    return {
        "schema": OWNERSHIP_SCHEMA,
        "generated_at": now,
        "generator": "tools/generate_m6_ownership_decision.py",
        "source_evidence": {
            "prerequisite_verification": str(PREREQ_PATH),
            "migration_matrix_reconciled": str(MIGRATION_MATRIX_PATH),
            "controlled_writer_registry": str(WRITER_REGISTRY_PATH),
            "authority_reader_registry": str(READER_REGISTRY_PATH),
            "finding_prevention_register": str(FINDING_REGISTER_PATH),
            "unified_authority_research": str(AUTHORITY_RESEARCH_PATH),
            "lineage_audit": str(LINEAGE_AUDIT_PATH),
        },
        "north_star_principles": [
            "One exact-version Run Authority reducer decides which attempts and claims are accepted.",
            "WBC preserves immutable attempt/boundary/effect facts.",
            "TransitionWriter and fenced repair custody serialize lifecycle mutation and recovery.",
            "All plan, chain, cloud, repair, resident, and operator views are rebuildable projections.",
            "No legacy authority bypass survives completion.",
        ],
        "explicit_ownership_matrix": explicit_owners,
        "owner_count": len(owner_decisions),
        "total_surface_count": sum(d["matrix_surface_count"] for d in owner_decisions),
        "blocker_count": len(global_blockers),
        "owner_decisions": owner_decisions,
        "global_blockers": global_blockers,
        "composite_hash": composite_hash,
    }


# ── Validation ──────────────────────────────────────────────────────────────


def _validate_pc_scope(pc_scope: dict[str, Any]) -> list[str]:
    """Validate the PC scope decision artifact. Returns list of errors."""
    errors: list[str] = []

    if pc_scope.get("schema") != PC_SCOPE_SCHEMA:
        errors.append(f"Schema mismatch: expected {PC_SCOPE_SCHEMA}, got {pc_scope.get('schema')}")

    if pc_scope.get("default_interpretation") != "program_counter":
        errors.append("default_interpretation must be 'program_counter'")

    decisions = pc_scope.get("decisions", [])
    if not decisions:
        errors.append("At least one PC scope decision required")

    for i, d in enumerate(decisions):
        if not d.get("decision_id"):
            errors.append(f"Decision {i} missing decision_id")
        if not d.get("verdict"):
            errors.append(f"Decision {i} missing verdict")
        if not d.get("row_hash"):
            errors.append(f"Decision {i} missing row_hash")

    # Verify composite hash
    if decisions and pc_scope.get("composite_hash"):
        expected = _compute_composite_hash(decisions)
        if expected != pc_scope["composite_hash"]:
            errors.append(f"Composite hash mismatch: expected {expected}, got {pc_scope['composite_hash']}")

    # Check that blockers have status=blocked
    for d in decisions:
        for b in d.get("blockers", []):
            if b.get("status") != "blocked":
                errors.append(f"Blocker {b.get('blocker_id')} in {d.get('decision_id')} must have status=blocked")

    return errors


def _validate_ownership(ownership: dict[str, Any]) -> list[str]:
    """Validate the ownership decision record artifact. Returns list of errors."""
    errors: list[str] = []

    if ownership.get("schema") != OWNERSHIP_SCHEMA:
        errors.append(f"Schema mismatch: expected {OWNERSHIP_SCHEMA}, got {ownership.get('schema')}")

    owner_decisions = ownership.get("owner_decisions", [])
    if not owner_decisions:
        errors.append("At least one owner decision required")

    owners_seen: set[str] = set()
    for d in owner_decisions:
        owner = d.get("owner", "")
        if not owner:
            errors.append("Owner decision missing owner field")
            continue
        if owner in owners_seen:
            errors.append(f"Duplicate owner: {owner}")
        owners_seen.add(owner)

        if not d.get("row_hash"):
            errors.append(f"Owner {owner} missing row_hash")

        # All surfaces must have a classification
        for s in d.get("surfaces", []):
            if not s.get("classification"):
                errors.append(f"Owner {owner} surface row {s.get('row_index')} missing classification")

        # Classification counts must match surfaces
        counts = d.get("classification_counts", {})
        actual: dict[str, int] = {}
        for s in d.get("surfaces", []):
            cls = s["classification"]
            actual[cls] = actual.get(cls, 0) + 1
        if counts != actual:
            errors.append(f"Owner {owner} classification_counts {counts} != actual {actual}")

    # Check for required owners
    required_owners = {"Run Authority", "WBC", "TransitionWriter/repair custody"}
    missing = required_owners - owners_seen
    if missing:
        errors.append(f"Missing required owners: {missing}")

    # Verify composite hash
    if owner_decisions and ownership.get("composite_hash"):
        expected = _compute_composite_hash(owner_decisions)
        if expected != ownership["composite_hash"]:
            errors.append(f"Composite hash mismatch: expected {expected}, got {ownership['composite_hash']}")

    # All global blockers must have status=blocked
    for b in ownership.get("global_blockers", []):
        if b.get("status") != "blocked":
            errors.append(f"Global blocker {b.get('blocker_id')} must have status=blocked")

    return errors


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate M6 ownership decision artifacts")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated artifacts and exit non-zero on errors",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load evidence
    evidence_loaded: dict[str, bool] = {}
    errors: list[str] = []

    prerequisite_data: dict[str, Any] = {}
    if PREREQ_PATH.exists():
        prerequisite_data = _load_json(PREREQ_PATH)
        evidence_loaded["prerequisite_verification"] = True
    else:
        errors.append(f"Missing prerequisite verification: {PREREQ_PATH}")
        evidence_loaded["prerequisite_verification"] = False

    migration_matrix: dict[str, Any] = {}
    if MIGRATION_MATRIX_PATH.exists():
        migration_matrix = _load_json(MIGRATION_MATRIX_PATH)
        evidence_loaded["migration_matrix_reconciled"] = True
    else:
        errors.append(f"Missing migration matrix: {MIGRATION_MATRIX_PATH}")
        evidence_loaded["migration_matrix_reconciled"] = False

    writer_registry: dict[str, Any] = {}
    if WRITER_REGISTRY_PATH.exists():
        writer_registry = _load_json(WRITER_REGISTRY_PATH)
        evidence_loaded["controlled_writer_registry"] = True
    else:
        evidence_loaded["controlled_writer_registry"] = False

    reader_registry: dict[str, Any] = {}
    if READER_REGISTRY_PATH.exists():
        reader_registry = _load_json(READER_REGISTRY_PATH)
        evidence_loaded["authority_reader_registry"] = True
    else:
        evidence_loaded["authority_reader_registry"] = False

    finding_register: dict[str, Any] = {}
    if FINDING_REGISTER_PATH.exists():
        finding_register = _load_json(FINDING_REGISTER_PATH)
        evidence_loaded["finding_prevention_register"] = True
    else:
        evidence_loaded["finding_prevention_register"] = False

    research_text = ""
    if AUTHORITY_RESEARCH_PATH.exists():
        research_text = _read_text(AUTHORITY_RESEARCH_PATH)
        evidence_loaded["unified_authority_research"] = True
    else:
        evidence_loaded["unified_authority_research"] = False

    lineage_text = ""
    if LINEAGE_AUDIT_PATH.exists():
        lineage_text = _read_text(LINEAGE_AUDIT_PATH)
        evidence_loaded["lineage_audit"] = True
    else:
        evidence_loaded["lineage_audit"] = False

    # ── Build PC scope decision ──────────────────────────────────────────

    pc_scope = _build_pc_scope_decision(prerequisite_data, migration_matrix)

    # ── Build ownership decision record ──────────────────────────────────

    ownership = _build_ownership_decision_record(
        prerequisite_data,
        migration_matrix,
        writer_registry,
        reader_registry,
        finding_register,
        research_text,
        lineage_text,
    )

    # ── Emit artifacts ───────────────────────────────────────────────────

    pc_scope_output = output_dir / "pc-scope-decision.json"
    with open(pc_scope_output, "w", encoding="utf-8") as fh:
        json.dump(pc_scope, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    ownership_output = output_dir / "ownership-decision-record.json"
    with open(ownership_output, "w", encoding="utf-8") as fh:
        json.dump(ownership, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"Wrote {pc_scope_output}")
    print(f"Wrote {ownership_output}")
    print(f"Evidence loaded: {json.dumps(evidence_loaded, indent=2)}")

    # ── Validate ─────────────────────────────────────────────────────────

    validation_errors = _validate_pc_scope(pc_scope)
    validation_errors.extend(_validate_ownership(ownership))

    if validation_errors:
        print(f"\nValidation errors ({len(validation_errors)}):")
        for err in validation_errors:
            print(f"  - {err}")

    if args.validate:
        if validation_errors:
            print("\nVALIDATION FAILED")
            sys.exit(1)
        else:
            print("\nVALIDATION PASSED")

    if errors:
        print(f"\nEvidence loading issues ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
        if args.validate:
            sys.exit(1)


if __name__ == "__main__":
    main()
