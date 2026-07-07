from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

REQUIRED_CASES = (
    "fresh-planning.json",
    "gate-iteration.json",
    "tiebreaker.json",
    "human-suspension.json",
    "finalize-execute-review.json",
    "override-fallback.json",
    "resume-sensitive.json",
)

M1_ADDED_CASES = {
    "tiebreaker.json",
    "human-suspension.json",
    "finalize-execute-review.json",
    "override-fallback.json",
}

REQUIRED_VOLATILE_FIELDS = (
    "absolute_path",
    "duration_ms",
    "event_id",
    "model_latency",
    "run_id",
    "timestamp",
    "token_count",
)

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PLACEHOLDER_TOKENS = ("placeholder", "stub", "todo", "example", "sample")

EXPECTED_CASE_CONTRACTS = {
    "finalize-execute-review": {
        "routes": {"finalize", "execute", "review"},
        "capabilities": {
            "agent:executor",
            "agent:finalizer",
            "agent:reviewer",
            "artifact:write",
        },
        "reentry_ids": {"review:accepted", "review:feedback"},
        "policy_slots": {"budget", "idempotency", "retry", "timing"},
        "overlay_types": {"review-feedback"},
        "edge_semantics": {
            "finalized plan hands immutable execution input to executor",
            "execution output is reviewed before completion",
        },
    },
    "fresh-planning": {
        "routes": {"critique", "execute", "finalize", "gate", "plan", "prep", "revise", "review"},
        "capabilities": {"agent:gatekeeper", "agent:planner", "artifact:write"},
        "reentry_ids": {"gate:iterate", "gate:proceed"},
        "policy_slots": {"budget", "idempotency", "loop", "retry"},
        "overlay_types": {"bounded-revision"},
    },
    "gate-iteration": {
        "routes": {"critique", "finalize", "gate", "revise"},
        "capabilities": {"agent:gatekeeper", "agent:planner", "artifact:write"},
        "reentry_ids": {"gate:iterate", "gate:proceed"},
        "policy_slots": {"budget", "idempotency", "loop", "retry"},
        "overlay_types": {"bounded-revision"},
    },
    "human-suspension": {
        "routes": {"operator-reentry", "resume", "suspend"},
        "capabilities": {"artifact:write", "human:operator", "resume:validated"},
        "reentry_ids": {"operator:reject", "operator:resume"},
        "policy_slots": {"budget", "idempotency", "retry", "timing"},
        "overlay_types": {"resume-reentry"},
        "edge_semantics": {
            "execution suspends until an operator supplies resume payload",
            "operator payload resumes the suspended node through a stable reentry id",
        },
        "node_semantics": {
            "operator-visible resume point",
            "pauses execution for external human decision",
            "resume continuation after validated human payload",
        },
    },
    "override-fallback": {
        "routes": {"fallback", "override"},
        "capabilities": {"artifact:write", "control:fallback", "control:override"},
        "reentry_ids": {"fallback:selected", "override:accepted"},
        "policy_slots": {"budget", "escalation", "idempotency", "retry"},
        "overlay_types": {"control-branch"},
        "edge_semantics": {
            "explicit operator override takes precedence over fallback",
            "fallback route is used only when no override is present",
        },
        "node_semantics": {
            "default continuation for absent override",
            "explicit control transition overrides default routing",
            "receives exactly one selected control transition",
        },
    },
    "resume-sensitive": {
        "routes": {"execute", "legacy-cursor", "manifest-coordinate-cursor", "resume", "review"},
        "capabilities": {
            "artifact:read",
            "resume:legacy-cursor",
            "resume:manifest-coordinate",
        },
        "reentry_ids": {"legacy:resume", "manifest-coordinate:resume"},
        "policy_slots": {"budget", "idempotency", "retry"},
        "overlay_types": {"cursor-reconciliation"},
        "cursor_kinds": {"legacy-state-and-manifest-coordinate", "manifest-coordinate"},
        "legacy_cursors": {"executed", "finalized"},
    },
    "tiebreaker": {
        "routes": {"researcher", "challenger", "synthesis", "decision"},
        "capabilities": {
            "agent:researcher",
            "agent:challenger",
            "agent:synthesizer",
            "agent:decider",
            "artifact:write",
        },
        "reentry_ids": {"tiebreaker:iterate", "tiebreaker:replan"},
        "policy_slots": {"budget", "idempotency", "loop", "retry"},
        "overlay_types": {"tiebreaker-phase-chain"},
        "edge_semantics": {
            "researcher produces initial findings for tiebreaker resolution",
            "challenger stress-tests researcher findings",
            "synthesis merges research and challenge into unified payload",
            "tiebreaker PROCEED routes to normal finalize",
            "tiebreaker ITERATE routes back through critique gate loop",
            "tiebreaker ESCALATE routes to override authority",
            "tiebreaker REPLAN routes back through critique gate loop",
        },
        "node_semantics": {
            "gathers evidence for tiebreaker resolution",
            "adversarial stress-test of researcher findings",
            "unified tiebreaker payload from research and challenge",
            "resolve tiebreaker with PROCEED, ITERATE, ESCALATE, or REPLAN",
        },
    },
}


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_source_or_coverage_origin(root: Path, name: str, data: dict[str, Any]) -> None:
    assert bool(data.get("coverage_origin")) != bool(data.get("source_golden")), name

    if name in M1_ADDED_CASES:
        assert data.get("coverage_origin") == "m1-added", name
        assert "source_golden" not in data, name
        return

    source_golden = data.get("source_golden")
    assert source_golden, name
    assert (root.parent / Path(source_golden).name).exists(), source_golden


