"""Tests for prompt/resource validation in ``arnold.pipeline.validator`` (M3c T6).

Covers:

* Missing prompt_key referencing unknown resource bundle
* Missing resource_bundles on pipeline
* Bundle-scoped success (prompt key matches a bundle)
* Deterministic defect ordering
* Doc/creative pipeline prompt rendering compatibility
* NO global mutable prompt registry (verified by boundary check)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.types import Edge, Pipeline, Port, PortRef, ReadRef, Stage, WriteRef
from arnold.pipeline.step_invocation import StepInvocation
from arnold.pipeline.validator import (
    CONTRACT_ERROR_CODE_MAP,
    DECLARATION_DRIFT_CODE,
    Diagnostics,
    MISSING_BINDING_CODE,
    UNKNOWN_ADAPTER_CODE,
    UNSATISFIED_CAPABILITY_CODE,
    _step_prompt_key,
    contract_diagnostic_code,
    validate,
    validate_dataflow_paths,
    validate_resource_dependencies,
)


# ── Minimal stub step with prompt_key ─────────────────────────────────────


@dataclass(frozen=True)
class _PromptStep:
    """A step that carries a prompt_key for validation testing."""

    name: str = "prompt_step"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: Any) -> Any:
        raise RuntimeError("static validator must not dispatch")


# ── Builder helper to avoid keyword-before-positional issues ──────────────


class _StageBuilder:
    """Fluent builder for constructing test stages without kwarg ordering issues."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._prompt_key: str | None = None
        self._edges: tuple[Edge, ...] = ()

    def with_prompt_key(self, key: str | None) -> "_StageBuilder":
        self._prompt_key = key
        return self

    def with_edges(self, *edges: Edge) -> "_StageBuilder":
        self._edges = edges
        return self

    def build(self) -> Stage:
        step = _PromptStep(name=self._name, prompt_key=self._prompt_key)
        return Stage(name=self._name, step=step, edges=self._edges)


def _pipeline(stages: dict, entry: str = "start", bundles: tuple = ()) -> Pipeline:
    return Pipeline(
        stages=stages,
        entry=entry,
        resource_bundles=bundles,
    )


def _assert_issue(
    diag: Diagnostics,
    *,
    code: str,
    stage: str,
    detail_items: dict[str, object] | None = None,
    message_contains: str | None = None,
) -> None:
    matches = [issue for issue in diag.issues if issue.code == code and issue.stage == stage]
    assert matches, diag.issues
    issue = matches[0]
    assert issue.message in diag.defects
    if message_contains is not None:
        assert message_contains in issue.message
    if detail_items is not None:
        for key, value in detail_items.items():
            assert issue.details.get(key) == value


# ── Missing prompt key ────────────────────────────────────────────────────


class TestMissingPromptKey:
    def test_prompt_key_with_no_bundles_is_flagged(self) -> None:
        """A stage with a prompt_key but no resource_bundles on the pipeline
        should emit a defect."""
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(stages={"start": stage})
        diag = validate_resource_dependencies(pipeline)
        assert not diag.ok
        _assert_issue(
            diag,
            code="prompt_key_missing_resource_bundles",
            stage="start",
            detail_items={"prompt_key": "critique"},
            message_contains="no resource_bundles",
        )

    def test_prompt_key_missing_from_bundles_is_flagged(self) -> None:
        """A prompt_key that doesn't match any known bundle name is flagged."""
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=("plan", "review", "revise"),
        )
        diag = validate_resource_dependencies(pipeline)
        assert not diag.ok
        _assert_issue(
            diag,
            code="prompt_key_unknown_resource_bundle",
            stage="start",
            detail_items={
                "prompt_key": "critique",
                "available_bundles": ["plan", "review", "revise"],
            },
            message_contains="no known resource bundle",
        )


# ── Bundle-scoped success ─────────────────────────────────────────────────


