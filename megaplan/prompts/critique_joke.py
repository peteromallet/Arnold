"""Joke-mode critique prompt builders."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from megaplan.audits.robustness import joke_checks_for_robustness
from megaplan.types import PlanState

from .critique import _build_critique_prompt, _critique_context, _write_critique_template


def _primary_criterion(state: PlanState) -> str:
    criterion = state.get("config", {}).get("primary_criterion", "")
    if isinstance(criterion, str) and criterion.strip():
        return criterion.strip()
    return "[missing primary criterion]"


def _lens_quality(check: dict[str, Any]) -> str:
    return str(check.get("id", "lens")).replace("_", " ")


def _joke_lens_instruction(check: dict[str, Any]) -> str:
    lens = str(check["id"])
    quality = _lens_quality(check)
    return textwrap.dedent(
        f"""
        Persona: {lens}
        Question: {check["question"]}
        Guidance: {check.get("guidance", "")}
        Your persona is `{lens}`. Propose exactly one concrete, named, committed beat change that would make this scene maximally {quality} while still serving the primary criterion.
        Do not hedge.
        Do not suggest multiple alternatives.
        Write the proposal as if you are committing to it: specific character, line, prop, turn, or button.
        Avoid meta-commentary.
        Output one `FLAG-{lens}` in the `flags` array for this lens and do not leave `findings` empty.
        """
    ).strip()


def _joke_findings_requirements() -> str:
    return textwrap.dedent(
        """
        For each active lens:
        - Add at least one finding to that check's `findings` array.
        - Keep the existing findings schema unchanged: each finding needs `detail` and `flagged`.
        - Use `detail` to describe the exact committed proposal and why it serves the primary criterion.
        - Set `flagged` to true for the committed proposal.

        For the `flags` array:
        - Emit one committed generative FLAG per active lens.
        - Use the exact ID format `FLAG-<lens>`.
        - Make the concern concrete and named: beat, line, prop, reveal, turn, or button.
        - Do not hedge. Do not say "consider". Do not offer multiple options.
        """
    ).strip()


def _critique_joke_prompt(state: PlanState, plan_dir: Path, root: Path | None = None) -> str:
    context = _critique_context(state, plan_dir, root)
    active_checks = joke_checks_for_robustness(context["robustness"])
    output_path = _write_critique_template(plan_dir, state, active_checks)
    primary_criterion = _primary_criterion(state)
    iteration = state.get("iteration", 1)

    if active_checks:
        iteration_context = ""
        if iteration > 1:
            iteration_context = (
                "\n\n            This is critique iteration {iteration}. "
                "The template file includes prior findings with their status. "
                "Keep each lens distinct, verify whether prior proposals still earn their place, "
                "and avoid collapsing multiple personas into the same move."
            ).format(iteration=iteration)
        lens_block = "\n\n".join(_joke_lens_instruction(check) for check in active_checks)
        critique_review_block = textwrap.dedent(
            f"""
            Your output template is at: {output_path}
            Read this file first — it contains {len(active_checks)} joke-lens checks, each with a question and guidance.
            This is the sequential fallback path: run every lens persona in one pass without inventing new infrastructure.

            The primary criterion for this scene is: {primary_criterion}

            {_joke_findings_requirements()}

            Active lens personas:
            {lens_block}

            Workflow: read the file → investigate the plan and repository context → read the file again → write one committed proposal per lens into both `findings` and `flags` → write the file back.{iteration_context}
        """
        ).strip()
    else:
        critique_review_block = textwrap.dedent(
            f"""
            Your output template is at: {output_path}
            No joke-lens checks are active at this robustness level.
            The primary criterion for this scene is: {primary_criterion}

            Review the plan broadly through a generative lens. If you identify a concrete beat, line, prop, turn, button, or reveal that would better serve the primary criterion, record it in the `flags` array using a committed proposal rather than a hedge.

            Workflow: read the file → investigate → read the file again → add any concrete generative flags → write the file back.
        """
        ).strip()
    return _build_critique_prompt(state, context, critique_review_block)


def single_check_critique_joke_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    check: dict[str, Any],
    template_path: Path,
) -> str:
    context = _critique_context(state, plan_dir, root)
    primary_criterion = _primary_criterion(state)
    iteration = state.get("iteration", 1)
    iteration_context = ""
    if iteration > 1:
        iteration_context = (
            "\n\n        This is critique iteration {iteration}. "
            "The template file includes prior findings with their status. "
            "Verify whether this persona's prior proposal still earns its place or whether a sharper committed move is warranted."
        ).format(iteration=iteration)
    critique_review_block = textwrap.dedent(
        f"""
        Your output template is at: {template_path}
        Read this file first — it contains 1 joke-lens check with a question and guidance.
        Investigate only this check, then add your finding to that check's `findings` array and one committed FLAG to the `flags` array.

        The primary criterion for this scene is: {primary_criterion}

        {_joke_lens_instruction(check)}

        Findings requirements:
        - Keep the existing findings schema unchanged: each finding needs `detail` and `flagged`.
        - Add at least one finding to this check's `findings` array.
        - Use `detail` to describe the exact committed proposal and why it serves the primary criterion.
        - Set `flagged` to true for the committed proposal.

        Flag requirements:
        - Emit exactly one `FLAG-{check["id"]}` entry in the `flags` array for this lens.
        - Make the proposal concrete and named: specific character, line, prop, reveal, turn, or button.
        - Do not hedge.
        - Do not suggest multiple alternatives.
        - Avoid meta-commentary.

        Workflow: read the file → investigate → read the file again → add one committed proposal to `findings` and one committed `FLAG-{check["id"]}` to `flags` → write the file back.{iteration_context}
    """
    ).strip()
    return _build_critique_prompt(state, context, critique_review_block)


__all__ = ["_critique_joke_prompt", "single_check_critique_joke_prompt"]
