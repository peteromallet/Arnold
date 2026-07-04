"""Manifest topology fixture lock and amendment enforcement.

The canonical M4 Megaplan topology is locked in
``tests/arnold_pipelines/megaplan/fixtures/megaplan_m4_topology.yaml``.
If the compiled manifest diverges from this fixture, the test fails and
requires an amendment in ``docs/arnold/workflow-manifest-amendments.md``.
"""

from __future__ import annotations

from importlib import import_module
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
import yaml

from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline
from arnold_pipelines.megaplan.registry import pipeline_metadata
from arnold_pipelines.megaplan.workflows import components as workflow_components
from arnold_pipelines.megaplan.workflows import planning as workflow_planning

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "megaplan_m4_topology.yaml"
MANIFEST_GOLDEN_PATH = Path(__file__).parent / "fixtures" / "megaplan_m4_manifest_golden.json"
NORMALIZED_SHAPE_PATH = Path(__file__).parent / "fixtures" / "normalized_pipeline_shape.json"
AMENDMENT_PATH = Path(__file__).parents[3] / "docs" / "arnold" / "workflow-manifest-amendments.md"
LOCKED_MANIFEST_HASH = "sha256:245a06ac778caf20c645772b7c0570655af7a79a0d00eda959b19d2cf01a3eba"
LOCKED_TOPOLOGY_HASH = "sha256:2705e157e12fc074301afa8f5aec4e48d9820814ebaaa77535d152a8cc381fd4"
LOWERED_WRAPPER_NODE_IDS = {
    "review_revise",
    "review_halt",
    "tiebreaker_finalize",
    "tiebreaker_override",
    "override_halt",
    "override_finalize",
    "override_execute",
    "override_revise",
    "override_unknown",
    "gate_abort",
    "gate_suspend",
    "blocked_override",
    "force_finalize",
    "force_execute",
    "fallback_finalize",
    "fallback_execute",
}


def _resolve_component(ref: str) -> Any:
    module_name, export_name = ref.split(":", 1)
    module = import_module(module_name)
    return getattr(module, export_name)


def _collapse_branch_target(target: str) -> str:
    if target in {"halt", "gate_abort", "gate_suspend", "review_halt", "override_halt", "override_unknown"}:
        return "halt"
    if target in {"blocked_override", "tiebreaker_override"}:
        return "override"
    if target in {"review_revise", "override_revise"}:
        return "revise"
    if target.endswith("finalize") or target == "finalize":
        return "finalize"
    return target


