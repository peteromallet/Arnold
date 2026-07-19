#!/usr/bin/env python3
"""M6 replay fixture generators (T8 — Transaction Spine, T9 — Strategy Roadmap).

Produces ``evidence/replay/transaction-spine.json`` and
``evidence/replay/strategy-roadmap.json`` from preserved handoff
documents, incident summaries, repair data, and initiative artifacts.

This generator is **strictly observe-only**: it reads committed source
files and writes only the replay fixture artifact. It does not mutate
lifecycle state, queues, providers, delivery, notifications, source
history, or runtime behavior.

Design invariants
-----------------

* **Deterministic ordering**: all lists are sorted so that two runs
  against the same commit always produce the same artifact.
* **Redacted paths**: absolute workspace paths (e.g.
  ``/workspace/agent-edit-verifiable-transaction-spine/…``) are
  replaced with redacted tokens so the fixture does not leak unstable
  workspace layout.
* **Original workspace limitation**: the original workspaces may no
  longer be available; this limitation is encoded explicitly in the
  fixture metadata.
* **Content-hash stability**: every top-level section carries a
  SHA-256 content hash.  The overall artifact also carries a
  deterministic composite hash.
* **UNKNOWN baselines**: compaction and productive-versus-replayed
  baselines are preserved as UNKNOWN when source data is unavailable.

Usage::

    python tools/generate_m6_replay_fixtures.py [--fixture {transaction-spine,strategy-roadmap}] [--output PATH]
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
REPLAY_DIR = EVIDENCE_DIR / "replay"

# Preserved handoff documents (committed under the repo)
HANDOFF_DIR = REPO_ROOT / ".megaplan" / "initiatives" / "megaplan-maintenance" / "handoff"
TRANSACTION_SPINE_HANDOFF = HANDOFF_DIR / "agent-edit-transaction-spine-retry-root-cause-20260714.md"
ACTIVE_EPICS_HANDOFF = HANDOFF_DIR / "active-epics-latency-synthesis-20260714.md"

# Incident ledger summaries
INCIDENT_SUMMARIES_DIR = (
    REPO_ROOT / ".megaplan" / "incident-ledger" / "summaries" / "incidents"
)
PROBLEM_SUMMARIES_DIR = (
    REPO_ROOT / ".megaplan" / "incident-ledger" / "summaries" / "problems"
)
INCIDENT_INDEX = REPO_ROOT / ".megaplan" / "incident-ledger" / "summaries" / "index.json"
INCIDENTS_LEDGER = REPO_ROOT / ".megaplan" / "incident-ledger" / "incidents.json"

# Output
DEFAULT_OUTPUT = REPLAY_DIR / "transaction-spine.json"
DEFAULT_STRATEGY_OUTPUT = REPLAY_DIR / "strategy-roadmap.json"

# Strategy Roadmap paths
STRATEGY_INITIATIVE_DIR = REPO_ROOT / ".megaplan" / "initiatives" / "repository-strategy-roadmap"
STRATEGY_CHAIN_YAML = STRATEGY_INITIATIVE_DIR / "chain.yaml"
STRATEGY_STRATEGY_MD = STRATEGY_INITIATIVE_DIR / "STRATEGY.md"
STRATEGY_NORTHSTAR_MD = STRATEGY_INITIATIVE_DIR / "NORTHSTAR.md"
STRATEGY_README_MD = STRATEGY_INITIATIVE_DIR / "README.md"
STRATEGY_INCIDENT_ID = "inc-repository-strategy-roadmap"
STRATEGY_SESSION_ID = "repository-strategy-roadmap"
STRATEGY_PROBLEM_ID = "problem-72f87afd3954"

# Redaction pattern: matches /workspace/ prefixes and their descendants.
# Uses a non-greedy character class that captures typical path characters
# plus markdown/brace punctuation so that paths inside backticks, braces,
# and shell globs are also redacted.
_WORKSPACE_PATH_RE = re.compile(r"/workspace/[a-zA-Z0-9_./{}\-]+")

# ── Helpers ─────────────────────────────────────────────────────────────────


def _sha256_hex(data: str) -> str:
    """Return SHA-256 hex digest of *data*."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _redact_paths(text: str) -> str:
    """Replace absolute workspace paths with redacted tokens.

    Preserves the directory depth but replaces each path segment beyond
    ``/workspace/`` with a stable hash-based token so the structure is
    recognizable but no actual path leaks.
    """
    def _replace(m: re.Match) -> str:
        full = m.group(0)
        # Keep /workspace/ prefix, hash the rest
        suffix = full[len("/workspace/"):]
        suffix_hash = _sha256_hex(suffix)[:12]
        return f"/workspace/[REDACTED:{suffix_hash}]"

    return _WORKSPACE_PATH_RE.sub(_replace, text)


