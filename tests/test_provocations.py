from __future__ import annotations

from megaplan.forms import get_form
from megaplan.forms.provocations import select_provocateur_voice, select_provocations


def test_provocation_firing_patterns_and_voice_rotation() -> None:
    form = get_form("joke")

    assert len(select_provocations(form, robustness="light", iteration=1, draft_state_tags=())) == 2
    assert len(select_provocations(form, robustness="standard", iteration=1, draft_state_tags=())) == 3
    assert len(select_provocations(form, robustness="robust", iteration=1, draft_state_tags=())) == 3
    assert select_provocateur_voice(form, 1, robustness="robust").id == "formalist"
    assert select_provocateur_voice(form, 2, robustness="robust").id == "iconoclast"
    assert select_provocateur_voice(form, 3, robustness="robust").id == "audience"


def test_standard_iteration_two_filters_prior_ids() -> None:
    form = get_form("joke")
    first = select_provocations(form, robustness="standard", iteration=1, draft_state_tags=())
    second = select_provocations(
        form,
        robustness="standard",
        iteration=2,
        draft_state_tags=(),
        prior_provocation_ids=[p.id for p in first],
    )

    assert {p.id for p in first}.isdisjoint({p.id for p in second})


def test_draft_state_tags_bias_over_explained_cuts() -> None:
    form = get_form("joke")
    selected = select_provocations(
        form,
        robustness="standard",
        iteration=1,
        draft_state_tags=("over_explained",),
    )

    assert selected[0].id == "joke-cut-explanation"
