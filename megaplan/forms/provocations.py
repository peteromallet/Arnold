"""Creative provocation selection and critique-check dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from megaplan._core import creative_form_id, is_creative_mode, latest_plan_path
from arnold.pipelines.megaplan.audits.robustness import checks_for_robustness
from megaplan.forms import Form, Provocation, ProvocateurVoice, get_form
from megaplan.profiles import normalize_robustness
from megaplan.types import PlanState


def select_provocateur_voice(
    form: Form,
    iteration: int,
    *,
    robustness: str = "full",
) -> ProvocateurVoice | None:
    robustness = normalize_robustness(robustness)
    if robustness not in {"thorough", "extreme"} or not form.provocateur_voices:
        return None
    index = max(iteration - 1, 0) % len(form.provocateur_voices)
    return form.provocateur_voices[index]


def _score_provocation(
    provocation: Provocation,
    *,
    draft_state_tags: set[str],
    voice: ProvocateurVoice | None,
) -> tuple[int, str]:
    score = 0
    if voice is not None and provocation.vector in voice.vector_bias:
        score += 10 - voice.vector_bias.index(provocation.vector)
    text = f"{provocation.id} {provocation.subtype} {provocation.prompt_text}".lower()
    if "over_explained" in draft_state_tags and any(token in text for token in ("explain", "unsaid")):
        score += 6
    if "safe" in draft_state_tags and any(token in text for token in ("risk", "dare", "hate", "embarrassing")):
        score += 6
    if "bloated" in draft_state_tags and any(token in text for token in ("halve", "compress")):
        score += 6
    if "replaceable" in draft_state_tags and any(token in text for token in ("borrow", "who could", "master")):
        score += 6
    return (-score, provocation.id)


def _pick_one(
    provocations: Iterable[Provocation],
    *,
    draft_state_tags: set[str],
    prior_provocation_ids: set[str],
    voice: ProvocateurVoice | None,
) -> Provocation | None:
    pool = tuple(provocations)
    candidates = [p for p in pool if p.id not in prior_provocation_ids]
    if not candidates:
        candidates = list(pool)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda p: _score_provocation(p, draft_state_tags=draft_state_tags, voice=voice),
    )[0]


def select_provocations(
    form: Form,
    *,
    robustness: str,
    iteration: int,
    draft_state_tags: Iterable[str],
    prior_provocation_ids: Iterable[str] = (),
) -> tuple[Provocation, ...]:
    robustness = normalize_robustness(robustness)
    if robustness == "bare":
        return ()
    tags = {tag for tag in draft_state_tags if isinstance(tag, str)}
    prior_ids = {pid for pid in prior_provocation_ids if isinstance(pid, str)}
    voice = select_provocateur_voice(form, iteration, robustness=robustness)
    vectors = ("cut", "spark") if robustness == "light" else ("cut", "force", "spark")
    selected: list[Provocation] = []
    for vector in vectors:
        provocation = _pick_one(
            getattr(form.provocations, f"{vector}s"),
            draft_state_tags=tags,
            prior_provocation_ids=prior_ids | {p.id for p in selected},
            voice=voice,
        )
        if provocation is not None:
            selected.append(provocation)
    return tuple(selected)


def _draft_state_tags(state: PlanState, plan_dir: Path | None) -> tuple[str, ...]:
    if plan_dir is None:
        return ()
    try:
        text = latest_plan_path(plan_dir, state).read_text(encoding="utf-8").lower()
    except Exception:
        return ()
    tags: set[str] = set()
    words = text.split()
    if len(words) > 1200 or text.count("because") + text.count("therefore") >= 8:
        tags.add("over_explained")
    if len(words) > 1800 or text.count("### step") >= 12:
        tags.add("bloated")
    if any(marker in text for marker in ("safe", "low-risk", "straightforward", "simple")):
        tags.add("safe")
    if any(marker in text for marker in ("generic", "replaceable", "template", "could be anyone")):
        tags.add("replaceable")
    return tuple(sorted(tags))


def _prior_provocation_ids(plan_dir: Path | None) -> tuple[str, ...]:
    if plan_dir is None:
        return ()
    notes_path = plan_dir / "directors_notes.json"
    if not notes_path.exists():
        return ()
    try:
        data = json.loads(notes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    prior_ids: list[str] = []
    for pass_entry in data.get("passes", []):
        if not isinstance(pass_entry, dict):
            continue
        for provocation in pass_entry.get("provocations_fired", []):
            if isinstance(provocation, dict) and isinstance(provocation.get("id"), str):
                prior_ids.append(provocation["id"])
    return tuple(prior_ids)


def _provocation_check(provocation: Provocation, voice: ProvocateurVoice | None) -> dict[str, Any]:
    voice_text = f"{voice.persona_text} " if voice is not None else ""
    targets = ", ".join(provocation.targets) if provocation.targets else "the work"
    return {
        "id": provocation.id,
        "question": f"What concrete {provocation.vector} move should hit {targets}?",
        "guidance": (
            f"{voice_text}Provocation `{provocation.id}` ({provocation.vector}/{provocation.subtype}): "
            f"{provocation.prompt_text} Commit to one concrete proposal. Do not hedge or offer alternatives."
        ),
        "category": "generative",
        "default_severity": "likely-minor",
        "tier": "core",
        "provocation": {
            "id": provocation.id,
            "vector": provocation.vector,
            "subtype": provocation.subtype,
            "prompt_text": provocation.prompt_text,
            "targets": list(provocation.targets),
        },
        "provocateur_voice": voice.id if voice is not None else None,
    }


def select_active_checks(
    state: PlanState,
    robustness: str,
    *,
    plan_dir: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    if not is_creative_mode(state):
        return tuple(checks_for_robustness(robustness))
    form = get_form(creative_form_id(state) or "joke")
    iteration = int(state.get("iteration") or 1)
    voice = select_provocateur_voice(form, iteration, robustness=robustness)
    provocations = select_provocations(
        form,
        robustness=robustness,
        iteration=iteration,
        draft_state_tags=_draft_state_tags(state, plan_dir),
        prior_provocation_ids=_prior_provocation_ids(plan_dir),
    )
    return tuple(_provocation_check(provocation, voice) for provocation in provocations)
