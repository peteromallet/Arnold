#!/usr/bin/env python3
"""M6 rollout/deletion register, work-ledger vocabulary, and proof index generator (T15).

Produces three evidence artifacts:

1. ``evidence/rollout-deletion-register.json`` — maps every F01-F17 finding and
   every rollout/promotion gate (8 gates from the unified authority research)
   into a structured register with owner, rollout gate, rollback behavior,
   deletion gate, and evidence references.  Unavailable denominators (SLO
   baselines, productive/replay fractions, measured p95) are preserved as
   ``UNKNOWN``, never ``0`` or success evidence.

2. ``evidence/work-ledger-vocabulary.json`` — defines the work tracking
   vocabulary: queue, session-start, inference, tool, validation, retry-wait,
   compaction, Git, transition, repair, verify, and replay time stages plus
   calls/tokens/dollars.  All baselines and measured denominators are
   ``UNKNOWN``; no field is defaulted to zero or labeled "success."

3. ``evidence/m6-proof-index.json`` — aggregates all M6 evidence artifacts
   produced so far with their SHA-256 content hashes, proof status
   (present/unavailable), schema versions, and explicit UNKNOWN baselines.

Design invariants
-----------------

* **Honest UNKNOWN accounting**: any denominator that is unavailable (SLO
  baselines, measured p95, productive/replay fractions, actual cost
  attribution, compaction time) is stored as the string ``"UNKNOWN"``, never
  as ``0`` or a success marker.
* **Named ownership**: every rollout/deletion row names a canonical owner
  derived from the finding register, migration matrix, or research document.
* **Deterministic ordering**: rows are sorted by identifier (finding_id for
  findings, gate index for promotion gates), producing stable content hashes
  across regeneration.
* **Rebuildable**: all data is derived from committed repo evidence (research
  document, finding register, migration matrix, prerequisite verification,
  WBC inventory, registries, replay fixtures, ownership decisions).
* **Observe-only**: reads git/files/import metadata and existing evidence;
  writes only the three artifact files.

Usage::

    python tools/generate_m6_rollout_register.py [--output-dir PATH] [--validate]
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
PC_SCOPE_PATH = EVIDENCE_DIR / "pc-scope-decision.json"
OWNERSHIP_PATH = EVIDENCE_DIR / "ownership-decision-record.json"
HISTORICAL_ADAPTERS_PATH = EVIDENCE_DIR / "wbc-historical-adapters.json"
DISCOVERY_RULES_PATH = EVIDENCE_DIR / "wbc-boundary-discovery-rules.yaml"
INVENTORY_VALIDATION_PATH = EVIDENCE_DIR / "wbc-boundary-inventory-validation.json"

# Research documents
AUTHORITY_RESEARCH_PATH = (
    REPO_ROOT
    / ".megaplan/initiatives/custody-control-plane/research"
    / "unified-authority-efficiency-prevention-20260714.md"
)

# Outputs
ROLLOUT_PATH = EVIDENCE_DIR / "rollout-deletion-register.json"
WORK_LEDGER_PATH = EVIDENCE_DIR / "work-ledger-vocabulary.json"
PROOF_INDEX_PATH = EVIDENCE_DIR / "m6-proof-index.json"

# Schemas
ROLLOUT_SCHEMA = "m6.rollout-deletion-register.v1"
WORK_LEDGER_SCHEMA = "m6.work-ledger-vocabulary.v1"
PROOF_INDEX_SCHEMA = "m6.proof-index.v1"

# ── Helpers ─────────────────────────────────────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file's contents."""
    if not path.exists():
        return "UNKNOWN"
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _compute_row_hash(row: dict[str, Any], exclude_keys: frozenset[str] = frozenset({"row_hash"})) -> str:
    """Compute stable SHA-256 hash for a row."""
    canonical = {k: row[k] for k in sorted(row) if k not in exclude_keys}
    return _sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False))


def _compute_composite_hash(rows: list[dict[str, Any]]) -> str:
    """Compute composite hash from sorted row hashes."""
    joined = "".join(sorted(r.get("row_hash", _compute_row_hash(r)) for r in rows))
    return _sha256(joined)


# ── Rollout/deletion register ───────────────────────────────────────────────


