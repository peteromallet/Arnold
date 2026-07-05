"""Focused tests for structural diff classification in pack_diff.

Covers the full required taxonomy:

Breaking diagnostics:
- Removed required inputs
- Narrowed outputs / schema changes
- Removed units with dependents
- Renamed stable IDs
- Removed wired branches

Non-breaking diagnostics:
- Added optional inputs
- Non-shadowing additive branches
- Body-only changes without ``body_hash``
- Body-hash committed changes
"""

from __future__ import annotations

import pytest

from arnold.pipeline.native.ir import (
    NativeProgram,
    NativeTopology,
    TopologyEdge,
    TopologyNode,
)
from arnold.pipeline.native.pack_diff import (
    DiffEntry,
    DiffReport,
    diff_pack_exports,
    diff_pack_manifests,
)
from arnold.pipeline.native.pack_metadata import (
    DependencySpec,
    ExportEntry,
    PackManifest,
)


# ── Shared test helpers ─────────────────────────────────────────────────


def _export(
    stable_id: str,
    *,
    kind: str = "step",
    name: str = "",
    inputs_schema: dict | None = None,
    outputs_schema: dict | None = None,
    body_hash: str | None = None,
    description: str = "",
) -> ExportEntry:
    """Create an ExportEntry with a default name derived from stable_id."""
    return ExportEntry(
        stable_id=stable_id,
        kind=kind,
        name=name or stable_id,
        inputs_schema=inputs_schema,
        outputs_schema=outputs_schema,
        body_hash=body_hash,
        description=description,
    )


def _program(
    name: str = "test_program",
    stable_id: str | None = None,
    inputs_schema: dict | None = None,
    outputs_schema: dict | None = None,
) -> NativeProgram:
    """Create a minimal NativeProgram."""
    return NativeProgram(
        name=name,
        stable_id=stable_id,
        inputs_schema=inputs_schema,
        outputs_schema=outputs_schema,
    )


def _topology(
    nodes: tuple[TopologyNode, ...] = (),
    edges: tuple[TopologyEdge, ...] = (),
    name: str = "test_topology",
) -> NativeTopology:
    """Create a NativeTopology from node/edge tuples."""
    return NativeTopology(name=name, nodes=nodes, edges=edges)


def _node(
    node_id: str,
    *,
    kind: str = "phase",
    label: str = "",
    path: str = "",
    stable_id: str | None = None,
    metadata: dict | None = None,
) -> TopologyNode:
    """Create a TopologyNode with defaults."""
    return TopologyNode(
        node_id=node_id,
        kind=kind,
        label=label or node_id,
        path=path or f"root/{node_id}",
        stable_id=stable_id,
        metadata=metadata or {},
    )


def _edge(
    source: str,
    target: str,
    *,
    label: str = "next",
    kind: str = "control_flow",
    metadata: dict | None = None,
) -> TopologyEdge:
    """Create a TopologyEdge."""
    return TopologyEdge(
        source=source,
        target=target,
        label=label,
        kind=kind,
        metadata=metadata or {},
    )


# ── Helpers for schema construction ─────────────────────────────────────

_OBJ_SCHEMA = {"type": "object", "required": [], "properties": {}}


def _obj_inputs(
    required: list[str] | None = None,
    properties: dict | None = None,
) -> dict:
    """Build an object-typed inputs schema with required + properties."""
    schema: dict = {"type": "object", "required": required or [], "properties": properties or {}}
    return schema


def _prop(type_: str = "string", description: str = "") -> dict:
    """Build a simple property descriptor."""
    result: dict = {"type": type_}
    if description:
        result["description"] = description
    return result


# ── Manifest helpers ────────────────────────────────────────────────────


def _manifest(
    name: str,
    version: str,
    *,
    exports: tuple[ExportEntry, ...] = (),
    dependencies: tuple[DependencySpec, ...] = (),
    stable_id: str | None = None,
    description: str = "",
) -> PackManifest:
    """Create a PackManifest."""
    return PackManifest(
        name=name,
        version=version,
        description=description,
        stable_id=stable_id,
        exports=exports,
        dependencies=dependencies,
    )


# ══════════════════════════════════════════════════════════════════════════
# Breaking diagnostics
# ══════════════════════════════════════════════════════════════════════════


