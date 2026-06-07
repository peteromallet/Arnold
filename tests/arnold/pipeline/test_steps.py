"""Tests for neutral Arnold steps and Megaplan bridge step compatibility.

Proves:
* Neutral AgentStep / PanelReviewerStep use ``artifact_root`` (no ``plan_dir``).
* Neutral steps write versioned artifacts under ``artifact_root``.
* Neutral steps fail cleanly when ``plan_dir`` is accessed (AttributeError on
  Arnold StepContext).
* Megaplan bridge steps (``megaplan._pipeline.steps.agent.AgentStep``,
  ``megaplan._pipeline.steps.panel.PanelReviewerStep``) preserve the legacy
  ``plan_dir``-based artifact layout.
* Neutral steps are importable from ``arnold.pipeline.steps``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import ContractResult
from arnold.pipeline.resources import PipelineResourceBundle
from arnold.pipeline.steps.agent import AgentStep
from arnold.pipeline.steps.panel import PanelReviewerStep
from arnold.pipeline.types import StepContext, StepResult


# ── helpers ───────────────────────────────────────────────────────────────


def _make_ctx(artifact_root: str | Path, **kwargs: Any) -> StepContext:
    """Build a neutral Arnold StepContext with *artifact_root*."""
    return StepContext(
        artifact_root=str(artifact_root),
        state={},
        resource_handles=kwargs.pop("resource_handles", {}),
        mode=kwargs.pop("mode", "default"),
        inputs=kwargs.pop("inputs", {}),
        **kwargs,
    )


def _bundle(prompt_dir: str | Path) -> PipelineResourceBundle:
    """Build a minimal bundle with a prompt directory."""
    return PipelineResourceBundle(
        base_dir=Path(prompt_dir),
        prompt_dir=Path(prompt_dir),
    )


# ── Neutral AgentStep ─────────────────────────────────────────────────────


class TestNeutralAgentStep:
    """Neutral AgentStep uses artifact_root and writes versioned output."""

    def test_writes_versioned_artifact(self, tmp_path: Path) -> None:
        """AgentStep writes <artifact_root>/<name>/<label>/v1.md."""
        step = AgentStep(
            name="draft",
            _prompt_source="Write a story.",
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)

        assert isinstance(result, StepResult)
        assert "draft" in result.outputs
        output_path = Path(result.outputs["draft"])
        assert output_path.exists()
        # Expected layout: <tmp>/draft/markdown/v1.md
        expected_dir = tmp_path / "draft" / "markdown"
        assert output_path.parent == expected_dir
        assert output_path.name == "v1.md"
        assert output_path.read_text() == "Write a story."

    def test_version_increments(self, tmp_path: Path) -> None:
        """Second run increments version number."""
        step = AgentStep(
            name="draft",
            _prompt_source="Write a story.",
        )
        ctx = _make_ctx(tmp_path)
        result1 = step.run(ctx)
        result2 = step.run(ctx)

        v1 = Path(result1.outputs["draft"])
        v2 = Path(result2.outputs["draft"])
        assert v1.name == "v1.md"
        assert v2.name == "v2.md"

    def test_worker_is_called(self, tmp_path: Path) -> None:
        """When _worker is set, its return value is written."""

        def fake_worker(**kwargs: object) -> str:
            return f"processed {kwargs.get('step_name', '?')}"

        step = AgentStep(
            name="draft",
            _prompt_source="Write.",
            _worker=fake_worker,
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)

        output_path = Path(result.outputs["draft"])
        assert output_path.read_text() == "processed draft"

    def test_no_plan_dir_on_context(self, tmp_path: Path) -> None:
        """Arnold StepContext has artifact_root, NOT plan_dir."""
        step = AgentStep(name="draft", _prompt_source="Write.")
        ctx = _make_ctx(tmp_path)
        # Arnold StepContext has artifact_root
        assert hasattr(ctx, "artifact_root")
        assert ctx.artifact_root == str(tmp_path)
        # Arnold StepContext does NOT have plan_dir
        assert not hasattr(ctx, "plan_dir")

    def test_plan_dir_access_raises(self, tmp_path: Path) -> None:
        """Accessing plan_dir on Arnold StepContext is an AttributeError."""
        ctx = _make_ctx(tmp_path)
        with pytest.raises(AttributeError):
            _ = ctx.plan_dir  # type: ignore[attr-defined]

    def test_inputs_are_interpolated(self, tmp_path: Path) -> None:
        """{name} placeholders in prompt are replaced with input values."""
        step = AgentStep(
            name="summary",
            _prompt_source="Summarize: {text}",
            _input_refs=["text"],
        )
        ctx = _make_ctx(tmp_path, inputs={"text": "hello world"})
        result = step.run(ctx)

        output_path = Path(result.outputs["summary"])
        content = output_path.read_text()
        assert "hello world" in content

    def test_interpolate_non_string_inputs(self, tmp_path: Path) -> None:
        """Non-string input values are str()'d for interpolation."""
        step = AgentStep(
            name="count",
            _prompt_source="Count: {num}",
            _input_refs=["num"],
        )
        ctx = _make_ctx(tmp_path, inputs={"num": 42})
        result = step.run(ctx)

        output_path = Path(result.outputs["count"])
        assert "42" in output_path.read_text()

    def test_returns_done_next_label(self, tmp_path: Path) -> None:
        """Neutral AgentStep returns next='done'."""
        step = AgentStep(name="draft", _prompt_source="Write.")
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)
        assert result.next == "done"

    def test_no_prompt_source_produces_placeholder(self, tmp_path: Path) -> None:
        """Without _prompt_source, a placeholder message is written."""
        step = AgentStep(name="draft")
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)
        output_path = Path(result.outputs["draft"])
        assert "no prompt source" in output_path.read_text()

    def test_satisfies_step_protocol(self) -> None:
        """Neutral AgentStep has name, kind, and run(ctx) → StepResult."""
        step = AgentStep(name="test")
        assert step.name == "test"
        assert step.kind == "produce"
        assert callable(step.run)

    def test_custom_output_label_and_suffix(self, tmp_path: Path) -> None:
        """_output_label and _output_suffix control artifact path."""
        step = AgentStep(
            name="report",
            _prompt_source="Report.",
            _output_label="json",
            _output_suffix="json",
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)

        output_path = Path(result.outputs["report"])
        assert output_path.suffix == ".json"
        assert output_path.parent.name == "json"