def _assert_non_empty_sequence(value: Any, *, field: str, fixture: str) -> None:
    assert isinstance(value, list), f"{fixture}: {field} must be a list"
    assert value, f"{fixture}: {field} must not be empty"


def _assert_non_placeholder_text(value: Any, *, field: str, fixture: str) -> None:
    assert isinstance(value, str) and value.strip(), f"{fixture}: {field} must be non-empty"
    normalized = value.lower()
    assert not any(token in normalized for token in PLACEHOLDER_TOKENS), (
        f"{fixture}: {field} looks like placeholder content"
    )


def _assert_sha256(value: Any, *, field: str, fixture: str) -> None:
    assert isinstance(value, str) and SHA256_RE.fullmatch(value), (
        f"{fixture}: {field} must be a sha256 hash"
    )


def _assert_capabilities(name: str, manifest: dict[str, Any], expected: dict[str, Any]) -> None:
    capabilities = manifest["capabilities"]
    capability_ids: set[str] = set()

    for index, capability in enumerate(capabilities):
        assert isinstance(capability, dict), f"{name}: capabilities[{index}] must be an object"
        capability_id = capability.get("capability_id")
        _assert_non_placeholder_text(
            capability_id, field=f"capabilities[{index}].capability_id", fixture=name
        )
        assert capability.get("required") is True, f"{name}: {capability_id} must be required"
        _assert_non_placeholder_text(capability.get("route"), field=f"{capability_id}.route", fixture=name)
        capability_ids.add(capability_id)

    assert capability_ids == expected["capabilities"], name


def _assert_policy(name: str, manifest: dict[str, Any], expected: dict[str, Any]) -> None:
    policy = manifest.get("policy")
    assert isinstance(policy, dict), f"{name}: missing manifest policy slots"
    assert expected["policy_slots"] <= set(policy), f"{name}: missing expected policy slot"

    for field in ("suspension_routes", "control_transitions", "topology_overlays"):
        _assert_non_empty_sequence(policy.get(field), field=f"policy.{field}", fixture=name)

    reentry_ids = set(manifest["reentry_ids"])
    capability_ids = {capability["capability_id"] for capability in manifest["capabilities"]}
    route_reentries: set[str] = set()
    for index, route in enumerate(policy["suspension_routes"]):
        route_id = route.get("route_id")
        _assert_non_placeholder_text(route_id, field=f"suspension_routes[{index}].route_id", fixture=name)
        _assert_sha256(
            route.get("payload_schema_hash"),
            field=f"suspension_routes[{index}].payload_schema_hash",
            fixture=name,
        )
        _assert_sha256(
            route.get("resume_schema_hash"),
            field=f"suspension_routes[{index}].resume_schema_hash",
            fixture=name,
        )
        capability_id = route.get("capability_id")
        assert capability_id in capability_ids, f"{name}: unknown suspension capability {capability_id}"
        reentry_id = route.get("reentry_id")
        assert reentry_id in reentry_ids, f"{name}: unlisted suspension reentry {reentry_id}"
        route_reentries.add(reentry_id)

    assert route_reentries, f"{name}: missing suspension reentry"

    for index, transition in enumerate(policy["control_transitions"]):
        _assert_non_placeholder_text(
            transition.get("transition_id"),
            field=f"control_transitions[{index}].transition_id",
            fixture=name,
        )
        assert transition.get("transition_type") in {"fallback", "override", "supervisor-promotion"}, (
            f"{name}: unsupported control transition type"
        )
        _assert_non_placeholder_text(
            transition.get("trigger_ref"),
            field=f"control_transitions[{index}].trigger_ref",
            fixture=name,
        )
        _assert_non_placeholder_text(
            transition.get("target_ref"),
            field=f"control_transitions[{index}].target_ref",
            fixture=name,
        )
        _assert_sha256(
            transition.get("payload_schema_hash"),
            field=f"control_transitions[{index}].payload_schema_hash",
            fixture=name,
        )
        idempotency = transition.get("idempotency")
        assert isinstance(idempotency, dict), f"{name}: missing transition idempotency"
        assert idempotency.get("required") is True, f"{name}: transition idempotency must be required"
        assert "{run_id}" in idempotency.get("key_template", ""), (
            f"{name}: transition idempotency must include run_id"
        )

    _assert_topology_overlays(name, policy["topology_overlays"], expected)


