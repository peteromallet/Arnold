"""Prompt builders for each megaplan step and dispatch tables."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan._core import creative_form_id, is_creative_mode
from arnold_pipelines.megaplan.anchors import render_anchor_block
from arnold_pipelines.megaplan.forms import get_form
from arnold_pipelines.megaplan.types import CliError, PlanState

from ._shared import (
    _render_contracts_block,
    _render_prep_block,
    _resolve_prompt_root,
)
from .critique import (
    _critique_prompt,
    _revise_prompt,
    _write_critique_template,
)
from arnold_pipelines.megaplan.pipelines.creative.prompts.critique_creative import _critique_creative_prompt
from arnold_pipelines.megaplan.pipelines.creative.prompts.critique_joke import _critique_joke_prompt
from arnold_pipelines.megaplan.pipelines.creative.prompts.revise_joke import _revise_joke_prompt
from .execute import (
    _execute_approval_note,
    _execute_batch_prompt as _execute_code_batch_prompt,
    _execute_nudges,
    _execute_prompt,
    _execute_rerun_guidance,
    _execute_review_block,
    _write_execute_batch_template,
    _write_execute_template,
)
from .feedback import build_feedback_prompt
from .finalize import _finalize_prompt, _write_finalize_template
from .gate import _collect_critique_summaries, _flag_summary, _gate_prompt, _write_gate_template


def _feedback_prompt(state: PlanState, plan_dir: Path) -> str:
    """Adapter so build_feedback_prompt fits the _PromptBuilder signature."""
    return build_feedback_prompt(plan_dir, state)
from arnold_pipelines.megaplan.pipelines.doc.prompts.execute_doc import _execute_doc_batch_prompt, _execute_doc_prompt
from arnold_pipelines.megaplan.pipelines.creative.prompts.execute_creative import _execute_creative_batch_prompt, _execute_creative_prompt
from arnold_pipelines.megaplan.pipelines.creative.prompts.execute_joke import _execute_joke_batch_prompt, _execute_joke_prompt
from .planning import (
    PLAN_TEMPLATE,
    _plan_prompt,
    _prep_distill_prompt,
    _prep_prompt,
    _prep_research_prompt,
    _prep_triage_prompt,
)
from .prep_doc import _prep_doc_prompt
from arnold_pipelines.megaplan.pipelines.creative.prompts.prep_joke import _prep_joke_prompt
from arnold_pipelines.megaplan.pipelines.creative.prompts.revise_creative import _revise_creative_prompt
from .review import (
    _review_prompt,
    _settled_decisions_block,
    _settled_decisions_instruction,
    _write_review_template,
    ensure_review_evidence_for_prompt,
)
from .critique_evaluator import _critique_evaluator_prompt, _write_critique_evaluator_template
from .review_doc import _review_doc_prompt
from .review_joke import _review_joke_prompt
from ._projection import PromptProjectionCapabilities

_PromptBuilder = Callable[..., str]


@dataclass(frozen=True)
class PromptComponents:
    """Structured prompt assembly that still degrades to the legacy string."""

    prompt: str
    system: str | None = None
    messages: tuple[Mapping[str, Any], ...] = ()
    schema: Mapping[str, Any] | None = None
    template: Any | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_prompt_text(self) -> str:
        return self.prompt

    def to_model_metadata(self) -> dict[str, Any]:
        payload = {
            "prompt": self.prompt,
            "prompt_components": self,
            **dict(self.metadata),
        }
        if self.system is not None:
            payload["system"] = self.system
        if self.messages:
            payload["messages"] = [dict(message) for message in self.messages]
        if self.schema is not None:
            payload["schema"] = dict(self.schema)
        if self.template is not None:
            payload["template"] = self.template
        return payload

# Shared builder map for all steps that are identical across agents.
_COMMON_BUILDERS: dict[str, _PromptBuilder] = {
    "plan": _plan_prompt,
    "prep": _prep_prompt,
    "prep-triage": _prep_triage_prompt,
    "prep-distill": _prep_distill_prompt,
    "critique": _critique_prompt,
    "critique_evaluator": _critique_evaluator_prompt,
    "revise": _revise_prompt,
    "gate": _gate_prompt,
    "finalize": _finalize_prompt,
    "execute": _execute_prompt,
    "feedback": _feedback_prompt,
}

# Per-agent review overlays — the only step whose wording differs by agent.
_CLAUDE_REVIEW_OVERLAY = partial(
    _review_prompt,
    review_intro="Review the execution critically against user intent and observable success criteria.",
    criteria_guidance="Judge against the success criteria, not plan elegance.",
    task_guidance="Review each task by cross-referencing the executor's per-task `files_changed` and `commands_run` against the git diff and any audit findings.",
    sense_check_guidance="Review every sense check explicitly. Confirm concise executor acknowledgments when they are specific; dig deeper only when they are perfunctory or contradicted by the code.",
)

_CODEX_REVIEW_OVERLAY = partial(
    _review_prompt,
    review_intro="Review the implementation against the success criteria.",
    criteria_guidance="Verify each success criterion explicitly.",
    task_guidance="Cross-reference each task's `files_changed` and `commands_run` against the git diff and any audit findings.",
    sense_check_guidance="Review every `sense_check` explicitly and treat perfunctory acknowledgments as a reason to dig deeper.",
)

# Exported agent builder maps assembled from the shared base + per-agent review.
_CLAUDE_PROMPT_BUILDERS: dict[str, _PromptBuilder] = {**_COMMON_BUILDERS, "review": _CLAUDE_REVIEW_OVERLAY}
_CODEX_PROMPT_BUILDERS: dict[str, _PromptBuilder] = {**_COMMON_BUILDERS, "review": _CODEX_REVIEW_OVERLAY}
_HERMES_PROMPT_BUILDERS: dict[str, _PromptBuilder] = {**_COMMON_BUILDERS, "review": _CLAUDE_REVIEW_OVERLAY}

_NESTED_HARNESS_GUARD = (
    "You are already running inside the megaplan harness for this step. "
    "Do the requested planning/review/execution work directly. "
    "Do NOT invoke the `megaplan` CLI, do NOT read or activate the `megaplan` skill, "
    "do NOT start nested megaplan plans, and do NOT recurse into another planning harness. "
    "Treat mentions of megaplan in the repository or environment as implementation context only.\n\n"
    "WRITE ACCESS CONTRACT: You are running with auto-approved writes inside a writable workspace. "
    "Treat the working directory as fully writable. Do NOT preemptively skip or block tasks on permission, "
    "sandbox, or read-only grounds. Attempt every required edit; only report failure AFTER a real OS-level "
    "rejection from a specific shell command. Do not infer 'read-only' from absence of activity; absence "
    "is not denial. If a single shell command unexpectedly fails, retry with a different invocation before "
    "concluding the environment is restricted."
)


def _prepend_harness_guard(prompt: str) -> str:
    return f"{_NESTED_HARNESS_GUARD}\n\n{prompt}"


def _with_anchor_block(prompt: str, state: PlanState, plan_dir: Path, *, audience: str) -> str:
    anchor_block = render_anchor_block(state, plan_dir, audience=audience)
    if not anchor_block:
        return prompt
    return f"{anchor_block}\n\n{prompt}"


def _builder_kwargs(builder: _PromptBuilder, prompt_kwargs: dict[str, object]) -> dict[str, object]:
    """Forward only kwargs accepted by the target builder."""
    if not prompt_kwargs:
        return {}
    signature = inspect.signature(builder)
    if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return dict(prompt_kwargs)
    accepted = {
        name
        for name, param in signature.parameters.items()
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return {key: value for key, value in prompt_kwargs.items() if key in accepted}


def _execute_batch_prompt(
    state: PlanState,
    plan_dir: Path,
    batch_task_ids: list[str],
    completed_task_ids: set[str] | None = None,
    root: Path | None = None,
    rework_context: dict[str, object] | None = None,
    projection_capabilities: PromptProjectionCapabilities | None = None,
    batch_template_path: Path | None = None,
) -> str:
    mode = state.get("config", {}).get("mode", "code")
    if mode == "doc":
        prompt = _execute_doc_batch_prompt(
            state,
            plan_dir,
            batch_task_ids,
            completed_task_ids,
            root=root,
            projection_capabilities=projection_capabilities,
        )
        return _with_anchor_block(prompt, state, plan_dir, audience="execute-batch")
    if is_creative_mode(state):
        prompt = _execute_creative_batch_prompt(
            state,
            plan_dir,
            batch_task_ids,
            completed_task_ids,
            root=root,
            projection_capabilities=projection_capabilities,
        )
        return _with_anchor_block(prompt, state, plan_dir, audience="execute-batch")
    prompt = _execute_code_batch_prompt(
        state,
        plan_dir,
        batch_task_ids,
        completed_task_ids,
        root=root,
        rework_context=rework_context,
        projection_capabilities=projection_capabilities,
        batch_template_path=batch_template_path,
    )
    return _with_anchor_block(prompt, state, plan_dir, audience="execute-batch")


def _resolve_builder(
    builders: dict[str, _PromptBuilder], step: str, state: PlanState, agent_label: str
) -> _PromptBuilder:
    mode = state.get("config", {}).get("mode", "code")
    if is_creative_mode(state) and get_form(creative_form_id(state) or "joke").id == "joke":
        if step == "prep":
            return _prep_joke_prompt
        if step == "critique":
            return _critique_joke_prompt
        if step == "revise":
            return _revise_joke_prompt
        if step == "execute":
            return _execute_joke_prompt
        if step == "review":
            return partial(
                _review_joke_prompt,
                review_intro="Review the scene critically against the brief, the declared primary criterion, and the approved scene canvas.",
                criteria_guidance="Judge first against the declared primary criterion, then against the remaining success criteria and scene-canvas commitments.",
                task_guidance="Review each task by cross-referencing the executor's per-task `sections_written` against the output scene prose.",
                sense_check_guidance="Review every sense check explicitly. Confirm concise executor acknowledgments when they are specific; dig deeper only when they are perfunctory or contradicted by the scene text.",
            )
    if is_creative_mode(state):
        if step == "prep":
            return _prep_doc_prompt
        if step == "critique":
            return _critique_creative_prompt
        if step == "revise":
            return _revise_creative_prompt
        if step == "execute":
            return _execute_creative_prompt
        if step == "review":
            return partial(
                _review_doc_prompt,
                review_intro="Review the creative artifact critically against the brief, the declared primary criterion, and the approved canvas.",
                criteria_guidance="Judge against the declared primary criterion and the form-specific canvas commitments.",
                task_guidance="Review each task by cross-referencing the executor's per-task `sections_written` against the output artifact.",
                sense_check_guidance="Review every sense check explicitly. Confirm concise executor acknowledgments when they are specific; dig deeper only when they are perfunctory or contradicted by the artifact.",
            )
    if mode == "doc":
        if step == "prep":
            return _prep_doc_prompt
        if step == "execute":
            return _execute_doc_prompt
        if step == "review":
            return partial(
                _review_doc_prompt,
                review_intro="Review the document critically against user intent and observable success criteria.",
                criteria_guidance="Judge against the success criteria, not plan elegance.",
                task_guidance="Review each task by cross-referencing the executor's per-task `sections_written` against the output document.",
                sense_check_guidance="Review every sense check explicitly. Confirm concise executor acknowledgments when they are specific; dig deeper only when they are perfunctory or contradicted by the document.",
            )
    builder = builders.get(step)
    if builder is None:
        raise CliError("unsupported_step", f"Unsupported {agent_label} step '{step}'")
    return builder


# Steps that accept a ``root`` keyword (project root). ``review`` doesn't —
# it threads extra prompt kwargs (e.g. pre_check_flags) instead.
_ROOT_BEARING_STEPS = {"prep", "prep-triage", "critique", "critique_evaluator", "gate", "finalize", "execute"}

# Maps the agent name used by callers to the (builder_dict, display_label)
# tuple used internally. Adding a new agent means appending one entry.
_AGENT_REGISTRY: dict[str, tuple[dict[str, "_PromptBuilder"], str]] = {
    "claude": (_CLAUDE_PROMPT_BUILDERS, "Claude"),
    "codex": (_CODEX_PROMPT_BUILDERS, "Codex"),
    "hermes": (_HERMES_PROMPT_BUILDERS, "Hermes"),
}


def create_prompt(
    agent: str,
    step: str,
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    **prompt_kwargs: object,
) -> str:
    """Render the prompt for ``(agent, step)``.

    ``agent`` is one of ``"claude"`` / ``"codex"`` / ``"hermes"``. All
    three resolve to the same shape:

    * ``step == "review"`` forwards ``prompt_kwargs`` to the builder.
    * Root-bearing steps forward ``root``.
    * Everything else calls the builder with just ``(state, plan_dir)``.

    The output always carries the harness-guard prefix.

    Thin per-agent wrappers — ``create_claude_prompt``, ``create_codex_prompt``,
    ``create_hermes_prompt`` — preserve the historical API used by 80+
    call sites across the codebase.
    """
    try:
        builders, label = _AGENT_REGISTRY[agent]
    except KeyError as exc:
        raise CliError(
            "unsupported_agent",
            f"create_prompt: unknown agent {agent!r}; "
            f"expected one of {sorted(_AGENT_REGISTRY)}",
        ) from exc
    builder = _resolve_builder(builders, step, state, label)
    contract_context = prompt_kwargs.pop("contract_context", None)
    if step == "review":
        ensure_review_evidence_for_prompt(state, plan_dir, root=root)
        prompt = builder(state, plan_dir, **_builder_kwargs(builder, prompt_kwargs))
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience="review"))
    if step == "plan":
        prompt = builder(state, plan_dir, contract_context=contract_context)
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience="plan"))
    if step == "prep":
        prompt = builder(state, plan_dir, root=root, contract_context=contract_context)
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience="prep"))
    if step == "prep-triage":
        prompt = builder(state, plan_dir, root=root, contract_context=contract_context)
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience="prep-triage"))
    if step == "prep-distill":
        allowed = {}
        for key in ("triage", "findings", "output_path", "dossier_path", "metrics_path"):
            if key in prompt_kwargs:
                allowed[key] = prompt_kwargs.pop(key)
        prompt = builder(state, plan_dir, root=root, contract_context=contract_context, **allowed)
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience="prep-distill"))
    if step in ("critique", "critique_evaluator"):
        critique_kwargs = _builder_kwargs(
            builder,
            {
                **prompt_kwargs,
                "contract_context": contract_context,
            },
        )
        prompt = builder(state, plan_dir, root=root, **critique_kwargs)
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience=step))
    if step == "gate":
        gate_kwargs = _builder_kwargs(
            builder,
            {
                **prompt_kwargs,
                "contract_context": contract_context,
            },
        )
        prompt = builder(state, plan_dir, root=root, **gate_kwargs)
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience="gate"))
    if step in _ROOT_BEARING_STEPS:
        prompt = builder(state, plan_dir, root=root, **_builder_kwargs(builder, prompt_kwargs))
        return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience=step))
    prompt = builder(state, plan_dir)
    return _prepend_harness_guard(_with_anchor_block(prompt, state, plan_dir, audience=step))


def create_prompt_components(
    agent: str,
    step: str,
    state: PlanState,
    plan_dir: Path,
    root: Path | None = None,
    *,
    system: str | None = None,
    messages: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
    schema: Mapping[str, Any] | None = None,
    template: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
    **prompt_kwargs: object,
) -> PromptComponents:
    prompt = create_prompt(agent, step, state, plan_dir, root=root, **prompt_kwargs)
    normalized_messages = tuple(dict(message) for message in (messages or ()))
    return PromptComponents(
        prompt=prompt,
        system=system,
        messages=normalized_messages,
        schema=dict(schema) if schema is not None else None,
        template=template,
        metadata=dict(metadata or {}),
    )


def create_claude_prompt(
    step: str, state: PlanState, plan_dir: Path, root: Path | None = None, **prompt_kwargs: object
) -> str:
    return create_prompt("claude", step, state, plan_dir, root=root, **prompt_kwargs)


def create_codex_prompt(
    step: str, state: PlanState, plan_dir: Path, root: Path | None = None, **prompt_kwargs: object
) -> str:
    return create_prompt("codex", step, state, plan_dir, root=root, **prompt_kwargs)


def create_hermes_prompt(
    step: str, state: PlanState, plan_dir: Path, root: Path | None = None, **prompt_kwargs: object
) -> str:
    return create_prompt("hermes", step, state, plan_dir, root=root, **prompt_kwargs)


def create_claude_prompt_components(
    step: str, state: PlanState, plan_dir: Path, root: Path | None = None, **prompt_kwargs: object
) -> PromptComponents:
    return create_prompt_components("claude", step, state, plan_dir, root=root, **prompt_kwargs)


def create_codex_prompt_components(
    step: str, state: PlanState, plan_dir: Path, root: Path | None = None, **prompt_kwargs: object
) -> PromptComponents:
    return create_prompt_components("codex", step, state, plan_dir, root=root, **prompt_kwargs)


def create_hermes_prompt_components(
    step: str, state: PlanState, plan_dir: Path, root: Path | None = None, **prompt_kwargs: object
) -> PromptComponents:
    return create_prompt_components("hermes", step, state, plan_dir, root=root, **prompt_kwargs)


__all__ = [
    "PLAN_TEMPLATE",
    "PromptComponents",
    "_CLAUDE_PROMPT_BUILDERS",
    "_CODEX_PROMPT_BUILDERS",
    "_HERMES_PROMPT_BUILDERS",
    "_collect_critique_summaries",
    "_critique_prompt",
    "_critique_creative_prompt",
    "_critique_joke_prompt",
    "_execute_approval_note",
    "_execute_batch_prompt",
    "_execute_creative_batch_prompt",
    "_execute_creative_prompt",
    "_execute_doc_batch_prompt",
    "_execute_doc_prompt",
    "_execute_joke_batch_prompt",
    "_execute_joke_prompt",
    "_execute_nudges",
    "_execute_prompt",
    "_execute_rerun_guidance",
    "_execute_review_block",
    "_finalize_prompt",
    "_flag_summary",
    "_gate_prompt",
    "_plan_prompt",
    "_prep_distill_prompt",
    "_prep_doc_prompt",
    "_prep_joke_prompt",
    "_prep_prompt",
    "_prep_research_prompt",
    "_prep_triage_prompt",
    "_render_contracts_block",
    "_review_doc_prompt",
    "_review_joke_prompt",
    "_write_critique_template",
    "_render_prep_block",
    "_resolve_prompt_root",
    "_review_prompt",
    "_revise_prompt",
    "_revise_creative_prompt",
    "_revise_joke_prompt",
    "_settled_decisions_block",
    "_settled_decisions_instruction",
    "_write_review_template",
    "_write_critique_evaluator_template",
    "_write_execute_batch_template",
    "_write_execute_template",
    "_write_finalize_template",
    "_write_gate_template",
    "create_claude_prompt",
    "create_claude_prompt_components",
    "create_codex_prompt",
    "create_codex_prompt_components",
    "create_hermes_prompt",
    "create_hermes_prompt_components",
    "create_prompt",
    "create_prompt_components",
]