# ── Neutral PanelReviewerStep ──────────────────────────────────────────────


class TestNeutralPanelReviewerStep:
    """Neutral PanelReviewerStep uses artifact_root and writes under reviewer_id."""

    def test_writes_under_reviewer_id(self, tmp_path: Path) -> None:
        """Writes <artifact_root>/<stage_id>/<reviewer_id>/v1.md."""
        step = PanelReviewerStep(
            name="panel_review.optimist",
            _prompt_source="Review optimistically.",
            _reviewer_id="optimist",
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)

        assert "optimist" in result.outputs
        output_path = Path(result.outputs["optimist"])
        assert output_path.exists()
        # Expected: <tmp>/panel_review/optimist/v1.md
        expected_dir = tmp_path / "panel_review" / "optimist"
        assert output_path.parent == expected_dir
        assert output_path.name == "v1.md"

    def test_version_increments(self, tmp_path: Path) -> None:
        """Second run of same reviewer increments version."""
        step = PanelReviewerStep(
            name="panel_review.pessimist",
            _prompt_source="Review pessimistically.",
            _reviewer_id="pessimist",
        )
        ctx = _make_ctx(tmp_path)
        result1 = step.run(ctx)
        result2 = step.run(ctx)

        v1 = Path(result1.outputs["pessimist"])
        v2 = Path(result2.outputs["pessimist"])
        assert v1.name == "v1.md"
        assert v2.name == "v2.md"

    def test_worker_is_called(self, tmp_path: Path) -> None:
        """When _worker is set, its return value is written."""

        def fake_worker(**kwargs: object) -> str:
            return f"review by {kwargs.get('step_name', '?')}"

        step = PanelReviewerStep(
            name="panel_review.critic",
            _prompt_source="Review.",
            _reviewer_id="critic",
            _worker=fake_worker,
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)

        output_path = Path(result.outputs["critic"])
        assert output_path.read_text() == "review by panel_review.critic"

    def test_returns_halt_next_label(self, tmp_path: Path) -> None:
        """Neutral PanelReviewerStep returns next='halt'."""
        step = PanelReviewerStep(
            name="panel_review.reviewer",
            _prompt_source="Review.",
            _reviewer_id="reviewer",
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)
        assert result.next == "halt"

    def test_no_plan_dir_on_context(self, tmp_path: Path) -> None:
        """Arnold StepContext used by neutral PanelReviewer has artifact_root only."""
        step = PanelReviewerStep(
            name="panel_review.r",
            _prompt_source="Review.",
            _reviewer_id="r",
        )
        ctx = _make_ctx(tmp_path)
        assert hasattr(ctx, "artifact_root")
        assert not hasattr(ctx, "plan_dir")
        result = step.run(ctx)
        assert "r" in result.outputs

    def test_name_without_dot(self, tmp_path: Path) -> None:
        """When name has no dot, stage_id is the name itself."""
        step = PanelReviewerStep(
            name="singlereview",
            _prompt_source="Review.",
            _reviewer_id="the_one",
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)

        output_path = Path(result.outputs["the_one"])
        expected_dir = tmp_path / "singlereview" / "the_one"
        assert output_path.parent == expected_dir

    def test_no_prompt_source_produces_placeholder(self, tmp_path: Path) -> None:
        """Without _prompt_source, a placeholder message is written."""
        step = PanelReviewerStep(
            name="panel_review.quiet",
            _reviewer_id="quiet",
        )
        ctx = _make_ctx(tmp_path)
        result = step.run(ctx)
        output_path = Path(result.outputs["quiet"])
        assert "no prompt source" in output_path.read_text()

    def test_satisfies_step_protocol(self) -> None:
        """Neutral PanelReviewerStep has name, kind, and run(ctx) → StepResult."""
        step = PanelReviewerStep(name="panel_review.t", _reviewer_id="t")
        assert step.name == "panel_review.t"
        assert step.kind == "produce"
        assert callable(step.run)


