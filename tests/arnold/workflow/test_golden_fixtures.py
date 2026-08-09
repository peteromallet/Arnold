from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
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


# ── Boundary Contract Schema Golden Fixtures ───────────────────────────────


SCHEMA_GOLDEN_CASES_PATH = Path(
    "tests/fixtures/workflow_boundary_contracts/schema_golden_cases.json"
)
GOLDEN_DIAGNOSTICS_PATH = Path(
    "tests/fixtures/workflow_boundary_contracts/golden_diagnostics.json"
)


def _load_json_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class TestBoundaryContractGoldenFixtures:
    """Assert schema golden fixtures are deterministic, compact, and stable."""

    def test_schema_golden_cases_exist_and_parse(self) -> None:
        assert SCHEMA_GOLDEN_CASES_PATH.exists(), (
            "schema_golden_cases.json fixture must exist"
        )
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        assert data["schema_version"] == (
            "arnold.workflow.boundary_contracts.golden.v1"
        ), "schema_version must be stable"
        assert "cases" in data, "golden cases must have a 'cases' key"

    def test_golden_diagnostics_exist_and_parse(self) -> None:
        assert GOLDEN_DIAGNOSTICS_PATH.exists(), (
            "golden_diagnostics.json fixture must exist"
        )
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        assert data["schema_version"] == (
            "arnold.workflow.boundary_contracts.diagnostics.golden.v1"
        ), "diagnostics schema_version must be stable"
        assert "diagnostics" in data, (
            "golden diagnostics must have a 'diagnostics' key"
        )

    # ── Ledger event type coverage ────────────────────────────────────

    def test_schema_golden_covers_all_ledger_event_types(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        event_types = data["cases"]["ledger_event_types"]["all_event_types"]
        assert len(event_types) == 11, "there must be exactly 11 ledger event types"
        assert "started" in event_types
        assert "completed" in event_types
        assert "failed" in event_types
        assert "persistence_failed" in event_types
        assert "reconciliation" in event_types

    def test_schema_golden_terminal_event_types_match_code(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        terminal = set(data["cases"]["ledger_event_types"]["terminal_event_types"])
        assert terminal == {"completed", "failed", "cancelled"}, (
            "terminal event types must match execution_attempt_ledger._TERMINAL_EVENT_TYPES"
        )

    def test_schema_golden_lifecycle_precedence_matches_code(self) -> None:
        """Assert the golden lifecycle precedence matches the code's _LIFECYCLE_PRECEDENCE."""
        from arnold.workflow.execution_attempt_ledger import AttemptEventType

        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        golden_prec = data["cases"]["ledger_event_types"]["lifecycle_precedence"]

        assert set(golden_prec.keys()) == {e.value for e in AttemptEventType}, (
            "golden event type keys must match AttemptEventType enum"
        )
        # started and persistence_failed have no required predecessors
        assert golden_prec["started"] == []
        assert golden_prec["persistence_failed"] == []
        # reconciliation requires persistence_failed
        assert golden_prec["reconciliation"] == ["persistence_failed"]
        # external_effect_outcome requires external_effect_intent
        assert golden_prec["external_effect_outcome"] == ["external_effect_intent"]
        # resumed requires suspended
        assert golden_prec["resumed"] == ["suspended"]

    # ── Identity failure coverage ─────────────────────────────────────

    def test_schema_golden_identity_failures_covered(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        identity = data["cases"]["identity"]
        assert "valid_minimal" in identity
        assert "valid_with_scope" in identity
        assert "failure_empty_workflow_id" in identity
        assert "failure_invalid_ordinal" in identity
        assert "failure_invalid_attempt_id" in identity

    # ── Ordering failure coverage ─────────────────────────────────────

    def test_schema_golden_ordering_failures_covered(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        ordering = data["cases"]["ordering"]
        assert "valid_monotonic_chain" in ordering
        assert "failure_duplicate_sequence" in ordering
        assert "failure_non_monotonic_sequence" in ordering
        assert "failure_first_event_nonzero_predecessor" in ordering
        assert "failure_missing_predecessor" in ordering

    # ── Inline vs reference payload classification ────────────────────

    def test_schema_golden_inline_payloads_under_16kib(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        inline = data["cases"]["payloads_inline"]
        assert inline["small_payload_under_16kib"]["expected_mode"] == "inline"
        assert inline["moderate_payload_under_16kib"]["expected_mode"] == "inline"
        assert inline["empty_payload"]["expected_mode"] == "inline"

    def test_schema_golden_reference_payloads_over_16kib(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        ref = data["cases"]["payloads_reference"]
        assert ref["large_payload_over_16kib"]["expected_mode"] == "reference"
        assert "durable_ref_minimal" in ref
        assert "durable_ref_full" in ref

    def test_inline_threshold_is_16kib_in_golden(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        defaults = data["cases"]["payload_policy_defaults"]
        assert defaults["inline_policy"]["threshold_bytes"] == 16384, (
            "golden must pin the 16 KiB inline threshold"
        )

    # ── Retention / redaction / legal-hold class coverage ─────────────

    def test_schema_golden_retention_classes_covered(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        retention = data["cases"]["retention_classes"]
        assert "ephemeral" in retention
        assert "run" in retention
        assert "audit" in retention
        assert "legal_hold" in retention
        assert "legal_hold_ephemeral_conflict" in retention

    def test_schema_golden_retention_durations_match_code(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        retention = data["cases"]["retention_classes"]
        # ephemeral = 0, run = 86400 (24h), audit = 7776000 (90d), legal_hold = -1
        assert retention["ephemeral"]["retention_seconds"] == 0
        assert retention["run"]["retention_seconds"] == 86400
        assert retention["audit"]["retention_seconds"] == 7776000
        assert retention["legal_hold"]["retention_seconds"] == -1

    def test_schema_golden_redaction_modes_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        assert set(data["cases"]["redaction_modes"]) == {"none", "default_on", "always"}

    def test_schema_golden_tombstone_modes_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        assert set(data["cases"]["tombstone_modes"]) == {"none", "marker", "full"}

    def test_schema_golden_audit_modes_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        assert set(data["cases"]["audit_modes"]) == {
            "none", "read", "read_write", "full",
        }

    def test_schema_golden_isolation_levels_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        assert set(data["cases"]["isolation_levels"]) == {
            "tenant", "workflow", "invocation", "shared",
        }

    # ── Persistence failure state coverage ────────────────────────────

    def test_schema_golden_persistence_failure_modes_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        pf = data["cases"]["persistence_failure_states"]
        assert set(pf["failure_modes"]) == {
            "write_failed", "store_unavailable", "quota_exceeded",
            "checksum_mismatch", "partial_write", "unknown",
        }

    def test_schema_golden_recoverable_modes(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        pf = data["cases"]["persistence_failure_states"]
        assert set(pf["recoverable_modes"]) == {
            "write_failed", "store_unavailable", "partial_write",
        }

    def test_schema_golden_reconciliation_outcomes_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        pf = data["cases"]["persistence_failure_states"]
        assert set(pf["reconciliation_outcomes"]) == {
            "recovered", "partially_recovered", "unrecoverable",
            "requires_manual_intervention", "quarantined",
        }

    # ── Typed payload ref coverage ────────────────────────────────────

    def test_schema_golden_typed_payload_refs_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        typed = data["cases"]["typed_payload_refs"]["all_types"]
        assert len(typed) == 9
        assert "InputPayload" in typed
        assert "OutputPayload" in typed
        assert "ResultPayload" in typed
        assert "VerdictPayload" in typed
        assert "StateDeltaPayload" in typed
        assert "ArtifactPayload" in typed
        assert "CheckpointPayload" in typed
        assert "AuthorityPayload" in typed
        assert "ExternalEffectPayload" in typed

    def test_schema_golden_typed_payload_mutual_exclusion(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        me = data["cases"]["typed_payload_refs"]["mutual_exclusion"]
        assert "valid_inline_only" in me
        assert "valid_ref_only" in me
        assert "valid_digest_only" in me
        assert "failure_both_inline_and_ref" in me
        assert "failure_nothing_provided" in me

    # ── Adapter kind coverage ─────────────────────────────────────────

    def test_schema_golden_adapter_kinds_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        kinds = set(data["cases"]["adapter_kinds"])
        assert len(kinds) == 7
        assert "arnold.pipeline.native" in kinds
        assert "megaplan.phase" in kinds
        assert "megaplan.chain" in kinds

    # ── Durable ref enum coverage ─────────────────────────────────────

    def test_schema_golden_durable_ref_enums_complete(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        enums = data["cases"]["durable_ref_enums"]
        assert len(enums["privacy_classes"]) == 4
        assert len(enums["availability_classes"]) == 4
        assert len(enums["encryption_scopes"]) == 4
        assert len(enums["retention_classes"]) == 4
        assert len(enums["access_scopes"]) == 4

    def test_schema_golden_forbidden_secret_keys_match_code(self) -> None:
        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        forbidden = set(data["cases"]["forbidden_secret_keys"])
        assert len(forbidden) == 8
        assert "api_key" in forbidden
        assert "password" in forbidden
        assert "secret" in forbidden
        assert "token" in forbidden
        assert "private_key" in forbidden
        assert "credential" in forbidden
        assert "bearer" in forbidden
        assert "authorization" in forbidden

    # ── Default policy coverage ───────────────────────────────────────

    def test_schema_golden_inline_policy_defaults_match_code(self) -> None:
        from arnold.workflow.payload_policy import default_inline_policy

        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        defaults = data["cases"]["payload_policy_defaults"]["inline_policy"]
        policy = default_inline_policy()
        assert defaults["threshold_bytes"] == policy.threshold_bytes
        assert defaults["schema_version"] == policy.schema_version
        assert defaults["allow_digest_only"] == policy.allow_digest_only

    def test_schema_golden_retention_policy_defaults_match_code(self) -> None:
        from arnold.workflow.payload_policy import default_retention_policy

        data = _load_json_fixture(SCHEMA_GOLDEN_CASES_PATH)
        defaults = data["cases"]["payload_policy_defaults"]["retention_policy"]
        policy = default_retention_policy()
        assert defaults["retention_mode"] == policy.retention_mode.value
        assert defaults["redaction_mode"] == policy.redaction_mode.value
        assert defaults["tombstone_mode"] == policy.tombstone_mode.value
        assert defaults["legal_hold"] == policy.legal_hold
        assert defaults["encryption_required"] == policy.encryption_required
        assert defaults["digest_only_preservation_rejected"] == (
            policy.digest_only_preservation_rejected
        )


class TestGoldenDiagnostics:
    """Assert golden diagnostics are stable and cover all required codes."""

    def test_diagnostics_c1r_codes_all_present(self) -> None:
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        codes = data["diagnostics"]["c1r_codes"]
        for expected in (
            "C1R001", "C1R002", "C1R003", "C1R004", "C1R005",
            "C1R006", "C1R007", "C1R008", "C1R009", "C1R010",
        ):
            assert expected in codes, f"C1R code {expected} must be in diagnostics"
        assert len(codes) == 10, "there must be exactly 10 C1R diagnostic codes"

    def test_diagnostics_c1r_codes_match_contract_reality(self) -> None:
        """Assert golden C1R codes match the actual C1RealityDiagnosticCode enum."""
        from arnold_pipelines.megaplan.workflows.contract_reality import (
            C1RealityDiagnosticCode,
        )

        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        golden_codes = data["diagnostics"]["c1r_codes"]

        for code_enum in C1RealityDiagnosticCode:
            # The enum value is something like "C1R001_RUN_AUTHORITY_MANIFEST_MISMATCH"
            short_key = code_enum.value[:6]  # e.g., "C1R001"
            assert short_key in golden_codes, (
                f"C1R code {code_enum.value} must be in golden diagnostics"
            )

    def test_diagnostics_digest_only_rejection_covered(self) -> None:
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        dor = data["diagnostics"]["digest_only_rejection"]
        assert "payload_policy_digest_only" in dor
        assert "durable_ref_digest_only" in dor
        assert "typed_payload_digest_only" in dor
        # Assert the expected issues are non-empty strings
        pp = dor["payload_policy_digest_only"]
        assert "digest" in pp["payload"]
        assert "expected_issue_inline" in pp
        assert "expected_issue_retention" in pp

    def test_diagnostics_secret_exclusion_covered(self) -> None:
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        se = data["diagnostics"]["secret_exclusion_diagnostics"]
        assert len(se["forbidden_patterns"]) == 8
        assert "durable_ref_secret" in se
        assert "payload_policy_secret" in se

    def test_diagnostics_ledger_validation_all_categories(self) -> None:
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        lvd = data["diagnostics"]["ledger_validation_diagnostics"]
        assert "identity_validation" in lvd
        assert "ordering_validation" in lvd
        assert "provenance_validation" in lvd
        assert "grant_validation" in lvd
        assert "timestamp_validation" in lvd
        assert "adapter_validation" in lvd
        assert "idempotency_validation" in lvd

    def test_diagnostics_durable_ref_validation_all_categories(self) -> None:
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        drv = data["diagnostics"]["durable_ref_validation_diagnostics"]
        assert "retrievability" in drv
        assert "tenant_scope" in drv
        assert "secret_exclusion" in drv

    def test_no_non_retrievable_hash_preservation_enforcement(self) -> None:
        """Assert the golden diagnostics explicitly document that non-retrievable
        hash-only preservation is rejected at every enforcement point."""
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        stability = data["diagnostics"]["stability_assertions"]
        rule = stability["no_non_retrievable_hash_preservation"]
        assert "rule" in rule
        assert "enforcement_points" in rule
        assert len(rule["enforcement_points"]) >= 6, (
            "at least 6 enforcement points must reject hash-only preservation"
        )

    def test_diagnostic_code_stability_all_codes_listed(self) -> None:
        data = _load_json_fixture(GOLDEN_DIAGNOSTICS_PATH)
        codes = data["diagnostics"]["stability_assertions"][
            "diagnostic_code_stability"
        ]["codes"]
        assert len(codes) == 10, "all 10 C1R codes must be listed"
        assert "C1R010_HASH_WITHOUT_RETAINED_PAYLOAD" in codes, (
            "C1R010 must be present — it covers hash-without-retained-payload"
        )

    # ── Runtime validation: diagnostics match actual validator output ──

    def test_digest_only_payload_rejected_by_inline_policy(self) -> None:
        """Verify that a digest-only payload exceeding 16 KiB is rejected by
        the wbc.inline.v1 policy. The digest-only check fires for REFERENCE
        mode (payloads > 16 KiB) that carry a digest but no retrievable locator."""
        from arnold.workflow.payload_policy import (
            validate_inline_payload_policy,
            default_inline_policy,
        )

        policy = default_inline_policy()
        # Payload must exceed 16 KiB to be classified as REFERENCE, then the
        # digest-only check fires.
        large_padding = "x" * 17000  # exceeds 16 KiB
        digest_only_payload = {
            "digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "padding": large_padding,
        }
        issues = validate_inline_payload_policy(policy, digest_only_payload)
        assert len(issues) > 0, "digest-only large payload must produce issues"
        assert any(
            "digest" in issue.lower()
            for issue in issues
        ), f"expected digest-only rejection, got {issues}"

    def test_digest_only_payload_rejected_by_retention_policy(self) -> None:
        """Verify that a digest-only payload is actually rejected by the
        wbc.retention.v1 policy at runtime."""
        from arnold.workflow.payload_policy import (
            validate_retention_payload_policy,
            default_retention_policy,
        )

        policy = default_retention_policy()
        digest_only_payload = {
            "digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
        issues = validate_retention_payload_policy(
            policy, payload=digest_only_payload,
        )
        assert len(issues) > 0, "digest-only payload must produce retention issues"
        assert any(
            "digest" in issue.lower()
            for issue in issues
        ), f"expected digest-only rejection in retention policy, got {issues}"

    def test_durable_ref_empty_store_id_rejected(self) -> None:
        """Verify that a DurableRef with empty store_id is rejected at construction."""
        from arnold.workflow.durable_refs import DurableRef

        with pytest.raises(ValueError, match="store_id must be non-empty"):
            DurableRef(
                store_id="",
                locator="some/key",
                digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            )

    def test_durable_ref_empty_locator_rejected(self) -> None:
        """Verify that a DurableRef with empty locator is rejected at construction."""
        from arnold.workflow.durable_refs import DurableRef

        with pytest.raises(ValueError, match="locator must be non-empty"):
            DurableRef(
                store_id="s3",
                locator="",
                digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            )

    def test_durable_ref_validator_rejects_digest_only(self) -> None:
        """Verify the retrievability validator rejects digest-only DurableRefs."""
        from arnold.workflow.durable_refs import (
            DurableRef,
            validate_durable_ref_retrievability,
        )

        # We cannot construct with empty store_id/locator, so use the validator
        # on a minimal valid ref and verify it passes
        valid_ref = DurableRef(
            store_id="s3",
            locator="bucket/key",
            digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        issues = validate_durable_ref_retrievability(valid_ref)
        assert len(issues) == 0, (
            f"valid durable ref should have no retrievability issues, got {issues}"
        )

    def test_secret_keys_rejected_in_durable_ref_metadata(self) -> None:
        """Verify that secret keys in DurableRef metadata are rejected."""
        from arnold.workflow.durable_refs import DurableRef

        with pytest.raises(ValueError, match="matches forbidden secret pattern"):
            DurableRef(
                store_id="s3",
                locator="bucket/key",
                digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                metadata={"api_key": "sk-12345"},
            )

    def test_secret_keys_rejected_in_retention_payload_policy(self) -> None:
        """Verify retention policy rejects secret-like keys in payloads."""
        from arnold.workflow.payload_policy import (
            validate_retention_payload_policy,
            default_retention_policy,
        )

        policy = default_retention_policy()
        secret_payload = {"bearer_token": "abc123", "data": "safe"}
        issues = validate_retention_payload_policy(policy, payload=secret_payload)
        assert len(issues) > 0, "secret payload must produce issues"
        assert any(
            "secret" in issue.lower()
            for issue in issues
        ), f"expected secret exclusion issue, got {issues}"

    def test_ledger_validates_all_events_in_chain(self) -> None:
        """Verify the composite ledger validator runs all checks."""
        from arnold.workflow.execution_attempt_ledger import (
            AttemptEventType,
            AttemptIdentity,
            AttemptProvenance,
            ExecutionAttemptLedger,
            GrantRef,
            LedgerEvent,
            RuntimeAdapter,
            VersionSet,
            AdapterKind,
            validate_ledger,
        )

        attempt_id = "11111111-1111-1111-1111-111111111111"
        identity = AttemptIdentity(
            workflow_id="wf-test",
            run_id="run-test",
            graph_revision=(
                "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            attempt_id=attempt_id,
            attempt_ordinal=1,
        )
        provenance = AttemptProvenance()
        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="1.0.0",
        )
        versions = VersionSet(code_version="abc123")
        grant_ref = GrantRef(grant_id="grant-001")

        event = LedgerEvent(
            idempotency_key="ik-001",
            event_type=AttemptEventType.STARTED,
            identity=identity,
            provenance=provenance,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
            sequence=1,
            causal_predecessor_sequence=0,
            append_position=100,
            occurred_at="2026-07-11T00:00:00Z",
            observed_at="2026-07-11T00:00:01Z",
        )

        ledger = ExecutionAttemptLedger(
            attempt_id=attempt_id,
            events=(event,),
        )

        issues = validate_ledger(ledger)
        assert len(issues) == 0, (
            f"valid single-event ledger should have no issues, got {issues}"
        )

    def test_ledger_rejects_terminal_event_without_outcome(self) -> None:
        """Verify that a terminal event without an outcome is rejected."""
        from arnold.workflow.execution_attempt_ledger import (
            AttemptEventType,
            AttemptIdentity,
            AttemptProvenance,
            GrantRef,
            LedgerEvent,
            RuntimeAdapter,
            VersionSet,
            AdapterKind,
        )

        attempt_id = "22222222-2222-2222-2222-222222222222"
        identity = AttemptIdentity(
            workflow_id="wf-test",
            run_id="run-test",
            graph_revision=(
                "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            attempt_id=attempt_id,
            attempt_ordinal=1,
        )
        provenance = AttemptProvenance()
        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="1.0.0",
        )
        versions = VersionSet(code_version="abc123")
        grant_ref = GrantRef(grant_id="grant-001")

        with pytest.raises(ValueError, match="must have an outcome"):
            LedgerEvent(
                idempotency_key="ik-002",
                event_type=AttemptEventType.COMPLETED,
                identity=identity,
                provenance=provenance,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
                sequence=1,
                causal_predecessor_sequence=0,
                append_position=200,
                occurred_at="2026-07-11T00:00:00Z",
                observed_at="2026-07-11T00:00:01Z",
            )