def _build_rollout_register(
    finding_register: dict[str, Any],
    research_text: str,
) -> dict[str, Any]:
    """Build the rollout/deletion register artifact.

    Contains:
    - F01-F17 finding rollout/deletion rows (extracted from finding register)
    - 8 promotion gate rows (from the unified authority research §Rollout and
      promotion gates)
    - Explicit UNKNOWN denominators for unavailable baselines
    """
    now = datetime.now(timezone.utc).isoformat()

    rows: list[dict[str, Any]] = []

    # ── F01-F17 rollout/deletion rows ────────────────────────────────────
    for finding in finding_register.get("rows", []):
        finding_id = finding["finding_id"]
        rows.append({
            "entry_id": finding_id,
            "entry_kind": "finding_rollout_deletion",
            "title": finding["title"],
            "canonical_owner": finding["canonical_owner"],
            "owner_control": finding.get("owner_control", ""),
            "rollout_gate": finding.get("rollout_gate", ""),
            "rollback_behavior": finding.get("rollback_behavior", ""),
            "deletion_gate": finding.get("deletion_gate", ""),
            "acceptance_proof_summary": finding.get("acceptance_proof", ""),
            "evidence_references": finding.get("evidence_references", []),
            "milestone_targets": _extract_milestones(finding.get("acceptance_proof", "")),
            "unavailable_denominators": {
                "measured_p95": "UNKNOWN",
                "productive_replay_baseline": "UNKNOWN",
                "cost_attribution": "UNKNOWN",
                "compaction_time": "UNKNOWN",
                "projection_io_latency": "UNKNOWN",
                "slo_baseline": "UNKNOWN",
            },
            "row_hash": "",
        })

    # ── 8 Promotion gate rows ────────────────────────────────────────────
    promotion_gates = _parse_promotion_gates(research_text)
    for pg in promotion_gates:
        rows.append({
            "entry_id": pg["gate_id"],
            "entry_kind": "promotion_gate",
            "title": pg["title"],
            "canonical_owner": pg["owner"],
            "owner_control": pg["control"],
            "rollout_gate": pg["description"],
            "rollback_behavior": pg["rollback"],
            "deletion_gate": pg["deletion"],
            "acceptance_proof_summary": pg["proof"],
            "evidence_references": [
                ".megaplan/initiatives/custody-control-plane/research/unified-authority-efficiency-prevention-20260714.md"
            ],
            "milestone_targets": pg.get("milestones", []),
            "unavailable_denominators": {
                "measured_p95": "UNKNOWN",
                "productive_replay_baseline": "UNKNOWN",
                "cost_attribution": "UNKNOWN",
                "compaction_time": "UNKNOWN",
                "projection_io_latency": "UNKNOWN",
                "slo_baseline": "UNKNOWN",
            },
            "row_hash": "",
        })

    # ── Global UNKNOWN baselines ─────────────────────────────────────────
    global_unknowns = {
        "productive_replay_token_cost": "UNKNOWN",
        "productive_replay_token_rationale": (
            "Productive-versus-replayed token/cost baselines are UNKNOWN "
            "until joined per-task/attempt/repair receipts exist. "
            "Current figures are conservative lower bounds, not SLO baselines. "
            "Source: unified-authority-efficiency-prevention-20260714.md §Explicit unknowns and non-goals."
        ),
        "compaction_time": "UNKNOWN",
        "compaction_time_rationale": (
            "Exact compaction time and the productive fraction of the "
            "50m20s Strategy GLM turn are UNKNOWN until M8A instrumentation exists. "
            "Source: unified-authority-efficiency-prevention-20260714.md §Explicit unknowns and non-goals."
        ),
        "projection_io_latency": "UNKNOWN",
        "projection_io_latency_rationale": (
            "Exact production latency caused by projection I/O is UNKNOWN "
            "until M9 timing and byte telemetry exists. The 137 GiB estimate "
            "demonstrates amplification, not a measured wall-time attribution. "
            "Source: unified-authority-efficiency-prevention-20260714.md §Explicit unknowns and non-goals."
        ),
        "initial_p95": "UNKNOWN",
        "initial_p95_rationale": (
            "Initial p95 and circuit thresholds are safety policies, not "
            "claims about mature cohort distributions. "
            "Source: unified-authority-efficiency-prevention-20260714.md §Explicit unknowns and non-goals."
        ),
        "productive_implementation_fraction": "UNKNOWN",
        "productive_implementation_fraction_rationale": (
            "Productive-implementation-versus-avoidable-overhead baselines "
            "are UNKNOWN until joined ledger coverage with exact task/batch/"
            "attempt/repair identities and stage decomposition exists. "
            "Source: F14 finding and M6 observe-only contract."
        ),
    }

    # Sort rows deterministically: finding rows first (F01-F17), then gate rows (G01-G08)
    def _sort_key(r: dict[str, Any]) -> tuple[int, str]:
        eid = r["entry_id"]
        if eid.startswith("F") and len(eid) >= 3:
            try:
                return (0, f"{int(eid[1:]):03d}")
            except ValueError:
                return (0, eid)
        elif eid.startswith("G"):
            try:
                return (1, f"{int(eid[1:]):03d}")
            except ValueError:
                return (1, eid)
        return (2, eid)

    rows.sort(key=_sort_key)

    # Compute row hashes
    for r in rows:
        r["row_hash"] = _compute_row_hash(r)

    composite_hash = _compute_composite_hash(rows)

    return {
        "schema": ROLLOUT_SCHEMA,
        "generated_at": now,
        "generator": "tools/generate_m6_rollout_register.py",
        "source_evidence": {
            "finding_prevention_register": str(FINDING_REGISTER_PATH),
            "unified_authority_research": str(AUTHORITY_RESEARCH_PATH),
        },
        "north_star_guard": (
            "Unavailable denominators (SLO baselines, measured p95, "
            "productive/replay fractions, cost attribution, compaction time, "
            "projection I/O latency) are preserved as UNKNOWN, never 0 or "
            "success evidence."
        ),
        "entry_count": len(rows),
        "finding_row_count": sum(1 for r in rows if r["entry_kind"] == "finding_rollout_deletion"),
        "promotion_gate_count": sum(1 for r in rows if r["entry_kind"] == "promotion_gate"),
        "rows": rows,
        "global_unknowns": global_unknowns,
        "composite_hash": composite_hash,
    }