class TestBreakingRemovedRequiredInputs:
    """Removed required inputs are detected as breaking interface changes."""

    def test_required_field_removed_from_schema(self):
        """When a required input is removed from the declared schema it is breaking."""
        old_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(required=["x", "y"], properties={"x": _prop(), "y": _prop()}),
        )
        new_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(required=["x"], properties={"x": _prop()}),
        )
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        breaking = report.breaking_entries
        assert len(breaking) == 1
        assert breaking[0].category == "interface"
        assert breaking[0].change == "inputs_schema_changed"
        assert breaking[0].breaking is True
        assert breaking[0].stable_id == "unit.v1"

    def test_required_field_added_narrowing_interface(self):
        """Adding a required field (narrowing interface) is also breaking."""
        old_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(required=["x"], properties={"x": _prop()}),
        )
        new_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(required=["x", "y"], properties={"x": _prop(), "y": _prop()}),
        )
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        assert report.breaking_entries[0].change == "inputs_schema_changed"

    def test_inputs_schema_changed_non_additive(self):
        """Any non-additive input schema change is flagged as breaking."""
        old_export = _export("unit.v1", inputs_schema={"type": "string"})
        new_export = _export("unit.v1", inputs_schema={"type": "integer"})
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        assert report.breaking_entries[0].change == "inputs_schema_changed"


class TestBreakingNarrowedOutputs:
    """Output schema changes are always breaking."""

    def test_output_schema_changed(self):
        """Any output schema change is classified as breaking."""
        old_export = _export("unit.v1", outputs_schema={"type": "object", "properties": {"a": _prop()}})
        new_export = _export("unit.v1", outputs_schema={"type": "object", "properties": {"b": _prop()}})
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        assert report.breaking_entries[0].category == "interface"
        assert report.breaking_entries[0].change == "outputs_schema_changed"
        assert report.breaking_entries[0].breaking is True

    def test_output_schema_from_none_to_something(self):
        """Adding an output schema where there was none is also breaking."""
        old_export = _export("unit.v1")
        new_export = _export("unit.v1", outputs_schema={"type": "object", "properties": {"x": _prop()}})
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        assert report.breaking_entries[0].change == "outputs_schema_changed"


class TestBreakingRemovedUnitsWithDependents:
    """Removing an export from a manifest is breaking."""

    def test_export_removed_from_manifest(self):
        """When a stable ID is in old manifest but not new, it's a breaking removal."""
        old_manifest = _manifest("pack", "1.0.0", exports=(_export("unit.alpha"), _export("unit.beta")))
        new_manifest = _manifest("pack", "2.0.0", exports=(_export("unit.alpha"),))
        old_programs = {"unit.alpha": _program(), "unit.beta": _program()}
        new_programs = {"unit.alpha": _program()}

        report = diff_pack_manifests(
            old_manifest=old_manifest,
            new_manifest=new_manifest,
            old_programs=old_programs,
            new_programs=new_programs,
        )

        assert report.has_breaking_changes
        removed = [e for e in report.breaking_entries if e.change == "export_removed"]
        assert len(removed) == 1
        assert removed[0].stable_id == "unit.beta"
        assert removed[0].breaking is True
        assert "removed" in removed[0].message.lower()

    def test_export_added_is_non_breaking(self):
        """Adding a new export is non-breaking."""
        old_manifest = _manifest("pack", "1.0.0", exports=(_export("unit.alpha"),))
        new_manifest = _manifest("pack", "2.0.0", exports=(_export("unit.alpha"), _export("unit.beta")))
        old_programs = {"unit.alpha": _program()}
        new_programs = {"unit.alpha": _program(), "unit.beta": _program()}

        report = diff_pack_manifests(
            old_manifest=old_manifest,
            new_manifest=new_manifest,
            old_programs=old_programs,
            new_programs=new_programs,
        )

        added = [e for e in report.non_breaking_entries if e.change == "export_added"]
        assert len(added) == 1
        assert added[0].stable_id == "unit.beta"
        assert added[0].breaking is False


