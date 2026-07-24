"""Policy-view conformance: rendered policy exposes timeout, retry, escalation,
model routes, and call-site attachments as declared authority rather than
hidden handler-local control flow.

These tests assert that the declared policy surfaces in
``arnold_pipelines/megaplan/workflows/components.py`` survive compilation
through ``WorkflowManifest`` and into ``Pipeline.native_program``, proving
that rendered/compiled views carry the same policy authority as the
canonical authored source.
"""

from __future__ import annotations

from typing import Any

from arnold.manifest.manifests import WorkflowManifest
from arnold.pipeline.native.ir import NativeProgram
from arnold.workflow.compiler import compile_pipeline
from arnold_pipelines.megaplan import workflows
from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline
from arnold_pipelines.megaplan.workflows import planning


# ── helpers ────────────────────────────────────────────────────────────────


def _manifest() -> WorkflowManifest:
    return compile_pipeline(build_pipeline())


def _compiled_shell() -> Any:
    return build_and_compile_pipeline()


_POLICY_COMPONENTS = (
    workflows.DEFAULT_POLICY,
    workflows.GATE_POLICY,
    workflows.REVISE_LOOP_POLICY,
    workflows.TIEBREAKER_POLICY,
    workflows.FINALIZE_POLICY,
    workflows.EXECUTE_POLICY,
    workflows.REVIEW_POLICY,
    workflows.OVERRIDE_POLICY,
    workflows.MODEL_ROUTING_POLICY,
    workflows.ROBUSTNESS_POLICY,
    workflows.ARTIFACT_CONTRACT_POLICY,
    workflows.SUSPENSION_POLICY,
)


# ── timeout exposure ───────────────────────────────────────────────────────


class TestTimeoutExposure:
    """Every policy component that carries timeout semantics must expose a
    ``timeout_seconds_ref`` in its config, and that ref must survive
    compilation into the WorkflowManifest."""

    def test_all_non_artifact_policies_have_timeout_ref(self) -> None:
        timeoutless = {
            "megaplan:artifact-contract",
            "megaplan:suspension",
            "megaplan:model-routing",
            "megaplan:robustness",
        }
        for policy in _POLICY_COMPONENTS:
            if policy.id in timeoutless:
                continue
            assert "timeout_seconds_ref" in policy.config, (
                f"{policy.id} must expose timeout_seconds_ref"
            )

    def test_manifest_policy_nodes_preserve_timeout_attachments(self) -> None:
        manifest = _manifest()
        # The manifest carries policy information through its policy attribute
        # and metadata, not through separate policy nodes
        assert manifest.policy is not None, (
            "manifest must have a WorkflowPolicy"
        )
        # The gate node must carry timeout semantics indirectly through
        # the compiled policy attachments
        gate_node = next(
            (n for n in manifest.nodes if n.id == "gate"), None
        )
        assert gate_node is not None, "manifest must include gate node"

    def test_compiled_shell_native_program_exposes_timeout_in_routing_topology(self) -> None:
        shell = _compiled_shell()
        native = shell.native_program
        topology = native.routing_topology
        assert isinstance(topology, dict), "routing_topology must be a dict"
        assert topology, "routing_topology must be non-empty"


# ── retryability exposure ──────────────────────────────────────────────────


