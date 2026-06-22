"""Director's notes sidecar assembly for creative work."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import atomic_write_json, creative_form_id, read_json
from arnold_pipelines.megaplan.forms import Provocation, ProvocateurVoice
from arnold_pipelines.megaplan.types import PlanState


def _voice_id(voice: str | ProvocateurVoice | None) -> str | None:
    if voice is None:
        return None
    if isinstance(voice, str):
        return voice
    return voice.id


def _provocation_entry(provocation: Any) -> dict[str, Any]:
    if isinstance(provocation, Provocation):
        return {
            "id": provocation.id,
            "vector": provocation.vector,
            "subtype": provocation.subtype,
        }
    if isinstance(provocation, dict):
        return {
            "id": str(provocation.get("id", "")),
            "vector": str(provocation.get("vector", "")),
            "subtype": str(provocation.get("subtype", "")),
        }
    return {"id": str(provocation), "vector": "", "subtype": ""}


def _stance_entry(task_update: dict[str, Any]) -> dict[str, Any] | None:
    stance = task_update.get("stance")
    if not isinstance(stance, dict):
        return None
    return {
        "task_id": str(task_update.get("task_id", "")),
        "challenge_engaged": str(stance.get("challenge_engaged", "")),
        "angle_taken": str(stance.get("angle_taken", "")),
        "what_changed": str(stance.get("what_changed", "")),
        "stance_violations": list(task_update.get("stance_violations", [])),
    }


def _load_notes(path: Path, state: PlanState) -> dict[str, Any]:
    if path.exists():
        try:
            data = read_json(path)
        except (OSError, ValueError):
            data = {}
        if isinstance(data, dict):
            data.setdefault("passes", [])
            return data
    return {
        "form": creative_form_id(state) or "joke",
        "primary_criterion": state.get("config", {}).get("primary_criterion", ""),
        "passes": [],
    }


def update_directors_notes_at_aggregate(
    plan_dir: Path,
    state: PlanState,
    aggregate_payload: dict[str, Any],
    *,
    iteration: int,
    voice: str | ProvocateurVoice | None,
    fired_provocations: list[Any] | tuple[Any, ...],
    preserve_existing_provocations: bool = False,
) -> None:
    notes_path = plan_dir / "directors_notes.json"
    notes = _load_notes(notes_path, state)
    notes["form"] = creative_form_id(state) or notes.get("form") or "joke"
    notes["primary_criterion"] = state.get("config", {}).get(
        "primary_criterion",
        notes.get("primary_criterion", ""),
    )

    stances: list[dict[str, Any]] = []
    stop_requested = False
    stop_defense = ""
    for task_update in aggregate_payload.get("task_updates", []):
        if not isinstance(task_update, dict):
            continue
        stance = _stance_entry(task_update)
        if stance is not None:
            stances.append(stance)
        stop_signal = task_update.get("stop_signal")
        if isinstance(stop_signal, dict) and stop_signal.get("requested") is True:
            stop_requested = True
            stop_defense = str(stop_signal.get("defense", "")).strip()

    pass_entry = {
        "iteration": iteration,
        "provocateur_voice": _voice_id(voice),
        "provocations_fired": [_provocation_entry(p) for p in fired_provocations],
        "stances": stances,
        "stop_requested": stop_requested,
        "stop_defense": stop_defense,
    }

    existing = [p for p in notes.get("passes", []) if isinstance(p, dict)]
    replaced = False
    for index, item in enumerate(existing):
        if item.get("iteration") == iteration:
            if preserve_existing_provocations and item.get("provocations_fired"):
                pass_entry["provocations_fired"] = item["provocations_fired"]
            if (
                preserve_existing_provocations
                and item.get("provocateur_voice")
                and pass_entry["provocateur_voice"] is None
            ):
                pass_entry["provocateur_voice"] = item["provocateur_voice"]
            existing[index] = pass_entry
            replaced = True
            break
    if not replaced:
        existing.append(pass_entry)
    notes["passes"] = sorted(existing, key=lambda item: int(item.get("iteration") or 0))
    atomic_write_json(notes_path, notes)


__all__ = ["update_directors_notes_at_aggregate"]