def _assert_topology_overlays(name: str, overlays: list[Any], expected: dict[str, Any]) -> None:
    overlay_types: set[str] = set()
    for index, overlay in enumerate(overlays):
        assert isinstance(overlay, dict), f"{name}: topology_overlays[{index}] must be an object"
        _assert_non_placeholder_text(
            overlay.get("overlay_id"), field=f"topology_overlays[{index}].overlay_id", fixture=name
        )
        overlay_type = overlay.get("overlay_type")
        _assert_non_placeholder_text(
            overlay_type, field=f"topology_overlays[{index}].overlay_type", fixture=name
        )
        overlay_types.add(overlay_type)
        _assert_non_placeholder_text(
            overlay.get("source_ref"), field=f"topology_overlays[{index}].source_ref", fixture=name
        )
        _assert_non_empty_sequence(
            overlay.get("target_refs"), field=f"topology_overlays[{index}].target_refs", fixture=name
        )
        _assert_non_placeholder_text(
            overlay.get("condition_ref"),
            field=f"topology_overlays[{index}].condition_ref",
            fixture=name,
        )
        _assert_sha256(
            overlay.get("payload_schema_hash"),
            field=f"topology_overlays[{index}].payload_schema_hash",
            fixture=name,
        )

    assert overlay_types == expected["overlay_types"], name


def _assert_case_route_semantics(name: str, manifest: dict[str, Any], expected: dict[str, Any]) -> None:
    node_metadata = [node["route_metadata"] for node in manifest["nodes"]]
    edge_metadata = [edge["route_metadata"] for edge in manifest["edges"]]
    all_metadata = node_metadata + edge_metadata
    behavioral_routes = {
        metadata.get("behavioral_step")
        for metadata in all_metadata
        if metadata.get("behavioral_step")
    }
    behavioral_routes.update(
        metadata.get("behavioral_state")
        for metadata in all_metadata
        if metadata.get("behavioral_state")
    )

    if name != "resume-sensitive.json":
        assert expected["routes"] <= behavioral_routes, f"{name}: routes lack behavioral metadata"

    for metadata in all_metadata:
        assert metadata, f"{name}: route metadata must not be empty"
        for key, value in metadata.items():
            if isinstance(value, str):
                _assert_non_placeholder_text(value, field=f"route_metadata.{key}", fixture=name)

    node_semantics = {
        metadata["route_semantics"] for metadata in node_metadata if "route_semantics" in metadata
    }
    edge_semantics = {
        metadata["route_semantics"] for metadata in edge_metadata if "route_semantics" in metadata
    }
    assert expected.get("node_semantics", set()) <= node_semantics, name
    assert expected.get("edge_semantics", set()) <= edge_semantics, name

    if "cursor_kinds" in expected:
        cursor_kinds = {
            metadata["cursor_kind"] for metadata in all_metadata if "cursor_kind" in metadata
        }
        legacy_cursors = {
            metadata["legacy_cursor"] for metadata in all_metadata if "legacy_cursor" in metadata
        }
        assert expected["cursor_kinds"] <= cursor_kinds, name
        assert expected["legacy_cursors"] == legacy_cursors, name