def _extract_milestones(text: str) -> list[str]:
    """Extract milestone references (M5, M6, M7, M8, M8A, M9, M10, M11) from text."""
    milestones: list[str] = []
    seen: set[str] = set()
    for token in text.replace(",", " ").replace(";", " ").replace(".", " ").split():
        token = token.strip()
        if token in ("M5", "M6", "M6A", "M7", "M8", "M8A", "M9", "M10", "M11"):
            if token not in seen:
                milestones.append(token)
                seen.add(token)
    # Sort in milestone order
    milestone_order = {"M5": 0, "M6": 1, "M6A": 2, "M7": 3, "M8": 4, "M8A": 5, "M9": 6, "M10": 7, "M11": 8}
    milestones.sort(key=lambda m: milestone_order.get(m, 99))
    return milestones


def _parse_promotion_gates(research_text: str) -> list[dict[str, Any]]:
    """Parse the 8 rollout/promotion gates from the research document."""
    gates: list[dict[str, Any]] = []

    # Find the "## Rollout and promotion gates" section
    section_start = research_text.find("## Rollout and promotion gates")
    if section_start == -1:
        return gates

    section = research_text[section_start:]
    # Find the next section
    next_section = section.find("\n## ", len("## Rollout and promotion gates"))
    if next_section != -1:
        section = section[:next_section]

    # Parse numbered items (1. through 8.)
    # Each gate starts with "N. " followed by text until the next numbered item or section end
    import re
    gate_pattern = re.compile(
        r"(\d+)\.\s+(.+?)(?=\n\d+\.\s+|\nAt every stage|\n##|\Z)",
        re.DOTALL,
    )
    matches = gate_pattern.findall(section)

    # Gate owners derived from the research document
    gate_owner_map = {
        "G01": "Observability/projection",
        "G02": "Executor/launcher",
        "G03": "Observability/projection",
        "G04": "Planner/compiler",
        "G05": "TransitionWriter/repair custody",
        "G06": "WBC",
        "G07": "Run Authority",
        "G08": "WBC",
    }

    gate_control_map = {
        "G01": "Shadow append-only evidence and latency/work telemetry; mutation, enforcement, external effects, and deletion remain off.",
        "G02": "Replay captured Transaction Spine and Strategy Roadmap inputs; results must be deterministic by content hash, exercise each F01-F17 reason/control, and preserve the productive-versus-avoidable distinction.",
        "G03": "Idle projection canary: pinned installed runtime, no active mutation, 10,000-heartbeat/stress proof, valid monotonic concurrent reads, rebuild digest parity, zero false-stall or authority drift.",
        "G04": "Planner/executor canary: new plans only, feasibility warnings before reject, deterministic validation and bounded circuits, no rewriting existing plans.",
        "G05": "Repair/worker canary: one allowlisted synthetic or naturally occurring eligible blocker, exact signature/fence, one managed worker, verify-only adoption, terminal custody, independent 5m/1h/6h checkpoints.",
        "G06": "Controlled deployment: record source, installed package, wrapper, config, contract, and running process SHAs; promote cohorts only on zero authoritative divergence and within SLO/error budgets.",
        "G07": "Genuine blocked-run acceptance: deliberately use a real supported run and a genuine eligible blocker to prove durable event to accepted repair/escalation p95, resumed authoritative progress, independent verification, projection agreement, and no duplicate/replayed effect.",
        "G08": "Retirement: only after mixed-version and forced rollback proof, zero legacy authority readers/writers at static and runtime levels, approved deletion list, compatibility expiry, and content-addressed evidence.",
    }

    for i, match in enumerate(matches):
        num = int(match[0])
        full_text = match[1].strip()
        # Extract title (first sentence before colon, or first line)
        if ":" in full_text:
            colon_pos = full_text.index(":")
            title = full_text[:colon_pos].strip()
            description = full_text[colon_pos + 1:].strip()
        else:
            # Use first line as title
            first_line_end = full_text.find("\n")
            if first_line_end != -1:
                title = full_text[:first_line_end].strip()
                description = full_text[first_line_end:].strip()
            else:
                title = full_text
                description = full_text
        gate_id = f"G{num:02d}"

        gates.append({
            "gate_id": gate_id,
            "gate_number": num,
            "title": title,
            "owner": gate_owner_map.get(gate_id, "UNKNOWN"),
            "control": gate_control_map.get(gate_id, description),
            "description": description,
            "proof": description,
            "rollback": (
                "Kill switch disables promotion/effects, not evidence append, "
                "reconciliation, observation, or reporting. Rollback retains "
                "the new history and projections and cannot restore a legacy "
                "authority writer."
            ),
            "deletion": (
                "Only after mixed-version and forced rollback proof, zero "
                "legacy authority readers/writers at static and runtime levels, "
                "approved deletion list, compatibility expiry, and content-"
                "addressed evidence. Source: §Rollout and promotion gates, "
                "gate 8 (Retirement)."
            ),
            "milestones": _extract_milestones(description),
        })

    return gates