def _load_json(path: Path) -> dict[str, Any] | list[Any]:
    """Load and return JSON from *path*."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_text_safe(path: Path) -> str | None:
    """Read text from *path*, returning None if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None


def _hash_dict(d: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 of a JSON-serializable dict."""
    raw = json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)
    return _sha256_hex(raw)


# ── Data collectors ─────────────────────────────────────────────────────────


def _collect_handoff_documents() -> dict[str, Any]:
    """Collect preserved handoff documents with redacted content."""
    handoffs: list[dict[str, Any]] = []

    for handoff_path, handoff_kind in [
        (TRANSACTION_SPINE_HANDOFF, "agent-edit-transaction-spine-retry-root-cause"),
        (ACTIVE_EPICS_HANDOFF, "active-epics-latency-synthesis"),
    ]:
        raw = _read_text_safe(handoff_path)
        if raw is None:
            handoffs.append({
                "kind": handoff_kind,
                "path": str(handoff_path.relative_to(REPO_ROOT)),
                "status": "missing",
                "content_sha256": None,
                "redacted_content_preview": None,
            })
            continue

        redacted = _redact_paths(raw)
        handoffs.append({
            "kind": handoff_kind,
            "path": str(handoff_path.relative_to(REPO_ROOT)),
            "status": "present",
            "content_sha256": _sha256_hex(redacted),
            "redacted_content_preview": redacted[:2000],
            "line_count": len(raw.splitlines()),
            "char_count": len(raw),
        })

    return {
        "schema": "m6.transaction-spine.handoff-documents.v1",
        "source_directory": str(HANDOFF_DIR.relative_to(REPO_ROOT)),
        "documents": sorted(handoffs, key=lambda h: h["kind"]),
        "content_hash": _hash_dict({"documents": handoffs}),
    }


def _collect_incident_summaries() -> dict[str, Any]:
    """Collect incident summaries with redacted paths."""
    summaries: list[dict[str, Any]] = []

    # Read the index for the list of incidents
    index_data = _load_json(INCIDENT_INDEX) if INCIDENT_INDEX.exists() else {}

    for inc_entry in index_data.get("incidents", []):
        inc_id = inc_entry.get("incident_id", "unknown")
        inc_path = REPO_ROOT / inc_entry.get("path", "")
        if not inc_path.exists():
            summaries.append({
                "incident_id": inc_id,
                "status": "missing",
                "content_sha256": None,
            })
            continue

        try:
            raw_data = _load_json(inc_path)
        except (json.JSONDecodeError, OSError):
            summaries.append({
                "incident_id": inc_id,
                "status": "unparseable",
                "content_sha256": None,
            })
            continue

        # Redact paths in the summary
        redacted_raw = _redact_paths(json.dumps(raw_data, sort_keys=True, default=str))
        summaries.append({
            "incident_id": inc_id,
            "status": "present",
            "content_sha256": _sha256_hex(redacted_raw),
            "state": raw_data.get("state", "unknown"),
            "outcome": raw_data.get("outcome", "unknown"),
            "latest_actor": raw_data.get("latest_actor", "unknown"),
            "problem_ids": raw_data.get("problem_ids", []),
            "schema_version": raw_data.get("schema_version"),
        })

    # Also collect problem summaries
    problems: list[dict[str, Any]] = []
    for prob_entry in index_data.get("problems", []):
        prob_id = prob_entry.get("problem_id", "unknown")
        prob_path = REPO_ROOT / prob_entry.get("path", "")
        if not prob_path.exists():
            problems.append({
                "problem_id": prob_id,
                "status": "missing",
            })
            continue

        try:
            raw_data = _load_json(prob_path)
        except (json.JSONDecodeError, OSError):
            problems.append({
                "problem_id": prob_id,
                "status": "unparseable",
            })
            continue

        problems.append({
            "problem_id": prob_id,
            "status": "present",
            "status_field": raw_data.get("status", "unknown"),
            "linked_incident_ids": raw_data.get("linked_incident_ids", []),
            "recurred_after_fix": raw_data.get("recurred_after_fix"),
            "occurrence_count": raw_data.get("occurrence_count"),
        })

    return {
        "schema": "m6.transaction-spine.incident-summaries.v1",
        "source_directory": str(INCIDENT_SUMMARIES_DIR.relative_to(REPO_ROOT)),
        "incident_count": len(summaries),
        "incidents": sorted(summaries, key=lambda s: s["incident_id"]),
        "problem_count": len(problems),
        "problems": sorted(problems, key=lambda p: p["problem_id"]),
        "content_hash": _hash_dict({"incidents": summaries, "problems": problems}),
    }


def _collect_repair_data() -> dict[str, Any]:
    """Collect repair data from the incidents ledger with redacted paths."""
    if not INCIDENTS_LEDGER.exists():
        return {
            "schema": "m6.transaction-spine.repair-data.v1",
            "status": "missing",
            "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
            "content_hash": None,
        }

    try:
        raw = INCIDENTS_LEDGER.read_text(encoding="utf-8")
    except OSError:
        return {
            "schema": "m6.transaction-spine.repair-data.v1",
            "status": "unreadable",
            "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
            "content_hash": None,
        }

    redacted = _redact_paths(raw)
    content_hash = _sha256_hex(redacted)

    # Parse the incidents ledger to extract structured repair info
    try:
        ledger = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "schema": "m6.transaction-spine.repair-data.v1",
            "status": "unparseable",
            "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
            "content_hash": content_hash,
        }

    incidents_list = ledger.get("incidents", [])
    repair_summaries: list[dict[str, Any]] = []
    for inc in incidents_list:
        session_id = inc.get("events", [{}])[0].get("session_id", "unknown") if inc.get("events") else "unknown"
        event_count = inc.get("event_count", 0)
        decisions = inc.get("decisions", [])

        # Collect decision hypotheses (truncated for fixture size)
        decision_summaries: list[dict[str, Any]] = []
        for d in decisions:
            dec = d.get("decision", {})
            hypothesis = dec.get("hypothesis", "")
            if hypothesis:
                # Truncate long hypotheses
                hypothesis_preview = hypothesis[:200]
            else:
                hypothesis_preview = None
            decision_summaries.append({
                "seq": d.get("seq"),
                "hypothesis_class": hypothesis.split("\n")[0] if hypothesis else None,
                "hypothesis_preview": hypothesis_preview,
                "reconciler_finding_count": len(dec.get("reconciler_findings", [])),
            })

        repair_summaries.append({
            "session_id": session_id,
            "event_count": event_count,
            "decision_count": len(decisions),
            "decisions": decision_summaries,
        })

    return {
        "schema": "m6.transaction-spine.repair-data.v1",
        "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
        "status": "present",
        "content_hash": content_hash,
        "total_incidents": len(incidents_list),
        "incident_summaries": sorted(repair_summaries, key=lambda s: s["session_id"]),
        "redacted": True,
    }


# ── Main generator ──────────────────────────────────────────────────────────


def generate_transaction_spine(output_path: Path | None = None) -> dict[str, Any]:
    """Generate the Transaction Spine replay fixture.

    Returns the full fixture dict; also writes it to *output_path* if given.
    """
    now = datetime.now(timezone.utc).isoformat()

    handoff_data = _collect_handoff_documents()
    incident_data = _collect_incident_summaries()
    repair_data = _collect_repair_data()

    # Build the top-level sections
    sections: dict[str, Any] = {
        "handoff_documents": handoff_data,
        "incident_summaries": incident_data,
        "repair_data": repair_data,
    }

    # Compute per-section content hashes (already embedded above; compute
    # overall composite for the artifact envelope)
    section_hashes = {
        key: _hash_dict(val) for key, val in sections.items()
    }

    # Composite hash: hash of the sorted section hashes
    composite_payload = json.dumps(
        dict(sorted(section_hashes.items())),
        sort_keys=True,
        ensure_ascii=False,
    )
    composite_hash = _sha256_hex(composite_payload)

    # Redact the repository root to avoid leaking the concrete checkout path.
    # The relative structure is preserved in the source_directory fields.
    redacted_root = _redact_paths(str(REPO_ROOT))

    fixture: dict[str, Any] = {
        "schema": "m6.transaction-spine-replay-fixture.v1",
        "generated_at": now,
        "generator": "tools/generate_m6_replay_fixtures.py",
        "repository_root": redacted_root,
        "composite_hash": composite_hash,
        "section_hashes": section_hashes,
        "limitations": {
            "missing_original_workspace": {
                "description": (
                    "The original Transaction Spine workspace "
                    "(/workspace/agent-edit-verifiable-transaction-spine/) "
                    "is not available in this checkout. Preserved handoff "
                    "documents, incident summaries, and repair data from the "
                    "committed incident ledger serve as the best available "
                    "evidence. Live plan state, chain logs, and raw repair "
                    "artifacts from the original workspace cannot be "
                    "independently verified from this fixture."
                ),
                "severity": "limitation",
                "mitigations": [
                    "Handoff documents are committed under .megaplan/initiatives/",
                    "Incident summaries are regenerated from the committed ledger",
                    "Repair data redacts unstable workspace paths",
                ],
            },
            "path_redaction": {
                "description": (
                    "All absolute /workspace/ paths have been redacted with "
                    "stable content-hash tokens to prevent leakage of unstable "
                    "workspace layout while preserving structural comparison."
                ),
                "pattern": "/workspace/[REDACTED:<sha256-prefix>]",
                "applied_to": [
                    "handoff_documents",
                    "incident_summaries",
                    "repair_data",
                ],
            },
        },
        "sections": sections,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(fixture, fh, indent=2, ensure_ascii=False, sort_keys=True)
        print(f"Transaction Spine replay fixture written to {output_path}", file=sys.stderr)

    return fixture


# ── Strategy Roadmap data collectors ─────────────────────────────────────────


def _collect_strategy_initiative_artifacts() -> dict[str, Any]:
    """Collect committed initiative artifacts for the Strategy Roadmap."""
    artifacts: list[dict[str, Any]] = []

    for art_path, art_kind in [
        (STRATEGY_CHAIN_YAML, "chain_yaml"),
        (STRATEGY_STRATEGY_MD, "strategy_md"),
        (STRATEGY_NORTHSTAR_MD, "northstar_md"),
        (STRATEGY_README_MD, "readme_md"),
    ]:
        raw = _read_text_safe(art_path)
        if raw is None:
            artifacts.append({
                "kind": art_kind,
                "path": str(art_path.relative_to(REPO_ROOT)),
                "status": "missing",
                "content_sha256": None,
                "line_count": None,
            })
            continue

        redacted = _redact_paths(raw)
        artifacts.append({
            "kind": art_kind,
            "path": str(art_path.relative_to(REPO_ROOT)),
            "status": "present",
            "content_sha256": _sha256_hex(redacted),
            "line_count": len(raw.splitlines()),
            "char_count": len(raw),
            "redacted_content_preview": redacted[:2000],
        })

    return {
        "schema": "m6.strategy-roadmap.initiative-artifacts.v1",
        "source_directory": str(STRATEGY_INITIATIVE_DIR.relative_to(REPO_ROOT)),
        "artifacts": sorted(artifacts, key=lambda a: a["kind"]),
        "content_hash": _hash_dict({"artifacts": artifacts}),
    }


def _collect_strategy_handoff_context() -> dict[str, Any]:
    """Collect handoff context relevant to Strategy Roadmap.

    Unlike Transaction Spine, Strategy Roadmap does not have a dedicated
    handoff document.  The active-epics-latency-synthesis document covers
    both Transaction Spine and Strategy Roadmap, so we extract the
    Strategy-specific portions from it.
    """
    # The active-epics-latency-synthesis covers both epics
    synthesis_raw = _read_text_safe(ACTIVE_EPICS_HANDOFF)
    if synthesis_raw is None:
        return {
            "schema": "m6.strategy-roadmap.handoff-context.v1",
            "status": "missing",
            "source_path": str(ACTIVE_EPICS_HANDOFF.relative_to(REPO_ROOT)),
            "content_hash": None,
        }

    redacted = _redact_paths(synthesis_raw)

    # Extract Strategy-specific sections from the synthesis
    lines = redacted.splitlines()
    strategy_lines: list[str] = []
    in_strategy_section = False
    for line in lines:
        if "Strategy Roadmap" in line or "Strategy M4" in line or "Strategy compaction" in line:
            in_strategy_section = True
        if in_strategy_section:
            strategy_lines.append(line)
        # Also capture sections that name Strategy explicitly
        if "strategy" in line.lower() and "roadmap" in line.lower():
            if not in_strategy_section:
                in_strategy_section = True
                strategy_lines.append(line)

    strategy_excerpt = "\n".join(strategy_lines) if strategy_lines else redacted[:3000]

    return {
        "schema": "m6.strategy-roadmap.handoff-context.v1",
        "source_path": str(ACTIVE_EPICS_HANDOFF.relative_to(REPO_ROOT)),
        "status": "present",
        "content_sha256": _sha256_hex(redacted),
        "full_line_count": len(lines),
        "full_char_count": len(redacted),
        "strategy_excerpt_line_count": len(strategy_lines),
        "strategy_excerpt_preview": strategy_excerpt[:2000],
        "note": (
            "Strategy Roadmap does not have a dedicated handoff document. "
            "Context is extracted from the joint active-epics-latency-synthesis "
            "which covers both Transaction Spine and Strategy Roadmap epics."
        ),
    }


def _collect_strategy_incident_data() -> dict[str, Any]:
    """Collect incident summary for the Strategy Roadmap incident."""
    inc_path = INCIDENT_SUMMARIES_DIR / f"{STRATEGY_INCIDENT_ID}.json"
    prob_path = PROBLEM_SUMMARIES_DIR / f"{STRATEGY_PROBLEM_ID}.json"

    incident_data: dict[str, Any] = {"status": "missing"}
    if inc_path.exists():
        try:
            raw = _load_json(inc_path)
            redacted_raw = _redact_paths(json.dumps(raw, sort_keys=True, default=str))
            incident_data = {
                "incident_id": STRATEGY_INCIDENT_ID,
                "status": "present",
                "content_sha256": _sha256_hex(redacted_raw),
                "state": raw.get("state", "unknown"),
                "outcome": raw.get("outcome", "unknown"),
                "latest_actor": raw.get("latest_actor", "unknown"),
                "problem_ids": raw.get("problem_ids", []),
                "schema_version": raw.get("schema_version"),
            }
        except (json.JSONDecodeError, OSError):
            incident_data = {
                "incident_id": STRATEGY_INCIDENT_ID,
                "status": "unparseable",
            }

    problem_data: dict[str, Any] = {"status": "missing"}
    if prob_path.exists():
        try:
            raw = _load_json(prob_path)
            problem_data = {
                "problem_id": STRATEGY_PROBLEM_ID,
                "status": "present",
                "status_field": raw.get("status", "unknown"),
                "occurrence_count": raw.get("occurrence_count"),
                "recurred_after_fix": raw.get("recurred_after_fix"),
                "linked_incident_ids": raw.get("linked_incident_ids", []),
                "owner_actor": raw.get("owner_actor"),
                "fix_commits": raw.get("fix_commits", []),
            }
        except (json.JSONDecodeError, OSError):
            problem_data = {
                "problem_id": STRATEGY_PROBLEM_ID,
                "status": "unparseable",
            }

    return {
        "schema": "m6.strategy-roadmap.incident-data.v1",
        "incident": incident_data,
        "problem": problem_data,
        "content_hash": _hash_dict({"incident": incident_data, "problem": problem_data}),
    }


def _collect_strategy_repair_data() -> dict[str, Any]:
    """Collect repair data from incidents.json filtered for Strategy Roadmap session."""
    if not INCIDENTS_LEDGER.exists():
        return {
            "schema": "m6.strategy-roadmap.repair-data.v1",
            "status": "missing",
            "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
            "content_hash": None,
        }

    try:
        raw = INCIDENTS_LEDGER.read_text(encoding="utf-8")
    except OSError:
        return {
            "schema": "m6.strategy-roadmap.repair-data.v1",
            "status": "unreadable",
            "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
            "content_hash": None,
        }

    redacted = _redact_paths(raw)
    content_hash = _sha256_hex(redacted)

    try:
        ledger = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "schema": "m6.strategy-roadmap.repair-data.v1",
            "status": "unparseable",
            "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
            "content_hash": content_hash,
        }

    # Filter incidents for the strategy-roadmap session
    incidents_list = ledger.get("incidents", [])
    strategy_repairs: list[dict[str, Any]] = []

    for inc in incidents_list:
        session_id = (
            inc.get("events", [{}])[0].get("session_id", "unknown")
            if inc.get("events")
            else "unknown"
        )
        if session_id != STRATEGY_SESSION_ID:
            continue

        event_count = inc.get("event_count", 0)
        decisions = inc.get("decisions", [])

        decision_summaries: list[dict[str, Any]] = []
        for d in decisions:
            dec = d.get("decision", {})
            hypothesis = dec.get("hypothesis", "")
            hypothesis_preview = hypothesis[:200] if hypothesis else None
            decision_summaries.append({
                "seq": d.get("seq"),
                "hypothesis_class": hypothesis.split("\n")[0] if hypothesis else None,
                "hypothesis_preview": hypothesis_preview,
                "reconciler_finding_count": len(dec.get("reconciler_findings", [])),
            })

        strategy_repairs.append({
            "session_id": session_id,
            "event_count": event_count,
            "decision_count": len(decisions),
            "decisions": decision_summaries,
        })

    return {
        "schema": "m6.strategy-roadmap.repair-data.v1",
        "source_path": str(INCIDENTS_LEDGER.relative_to(REPO_ROOT)),
        "status": "present",
        "content_hash": content_hash,
        "total_incidents": len(incidents_list),
        "strategy_roadmap_incident_count": len(strategy_repairs),
        "incident_summaries": sorted(strategy_repairs, key=lambda s: s["session_id"]),
        "redacted": True,
    }


def _collect_strategy_compaction_baseline() -> dict[str, Any]:
    """Return the compaction baseline — UNKNOWN for Strategy Roadmap.

    The handoff document notes: "Strategy compaction/import churn and
    the productive fraction of the 50-minute GLM turn are not separately
    timed."  Without the original workspace or a per-task cost ledger,
    compaction and productive-versus-replayed baselines cannot be measured.
    """
    return {
        "schema": "m6.strategy-roadmap.compaction-baseline.v1",
        "status": "UNKNOWN",
        "reason": (
            "The active-epics-latency-synthesis handoff explicitly states that "
            "Strategy compaction/import churn and the productive fraction of "
            "the 50-minute GLM turn are not separately timed. Per-task cost "
            "ledgers and the original workspace are unavailable, so compaction "
            "and productive-versus-replayed baselines cannot be measured."
        ),
        "evidence_reference": (
            "See .megaplan/initiatives/megaplan-maintenance/handoff/"
            "active-epics-latency-synthesis-20260714.md, lines 78-80: "
            "'Strategy compaction/import churn and the productive fraction of "
            "the 50-minute GLM turn are not separately timed.'"
        ),
        "compaction_baseline": "UNKNOWN",
        "productive_versus_replayed_baseline": "UNKNOWN",
    }


# ── Strategy Roadmap generator ──────────────────────────────────────────────


def generate_strategy_roadmap(output_path: Path | None = None) -> dict[str, Any]:
    """Generate the Strategy Roadmap replay fixture.

    Returns the full fixture dict; also writes it to *output_path* if given.
    """
    now = datetime.now(timezone.utc).isoformat()

    initiative_data = _collect_strategy_initiative_artifacts()
    handoff_context = _collect_strategy_handoff_context()
    incident_data = _collect_strategy_incident_data()
    repair_data = _collect_strategy_repair_data()
    compaction_baseline = _collect_strategy_compaction_baseline()

    sections: dict[str, Any] = {
        "initiative_artifacts": initiative_data,
        "handoff_context": handoff_context,
        "incident_data": incident_data,
        "repair_data": repair_data,
        "compaction_baseline": compaction_baseline,
    }

    section_hashes = {
        key: _hash_dict(val) for key, val in sections.items()
    }

    composite_payload = json.dumps(
        dict(sorted(section_hashes.items())),
        sort_keys=True,
        ensure_ascii=False,
    )
    composite_hash = _sha256_hex(composite_payload)

    redacted_root = _redact_paths(str(REPO_ROOT))

    fixture: dict[str, Any] = {
        "schema": "m6.strategy-roadmap-replay-fixture.v1",
        "generated_at": now,
        "generator": "tools/generate_m6_replay_fixtures.py",
        "repository_root": redacted_root,
        "composite_hash": composite_hash,
        "section_hashes": section_hashes,
        "limitations": {
            "missing_original_workspace": {
                "description": (
                    "The original Strategy Roadmap workspace "
                    "(/workspace/repository-strategy-roadmap/) "
                    "is not available in this checkout. Preserved handoff "
                    "context, incident summaries, repair data from the "
                    "committed incident ledger, and committed initiative "
                    "artifacts serve as the best available evidence. Live "
                    "plan state, chain logs, and raw repair artifacts from "
                    "the original workspace cannot be independently verified "
                    "from this fixture."
                ),
                "severity": "limitation",
                "mitigations": [
                    "Initiative artifacts are committed under .megaplan/initiatives/repository-strategy-roadmap/",
                    "Handoff context is extracted from committed active-epics-latency-synthesis",
                    "Incident summaries are regenerated from the committed ledger",
                    "Repair data redacts unstable workspace paths",
                ],
            },
            "path_redaction": {
                "description": (
                    "All absolute /workspace/ paths have been redacted with "
                    "stable content-hash tokens to prevent leakage of unstable "
                    "workspace layout while preserving structural comparison."
                ),
                "pattern": "/workspace/[REDACTED:<sha256-prefix>]",
                "applied_to": [
                    "initiative_artifacts",
                    "handoff_context",
                    "incident_data",
                    "repair_data",
                ],
            },
            "compaction_and_productive_baselines_unknown": {
                "description": (
                    "Compaction and productive-versus-replayed baselines are "
                    "preserved as UNKNOWN because the original workspace is "
                    "unavailable and the handoff document explicitly notes "
                    "that these metrics were not separately timed."
                ),
                "severity": "limitation",
                "affected_fields": [
                    "compaction_baseline.compaction_baseline",
                    "compaction_baseline.productive_versus_replayed_baseline",
                ],
            },
        },
        "sections": sections,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(fixture, fh, indent=2, ensure_ascii=False, sort_keys=True)
        print(f"Strategy Roadmap replay fixture written to {output_path}", file=sys.stderr)

    return fixture


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate M6 replay fixtures (T8 — Transaction Spine, T9 — Strategy Roadmap)",
    )
    parser.add_argument(
        "--fixture",
        choices=["transaction-spine", "strategy-roadmap"],
        default="transaction-spine",
        help="Which fixture to generate (default: transaction-spine)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for the fixture JSON (default: evidence/replay/<fixture>.json)",
    )
    args = parser.parse_args()

    if args.fixture == "strategy-roadmap":
        output = args.output or DEFAULT_STRATEGY_OUTPUT
        generate_strategy_roadmap(output_path=output)
    else:
        output = args.output or DEFAULT_OUTPUT
        generate_transaction_spine(output_path=output)


if __name__ == "__main__":
    main()