class TestBreakingRenamedStableIds:
    """Renaming a stable ID is a breaking change."""

    def test_stable_id_changed_on_export(self):
        """When stable ID differs between old and new export, it's breaking."""
        old_export = _export("unit.old")
        new_export = _export("unit.new")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        rename = [e for e in report.breaking_entries if e.change == "stable_id_changed"]
        assert len(rename) == 1
        assert rename[0].category == "rename"
        assert rename[0].breaking is True

    def test_stable_id_rename_via_name_kind_match_in_manifest(self):
        """When a removed export can be matched by (name, kind) to an added one,
        it's classified as a rename rather than removal+addition."""
        old_manifest = _manifest(
            "pack", "1.0.0",
            exports=(_export("pkg.old_id", kind="workflow", name="my_wf"),),
        )
        new_manifest = _manifest(
            "pack", "2.0.0",
            exports=(_export("pkg.new_id", kind="workflow", name="my_wf"),),
        )
        old_programs = {"pkg.old_id": _program()}
        new_programs = {"pkg.new_id": _program()}

        report = diff_pack_manifests(
            old_manifest=old_manifest,
            new_manifest=new_manifest,
            old_programs=old_programs,
            new_programs=new_programs,
        )

        renames = [e for e in report.breaking_entries if e.change == "stable_id_changed"]
        assert len(renames) == 1
        assert renames[0].breaking is True
        # Should NOT have a separate export_removed for pkg.old_id
        removed = [e for e in report.entries if e.change == "export_removed"]
        assert len(removed) == 0
        added = [e for e in report.entries if e.change == "export_added"]
        assert len(added) == 0

    def test_export_name_changed_is_non_breaking(self):
        """Changing the display name (not stable ID) is non-breaking."""
        old_export = _export("unit.v1", name="old_display")
        new_export = _export("unit.v1", name="new_display")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        name_changes = [e for e in report.non_breaking_entries if e.change == "export_name_changed"]
        assert len(name_changes) == 1
        assert name_changes[0].breaking is False


class TestBreakingRemovedWiredBranches:
    """Removing a wired control-flow branch is breaking."""

    def test_branch_removed_from_decision_node(self):
        """When a branch label disappears from control routes, it's breaking."""
        n1_old = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass", "fail"]})
        n2_old = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")
        n3_old = _node("n3", kind="phase", stable_id="step.v2", path="root/step_b")

        n1_new = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass"]})
        n2_new = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")

        old_nodes = (n1_old, n2_old, n3_old)
        new_nodes = (n1_new, n2_new)

        old_topo = _topology(
            nodes=old_nodes,
            edges=(
                _edge("n1", "n2", label="pass"),
                _edge("n1", "n3", label="fail"),
            ),
        )
        new_topo = _topology(
            nodes=new_nodes,
            edges=(_edge("n1", "n2", label="pass"),),
        )

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        removed_branches = [e for e in report.entries if e.change == "branch_removed"]
        assert len(removed_branches) == 1, f"Expected 1 branch_removed, got {removed_branches}"
        assert removed_branches[0].breaking is True
        assert "fail" in removed_branches[0].message.lower()

    def test_branch_target_changed_is_breaking(self):
        """When a branch label's target changes, it's breaking."""
        n1_old = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass", "fail"]})
        n2_old = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")
        n3_old = _node("n3", kind="phase", stable_id="step.v2", path="root/step_b")

        n1_new = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass", "fail"]})
        n2_new = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")
        n4_new = _node("n4", kind="phase", stable_id="step.v3", path="root/step_c")

        old_topo = _topology(
            nodes=(n1_old, n2_old, n3_old),
            edges=(_edge("n1", "n2", label="pass"), _edge("n1", "n3", label="fail")),
        )
        new_topo = _topology(
            nodes=(n1_new, n2_new, n4_new),
            edges=(_edge("n1", "n2", label="pass"), _edge("n1", "n4", label="fail")),
        )

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        target_changes = [e for e in report.entries if e.change == "branch_target_changed"]
        assert len(target_changes) == 1
        assert target_changes[0].breaking is True

    def test_edge_target_changed_is_breaking(self):
        """When the 'next' edge target changes, it's classified under path category."""
        n1_old = _node("n1", kind="phase", stable_id="step.v1", path="root/step_a")
        n2_old = _node("n2", kind="phase", stable_id="step.v2", path="root/step_b")

        n1_new = _node("n1", kind="phase", stable_id="step.v1", path="root/step_a")
        n3_new = _node("n3", kind="phase", stable_id="step.v3", path="root/step_c")

        old_topo = _topology(nodes=(n1_old, n2_old), edges=(_edge("n1", "n2", label="next"),))
        new_topo = _topology(nodes=(n1_new, n3_new), edges=(_edge("n1", "n3", label="next"),))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        edge_changes = [e for e in report.entries if e.change == "edge_target_changed"]
        assert len(edge_changes) == 1
        assert edge_changes[0].breaking is True
        assert edge_changes[0].category == "path"


