"""Correctness metric for the intent-oracle gate.

Usage (Python):
    from vibecomfy.intent.metric import edit_correctness
    report = edit_correctness(fixtures, family="image", runtime="structural")

Usage (CLI):
    python vibecomfy/intent/report.py --family image --runtime structural
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal


@dataclass
class FixtureResult:
    id: str
    panel_verdict: Any  # PanelVerdict | None


@dataclass
class FamilyReport:
    family: str
    total: int
    passed: int
    fraction: float
    per_fixture: list[dict]


def edit_correctness(
    fixtures: list[Any],
    *,
    family: str,
    runtime: Literal["structural", "embedded"],
    judge_text_fn: Callable | None = None,
    judge_vision_fn: Callable | None = None,
) -> "FamilyReport":
    """Evaluate a list of :class:`~vibecomfy.intent._fixture.Fixture` objects.

    Parameters
    ----------
    fixtures:
        List of :class:`Fixture` instances — must all belong to *family*.
    family:
        One of ``"image"``, ``"edit"``, or ``"video"``.
    runtime:
        ``"structural"`` uses only the text judge (no rendered images);
        ``"embedded"`` runs the full text+vision panel.
    judge_text_fn:
        Optional dependency-injected replacement for
        :func:`~vibecomfy.intent.judge.judge_text`.  Receives
        ``(pre_ir, post_ir, nl_intent)`` and must return a
        :class:`~vibecomfy.intent.judge.JudgeVerdict`.
    judge_vision_fn:
        Optional dependency-injected replacement for
        :func:`~vibecomfy.intent.judge.judge_vision`.  Only consulted
        when *runtime* is ``"embedded"``.

    Returns
    -------
    FamilyReport
    """
    from vibecomfy.intent.judge import JudgeVerdict, PanelVerdict, judge_text, judge_vision, panel_verdict

    if judge_text_fn is None:
        judge_text_fn = judge_text
    if judge_vision_fn is None:
        judge_vision_fn = judge_vision

    per_fixture = []
    passed = 0

    for fx in fixtures:
        if fx.family != family:
            raise ValueError(
                f"edit_correctness: fixture {fx.id!r} has family {fx.family!r}, "
                f"expected {family!r}; never blend across families"
            )

        text_v: JudgeVerdict = judge_text_fn(fx.pre_ui, fx.post_ui, fx.nl_intent)

        if runtime == "embedded":
            vision_v: JudgeVerdict = judge_vision_fn([], [], fx.nl_intent)
            pv: PanelVerdict = panel_verdict(text_v, vision_v)
        else:
            # Structural runtime: vision judge not available; synthesise a
            # passing vision verdict so the panel reduces to the text verdict.
            passing_vision = JudgeVerdict(
                pass_=True,
                criteria={
                    "correct_node_targeted": True,
                    "correct_parameter_changed": True,
                    "value_semantically_matches_intent": True,
                    "no_orphaned_wiring": True,
                },
                rationale="structural runtime — vision judge skipped",
            )
            pv = panel_verdict(text_v, passing_vision)

        if pv.pass_:
            passed += 1

        per_fixture.append({"id": fx.id, "panel_verdict": pv})

    total = len(fixtures)
    fraction = passed / total if total > 0 else 0.0

    return FamilyReport(
        family=family,
        total=total,
        passed=passed,
        fraction=fraction,
        per_fixture=per_fixture,
    )
