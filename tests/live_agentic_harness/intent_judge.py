"""LLM intent judge for live agentic harness artifacts.

Provides a DeepSeek-backed text judge that scores a candidate workflow edit
against the scenario's natural-language intent.  The judge is intentionally
separate from the deterministic assessor so it can be enabled/disabled without
changing the core pass/fail logic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent.provider import run_model_turn

_PROMPT_PATH = Path(__file__).parents[2] / "vibecomfy" / "intent" / "prompts" / "text_judge.prompt.md"


def _load_prompt() -> str:
    if _PROMPT_PATH.is_file():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    # Fallback rubric if the canonical prompt is missing.
    return (
        "You are a precise evaluator for ComfyUI workflow edits. Given a natural-language\n"
        "intent and a structural diff between a pre-edit and post-edit workflow IR, you\n"
        "must determine whether the edit correctly implements the intent.\n\n"
        "Evaluate the edit against exactly four binary criteria:\n"
        "- correct_node_targeted\n"
        "- correct_parameter_changed\n"
        "- value_semantically_matches_intent\n"
        "- no_orphaned_wiring\n\n"
        "Respond with a JSON object and nothing else:\n"
        '{"pass_": true | false, "criteria": {"correct_node_targeted": true | false, '
        '"correct_parameter_changed": true | false, "value_semantically_matches_intent": true | false, '
        '"no_orphaned_wiring": true | false}, "rationale": "<one or two sentences>"}\n'
        "`pass_` must be true if and only if all four criteria are true."
    )


def _parse_verdict(raw: str) -> dict[str, Any]:
    """Parse the judge's JSON response into a normalized dict."""
    text = raw.strip()
    # Some models wrap JSON in markdown fences; strip them.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    parsed = json.loads(text)
    criteria = parsed.get("criteria") or {}
    normalized_criteria = {
        "correct_node_targeted": bool(criteria.get("correct_node_targeted")),
        "correct_parameter_changed": bool(criteria.get("correct_parameter_changed")),
        "value_semantically_matches_intent": bool(criteria.get("value_semantically_matches_intent")),
        "no_orphaned_wiring": bool(criteria.get("no_orphaned_wiring")),
    }
    return {
        "pass_": bool(parsed.get("pass_")),
        "criteria": normalized_criteria,
        "rationale": str(parsed.get("rationale", "")),
    }


def judge_edit_intent(
    output_dir: Path | str,
    scenario: Mapping[str, Any],
    *,
    route: str = "deepseek",
    model: str = "deepseek-v4-pro",
) -> dict[str, Any]:
    """Run the DeepSeek text judge on the candidate edit in *output_dir*.

    Returns a dict with ``pass_``, ``criteria``, ``rationale``, and ``metadata``.
    If required artifacts are missing or the model call fails, ``pass_`` is None
    and ``error`` describes why.
    """
    output_dir = Path(output_dir)
    query = str(scenario.get("query", "")).strip()
    if not query:
        return {"pass_": None, "error": "scenario has no query"}

    # The durable turn writes UI artifacts under out/editor_sessions; the response
    # JSON carries the exact paths in its artifacts block.
    response_path = output_dir / "response.json"
    original_ui_path: Path | None = None
    candidate_ui_path: Path | None = None
    if response_path.is_file():
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
            artifacts = response.get("artifacts", {}) or {}
            if isinstance(artifacts.get("original_ui"), str):
                original_ui_path = Path(artifacts["original_ui"])
            if isinstance(artifacts.get("candidate_ui"), str):
                candidate_ui_path = Path(artifacts["candidate_ui"])
        except (OSError, json.JSONDecodeError):
            pass

    # Fallback to common in-directory locations if response artifacts are absent.
    if original_ui_path is None:
        original_ui_path = output_dir / "original.ui.json"
    if candidate_ui_path is None:
        candidate_ui_path = output_dir / "candidate.ui.json"

    if not original_ui_path.is_file() or not candidate_ui_path.is_file():
        return {
            "pass_": None,
            "error": f"missing UI artifacts: {original_ui_path} / {candidate_ui_path}",
        }

    try:
        pre_ir = json.loads(original_ui_path.read_text(encoding="utf-8"))
        post_ir = json.loads(candidate_ui_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"pass_": None, "error": f"failed to load UI artifacts: {exc}"}

    system_prompt = _load_prompt()
    # Optional non-prescriptive "desired outcome" rubric from the scenario. When
    # present, it grounds the judge on what a GOOD result achieves (the outcome +
    # what "smart/complete" means) WITHOUT prescribing exact nodes/params — sound
    # alternative approaches that reach the same outcome count as correct.
    desired = scenario.get("desired")
    if desired:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n## Scenario-specific desired outcome (non-prescriptive)\n"
            "The scenario author described what a GOOD result looks like below. Use it to "
            "judge whether the edit achieves the desired OUTCOME in a smart, complete way. "
            "This is NOT a recipe of exact nodes/params to use — any sound approach that "
            "achieves the outcome counts as correct. Weigh: did it achieve the outcome, is "
            "it fully wired/complete (no dangling or broken connections, existing pipeline "
            "not broken), and is the approach a sensible one?\n\n"
            f"Desired outcome: {desired.get('outcome', '')}\n"
            f"What 'smart/complete' means here: {desired.get('quality', '')}\n"
            f"Alternative approaches acceptable: {desired.get('alternatives_ok', True)}"
        )
    payload = {"nl_intent": query, "pre_ir": pre_ir, "post_ir": post_ir}
    if desired:
        payload["desired_outcome"] = desired
    user_content = json.dumps(payload, indent=2)

    try:
        response = run_model_turn(
            "evaluate workflow edit against intent",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            route=route,
            model=model,
            response_contract="json",
        )
    except Exception as exc:  # noqa: BLE001
        return {"pass_": None, "error": f"model call failed: {exc}"}

    raw = response.get("content") or ""
    if not raw:
        return {"pass_": None, "error": "model returned empty content"}

    try:
        verdict = _parse_verdict(raw)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {
            "pass_": None,
            "error": f"could not parse judge response: {exc}",
            "raw": raw[:500],
        }

    verdict["metadata"] = {
        "route": route,
        "model": model,
        "elapsed_ms": response.get("_profiling", {}).get("elapsed_ms"),
    }
    return verdict