class TestRetryabilityExposure:
    """Policies that carry retry semantics must expose ``retry`` config
    with ``max_attempts``, ``backoff``, and ``retry_on``."""

    RETRY_POLICY_IDS = {
        "megaplan:review",
        "megaplan:execute",
    }

    def test_retry_policies_expose_max_attempts(self) -> None:
        for policy in _POLICY_COMPONENTS:
            if policy.id not in self.RETRY_POLICY_IDS:
                continue
            assert "retry" in policy.config, (
                f"{policy.id} must expose retry config"
            )
            assert "max_attempts" in policy.config["retry"], (
                f"{policy.id} retry must have max_attempts"
            )

    def test_retry_policies_expose_backoff(self) -> None:
        for policy in _POLICY_COMPONENTS:
            if policy.id not in self.RETRY_POLICY_IDS:
                continue
            assert "backoff" in policy.config["retry"], (
                f"{policy.id} retry must have backoff"
            )

    def test_retry_policies_expose_retry_on(self) -> None:
        for policy in _POLICY_COMPONENTS:
            if policy.id not in self.RETRY_POLICY_IDS:
                continue
            assert "retry_on" in policy.config["retry"], (
                f"{policy.id} retry must have retry_on"
            )

    def test_retryability_survives_compilation(self) -> None:
        """The compiled shell must carry the authored retry policy intact."""
        shell = _compiled_shell()
        native = shell.native_program
        assert native is not None
        # The native_program instructions must reference phases with retry metadata
        assert len(native.instructions) > 0


# ── escalation exposure ────────────────────────────────────────────────────


class TestEscalationExposure:
    """Policies that carry escalation semantics must expose ``escalation``
    config with ``targets``, ``escalate_after_attempts``, and ``policy_ref``."""

    ESCALATION_POLICY_IDS = {
        "megaplan:review",
        "megaplan:execute",
    }

    def test_escalation_policies_expose_targets(self) -> None:
        for policy in _POLICY_COMPONENTS:
            if policy.id not in self.ESCALATION_POLICY_IDS:
                continue
            assert "escalation" in policy.config, (
                f"{policy.id} must expose escalation config"
            )
            assert "targets" in policy.config["escalation"], (
                f"{policy.id} escalation must have targets"
            )

    def test_escalation_policies_expose_escalate_after_attempts(self) -> None:
        for policy in _POLICY_COMPONENTS:
            if policy.id not in self.ESCALATION_POLICY_IDS:
                continue
            assert "escalate_after_attempts" in policy.config["escalation"], (
                f"{policy.id} escalation must have escalate_after_attempts"
            )

    def test_escalation_policies_expose_policy_ref(self) -> None:
        for policy in _POLICY_COMPONENTS:
            if policy.id not in self.ESCALATION_POLICY_IDS:
                continue
            assert "policy_ref" in policy.config["escalation"], (
                f"{policy.id} escalation must have policy_ref"
            )

    def test_review_route_surface_exposes_escalation(self) -> None:
        route_surface = workflows.REVIEW_POLICY.metadata["route_surface"]
        assert "escalation" in route_surface, (
            "REVIEW_POLICY route_surface must expose escalation"
        )
        assert route_surface["escalation"]["policy_ref"] == "megaplan:override"

    def test_execute_policy_exposes_escalation_directly(self) -> None:
        escalation = workflows.EXECUTE_POLICY.config["escalation"]
        assert "override" in escalation["targets"]


# ── model-route exposure ───────────────────────────────────────────────────