# ── Work-ledger vocabulary ──────────────────────────────────────────────────


def _build_work_ledger_vocabulary() -> dict[str, Any]:
    """Build the work-ledger vocabulary artifact.

    Defines all work tracking stages (queue, session-start, inference, tool,
    validation, retry-wait, compaction, Git, transition, repair, verify, replay)
    plus calls/tokens/dollars as defined in the unified authority research
    §F14 — productive and replayed time/tokens/cost.

    All baselines and measured denominators are UNKNOWN; no field is defaulted
    to zero or labeled "success."
    """
    now = datetime.now(timezone.utc).isoformat()

    stages = [
        {
            "stage_id": "queue",
            "label": "Queue time",
            "description": "Time spent waiting for a worker slot after admission.",
            "category": "overhead",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured queue time baselines are UNKNOWN until M8A instrumentation and joined ledger exist.",
        },
        {
            "stage_id": "session_start",
            "label": "Session-start time",
            "description": "Time spent on worker/session initialization, model loading, and import resolution.",
            "category": "overhead",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured session-start time baselines are UNKNOWN until M8A instrumentation exists.",
        },
        {
            "stage_id": "inference",
            "label": "Inference time",
            "description": "Time spent on model inference calls (prompt processing and token generation).",
            "category": "productive",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Productive-versus-replayed inference baselines are UNKNOWN until joined per-task/attempt/repair receipts exist.",
        },
        {
            "stage_id": "tool",
            "label": "Tool execution time",
            "description": "Time spent executing tool calls (shell, file operations, API calls).",
            "category": "productive",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured tool time baselines are UNKNOWN until M8A instrumentation exists.",
        },
        {
            "stage_id": "validation",
            "label": "Validation time",
            "description": "Time spent on deterministic harness validation jobs.",
            "category": "productive",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured validation time baselines are UNKNOWN until M8A instrumentation exists.",
        },
        {
            "stage_id": "retry_wait",
            "label": "Retry-wait time",
            "description": "Time spent waiting between retry attempts (backoff, provider cooldown).",
            "category": "overhead",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured retry-wait baselines are UNKNOWN until M8A circuit instrumentation exists.",
        },
        {
            "stage_id": "compaction",
            "label": "Compaction time",
            "description": "Time spent compacting conversation context for budget management.",
            "category": "overhead",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": (
                "Exact compaction time and the productive fraction of compaction "
                "are UNKNOWN until M8A instrumentation exists. "
                "Source: unified-authority-efficiency-prevention-20260714.md §Explicit unknowns."
            ),
        },
        {
            "stage_id": "git",
            "label": "Git operation time",
            "description": "Time spent on Git operations (commits, diffs, status checks).",
            "category": "overhead",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured Git operation baselines are UNKNOWN until M8A instrumentation exists.",
        },
        {
            "stage_id": "transition",
            "label": "Transition time",
            "description": "Time spent on lifecycle state transitions (plan/chain/task phase changes).",
            "category": "overhead",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured transition time baselines are UNKNOWN until M7 writer boundary instrumentation exists.",
        },
        {
            "stage_id": "repair",
            "label": "Repair time",
            "description": "Time spent on repair custody operations (dispatch, terminalization, verification).",
            "category": "productive",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured repair time baselines are UNKNOWN until M7/M10 custody instrumentation exists.",
        },
        {
            "stage_id": "verify",
            "label": "Verification time",
            "description": "Time spent on verify-only repair receipt adoption (checkpoint replay, test re-execution).",
            "category": "productive",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured verification time baselines are UNKNOWN until M8A verify-only adoption path exists.",
        },
        {
            "stage_id": "replay",
            "label": "Replay time",
            "description": "Time spent on deterministic replay of captured fixtures for proof generation.",
            "category": "productive",
            "unit": "seconds",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Measured replay time baselines are UNKNOWN; current captured fixtures are M6 observe-only baselines.",
        },
    ]

    # Sort stages deterministically
    stages.sort(key=lambda s: s["stage_id"])

    # Cost dimensions
    cost_dimensions = [
        {
            "dimension_id": "calls",
            "label": "Model calls",
            "description": "Number of model inference calls (prompt processing + generation).",
            "category": "productive",
            "unit": "count",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Productive-versus-replayed call count baselines are UNKNOWN until joined ledger exists.",
        },
        {
            "dimension_id": "tokens",
            "label": "Tokens",
            "description": "Number of input and output tokens consumed.",
            "category": "productive",
            "unit": "count",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Productive-versus-replayed token baselines are UNKNOWN until joined ledger exists.",
        },
        {
            "dimension_id": "dollars",
            "label": "Cost (USD)",
            "description": "Estimated cost in USD for model calls, provider usage, and infrastructure.",
            "category": "productive",
            "unit": "USD",
            "baseline": "UNKNOWN",
            "baseline_rationale": "Productive-versus-replayed cost baselines are UNKNOWN until joined per-task/attempt/repair receipts exist.",
        },
    ]

    cost_dimensions.sort(key=lambda c: c["dimension_id"])

    # Global UNKNOWN accounting
    global_unknowns = {
        "productive_implementation_fraction": "UNKNOWN",
        "productive_implementation_fraction_rationale": (
            "The fraction of total time/tokens/cost that is productive implementation "
            "(versus avoidable queue, replay, retry, compaction, validation, detection, "
            "and projection overhead) is UNKNOWN until joined per-task/attempt/repair "
            "receipts with stage decomposition exist. "
            "Source: F14 finding and unified-authority-efficiency-prevention-20260714.md §Explicit unknowns."
        ),
        "total_bytes_projected": "UNKNOWN",
        "total_bytes_projected_rationale": (
            "Total projection I/O bytes are UNKNOWN until M9 timing and byte "
            "telemetry exists. The 137 GiB estimate demonstrates amplification "
            "risk, not a measured value. "
            "Source: unified-authority-efficiency-prevention-20260714.md §Explicit unknowns."
        ),
        "slo_p95": "UNKNOWN",
        "slo_p95_rationale": (
            "Initial p95 and circuit thresholds are safety policies, not claims "
            "about mature cohort distributions. "
            "Source: unified-authority-efficiency-prevention-20260714.md §Explicit unknowns."
        ),
    }

    return {
        "schema": WORK_LEDGER_SCHEMA,
        "generated_at": now,
        "generator": "tools/generate_m6_rollout_register.py",
        "source_evidence": {
            "unified_authority_research": str(AUTHORITY_RESEARCH_PATH),
            "finding_F14": "Productive and replayed time/tokens/cost were not authoritative",
        },
        "north_star_guard": (
            "All baseline denominators are preserved as UNKNOWN. No field is "
            "defaulted to zero or labeled success evidence. Missing cost has "
            "an explicit reason. The prevention target is avoidable overhead, "
            "reported separately from productive implementation and necessary "
            "proof/review."
        ),
        "stage_count": len(stages),
        "cost_dimension_count": len(cost_dimensions),
        "stages": stages,
        "cost_dimensions": cost_dimensions,
        "global_unknowns": global_unknowns,
    }


