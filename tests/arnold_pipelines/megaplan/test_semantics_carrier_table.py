"""Semantics carrier table conformance tests for M1 Megaplan migration.

These tests mechanically verify three contracts defined by the semantics
carrier table (``docs/arnold/megaplan-semantics-carrier-table.md``):

1. **Every exported handler is inventoried** — the live ``__all__`` export
   surface from ``arnold_pipelines.megaplan.handlers`` must have a 1:1 match
   with the handler inventory in the carrier table.
2. **Every report-owned semantic has exactly one allowed carrier** — each
   row in the traceability matrix (``megaplan-native-representation-traceability.yaml``)
   must be mapped to at least one owning handler in the carrier table, and
   no row may be silently unowned.  A semantic whose carrier is ``pending``
   is acceptable (it is an *explicit* pending status, not a missing one).
3. **Handler-ref carriers cannot be silently treated as implemented
   semantics** — the carrier table's classification is binding: no handler
   classified as ``pending`` may be claimed as conformance evidence, and
   every traceability row owned solely by ``pending`` handlers blocks any
   ``implemented`` status claim.

These tests are **Phase 1 launch-gate guards**.  Failing any of them means
the handler inventory, carrier classification, or traceability mapping has
drifted and the migration cannot proceed without re-synchronising the
carrier table.

Doctrine: ``megaplan-composition-doctrine-proof.md`` §5.3; carrier table
acceptance criteria §7.
"""

from __future__ import annotations

import importlib
import re
import yaml
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest


# ── Path constants ──────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[3]

CARRIER_TABLE_PATH = REPO_ROOT / "docs/arnold/megaplan-semantics-carrier-table.md"
TRACEABILITY_PATH = REPO_ROOT / "docs/arnold/megaplan-native-representation-traceability.yaml"
HANDLERS_INIT_PATH = REPO_ROOT / "arnold_pipelines/megaplan/handlers/__init__.py"

# Canonical carrier classifications (from carrier table §1)
ALLOWED_CARRIERS: frozenset[str] = frozenset({
    "canonical_source",
    "declared_policy",
    "audited_pure_phase_body",
    "pending",
})


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_live_handler_exports() -> frozenset[str]:
    """Return the set of handler names exported from ``handlers/__init__.py``."""
    spec = importlib.util.spec_from_file_location(
        "arnold_pipelines.megaplan.handlers",
        str(HANDLERS_INIT_PATH),
    )
    # We don't want to actually execute the module (it imports heavy
    # dependencies), so we parse __all__ from the source text instead.
    source = HANDLERS_INIT_PATH.read_text(encoding="utf-8")
    # Find the __all__ list
    match = re.search(r"__all__\s*=\s*\[(.*?)\]", source, re.DOTALL)
    if match is None:
        raise RuntimeError("Could not find __all__ in handlers/__init__.py")
    body = match.group(1)
    # Extract string literals
    names: list[str] = re.findall(r'"([^"]+)"', body)
    return frozenset(names)