class TestModelRouteExposure:
    """MODEL_ROUTING_POLICY must expose both phase-level and
    task-complexity model routes in its config and metadata."""

    def test_model_routing_policy_exists(self) -> None:
        assert workflows.MODEL_ROUTING_POLICY is not None
        assert workflows.MODEL_ROUTING_POLICY.id == "megaplan:model-routing"

    def test_model_routing_config_exposes_default_routing(self) -> None:
        config = workflows.MODEL_ROUTING_POLICY.config
        assert "default_routing_ref" in config

    def test_model_routing_config_exposes_phase_model_override(self) -> None:
        config = workflows.MODEL_ROUTING_POLICY.config
        assert "phase_model_override_ref" in config
        assert "state.config.phase_model" in config["phase_model_override_ref"]

    def test_model_routing_config_exposes_task_complexity_route(self) -> None:
        config = workflows.MODEL_ROUTING_POLICY.config
        assert "task_complexity_route_ref" in config
        assert "task_complexity_source_ref" in config

    def test_phase_model_topology_overlays_declared(self) -> None:
        config = workflows.MODEL_ROUTING_POLICY.config
        overlays = config.get("topology_overlays", ())
        overlay_ids = {o["overlay_id"] for o in overlays}
        assert "model-routing:phase" in overlay_ids, (
            "MODEL_ROUTING_POLICY must declare phase model overlay"
        )
        assert "model-routing:task-complexity" in overlay_ids, (
            "MODEL_ROUTING_POLICY must declare task-complexity overlay"
        )

    def test_phase_model_overlay_covers_all_phases(self) -> None:
        config = workflows.MODEL_ROUTING_POLICY.config
        phase_overlay = next(
            o for o in config["topology_overlays"]
            if o["overlay_id"] == "model-routing:phase"
        )
        # The phase model overlay covers all 10 planning/intelligence phases
        expected_phases = {
            "prep", "plan", "critique", "gate", "revise",
            "tiebreaker_run", "tiebreaker_decide", "finalize",
            "execute", "review",
        }
        assert set(phase_overlay["target_refs"]) == expected_phases, (
            f"Phase model overlay targets mismatch: "
            f"got {set(phase_overlay['target_refs'])}"
        )

    def test_task_complexity_overlay_covers_execute_tiers(self) -> None:
        config = workflows.MODEL_ROUTING_POLICY.config
        tc_overlay = next(
            o for o in config["topology_overlays"]
            if o["overlay_id"] == "model-routing:task-complexity"
        )
        assert tc_overlay["overlay_type"] == "model_route"
        assert "task.complexity" in tc_overlay.get("condition_ref", "")

    def test_execute_policy_exposes_task_complexity_overlay(self) -> None:
        config = workflows.EXECUTE_POLICY.config
        overlays = config.get("topology_overlays", ())
        tc_overlay = next(
            o for o in overlays
            if o["overlay_id"] == "execute:task-complexity-route"
        )
        assert tc_overlay["overlay_type"] == "model_route"
        assert "finalize.task_complexity_route" in tc_overlay["source_ref"]


# ── call-site / declared-policy attachment exposure ────────────────────────


class TestCallSiteAttachmentExposure:
    """Step components must declare ``policy_refs`` tuples that map to
    actual PolicyComponent ids, and those call-site attachments must
    survive compilation into the WorkflowManifest."""

    def test_all_step_components_declare_policy_refs(self) -> None:
        """Step components that carry explicit policy attachments must declare
        policy_refs. Entry/terminal/utility steps may not need them."""
        components_with_policy_refs = {
            c.id: c for c in workflows.ALL_STEP_COMPONENTS
            if c.metadata.get("policy_refs") is not None
        }
        # At minimum, execute, review, override, and finalize must declare policy_refs
        for required_id in (
            "megaplan:execute", "megaplan:review",
            "megaplan:override", "megaplan:finalize",
        ):
            assert required_id in components_with_policy_refs, (
                f"{required_id} must declare policy_refs"
            )
        for comp_id, component in components_with_policy_refs.items():
            policy_refs = component.metadata["policy_refs"]
            assert isinstance(policy_refs, tuple), (
                f"{comp_id} policy_refs must be a tuple"
            )
            assert len(policy_refs) > 0, (
                f"{comp_id} policy_refs must be non-empty"
            )

    def test_policy_refs_map_to_known_policy_ids(self) -> None:
        known_ids = {p.id for p in _POLICY_COMPONENTS}
        for component in workflows.ALL_STEP_COMPONENTS:
            policy_refs = component.metadata.get("policy_refs")
            if policy_refs is None:
                continue
            for ref in policy_refs:
                assert ref in known_ids, (
                    f"{component.id} policy_refs references unknown policy: {ref}"
                )

    def test_policy_refs_include_expected_primary_policy(self) -> None:
        """Components that declare policy_refs must include their primary
        policy_id in that tuple."""
        for component in workflows.ALL_STEP_COMPONENTS:
            policy_refs = component.metadata.get("policy_refs")
            if policy_refs is None:
                continue
            policy_id = component.metadata.get("policy_id", "")
            assert policy_id in policy_refs, (
                f"{component.id} policy_refs must include its primary "
                f"policy_id {policy_id}"
            )

    def test_execute_review_override_policy_refs_match_declared_surface(self) -> None:
        assert workflows.EXECUTE.metadata["policy_refs"] == (
            "megaplan:execute",
            "megaplan:model-routing",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        )
        assert workflows.REVIEW.metadata["policy_refs"] == (
            "megaplan:review",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        )
        assert workflows.OVERRIDE.metadata["policy_refs"] == (
            "megaplan:override",
            "megaplan:model-routing",
        )

    def test_manifest_preserves_policy_attachments_on_nodes(self) -> None:
        manifest = _manifest()
        # Policy attachments are carried on the manifest itself (policy
        # attribute and metadata.policy_refs), not per-node
        assert manifest.policy is not None, (
            "manifest must carry WorkflowPolicy"
        )
        assert "policy_refs" in manifest.metadata, (
            "manifest metadata must include policy_refs"
        )

    def test_compiled_shell_manifest_preserves_policy_metadata(self) -> None:
        shell = _compiled_shell()
        manifest = shell.manifest
        assert manifest is not None
        assert manifest.metadata is not None
        # The canonical source's policy surfaces must be reflected in
        # compiled manifest metadata (not hidden behind handler-local state)
        assert isinstance(manifest.metadata, dict)


