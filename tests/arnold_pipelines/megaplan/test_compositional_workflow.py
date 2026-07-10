"""Behavioral scenarios for the canonical Megaplan workflow shell."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from arnold.execution import ExecutionRegistries, ExecutionState, run
from arnold.execution.backend import NodeOutcome, NodeState
from arnold.execution.registries import EffectRegistry
from arnold.kernel import read_event_journal
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.pipeline import build_pipeline
from arnold_pipelines.megaplan.workflows import components as workflow_components
from arnold_pipelines.megaplan.workflows import planning as workflow_planning
from tests.arnold.execution.conftest import FakeBackend

# ── M2 routing-validator and authoring-boundary imports ───────────────────
from arnold.pipeline.native import validate_pipeline_purity
from arnold.pipeline.native.ir import NativeProgram


class _BranchSequenceBackend(FakeBackend):
    """Fake backend that chooses route IDs in the supplied order."""

    def __init__(self, *, sequences: dict[str, list[str]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sequences = {node_id: list(edge_ids) for node_id, edge_ids in sequences.items()}

    def _select_branch(self, coordinate, node, edges, context):
        sequence = self._sequences.get(node.id)
        if sequence:
            return sequence.pop(0)
        return super()._select_branch(coordinate, node, edges, context)


class _NoopEffectHandler:
    def execute(
        self,
        effect_id: str,
        *,
        route: str,
        payload: dict[str, Any],
        idempotency_key: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "effect_id": effect_id,
            "route": route,
            "idempotency_key": idempotency_key,
        }


def _registries() -> ExecutionRegistries:
    effects = EffectRegistry()
    handler = _NoopEffectHandler()
    for effect_id in (
        "artifact.execute.checkpoint",
        "artifact.execute.receipt",
        "artifact.review.output",
        "artifact.review.receipt",
        "override.add_note",
        "override.set_model",
        "override.set_profile",
        "override.set_robustness",
        "override.set_vendor",
    ):
        effects.register(effect_id, handler)
    return ExecutionRegistries(effects=effects)


def _manifest():
    return compile_pipeline(build_pipeline())


def _completed_node_refs(tmp_path: Path) -> list[str]:
    return [
        event.payload["node_ref"]
        for event in read_event_journal(tmp_path)
        if event.kind == "node_completed" and event.payload.get("child_key") is None
    ]


def _branch_selections(tmp_path: Path) -> dict[str, str]:
    return {
        event.payload["node_ref"]: event.payload["edge_id"]
        for event in read_event_journal(tmp_path)
        if event.kind == "branch_selected"
    }


def _resolve_component(ref: str) -> Any:
    module_name, export_name = ref.split(":", 1)
    module = import_module(module_name)
    return getattr(module, export_name)


class TestCompositionalWorkflowScenarios:
    def test_proceed_path_reaches_review_and_done(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(sequences={"gate": ["gate:finalize"]})

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "finalize",
            "execute",
            "review",
            "halt",
        ]

    def test_iterate_route_reaches_revise_before_looping(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:revise"],
                "revise": ["revise:critique"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == ["prep", "plan", "critique", "gate", "revise"]
        assert _branch_selections(tmp_path)["revise"] == "revise:critique"

    def test_tiebreaker_path_promotes_back_to_finalize(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:tiebreaker"],
                "tiebreaker_decide": ["tiebreaker_decide:finalize"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "tiebreaker_run",
            "tiebreaker_decide",
            "finalize",
            "execute",
            "review",
            "halt",
        ]

    def test_escalation_path_routes_through_override_then_force_proceed(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:override"],
                "override": ["override:finalize"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "override",
            "finalize",
            "execute",
            "review",
            "halt",
        ]

    def test_execute_review_rework_path_returns_to_revise(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(
            sequences={
                "gate": ["gate:finalize"],
                "review": ["review:revise"],
                "revise": ["revise:critique"],
            }
        )

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == [
            "prep",
            "plan",
            "critique",
            "gate",
            "finalize",
            "execute",
            "review",
            "revise",
        ]

    def test_human_gate_continue_resumes_into_proceed_path(self, tmp_path: Path) -> None:
        suspend_backend = FakeBackend(
            node_behaviors={
                "gate": NodeOutcome(
                    state=NodeState.SUSPENDED,
                    suspension_route_id="gate:human",
                ),
            }
        )
        first = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=suspend_backend,
        )

        assert first.state is ExecutionState.SUSPENDED
        assert first.resume_cursor is not None

        resume_backend = _BranchSequenceBackend(
            run_id="run:resume",
            reentry_id="resume",
            sequences={"gate": ["gate:finalize"]},
        )
        second = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=resume_backend,
            resume_cursor=first.resume_cursor,
        )

        assert second.state is ExecutionState.COMPLETED
        assert any(event.kind == "node_resumed" for event in read_event_journal(tmp_path))
        assert _completed_node_refs(tmp_path)[-4:] == ["finalize", "execute", "review", "halt"]

    def test_abort_path_stops_at_halt(self, tmp_path: Path) -> None:
        backend = _BranchSequenceBackend(sequences={"gate": ["gate:halt"]})

        result = run(
            _manifest(),
            artifact_root=tmp_path,
            registries=_registries(),
            backend=backend,
        )

        assert result.state is ExecutionState.COMPLETED
        assert _completed_node_refs(tmp_path) == ["prep", "plan", "critique", "gate", "halt"]


# ── M2 Routing Validator Compatibility Tests ──────────────────────────────


class TestMegaplanRoutingValidatorCompatibility:
    """Assert that the canonical Megaplan pipeline satisfies the M2
    routing-purity validator and exposes the expected static route
    topology carriers without requiring any semantic rewrite of
    workflow.pypeline for this milestone."""

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _native_program() -> NativeProgram:
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        shell = build_and_compile_pipeline()
        native = shell.native_program
        assert isinstance(native, NativeProgram), (
            f"native_program must be NativeProgram, got {type(native).__name__}"
        )
        return native

    # ── purity validation ─────────────────────────────────────────────

    def test_native_program_validates_cleanly(self) -> None:
        """build_pipeline().native_program must produce a clean
        RoutingPurityReport — zero diagnostics."""
        program = self._native_program()
        report = validate_pipeline_purity(program)

        assert report.ok, (
            f"Routing-purity report must be clean; got "
            f"{len(report.diagnostics)} diagnostic(s): "
            f"{[d.code for d in report.diagnostics]}"
        )

    # ── route topology structure ──────────────────────────────────────

    def test_routing_topology_is_nonempty_dict(self) -> None:
        """NativeProgram.routing_topology must be a non-empty dict with
        'nodes' and 'routes' keys."""
        program = self._native_program()
        topology = program.routing_topology

        assert isinstance(topology, dict), (
            f"routing_topology must be dict, got {type(topology).__name__}"
        )
        assert topology, "routing_topology must be non-empty"
        assert "nodes" in topology, "routing_topology must have 'nodes' key"
        assert "routes" in topology, "routing_topology must have 'routes' key"

    def test_topology_node_count_matches_canonical_steps(self) -> None:
        """The 12 canonical Megaplan steps must each appear as a node
        in the routing topology."""
        program = self._native_program()
        nodes = program.routing_topology["nodes"]

        assert len(nodes) == 12, (
            f"Expected 12 topology nodes, got {len(nodes)}"
        )
        node_names = {n["name"] for n in nodes}
        expected = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker_run", "tiebreaker_decide", "finalize",
            "execute", "review", "halt", "override",
        }
        assert node_names == expected, (
            f"Topology node names mismatch: "
            f"missing={expected - node_names}, extra={node_names - expected}"
        )

    # ── gate route carriers ───────────────────────────────────────────

    def test_gate_route_carriers_in_topology(self) -> None:
        """Gate must expose proceed (→finalize), iterate (→revise),
        tiebreaker (→tiebreaker_run), escalate (→override), abort
        (→halt), and suspend (→halt) route carriers."""
        program = self._native_program()
        routes = program.routing_topology["routes"]

        gate_routes = [r for r in routes if r["source"] == "gate"]
        gate_labels = {(r["label"], r["target"]) for r in gate_routes}

        expected = {
            ("proceed", "finalize"),
            ("iterate", "revise"),
            ("tiebreaker", "tiebreaker_run"),
            ("escalate", "override"),
            ("abort", "halt"),
            ("suspend", "halt"),
        }
        missing = expected - gate_labels
        assert not missing, (
            f"Gate missing expected route carriers: {missing}"
        )

    def test_gate_all_routes_reference_known_targets(self) -> None:
        """Every gate route target must be a known node in the topology."""
        program = self._native_program()
        node_names = {n["name"] for n in program.routing_topology["nodes"]}
        gate_routes = [
            r for r in program.routing_topology["routes"]
            if r["source"] == "gate"
        ]
        for route in gate_routes:
            target = route["target"]
            assert target in node_names or target == "halt", (
                f"Gate route target '{target}' not in known nodes: {node_names}"
            )

    # ── tiebreaker route carriers ─────────────────────────────────────

    def test_tiebreaker_route_carriers_in_topology(self) -> None:
        """Tiebreaker_decide must expose proceed (→finalize) and
        escalate (→override) route carriers."""
        program = self._native_program()
        routes = program.routing_topology["routes"]

        tb_routes = [r for r in routes if r["source"] == "tiebreaker_decide"]
        tb_labels = {(r["label"], r["target"]) for r in tb_routes}

        assert ("proceed", "finalize") in tb_labels, (
            f"Tiebreaker missing 'proceed → finalize' carrier; got {tb_labels}"
        )
        assert ("escalate", "override") in tb_labels, (
            f"Tiebreaker missing 'escalate → override' carrier; got {tb_labels}"
        )

    # ── review route carriers ─────────────────────────────────────────

    def test_review_route_carriers_in_topology(self) -> None:
        """Review must expose rework (→revise) route carrier."""
        program = self._native_program()
        routes = program.routing_topology["routes"]

        review_routes = [r for r in routes if r["source"] == "review"]
        review_labels = {(r["label"], r["target"]) for r in review_routes}

        assert ("rework", "revise") in review_labels, (
            f"Review missing 'rework → revise' carrier; got {review_labels}"
        )

    # ── override route carriers ───────────────────────────────────────

    def test_override_route_carriers_in_topology(self) -> None:
        """Override must expose force_proceed (→finalize) and
        replan (→revise) route carriers."""
        program = self._native_program()
        routes = program.routing_topology["routes"]

        override_routes = [r for r in routes if r["source"] == "override"]
        override_labels = {(r["label"], r["target"]) for r in override_routes}

        assert ("force_proceed", "finalize") in override_labels, (
            f"Override missing 'force_proceed → finalize' carrier; got {override_labels}"
        )
        assert ("replan", "revise") in override_labels, (
            f"Override missing 'replan → revise' carrier; got {override_labels}"
        )

    # ── workflow.pypeline semantic stability ──────────────────────────

    def test_workflow_dsl_compiles_to_same_canonical_steps(self) -> None:
        """workflow.pypeline must still compile to the same 12 canonical DSL
        steps — proving no semantic rewrite was needed for this milestone."""
        pipeline = build_pipeline()
        steps = pipeline.steps
        assert len(steps) == 12, (
            f"Canonical DSL must have 12 steps; got {len(steps)}"
        )

    def test_compatibility_shell_instruction_count_matches_dsl(self) -> None:
        """The native compatibility shell must have exactly as many
        instructions as the DSL has steps."""
        program = self._native_program()
        pipeline = build_pipeline()

        assert len(program.instructions) == len(pipeline.steps), (
            f"Native program has {len(program.instructions)} instructions "
            f"but DSL has {len(pipeline.steps)} steps"
        )

    def test_workflow_routes_are_fully_captured_in_topology(self) -> None:
        """Every DSL route must have a corresponding entry in the
        routing topology with matching source, label, and target."""
        program = self._native_program()
        pipeline = build_pipeline()

        topology_routes = {
            (r["source"], r["label"], r["target"])
            for r in program.routing_topology["routes"]
        }

        dsl_routes = set()
        for route in pipeline.routes:
            dsl_routes.add((route.source, route.label, route.target))

        missing = dsl_routes - topology_routes
        assert not missing, (
            f"DSL routes not captured in routing topology: {missing}"
        )

    def test_canonical_authored_source_keeps_dynamic_maps_and_child_call_sites_visible(self) -> None:
        lowered = lower_workflow_file(workflow_planning.AUTHORING_SOURCE_PATH)

        dynamic_map_ids = [step.id for step in lowered.steps if step.kind == "parallel_map"]
        child_workflow_ids = [step.id for step in lowered.steps if step.kind == "subpipeline"]

        assert dynamic_map_ids == [
            "critique-fanout",
            "execute-batches",
            "review-fan-in",
            "tiebreaker-execute-batches",
        ]
        assert child_workflow_ids == ["tiebreaker"]

    def test_canonical_authored_contracts_expose_review_and_execute_hidden_routes(self) -> None:
        execute_contract = _resolve_component(
            "arnold_pipelines.megaplan.workflows.components:SOURCE_EXECUTE_BATCH_WORKFLOW"
        ).metadata["topology_contract"]
        review_contract = _resolve_component(
            "arnold_pipelines.megaplan.workflows.components:SOURCE_REVIEW_PANEL_WORKFLOW"
        ).metadata["topology_contract"]
        tiebreaker_contract = _resolve_component(
            "arnold_pipelines.megaplan.workflows.components:SOURCE_TIEBREAKER_WORKFLOW"
        ).metadata["topology_contract"]

        assert execute_contract["approval_gate"] == {
            "required_ref": "state.meta.user_approved_gate",
            "confirmation_ref": "args.confirm_destructive",
        }
        assert {
            (route["route_signal"], route["target_ref"])
            for route in execute_contract["post_batch_routes"]
        } == {
            ("review_required", "review-fan-in"),
            ("no_review", "halt"),
            ("deferred_human", "halt"),
        }
        assert review_contract["no_review_route_signal"] == "pass"
        assert "deferred_human" in workflow_components.RUNTIME_BRANCH_VOCABULARY["review"]
        assert {
            (route["action"], route["route_signal"])
            for route in tiebreaker_contract["decision_routes"]
        } == {
            ("pick", "proceed"),
            ("replan", "iterate"),
            ("escalate", "escalate"),
        }