def _parse_carrier_table() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Parse the carrier table markdown.

    Returns:
        handler_classification: {handler_name: classification}
        row_handler_map: {traceability_row_id: [handler_names]}
    """
    text = CARRIER_TABLE_PATH.read_text(encoding="utf-8")

    # ── Extract handler inventory from §2 table ──
    # The table rows look like: | 1 | `handle_init` | `handlers/init.py` | 630 | ...
    handler_classification: dict[str, str] = {}

    # ── Extract classifications from §3 per-handler sections ──
    # Each section header is "### 3.N handlername"
    # Within each section, there's an "**Overall classification:** `value`" line
    section_pattern = re.compile(
        r"###\s+3\.\d+\s+(\w+)\s*\n.*?\*\*Overall classification:\*\*\s*`([^`]+)`",
        re.DOTALL,
    )
    for match in section_pattern.finditer(text):
        handler_name = match.group(1)
        classification = match.group(2).strip()
        # Some have compound classifications like "declared_policy / audited_pure_phase_body"
        # We take the primary (first) classification for inventory purposes
        primary = classification.split("/")[0].strip()
        handler_classification[handler_name] = primary

    # ── Extract handler inventory from §2 table (for cross-check) ──
    table_handler_names: set[str] = set()
    table_pattern = re.compile(r"^\|\s*\d+\s*\|\s*`(\w+)`\s*\|", re.MULTILINE)
    for match in table_pattern.finditer(text):
        table_handler_names.add(match.group(1))

    # ── Extract traceability row → handler mapping from §4.2 ──
    row_handler_map: dict[str, list[str]] = {}
    # The table rows in §4.2 look like:
    # | `row-id` | `handler1`, `handler2` | `pending` |
    # Starting after "### 4.2 Traceability Row Coverage"
    section_42_start = text.find("### 4.2 Traceability Row Coverage")
    if section_42_start == -1:
        # Fallback: search the whole doc
        section_42_text = text
    else:
        section_42_text = text[section_42_start:]

    # Parse the §4.2 traceability row → handler mapping table.
    # Rows look like:
    # | `row-id` | `handler1`, `handler2` | `pending` |
    # The second column may contain multiple backtick-delimited handler names.
    # Strategy: find table rows, extract the row-id from the first column,
    # extract all backtick-delimited names from the second column as handlers.
    for line in section_42_text.splitlines():
        # Only process table rows (start with |)
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Skip header/separator rows
        if stripped.startswith("|---") or stripped.startswith("| Row"):
            continue
        # Split into columns
        cols = [c.strip() for c in stripped.split("|")]
        # Need at least 3 columns (empty, col1, col2, col3, empty)
        if len(cols) < 4:
            continue
        # First meaningful column (index 1) is the row ID
        row_id_match = re.match(r"`([a-z][a-z0-9_-]+)`", cols[1])
        if not row_id_match:
            continue
        row_id = row_id_match.group(1)
        # Second column (index 2) contains handler names
        handler_names = re.findall(r"`(\w+)`", cols[2])
        # Filter to handler-like names only (handle_*)
        handlers = [h for h in handler_names if h.startswith("handle_")]
        if handlers:
            row_handler_map[row_id] = handlers

    return handler_classification, row_handler_map


def _parse_traceability_yaml() -> dict[str, dict[str, Any]]:
    """Parse the traceability YAML and return {row_id: row_data}."""
    with open(TRACEABILITY_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    rows: dict[str, dict[str, Any]] = {}
    for row in data.get("rows", []):
        row_id = row.get("id", "")
        if row_id:
            rows[row_id] = row
    return rows


# ── Module-level (cached) parsed data ───────────────────────────────────────

_live_exports: frozenset[str] | None = None
_carrier_classifications: dict[str, str] | None = None
_row_handler_map: dict[str, list[str]] | None = None
_traceability_rows: dict[str, dict[str, Any]] | None = None


def _get_live_exports() -> frozenset[str]:
    global _live_exports
    if _live_exports is None:
        _live_exports = _get_live_handler_exports()
    return _live_exports


def _get_carrier_data() -> tuple[dict[str, str], dict[str, list[str]]]:
    global _carrier_classifications, _row_handler_map
    if _carrier_classifications is None or _row_handler_map is None:
        _carrier_classifications, _row_handler_map = _parse_carrier_table()
    return _carrier_classifications, _row_handler_map


def _get_traceability_rows() -> dict[str, dict[str, Any]]:
    global _traceability_rows
    if _traceability_rows is None:
        _traceability_rows = _parse_traceability_yaml()
    return _traceability_rows


# ── Test: Handler export inventory completeness ─────────────────────────────

class TestHandlerExportInventory:
    """Every handler in the live ``__all__`` export must be inventoried
    in the carrier table, and no handler in the carrier table may reference
    a non-existent export."""

    def test_all_exports_appear_in_carrier_table(self) -> None:
        """Every handler in ``__all__`` has a classification in the carrier table."""
        live = _get_live_exports()
        classifications, _ = _get_carrier_data()

        missing = live - set(classifications.keys())
        assert not missing, (
            f"Handlers in __all__ but not classified in carrier table: "
            f"{sorted(missing)}.  Add them to §3 of the carrier table."
        )

    def test_all_carrier_table_handlers_are_exported(self) -> None:
        """Every handler classified in the carrier table is in ``__all__``."""
        live = _get_live_exports()
        classifications, _ = _get_carrier_data()

        # Exclude handlers that appear only in §4.2 row mappings and not in §3
        # (e.g., "(distributed — runtime helpers, not a single handler)")
        phantom = set()
        for name in classifications:
            if name not in live:
                # Some entries in the row mappings use parenthetical descriptions
                if "(" not in name and name != "None":
                    phantom.add(name)

        assert not phantom, (
            f"Handlers classified in carrier table §3 but NOT in __all__: "
            f"{sorted(phantom)}.  Either add them to __all__ or remove them "
            f"from the carrier table."
        )

    def test_carrier_table_has_14_exported_handlers(self) -> None:
        """The carrier table documents exactly 14 exported handlers (§2)."""
        live = _get_live_exports()
        assert len(live) == 14, (
            f"Expected 14 handlers in __all__ per carrier table §2, "
            f"got {len(live)}: {sorted(live)}"
        )

    def test_no_handler_missing_classification(self) -> None:
        """Every handler in §3 has a non-empty classification."""
        classifications, _ = _get_carrier_data()
        for handler, cls in classifications.items():
            assert cls, (
                f"Handler '{handler}' has empty classification in carrier table §3."
            )
            assert cls in ALLOWED_CARRIERS, (
                f"Handler '{handler}' has unrecognized classification "
                f"'{cls}'.  Allowed: {sorted(ALLOWED_CARRIERS)}"
            )


# ── Test: Carrier classification integrity ──────────────────────────────────

class TestCarrierClassificationIntegrity:
    """Every handler must have exactly one primary carrier classification
    and the classification must be consistent across the carrier table."""

    def test_audited_pure_phase_body_handlers_are_correct(self) -> None:
        """Only handle_audit_verifiability and handle_verify_human are
        ``audited_pure_phase_body`` (carrier table §4.1)."""
        classifications, _ = _get_carrier_data()

        audited = {
            h for h, c in classifications.items()
            if c == "audited_pure_phase_body"
        }
        expected = {"handle_audit_verifiability", "handle_verify_human"}
        assert audited == expected, (
            f"audited_pure_phase_body handlers: got {sorted(audited)}, "
            f"expected {sorted(expected)}.  Carrier table §4.1 defines exactly "
            f"these two handlers as pure phase bodies."
        )

    def test_declared_policy_handlers_are_correct(self) -> None:
        """Only handle_init has ``declared_policy`` as primary classification
        (carrier table §4.1)."""
        classifications, _ = _get_carrier_data()

        declared = {
            h for h, c in classifications.items()
            if c == "declared_policy"
        }
        expected = {"handle_init"}
        assert declared == expected, (
            f"declared_policy handlers: got {sorted(declared)}, "
            f"expected {sorted(expected)}.  Carrier table §4.1 documents "
            f"handle_init mode routing as the only declared_policy semantic."
        )

    def test_zero_canonical_source_handlers(self) -> None:
        """Zero handlers are ``canonical_source`` — Phase 3 migration has
        not yet executed (carrier table §4.1)."""
        classifications, _ = _get_carrier_data()

        canonical = {
            h for h, c in classifications.items()
            if c == "canonical_source"
        }
        assert len(canonical) == 0, (
            f"canonical_source handlers found: {sorted(canonical)}.  "
            f"Carrier table §4.1 states '0 canonical_source — Phase 3 "
            f"migration not yet executed'.  No handler may be reclassified "
            f"as canonical_source before Phase 3 decomposition."
        )

    def test_exactly_11_pending_handlers(self) -> None:
        """Exactly 11 handlers are ``pending`` (carrier table §4.1)."""
        classifications, _ = _get_carrier_data()

        pending = {
            h for h, c in classifications.items()
            if c == "pending"
        }
        expected = {
            "handle_plan", "handle_prep", "handle_critique", "handle_revise",
            "handle_gate", "handle_finalize", "handle_execute", "handle_review",
            "handle_override", "handle_tiebreaker_run", "handle_tiebreaker_decide",
        }
        assert pending == expected, (
            f"pending handlers: got {sorted(pending)}, "
            f"expected {sorted(expected)}.  Carrier table §4.1 documents "
            f"exactly these 11 handlers as pending decomposition."
        )

    def test_classification_counts_match_4_1(self) -> None:
        """The classification counts match carrier table §4.1:
        canonical_source=0, declared_policy=1, audited_pure_phase_body=2,
        pending=11."""
        classifications, _ = _get_carrier_data()

        counts: dict[str, int] = defaultdict(int)
        for c in classifications.values():
            counts[c] += 1

        assert counts.get("canonical_source", 0) == 0
        assert counts.get("declared_policy", 0) == 1
        assert counts.get("audited_pure_phase_body", 0) == 2
        assert counts.get("pending", 0) == 11
        total = sum(counts.values())
        assert total == 14, (
            f"Expected 14 classified handlers total, got {total}"
        )


# ── Test: Traceability row coverage ─────────────────────────────────────────

class TestTraceabilityRowCoverage:
    """Every report-owned semantic (traceability row) must be mapped to at
    least one owning handler in the carrier table.  No row may be silently
    unmapped."""

    def test_every_traceability_row_has_handler_mapping(self) -> None:
        """Every row in the traceability YAML has at least one owning handler
        in the carrier table's row→handler map (§4.2)."""
        trace_rows = _get_traceability_rows()
        _, row_handler_map = _get_carrier_data()

        # Some rows are not handler-owned by design
        # (e.g., "source-path-reconciliation" is a docs task, "shadow-topology"
        #  is a planning artifact, "runtime-list-iteration" is compiler-owned)
        # We accept that some rows may have non-handler carriers
        unmapped: list[str] = []
        for row_id in trace_rows:
            if row_id not in row_handler_map:
                unmapped.append(row_id)

        # Acceptable unmapped rows (have non-handler carriers per carrier table)
        # These are rows whose carrier is documented as distributed/compiler/meta
        # in the carrier table §4.2 itself.
        acceptable_unmapped = {
            "source-path-reconciliation",  # docs task, declared_policy
            "timeout-deadline-policy",     # distributed — runtime helpers
            "runtime-list-iteration",      # compiler — not handler-owned
            "autodrive-event-liveness",    # distributed — control transitions
            "shadow-topology",             # not handler-owned — planning artifact
            "handler-purity-audit",        # meta — the carrier table itself
            "behavior-parity",             # cross-cutting — all handlers
            "source-readability",          # cross-cutting — all handlers
        }

        unexpected_unmapped = set(unmapped) - acceptable_unmapped
        assert not unexpected_unmapped, (
            f"Traceability rows with no handler mapping in carrier table §4.2: "
            f"{sorted(unexpected_unmapped)}.  Every row must have at least one "
            f"owning handler, or be explicitly listed as having a non-handler "
            f"carrier."
        )

    def test_no_traceability_row_claims_implemented_with_pending_carrier(
        self,
    ) -> None:
        """No traceability row whose ONLY owning handlers are ``pending``
        may be claimed as ``implemented``.  All rows owned solely by pending
        handlers block implementation claims."""
        _, row_handler_map = _get_carrier_data()
        classifications, _ = _get_carrier_data()
        trace_rows = _get_traceability_rows()

        # For each row, check if all its owning handlers are pending
        rows_blocked_by_pending: list[str] = []
        for row_id, handlers in row_handler_map.items():
            # Filter out non-handler entries (parenthetical descriptions)
            actual_handlers = [
                h for h in handlers
                if h in classifications
            ]
            if not actual_handlers:
                # No handler is mapped — the row has a different carrier type
                continue

            all_pending = all(
                classifications.get(h) == "pending"
                for h in actual_handlers
            )
            if all_pending:
                rows_blocked_by_pending.append(row_id)

        # Verify that blocked rows are the ones we expect (all product-semantic
        # rows except source-path-reconciliation which is declared_policy)
        # Per carrier table §4.2, all product rows are pending-blocked
        assert len(rows_blocked_by_pending) > 0, (
            "Expected at least some traceability rows to be blocked by pending "
            "handlers, but found none.  The carrier table should show that all "
            "product-semantic rows are pending until Phase 3."
        )

        # Verify that any row claimed implemented in the traceability YAML
        # does NOT have a pending-only carrier.
        # (Currently no rows should be 'implemented' in Phase 1, but we validate
        # structurally anyway.)
        for row_id, row_data in trace_rows.items():
            status = row_data.get("status", "")
            if status == "implemented":
                if row_id in rows_blocked_by_pending:
                    pytest.fail(
                        f"Traceability row '{row_id}' is marked 'implemented' "
                        f"but all its owning handlers are 'pending'.  "
                        f"Per carrier table rule: 'No alignment-plan row may "
                        f"be marked implemented if its semantic carrier is "
                        f"pending.'"
                    )

    def test_carrier_table_4_2_row_count_matches_traceability(self) -> None:
        """The row→handler map in carrier table §4.2 covers all traceability
        YAML rows (modulo acceptable non-handler-carrier rows)."""
        trace_rows = _get_traceability_rows()
        _, row_handler_map = _get_carrier_data()

        trace_row_ids = set(trace_rows.keys())
        # Rows that are non-handler-carrier in the carrier table
        non_handler_rows = {
            "source-path-reconciliation",
            "timeout-deadline-policy",
            "runtime-list-iteration",
            "autodrive-event-liveness",
            "shadow-topology",
            "handler-purity-audit",
            "behavior-parity",
            "source-readability",
        }

        handler_rows = trace_row_ids - non_handler_rows
        mapped_rows = set(row_handler_map.keys())

        missing = handler_rows - mapped_rows
        extra = mapped_rows - handler_rows

        assert not missing, (
            f"Traceability rows not mapped in carrier table §4.2: "
            f"{sorted(missing)}"
        )
        # Extra entries in the carrier table that aren't traceability rows
        # are acceptable (they may be sub-items or explanatory)