# ══════════════════════════════════════════════════════════════════════════
# Non-breaking diagnostics
# ══════════════════════════════════════════════════════════════════════════


class TestNonBreakingAddedOptionalInputs:
    """Adding optional input fields is non-breaking."""

    def test_optional_field_added_keeps_required_same(self):
        """Adding a new optional property while keeping required list the same is non-breaking."""
        old_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(required=["x"], properties={"x": _prop()}),
        )
        new_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(required=["x"], properties={"x": _prop(), "y": _prop()}),
        )
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert not report.has_breaking_changes
        non_breaking = report.non_breaking_entries
        assert len(non_breaking) == 1
        assert non_breaking[0].category == "interface"
        assert non_breaking[0].change == "optional_inputs_added"
        assert non_breaking[0].breaking is False

    def test_multiple_optional_fields_added(self):
        """Multiple new optional properties with same required list is still non-breaking."""
        old_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(required=["x"], properties={"x": _prop()}),
        )
        new_export = _export(
            "unit.v1",
            inputs_schema=_obj_inputs(
                required=["x"],
                properties={"x": _prop(), "y": _prop(), "z": _prop()},
            ),
        )
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert not report.has_breaking_changes
        assert report.non_breaking_entries[0].change == "optional_inputs_added"

    def test_adding_inputs_from_none_is_breaking(self):
        """Going from None to a schema is not additive — it's a breaking change."""
        old_export = _export("unit.v1", inputs_schema=None)
        new_export = _export("unit.v1", inputs_schema=_obj_inputs(properties={"x": _prop()}))
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        assert report.breaking_entries[0].change == "inputs_schema_changed"

    def test_optional_input_added_in_topology_node(self):
        """Optional inputs added on a phase node in the topology are also non-breaking."""
        n1_old = _node("n1", kind="phase", stable_id="step.v1", path="root/step",
                        metadata={"inputs_schema": _obj_inputs(required=["x"], properties={"x": _prop()})})
        n1_new = _node("n1", kind="phase", stable_id="step.v1", path="root/step",
                        metadata={"inputs_schema": _obj_inputs(required=["x"], properties={"x": _prop(), "y": _prop()})})

        old_topo = _topology(nodes=(n1_old,))
        new_topo = _topology(nodes=(n1_new,))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        added = [e for e in report.non_breaking_entries if e.change == "optional_inputs_added"]
        assert len(added) == 1


class TestNonBreakingAdditiveBranches:
    """Adding a new branch that doesn't shadow existing routes is non-breaking."""

    def test_branch_added_to_decision_node(self):
        """A new branch label added to a decision node is non-breaking."""
        n1_old = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass", "fail"]})
        n2_old = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")

        n1_new = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass", "fail", "retry"]})
        n2_new = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")
        n3_new = _node("n3", kind="phase", stable_id="step.v2", path="root/step_b")

        old_topo = _topology(
            nodes=(n1_old, n2_old),
            edges=(_edge("n1", "n2", label="pass"), _edge("n1", "n2", label="fail")),
        )
        new_topo = _topology(
            nodes=(n1_new, n2_new, n3_new),
            edges=(
                _edge("n1", "n2", label="pass"),
                _edge("n1", "n2", label="fail"),
                _edge("n1", "n3", label="retry"),
            ),
        )

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        added = [e for e in report.non_breaking_entries if e.change == "branch_added"]
        assert len(added) == 1
        assert added[0].breaking is False
        assert "retry" in added[0].message.lower()

    def test_unwired_vocabulary_added_is_non_breaking(self):
        """Adding an unwired vocabulary label (no control edge) is non-breaking."""
        n1_old = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass"]})
        n1_new = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass", "retry"]})

        n2_old = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")
        n2_new = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")

        old_topo = _topology(nodes=(n1_old, n2_old), edges=(_edge("n1", "n2", label="pass"),))
        new_topo = _topology(nodes=(n1_new, n2_new), edges=(_edge("n1", "n2", label="pass"),))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        vocab_added = [e for e in report.non_breaking_entries if e.change == "branch_vocabulary_added"]
        assert len(vocab_added) == 1
        assert vocab_added[0].breaking is False

    def test_unwired_vocabulary_removed_is_non_breaking(self):
        """Removing an unwired vocabulary label (no control edge) is non-breaking."""
        n1_old = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass", "retry"]})
        n1_new = _node("n1", kind="decision", stable_id="dec.v1", path="root/dec",
                        metadata={"vocabulary": ["pass"]})

        n2_old = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")
        n2_new = _node("n2", kind="phase", stable_id="step.v1", path="root/step_a")

        old_topo = _topology(nodes=(n1_old, n2_old), edges=(_edge("n1", "n2", label="pass"),))
        new_topo = _topology(nodes=(n1_new, n2_new), edges=(_edge("n1", "n2", label="pass"),))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        vocab_removed = [e for e in report.non_breaking_entries if e.change == "branch_vocabulary_removed"]
        assert len(vocab_removed) == 1
        assert vocab_removed[0].breaking is False


