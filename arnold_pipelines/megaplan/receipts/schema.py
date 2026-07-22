"""Receipt schema declarations and artifact provenance helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from arnold_pipelines.megaplan._core import sha256_file


class Receipt(TypedDict):
    receipt_id: str
    plan_id: str
    phase: str
    iteration: int
    attempt: int
    timestamp_utc: str
    profile_name: str | None
    agent: str
    agent_mode: Literal["oneshot", "persistent"]
    model_configured: str | None
    model_actual: str | None
    configured_specs: list[str]
    attempted_specs: list[str]
    selected_spec_index: int
    selected_spec_total: int
    fallback_trigger: str | None
    failed_attempt_reasons: list[str]
    session_id: str | None
    megaplan_version: str
    schema_version: int
    prompt_hash_raw: str | None
    prompt_hash_canonical: str | None
    canonicalization_version: int
    upstream_artifact_hashes: list[str]
    cost_usd: float
    cost_pricing: str | None
    duration_ms: int
    prompt_tokens: int
    completion_tokens: int
    verdict: str | None
    metrics: dict[str, Any]
    scope_drift_severity: str | None


DispatchOutcome = Literal[
    "initialized",
    "running",
    "blocked",
    "succeeded",
    "failed",
    "indeterminate",
]


class DispatchMutationFacts(TypedDict, total=False):
    """Facts about mutation observed during one automatic dispatch.

    The common mutation classes are declared for type checkers while the
    mapping remains extensible for action-specific facts.  Values are facts,
    not permissions or intentions.
    """

    state: bool | None
    source: bool | None
    commit: bool | None
    push: bool | None


class AutomaticDispatchReceipt(TypedDict):
    """Authoritative lifecycle record for a subprocess-backed action.

    ``subprocess_started`` records observation, not expected behaviour.
    ``resolved_runtime_model`` is runtime evidence and must not be populated
    from configuration intent.
    """

    schema_version: Literal[1]
    dispatch_id: str
    action: str
    configured_model: str | None
    resolved_runtime_model: str | None
    subprocess_started: bool
    outcome: DispatchOutcome
    mutation_facts: DispatchMutationFacts
    created_at_utc: str
    updated_at_utc: str
    sequence: int
    failure_stage: NotRequired[str | None]
    detail: NotRequired[str | None]


def _hash_if_present(path: Path) -> list[str]:
    try:
        return [sha256_file(path)]
    except Exception:
        return []


def registered_plan_artifact_path(plan_dir: Path, iteration: int) -> Path:
    """Resolve the latest registered plan artifact for ``iteration``.

    Recovery can register a byte-distinct same-iteration plan under an
    alternate filename.  Receipts must follow the durable plan-version record
    rather than silently falling back to the primary ``plan_vN.md`` alias.
    """
    fallback = plan_dir / f"plan_v{iteration}.md"
    try:
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        records = state.get("plan_versions") if isinstance(state, dict) else None
        if not isinstance(records, list):
            return fallback
        for record in reversed(records):
            if not isinstance(record, dict) or record.get("version") != iteration:
                continue
            filename = record.get("file")
            if not isinstance(filename, str) or not filename.endswith(".md"):
                return fallback
            candidate = plan_dir / filename
            if candidate.resolve().parent != plan_dir.resolve():
                return fallback
            return candidate
    except (OSError, ValueError, TypeError):
        pass
    return fallback


def upstream_artifact_hashes(plan_dir: Path, phase: str, iteration: int) -> list[str]:
    """Return ordered hashes of the artifacts that fed a phase receipt."""
    if phase == "plan":
        return []
    if phase == "critique":
        return _hash_if_present(registered_plan_artifact_path(plan_dir, iteration))
    if phase == "gate":
        hashes: list[str] = []
        for index in range(1, iteration + 1):
            hashes.extend(_hash_if_present(plan_dir / f"critique_v{index}.json"))
        return hashes
    if phase == "finalize":
        return _hash_if_present(plan_dir / f"gate_v{iteration}.json")
    if phase == "execute":
        return _hash_if_present(plan_dir / "finalize.json")
    if phase == "review":
        return _hash_if_present(plan_dir / "execution.json")
    return []
