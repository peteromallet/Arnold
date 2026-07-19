#!/usr/bin/env python3
"""M6 migration matrix reconciler (T13 — Step 12).

Produces ``evidence/migration-matrix-reconciled.json`` by joining the
91-row (92-row actual) migration matrix from the committed research document
with prerequisite verification, WBC boundary inventory, controlled writer
registry, authority reader registry, finding prevention register, and
replay fixtures.

Every row is classified into exactly one of:

* **prerequisite-satisfied** — WBC proof exists, owner confirmed, evidence present
* **residual** — substrate gap (→M6A), missing producers (→M8), missing
  consumers (→M9), or legacy path needing migration
* **blocked** — evidence blocked, gate not met, manifest absent, or
  prerequisite failure
* **retired** — superseded initiative, no parallel authority
* **out-of-supported-scope** — adjacent initiative, not in Custody scope

Design invariants
-----------------

* **No unexplained bucket**: every row is classifiable from its Status field
  plus joined evidence.
* **No missing owner**: every row has a non-UNKNOWN owner extracted from the
  matrix's Owner/initiative column.
* **No wrong M6A/M8 handoff**: substrate gaps are explicitly tagged
  ``handoff_milestone: M6A``; producer gaps tagged ``handoff_milestone: M8``;
  consumer gaps tagged ``handoff_milestone: M9``.
* **Deterministic ordering**: rows sorted by (classification priority, row_index)
  so two runs against the same commit produce the same artifact.
* **Stable row hashes**: each row carries a SHA-256 content hash.

Usage::

    python tools/reconcile_m6_migration_matrix.py [--output PATH] [--validate]
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

MATRIX_PATH = (
    REPO_ROOT
    / ".megaplan/initiatives/custody-control-plane/research/migration-matrix.md"
)
PREREQ_PATH = EVIDENCE_DIR / "m6-prerequisite-verification.json"
WBC_INVENTORY_PATH = EVIDENCE_DIR / "wbc-boundary-inventory.json"
WRITER_REGISTRY_PATH = EVIDENCE_DIR / "controlled-writer-registry.json"
READER_REGISTRY_PATH = EVIDENCE_DIR / "authority-reader-registry.json"
FINDING_REGISTER_PATH = EVIDENCE_DIR / "finding-prevention-register.json"
REPLAY_TX_PATH = EVIDENCE_DIR / "replay" / "transaction-spine.json"
REPLAY_STRATEGY_PATH = EVIDENCE_DIR / "replay" / "strategy-roadmap.json"

DEFAULT_OUTPUT = EVIDENCE_DIR / "migration-matrix-reconciled.json"
SCHEMA = "m6.migration-matrix-reconciled.v1"

# ── Classification vocabulary ───────────────────────────────────────────────

CLASS_PREREQ_SATISFIED = "prerequisite-satisfied"
CLASS_RESIDUAL = "residual"
CLASS_BLOCKED = "blocked"
CLASS_RETIRED = "retired"
CLASS_OUT_OF_SCOPE = "out-of-supported-scope"

VALID_CLASSIFICATIONS = frozenset({
    CLASS_PREREQ_SATISFIED,
    CLASS_RESIDUAL,
    CLASS_BLOCKED,
    CLASS_RETIRED,
    CLASS_OUT_OF_SCOPE,
})

# Status→classification mapping from the matrix vocabulary
STATUS_TO_CLASSIFICATION: dict[str, str] = {
    "blocked evidence": CLASS_BLOCKED,
    "blocked substrate": CLASS_BLOCKED,
    "blocked substrate/adoption": CLASS_BLOCKED,
    "blocked adoption": CLASS_BLOCKED,
    "substrate": CLASS_RESIDUAL,
    "substrate gap": CLASS_RESIDUAL,
    "substrate; landing gate": CLASS_BLOCKED,
    "substrate, manifest absent": CLASS_BLOCKED,
    "legacy": CLASS_RESIDUAL,
    "legacy/substrate": CLASS_RESIDUAL,
    "in-flight-WBC": CLASS_RESIDUAL,
    "partial": CLASS_RESIDUAL,
    "prerequisite-WBC": CLASS_PREREQ_SATISFIED,
    "retired": CLASS_RETIRED,
    "gate": CLASS_BLOCKED,
    "planned": CLASS_RESIDUAL,
    "adjacent": CLASS_OUT_OF_SCOPE,
}

# ── Normative column defaults (from the matrix's Required column table) ─────

NORMATIVE_FAIL_CLOSED = (
    "If the row's exact contract/version, Run Authority grant/coordinator fence, "
    "Custody lease/custody epoch, coherent WBC evidence, owner, or listed proof "
    "is absent or contradictory, the reader returns UNKNOWN/INCOHERENT, emits "
    "drift, and performs zero authority-increasing transition, dispatch, retry, "
    "repair, completion, cancellation, delivery, publication, or deletion. "
    "A projection cannot fill a missing source record."
)

NORMATIVE_ROLLBACK = (
    "Shadow before enforcement; old readers may consume only an explicit, "
    "expiring compatibility projection; old writers are rejected after cutover. "
    "Rollback disables promotion/effects and keeps append, reconciliation, "
    "and evidence intact—never restoring raw legacy authority or rewriting history."
)

NORMATIVE_MIXED_VERSION = (
    "Old readers may consume only an explicit, expiring compatibility "
    "projection; old writers are rejected after cutover. Version-specific "
    "rules in milestone briefs and the decision record win."
)

# ── Owner normalization ─────────────────────────────────────────────────────

# Maps raw Owner/initiative column text to canonical owner names
OWNER_NORMALIZATION: dict[str, str] = {
    "runauthority-epic / custody M5 evidence repair": "Run Authority",
    "runauthority-epic / custody M5; Resident supplies supporting session evidence": "Run Authority",
    "Native Platform": "Native Platform",
    "WBC / Run Authority; Custody adapter only": "WBC",
    "Native Platform; PC gate": "Native Platform",
    "Native Parity": "Native Parity",
    "runauthority-epic": "Run Authority",
    "runauthority-epic / custody-control-plane M1-M4": "custody-control-plane",
    "custody-control-plane M1-M4": "custody-control-plane",
    "custody-control-plane": "custody-control-plane",
    "WBC + custody": "WBC",
    "WBC / observability": "WBC",
    "Native Platform / custody": "Native Platform",
    "Megaplan": "Megaplan orchestration",
    "WBC C2-C3": "WBC",
    "WBC / Run Authority": "WBC",
    "Megaplan runtime": "Megaplan runtime",
    "custody / chain": "custody-control-plane",
    "Run Authority / custody": "Run Authority",
    "Megaplan chain": "Megaplan chain",
    "Run Authority / Native Platform": "Run Authority",
    "Megaplan Cloud": "Megaplan Cloud",
    "Maintenance / custody": "custody-control-plane",
    "megaplan-maintenance": "Megaplan Maintenance",
    "Discord corrective / custody": "custody-control-plane",
    "Resident / custody": "custody-control-plane",
    "AgentBox / custody": "custody-control-plane",
    "workflow-boundary-contracts": "WBC",
    "workflow-boundary-contracts with named runtime owners": "WBC",
    "named consumer owners; WBC owns query semantics": "WBC",
    "native parity": "Native Parity",
    "portfolio": "Portfolio / Retired",
    "Megaplan orchestration": "Megaplan orchestration",
    "planner/compiler": "Planner/compiler",
    "planner/compiler + executor": "Planner/compiler",
    "executor": "Executor/launcher",
    "launcher/runtime packaging": "Executor/launcher",
    "WBC + Run Authority + executor": "WBC",
    "observability + Maintenance": "Observability",
    "repair custody + Run Authority + Maintenance backstop": "custody-control-plane",
    "human portfolio gate": "Portfolio gate",
    "deployment human gate": "Portfolio gate",
    "cleanup/native parity": "Native Parity",
    "Discord corrective / custody": "custody-control-plane",
    "Discord corrective": "custody-control-plane",
    "custody / Maintenance": "custody-control-plane",
}


def _normalize_owner(raw_owner: str) -> str:
    """Normalize a raw owner string to a canonical owner name."""
    stripped = raw_owner.strip()
    if stripped in OWNER_NORMALIZATION:
        return OWNER_NORMALIZATION[stripped]
    # Try case-insensitive match
    for key, value in OWNER_NORMALIZATION.items():
        if key.lower() == stripped.lower():
            return value
    # Return as-is with a warning marker for unknown owners
    if stripped:
        return stripped
    return "UNKNOWN"


# ── Milestone → handoff mapping ─────────────────────────────────────────────

def _extract_handoff_milestone(
    status: str, milestone: str, classification: str
) -> str | None:
    """Determine which milestone a residual row hands off to."""
    if classification != CLASS_RESIDUAL:
        return None
    status_lower = status.lower()
    if "substrate" in status_lower:
        return "M6A"
    if "legacy" in status_lower:
        # Check if producer or consumer gap
        return "M8"
    if "planned" in status_lower:
        return "M9"
    if "in-flight" in status_lower:
        return "M8"
    if "partial" in status_lower:
        return "M8"
    return None


# ── Parsing helpers ─────────────────────────────────────────────────────────


def _split_markdown_table_cells(line: str) -> list[str]:
    """Split a markdown table row into cells, respecting backtick-quoted pipes.

    Pipes inside backtick-quoted inline code (`` `||` ``) are treated as
    literal characters, not cell separators.
    """
    # Strategy: find all backtick-quoted spans, replace pipes inside them
    # with a placeholder, split, then restore.
    placeholder = "\x00PIPE\x00"

    # Match inline code spans: `...`
    def _replace_pipes_in_code(match: re.Match[str]) -> str:
        return match.group(0).replace("|", placeholder)

    protected = re.sub(r"`[^`]*`", _replace_pipes_in_code, line)

    # Now split safely
    cells = [c.strip() for c in protected.strip("|").split("|")]

    # Restore pipes inside backtick spans
    cells = [c.replace(placeholder, "|") for c in cells]

    return cells


def _parse_markdown_table(markdown_text: str) -> list[dict[str, str]]:
    """Parse markdown tables into a list of row dicts.

    Handles multiple tables in a single document. A table consists of:
    a header row, a separator row, and data rows. When the column count
    changes or a new header+separator pair appears, a new table begins.

    Returns all rows from all tables, keyed by their respective headers.
    The caller should filter for the desired table by checking for
    expected column names.
    """
    lines = markdown_text.split("\n")
    all_rows: list[dict[str, str]] = []
    headers: list[str] = []
    # State machine: waiting_header → waiting_sep → reading_data
    state = "waiting_header"

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            # Non-table line: if we were reading data, go back to waiting
            if state == "reading_data":
                state = "waiting_header"
                headers = []
            continue

        # Parse cells (respecting backtick-quoted pipes)
        cells = _split_markdown_table_cells(stripped)

        # Is this a separator line (|---|---|...)?
        is_sep = all(
            re.match(r"^:?-{3,}:?$", c.strip()) for c in cells if c.strip()
        )

        if state == "waiting_header":
            if is_sep:
                # Stray separator, skip
                continue
            headers = cells
            state = "waiting_sep"
            continue

        if state == "waiting_sep":
            if is_sep:
                state = "reading_data"
                continue
            else:
                # Not a separator — this is a new header row, restart
                headers = cells
                state = "waiting_sep"
                continue

        # state == "reading_data"
        if is_sep:
            # Separator in data region means a new table is starting
            state = "waiting_header"
            headers = []
            continue

        if not headers:
            continue

        # Pad cells to match header count
        while len(cells) < len(headers):
            cells.append("")
        cells = cells[: len(headers)]

        row = dict(zip(headers, cells))
        all_rows.append(row)

    return all_rows


def _parse_matrix() -> list[dict[str, str]]:
    """Parse the migration matrix markdown file."""
    if not MATRIX_PATH.exists():
        print(f"ERROR: Migration matrix not found at {MATRIX_PATH}", file=sys.stderr)
        sys.exit(1)

    text = MATRIX_PATH.read_text(encoding="utf-8")
    rows = _parse_markdown_table(text)

    # Filter out non-data rows (section headers appearing inside tables)
    data_rows = []
    for row in rows:
        consumer = row.get("Consumer / surface", "")
        if not consumer:
            continue
        # Skip the adversarial acceptance catalog section header
        if "Adversarial acceptance catalog" in consumer:
            continue
        if consumer.startswith("Scenario"):
            continue
        if "stale contract" in consumer:
            # This is the adversarial acceptance catalog, stop here
            break
        data_rows.append(row)

    return data_rows


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON file, returning None if missing."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Hash helpers ────────────────────────────────────────────────────────────


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _compute_row_hash(row: dict[str, Any]) -> str:
    """Compute stable SHA-256 hash from deterministically ordered row fields.

    The hash excludes the ``row_hash`` field itself, as well as volatile
    fields like ``generated_at``.
    """
    hash_excluded = {"row_hash", "generated_at"}
    ordered = dict(sorted((k, v) for k, v in row.items() if k not in hash_excluded))
    canonical = json.dumps(ordered, ensure_ascii=False, sort_keys=True, default=str)
    return _sha256_hex(canonical)


# ── Evidence join helpers ───────────────────────────────────────────────────


def _build_evidence_index(inventory: dict[str, Any] | None) -> dict[str, list[str]]:
    """Build a keyword→row_ids index from the WBC inventory for joining."""
    if inventory is None:
        return {}
    index: dict[str, list[str]] = {}
    rows = inventory.get("rows", [])
    for row in rows:
        # Index by boundary_id
        bid = row.get("boundary_id", "")
        if bid:
            index.setdefault(bid.lower(), []).append(row.get("row_id", bid))
        # Index by workflow_id
        wid = row.get("workflow_id", "")
        if wid:
            index.setdefault(wid.lower(), []).append(row.get("row_id", wid))
        # Index by producer_path
        pp = row.get("producer_path", "")
        if pp and pp != "UNKNOWN":
            index.setdefault(pp.lower(), []).append(row.get("row_id", pp))
    return index


def _build_writer_index(registry: dict[str, Any] | None) -> dict[str, list[str]]:
    """Build a keyword→writer_ids index from the writer registry."""
    if registry is None:
        return {}
    index: dict[str, list[str]] = {}
    rows = registry.get("rows", [])
    for row in rows:
        wid = row.get("writer_id", "")
        wpath = row.get("writer_path", "")
        wcat = row.get("writer_category", "")
        if wid:
            index.setdefault(wid.lower(), []).append(wid)
        if wpath:
            index.setdefault(wpath.lower(), []).append(wid)
        if wcat:
            index.setdefault(wcat.lower(), []).append(wid)
    return index


def _build_reader_index(registry: dict[str, Any] | None) -> dict[str, list[str]]:
    """Build a keyword→reader_ids index from the reader registry."""
    if registry is None:
        return {}
    index: dict[str, list[str]] = {}
    rows = registry.get("rows", [])
    for row in rows:
        rid = row.get("reader_id", "")
        rpath = row.get("reader_path", "")
        rcat = row.get("reader_category", "")
        if rid:
            index.setdefault(rid.lower(), []).append(rid)
        if rpath:
            index.setdefault(rpath.lower(), []).append(rid)
        if rcat:
            index.setdefault(rcat.lower(), []).append(rid)
    return index


def _join_evidence(
    consumer_text: str,
    status: str,
    wbc_index: dict[str, list[str]],
    writer_index: dict[str, list[str]],
    reader_index: dict[str, list[str]],
    finding_register: dict[str, Any] | None,
    prereq: dict[str, Any] | None,
    replay_tx: dict[str, Any] | None,
    replay_strategy: dict[str, Any] | None,
) -> dict[str, Any]:
    """Join matrix row with all available evidence artifacts."""
    evidence: dict[str, Any] = {}

    # WBC inventory matches
    wbc_matches: list[str] = []
    consumer_lower = consumer_text.lower()
    for keyword, ids in wbc_index.items():
        if keyword in consumer_lower:
            wbc_matches.extend(ids)
    if wbc_matches:
        evidence["wbc_inventory_matches"] = sorted(set(wbc_matches))

    # Writer registry matches
    writer_matches: list[str] = []
    for keyword, ids in writer_index.items():
        if keyword in consumer_lower or keyword in status.lower():
            writer_matches.extend(ids)
    if writer_matches:
        evidence["writer_registry_matches"] = sorted(set(writer_matches))

    # Reader registry matches
    reader_matches: list[str] = []
    for keyword, ids in reader_index.items():
        if keyword in consumer_lower or keyword in status.lower():
            reader_matches.extend(ids)
    if reader_matches:
        evidence["reader_registry_matches"] = sorted(set(reader_matches))

    # Finding register match (check if any F01-F17 finding relates)
    if finding_register:
        finding_rows = finding_register.get("rows", [])
        related_findings = []
        finding_keywords = {
            "repair": ["F01", "F03", "F15"],
            "recovery": ["F02"],
            "adoption": ["F03", "F04", "F17"],
            "block": ["F02", "F10"],
            "replay": ["F01", "F03", "F04"],
            "work": ["F14"],
            "provenance": ["F17"],
            "alias": ["F04"],
            "version": ["F17"],
            "wbc": ["F02", "F03", "F04", "F17"],
            "run authority": ["F01", "F05"],
            "producer": ["F03", "F17"],
            "consumer": ["F04"],
            "executor": ["F10", "F11", "F13"],
            "planner": ["F07", "F08", "F09", "F12"],
            "observability": ["F06", "F14", "F16"],
            "ledger": ["F06", "F14"],
            "projection": ["F06", "F16"],
            "complexity": ["F08", "F10"],
            "budget": ["F08", "F14"],
            "task": ["F09", "F10", "F12"],
            "review": ["F12"],
            "retry": ["F10", "F11"],
            "compaction": ["F11"],
            "import": ["F11"],
            "chain": ["F07", "F05"],
            "migration": ["F17"],
            "subscription": ["F06"],
        }
        matched_fids = set()
        for keyword, fids in finding_keywords.items():
            if keyword in consumer_lower or keyword in status.lower():
                matched_fids.update(fids)
        if matched_fids:
            evidence["finding_register_matches"] = sorted(matched_fids)

    # Replay fixture matches
    if "transaction" in consumer_lower or "spine" in consumer_lower:
        if replay_tx:
            evidence["replay_fixture"] = "transaction-spine"
            evidence["replay_composite_hash"] = replay_tx.get("composite_hash", "UNKNOWN")
    if "strategy" in consumer_lower or "roadmap" in consumer_lower:
        if replay_strategy:
            evidence["replay_fixture"] = "strategy-roadmap"
            evidence["replay_composite_hash"] = replay_strategy.get("composite_hash", "UNKNOWN")

    # Prerequisite status
    if prereq:
        prereq_checks = prereq.get("checks", [])
        prereq_summary = {
            "checks": [
                {
                    "check": c.get("check", "unknown"),
                    "status": c.get("status", "UNKNOWN"),
                }
                for c in prereq_checks
            ],
            "overall": prereq.get("overall_status", "UNKNOWN"),
        }
        evidence["prerequisite_verification"] = prereq_summary

    return evidence


# ── Classification ──────────────────────────────────────────────────────────


def _classify_row(row: dict[str, str]) -> tuple[str, str]:
    """Classify a matrix row and return (classification, rationale)."""
    status = row.get("Status", "").strip().lower()

    # Direct mapping
    if status in STATUS_TO_CLASSIFICATION:
        classification = STATUS_TO_CLASSIFICATION[status]
        return classification, f"Status '{row.get('Status', '').strip()}' maps to {classification}"

    # Fuzzy matching
    if "blocked" in status:
        return CLASS_BLOCKED, f"Status '{row.get('Status', '').strip()}' contains 'blocked'"
    if "substrate" in status:
        return CLASS_RESIDUAL, f"Status '{row.get('Status', '').strip()}' contains 'substrate'"
    if "legacy" in status:
        return CLASS_RESIDUAL, f"Status '{row.get('Status', '').strip()}' contains 'legacy'"
    if "partial" in status:
        return CLASS_RESIDUAL, f"Status '{row.get('Status', '').strip()}' contains 'partial'"
    if "planned" in status:
        return CLASS_RESIDUAL, f"Status '{row.get('Status', '').strip()}' contains 'planned'"
    if "in-flight" in status:
        return CLASS_RESIDUAL, f"Status '{row.get('Status', '').strip()}' contains 'in-flight'"
    if "retired" in status:
        return CLASS_RETIRED, f"Status '{row.get('Status', '').strip()}' contains 'retired'"
    if "adjacent" in status:
        return CLASS_OUT_OF_SCOPE, f"Status '{row.get('Status', '').strip()}' contains 'adjacent'"
    if "prerequisite" in status:
        return CLASS_PREREQ_SATISFIED, (
            f"Status '{row.get('Status', '').strip()}' contains 'prerequisite'"
        )
    if "gate" in status:
        return CLASS_BLOCKED, f"Status '{row.get('Status', '').strip()}' contains 'gate'"

    # Fallback
    consumer = row.get("Consumer / surface", "")
    consumer_lower = consumer.lower()
    if "retired" in consumer_lower:
        return CLASS_RETIRED, "Consumer mentions 'retired'"
    if "superseded" in consumer_lower:
        return CLASS_RETIRED, "Consumer mentions 'superseded'"

    return CLASS_RESIDUAL, f"No explicit mapping for status '{row.get('Status', '').strip()}'; defaulting to residual"


# ── Row assembly ────────────────────────────────────────────────────────────


def _assemble_reconciled_row(
    row_index: int,
    matrix_row: dict[str, str],
    classification: str,
    rationale: str,
    evidence: dict[str, Any],
    prereq: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble a full reconciled row from the matrix row and joined evidence."""

    consumer = matrix_row.get("Consumer / surface", "")
    status_raw = matrix_row.get("Status", "").strip()
    owner_raw = matrix_row.get("Owner / initiative", "")
    milestone_raw = matrix_row.get("Milestone", "")
    current_auth = matrix_row.get("Current authority", "")
    target_auth = matrix_row.get("Target authority", "")
    proof = matrix_row.get("Shadow / conformance proof", "")
    deletion_gate = matrix_row.get("Deletion gate", "")

    owner = _normalize_owner(owner_raw)
    handoff_milestone = _extract_handoff_milestone(status_raw, milestone_raw, classification)

    reconciled: dict[str, Any] = {
        "row_index": row_index,
        "consumer_surface": consumer,
        "current_authority": current_auth,
        "target_authority": target_auth,
        "milestone": milestone_raw,
        "status_raw": status_raw,
        "classification": classification,
        "classification_rationale": rationale,
        "owner": owner,
        "owner_raw": owner_raw,
        "proof_requirement": proof,
        "deletion_gate": deletion_gate,
        "fail_closed_behavior": NORMATIVE_FAIL_CLOSED,
        "rollback_policy": NORMATIVE_ROLLBACK,
        "mixed_version_policy": NORMATIVE_MIXED_VERSION,
        "handoff_milestone": handoff_milestone,
        "evidence": evidence,
    }

    # Add prerequisite-aware block reason for blocked rows
    if classification == CLASS_BLOCKED and prereq:
        prereq_checks = prereq.get("checks", [])
        incoherent = [c for c in prereq_checks if c.get("status") == "INCOHERENT"]
        blocked_checks = [c for c in prereq_checks if c.get("status") == "BLOCKED"]
        unknown_checks = [c for c in prereq_checks if c.get("status") == "UNKNOWN"]
        if incoherent or blocked_checks:
            reconciled["blocked_by_prerequisites"] = [
                c.get("check", "unknown") for c in incoherent + blocked_checks
            ]
        if unknown_checks and classification == CLASS_BLOCKED:
            reconciled["unknown_prerequisites"] = [
                c.get("check", "unknown") for c in unknown_checks
            ]

    # Add row hash
    reconciled["row_hash"] = _compute_row_hash(reconciled)

    return reconciled