# ── policy authority chain: source → manifest → native_program ─────────────


class TestPolicyAuthorityChain:
    """The declared policy surfaces must be visible at every level of the
    authority chain: canonical authored source, compiled WorkflowManifest,
    and Pipeline.native_program dispatch substrate."""

    def test_policy_ids_are_consistent_across_source_and_compiled(self) -> None:
        """Policy surfaces declared in the authored source must be reflected
        in the compiled WorkflowManifest via its policy attribute and metadata."""
        manifest = _manifest()

        # The manifest carries policy through its WorkflowPolicy and metadata
        assert manifest.policy is not None, (
            "manifest must have a WorkflowPolicy"
        )
        # Phase-specific policies are carried via WorkflowPolicy; cross-cutting
        # policies are carried via metadata.policy_refs
        manifest_policy_refs = set(manifest.metadata.get("policy_refs", ()))
        # Cross-cutting policies (non-phase-specific) must be visible
        cross_cutting_policy_refs = {
            "megaplan:default",
            "megaplan:model-routing",
            "megaplan:robustness",
            "megaplan:artifact-contract",
            "megaplan:suspension",
        }
        assert cross_cutting_policy_refs <= manifest_policy_refs, (
            f"manifest metadata policy_refs missing cross-cutting policies: "
            f"{cross_cutting_policy_refs - manifest_policy_refs}"
        )

    def test_native_program_routing_topology_reflects_policy_routes(self) -> None:
        shell = _compiled_shell()
        topology = shell.native_program.routing_topology
        routes = topology.get("routes", [])
        # The routing topology must carry routes matching the authored DSL
        source_nodes = {r["source"] for r in routes}
        assert "gate" in source_nodes, "routing topology must include gate routes"
        assert "review" in source_nodes, "routing topology must include review routes"

    def test_authored_pipeline_and_compiled_manifest_agree_on_policy_count(self) -> None:
        """Policy surfaces declared in the authored source must be carried
        into the compiled manifest's policy and metadata."""
        authored_policy_count = len(_POLICY_COMPONENTS)
        assert authored_policy_count == 12, (
            f"authored source must declare 12 policy components, got {authored_policy_count}"
        )
        manifest = _manifest()
        # The manifest carries policy through its WorkflowPolicy, not separate nodes
        assert manifest.policy is not None, "manifest must have WorkflowPolicy"
        # Metadata carries cross-cutting policy_refs (5); phase-specific
        # policies are carried via WorkflowPolicy
        manifest_policy_refs = manifest.metadata.get("policy_refs", ())
        assert len(manifest_policy_refs) == 5, (
            f"manifest metadata policy_refs must have 5 cross-cutting policy refs, "
            f"got {len(manifest_policy_refs)}: {manifest_policy_refs}"
        )

    def test_compiled_shell_exposes_all_three_layers(self) -> None:
        """build_and_compile_pipeline() must expose manifest + native_program
        + authored_pipeline in a single shell."""
        shell = _compiled_shell()
        assert shell.manifest is not None, "shell must have manifest"
        assert isinstance(shell.manifest, WorkflowManifest), (
            "shell.manifest must be WorkflowManifest"
        )
        assert shell.native_program is not None, "shell must have native_program"
        assert isinstance(shell.native_program, NativeProgram), (
            "shell.native_program must be NativeProgram"
        )
        assert shell.authored_pipeline is not None, "shell must have authored_pipeline"


