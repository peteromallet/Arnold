"""M4 graph baseline — capture the hand-built Megaplan pipeline topology before rewrite.

Persists the canonical topology hash, validates control-flow cleanliness,
and asserts the public stage order so that any structural regression during
the M4 native rewrite is caught immediately.

This file MUST be updated whenever the canonical ``build_pipeline()`` graph
is intentionally changed — the hash and stage order here are the source of
truth for the pre-rewrite baseline.
"""

from __future__ import annotations

from arnold.pipelines.megaplan.pipeline import build_pipeline
from arnold.pipeline.topology import compute_topology_hash
from arnold.pipeline.validator import validate_control_flow

# ── Captured baseline constants ────────────────────────────────────────────
# These are the values produced by the hand-built ``build_pipeline()`` on
# 2026-06-19.  They MUST be updated when the graph is intentionally changed.
EXPECTED_TOPOLOGY_HASH: str = (
    "sha256:f11cd2e61fdb8fcb8aac558db6ceb5aef2a936cd2a58c0277a7e45523512ba30"
)

EXPECTED_STAGE_ORDER: tuple[str, ...] = (
    "prep",
    "plan",
    "critique",
    "gate",
    "revise",
    "finalize",
    "execute",
    "review",
    "tiebreaker",
)


# ═══════════════════════════════════════════════════════════════════════════
# Topology hash baseline
# ═══════════════════════════════════════════════════════════════════════════


class TestTopologyHashBaseline:
    """The hand-built Megaplan graph must produce a stable topology hash."""

    def test_topology_hash_matches_baseline(self) -> None:
        """``compute_topology_hash(build_pipeline())`` equals the captured baseline."""
        pipeline = build_pipeline()
        actual = compute_topology_hash(pipeline)
        assert actual == EXPECTED_TOPOLOGY_HASH, (
            f"Topology hash mismatch!\n"
            f"  expected: {EXPECTED_TOPOLOGY_HASH}\n"
            f"  actual:   {actual}\n"
            f"If the graph was intentionally changed, update EXPECTED_TOPOLOGY_HASH "
            f"in this file."
        )

    def test_topology_hash_is_stable_across_builds(self) -> None:
        """Multiple calls to ``build_pipeline()`` produce the same hash."""
        hashes = {compute_topology_hash(build_pipeline()) for _ in range(5)}
        assert len(hashes) == 1, (
            f"Expected 1 unique hash across 5 builds, got {len(hashes)}"
        )

    def test_topology_hash_format(self) -> None:
        """The hash string has the canonical ``sha256:<hex>`` form."""
        h = compute_topology_hash(build_pipeline())
        assert h.startswith("sha256:"), f"Missing sha256: prefix: {h[:20]!r}..."
        assert len(h) == 71, f"Expected 71 chars, got {len(h)}"
        hex_part = h[7:]
        assert all(c in "0123456789abcdef" for c in hex_part), "Non-hex in digest"


# ═══════════════════════════════════════════════════════════════════════════
# Control-flow validation
# ═══════════════════════════════════════════════════════════════════════════


class TestControlFlowBaseline:
    """The hand-built Megaplan graph must pass control-flow validation cleanly."""

    def test_validate_control_flow_returns_no_defects(self) -> None:
        """``validate_control_flow(build_pipeline())`` must return zero defects."""
        pipeline = build_pipeline()
        diag = validate_control_flow(pipeline)
        assert diag.ok, (
            f"Control-flow validation found unexpected defects:\n"
            + "\n".join(f"  - {d}" for d in diag.defects)
        )

    def test_validate_control_flow_no_structured_issues(self) -> None:
        """No structured ``ValidationIssue`` entries are emitted."""
        pipeline = build_pipeline()
        diag = validate_control_flow(pipeline)
        assert len(diag.issues) == 0, (
            f"Expected 0 structured issues, got {len(diag.issues)}:\n"
            + "\n".join(f"  - [{i.code}] {i.message}" for i in diag.issues)
        )


# ═══════════════════════════════════════════════════════════════════════════
# Public stage order
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicStageOrder:
    """The canonical Megaplan pipeline must expose exactly the expected stages
    in the documented order."""

    def test_stage_count(self) -> None:
        """Exactly 9 public stages (no feedback stage)."""
        pipeline = build_pipeline()
        assert len(pipeline.stages) == 9, (
            f"Expected 9 stages, got {len(pipeline.stages)}: "
            f"{list(pipeline.stages.keys())}"
        )

    def test_stage_order_matches_baseline(self) -> None:
        """``pipeline.stages.keys()`` preserves insert order matching the
        documented layout: prep → plan → critique → gate → revise →
        finalize → execute → review → tiebreaker."""
        pipeline = build_pipeline()
        actual = tuple(pipeline.stages.keys())
        assert actual == EXPECTED_STAGE_ORDER, (
            f"Stage order mismatch!\n"
            f"  expected: {EXPECTED_STAGE_ORDER}\n"
            f"  actual:   {actual}"
        )

    def test_entry_is_prep(self) -> None:
        """The entry stage is ``prep``."""
        pipeline = build_pipeline()
        assert pipeline.entry == "prep", (
            f"Expected entry='prep', got {pipeline.entry!r}"
        )

    def test_resource_bundles_match_stages(self) -> None:
        """The resource_bundles tuple mirrors the nine stage keys in order."""
        pipeline = build_pipeline()
        assert pipeline.resource_bundles == EXPECTED_STAGE_ORDER, (
            f"resource_bundles mismatch:\n"
            f"  expected: {EXPECTED_STAGE_ORDER}\n"
            f"  actual:   {pipeline.resource_bundles}"
        )
