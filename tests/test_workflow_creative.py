from __future__ import annotations

import megaplan
from megaplan._core import workflow_next


def _state(mode: str, robustness: str, current_state: str, *, form: str | None = None) -> dict:
    config = {"mode": mode, "robustness": robustness}
    if form is not None:
        config["form"] = form
    return {"current_state": current_state, "last_gate": {}, "config": config}


def test_creative_standard_keeps_prep() -> None:
    assert workflow_next(_state("creative", "standard", megaplan.STATE_INITIALIZED, form="poem"))[0] == "prep"
    assert workflow_next(_state("code", "standard", megaplan.STATE_INITIALIZED))[0] == "plan"


def test_creative_light_keeps_prep() -> None:
    assert workflow_next(_state("creative", "light", megaplan.STATE_INITIALIZED, form="poem"))[0] == "prep"
    assert workflow_next(_state("code", "light", megaplan.STATE_INITIALIZED))[0] == "plan"


def test_creative_light_planned_surfaces_finalize() -> None:
    assert workflow_next(_state("creative", "light", megaplan.STATE_PLANNED, form="poem"))[0] == "finalize"
    assert workflow_next(_state("code", "light", megaplan.STATE_PLANNED))[0] == "critique"