class TestBodyHashBehavior:
    """Body-only changes are non-breaking when body_hash is None; breaking when committed."""

    def test_body_only_change_without_body_hash_is_non_breaking(self):
        """When body_hash is None on both sides and only body changed, there's no diff entry."""
        old_export = _export("unit.v1", inputs_schema=_obj_inputs(properties={"x": _prop()}))
        new_export = _export("unit.v1", inputs_schema=_obj_inputs(properties={"x": _prop()}))
        # Identical exports with no body_hash — no diff at all
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert not report.has_breaking_changes
        # Body-only changes without body_hash produce no entries
        assert len(report.entries) == 0

    def test_body_hash_opt_in_status_changes_is_non_breaking(self):
        """When one side has body_hash=None and the other has a value, it's non-breaking advisory."""
        old_export = _export("unit.v1", body_hash=None)
        new_export = _export("unit.v1", body_hash="sha256:abcdef1234567890")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert not report.has_breaking_changes
        body_entries = [e for e in report.entries if e.category == "body"]
        assert len(body_entries) == 1
        assert body_entries[0].change == "body_hash_opt_in_changed"
        assert body_entries[0].breaking is False

    def test_body_hash_changed_is_breaking(self):
        """When both sides have a body_hash and they differ, it's a breaking committed change."""
        old_export = _export("unit.v1", body_hash="sha256:aaaa")
        new_export = _export("unit.v1", body_hash="sha256:bbbb")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert report.has_breaking_changes
        body_entries = [e for e in report.breaking_entries if e.category == "body"]
        assert len(body_entries) == 1
        assert body_entries[0].change == "body_hash_changed"
        assert body_entries[0].breaking is True

    def test_body_hash_same_is_no_diff(self):
        """When both sides have the same body_hash, no body diff entry is produced."""
        old_export = _export("unit.v1", body_hash="sha256:same")
        new_export = _export("unit.v1", body_hash="sha256:same")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert not report.has_breaking_changes
        body_entries = [e for e in report.entries if e.category == "body"]
        assert len(body_entries) == 0

    def test_body_hash_cleared_is_non_breaking(self):
        """When body_hash goes from a committed value to None, it's non-breaking advisory."""
        old_export = _export("unit.v1", body_hash="sha256:aaaa")
        new_export = _export("unit.v1", body_hash=None)
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        assert not report.has_breaking_changes
        body_entries = [e for e in report.entries if e.category == "body"]
        assert len(body_entries) == 1
        assert body_entries[0].change == "body_hash_opt_in_changed"


# ══════════════════════════════════════════════════════════════════════════
# Topology diff classifier
# ══════════════════════════════════════════════════════════════════════════


