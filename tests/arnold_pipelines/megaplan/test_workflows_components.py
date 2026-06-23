"""Tests for Megaplan workflow authoring components."""

from __future__ import annotations

import importlib
import sys

from arnold.workflow.authoring import ComponentKind, PromptComponent, StepComponent

from arnold_pipelines.megaplan import workflows


class TestWorkflowComponents:
    def test_all_exports_are_step_or_prompt_components(self) -> None:
        for component in workflows.ALL_STEP_COMPONENTS:
            assert isinstance(component, StepComponent)
            assert component.kind == ComponentKind.STEP
        for prompt in workflows.PROMPT_COMPONENTS:
            assert isinstance(prompt, PromptComponent)
            assert prompt.kind == ComponentKind.PROMPT

    def test_step_ids_are_stable(self) -> None:
        assert [c.id.removeprefix("megaplan:") for c in workflows.ALL_STEP_COMPONENTS] == [
            "prep",
            "plan",
            "critique",
            "gate",
            "revise",
            "tiebreaker_run",
            "tiebreaker_decide",
            "finalize",
            "execute",
            "review",
            "halt",
            "override",
        ]

    def test_lookup_by_step_id(self) -> None:
        assert workflows.STEP_COMPONENTS_BY_ID["gate"].label == "Megaplan gate"
        assert workflows.STEP_COMPONENTS_BY_ID["halt"].metadata["terminal"] is True

    def test_handler_refs_point_to_megaplan_handlers(self) -> None:
        for component in workflows.ALL_STEP_COMPONENTS:
            handler_ref = component.metadata.get("handler_ref")
            if handler_ref is None:
                assert component.id == "megaplan:halt", "only halt lacks a handler"
                continue
            assert handler_ref.startswith("arnold_pipelines.megaplan.handlers:"), handler_ref

    def test_prompt_components_reference_resolver_not_strings(self) -> None:
        for prompt in workflows.PROMPT_COMPONENTS:
            assert prompt.provenance.qualname == "create_prompt"
            assert prompt.metadata["resolver_ref"] == "arnold_pipelines.megaplan.prompts:create_prompt"
            assert "builder_family_refs" in prompt.metadata
            assert prompt.template is None, "prompt strings are rendered by create_prompt, not copied"

    def test_capability_requirements_match_runtime(self) -> None:
        assert workflows.CAPABILITY_REQUIREMENTS == {
            "megaplan:planning": {"route": "default", "required": True},
            "human:gate": {"route": "default", "required": False},
            "human:review": {"route": "default", "required": False},
        }

    def test_runtime_branch_vocabulary_is_declared(self) -> None:
        gate = workflows.STEP_COMPONENTS_BY_ID["gate"]
        assert gate.metadata["runtime_branch_vocabulary"] == (
            "proceed",
            "iterate",
            "tiebreaker",
            "escalate",
            "abort",
            "suspend",
            "blocked_preflight",
            "force_proceed",
        )
        assert workflows.STEP_COMPONENTS_BY_ID["review"].metadata["runtime_branch_vocabulary"] == (
            "pass",
            "rework",
        )

    def test_importing_components_does_not_load_legacy_package(self) -> None:
        before = set(sys.modules.keys())
        importlib.reload(workflows)
        loaded = {m for m in set(sys.modules.keys()) - before if m.startswith("arnold.pipelines.megaplan.")}
        assert loaded == set(), f"components import loaded legacy modules: {loaded}"

    def test_components_do_not_invoke_handlers_or_render_prompts(self) -> None:
        # The components module must contain only static metadata; no runtime
        # function calls that execute handlers, render prompts, or touch plan
        # state.  Handler references are allowed as literal strings.
        source = workflows.components.__file__
        text = open(source, encoding="utf-8").read()
        banned_calls = ["create_prompt(", "load_plan(", "PlanState(", "emit("]
        for token in banned_calls:
            assert token not in text, f"components source contains runtime call: {token}"