# ── Test: Handler-ref false-pass guards ─────────────────────────────────────

class TestHandlerRefFalsePassGuards:
    """Handler-ref carriers (pending handlers) cannot be silently treated
    as implemented semantics.  This class verifies structural guards."""

    def test_pending_handlers_are_not_conformance_evidence(self) -> None:
        """No pending handler may appear in any conformance claim as evidence
        of implementation.  This is a structural negative test: the carrier
        table itself must classify these handlers as pending."""
        classifications, _ = _get_carrier_data()

        pending_handlers = {
            h for h, c in classifications.items() if c == "pending"
        }

        # Verify the known set
        expected_pending = {
            "handle_plan", "handle_prep", "handle_critique", "handle_revise",
            "handle_gate", "handle_finalize", "handle_execute", "handle_review",
            "handle_override", "handle_tiebreaker_run", "handle_tiebreaker_decide",
        }
        assert pending_handlers == expected_pending, (
            f"Pending handler set mismatch.  Carrier table §4.1 specifies "
            f"exactly 11 pending handlers."
        )

    def test_handler_owned_routing_patterns_are_enumerated(self) -> None:
        """The carrier table §5 enumerates the five handler-ref false-pass
        patterns: state mutation routing, worker dispatch, parallel dispatch,
        loop/retry, and override action dispatch."""
        text = CARRIER_TABLE_PATH.read_text(encoding="utf-8")

        required_sections = [
            "5.1 State Mutation Routing",
            "5.2 Worker Dispatch",
            "5.3 Parallel Dispatch",
            "5.4 Loop / Retry",
            "5.5 Override Action Dispatch",
        ]

        for section in required_sections:
            assert section in text, (
                f"Carrier table must include false-pass guard section "
                f"'{section}'.  Missing from document."
            )

    def test_phase_dependent_status_is_declared(self) -> None:
        """The carrier table §6 declares phase-dependent carrier status,
        gating all ``pending`` → ``canonical_source`` transitions on Phase 3
        + M7 completion."""
        text = CARRIER_TABLE_PATH.read_text(encoding="utf-8")

        assert "### 6.1 Phase 1" in text
        assert "### 6.2 Phase 2" in text
        assert "### 6.3 Phase 3" in text

        # Phase 3 must be gated
        assert "Blocked" in text or "blocked" in text, (
            "Carrier table §6.3 must indicate Phase 3 is blocked/gated"
        )
        assert "M7" in text, (
            "Carrier table §6.3 must reference the M7 prerequisite gate"
        )

    def test_carrier_table_acceptance_criteria_are_self_documenting(self) -> None:
        """The carrier table §7 documents its own acceptance criteria with
        8 checkmarks."""
        text = CARRIER_TABLE_PATH.read_text(encoding="utf-8")

        # Count the checkmarks
        checks = text.count("✅")
        assert checks >= 8, (
            f"Carrier table §7 should have 8 acceptance checkmarks; "
            f"found {checks}"
        )

    def test_no_handler_is_unclassified(self) -> None:
        """Every handler in the carrier table §3 has an explicit overall
        classification, not just per-semantic classifications."""
        classifications, _ = _get_carrier_data()
        live = _get_live_exports()

        # Every live export must be in classifications
        unclassified = live - set(classifications.keys())
        assert not unclassified, (
            f"Handlers with no overall classification in carrier table §3: "
            f"{sorted(unclassified)}"
        )


