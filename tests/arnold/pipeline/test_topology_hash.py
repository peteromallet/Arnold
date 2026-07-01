"""Tests for :func:`arnold.pipeline.topology.compute_topology_hash`.

Covers:
* Stability — repeated ``folder_audit.build_pipeline()`` calls return
  the same topology hash.
* Edge-change sensitivity — changing a fixture graph edge changes the hash.
* Vocabulary sensitivity — changing declared decision/override vocabularies
  changes the hash.
* Port sensitivity — changing declared ports changes the hash.
* Binding-map sensitivity.
"""

from __future__ import annotations

import pytest

from arnold.pipeline.topology import compute_topology_hash
from arnold.pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Minimal step for constructing fixture pipelines
# ---------------------------------------------------------------------------


class _FakeStep:
    """A step that does nothing — used only for structural tests."""

    def __init__(self, name: str = "fake", kind: str = "produce") -> None:
        self.name = name
        self.kind = kind

    def run(self, ctx: StepContext) -> StepResult:
        raise NotImplementedError("test-only stub")


def _human_gate_suspension_schema(
    *,
    override_routes: dict[str, str | None] | None = None,
) -> dict[str, object]:
    routes = (
        {"force_continue": "continue", "force_stop": "halt"}
        if override_routes is None
        else override_routes
    )
    return {
        "type": "object",
        "properties": {
            "choice": {
                "type": "string",
                "enum": ["continue", "stop"],
            },
        },
        "required": ["choice"],
        "x-arnold-human-gate": {
            "stage": "human_review_gate",
            "decision": "human_review_gate",
            "artifact_stage": "draft",
            "choices": ["continue", "stop"],
            "override_routes": routes,
        },
    }


def _make_human_gate_pipeline(
    *,
    decision_vocabulary: frozenset[str] | None = None,
    override_vocabulary: frozenset[str] | None = None,
    decision_routes: dict[str, str | None] | None = None,
    suspension_schema: dict[str, object] | None = None,
) -> Pipeline:
    if decision_vocabulary is None:
        decision_vocabulary = frozenset({"continue", "stop"})
    if override_vocabulary is None:
        override_vocabulary = frozenset({"force_continue", "force_stop"})
    if decision_routes is None:
        decision_routes = {"continue": "continue", "stop": None}
    if suspension_schema is None:
        suspension_schema = _human_gate_suspension_schema()

    draft = Stage(
        name="draft",
        step=_FakeStep("draft"),
        edges=(Edge(label="human_review_gate", target="human_review_gate"),),
    )
    gate = Stage(
        name="human_review_gate",
        step=_FakeStep("human_review_gate", kind="native_decision"),
        edges=(
            Edge(label="continue", target="panel_review"),
            Edge(label="stop", target="halt"),
            Edge(
                label="override force_continue",
                target="panel_review",
                kind="override",
            ),
            Edge(label="override force_stop", target="halt", kind="override"),
        ),
        decision_vocabulary=decision_vocabulary,
        override_vocabulary=override_vocabulary,
        decision_routes=decision_routes,
        suspension_schema=suspension_schema,
    )
    panel_review = Stage(
        name="panel_review",
        step=_FakeStep("panel_review"),
        edges=(Edge(label="human_review_gate", target="human_review_gate"),),
    )
    return Pipeline(
        stages={
            "draft": draft,
            "human_review_gate": gate,
            "panel_review": panel_review,
        },
        entry="draft",
    )


# ---------------------------------------------------------------------------
# Stability — folder_audit.build_pipeline()
# ---------------------------------------------------------------------------


class TestFolderAuditTopologyStability:
    """The folder_audit graph must produce a stable topology hash."""

    def test_repeated_build_returns_same_hash(self) -> None:
        """Multiple calls to build_pipeline() yield the same topology hash."""
        from arnold.pipelines.folder_audit import build_pipeline

        hashes = {compute_topology_hash(build_pipeline()) for _ in range(5)}
        assert len(hashes) == 1, (
            f"Expected 1 unique hash across 5 builds, got {len(hashes)}"
        )

    def test_hash_is_sha256_prefixed(self) -> None:
        """The returned string has the expected format."""
        from arnold.pipelines.folder_audit import build_pipeline

        h = compute_topology_hash(build_pipeline())
        assert h.startswith("sha256:"), f"Expected sha256: prefix, got {h[:20]!r}..."
        assert len(h) == 71, f"Expected 71 chars (sha256: + 64 hex), got {len(h)}"
        hex_part = h[7:]
        assert all(c in "0123456789abcdef" for c in hex_part), "Non-hex in digest"

    def test_deterministic_across_process_boundary(self) -> None:
        """Same input → same hash (no randomness, no timestamp)."""
        from arnold.pipelines.folder_audit import build_pipeline

        p1 = build_pipeline()
        p2 = build_pipeline()
        assert compute_topology_hash(p1) == compute_topology_hash(p2)