def _assert_manifest_contract_substance(name: str, data: dict[str, Any]) -> None:
    expected = EXPECTED_CASE_CONTRACTS[data["case"]]
    manifest = data["manifest_contract"]

    assert manifest["id"] == data["case"], name
    assert manifest["schema_version"] == "arnold.workflow.manifest.v1"
    assert manifest["version"] == "manifest-contract.v1", name
    assert set(data["routes"]) == expected["routes"], name

    _assert_non_empty_sequence(manifest.get("nodes"), field="nodes", fixture=name)
    _assert_non_empty_sequence(manifest.get("edges"), field="edges", fixture=name)
    _assert_non_empty_sequence(manifest.get("capabilities"), field="capabilities", fixture=name)
    _assert_non_empty_sequence(manifest.get("reentry_ids"), field="reentry_ids", fixture=name)

    node_ids: set[str] = set()
    for node in manifest["nodes"]:
        node_id = node.get("id")
        _assert_non_placeholder_text(node_id, field="node.id", fixture=name)
        assert node_id.startswith(f"{data['case']}-"), f"{name}: node id must be case-derived"
        assert node_id not in node_ids, f"{name}: duplicate node id {node_id}"
        _assert_non_placeholder_text(node.get("kind"), field=f"{node_id}.kind", fixture=name)
        node_ids.add(node_id)

    edge_ids: set[str] = set()
    for edge in manifest["edges"]:
        edge_id = edge.get("id")
        _assert_non_placeholder_text(edge_id, field="edge.id", fixture=name)
        assert edge_id == f"{edge['source']}-{edge['target']}", f"{name}: edge id is not source-target"
        assert edge_id not in edge_ids, f"{name}: duplicate edge id {edge_id}"
        edge_ids.add(edge_id)
        assert edge["source"] in node_ids, f"{name}: unknown edge source {edge['source']}"
        assert edge["target"] in node_ids, f"{name}: unknown edge target {edge['target']}"
        _assert_non_placeholder_text(edge.get("label"), field=f"{edge_id}.label", fixture=name)

    assert len(edge_ids) >= len(node_ids) - 1, f"{name}: topology is too thin"
    assert set(manifest["reentry_ids"]) == expected["reentry_ids"], name
    _assert_capabilities(name, manifest, expected)
    _assert_policy(name, manifest, expected)
    _assert_case_route_semantics(name, manifest, expected)


def test_workflow_manifest_runtime_fixture_cases_are_present_and_normalized() -> None:
    root = Path("tests/fixtures/golden/workflow_manifest_runtime")

    for name in REQUIRED_CASES:
        path = root / name
        assert path.exists(), name
        data = _load_fixture(path)
        assert data["schema_version"] == "workflow-manifest-runtime.golden.v1"
        assert data["normalization"]["volatile_fields"] == sorted(REQUIRED_VOLATILE_FIELDS)
        assert "seed" not in data["normalization"], name
        _assert_source_or_coverage_origin(root, name, data)
        _assert_manifest_contract_substance(name, data)


REQUIRED_CANONICAL_SHAPE_FILES = (
    "canonical_megaplan_nodes.yaml",
    "canonical_megaplan_refs.yaml",
    "canonical_megaplan_capabilities.yaml",
    "canonical_megaplan_suspension_points.yaml",
    "canonical_megaplan_control_routes.yaml",
    "canonical_megaplan_overlay_slots.yaml",
    "canonical_megaplan_hashes.yaml",
)


def test_canonical_megaplan_shape_files_exist_and_parse() -> None:
    root = Path("tests/fixtures/workflow")
    for name in REQUIRED_CANONICAL_SHAPE_FILES:
        path = root / name
        assert path.exists(), name
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), name


def test_canonical_megaplan_shape_matrix_covers_named_shapes() -> None:
    from tests.arnold.workflow.test_canonical_megaplan_conformance import (
        _load_fixture_matrix,
    )

    matrix = _load_fixture_matrix()
    expected_shape_names = set(matrix["shapes"].keys())
    required_canonical_shapes = {
        "branch",
        "loop_revise",
        "fanout_panel",
        "retry",
        "subpipeline",
        "suspension_capability",
        "override_fallback",
        "escalation",
        "compensation",
        "supervisor_promotion",
        "feedback",
        "robustness_budget",
        "dynamic_topology_overlay",
        "tournament",
    }

    assert required_canonical_shapes <= expected_shape_names
    assert matrix["shapes"]["dynamic_topology_overlay"]["metadata"]["overlay"][
        "dynamic_events"
    ]