# ── M6 proof index ──────────────────────────────────────────────────────────


def _build_proof_index() -> dict[str, Any]:
    """Build the M6 proof index artifact.

    Aggregates all M6 evidence artifacts with SHA-256 content hashes, proof
    status (present/unavailable), schema versions, and explicit UNKNOWN
    baselines.
    """
    now = datetime.now(timezone.utc).isoformat()

    artifact_paths = {
        "prerequisite_verification": PREREQ_PATH,
        "wbc_boundary_discovery_rules": DISCOVERY_RULES_PATH,
        "wbc_boundary_inventory": WBC_INVENTORY_PATH,
        "wbc_boundary_inventory_validation": INVENTORY_VALIDATION_PATH,
        "wbc_historical_adapters": HISTORICAL_ADAPTERS_PATH,
        "finding_prevention_register": FINDING_REGISTER_PATH,
        "controlled_writer_registry": WRITER_REGISTRY_PATH,
        "authority_reader_registry": READER_REGISTRY_PATH,
        "migration_matrix_reconciled": MIGRATION_MATRIX_PATH,
        "replay_transaction_spine": REPLAY_TX_PATH,
        "replay_strategy_roadmap": REPLAY_STRATEGY_PATH,
        "pc_scope_decision": PC_SCOPE_PATH,
        "ownership_decision_record": OWNERSHIP_PATH,
        "rollout_deletion_register": ROLLOUT_PATH,
        "work_ledger_vocabulary": WORK_LEDGER_PATH,
    }

    expected_schemas = {
        "prerequisite_verification": "m6.prerequisite-verification.v1",
        "wbc_boundary_discovery_rules": "m6.wbc-boundary-discovery-rules.v1",
        "wbc_boundary_inventory": "m6.wbc-boundary-inventory.v1",
        "wbc_boundary_inventory_validation": "m6.wbc-boundary-inventory-validation.v1",
        "wbc_historical_adapters": "m6.wbc-historical-adapters.v1",
        "finding_prevention_register": "m6.finding-prevention-register.v1",
        "controlled_writer_registry": "m6.controlled-writer-registry.v1",
        "authority_reader_registry": "m6.authority-reader-registry.v1",
        "migration_matrix_reconciled": "m6.migration-matrix-reconciled.v1",
        "replay_transaction_spine": "m6.transaction-spine-replay-fixture.v1",
        "replay_strategy_roadmap": "m6.strategy-roadmap-replay-fixture.v1",
        "pc_scope_decision": "m6.pc-scope-decision.v1",
        "ownership_decision_record": "m6.ownership-decision-record.v1",
        "rollout_deletion_register": ROLLOUT_SCHEMA,
        "work_ledger_vocabulary": WORK_LEDGER_SCHEMA,
    }

    entries: list[dict[str, Any]] = []
    for key, path in sorted(artifact_paths.items()):
        content_hash = _file_sha256(path)
        present = path.exists()

        # Try to extract composite_hash from JSON artifacts
        composite_hash = "UNKNOWN"
        row_count = "UNKNOWN"
        if present and path.suffix == ".json":
            try:
                data = _load_json(path)
                composite_hash = data.get("composite_hash", str(content_hash))
                row_count = data.get("row_count") or data.get("entry_count") or data.get("finding_count") or data.get("stage_count") or "UNKNOWN"
            except Exception:
                pass

        entries.append({
            "artifact_key": key,
            "path": str(path),
            "expected_schema": expected_schemas.get(key, "UNKNOWN"),
            "actual_schema": _get_actual_schema(path),
            "content_hash": content_hash,
            "composite_hash": composite_hash,
            "row_count": row_count,
            "present": present,
        })

    # Compute proof index composite
    present_count = sum(1 for e in entries if e["present"])
    total_count = len(entries)
    missing = [e["artifact_key"] for e in entries if not e["present"]]

    # Global UNKNOWN baselines
    global_unknowns = {
        "run_authority_m1_m3_accepted": "UNKNOWN",
        "run_authority_m1_m3_rationale": (
            "Run Authority M1-M3 completion receipts all have accepted: false. "
            "Source: migration matrix row 0, ownership-decision-record OWNERSHIP-BLOCKER-001."
        ),
        "m5_bound_head_coherent": "UNKNOWN",
        "m5_bound_head_rationale": (
            "M5 bound-head (8bb779d) does not match current HEAD. "
            "Prerequisite verification reports INCOHERENT. "
            "Source: evidence/m6-prerequisite-verification.json."
        ),
        "wbc_file_hashes_coherent": "UNKNOWN",
        "wbc_file_hashes_rationale": (
            "WBC file hash check reports INCOHERENT: one source file mismatch. "
            "Source: evidence/m6-prerequisite-verification.json."
        ),
        "portfolio_gate_approved": "UNKNOWN",
        "portfolio_gate_rationale": (
            "Portfolio gate PC scope decision is machine-generated with blocker PC-SCOPE-BLOCKER-001. "
            "Human approval is required but not recorded. "
            "Source: evidence/pc-scope-decision.json."
        ),
        "productive_replay_ledger_coverage": "UNKNOWN",
        "productive_replay_ledger_rationale": (
            "Productive-versus-replayed token/cost baselines are UNKNOWN "
            "until joined per-task/attempt/repair receipts exist. "
            "Source: F14 finding, work-ledger-vocabulary."
        ),
    }

    return {
        "schema": PROOF_INDEX_SCHEMA,
        "generated_at": now,
        "generator": "tools/generate_m6_rollout_register.py",
        "north_star_guard": (
            "M6 is observe-only. This proof index catalogs all M6 evidence "
            "artifacts with content hashes and proof status. Unavailable "
            "denominators and blocked prerequisites are recorded as UNKNOWN, "
            "never as success evidence or zero."
        ),
        "artifact_count": total_count,
        "present_count": present_count,
        "missing_count": len(missing),
        "missing_artifacts": missing,
        "entries": entries,
        "global_unknowns": global_unknowns,
    }