# ── Megaplan bridge steps preserve plan_dir layout ────────────────────────


class TestMegaplanBridgeSteps:
    """Megaplan AgentStep / PanelReviewerStep still work with plan_dir context."""

    def test_megaplan_agent_step_uses_plan_dir(self, tmp_path: Path) -> None:
        """Legacy AgentStep writes under ctx.plan_dir."""
        from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep as MegaAgentStep
        from arnold.pipelines.megaplan._pipeline.types import StepContext as MegaStepContext

        # Create a prompt file so resolve_prompt_text can find it
        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        prompt_md = pipeline_dir / "write_a_plan.md"
        prompt_md.write_text("Write a plan.")

        step = MegaAgentStep(name="draft")
        step._prompt_ref = "write_a_plan.md"  # .md ref resolved against pipeline_dir
        step._pipeline_dir = pipeline_dir

        ctx = MegaStepContext(
            plan_dir=tmp_path / "plan_dir",
            state={},
            profile=None,
            mode="default",
        )
        ctx.plan_dir.mkdir(parents=True, exist_ok=True)

        result = step.run(ctx)
        assert "draft" in result.outputs
        output_path = result.outputs["draft"]
        # Should be under plan_dir, not under another root
        assert str(ctx.plan_dir) in str(output_path)
        assert output_path.exists()

    def test_megaplan_agent_model_invocation_runs_render_and_capture_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Declared model invocations render/capture once and keep markdown output."""
        import arnold.pipelines.megaplan._pipeline.steps.agent as mega_agent_module
        from arnold.pipeline.step_invocation import StepInvocation
        from arnold.pipelines.megaplan.model_seam import (
            CaptureOutcome,
            ModelSeamTelemetry,
            ModelTier,
            RenderedStepMessage,
            TierMetadata,
        )
        from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep as MegaAgentStep
        from arnold.pipelines.megaplan._pipeline.types import StepContext as MegaStepContext

        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        (pipeline_dir / "write_a_plan.md").write_text("Write a plan for {topic}.")

        step = MegaAgentStep(
            name="draft",
            _prompt_ref="write_a_plan.md",
            _pipeline_dir=pipeline_dir,
            _pipeline_name="writer",
            _input_refs=["topic"],
            _worker=lambda **kwargs: json.dumps({"output": kwargs["prompt"]}),
            _invocation=StepInvocation.model(
                adapter_config={
                    "schema": {
                        "type": "object",
                        "properties": {"output": {"type": "string"}},
                    },
                    "system": "follow the schema",
                },
                metadata={"worker": "codex", "validation_step": "draft"},
            ),
        )
        ctx = MegaStepContext(
            plan_dir=tmp_path / "plan_dir",
            state={},
            profile=None,
            mode="default",
            inputs={"topic": tmp_path / "topic.md"},
        )
        ctx.plan_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "topic.md").write_text("testing")

        render_calls: list[StepInvocation] = []
        capture_calls: list[tuple[StepInvocation, Any]] = []

        def _fake_render(invocation: StepInvocation) -> RenderedStepMessage:
            render_calls.append(invocation)
            assert invocation.metadata["worker"] == "codex"
            assert invocation.metadata["system"] == "follow the schema"
            assert invocation.metadata["schema"] == {
                "type": "object",
                "properties": {"output": {"type": "string"}},
            }
            assert invocation.metadata["prompt"] == "Write a plan for testing."
            assert invocation.metadata["message"] == "Write a plan for testing."
            return RenderedStepMessage(
                text="rendered for worker",
                prompt="rendered for worker",
                metadata=invocation.metadata,
                telemetry=ModelSeamTelemetry(
                    tier=TierMetadata(tier=ModelTier.ENFORCED, enforced=True, worker="codex"),
                ),
            )

        expected_contract = ContractResult(payload={"captured": True})

        def _fake_capture(invocation: StepInvocation, output: Any) -> CaptureOutcome:
            capture_calls.append((invocation, output))
            return CaptureOutcome(
                contract_result=expected_contract,
                legacy_payload={"output": "rendered for worker"},
                telemetry=ModelSeamTelemetry(
                    tier=TierMetadata(tier=ModelTier.ENFORCED, enforced=True, worker="codex"),
                ),
            )

        monkeypatch.setattr(mega_agent_module, "render_step_message", _fake_render)
        monkeypatch.setattr(mega_agent_module, "capture_step_output", _fake_capture)

        result = step.run(ctx)

        assert len(render_calls) == 1
        assert len(capture_calls) == 1
        assert capture_calls[0][0] == render_calls[0]
        assert capture_calls[0][1] == json.dumps({"output": "rendered for worker"})
        assert result.contract_result is expected_contract
        output_path = result.outputs["draft"]
        assert output_path.read_text(encoding="utf-8") == json.dumps({"output": "rendered for worker"})
        assert output_path.name == "v1.md"

    def test_megaplan_panel_step_uses_plan_dir(self, tmp_path: Path) -> None:
        """Legacy PanelReviewerStep writes under ctx.plan_dir with reviewer_id."""
        from arnold.pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep as MegaPanelStep
        from arnold.pipelines.megaplan._pipeline.types import StepContext as MegaStepContext

        # Create a prompt file so resolve_prompt_text can find it
        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        prompt_md = pipeline_dir / "review_critically.md"
        prompt_md.write_text("Review critically.")

        step = MegaPanelStep(name="panel_review.pessimist")
        step._prompt_ref = "review_critically.md"
        step._pipeline_dir = pipeline_dir
        step._reviewer_id = "pessimist"

        ctx = MegaStepContext(
            plan_dir=tmp_path / "plan_dir",
            state={},
            profile=None,
            mode="default",
        )
        ctx.plan_dir.mkdir(parents=True, exist_ok=True)

        result = step.run(ctx)
        assert "pessimist" in result.outputs
        output_path = result.outputs["pessimist"]
        assert str(ctx.plan_dir) in str(output_path)
        assert output_path.exists()
        # Expected: <plan_dir>/panel_review/pessimist/v1.md
        expected_dir = ctx.plan_dir / "panel_review" / "pessimist"
        assert output_path.parent == expected_dir

    def test_megaplan_agent_step_wraps_structural_audit_failure_with_author_diagnostic(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import arnold.pipelines.megaplan._pipeline.steps.agent as mega_agent_module
        from arnold.pipeline import Port
        from arnold.pipeline.step_invocation import StepInvocation
        from arnold.pipelines.megaplan.model_seam import (
            CaptureOutcome,
            ModelSeamTelemetry,
            ModelStructuralAuditError,
            ModelTier,
            RenderedStepMessage,
            TierMetadata,
        )
        from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep as MegaAgentStep
        from arnold.pipelines.megaplan._pipeline.types import StepContext as MegaStepContext

        pipeline_dir = tmp_path / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        (pipeline_dir / "write_a_plan.md").write_text("Write a plan for {topic}.")

        step = MegaAgentStep(
            name="draft",
            _prompt_ref="write_a_plan.md",
            _pipeline_dir=pipeline_dir,
            _pipeline_name="writer",
            _input_refs=["topic"],
            _worker=lambda **kwargs: json.dumps({"output": kwargs["prompt"]}),
            _invocation=StepInvocation.model(adapter_config={"schema": {"type": "object"}}),
            produces=(Port(name="result", content_type="application/json", logical_type="review"),),
        )
        ctx = MegaStepContext(
            plan_dir=tmp_path / "plan_dir",
            state={},
            profile=None,
            mode="default",
            inputs={"topic": tmp_path / "topic.md"},
        )
        ctx.plan_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / "topic.md").write_text("testing")

        monkeypatch.setattr(
            mega_agent_module,
            "render_step_message",
            lambda invocation: RenderedStepMessage(
                text="rendered",
                prompt="rendered",
                metadata=invocation.metadata,
                telemetry=ModelSeamTelemetry(
                    tier=TierMetadata(tier=ModelTier.ENFORCED, enforced=True, worker="codex"),
                ),
            ),
        )

        def _boom(invocation: StepInvocation, output: Any) -> CaptureOutcome:
            raise ModelStructuralAuditError("schema_mismatch at /output: expected string")

        monkeypatch.setattr(mega_agent_module, "capture_step_output", _boom)

        with pytest.raises(ValueError, match="Typed contract violation") as excinfo:
            step.run(ctx)

        message = str(excinfo.value)
        assert "producer_stage='draft'" in message
        assert "consumer_stage='model_capture'" in message
        assert "logical_type='review'" in message
        assert "failure_code='worker_structural_audit_failed'" in message
        assert "Suggested author action:" in message


# ── Import path smoke tests ────────────────────────────────────────────────


class TestStepImports:
    """Neutral steps are importable from arnold.pipeline.steps."""

    def test_agent_step_import(self) -> None:
        from arnold.pipeline.steps import AgentStep as AS

        assert AS is AgentStep

    def test_panel_step_import(self) -> None:
        from arnold.pipeline.steps import PanelReviewerStep as PRS

        assert PRS is PanelReviewerStep

    def test_megaplan_steps_still_importable(self) -> None:
        """Megaplan bridge steps still import as expected."""
        from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep as MegaAS
        from arnold.pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep as MegaPRS
        from arnold.pipelines.megaplan._pipeline.steps.human_gate import HumanDecisionStep

        assert MegaAS is not None
        assert MegaPRS is not None
        assert HumanDecisionStep is not None


# ── Boundary: no megaplan in Arnold step modules ──────────────────────────


class TestBoundaryNoMegaplan:
    """Arnold step modules do not import megaplan."""

    def test_agent_module_no_megaplan_import(self) -> None:
        """arnold.pipeline.steps.agent has no megaplan imports."""
        import ast
        import inspect

        import arnold.pipeline.steps.agent as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = getattr(node, "module", None)
                if module_name and "megaplan" in str(module_name):
                    pytest.fail(
                        f"arnold.pipeline.steps.agent imports megaplan: "
                        f"{module_name}"
                    )
                # Also check bare imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "megaplan" in alias.name:
                            pytest.fail(
                                f"arnold.pipeline.steps.agent imports megaplan: "
                                f"{alias.name}"
                            )

    def test_panel_module_no_megaplan_import(self) -> None:
        """arnold.pipeline.steps.panel has no megaplan imports."""
        import ast
        import inspect

        import arnold.pipeline.steps.panel as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = getattr(node, "module", None)
                if module_name and "megaplan" in str(module_name):
                    pytest.fail(
                        f"arnold.pipeline.steps.panel imports megaplan: "
                        f"{module_name}"
                    )
