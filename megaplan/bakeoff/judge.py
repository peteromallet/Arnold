"""Optional judge support for bake-off comparison."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, TypedDict

from megaplan._core.io import collect_git_diff_patch
from megaplan.bakeoff.state import BakeoffState
from megaplan.profiles import load_profiles, resolve_profile
from megaplan.types import CliError, parse_agent_spec


JUDGE_CANDIDATES = ["claude", "codex", "gpt-5"]
JUDGED_PHASES = ("plan", "execute")


class JudgeVerdict(TypedDict):
    judge_model: str
    rank: list[str]
    rationale_per_profile: dict[str, str]
    scope_drift_flags: dict[str, list[str]]
    concerns: list[str]


def resolve_requested_judge(
    root: Path,
    bakeoff_state: BakeoffState,
    requested: str | None,
) -> str | None:
    """Resolve a CLI --judge value without dispatching an agent call."""
    if requested is None:
        return None
    if requested == "auto":
        return auto_select_judge_model(root, bakeoff_state)
    return requested


def auto_select_judge_model(root: Path, bakeoff_state: BakeoffState) -> str:
    used = used_executor_identities(root, bakeoff_state)
    for candidate in JUDGE_CANDIDATES:
        if not _candidate_is_used(candidate, used):
            return candidate
    raise CliError(
        "bakeoff_no_free_judge",
        "no auto-selectable judge; pass --judge <model> explicitly.",
    )


def used_executor_identities(root: Path, bakeoff_state: BakeoffState) -> set[str]:
    profiles = load_profiles(project_dir=root)
    used: set[str] = set()
    for record in bakeoff_state.get("profiles", []):
        phase_map = resolve_profile(record["name"], profiles)
        for phase in JUDGED_PHASES:
            spec = phase_map.get(phase)
            if not spec:
                continue
            parsed = parse_agent_spec(spec)
            used.add(parsed.agent.lower())
            if parsed.model:
                used.add(parsed.model.lower())
    return used


async def run_judge(
    bakeoff_state: BakeoffState,
    metrics_by_profile: dict[str, dict[str, Any]],
    judge_model: str,
) -> JudgeVerdict:
    prompt = build_judge_prompt(bakeoff_state, metrics_by_profile)
    response = await _run_agent_prompt(judge_model, prompt)
    return _parse_judge_response(response, judge_model, metrics_by_profile)


def build_judge_prompt(
    bakeoff_state: BakeoffState,
    metrics_by_profile: dict[str, dict[str, Any]],
) -> str:
    mode = bakeoff_state.get("mode") or "code"
    output_path = bakeoff_state.get("output_path")
    bundles = []
    for record in bakeoff_state.get("profiles", []):
        profile = record["name"]
        worktree = Path(record["worktree"])
        bundle: dict[str, Any] = {
            "profile": profile,
            "outcome": record.get("outcome"),
            "metrics": metrics_by_profile.get(profile, {}),
            "artifacts": _artifact_bundle(worktree, record["plan_id"]),
        }
        if mode == "doc":
            # In doc-mode bake-offs, the deliverable is the doc file itself.
            # Send its content (truncated) to the judge instead of a code patch.
            bundle["doc"] = _doc_summary(worktree, output_path)
        else:
            bundle["patch"] = _patch_summary(worktree)
        bundles.append(bundle)
    if mode == "doc":
        instruction = (
            "These bake-off profiles each produced a document at the given relative "
            "path inside their worktree. Compare the document content (and supporting "
            "plan artifacts) and rank the profiles by document quality, completeness, "
            "and how well they satisfy the idea. Flag scope drift and missed "
            "requirements. Return only JSON with keys: rank, rationale_per_profile, "
            "scope_drift_flags, concerns."
        )
    else:
        instruction = (
            "Given these bake-off profile bundles, rank the profiles and flag "
            "scope drift, quality concerns, or missed requirements. Return only "
            "JSON with keys: rank, rationale_per_profile, scope_drift_flags, concerns."
        )
    payload: dict[str, Any] = {
        "instruction": instruction,
        "experiment_id": bakeoff_state["experiment_id"],
        "base_sha": bakeoff_state["base_sha"],
        "idea_hash": bakeoff_state["idea_hash"],
        "mode": mode,
        "profiles": bundles,
    }
    if output_path:
        payload["output_path"] = output_path
    return json.dumps(payload, indent=2, sort_keys=True)


async def _run_agent_prompt(judge_model: str, prompt: str) -> str:
    agent_dir = Path(__file__).resolve().parents[1] / "agent"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(agent_dir / "run_agent.py"),
        "--query",
        prompt,
        "--model",
        judge_model,
        "--max_turns",
        "3",
        "--disabled_toolsets",
        "terminal",
        cwd=agent_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        detail = stderr.decode(errors="replace").strip() or stdout.decode(errors="replace").strip()
        raise CliError("bakeoff_judge_failed", f"Judge failed: {detail}")
    return stdout.decode(errors="replace")


def _parse_judge_response(
    response: str,
    judge_model: str,
    metrics_by_profile: dict[str, dict[str, Any]],
) -> JudgeVerdict:
    data = _extract_json_object(response)
    profile_names = list(metrics_by_profile)
    rank = data.get("rank") if isinstance(data.get("rank"), list) else profile_names
    rationale = data.get("rationale_per_profile")
    flags = data.get("scope_drift_flags")
    concerns = data.get("concerns")
    return {
        "judge_model": judge_model,
        "rank": [str(item) for item in rank],
        "rationale_per_profile": (
            {str(key): str(value) for key, value in rationale.items()}
            if isinstance(rationale, dict)
            else {name: "" for name in profile_names}
        ),
        "scope_drift_flags": (
            {
                str(key): [str(item) for item in value]
                for key, value in flags.items()
                if isinstance(value, list)
            }
            if isinstance(flags, dict)
            else {name: [] for name in profile_names}
        ),
        "concerns": [str(item) for item in concerns] if isinstance(concerns, list) else [],
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(stripped[start : end + 1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _artifact_bundle(worktree: Path, plan_id: str) -> dict[str, str | None]:
    plan_dir = worktree / ".megaplan" / "plans" / plan_id
    artifacts: dict[str, str | None] = {
        # cache-tolerant: judge bundle view.
        "state.json": _read_text(plan_dir / "state.json"),
        "plan_v1.md": _read_text(plan_dir / "plan_v1.md"),
        "execution.json": _read_text(plan_dir / "execution.json"),
        "review_output.json": _read_text(plan_dir / "review_output.json"),
        "review.json": _read_text(plan_dir / "review.json"),
    }
    critiques = sorted(plan_dir.glob("critique_v*.json")) if plan_dir.exists() else []
    for critique in critiques:
        artifacts[critique.name] = _read_text(critique)
    return artifacts


def _patch_summary(worktree: Path) -> str | None:
    if not worktree.exists():
        return None
    patch = collect_git_diff_patch(worktree)
    if len(patch) > 20000:
        return patch[:20000] + "\n...[truncated]"
    return patch


def _doc_summary(worktree: Path, output_path: str | None) -> dict[str, Any]:
    """Bundle the doc artifact for the judge in doc-mode bake-offs."""
    if not output_path:
        return {"output_path": None, "present": False, "content": None}
    if not worktree.exists():
        return {"output_path": output_path, "present": False, "content": None}
    doc_abs = worktree / output_path
    if not doc_abs.exists() or not doc_abs.is_file():
        return {"output_path": output_path, "present": False, "content": None}
    try:
        text = doc_abs.read_text(encoding="utf-8")
    except OSError:
        return {"output_path": output_path, "present": True, "content": None}
    if len(text) > 40000:
        text = text[:40000] + "\n...[truncated]"
    return {"output_path": output_path, "present": True, "content": text}


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _candidate_is_used(candidate: str, used: set[str]) -> bool:
    normalized = candidate.lower()
    return any(normalized == identity or normalized in identity for identity in used)