def _get_actual_schema(path: Path) -> str:
    """Extract schema field from a JSON artifact, or return UNKNOWN."""
    if not path.exists() or path.suffix != ".json":
        return "UNKNOWN"
    try:
        data = _load_json(path)
        return data.get("schema", "UNKNOWN")
    except Exception:
        return "UNKNOWN"


# ── Validation ──────────────────────────────────────────────────────────────


def _validate_rollout_register(rollout: dict[str, Any]) -> list[str]:
    """Validate the rollout/deletion register. Returns list of errors."""
    errors: list[str] = []

    if rollout.get("schema") != ROLLOUT_SCHEMA:
        errors.append(f"Schema mismatch: expected {ROLLOUT_SCHEMA}, got {rollout.get('schema')}")

    rows = rollout.get("rows", [])
    if not rows:
        errors.append("At least one row required")
        return errors

    # Must have at least 17 finding rows (F01-F17)
    finding_rows = [r for r in rows if r.get("entry_kind") == "finding_rollout_deletion"]
    finding_ids = {r["entry_id"] for r in finding_rows}
    expected_findings = {f"F{i:02d}" for i in range(1, 18)}
    missing_findings = expected_findings - finding_ids
    extra_findings = finding_ids - expected_findings
    if missing_findings:
        errors.append(f"Missing findings: {sorted(missing_findings)}")
    if extra_findings:
        errors.append(f"Unexpected finding IDs: {sorted(extra_findings)}")

    # Must have 8 promotion gate rows (G01-G08)
    gate_rows = [r for r in rows if r.get("entry_kind") == "promotion_gate"]
    gate_ids = {r["entry_id"] for r in gate_rows}
    expected_gates = {f"G{i:02d}" for i in range(1, 9)}
    missing_gates = expected_gates - gate_ids
    if missing_gates:
        errors.append(f"Missing promotion gates: {sorted(missing_gates)}")

    # Every row must have a non-empty owner and non-UNKNOWN owner
    for r in rows:
        owner = r.get("canonical_owner", "")
        if not owner or owner == "UNKNOWN":
            errors.append(f"Row {r.get('entry_id')} missing canonical_owner")
        # Every row must have a row_hash
        if not r.get("row_hash"):
            errors.append(f"Row {r.get('entry_id')} missing row_hash")
        # Every row must have unavailable_denominators that are all UNKNOWN
        ud = r.get("unavailable_denominators", {})
        for key, val in ud.items():
            if val != "UNKNOWN":
                errors.append(
                    f"Row {r.get('entry_id')} unavailable_denominators.{key} must be 'UNKNOWN', got '{val}'"
                )

    # Global unknowns must all be UNKNOWN
    global_unknowns = rollout.get("global_unknowns", {})
    for key, val in global_unknowns.items():
        if not key.endswith("_rationale") and val != "UNKNOWN":
            errors.append(
                f"global_unknowns.{key} must be 'UNKNOWN', got '{val}'"
            )

    # Verify composite hash
    if rows and rollout.get("composite_hash"):
        expected = _compute_composite_hash(rows)
        if expected != rollout["composite_hash"]:
            errors.append(f"Composite hash mismatch: expected {expected}, got {rollout['composite_hash']}")

    return errors