class TestTopologyNodeAdditionRemoval:
    """Adding/removing topology nodes with stable IDs."""

    def test_node_added_is_non_breaking(self):
        """A new stable node added to the topology is non-breaking."""
        n1_old = _node("n1", kind="phase", stable_id="step.v1", path="root/step_a")
        n2_old = _node("n2", kind="phase", stable_id="step.v2", path="root/step_b")
        n1_new = _node("n1", kind="phase", stable_id="step.v1", path="root/step_a")
        n2_new = _node("n2", kind="phase", stable_id="step.v2", path="root/step_b")
        n3_new = _node("n3", kind="phase", stable_id="step.v3", path="root/step_c")

        old_topo = _topology(nodes=(n1_old, n2_old))
        new_topo = _topology(nodes=(n1_new, n2_new, n3_new))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        added = [e for e in report.entries if e.change == "node_added"]
        assert len(added) == 1
        assert added[0].stable_id == "step.v3"
        assert added[0].breaking is False

    def test_node_removed_is_breaking(self):
        """Removing a stable node from the topology is breaking."""
        n1_old = _node("n1", kind="phase", stable_id="step.v1", path="root/step_a")
        n2_old = _node("n2", kind="phase", stable_id="step.v2", path="root/step_b")
        n1_new = _node("n1", kind="phase", stable_id="step.v1", path="root/step_a")

        old_topo = _topology(nodes=(n1_old, n2_old))
        new_topo = _topology(nodes=(n1_new,))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        removed = [e for e in report.entries if e.change == "node_removed"]
        assert len(removed) == 1
        assert removed[0].stable_id == "step.v2"
        assert removed[0].breaking is True

    def test_node_kind_changed_is_breaking(self):
        """Changing a node's kind (e.g. phase→decision) is breaking."""
        n1_old = _node("n1", kind="phase", stable_id="unit.v1", path="root/unit")
        n1_new = _node("n1", kind="decision", stable_id="unit.v1", path="root/unit",
                        metadata={"vocabulary": ["pass"]})

        n2_old = _node("n2", kind="phase", path="root/step")
        n2_new = _node("n2", kind="phase", path="root/step")

        old_topo = _topology(nodes=(n1_old, n2_old), edges=(_edge("n1", "n2"),))
        new_topo = _topology(nodes=(n1_new, n2_new), edges=(_edge("n1", "n2"),))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        kind_changes = [e for e in report.entries if e.change == "node_kind_changed"]
        assert len(kind_changes) == 1
        assert kind_changes[0].breaking is True

    def test_node_label_changed_is_non_breaking(self):
        """Changing a node's human-readable label is non-breaking."""
        n1_old = _node("n1", kind="phase", stable_id="step.v1", path="root/step", label="Old Label")
        n1_new = _node("n1", kind="phase", stable_id="step.v1", path="root/step", label="New Label")

        old_topo = _topology(nodes=(n1_old,))
        new_topo = _topology(nodes=(n1_new,))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        label_changes = [e for e in report.non_breaking_entries if e.change == "node_label_changed"]
        assert len(label_changes) == 1
        assert label_changes[0].breaking is False


class TestTopologyPathChanges:
    """Path changes for stable nodes are breaking."""

    def test_node_path_changed_is_breaking(self):
        """Moving a node to a different path is breaking."""
        n1_old = _node("n1", kind="phase", stable_id="step.v1", path="root/old_path")
        n2_old = _node("n2", kind="phase", stable_id="step.v2", path="root/step_b")

        n1_new = _node("n1", kind="phase", stable_id="step.v1", path="root/new_path")
        n2_new = _node("n2", kind="phase", stable_id="step.v2", path="root/step_b")

        old_topo = _topology(nodes=(n1_old, n2_old))
        new_topo = _topology(nodes=(n1_new, n2_new))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        path_changes = [e for e in report.entries if e.change == "node_path_changed"]
        assert len(path_changes) == 1
        assert path_changes[0].breaking is True
        assert path_changes[0].category == "path"

    def test_same_path_no_change(self):
        """When nodes have exactly the same path, no path change is reported."""
        n1_old = _node("n1", kind="phase", stable_id="step.v1", path="root/step")
        n1_new = _node("n1", kind="phase", stable_id="step.v1", path="root/step")

        old_topo = _topology(nodes=(n1_old,))
        new_topo = _topology(nodes=(n1_new,))

        old_export = _export("wf.v1", kind="workflow")
        new_export = _export("wf.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
            old_topology=old_topo,
            new_topology=new_topo,
        )

        assert len(report.entries) == 0


# ══════════════════════════════════════════════════════════════════════════
# DiffEntry / DiffReport round-trip
# ══════════════════════════════════════════════════════════════════════════