# ---------------------------------------------------------------------------
# Edge-change sensitivity
# ---------------------------------------------------------------------------


class TestEdgeChangeSensitivity:
    """Changing any graph edge must produce a different topology hash."""

    @staticmethod
    def _make_linear_pipeline() -> Pipeline:
        """Return a simple two-stage linear pipeline."""
        s1 = Stage(
            name="first",
            step=_FakeStep("first"),
            edges=(Edge(label="done", target="second"),),
        )
        s2 = Stage(
            name="second",
            step=_FakeStep("second"),
            edges=(Edge(label="halt", target="halt"),),
        )
        return Pipeline(stages={"first": s1, "second": s2}, entry="first")

    def test_same_pipeline_same_hash(self) -> None:
        p1 = self._make_linear_pipeline()
        p2 = self._make_linear_pipeline()
        assert compute_topology_hash(p1) == compute_topology_hash(p2)

    def test_changed_edge_target_changes_hash(self) -> None:
        p1 = self._make_linear_pipeline()
        # Change second stage's edge target.
        s2_mod = Stage(
            name="second",
            step=_FakeStep("second"),
            edges=(Edge(label="halt", target="first"),),  # was "halt"
        )
        p2 = Pipeline(
            stages={"first": p1.stages["first"], "second": s2_mod},
            entry="first",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_changed_edge_label_changes_hash(self) -> None:
        p1 = self._make_linear_pipeline()
        s1_mod = Stage(
            name="first",
            step=_FakeStep("first"),
            edges=(Edge(label="finished", target="second"),),  # was "done"
        )
        p2 = Pipeline(
            stages={"first": s1_mod, "second": p1.stages["second"]},
            entry="first",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_changed_edge_kind_changes_hash(self) -> None:
        p1 = self._make_linear_pipeline()
        s1_mod = Stage(
            name="first",
            step=_FakeStep("first"),
            edges=(Edge(label="done", target="second", kind="decision"),),
            # was kind="normal"
        )
        p2 = Pipeline(
            stages={"first": s1_mod, "second": p1.stages["second"]},
            entry="first",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_added_edge_changes_hash(self) -> None:
        p1 = self._make_linear_pipeline()
        s1_mod = Stage(
            name="first",
            step=_FakeStep("first"),
            edges=(
                Edge(label="done", target="second"),
                Edge(label="skip", target="halt"),
            ),
        )
        p2 = Pipeline(
            stages={"first": s1_mod, "second": p1.stages["second"]},
            entry="first",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_removed_edge_changes_hash(self) -> None:
        p1 = self._make_linear_pipeline()
        s1_mod = Stage(
            name="first",
            step=_FakeStep("first"),
            edges=(),  # removed the edge
        )
        p2 = Pipeline(
            stages={"first": s1_mod, "second": p1.stages["second"]},
            entry="first",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)


# ---------------------------------------------------------------------------
# Stage-set sensitivity
# ---------------------------------------------------------------------------


class TestStageSetSensitivity:
    """Adding, removing, or renaming stages changes the hash."""

    def test_added_stage_changes_hash(self) -> None:
        p1 = Pipeline(
            stages={
                "a": Stage(name="a", step=_FakeStep("a"), edges=()),
            },
            entry="a",
        )
        p2 = Pipeline(
            stages={
                "a": Stage(name="a", step=_FakeStep("a"), edges=()),
                "b": Stage(name="b", step=_FakeStep("b"), edges=()),
            },
            entry="a",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_renamed_stage_changes_hash(self) -> None:
        p1 = Pipeline(
            stages={
                "a": Stage(name="a", step=_FakeStep("a"), edges=()),
            },
            entry="a",
        )
        p2 = Pipeline(
            stages={
                "renamed": Stage(name="renamed", step=_FakeStep("renamed"), edges=()),
            },
            entry="renamed",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_changed_entry_changes_hash(self) -> None:
        p1 = Pipeline(
            stages={
                "a": Stage(name="a", step=_FakeStep("a"), edges=()),
                "b": Stage(name="b", step=_FakeStep("b"), edges=()),
            },
            entry="a",
        )
        p2 = Pipeline(
            stages={
                "a": Stage(name="a", step=_FakeStep("a"), edges=()),
                "b": Stage(name="b", step=_FakeStep("b"), edges=()),
            },
            entry="b",
        )
        assert compute_topology_hash(p1) != compute_topology_hash(p2)


# ---------------------------------------------------------------------------
# Vocabulary sensitivity
# ---------------------------------------------------------------------------


class TestVocabularySensitivity:
    """Changing decision or override vocabularies changes the hash."""

    def test_decision_vocabulary_change_changes_hash(self) -> None:
        s1 = Stage(
            name="gate",
            step=_FakeStep("gate"),
            edges=(),
            decision_vocabulary=frozenset({"approve", "reject"}),
        )
        p1 = Pipeline(stages={"gate": s1}, entry="gate")

        s2 = Stage(
            name="gate",
            step=_FakeStep("gate"),
            edges=(),
            decision_vocabulary=frozenset({"approve", "reject", "escalate"}),
        )
        p2 = Pipeline(stages={"gate": s2}, entry="gate")

        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_override_vocabulary_change_changes_hash(self) -> None:
        s1 = Stage(
            name="gate",
            step=_FakeStep("gate"),
            edges=(),
            override_vocabulary=frozenset({"abort"}),
        )
        p1 = Pipeline(stages={"gate": s1}, entry="gate")

        s2 = Stage(
            name="gate",
            step=_FakeStep("gate"),
            edges=(),
            override_vocabulary=frozenset({"abort", "force_proceed"}),
        )
        p2 = Pipeline(stages={"gate": s2}, entry="gate")

        assert compute_topology_hash(p1) != compute_topology_hash(p2)


# ---------------------------------------------------------------------------
# Human-gate topology sensitivity
# ---------------------------------------------------------------------------


class TestHumanGateTopologySensitivity:
    """Human-gate route metadata must participate in topology hashing."""

    def test_human_gate_decision_route_change_changes_hash(self) -> None:
        p1 = _make_human_gate_pipeline()
        p2 = _make_human_gate_pipeline(
            decision_routes={"continue": None, "stop": None}
        )

        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_human_gate_suspension_schema_override_route_change_changes_hash(
        self,
    ) -> None:
        p1 = _make_human_gate_pipeline(
            suspension_schema=_human_gate_suspension_schema(
                override_routes={"force_continue": "continue"}
            )
        )
        p2 = _make_human_gate_pipeline(
            suspension_schema=_human_gate_suspension_schema(
                override_routes={
                    "force_continue": "continue",
                    "force_stop": "halt",
                }
            )
        )

        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_human_gate_decision_vocabulary_change_changes_hash(self) -> None:
        p1 = _make_human_gate_pipeline()
        p2 = _make_human_gate_pipeline(
            decision_vocabulary=frozenset({"continue", "stop", "revise"})
        )

        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_human_gate_override_vocabulary_change_changes_hash(self) -> None:
        p1 = _make_human_gate_pipeline()
        p2 = _make_human_gate_pipeline(
            override_vocabulary=frozenset(
                {"force_continue", "force_stop", "force_revise"}
            )
        )

        assert compute_topology_hash(p1) != compute_topology_hash(p2)


# ---------------------------------------------------------------------------
# Port sensitivity
# ---------------------------------------------------------------------------


class TestPortSensitivity:
    """Changing declared ports changes the hash."""

    def test_added_produces_changes_hash(self) -> None:
        s1 = Stage(name="s", step=_FakeStep("s"), edges=(), produces=())
        p1 = Pipeline(stages={"s": s1}, entry="s")

        s2 = Stage(
            name="s",
            step=_FakeStep("s"),
            edges=(),
            produces=(Port(name="out", content_type="application/json"),),
        )
        p2 = Pipeline(stages={"s": s2}, entry="s")

        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_added_consumes_changes_hash(self) -> None:
        s1 = Stage(name="s", step=_FakeStep("s"), edges=(), consumes=())
        p1 = Pipeline(stages={"s": s1}, entry="s")

        s2 = Stage(
            name="s",
            step=_FakeStep("s"),
            edges=(),
            consumes=(PortRef(port_name="in", content_type="text/plain"),),
        )
        p2 = Pipeline(stages={"s": s2}, entry="s")

        assert compute_topology_hash(p1) != compute_topology_hash(p2)


# ---------------------------------------------------------------------------
# Binding-map sensitivity
# ---------------------------------------------------------------------------


class TestBindingMapSensitivity:
    """The binding map (when present) affects the hash."""

    def test_binding_map_none_vs_present_changes_hash(self) -> None:
        s1 = Stage(name="s", step=_FakeStep("s"), edges=())
        p1 = Pipeline(stages={"s": s1}, entry="s", binding_map=None)
        p2 = Pipeline(stages={"s": s1}, entry="s", binding_map={"k": "v"})
        assert compute_topology_hash(p1) != compute_topology_hash(p2)

    def test_binding_map_value_change_changes_hash(self) -> None:
        s1 = Stage(name="s", step=_FakeStep("s"), edges=())
        p1 = Pipeline(stages={"s": s1}, entry="s", binding_map={"a": {"x": "y"}})
        p2 = Pipeline(stages={"s": s1}, entry="s", binding_map={"a": {"x": "z"}})
        assert compute_topology_hash(p1) != compute_topology_hash(p2)


# ---------------------------------------------------------------------------
# Irrelevant fields do NOT affect the hash
# ---------------------------------------------------------------------------


class TestStepIdentityExcluded:
    """Step identity (callable refs, internal state) must NOT affect hash."""

    def test_different_step_instances_same_hash(self) -> None:
        """Two different step objects with same structural fields → same hash."""
        s1 = Stage(
            name="s",
            step=_FakeStep("s", kind="produce"),
            edges=(Edge(label="done", target="halt"),),
        )
        p1 = Pipeline(stages={"s": s1}, entry="s")

        # Different step instance — structurally equivalent.
        s2 = Stage(
            name="s",
            step=_FakeStep("s", kind="produce"),
            edges=(Edge(label="done", target="halt"),),
        )
        p2 = Pipeline(stages={"s": s2}, entry="s")

        assert compute_topology_hash(p1) == compute_topology_hash(p2)

    def test_resource_bundles_do_not_affect_hash(self) -> None:
        """Pipeline resource_bundles field is excluded from the hash."""
        s1 = Stage(name="s", step=_FakeStep("s"), edges=())
        p1 = Pipeline(stages={"s": s1}, entry="s", resource_bundles=())
        p2 = Pipeline(
            stages={"s": s1},
            entry="s",
            resource_bundles=(object(),),  # different bundles
        )
        assert compute_topology_hash(p1) == compute_topology_hash(p2)

    def test_native_program_does_not_affect_hash(self) -> None:
        """Pipeline native_program field is excluded from the hash."""
        from arnold.pipeline.native.ir import NativeProgram

        s1 = Stage(name="s", step=_FakeStep("s"), edges=())
        p1 = Pipeline(stages={"s": s1}, entry="s", native_program=None)
        p2 = Pipeline(
            stages={"s": s1},
            entry="s",
            native_program=NativeProgram(name="should-not-matter"),
        )
        assert compute_topology_hash(p1) == compute_topology_hash(p2)

    def test_different_native_programs_same_hash(self) -> None:
        """Two different NativeProgram values on same graph → same hash."""
        from arnold.pipeline.native.ir import NativeProgram

        s1 = Stage(name="s", step=_FakeStep("s"), edges=())
        p1 = Pipeline(
            stages={"s": s1},
            entry="s",
            native_program=NativeProgram(name="prog-a"),
        )
        p2 = Pipeline(
            stages={"s": s1},
            entry="s",
            native_program=NativeProgram(
                name="prog-b",
                description="completely different",
            ),
        )
        assert compute_topology_hash(p1) == compute_topology_hash(p2)