def _validate_work_ledger(work_ledger: dict[str, Any]) -> list[str]:
    """Validate the work-ledger vocabulary. Returns list of errors."""
    errors: list[str] = []

    if work_ledger.get("schema") != WORK_LEDGER_SCHEMA:
        errors.append(f"Schema mismatch: expected {WORK_LEDGER_SCHEMA}, got {work_ledger.get('schema')}")

    # All stages must have baseline=UNKNOWN
    stages = work_ledger.get("stages", [])
    stage_ids_seen: set[str] = set()
    for s in stages:
        sid = s.get("stage_id", "")
        if not sid:
            errors.append("Stage missing stage_id")
            continue
        if sid in stage_ids_seen:
            errors.append(f"Duplicate stage_id: {sid}")
        stage_ids_seen.add(sid)
        if s.get("baseline") != "UNKNOWN":
            errors.append(f"Stage {sid} baseline must be 'UNKNOWN', got '{s.get('baseline')}'")
        # Must have a baseline_rationale
        if not s.get("baseline_rationale"):
            errors.append(f"Stage {sid} missing baseline_rationale")

    # Required stages
    required_stages = {
        "queue", "session_start", "inference", "tool", "validation",
        "retry_wait", "compaction", "git", "transition", "repair", "verify", "replay",
    }
    missing_stages = required_stages - stage_ids_seen
    if missing_stages:
        errors.append(f"Missing required stages: {sorted(missing_stages)}")

    # Cost dimensions must have baseline=UNKNOWN
    cost_dims = work_ledger.get("cost_dimensions", [])
    dim_ids_seen: set[str] = set()
    for cd in cost_dims:
        did = cd.get("dimension_id", "")
        if not did:
            errors.append("Cost dimension missing dimension_id")
            continue
        if did in dim_ids_seen:
            errors.append(f"Duplicate dimension_id: {did}")
        dim_ids_seen.add(did)
        if cd.get("baseline") != "UNKNOWN":
            errors.append(f"Cost dimension {did} baseline must be 'UNKNOWN', got '{cd.get('baseline')}'")

    required_dims = {"calls", "tokens", "dollars"}
    missing_dims = required_dims - dim_ids_seen
    if missing_dims:
        errors.append(f"Missing required cost dimensions: {sorted(missing_dims)}")

    # Global unknowns must be UNKNOWN
    global_unknowns = work_ledger.get("global_unknowns", {})
    for key, val in global_unknowns.items():
        if not key.endswith("_rationale") and val != "UNKNOWN":
            errors.append(
                f"global_unknowns.{key} must be 'UNKNOWN', got '{val}'"
            )

    return errors