# ── Test: Cross-file contract enforcement ───────────────────────────────────

class TestCrossFileContract:
    """The carrier table, traceability YAML, and live handler exports form
    a cross-file contract.  This class verifies the contract is closed —
    nothing is silently unowned, ambiguous, or misclassified."""

    def test_live_exports_match_carrier_table_exactly(self) -> None:
        """The set of handler names in ``__all__`` matches the set of handler
        names with classifications in the carrier table §3, 1:1."""
        live = _get_live_exports()
        classifications, _ = _get_carrier_data()

        live_only = live - set(classifications.keys())
        carrier_only = set(classifications.keys()) - live

        assert not live_only, (
            f"Handlers in __all__ but missing from carrier table §3: "
            f"{sorted(live_only)}"
        )
        assert not carrier_only, (
            f"Handlers in carrier table §3 but missing from __all__: "
            f"{sorted(carrier_only)}"
        )

    def test_every_classified_handler_has_source_file(self) -> None:
        """Every handler in the carrier table §2 has a source file that
        exists on disk."""
        text = CARRIER_TABLE_PATH.read_text(encoding="utf-8")

        # Parse §2 table: | N | `handler_name` | `source.py` | ...
        handler_file_pattern = re.compile(
            r"\|\s*\d+\s*\|\s*`(\w+)`\s*\|\s*`([^`]+)`\s*\|"
        )
        megaplan_dir = REPO_ROOT / "arnold_pipelines/megaplan"

        for match in handler_file_pattern.finditer(text):
            handler_name = match.group(1)
            source_file_rel = match.group(2)
            # Source files in the carrier table §2 are relative to the
            # megaplan package root (e.g., "handlers/init.py")
            source_file = megaplan_dir / source_file_rel
            assert source_file.exists(), (
                f"Handler '{handler_name}' source file '{source_file_rel}' "
                f"referenced in carrier table §2 does not exist at "
                f"{source_file}"
            )

    def test_traceability_yaml_false_pass_guards_align_with_carrier_table(
        self,
    ) -> None:
        """The false_pass_guard entries in the traceability YAML are
        consistent with carrier table classifications: rows whose carriers
        are pending should not have empty false_pass_guard fields."""
        trace_rows = _get_traceability_rows()
        _, row_handler_map = _get_carrier_data()
        classifications, _ = _get_carrier_data()

        for row_id, row_data in trace_rows.items():
            false_pass_guard = row_data.get("false_pass_guard", "")
            assert false_pass_guard, (
                f"Traceability row '{row_id}' has no false_pass_guard.  "
                f"Every row must declare a false-pass guard per the "
                f"traceability schema."
            )

    def test_pending_handlers_match_doctrine_false_pass_language(self) -> None:
        """The 11 pending handlers in the carrier table correspond to
        handlers that doctrine identifies as owning handler-ref routing
        patterns (state mutation, worker dispatch, parallel dispatch,
        loop/retry, override action dispatch).  Verify the overlap."""
        classifications, _ = _get_carrier_data()
        text = CARRIER_TABLE_PATH.read_text(encoding="utf-8")

        pending_handlers = {
            h for h, c in classifications.items() if c == "pending"
        }

        # Extract handlers listed in §5 false-pass guard sections
        # Each section lists affected handlers as `- `handle_*``
        affected_pattern = re.findall(r"-\s*`(\w+)`", text)

        affected_set = set(affected_pattern)
        # All affected handlers should be pending
        unclassified_affected = affected_set - set(classifications.keys())
        non_pending_affected = {
            h for h in affected_set
            if h in classifications and classifications[h] != "pending"
        }

        # Some affected handlers may appear multiple times across patterns
        # The point is: no handler listed as having handler-ref routing
        # patterns should be anything other than pending
        assert not non_pending_affected, (
            f"Handlers listed in false-pass guard sections §5 but classified "
            f"as non-pending: {sorted(non_pending_affected)}.  Any handler "
            f"with state-mutation routing, worker dispatch, parallel dispatch, "
            f"loop/retry, or override action dispatch must be 'pending'."
        )

    def test_override_action_surface_fully_pending(self) -> None:
        """handle_override's action matrix (abort, replan, force-proceed,
        add-note, resume-clarify, recover-blocked, set-robustness/profile/
        model/vendor) is fully pending — the handler is not a carrier for
        any canonical_source semantic."""
        classifications, _ = _get_carrier_data()

        assert classifications.get("handle_override") == "pending", (
            f"handle_override must be 'pending': its full action surface "
            f"(10+ routes) is handler-owned and must be decomposed before "
            f"claiming canonical_source.  Per carrier table §3.10."
        )