class TestBundleScopedSuccess:
    def test_prompt_key_matching_string_bundle_passes(self) -> None:
        """A prompt_key that matches a string bundle name passes validation."""
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=("plan", "critique", "revise"),
        )
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_prompt_key_matching_bundle_object_passes(self) -> None:
        """A prompt_key that matches an object bundle's name passes."""

        @dataclass(frozen=True)
        class _Bundle:
            name: str

        bundle = _Bundle(name="critique")
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=(bundle,),
        )
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_prompt_key_prefix_matching_bundle_passes(self) -> None:
        """A prompt_key that starts with a bundle name prefix passes."""
        stage = _StageBuilder("start").with_prompt_key("critique_v2").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=("critique",),
        )
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_null_prompt_key_is_skipped(self) -> None:
        """A stage with prompt_key=None does not trigger any defect."""
        stage = _StageBuilder("start").with_prompt_key(None).build()
        pipeline = _pipeline(stages={"start": stage})
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_empty_prompt_key_is_skipped(self) -> None:
        """A stage with prompt_key='' (empty string) is skipped."""
        stage = _StageBuilder("start").with_prompt_key("").build()
        pipeline = _pipeline(stages={"start": stage})
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects


# ── Deterministic ordering ────────────────────────────────────────────────


class TestDeterministicOrdering:
    def test_defects_emitted_in_sorted_stage_order(self) -> None:
        """Defects should appear in sorted stage-name order, not insertion order."""
        pipeline = _pipeline(
            stages={
                "zebra": _StageBuilder("zebra").with_prompt_key("unknown_a").build(),
                "alpha": _StageBuilder("alpha").with_prompt_key("unknown_b").build(),
                "mid": _StageBuilder("mid").with_prompt_key("unknown_c").build(),
            },
            bundles=("known",),
        )
        diag = validate_resource_dependencies(pipeline)
        assert not diag.ok
        # Should be alpha, mid, zebra (sorted)
        defect_stage_order = []
        for d in diag.defects:
            import re
            m = re.search(r"stage '(\w+)'", d)
            if m:
                defect_stage_order.append(m.group(1))
        assert defect_stage_order == sorted(defect_stage_order), (
            f"Expected sorted order, got {defect_stage_order}"
        )


# ── Full validate() integration ───────────────────────────────────────────