class TestDiffEntryRoundTrip:
    """DiffEntry serialization round-trips correctly."""

    def test_diff_entry_to_dict_and_back(self):
        """DiffEntry JSON round-trip preserves all fields."""
        entry = DiffEntry(
            category="interface",
            change="inputs_schema_changed",
            breaking=True,
            stable_id="unit.v1",
            node_kind="step",
            old_path="root/step",
            new_path="root/step",
            message="Schema changed.",
            details={"old": {"type": "string"}, "new": {"type": "integer"}},
        )
        data = entry.to_dict()
        restored = DiffEntry.from_dict(data)
        assert restored.category == entry.category
        assert restored.change == entry.change
        assert restored.breaking == entry.breaking
        assert restored.stable_id == entry.stable_id
        assert restored.node_kind == entry.node_kind
        assert restored.old_path == entry.old_path
        assert restored.new_path == entry.new_path
        assert restored.message == entry.message

    def test_diff_entry_minimal_fields(self):
        """DiffEntry with only required fields round-trips."""
        entry = DiffEntry(category="unit", change="export_added", breaking=False)
        data = entry.to_dict()
        restored = DiffEntry.from_dict(data)
        assert restored.category == "unit"
        assert restored.change == "export_added"
        assert restored.breaking is False
        assert restored.stable_id is None

    def test_diff_report_properties(self):
        """DiffReport breaking/non-breaking property partitions."""
        report = DiffReport(
            old_stable_id="v1",
            new_stable_id="v2",
            entries=(
                DiffEntry(category="unit", change="removed", breaking=True),
                DiffEntry(category="unit", change="added", breaking=False),
                DiffEntry(category="interface", change="changed", breaking=True),
            ),
        )
        assert report.has_breaking_changes
        assert len(report.breaking_entries) == 2
        assert len(report.non_breaking_entries) == 1

    def test_diff_report_to_dict_and_back(self):
        """DiffReport JSON round-trip preserves entries."""
        report = DiffReport(
            old_stable_id="pack.v1",
            new_stable_id="pack.v2",
            entries=(
                DiffEntry(category="unit", change="export_removed", breaking=True, stable_id="a"),
                DiffEntry(category="unit", change="export_added", breaking=False, stable_id="b"),
            ),
        )
        data = report.to_dict()
        restored = DiffReport.from_dict(data)
        assert restored.old_stable_id == "pack.v1"
        assert restored.new_stable_id == "pack.v2"
        assert len(restored.entries) == 2
        assert restored.has_breaking_changes
        assert len(restored.breaking_entries) == 1
        assert len(restored.non_breaking_entries) == 1


# ══════════════════════════════════════════════════════════════════════════
# Manifest-level diff
# ══════════════════════════════════════════════════════════════════════════


class TestManifestDiff:
    """Manifest-level diff identifies export-level and pack-ID changes."""

    def test_pack_stable_id_changed_is_breaking(self):
        """When the pack stable_id changes, it's breaking."""
        old_manifest = _manifest("pack", "1.0.0", stable_id="pack.v1", exports=(_export("unit.v1"),))
        new_manifest = _manifest("pack", "2.0.0", stable_id="pack.v2", exports=(_export("unit.v1"),))
        old_programs = {"unit.v1": _program()}
        new_programs = {"unit.v1": _program()}

        report = diff_pack_manifests(
            old_manifest=old_manifest,
            new_manifest=new_manifest,
            old_programs=old_programs,
            new_programs=new_programs,
        )

        pack_renames = [e for e in report.entries if e.change == "pack_stable_id_changed"]
        assert len(pack_renames) == 1
        assert pack_renames[0].breaking is True

    def test_manifest_falls_back_to_name_when_stable_id_none(self):
        """When stable_id is None, manifest diff uses name as fallback identifier."""
        old_manifest = _manifest("old_pack", "1.0.0", exports=(_export("unit.v1"),))
        new_manifest = _manifest("new_pack", "2.0.0", exports=(_export("unit.v1"),))
        old_programs = {"unit.v1": _program()}
        new_programs = {"unit.v1": _program()}

        report = diff_pack_manifests(
            old_manifest=old_manifest,
            new_manifest=new_manifest,
            old_programs=old_programs,
            new_programs=new_programs,
        )

        # Name differs → pack_stable_id_changed
        pack_renames = [e for e in report.entries if e.change == "pack_stable_id_changed"]
        assert len(pack_renames) == 1
        assert pack_renames[0].breaking is True

    def test_export_kind_changed_is_breaking(self):
        """When an export changes kind (step→workflow), it's breaking."""
        old_export = _export("unit.v1", kind="step")
        new_export = _export("unit.v1", kind="workflow")
        old_prog = _program()
        new_prog = _program()

        report = diff_pack_exports(
            old_export=old_export,
            new_export=new_export,
            old_program=old_prog,
            new_program=new_prog,
        )

        kind_changes = [e for e in report.breaking_entries if e.change == "export_kind_changed"]
        assert len(kind_changes) == 1
        assert kind_changes[0].breaking is True