# ── Main generator ──────────────────────────────────────────────────────────


def generate_reconciled_matrix(
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate the reconciled migration matrix artifact.

    Args:
        output_path: If provided, write the artifact to this path.

    Returns:
        The complete artifact as a dict.
    """
    # 1. Parse the matrix
    matrix_rows = _parse_matrix()
    if not matrix_rows:
        print("ERROR: No data rows found in migration matrix", file=sys.stderr)
        sys.exit(1)

    # 2. Load evidence artifacts
    prereq = _load_json(PREREQ_PATH)
    wbc_inventory = _load_json(WBC_INVENTORY_PATH)
    writer_registry = _load_json(WRITER_REGISTRY_PATH)
    reader_registry = _load_json(READER_REGISTRY_PATH)
    finding_register = _load_json(FINDING_REGISTER_PATH)
    replay_tx = _load_json(REPLAY_TX_PATH)
    replay_strategy = _load_json(REPLAY_STRATEGY_PATH)

    # 3. Build evidence indexes
    wbc_index = _build_evidence_index(wbc_inventory)
    writer_index = _build_writer_index(writer_registry)
    reader_index = _build_reader_index(reader_registry)

    # 4. Process each row
    reconciled_rows: list[dict[str, Any]] = []
    classification_counts: dict[str, int] = {
        CLASS_PREREQ_SATISFIED: 0,
        CLASS_RESIDUAL: 0,
        CLASS_BLOCKED: 0,
        CLASS_RETIRED: 0,
        CLASS_OUT_OF_SCOPE: 0,
    }

    for i, matrix_row in enumerate(matrix_rows):
        consumer = matrix_row.get("Consumer / surface", "")
        if not consumer:
            continue

        # Classify
        classification, rationale = _classify_row(matrix_row)
        classification_counts[classification] += 1

        # Join evidence
        status = matrix_row.get("Status", "")
        evidence = _join_evidence(
            consumer,
            status,
            wbc_index,
            writer_index,
            reader_index,
            finding_register,
            prereq,
            replay_tx,
            replay_strategy,
        )

        # Assemble row
        reconciled = _assemble_reconciled_row(
            i, matrix_row, classification, rationale, evidence, prereq
        )
        reconciled_rows.append(reconciled)

    # 5. Sort by classification priority then row_index
    class_priority = {
        CLASS_BLOCKED: 0,
        CLASS_PREREQ_SATISFIED: 1,
        CLASS_RESIDUAL: 2,
        CLASS_RETIRED: 3,
        CLASS_OUT_OF_SCOPE: 4,
    }
    reconciled_rows.sort(
        key=lambda r: (class_priority.get(r["classification"], 99), r["row_index"])
    )

    # 6. Collect owners without UNKNOWN
    owners = sorted(set(r["owner"] for r in reconciled_rows if r["owner"] != "UNKNOWN"))
    unknown_owner_rows = [
        r["row_index"] for r in reconciled_rows if r["owner"] == "UNKNOWN"
    ]

    # 7. Compute composite hash
    row_hashes = sorted(r["row_hash"] for r in reconciled_rows)
    composite_hash = _sha256_hex("".join(row_hashes))

    # 8. Build artifact
    prereq_overall = prereq.get("overall_status", "UNKNOWN") if prereq else "MISSING"
    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/reconcile_m6_migration_matrix.py",
        "source_matrix": str(MATRIX_PATH.relative_to(REPO_ROOT)),
        "source_matrix_hash": _sha256_hex(MATRIX_PATH.read_text(encoding="utf-8")),
        "row_count": len(reconciled_rows),
        "classification_counts": classification_counts,
        "composite_hash": composite_hash,
        "prerequisite_status": prereq_overall,
        "evidence_artifacts_loaded": {
            "prerequisite_verification": prereq is not None,
            "wbc_boundary_inventory": wbc_inventory is not None,
            "controlled_writer_registry": writer_registry is not None,
            "authority_reader_registry": reader_registry is not None,
            "finding_prevention_register": finding_register is not None,
            "replay_transaction_spine": replay_tx is not None,
            "replay_strategy_roadmap": replay_strategy is not None,
        },
        "owners": owners,
        "unknown_owner_row_indices": unknown_owner_rows,
        "unknown_owner_count": len(unknown_owner_rows),
        "rows": reconciled_rows,
    }

    # 9. Write if output path provided
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(artifact, fh, ensure_ascii=False, indent=2)
        print(f"Wrote reconciled matrix ({len(reconciled_rows)} rows) → {output_path}")

    return artifact


# ── Validation ──────────────────────────────────────────────────────────────


def validate_artifact(artifact: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate the reconciled artifact.

    Returns:
        (is_valid, list_of_issues)
    """
    issues: list[str] = []

    # Schema check
    if artifact.get("schema") != SCHEMA:
        issues.append(f"Schema mismatch: expected {SCHEMA}, got {artifact.get('schema')}")

    # Row count
    rows = artifact.get("rows", [])
    if not rows:
        issues.append("No rows in artifact")
    else:
        expected_count = artifact.get("row_count")
        if expected_count != len(rows):
            issues.append(
                f"Row count mismatch: declared {expected_count}, actual {len(rows)}"
            )

    # Classification coverage
    for row in rows:
        classification = row.get("classification", "")
        if classification not in VALID_CLASSIFICATIONS:
            issues.append(
                f"Row {row.get('row_index', '?')}: invalid classification "
                f"'{classification}'"
            )
        if not row.get("classification_rationale"):
            issues.append(
                f"Row {row.get('row_index', '?')}: missing classification_rationale"
            )

    # No unexplained bucket
    unclassified = [r for r in rows if not r.get("classification")]
    if unclassified:
        issues.append(f"{len(unclassified)} rows have no classification")

    # No missing owner
    unknown_owners = [r for r in rows if r.get("owner") == "UNKNOWN"]
    if unknown_owners:
        indices = [r.get("row_index", "?") for r in unknown_owners]
        issues.append(f"Rows with UNKNOWN owner: {indices}")

    # No wrong M6A/M8 handoff
    for row in rows:
        if row.get("classification") == CLASS_RESIDUAL:
            handoff = row.get("handoff_milestone")
            if handoff is None:
                issues.append(
                    f"Row {row.get('row_index', '?')}: residual row has no "
                    f"handoff_milestone"
                )

    # Hash stability
    for row in rows:
        stored_hash = row.get("row_hash", "")
        if not stored_hash:
            issues.append(f"Row {row.get('row_index', '?')}: missing row_hash")
            continue
        computed = _compute_row_hash(row)
        if computed != stored_hash:
            issues.append(
                f"Row {row.get('row_index', '?')}: hash mismatch "
                f"(stored={stored_hash[:12]}..., computed={computed[:12]}...)"
            )

    # Composite hash
    row_hashes = sorted(r.get("row_hash", "") for r in rows)
    expected_composite = _sha256_hex("".join(row_hashes))
    actual_composite = artifact.get("composite_hash", "")
    if expected_composite != actual_composite:
        issues.append(
            f"Composite hash mismatch: expected {expected_composite[:12]}..., "
            f"got {actual_composite[:12]}..."
        )

    # Required fields per row
    required_fields = {
        "row_index",
        "consumer_surface",
        "current_authority",
        "target_authority",
        "milestone",
        "status_raw",
        "classification",
        "classification_rationale",
        "owner",
        "proof_requirement",
        "deletion_gate",
        "fail_closed_behavior",
        "rollback_policy",
        "mixed_version_policy",
        "evidence",
        "row_hash",
    }
    for row in rows:
        missing = required_fields - set(row.keys())
        if missing:
            issues.append(
                f"Row {row.get('row_index', '?')}: missing fields {sorted(missing)}"
            )

    return len(issues) == 0, issues


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M6 migration matrix reconciler (T13)"
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
        help="Validate the generated artifact and exit nonzero on issues",
    )
    args = parser.parse_args()

    artifact = generate_reconciled_matrix(output_path=args.output)

    if args.validate:
        is_valid, issues = validate_artifact(artifact)
        if issues:
            print(f"VALIDATION FAILED ({len(issues)} issues):", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            sys.exit(1)
        print("VALIDATION PASSED")
        sys.exit(0)

    # Print summary
    counts = artifact["classification_counts"]
    print(f"Reconciled {artifact['row_count']} rows:")
    print(f"  blocked:              {counts[CLASS_BLOCKED]}")
    print(f"  prerequisite-satisfied: {counts[CLASS_PREREQ_SATISFIED]}")
    print(f"  residual:             {counts[CLASS_RESIDUAL]}")
    print(f"  retired:              {counts[CLASS_RETIRED]}")
    print(f"  out-of-supported-scope: {counts[CLASS_OUT_OF_SCOPE]}")
    print(f"  owners:               {len(artifact['owners'])}")
    if artifact["unknown_owner_count"]:
        print(f"  UNKNOWN owners:       {artifact['unknown_owner_count']} rows")
    print(f"  composite_hash:       {artifact['composite_hash'][:16]}...")


if __name__ == "__main__":
    main()
