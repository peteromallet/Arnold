"""Tests for the external feedback.md feature."""

from __future__ import annotations

from pathlib import Path

from megaplan.feedback import (
    FEEDBACK_FILENAME,
    PlanFeedback,
    STAGES,
    StageFeedback,
    feedback_path,
    format_summary,
    load_feedback,
    parse_feedback,
    render_template,
)


def test_template_contains_all_stages_plus_overall() -> None:
    text = render_template("demo-plan", idea="Add feedback feature")
    assert "# Feedback for plan: demo-plan" in text
    assert "> Add feedback feature" in text
    assert "## Overall" in text
    for stage in STAGES:
        assert f"## {stage}" in text
    # Template fields are blank by design.
    fb = parse_feedback(text)
    assert fb.is_empty()


def test_parse_filled_in_overall_and_stage() -> None:
    text = """# Feedback for plan: demo

## Overall

rating: 8/10
comment: solid plan, execute step was flaky

## plan

rating: 9
comment:

## execute

rating: 6
comment: needed two retries
to land cleanly
"""
    fb = parse_feedback(text)
    assert fb.overall.rating == 8
    assert fb.overall.comment == "solid plan, execute step was flaky"
    assert fb.stages["plan"].rating == 9
    assert fb.stages["plan"].comment is None
    assert fb.stages["execute"].rating == 6
    assert fb.stages["execute"].comment == "needed two retries\nto land cleanly"


def test_parse_rejects_out_of_range_ratings() -> None:
    text = """## Overall

rating: 42
comment:
"""
    fb = parse_feedback(text)
    # Out-of-range → ignored, comment empty → section dropped entirely.
    assert fb.overall.is_empty()


def test_parse_handles_blank_template() -> None:
    fb = parse_feedback(render_template("p"))
    assert fb.is_empty()
    assert fb.overall.rating is None
    assert fb.stages == {}


def test_load_feedback_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_feedback(tmp_path) is None


def test_load_feedback_round_trip(tmp_path: Path) -> None:
    (tmp_path / FEEDBACK_FILENAME).write_text(
        render_template("p").replace("## Overall\n\nrating:", "## Overall\n\nrating: 7"),
        encoding="utf-8",
    )
    fb = load_feedback(tmp_path)
    assert fb is not None
    assert fb.overall.rating == 7


def test_format_summary_handles_blank() -> None:
    out = format_summary(PlanFeedback())
    assert "Overall" in out
    assert "—" in out


def test_format_summary_includes_filled_stages() -> None:
    fb = PlanFeedback(
        overall=StageFeedback(rating=8, comment="good"),
        stages={"execute": StageFeedback(rating=6, comment="retries")},
    )
    out = format_summary(fb)
    assert "8/10" in out
    assert "execute" in out
    assert "retries" in out


def test_feedback_path() -> None:
    assert feedback_path(Path("/tmp/x")).name == FEEDBACK_FILENAME


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------


def _row(plan: str, profile: str | None, repo: str, *, overall: int | None, comment: str = "", stages: dict[str, int] | None = None) -> dict:
    return {
        "plan": plan,
        "profile": profile,
        "repo": repo,
        "backend": "file",
        "feedback": {
            "overall": {"rating": overall, "comment": comment},
            "stages": {name: {"rating": r, "comment": ""} for name, r in (stages or {}).items()},
        },
    }


def test_filter_by_profile_substring() -> None:
    from argparse import Namespace
    from megaplan.cli import _filter_feedback_rows

    rows = [
        _row("a", "all-claude", "/r1", overall=8),
        _row("b", "poirot", "/r2", overall=7),
        _row("c", None, "/r3", overall=9),
    ]
    out = _filter_feedback_rows(rows, Namespace(profile="claude", repo=None, min_rating=None, max_rating=None, stage=None, has_comment=False))
    assert {r["plan"] for r in out} == {"a"}


def test_filter_by_repo_substring() -> None:
    from argparse import Namespace
    from megaplan.cli import _filter_feedback_rows

    rows = [
        _row("a", "p", "/Users/me/reigh-workspace", overall=8),
        _row("b", "p", "/Users/me/megaplan", overall=7),
    ]
    out = _filter_feedback_rows(rows, Namespace(profile=None, repo="reigh", min_rating=None, max_rating=None, stage=None, has_comment=False))
    assert {r["plan"] for r in out} == {"a"}


def test_filter_by_rating_range_and_comment() -> None:
    from argparse import Namespace
    from megaplan.cli import _filter_feedback_rows

    rows = [
        _row("a", "p", "/r", overall=8, comment="solid"),
        _row("b", "p", "/r", overall=5, comment=""),
        _row("c", "p", "/r", overall=None, comment="no rating"),
    ]
    out = _filter_feedback_rows(rows, Namespace(profile=None, repo=None, min_rating=6, max_rating=10, stage=None, has_comment=True))
    assert {r["plan"] for r in out} == {"a"}


def test_filter_by_stage() -> None:
    from argparse import Namespace
    from megaplan.cli import _filter_feedback_rows

    rows = [
        _row("a", "p", "/r", overall=8, stages={"execute": 6}),
        _row("b", "p", "/r", overall=8, stages={"plan": 9}),
    ]
    out = _filter_feedback_rows(rows, Namespace(profile=None, repo=None, min_rating=None, max_rating=None, stage="execute", has_comment=False))
    assert {r["plan"] for r in out} == {"a"}


def test_render_feedback_table_empty_and_populated() -> None:
    from megaplan.cli import _render_feedback_table

    assert _render_feedback_table([]) == "(no matches)"
    out = _render_feedback_table([_row("demo", "poirot", "/repo/x", overall=8, comment="solid run")])
    assert "demo" in out
    assert "poirot" in out
    assert "8/10" in out
    assert "solid run" in out


def test_collect_feedback_rows_walks_plan_tree(tmp_path: Path, monkeypatch) -> None:
    """End-to-end: a plan dir with feedback.md should be discovered."""

    from megaplan._core.io import atomic_write_text
    from megaplan.cli import _collect_feedback_rows

    # Make a plausible megaplan project root with one plan dir under it
    project = tmp_path / "proj"
    plan_dir = project / ".megaplan" / "plans" / "my-plan"
    plan_dir.mkdir(parents=True)
    atomic_write_text(plan_dir / "state.json", '{"name":"my-plan","idea":"i","current_state":"done","iteration":1,"created_at":"2026-01-01T00:00:00Z","config":{"profile":"poirot","project_dir":"/work/proj"},"sessions":{},"plan_versions":[],"history":[],"meta":{},"last_gate":{}}')
    atomic_write_text(plan_dir / "feedback.md", "## Overall\n\nrating: 8\ncomment: nice\n")

    rows = _collect_feedback_rows(project, all_system=False, include_db=False)
    assert len(rows) == 1
    row = rows[0]
    assert row["plan"] == "my-plan"
    assert row["profile"] == "poirot"
    assert row["repo"] == "/work/proj"
    assert row["feedback"]["overall"]["rating"] == 8