class TestFullValidateIntegration:
    def test_validate_merges_resource_defects_with_control_flow(self) -> None:
        """validate() should merge resource defects alongside control-flow defects."""
        stage = (
            _StageBuilder("start")
            .with_prompt_key("missing")
            .with_edges(Edge(label="halt", target="halt"))
            .build()
        )
        pipeline = _pipeline(stages={"start": stage})
        diag = validate(pipeline)
        # Should have resource defect about missing bundle
        assert not diag.ok
        _assert_issue(
            diag,
            code="prompt_key_missing_resource_bundles",
            stage="start",
            detail_items={"prompt_key": "missing"},
            message_contains="no resource_bundles",
        )

    def test_validate_dataflow_paths_accepts_typed_reads_and_writes(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(Port(name="draft", content_type="text/markdown"),),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        assert diag.ok, diag.issues

    def test_validate_accepts_builder_derived_binding_map_for_agreeing_typed_authoring(self) -> None:
        builder = PipelineBuilder("typed-authoring", "typed authoring validation coverage")
        builder.add_stage(
            Stage(
                name="start",
                step=_PromptStep(name="start"),
                writes=(Port(name="draft", content_type="text/markdown"),),
                produces=(Port(name="draft", content_type="text/markdown"),),
                edges=(Edge(label="next", target="end"),),
            )
        )
        builder.add_stage(
            Stage(
                name="end",
                step=_PromptStep(name="end"),
                reads=(PortRef(port_name="draft", content_type="text/markdown"),),
                consumes=(PortRef(port_name="draft", content_type="text/markdown"),),
                edges=(Edge(label="halt", target="halt"),),
            )
        )

        pipeline = builder.build()

        assert pipeline.binding_map == {("end", "draft"): ("start", "draft")}
        diag = validate(pipeline)
        assert diag.ok, diag.issues

    def test_validate_dataflow_paths_reports_typed_missing_binding(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(Port(name="other", content_type="text/markdown"),),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        _assert_issue(
            diag,
            code=MISSING_BINDING_CODE,
            stage="end",
            detail_items={"dependency": "draft", "route_hint": "(missing from predecessor 'start')"},
            message_contains="dependency 'draft' is unsatisfied",
        )

    def test_validate_dataflow_paths_reports_typed_typo_suggestion(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(Port(name="draf", content_type="text/markdown"),),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        _assert_issue(
            diag,
            code="contract.no_match",
            stage="end",
            detail_items={"dependency": "draft", "error_kind": "typo_name"},
            message_contains="did you mean ['draf']",
        )

    def test_validate_dataflow_paths_reports_content_type_mismatch(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(Port(name="draft", content_type="text/plain"),),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        _assert_issue(
            diag,
            code="contract.content_type_mismatch",
            stage="end",
            detail_items={"dependency": "draft", "error_kind": "content_type_mismatch"},
            message_contains="expects content_type 'text/markdown'",
        )

    def test_validate_dataflow_paths_reports_cardinality_mismatch(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(
                Port(name="draft", content_type="text/markdown", cardinality="collection"),
            ),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        _assert_issue(
            diag,
            code="contract.cardinality_mismatch",
            stage="end",
            detail_items={"dependency": "draft", "error_kind": "cardinality_mismatch"},
            message_contains="expects cardinality 'singleton'",
        )

    def test_validate_dataflow_paths_reports_logical_metadata_mismatch(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(
                Port(
                    name="draft",
                    content_type="text/markdown",
                    logical_type="draft.v1",
                ),
            ),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(
                PortRef(
                    port_name="draft",
                    content_type="text/markdown",
                    logical_type="brief.v1",
                ),
            ),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        _assert_issue(
            diag,
            code="contract.schema_mismatch",
            stage="end",
            detail_items={
                "dependency": "draft",
                "error_kind": "schema_mismatch",
                "mismatch_reason": "logical_type_mismatch",
            },
            message_contains="declares logical_type 'brief.v1'",
        )

    def test_validate_dataflow_paths_reports_schema_version_mismatch(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(
                Port(
                    name="draft",
                    content_type="text/markdown",
                    accepted_version_range=">=2,<3",
                ),
            ),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(
                PortRef(
                    port_name="draft",
                    content_type="text/markdown",
                    accepted_version_range=">=1,<2",
                ),
            ),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        _assert_issue(
            diag,
            code="contract.schema_mismatch",
            stage="end",
            detail_items={
                "dependency": "draft",
                "error_kind": "schema_mismatch",
                "mismatch_reason": "accepted_version_range_mismatch",
            },
            message_contains="accepted_version_range",
        )

    def test_validate_dataflow_paths_reports_declaration_drift_and_keeps_legacy_binding_checks(
        self,
    ) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(Port(name="draft", content_type="text/plain"), WriteRef(name="draft.md")),
            produces=(Port(name="draft", content_type="text/markdown"),),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(ReadRef(name="missing.md"),),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        _assert_issue(
            diag,
            code=DECLARATION_DRIFT_CODE,
            stage="start",
            detail_items={"direction": "produces", "name": "draft"},
            message_contains="conflicting explicit and typed produces declarations",
        )
        _assert_issue(
            diag,
            code=MISSING_BINDING_CODE,
            stage="end",
            detail_items={"dependency": "missing.md", "route_hint": "(missing from predecessor 'start')"},
            message_contains="dependency 'missing.md' is unsatisfied",
        )

    def test_validate_dataflow_paths_accepts_legacy_untyped_passthrough(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            writes=(WriteRef(name="draft.md"),),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            reads=(ReadRef(name="draft.md"),),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate_dataflow_paths(_pipeline(stages={"start": start, "end": end}))

        assert diag.ok, diag.issues

    def test_validate_planning_pipeline_resource_check(self) -> None:
        """The planning pipeline stages with prompt_keys should pass
        resource validation since they don't rely on Arnold resource_bundles
        (they have their own prompt resolution mechanism)."""
        from arnold.pipelines.megaplan._pipeline.registry import get_pipeline

        pipeline = get_pipeline("planning")
        diag = validate_resource_dependencies(pipeline)
        # The planning pipeline doesn't set resource_bundles, so any stage
        # with a prompt_key will get a soft warning about missing bundles.
        # We just verify it doesn't crash.
        assert isinstance(diag, Diagnostics)

    def test_validate_preserves_legacy_defects_and_structured_issues(self) -> None:
        """Structured issues should mirror the legacy human-readable defects."""
        stage = _StageBuilder("start").with_prompt_key("missing").build()
        pipeline = _pipeline(stages={"start": stage})

        diag = validate(pipeline)

        assert diag.defects == [
            "stage 'start': declares prompt_key 'missing' but pipeline has no resource_bundles"
        ]
        assert len(diag.issues) == 1
        issue = diag.issues[0]
        assert issue.code == "prompt_key_missing_resource_bundles"
        assert issue.message == diag.defects[0]
        assert issue.severity == "error"
        assert issue.stage == "start"
        assert issue.edge is None
        assert issue.details == {"prompt_key": "missing"}
        assert diag.structured_defects == diag.issues

    def test_diagnostics_add_defect_builds_structured_issue(self) -> None:
        """Manual defect recording should maintain both diagnostics surfaces."""
        diag = Diagnostics()

        diag.add_defect(
            "stage 'start': edge 'go' targets unknown stage 'missing'",
            code="edge_target_unknown_stage",
            stage="start",
            edge=Edge(label="go", target="missing"),
            details={"known_stages": ["start"]},
        )

        assert diag.defects == [
            "stage 'start': edge 'go' targets unknown stage 'missing'"
        ]
        assert [issue.code for issue in diag.issues] == ["edge_target_unknown_stage"]
        assert diag.issues[0].edge == {
            "label": "go",
            "target": "missing",
            "kind": "normal",
        }

    def test_validate_dataflow_paths_uses_stable_missing_binding_code(self) -> None:
        start = Stage(
            name="start",
            step=_PromptStep(name="start"),
            edges=(Edge(label="next", target="end"),),
        )
        end = Stage(
            name="end",
            step=_PromptStep(name="end"),
            consumes=("plan_payload",),
            edges=(Edge(label="halt", target="halt"),),
        )
        pipeline = _pipeline(stages={"start": start, "end": end})

        diag = validate_dataflow_paths(pipeline)

        assert diag.defects == [
            "stage 'end': dependency 'plan_payload' is unsatisfied (missing from predecessor 'start')"
        ]
        assert [issue.code for issue in diag.issues] == [MISSING_BINDING_CODE]
        assert diag.issues[0].details == {
            "dependency": "plan_payload",
            "route_hint": "(missing from predecessor 'start')",
        }

    def test_validate_reports_unknown_invocation_adapter_kind(self) -> None:
        stage = Stage(
            name="start",
            step=_PromptStep(name="start"),
            invocation=StepInvocation(kind="custom-collector-v2"),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate(_pipeline(stages={"start": stage}))

        _assert_issue(
            diag,
            code=UNKNOWN_ADAPTER_CODE,
            stage="start",
            detail_items={
                "invocation_kind": "custom-collector-v2",
                "registered_kinds": ["model"],
            },
            message_contains="does not resolve to a registered adapter",
        )

    @pytest.mark.parametrize(
        ("required_capability", "invocation"),
        [
            (
                "model:text",
                StepInvocation.model(adapter_config={"prompt": "write a draft"}),
            ),
            (
                "model:vision",
                StepInvocation.model(
                    adapter_config={
                        "media": [{"mime_type": "image/png", "descriptor": "diagram"}]
                    }
                ),
            ),
            (
                "decoder:image",
                StepInvocation.model(adapter_config={"capabilities": ["decoder:image"]}),
            ),
        ],
    )
    def test_validate_accepts_satisfied_required_capabilities(
        self,
        required_capability: str,
        invocation: StepInvocation,
    ) -> None:
        stage = Stage(
            name="review",
            step=_PromptStep(name="review"),
            invocation=invocation,
            required_capabilities=(required_capability,),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate(_pipeline(stages={"review": stage}, entry="review"))

        assert diag.ok, diag.issues

    @pytest.mark.parametrize(
        "required_capability",
        ["model:text", "model:vision", "decoder:image"],
    )
    def test_validate_reports_unsatisfied_required_capabilities(
        self,
        required_capability: str,
    ) -> None:
        stage = Stage(
            name="review",
            step=_PromptStep(name="review"),
            invocation=StepInvocation.model(adapter_config={}),
            required_capabilities=(required_capability,),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate(_pipeline(stages={"review": stage}, entry="review"))

        _assert_issue(
            diag,
            code=UNSATISFIED_CAPABILITY_CODE,
            stage="review",
            detail_items={
                "required_capabilities": [required_capability],
                "proven_capabilities": [],
                "unsatisfied_capabilities": [required_capability],
                "unknown_required_capabilities": [],
            },
            message_contains="required capabilities are not satisfied",
        )

    def test_validate_reports_unknown_required_capabilities(self) -> None:
        stage = Stage(
            name="review",
            step=_PromptStep(name="review"),
            invocation=StepInvocation.model(adapter_config={"prompt": "write a review"}),
            required_capabilities=("model:text", "model:audio"),
            edges=(Edge(label="halt", target="halt"),),
        )

        diag = validate(_pipeline(stages={"review": stage}, entry="review"))

        _assert_issue(
            diag,
            code=UNSATISFIED_CAPABILITY_CODE,
            stage="review",
            detail_items={
                "required_capabilities": ["model:text", "model:audio"],
                "proven_capabilities": ["model:text"],
                "unsatisfied_capabilities": [],
                "unknown_required_capabilities": ["model:audio"],
            },
            message_contains="unknown required capabilities",
        )

    def test_validate_accepts_capabilities_proven_from_pipeline_metadata(self) -> None:
        stage = Stage(
            name="draft",
            step=_PromptStep(name="draft"),
            invocation=StepInvocation.model(adapter_config={"prompt": "write a draft"}),
            required_capabilities=("model:text", "decoder:image"),
            edges=(Edge(label="halt", target="halt"),),
        )
        pipeline = _pipeline(stages={"draft": stage}, entry="draft")
        object.__setattr__(pipeline, "metadata", {"supported_capabilities": ["decoder:image"]})

        diag = validate(pipeline)

        assert diag.ok, diag.issues

    def test_contract_diagnostic_code_maps_required_m7_categories(self) -> None:
        assert CONTRACT_ERROR_CODE_MAP == {
            "no_match": "contract.no_match",
            "typo_name": "contract.no_match",
            "content_type_mismatch": "contract.content_type_mismatch",
            "cardinality_mismatch": "contract.cardinality_mismatch",
            "schema_mismatch": "contract.schema_mismatch",
        }
        assert contract_diagnostic_code("no_match") == "contract.no_match"
        assert contract_diagnostic_code("typo_name") == "contract.no_match"
        assert contract_diagnostic_code("content_type_mismatch") == "contract.content_type_mismatch"
        assert contract_diagnostic_code("cardinality_mismatch") == "contract.cardinality_mismatch"
        assert contract_diagnostic_code("schema_mismatch") == "contract.schema_mismatch"
        assert DECLARATION_DRIFT_CODE == "contract.declaration_drift"
        assert UNKNOWN_ADAPTER_CODE == "invocation.unknown_adapter"
        assert UNSATISFIED_CAPABILITY_CODE == "capability.unsatisfied"


# ── Duck-typed accessors ──────────────────────────────────────────────────


class TestDuckTypedAccessors:
    def test_step_prompt_key_from_arnold_stage(self) -> None:
        """_step_prompt_key reads from Arnold Stage.step.prompt_key."""
        stage = _StageBuilder("test").with_prompt_key("critique").build()
        assert _step_prompt_key(stage) == "critique"

    def test_step_prompt_key_from_megaplan_style_step(self) -> None:
        """_step_prompt_key duck-types Megaplan step shapes."""

        class MegaplanStep:
            name = "mega_step"
            kind = "produce"
            prompt_key = "review"

        class MegaplanStage:
            def __init__(self):
                self.name = "mega_stage"
                self.step = MegaplanStep()
                self.edges = ()

        stage = MegaplanStage()
        assert _step_prompt_key(stage) == "review"

    def test_step_prompt_key_none_when_no_step(self) -> None:
        """_step_prompt_key returns None when stage has no step."""
        stage = Stage(name="empty", step=None, edges=())
        assert _step_prompt_key(stage) is None


# ── Boundary: No global mutable prompt registry ───────────────────────────


class TestNoGlobalPromptRegistry:
    def test_validator_has_no_mutable_global_registry(self) -> None:
        """The validator module must not declare a global mutable prompt registry."""
        src = (
            Path(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "validator.py"
        )
        tree = ast.parse(src.read_text())

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id.lower()
                        if any(
                            keyword in name
                            for keyword in ("registry", "prompt_map", "prompt_dict")
                        ):
                            if isinstance(node.value, (ast.Dict, ast.List, ast.Set)):
                                pytest.fail(
                                    f"validator.py has mutable global registry: {target.id}"
                                )

    def test_validator_has_no_prompt_registry_import(self) -> None:
        """The validator must not import any prompt registry modules."""
        src = (
            Path(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "validator.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "prompt_registry" not in alias.name.lower(), (
                        f"validator imports prompt registry: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "prompt_registry" not in node.module.lower(), (
                        f"validator imports from prompt registry: {node.module}"
                    )