def _normalize_plain(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        value = dict(value)
    if isinstance(value, dict):
        return {key: _normalize_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_plain(item) for item in value]
    return value


def _canonical_authored_topology() -> dict[str, Any]:
    lowered = lower_workflow_file(workflow_planning.AUTHORING_SOURCE_PATH)
    semantic_nodes = [
        "prep",
        "plan",
        "critique-fanout",
        "gate",
        "revise",
        "tiebreaker",
        "finalize",
        "execute-batches",
        "review-fan-in",
        "override",
        "tiebreaker-execute-batches",
        "execute",
        "halt",
    ]

    def _routes_for(source_id: str) -> list[dict[str, Any]]:
        return [
            {
                "route_id": route.id,
                "label": route.label,
                "target": _collapse_branch_target(route.target),
                "lowered_target": route.target,
                "condition_ref": route.condition_ref,
            }
            for route in lowered.routes
            if route.source == source_id
        ]

    dynamic_maps = []
    for step in lowered.steps:
        if step.kind != "parallel_map":
            continue
        component = _resolve_component(step.metadata["mapper_ref"])
        dynamic_maps.append(
            {
                "id": step.id,
                "items_ref": step.metadata["items_ref"],
                "mapper_ref": step.metadata["mapper_ref"],
                "reducer_ref": step.metadata["reducer_ref"],
                "path_template": step.metadata["path_template"],
                "iteration_coordinate": step.metadata["iteration_coordinate"],
                "call_site_path": step.metadata["call_site_path"],
                "topology_contract": _normalize_plain(component.metadata.get("topology_contract", {})),
            }
        )

    child_workflows = []
    for step in lowered.steps:
        if step.kind != "subpipeline":
            continue
        component = _resolve_component(step.metadata["component_ref"])
        child_workflows.append(
            {
                "id": step.id,
                "child_workflow_id": step.metadata["child_workflow_id"],
                "call_site_path": step.metadata["call_site_path"],
                "parent_path": step.metadata["parent_path"],
                "inputs_schema": list(step.metadata["inputs_schema"]),
                "outputs_schema": list(step.metadata["outputs_schema"]),
                "topology_contract": _normalize_plain(component.metadata.get("topology_contract", {})),
            }
        )

    return {
        "source_path": "arnold_pipelines/megaplan/workflows/workflow.py",
        "workflow_id": lowered.id,
        "workflow_version": lowered.version,
        "semantic_nodes": semantic_nodes,
        "excluded_wrapper_nodes": sorted(
            step.id for step in lowered.steps if step.id not in set(semantic_nodes)
        ),
        "gate_routes": _routes_for("gate"),
        "review_routes": _routes_for("review-fan-in"),
        "override_routes": _routes_for("override"),
        "tiebreaker_routes": _routes_for("tiebreaker"),
        "dynamic_maps": dynamic_maps,
        "child_workflows": child_workflows,
        "suspension_routes": {
            "gate": _normalize_plain(
                list(workflow_components.STEP_COMPONENTS_BY_ID["gate"].policy.config["suspension_routes"])
            ),
            "review": _normalize_plain(
                list(workflow_components.STEP_COMPONENTS_BY_ID["review"].policy.config["suspension_routes"])
            ),
            "tiebreaker": _normalize_plain(
                list(
                workflow_components.STEP_COMPONENTS_BY_ID["tiebreaker_decide"].policy.config["suspension_routes"]
                )
            ),
        },
    }


@pytest.fixture
def fixture() -> dict:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def normalized_shape() -> dict[str, Any]:
    with NORMALIZED_SHAPE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _fixture_has_m4_amendment() -> bool:
    if not AMENDMENT_PATH.exists():
        return False
    text = AMENDMENT_PATH.read_text(encoding="utf-8")
    return "## M4 Megaplan Product Migration" in text


def _canonical_manifest_json_bytes(manifest: Any) -> bytes:
    payload = json.loads(manifest.to_json())
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _io_contract(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        entry: dict[str, Any] = {"name": item.name}
        schema_hash = getattr(item, "schema_hash", None)
        value_ref = getattr(item, "value_ref", None)
        if schema_hash is not None:
            entry["schema_hash"] = schema_hash
        if value_ref is not None:
            entry["value_ref"] = value_ref
        if dict(getattr(item, "metadata", {}) or {}):
            entry["metadata"] = dict(item.metadata)
        result.append(entry)
    return result


def _capability_contract(capability: Any) -> dict[str, Any]:
    capability_id = getattr(capability, "id", None) or getattr(capability, "capability_id")
    return {
        "id": capability_id,
        "route": capability.route,
        "required": capability.required,
    }


def _policy_contract(policy: Any | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    result: dict[str, Any] = {}
    if policy.loop is not None:
        result["loop"] = {
            "max_iterations": policy.loop.max_iterations,
            "until_ref": policy.loop.until_ref,
        }
    if policy.timing is not None:
        result["timing"] = {"timeout_seconds": policy.timing.timeout_seconds}
    if policy.control_transitions:
        result["control_transitions"] = [
            {
                "transition_id": slot.transition_id,
                "transition_type": slot.transition_type,
                "trigger_ref": slot.trigger_ref,
                "target_ref": slot.target_ref,
                "policy_ref": slot.policy_ref,
            }
            for slot in policy.control_transitions
        ]
    if policy.suspension_routes:
        routes: list[dict[str, Any]] = []
        for route in policy.suspension_routes:
            entry = {
                "route_id": route.route_id,
                "capability_id": route.capability_id,
            }
            if route.reentry_id is not None:
                entry["reentry_id"] = route.reentry_id
            routes.append(entry)
        result["suspension_routes"] = routes
    return result


def _subpipeline_contract(subpipeline: Any | None) -> dict[str, Any] | None:
    if subpipeline is None:
        return None
    return {
        "manifest_hash": subpipeline.manifest_hash,
        "alias": subpipeline.alias,
    }


def _normalized_pipeline_contract(pipeline: Any) -> dict[str, Any]:
    return {
        "fixture_schema": "arnold.megaplan.normalized_pipeline_shape.v1",
        "source": "arnold_pipelines.megaplan.pipeline:build_pipeline",
        "hash_neutral": True,
        "pipeline": {
            "id": pipeline.id,
            "version": pipeline.version,
            "metadata": dict(pipeline.metadata),
            "policy": _policy_contract(pipeline.policy),
        },
        "counts": {
            "steps": len(pipeline.steps),
            "routes": len(pipeline.routes),
            "capabilities": len(pipeline.capabilities),
        },
        "ordered_step_ids": [step.id for step in pipeline.steps],
        "steps": [
            {
                "id": step.id,
                "kind": step.kind,
                "inputs": _io_contract(step.inputs),
                "outputs": _io_contract(step.outputs),
                "capabilities": [_capability_contract(capability) for capability in step.capabilities],
                "policy": _policy_contract(step.policy),
                "handler_ref": step.metadata.get("handler_ref"),
                "terminal": bool(step.metadata.get("terminal", False)),
                "subpipeline": _subpipeline_contract(step.subpipeline),
                "metadata": dict(step.metadata),
            }
            for step in pipeline.steps
        ],
        "capabilities": [_capability_contract(capability) for capability in pipeline.capabilities],
        "routes": [
            {
                "id": route.id,
                "source": route.source,
                "target": route.target,
                "label": route.label,
                "condition_ref": route.condition_ref,
                "metadata": dict(route.metadata),
            }
            for route in pipeline.routes
        ],
    }


def _manifest_policy_contract(policy: Any | None) -> dict[str, Any] | None:
    contract = _policy_contract(policy)
    return contract or None


class TestTopologyFixtureLock:
    def test_registered_package_and_authored_source_paths_stay_aligned(self) -> None:
        metadata = pipeline_metadata("megaplan")

        assert metadata["source_path"].endswith("/arnold_pipelines/megaplan/pipeline.py")
        assert metadata["authored_source_path"] == str(workflow_planning.AUTHORING_SOURCE_PATH.resolve())

    def test_compiled_manifest_matches_locked_manifest_golden_bytes(self) -> None:
        manifest = build_and_compile_pipeline()
        assert manifest.manifest_hash == LOCKED_MANIFEST_HASH
        assert manifest.topology_hash == LOCKED_TOPOLOGY_HASH
        assert _canonical_manifest_json_bytes(manifest) == MANIFEST_GOLDEN_PATH.read_bytes()

    def test_workflow_surface_manifest_matches_locked_manifest_golden_bytes(self) -> None:
        manifest = compile_pipeline(workflow_planning.build_pipeline())
        assert manifest.manifest_hash == LOCKED_MANIFEST_HASH
        assert manifest.topology_hash == LOCKED_TOPOLOGY_HASH
        assert _canonical_manifest_json_bytes(manifest) == MANIFEST_GOLDEN_PATH.read_bytes()

    def test_compiled_manifest_matches_locked_topology(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        assert manifest.id == fixture["manifest_id"]
        assert fixture["manifest_hash"] == LOCKED_MANIFEST_HASH
        assert fixture["topology_hash"] == LOCKED_TOPOLOGY_HASH
        assert manifest.manifest_hash == fixture["manifest_hash"]
        assert manifest.topology_hash == fixture["topology_hash"]

    def test_compiled_nodes_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        node_ids = {n.id for n in manifest.nodes}
        assert node_ids == set(fixture["nodes"])

    def test_authored_node_order_matches_fixture(self, fixture: dict) -> None:
        pipeline = build_pipeline()
        assert [step.id for step in pipeline.steps] == fixture["nodes"]

    def test_compiled_capabilities_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        cap_ids = {c.id for c in manifest.capabilities}
        assert cap_ids == set(fixture["capabilities"])

    def test_compiled_gate_edges_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        gate_edges = {
            (e.label, e.target)
            for e in manifest.edges
            if e.source == "gate"
        }
        expected = {(item["label"], item["target"]) for item in fixture["gate_targets"]}
        assert gate_edges == expected

    def test_compiled_tiebreaker_edges_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        edges = {
            (e.label, e.target)
            for e in manifest.edges
            if e.source == "tiebreaker_decide"
        }
        expected = {(item["label"], item["target"]) for item in fixture["tiebreaker_targets"]}
        assert edges == expected

    def test_loop_suspension_routes_survive_lowering_and_compilation(self) -> None:
        pipeline = build_pipeline()
        pipeline_loop_routes = {
            route.id: (route.source, route.target, route.label, route.condition_ref)
            for route in pipeline.routes
            if route.id in {"revise:critique", "tiebreaker_decide:critique"}
        }
        assert pipeline_loop_routes == {
            "revise:critique": ("revise", "critique", "default", "revise:loop"),
            "tiebreaker_decide:critique": (
                "tiebreaker_decide",
                "critique",
                "iterate",
                "tiebreaker:loop",
            ),
        }

        manifest = build_and_compile_pipeline()
        manifest_loop_edges = {
            edge.id: (edge.source, edge.target, edge.label, edge.condition_ref)
            for edge in manifest.edges
            if edge.id in {"revise:critique", "tiebreaker_decide:critique"}
        }
        assert manifest_loop_edges == pipeline_loop_routes

    def test_compiled_review_edges_match_fixture(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        edges = {
            (e.label, e.target)
            for e in manifest.edges
            if e.source == "review"
        }
        expected = {(item["label"], item["target"]) for item in fixture["review_targets"]}
        assert edges == expected

    def test_route_order_for_branch_nodes_is_stable(self) -> None:
        pipeline = build_pipeline()
        labels_by_source = {
            source: [route.label for route in pipeline.routes if route.source == source]
            for source in ("gate", "tiebreaker_decide", "review")
        }

        assert labels_by_source == {
            "gate": [
                "proceed",
                "iterate",
                "tiebreaker",
                "escalate",
                "abort",
                "suspend",
                "blocked_preflight",
                "force_proceed",
            ],
            "tiebreaker_decide": ["iterate", "proceed", "escalate"],
            "review": ["default", "rework"],
        }

    @pytest.mark.parametrize(
        ("surface", "builder"),
        [
            ("workflow_planning", workflow_planning.build_pipeline),
            ("pipeline_facade", build_pipeline),
        ],
    )
    def test_public_surfaces_match_normalized_explicit_contract(
        self,
        normalized_shape: dict[str, Any],
        surface: str,
        builder: Any,
    ) -> None:
        actual = _normalized_pipeline_contract(builder())
        assert actual == normalized_shape, surface

    def test_compiled_manifest_preserves_explicit_contract_details(
        self,
        normalized_shape: dict[str, Any],
    ) -> None:
        manifest = build_and_compile_pipeline()
        nodes_by_id = {node.id: node for node in manifest.nodes}
        edges_by_id = {edge.id: edge for edge in manifest.edges}

        assert {node.id for node in manifest.nodes} == set(normalized_shape["ordered_step_ids"])
        assert [
            _capability_contract(capability)
            for capability in manifest.capabilities
        ] == normalized_shape["capabilities"]

        for expected_step in normalized_shape["steps"]:
            node = nodes_by_id[expected_step["id"]]
            assert node.kind == expected_step["kind"]
            assert _manifest_policy_contract(node.policy) == expected_step["policy"]
            assert _subpipeline_contract(node.subpipeline) == expected_step["subpipeline"]
            for key in ("handler_ref", "terminal"):
                if key in expected_step["metadata"]:
                    assert node.metadata.get(key) == expected_step["metadata"][key]

        for expected_route in normalized_shape["routes"]:
            edge = edges_by_id[expected_route["id"]]
            assert {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "label": edge.label,
                "condition_ref": edge.condition_ref,
                "metadata": edge.metadata,
            } == expected_route

    def test_authored_lowering_accepts_nested_wrapper_nodes_without_moving_entry_path(self) -> None:
        authored = lower_workflow_file(workflow_planning.AUTHORING_SOURCE_PATH)

        lowered_ids = {step.id for step in authored.steps}
        assert LOWERED_WRAPPER_NODE_IDS.issubset(lowered_ids)
        assert [step.id for step in authored.steps[:4]] == ["prep", "plan", "critique-fanout", "gate"]

    def test_authored_lowering_remains_non_conformant_while_branch_wrappers_exist(
        self,
        fixture: dict,
    ) -> None:
        authored = lower_workflow_file(workflow_planning.AUTHORING_SOURCE_PATH)
        manifest = compile_pipeline(authored)

        authored_node_ids = {node.id for node in manifest.nodes}
        assert LOWERED_WRAPPER_NODE_IDS.issubset(authored_node_ids)
        assert authored_node_ids != set(fixture["nodes"])

    def test_canonical_authored_topology_snapshot_matches_fixture(self, fixture: dict) -> None:
        assert _canonical_authored_topology() == fixture["canonical_authoring"]

    def test_canonical_authored_topology_proves_hidden_megaplan_semantics(self) -> None:
        topology = _canonical_authored_topology()

        tiebreaker = topology["child_workflows"][0]
        assert {
            (route["action"], route["route_signal"], route["target_ref"])
            for route in tiebreaker["topology_contract"]["decision_routes"]
        } == {
            ("pick", "proceed", "finalize"),
            ("replan", "iterate", "critique-fanout"),
            ("escalate", "escalate", "override"),
        }

        review_fan_in = next(item for item in topology["dynamic_maps"] if item["id"] == "review-fan-in")
        assert review_fan_in["topology_contract"]["no_review_route_signal"] == "pass"
        assert {
            (route["route_signal"], route["target_ref"])
            for route in review_fan_in["topology_contract"]["reducer_routes"]
        } == {
            ("pass", "halt"),
            ("rework", "revise"),
            ("blocked", "halt"),
            ("force_proceeded", "halt"),
            ("deferred_human", "halt"),
        }

        execute_batches = next(item for item in topology["dynamic_maps"] if item["id"] == "execute-batches")
        assert execute_batches["topology_contract"]["approval_gate"] == {
            "required_ref": "state.meta.user_approved_gate",
            "confirmation_ref": "args.confirm_destructive",
        }
        assert {
            (route["route_signal"], route["target_ref"])
            for route in execute_batches["topology_contract"]["post_batch_routes"]
        } == {
            ("review_required", "review-fan-in"),
            ("no_review", "halt"),
            ("deferred_human", "halt"),
        }


class TestAmendmentEnforcement:
    def test_structural_fixture_changes_require_amendment(self, fixture: dict) -> None:
        manifest = build_and_compile_pipeline()
        # If the manifest or topology hash changed from the locked fixture,
        # an M4 amendment must exist explaining the change.
        if (
            manifest.manifest_hash != fixture["manifest_hash"]
            or manifest.topology_hash != fixture["topology_hash"]
        ):
            assert _fixture_has_m4_amendment(), (
                "Manifest/topology hash changed; add an M4 amendment to "
                "docs/arnold/workflow-manifest-amendments.md"
            )