def _validate_proof_index(proof_index: dict[str, Any]) -> list[str]:
    """Validate the proof index. Returns list of errors."""
    errors: list[str] = []

    if proof_index.get("schema") != PROOF_INDEX_SCHEMA:
        errors.append(f"Schema mismatch: expected {PROOF_INDEX_SCHEMA}, got {proof_index.get('schema')}")

    entries = proof_index.get("entries", [])
    if not entries:
        errors.append("At least one proof index entry required")

    keys_seen: set[str] = set()
    for e in entries:
        key = e.get("artifact_key", "")
        if not key:
            errors.append("Entry missing artifact_key")
            continue
        if key in keys_seen:
            errors.append(f"Duplicate artifact_key: {key}")
        keys_seen.add(key)
        if not e.get("content_hash"):
            errors.append(f"Entry {key} missing content_hash")

    # Present/missing count must match
    present_count = sum(1 for e in entries if e["present"])
    missing_count = sum(1 for e in entries if not e["present"])
    if proof_index.get("present_count") != present_count:
        errors.append(f"present_count mismatch: {proof_index.get('present_count')} != {present_count}")
    if proof_index.get("missing_count") != missing_count:
        errors.append(f"missing_count mismatch: {proof_index.get('missing_count')} != {missing_count}")

    # Global unknowns must be UNKNOWN
    global_unknowns = proof_index.get("global_unknowns", {})
    for key, val in global_unknowns.items():
        if not key.endswith("_rationale") and val != "UNKNOWN":
            errors.append(
                f"global_unknowns.{key} must be 'UNKNOWN', got '{val}'"
            )

    return errors


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate M6 rollout/deletion register and work-ledger artifacts")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=EVIDENCE_DIR,
        help=f"Output directory (default: {EVIDENCE_DIR})",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated artifacts and exit non-zero on errors",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence_loaded: dict[str, bool] = {}
    errors: list[str] = []

    # Load finding register
    finding_register: dict[str, Any] = {}
    if FINDING_REGISTER_PATH.exists():
        finding_register = _load_json(FINDING_REGISTER_PATH)
        evidence_loaded["finding_prevention_register"] = True
    else:
        errors.append(f"Missing finding register: {FINDING_REGISTER_PATH}")
        evidence_loaded["finding_prevention_register"] = False

    # Load research text
    research_text = ""
    if AUTHORITY_RESEARCH_PATH.exists():
        research_text = _read_text(AUTHORITY_RESEARCH_PATH)
        evidence_loaded["unified_authority_research"] = True
    else:
        errors.append(f"Missing research document: {AUTHORITY_RESEARCH_PATH}")
        evidence_loaded["unified_authority_research"] = False

    # ── Build rollout/deletion register ─────────────────────────────────
    rollout = _build_rollout_register(finding_register, research_text)

    # ── Build work-ledger vocabulary ─────────────────────────────────────
    work_ledger = _build_work_ledger_vocabulary()

    # ── Build proof index ────────────────────────────────────────────────
    proof_index = _build_proof_index()

    # ── Emit artifacts ───────────────────────────────────────────────────
    rollout_output = output_dir / "rollout-deletion-register.json"
    with open(rollout_output, "w", encoding="utf-8") as fh:
        json.dump(rollout, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {rollout_output}")

    work_ledger_output = output_dir / "work-ledger-vocabulary.json"
    with open(work_ledger_output, "w", encoding="utf-8") as fh:
        json.dump(work_ledger, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {work_ledger_output}")

    proof_index_output = output_dir / "m6-proof-index.json"
    with open(proof_index_output, "w", encoding="utf-8") as fh:
        json.dump(proof_index, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {proof_index_output}")

    print(f"Evidence loaded: {json.dumps(evidence_loaded, indent=2)}")

    # ── Validate ─────────────────────────────────────────────────────────
    validation_errors: list[str] = []
    validation_errors.extend(_validate_rollout_register(rollout))
    validation_errors.extend(_validate_work_ledger(work_ledger))
    validation_errors.extend(_validate_proof_index(proof_index))

    if validation_errors:
        print(f"\nValidation errors ({len(validation_errors)}):")
        for err in validation_errors:
            print(f"  - {err}")

    if args.validate:
        if validation_errors or errors:
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
