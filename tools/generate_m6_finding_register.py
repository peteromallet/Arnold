#!/usr/bin/env python3
"""M6 finding-prevention register generator (T10 — Step 9).

Produces ``evidence/finding-prevention-register.json`` with exactly one
row for each F01-F17 finding from the unified Run Authority and Megaplan
efficiency prevention synthesis.

This generator is **strictly observe-only**: it reads the committed
research document and writes only the register artifact. It does not
mutate lifecycle state, queues, providers, delivery, notifications,
source history, or runtime behavior.

Design invariants
-----------------

* **Exact F01-F17 coverage**: every finding in the unified synthesis
  (:file:`.megaplan/initiatives/custody-control-plane/research/unified-authority-efficiency-prevention-20260714.md`)
  appears exactly once, no omissions, no duplicates.
* **Deterministic ordering**: rows are sorted by finding ID so two runs
  against the same commit always produce the same artifact.
* **Stable row hashes**: each row carries a SHA-256 content hash computed
  from the deterministically ordered JSON representation of the row
  (excluding the hash field itself).
* **Complete fields**: every row has owner, control, acceptance proof,
  rollout gate, rollback/fail-closed behavior, deletion gate, evidence
  references, and the stable row hash.
* **Root cause included**: the root cause from the research document is
  included as a string field for traceability.

Usage::

    python tools/generate_m6_finding_register.py [--output PATH] [--validate]
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

RESEARCH_DOC = (
    REPO_ROOT
    / ".megaplan"
    / "initiatives"
    / "custody-control-plane"
    / "research"
    / "unified-authority-efficiency-prevention-20260714.md"
)

DEFAULT_OUTPUT = EVIDENCE_DIR / "finding-prevention-register.json"

SCHEMA = "m6.finding-prevention-register.v1"

# ── Parsing helpers ─────────────────────────────────────────────────────────

_FINDING_HEADER_RE = re.compile(r"^### (F\d{2}) — (.+)$")

# The document uses separate sections for each finding.  We collect
# paragraphs between "### Fnn — ..." headers until the next header or
# horizontal rule.

_NEXT_SECTION_RE = re.compile(r"^(### |---$)")


def _parse_findings(doc_text: str) -> list[dict[str, str]]:
    """Parse F01-F17 definitions from the unified synthesis document.

    Returns a list of dicts with keys ``finding_id``, ``title``, and
    ``body`` (the raw markdown text of the finding section).
    """
    lines = doc_text.split("\n")
    findings: list[dict[str, str]] = []
    current_id: str | None = None
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        m = _FINDING_HEADER_RE.match(line)
        if m:
            # Save the previous finding
            if current_id is not None:
                findings.append({
                    "finding_id": current_id,
                    "title": current_title or "",
                    "body": "\n".join(current_lines).strip(),
                })

            current_id = m.group(1)
            current_title = m.group(2).strip()
            current_lines = []
            continue

        if current_id is not None:
            if _NEXT_SECTION_RE.match(line):
                # End of current finding section
                findings.append({
                    "finding_id": current_id,
                    "title": current_title or "",
                    "body": "\n".join(current_lines).strip(),
                })
                current_id = None
                current_title = None
                current_lines = []
                continue
            current_lines.append(line)

    # Don't forget the last one
    if current_id is not None:
        findings.append({
            "finding_id": current_id,
            "title": current_title or "",
            "body": "\n".join(current_lines).strip(),
        })

    return findings


# ── Extraction helpers ──────────────────────────────────────────────────────

# Patterns to extract structured fields from each finding body.
# The document uses consistent formatting:
#   - Root cause: ...
#   - Owner/control: ...
#   - Milestone/proof: ...
#   - Rollout gate: ...
#   - Fail closed/retirement: ...   (also appears as "Fail-closed/retirement")
#   - (some findings also have "Rollback/fail-closed behavior")

# We extract by matching label lines and collecting the following
# paragraphs until the next label or blank-line-separated block.

_LABEL_RE = re.compile(
    r"^- (?:\*\*)?(Root cause|Owner/control|Milestone/proof|Rollout gate"
    r"|Fail(?:[ -]closed| closed)/retirement"
    r"|Rollback/fail-closed"
    r"|Deletion gate)(?:\*\*)?:?\s*(.*)$",
    re.IGNORECASE,
)


def _extract_fields(body: str) -> dict[str, str]:
    """Extract structured fields from a finding body.

    Returns dict with keys: root_cause, owner_control, milestone_proof,
    rollout_gate, fail_closed_retirement, rollback_behavior.
    """
    fields: dict[str, str] = {}
    lines = body.split("\n")
    current_key: str | None = None
    current_value: list[str] = []

    for line in lines:
        m = _LABEL_RE.match(line)
        if m:
            # Save the previous field
            if current_key is not None and current_value:
                fields[current_key] = " ".join(current_value).strip()

            label = m.group(1).strip().lower()
            remainder = m.group(2).strip()

            # Normalize label names
            if label.startswith("root cause"):
                current_key = "root_cause"
            elif label.startswith("owner/control"):
                current_key = "owner_control"
            elif label.startswith("milestone/proof"):
                current_key = "milestone_proof"
            elif label.startswith("rollout gate"):
                current_key = "rollout_gate"
            elif "fail" in label and "retirement" in label:
                current_key = "fail_closed_retirement"
            elif label.startswith("rollback/fail-closed"):
                current_key = "rollback_behavior"
            else:
                current_key = None
                current_value = []
                continue

            current_value = [remainder] if remainder else []
            continue

        if current_key is not None and line.strip():
            # Continuation of the current field
            current_value.append(line.strip())
        elif current_key is not None and not line.strip():
            # Blank line ends the current field
            if current_value:
                fields[current_key] = " ".join(current_value).strip()
            current_key = None
            current_value = []

    # Save the last field
    if current_key is not None and current_value:
        fields[current_key] = " ".join(current_value).strip()

    return fields


# ── Row builder ─────────────────────────────────────────────────────────────


def _compute_row_hash(row: dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash for a row (excluding the hash field)."""
    row_copy = {k: v for k, v in row.items() if k != "row_hash"}
    canonical = json.dumps(row_copy, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_register_rows(
    findings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Convert parsed findings into register rows with stable hashes."""
    rows: list[dict[str, Any]] = []

    # Evidence document reference
    evidence_ref = (
        ".megaplan/initiatives/custody-control-plane/research/"
        "unified-authority-efficiency-prevention-20260714.md"
    )

    for f in sorted(findings, key=lambda x: x["finding_id"]):
        fid = f["finding_id"]
        title = f["title"]
        body = f["body"]

        fields = _extract_fields(body)

        root_cause = fields.get("root_cause", "")
        owner_control = fields.get("owner_control", "")
        milestone_proof = fields.get("milestone_proof", "")
        rollout_gate = fields.get("rollout_gate", "")
        fail_closed_retirement = fields.get("fail_closed_retirement", "")
        rollback_behavior = fields.get("rollback_behavior", "")

        # Derive canonical owner from owner_control field.
        # Format is typically: "Run Authority defines ...; repair custody dispatches ..."
        # or "WBC emits ...; repair custody consumes ..."
        # The canonical owner is the first named authority.
        canonical_owner = _extract_canonical_owner(owner_control)

        # Deletion gate: extract from fail_closed_retirement or derive
        deletion_gate = _extract_deletion_gate(fail_closed_retirement, rollback_behavior)

        row: dict[str, Any] = {
            "finding_id": fid,
            "title": title,
            "root_cause": root_cause,
            "canonical_owner": canonical_owner,
            "owner_control": owner_control,
            "acceptance_proof": milestone_proof,
            "rollout_gate": rollout_gate,
            "rollback_behavior": rollback_behavior or fail_closed_retirement,
            "deletion_gate": deletion_gate,
            "evidence_references": [evidence_ref],
        }

        # Compute stable row hash
        row["row_hash"] = _compute_row_hash(row)

        rows.append(row)

    return rows


def _extract_canonical_owner(owner_control: str) -> str:
    """Extract the canonical owner from the owner_control text.

    Returns the **first** named authority in the text.  The document
    consistently puts the primary owner before any supporting roles
    (e.g. "WBC stores …; Run Authority validates …" → WBC).

    Returns one of: Run Authority, WBC, TransitionWriter/repair custody,
    Megaplan Maintenance, Planner/compiler, Executor/launcher,
    Observability/projection, or UNKNOWN.
    """
    if not owner_control:
        return "UNKNOWN"

    # Ordered list of owner patterns — we scan for the first occurrence in
    # the original text (case-insensitive).  More specific patterns come
    # first to avoid false matches (e.g. "repair custody" before "run authority"
    # so F15 gets TransitionWriter/repair custody, not Run Authority).
    owner_patterns: list[tuple[str, str]] = [
        ("transitionwriter", "TransitionWriter/repair custody"),
        ("repair custody", "TransitionWriter/repair custody"),
        ("run authority", "Run Authority"),
        ("wbc", "WBC"),
        ("megaplan maintenance", "Megaplan Maintenance"),
        ("maintenance owns", "Megaplan Maintenance"),
        ("planner/compiler", "Planner/compiler"),
        ("executor/launcher", "Executor/launcher"),
        ("runtime packaging", "Executor/launcher"),
        ("launcher/runtime packaging", "Executor/launcher"),
        ("observability", "Observability/projection"),
        ("planner", "Planner/compiler"),
        ("compiler", "Planner/compiler"),
        ("executor", "Executor/launcher"),
        ("launcher", "Executor/launcher"),
    ]

    # Find the first match by position in the original text
    text_lower = owner_control.lower()
    best_pos = len(owner_control) + 1
    best_owner = "UNKNOWN"

    for pattern, owner in owner_patterns:
        pos = text_lower.find(pattern)
        if 0 <= pos < best_pos:
            best_pos = pos
            best_owner = owner

    return best_owner


def _extract_deletion_gate(fail_closed: str, rollback: str) -> str:
    """Extract the deletion gate conditions from the fail-closed/retirement text.

    The deletion gate is typically the last sentence about when legacy
    paths can be removed (e.g., "after zero callers and ... proof").
    """
    combined = fail_closed + " " + rollback if rollback else fail_closed
    if not combined.strip():
        return "UNKNOWN"

    # Look for "Delete ..." or "Remove ..." or "Retire ..." sentences
    for prefix in ["Delete ", "Remove ", "Retire ", "delete ", "remove ", "retire "]:
        idx = combined.find(prefix)
        if idx >= 0:
            # Find the end of the sentence (period or next sentence boundary)
            end = combined.find(".", idx)
            if end < 0:
                end = len(combined)
            snippet = combined[idx:end + 1].strip()
            # Take up to the last sentence boundary
            # If there's a period within, trim to that
            period_idx = snippet.rfind(".")
            if period_idx > 0:
                snippet = snippet[:period_idx + 1]
            return snippet

    return "UNKNOWN"


# ── Artifact assembly ───────────────────────────────────────────────────────


def _compute_composite_hash(rows: list[dict[str, Any]]) -> str:
    """Compute composite hash from sorted row hashes."""
    row_hashes = sorted(r["row_hash"] for r in rows)
    combined = "".join(row_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def generate_register(output_path: Path | None = None) -> dict[str, Any]:
    """Generate the full finding-prevention register artifact.

    Returns the artifact dict (also writes it to disk if *output_path*
    is provided).
    """
    if not RESEARCH_DOC.exists():
        print(
            f"Error: research document not found: {RESEARCH_DOC}",
            file=sys.stderr,
        )
        sys.exit(1)

    doc_text = RESEARCH_DOC.read_text(encoding="utf-8")
    findings = _parse_findings(doc_text)

    # We must have exactly F01-F17
    expected_ids = {f"F{i:02d}" for i in range(1, 18)}
    found_ids = {f["finding_id"] for f in findings}

    if found_ids != expected_ids:
        missing = expected_ids - found_ids
        extra = found_ids - expected_ids
        msg_parts = []
        if missing:
            msg_parts.append(f"Missing: {sorted(missing)}")
        if extra:
            msg_parts.append(f"Extra: {sorted(extra)}")
        print(
            f"Error: finding coverage mismatch. {'; '.join(msg_parts)}",
            file=sys.stderr,
        )
        sys.exit(1)

    rows = _build_register_rows(findings)

    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "tools/generate_m6_finding_register.py",
        "source_document": str(
            RESEARCH_DOC.relative_to(REPO_ROOT)
        ),
        "finding_count": len(rows),
        "expected_coverage": "F01–F17 (exactly 17 findings)",
        "rows": rows,
        "composite_hash": _compute_composite_hash(rows),
        "row_hash_algorithm": "SHA-256",
        "row_hash_coverage": "each row hash computed from deterministically ordered JSON excluding row_hash field",
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return artifact


# ── Validation ──────────────────────────────────────────────────────────────


def _validate_register(artifact: dict[str, Any]) -> bool:
    """Validate the register artifact.  Returns True if valid."""
    errors: list[str] = []

    # Schema check
    if artifact.get("schema") != SCHEMA:
        errors.append(f"Schema mismatch: {artifact.get('schema')} != {SCHEMA}")

    # Row count
    rows = artifact.get("rows", [])
    if len(rows) != 17:
        errors.append(f"Row count: {len(rows)} != 17")

    # Coverage
    row_ids = {r["finding_id"] for r in rows}
    expected = {f"F{i:02d}" for i in range(1, 18)}
    if row_ids != expected:
        errors.append(
            f"Coverage mismatch: missing {sorted(expected - row_ids)}, "
            f"extra {sorted(row_ids - expected)}"
        )

    # Required fields per row
    required_fields = {
        "finding_id",
        "title",
        "root_cause",
        "canonical_owner",
        "owner_control",
        "acceptance_proof",
        "rollout_gate",
        "rollback_behavior",
        "deletion_gate",
        "evidence_references",
        "row_hash",
    }

    for row in rows:
        fid = row.get("finding_id", "?")
        missing = required_fields - set(row.keys())
        if missing:
            errors.append(f"Row {fid}: missing fields {sorted(missing)}")
        # Verify row hash
        expected_hash = _compute_row_hash(row)
        actual_hash = row.get("row_hash", "")
        if expected_hash != actual_hash:
            errors.append(
                f"Row {fid}: hash mismatch "
                f"(expected {expected_hash[:12]}..., got {actual_hash[:12]}...)"
            )

    # Composite hash
    expected_composite = _compute_composite_hash(rows)
    actual_composite = artifact.get("composite_hash", "")
    if expected_composite != actual_composite:
        errors.append("Composite hash mismatch")

    # Verify canonical_owner is one of the known owners
    known_owners = {
        "Run Authority",
        "WBC",
        "TransitionWriter/repair custody",
        "Megaplan Maintenance",
        "Planner/compiler",
        "Executor/launcher",
        "Observability/projection",
        "UNKNOWN",
    }
    for row in rows:
        owner = row.get("canonical_owner", "")
        if owner not in known_owners:
            errors.append(f"Row {row['finding_id']}: unknown canonical_owner '{owner}'")

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        return False

    print("Validation PASSED: 17 rows, all fields present, all hashes valid.")
    return True


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate M6 finding-prevention register from unified synthesis."
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
        help="Additionally validate the generated register after writing.",
    )
    args = parser.parse_args()

    artifact = generate_register(output_path=args.output)

    print(
        f"Generated {args.output}: {len(artifact['rows'])} findings, "
        f"composite_hash={artifact['composite_hash'][:16]}..."
    )

    if args.validate:
        ok = _validate_register(artifact)
        if not ok:
            sys.exit(1)

    # Print summary
    owner_counts: dict[str, int] = {}
    for row in artifact["rows"]:
        owner = row["canonical_owner"]
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
    print("Ownership distribution:")
    for owner, count in sorted(owner_counts.items()):
        print(f"  {owner}: {count}")


if __name__ == "__main__":
    main()