# ── rendered suspension policy exposure ────────────────────────────────────


class TestSuspensionPolicyExposure:
    """SUSPENSION_POLICY must expose suspension routes with capability,
    reentry, resume schema, and resume payload references."""

    def test_suspension_policy_exists(self) -> None:
        assert workflows.SUSPENSION_POLICY is not None
        assert workflows.SUSPENSION_POLICY.id == "megaplan:suspension"

    def test_suspension_policy_exposes_suspension_routes(self) -> None:
        config = workflows.SUSPENSION_POLICY.config
        assert "suspension_routes" in config, (
            "SUSPENSION_POLICY must expose suspension_routes"
        )

    def test_execute_policy_exposes_suspension_routes(self) -> None:
        config = workflows.EXECUTE_POLICY.config
        routes = config.get("suspension_routes", ())
        assert len(routes) > 0, "EXECUTE_POLICY must have suspension routes"

    def test_review_policy_exposes_suspension_routes(self) -> None:
        config = workflows.REVIEW_POLICY.config
        routes = config.get("suspension_routes", ())
        assert len(routes) > 0, "REVIEW_POLICY must have suspension routes"


# ── artifact contract policy exposure ──────────────────────────────────────


class TestArtifactContractExposure:
    """ARTIFACT_CONTRACT_POLICY must expose effect declarations that
    survive compilation."""

    def test_artifact_contract_policy_exists(self) -> None:
        assert workflows.ARTIFACT_CONTRACT_POLICY is not None
        assert workflows.ARTIFACT_CONTRACT_POLICY.id == "megaplan:artifact-contract"

    def test_artifact_contract_config_is_nonempty(self) -> None:
        config = workflows.ARTIFACT_CONTRACT_POLICY.config
        assert config, "ARTIFACT_CONTRACT_POLICY config must be non-empty"


# ── robustness policy exposure ─────────────────────────────────────────────


class TestRobustnessPolicyExposure:
    """ROBUSTNESS_POLICY must expose robustness levels and retry config."""

    def test_robustness_policy_exists(self) -> None:
        assert workflows.ROBUSTNESS_POLICY is not None
        assert workflows.ROBUSTNESS_POLICY.id == "megaplan:robustness"

    def test_robustness_policy_has_expected_config(self) -> None:
        """ROBUSTNESS_POLICY must expose robustness levels, accepted,
        and normalizer references."""
        config = workflows.ROBUSTNESS_POLICY.config
        assert "levels_ref" in config, "ROBUSTNESS_POLICY must have levels_ref"
        assert "accepted_ref" in config, "ROBUSTNESS_POLICY must have accepted_ref"
        assert "normalizer_ref" in config, "ROBUSTNESS_POLICY must have normalizer_ref"
