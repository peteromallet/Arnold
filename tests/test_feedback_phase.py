"""Comprehensive tests for the AI-rated feedback phase.

Covers:
    (a) Schema — StageFeedback serialization, effective_rating, is_empty
    (b) Template — render_template with prefilled populates ai_* lines
    (c) Parser — round-trips ai_* fields, regression test for regex non-overlap
    (d) Prompt builder — build_feedback_prompt mentions every stage, marks absent
    (e) Routing — profile loading, apply_vendor_rewrite leaves feedback at claude:low
    (f) Handler happy path — mock worker returns valid JSON → populated feedback.md
    (g) Handler malformed output — invalid JSON → empty template, state DONE, no exception
    (h) Handler --force merge — preserves user fields, overwrites ai_*
    (i) Idempotency — second run without --force is a no-op
    (j) Display — _render_feedback_table shows AI ratings, format_summary shows (AI) suffix
    (k) Filter — _filter_feedback_rows matches ai_rating with --min-rating
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from argparse import Namespace
from pathlib import Path
from unittest import mock

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan._core import (
    STATE_DONE,
    STATE_REVIEWED,
    load_plan,
    save_state,
)
from arnold.pipelines.megaplan.orchestration.feedback import (
    FEEDBACK_FILENAME,
    STAGES,
    PlanFeedback,
    StageFeedback,
    effective_comment,
    effective_rating,
    feedback_path,
    format_summary,
    load_feedback,
    parse_feedback,
    render_template,
)
from arnold.pipelines.megaplan.prompts.feedback import build_feedback_prompt
from arnold.pipelines.megaplan.workers import WorkerResult


# ============================================================================
# (a) Schema — StageFeedback, effective_rating, is_empty
# ============================================================================


class TestStageFeedbackSchema:
    """StageFeedback dataclass with ai_* provenance fields."""

    def test_to_dict_with_only_ai_rating(self) -> None:
        """StageFeedback with only ai_rating serializes correctly via to_dict."""
        sf = StageFeedback(ai_rating=8)
        plan_fb = PlanFeedback(overall=sf)
        d = plan_fb.to_dict()
        assert d["overall"]["rating"] is None
        assert d["overall"]["comment"] is None
        assert d["overall"]["ai_rating"] == 8
        assert d["overall"]["ai_comment"] is None

    def test_to_dict_with_all_fields(self) -> None:
        """StageFeedback with all fields serializes correctly."""
        sf = StageFeedback(rating=7, comment="good", ai_rating=8, ai_comment="solid")
        plan_fb = PlanFeedback(overall=sf)
        d = plan_fb.to_dict()
        assert d["overall"]["rating"] == 7
        assert d["overall"]["comment"] == "good"
        assert d["overall"]["ai_rating"] == 8
        assert d["overall"]["ai_comment"] == "solid"

    def test_to_dict_stages(self) -> None:
        """Stage feedback dicts in PlanFeedback.to_dict include ai_* keys."""
        plan_fb = PlanFeedback(
            stages={
                "plan": StageFeedback(ai_rating=9, ai_comment="excellent plan"),
                "execute": StageFeedback(rating=5, ai_rating=6),
            }
        )
        d = plan_fb.to_dict()
        assert d["stages"]["plan"]["rating"] is None
        assert d["stages"]["plan"]["ai_rating"] == 9
        assert d["stages"]["plan"]["ai_comment"] == "excellent plan"
        assert d["stages"]["execute"]["rating"] == 5
        assert d["stages"]["execute"]["ai_rating"] == 6

    def test_effective_rating_user_wins(self) -> None:
        """effective_rating returns user rating when set."""
        sf = StageFeedback(rating=7, ai_rating=8)
        assert effective_rating(sf) == 7

    def test_effective_rating_falls_back_to_ai(self) -> None:
        """effective_rating returns ai_rating when user rating is None."""
        sf = StageFeedback(rating=None, ai_rating=8)
        assert effective_rating(sf) == 8

    def test_effective_rating_none_fallback(self) -> None:
        """effective_rating returns None when both are None."""
        sf = StageFeedback(rating=None, ai_rating=None)
        assert effective_rating(sf) is None

    def test_effective_comment_user_wins(self) -> None:
        """effective_comment returns user comment when set."""
        sf = StageFeedback(comment="user says good", ai_comment="ai says great")
        assert effective_comment(sf) == "user says good"

    def test_effective_comment_falls_back_to_ai(self) -> None:
        """effective_comment returns ai_comment when user comment is None."""
        sf = StageFeedback(comment=None, ai_comment="ai says great")
        assert effective_comment(sf) == "ai says great"

    def test_effective_comment_empty_user_not_used(self) -> None:
        """effective_comment returns ai_comment when user comment is whitespace."""
        sf = StageFeedback(comment="   ", ai_comment="ai says great")
        assert effective_comment(sf) == "ai says great"

    def test_effective_comment_none_fallback(self) -> None:
        """effective_comment returns None when both are None."""
        sf = StageFeedback(comment=None, ai_comment=None)
        assert effective_comment(sf) is None

    def test_is_empty_all_fields_unset(self) -> None:
        """is_empty returns True when all four fields are unset."""
        sf = StageFeedback()
        assert sf.is_empty() is True

    def test_is_empty_user_rating_set(self) -> None:
        """is_empty returns False when user rating is set."""
        sf = StageFeedback(rating=7)
        assert sf.is_empty() is False

    def test_is_empty_user_comment_set(self) -> None:
        """is_empty returns False when user comment is set."""
        sf = StageFeedback(comment="hello")
        assert sf.is_empty() is False

    def test_is_empty_ai_rating_set(self) -> None:
        """is_empty returns False when ai_rating is set."""
        sf = StageFeedback(ai_rating=8)
        assert sf.is_empty() is False

    def test_is_empty_ai_comment_set(self) -> None:
        """is_empty returns False when ai_comment is set."""
        sf = StageFeedback(ai_comment="good")
        assert sf.is_empty() is False

    def test_is_empty_empty_string_comment_treated_as_empty(self) -> None:
        """is_empty treats empty string comment as empty."""
        sf = StageFeedback(comment="", ai_comment="")
        assert sf.is_empty() is True

    def test_plan_feedback_is_empty(self) -> None:
        """PlanFeedback.is_empty returns True when everything is empty."""
        fb = PlanFeedback()
        assert fb.is_empty() is True

    def test_plan_feedback_is_not_empty_with_ai_rating(self) -> None:
        """PlanFeedback.is_empty returns False when overall has ai_rating."""
        fb = PlanFeedback(overall=StageFeedback(ai_rating=8))
        assert fb.is_empty() is False


# ============================================================================
# (b) Template — render_template with prefilled
# ============================================================================


class TestRenderTemplate:
    """render_template with prefilled=PlanFeedback(...)."""

    def test_prefilled_populates_ai_rating_lines(self) -> None:
        """Prefilled template has ai_rating: 8 and blank rating:."""
        fb = PlanFeedback(overall=StageFeedback(ai_rating=8, ai_comment="solid run"))
        out = render_template("test-plan", idea="do something", prefilled=fb)
        # ai_rating should be populated
        assert "ai_rating: 8" in out
        assert "ai_comment: solid run" in out
        # User rating/comment lines are blank (no values set in StageFeedback)
        assert "\nrating: \n" in out
        assert "\ncomment: \n" in out

    def test_prefilled_blank_ai_fields(self) -> None:
        """When ai_* are None, the template shows blank ai_rating: and ai_comment:."""
        fb = PlanFeedback(overall=StageFeedback())
        out = render_template("test-plan", prefilled=fb)
        assert "ai_rating:" in out
        assert "ai_comment:" in out
        # Should be "ai_rating: " (with trailing space from str(None)="" format)
        assert "ai_rating: \n" in out

    def test_prefilled_covers_all_stages(self) -> None:
        """Template includes ai_* and blank rating:/comment: for all STAGES including tiebreaker."""
        fb = PlanFeedback(
            stages={
                "tiebreaker": StageFeedback(ai_rating=7, ai_comment="fair decision"),
            }
        )
        out = render_template("test-plan", prefilled=fb)
        # Every stage heading must appear
        for stage in STAGES:
            assert f"## {stage}" in out, f"Missing heading for stage: {stage}"
            # Each stage section has ai_rating:/ai_comment:/rating:/comment:
            # Check that the ai_rating line exists for each stage
            assert "ai_rating:" in out  # present throughout

        # Specifically verify tiebreaker ai fields
        assert "ai_rating: 7" in out
        assert "ai_comment: fair decision" in out

    def test_prefilled_overall_block(self) -> None:
        """Template has Overall section with ai_* and blank rating/comment."""
        fb = PlanFeedback(overall=StageFeedback(ai_rating=9, ai_comment="nearly perfect"))
        out = render_template("test-plan", prefilled=fb)
        assert "## Overall" in out
        assert "ai_rating: 9" in out
        assert "ai_comment: nearly perfect" in out

    def test_no_prefilled_gives_blank_template(self) -> None:
        """Without prefilled, all ai_rating:/ai_comment:/rating:/comment: are blank."""
        out = render_template("test-plan")
        # ai_rating lines exist but are blank
        assert "ai_rating:" in out
        # No numeric ratings should appear
        assert "ai_rating: 0" not in out
        assert "ai_rating: 1" not in out

    def test_idea_included_when_provided(self) -> None:
        """The idea is included as a blockquote in the template."""
        out = render_template("test-plan", idea="build a thing")
        assert "> build a thing" in out


# ============================================================================
# (c) Parser — round-trips ai_* fields, regression test
# ============================================================================


class TestParseFeedback:
    """parse_feedback round-trips ai_* fields correctly."""

    def test_round_trip_ai_fields(self) -> None:
        """Feedback with ai_rating/ai_comment round-trips through parse."""
        text = textwrap.dedent("""\
            ## Overall
            ai_rating: 8
            ai_comment: solid work overall
            rating:
            comment:

            ## plan
            ai_rating: 9
            ai_comment: well-structured plan
            rating:
            comment:

            ## execute
            ai_rating: 6
            ai_comment: some missed items
            rating:
            comment:
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_rating == 8
        assert fb.overall.ai_comment == "solid work overall"
        assert fb.overall.rating is None
        assert fb.overall.comment is None

        assert fb.stages["plan"].ai_rating == 9
        assert fb.stages["plan"].ai_comment == "well-structured plan"

        assert fb.stages["execute"].ai_rating == 6
        assert fb.stages["execute"].ai_comment == "some missed items"

    def test_user_edited_rating_does_not_clobber_ai_rating(self) -> None:
        """User-edited rating: does NOT overwrite ai_rating:."""
        text = textwrap.dedent("""\
            ## Overall
            ai_rating: 8
            ai_comment: AI thinks this is great
            rating: 5
            comment: user disagrees
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_rating == 8
        assert fb.overall.ai_comment == "AI thinks this is great"
        assert fb.overall.rating == 5
        assert fb.overall.comment == "user disagrees"

    def test_regression_ai_rating_does_not_populate_rating(self) -> None:
        """ai_rating: 8 does NOT also populate the rating field (regex non-overlap)."""
        text = textwrap.dedent("""\
            ## Overall
            ai_rating: 8
            ai_comment: solid
            rating:
            comment:
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_rating == 8
        # rating must NOT be set — regex anchored with ^ai_rating and ^rating must not overlap
        assert fb.overall.rating is None, (
            "BUG: ai_rating: 8 accidentally populated the rating field "
            "(regex non-overlap violation)"
        )

    def test_regression_ai_comment_does_not_populate_comment(self) -> None:
        """ai_comment: text does NOT populate the comment field."""
        text = textwrap.dedent("""\
            ## Overall
            ai_comment: AI thought this was fine
            comment:
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_comment == "AI thought this was fine"
        assert fb.overall.comment is None, (
            "BUG: ai_comment accidentally populated the comment field"
        )

    def test_backward_compat_old_format_no_ai_fields(self) -> None:
        """Old feedback.md with only rating:/comment: still parses correctly."""
        text = textwrap.dedent("""\
            ## Overall
            rating: 7
            comment: decent run

            ## plan
            rating: 8
            comment: good structure
        """)
        fb = parse_feedback(text)
        assert fb.overall.rating == 7
        assert fb.overall.comment == "decent run"
        assert fb.overall.ai_rating is None
        assert fb.overall.ai_comment is None

        assert fb.stages["plan"].rating == 8
        assert fb.stages["plan"].comment == "good structure"

    def test_parse_multiline_comment(self) -> None:
        """Multiline comments under ai_comment or comment are captured correctly."""
        text = textwrap.dedent("""\
            ## Overall
            ai_rating: 7
            ai_comment: This is a long
            comment that spans
            multiple lines.
            rating:
            comment:
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_rating == 7
        # The parser captures everything until the next heading
        assert "This is a long" in (fb.overall.ai_comment or "")

    def test_parse_rating_with_slash_format(self) -> None:
        """Rating formats like '8/10' are parsed correctly."""
        text = textwrap.dedent("""\
            ## Overall
            ai_rating: 8/10
            ai_comment: good
            rating:
            comment:
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_rating == 8

    def test_parse_out_of_range_rating_returns_none(self) -> None:
        """Ratings outside 0-10 return None."""
        text = textwrap.dedent("""\
            ## Overall
            ai_rating: 15
            ai_comment: overrated
            rating:
            comment:
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_rating is None

    def test_parse_negative_rating_returns_none(self) -> None:
        """Negative ratings return None."""
        text = textwrap.dedent("""\
            ## Overall
            ai_rating: -3
            ai_comment: terrible
            rating:
            comment:
        """)
        fb = parse_feedback(text)
        assert fb.overall.ai_rating is None

    def test_empty_sections_are_skipped(self) -> None:
        """Sections with no data are not added to stages."""
        text = textwrap.dedent("""\
            ## Overall
            rating: 7
            comment: ok

            ## plan
            rating:
            comment:
        """)
        fb = parse_feedback(text)
        assert "plan" not in fb.stages


# ============================================================================
# (d) Prompt builder — build_feedback_prompt
# ============================================================================


class TestBuildFeedbackPrompt:
    """build_feedback_prompt mentions every stage with artifacts, marks absent ones."""

    def test_mentions_every_ran_stage(self, tmp_path: Path) -> None:
        """Prompt mentions every stage that has artifacts."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        # Create minimal artifacts for all 9 STAGES
        (plan_dir / "prep.json").write_text(
            json.dumps({"findings": [{"fact": "x"}], "scope": "test scope"}),
            encoding="utf-8",
        )
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nSome plan text.\n", encoding="utf-8")
        (plan_dir / "critique_v1.json").write_text(
            json.dumps({"flags": [{"category": "completeness"}, {"category": "safety"}]}),
            encoding="utf-8",
        )
        (plan_dir / "gate.json").write_text(
            json.dumps({"recommendation": "PROCEED", "passed": True}),
            encoding="utf-8",
        )
        (plan_dir / "tiebreaker_synthesis.json").write_text(
            json.dumps({"winner": "branch_a"}),
            encoding="utf-8",
        )
        (plan_dir / "finalize.json").write_text(
            json.dumps({"tasks": [{"id": "T1"}, {"id": "T2"}], "batches": 1}),
            encoding="utf-8",
        )
        (plan_dir / "execution.json").write_text(
            json.dumps({"tasks": [
                {"id": "T1", "status": "done"},
                {"id": "T2", "status": "done"},
            ]}),
            encoding="utf-8",
        )
        (plan_dir / "review.json").write_text(
            json.dumps({"review_verdict": "approved", "summary": "looks good"}),
            encoding="utf-8",
        )

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 1,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "standard", "profile": "thoughtful"},
            "meta": {"total_cost_usd": 0.05},
            "history": [],
        }

        prompt = build_feedback_prompt(plan_dir, state)

        # Every stage should be mentioned in the digests
        for stage in STAGES:
            assert f"### {stage}" in prompt, (
                f"Prompt missing digest heading for stage: {stage}"
            )

        # Stages that ran should NOT say "did not run"
        assert "did not run" not in prompt or "did not run" not in prompt.split("### prep")[1].split("### plan")[0] if "### prep" in prompt else True

    def test_marks_absent_stages(self, tmp_path: Path) -> None:
        """Stages that didn't run get 'did not run'."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        # Only create plan and gate artifacts — others absent
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nText.\n", encoding="utf-8")
        (plan_dir / "gate.json").write_text(
            json.dumps({"recommendation": "PROCEED", "passed": True}),
            encoding="utf-8",
        )

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 1,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "standard", "profile": "thoughtful"},
            "meta": {"total_cost_usd": 0.01},
            "history": [],
        }

        prompt = build_feedback_prompt(plan_dir, state)

        # Absent stages should say "did not run"
        for stage in ["prep", "critique", "revise", "tiebreaker", "finalize", "execute", "review"]:
            stage_section_start = prompt.find(f"### {stage}")
            if stage_section_start >= 0:
                next_section = prompt.find("###", stage_section_start + len(f"### {stage}"))
                section_body = prompt[stage_section_start:next_section] if next_section >= 0 else prompt[stage_section_start:]
                assert "did not run" in section_body, (
                    f"Stage {stage} should say 'did not run' but it didn't"
                )

    def test_tiebreaker_absent_marks_did_not_run(self, tmp_path: Path) -> None:
        """When no tiebreaker artifacts exist, prompt marks it 'did not run'."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nText.\n", encoding="utf-8")

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 1,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "standard", "profile": "thoughtful"},
            "meta": {"total_cost_usd": 0.01},
            "history": [],
        }

        prompt = build_feedback_prompt(plan_dir, state)
        assert "Tiebreaker did not run" in prompt

    def test_tiebreaker_present_mentions_winner(self, tmp_path: Path) -> None:
        """When tiebreaker artifacts exist, prompt mentions winner."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nText.\n", encoding="utf-8")
        (plan_dir / "tiebreaker_synthesis.json").write_text(
            json.dumps({"winner": "branch_b"}),
            encoding="utf-8",
        )

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 1,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "standard", "profile": "thoughtful"},
            "meta": {"total_cost_usd": 0.01},
            "history": [],
        }

        prompt = build_feedback_prompt(plan_dir, state)
        assert "winner: branch_b" in prompt

    def test_prompt_includes_rubric_text(self, tmp_path: Path) -> None:
        """Prompt body includes the full rubric text."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nText.\n", encoding="utf-8")

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 1,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "standard", "profile": "thoughtful"},
            "meta": {"total_cost_usd": 0.01},
            "history": [],
        }

        prompt = build_feedback_prompt(plan_dir, state)

        # Check key rubric text is present
        assert "retrospective evaluator" in prompt
        assert "Errors of leniency cost" in prompt
        assert "Rate quality only, not cost-effectiveness" in prompt
        assert "Scale (0-10)" in prompt
        assert "textbook; no notes" in prompt

    def test_prompt_includes_tiebreaker_rubric(self, tmp_path: Path) -> None:
        """Prompt includes tiebreaker rubric line."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nText.\n", encoding="utf-8")

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 1,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "standard", "profile": "thoughtful"},
            "meta": {"total_cost_usd": 0.01},
            "history": [],
        }

        prompt = build_feedback_prompt(plan_dir, state)
        assert "tiebreaker: did the decision pick the better branch" in prompt

    def test_prompt_includes_run_meta(self, tmp_path: Path) -> None:
        """Prompt includes run metadata."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nText.\n", encoding="utf-8")

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 3,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "robust", "profile": "super-premium"},
            "meta": {"total_cost_usd": 12.50},
            "history": [
                {"step": "plan", "duration_ms": 5000},
                {"step": "critique", "duration_ms": 3000},
            ],
        }

        prompt = build_feedback_prompt(plan_dir, state)
        assert "Robustness: robust" in prompt
        assert "Profile: super-premium" in prompt
        assert "Iteration: 3" in prompt
        assert "$12.5000 USD" in prompt

    def test_prompt_includes_json_instruction(self, tmp_path: Path) -> None:
        """Prompt includes strict JSON response instruction."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        (plan_dir / "plan_v1.md").write_text("## Plan\n\nText.\n", encoding="utf-8")

        state = {
            "name": "test",
            "current_state": "reviewed",
            "iteration": 1,
            "plan_versions": [{"file": "plan_v1.md"}],
            "config": {"robustness": "standard", "profile": "thoughtful"},
            "meta": {"total_cost_usd": 0.01},
            "history": [],
        }

        prompt = build_feedback_prompt(plan_dir, state)
        assert '"overall": {"rating": int, "comment": str}' in prompt
        assert "Only include stages that actually ran" in prompt


# ============================================================================
# (e) Routing — profile loading, vendor rewrite
# ============================================================================


class TestRouting:
    """Profile loading and vendor-rewrite routing for the feedback slot."""

    def test_any_profile_loads_with_feedback_slot(self) -> None:
        """Loading any TOML profile with a valid feedback slot succeeds."""
        from arnold.pipelines.megaplan.profiles import load_profile_sources
        sources = load_profile_sources()
        # sources is list[tuple[str, str, dict]]: (source, name, profile)
        builtin_sources = [(name, profile) for src, name, profile in sources if src == "built-in"]
        for name, profile in builtin_sources:
            assert "feedback" in profile, (
                f"Profile '{name}' missing 'feedback' slot"
            )
            # Most built-in profiles pin feedback to Claude. The Arnold launch
            # profile is intentionally all-OpenRouter so a no-Anthropic-key run
            # can keep every role on the available provider.
            expected_feedback = (
                ("hermes:openrouter:deepseek/deepseek-chat",)
                if name == "arnold-openrouter"
                else ("claude:low", "claude")
            )
            assert profile["feedback"] in expected_feedback, (
                f"Profile '{name}' has unexpected feedback value: {profile['feedback']}"
            )

    def test_vendor_rewrite_leaves_feedback_at_claude_low(self) -> None:
        """apply_vendor_rewrite('codex') leaves feedback at claude:low."""
        from arnold.pipelines.megaplan.profiles import apply_vendor_rewrite
        profile = {
            "plan": "claude",
            "critique": "codex",
            "execute": "codex",
            "review": "codex",
            "feedback": "claude:low",
        }
        rewritten = apply_vendor_rewrite(profile, "codex")
        # All premium slots become codex, but feedback stays claude:low
        assert rewritten["feedback"] == "claude:low"
        assert rewritten["plan"] == "codex"

    def test_vendor_rewrite_claude_vendor_for_claude_profile(self) -> None:
        """apply_vendor_rewrite('claude') on a claude profile leaves feedback."""
        from arnold.pipelines.megaplan.profiles import apply_vendor_rewrite
        profile = {
            "plan": "claude",
            "critique": "claude",
            "feedback": "claude:low",
        }
        rewritten = apply_vendor_rewrite(profile, "claude")
        assert rewritten["feedback"] == "claude:low"
        # plan and critique stay claude
        assert rewritten["plan"] == "claude"

    def test_depth_rewrite_does_not_affect_feedback(self) -> None:
        """apply_depth_rewrite does NOT affect feedback slot."""
        from arnold.pipelines.megaplan.profiles import apply_depth_rewrite
        profile = {
            "plan": "claude",
            "feedback": "claude:low",
        }
        rewritten = apply_depth_rewrite(profile, "medium")
        assert rewritten["feedback"] == "claude:low"
        # plan gets depth applied
        assert rewritten["plan"] == "claude:medium"

    def test_critic_rewrite_does_not_affect_feedback(self) -> None:
        """apply_critic_rewrite does NOT affect feedback slot."""
        from arnold.pipelines.megaplan.profiles import apply_critic_rewrite
        profile = {
            "plan": "claude",
            "critique": "codex",
            "review": "codex",
            "feedback": "claude:low",
        }
        rewritten = apply_critic_rewrite(profile, "cross", vendor="claude")
        assert rewritten["feedback"] == "claude:low"
        # The critic rewrite does affect critique+review (cross from claude→codex)
        # but importantly feedback is untouched
        assert "feedback" in rewritten

    def test_vendor_rewrite_preserves_bare_feedback_not_normalized_or_swapped(self) -> None:
        """Bare feedback='claude' stays 'claude' — not normalized to 'claude:low'
        and not swapped to the target vendor."""
        from arnold.pipelines.megaplan.profiles import apply_vendor_rewrite

        # all-claude.toml has bare feedback = "claude" (no effort suffix).
        # This test proves that behavior is intentional: bare values are
        # preserved as-is during vendor rewrite.
        profile: dict[str, str] = {
            "plan": "claude",
            "critique": "claude",
            "execute": "claude",
            "review": "claude",
            "feedback": "claude",  # bare — no ':low' suffix
        }
        rewritten = apply_vendor_rewrite(profile, "codex")
        # Premium phases become codex (vendor-swapped)
        assert rewritten["plan"] == "codex"
        assert rewritten["critique"] == "codex"
        # feedback is NOT vendor-swapped — it stays claude
        assert rewritten["feedback"] == "claude"
        # feedback is NOT normalized — bare "claude" stays bare,
        # not coerced to "claude:low"
        assert rewritten["feedback"] != "claude:low"

    def test_vendor_rewrite_defaults_feedback_when_absent(self) -> None:
        """When profile has no 'feedback' key, apply_vendor_rewrite defaults
        to 'claude:low'."""
        from arnold.pipelines.megaplan.profiles import apply_vendor_rewrite

        profile: dict[str, str] = {
            "plan": "claude",
            "critique": "codex",
        }
        rewritten = apply_vendor_rewrite(profile, "claude")
        assert rewritten["feedback"] == "claude:low"
        assert rewritten["plan"] == "claude"

    def test_default_agent_routing_has_feedback(self) -> None:
        """DEFAULT_AGENT_ROUTING includes 'feedback' key."""
        from arnold.pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING
        assert "feedback" in DEFAULT_AGENT_ROUTING
        assert DEFAULT_AGENT_ROUTING["feedback"] == "claude:low"


# ============================================================================
# (f) Handler happy path — mock worker returns valid JSON
# ============================================================================


class TestHandlerHappyPath:
    """handle_feedback workflow with mocked worker returning valid JSON."""

    def test_handler_happy_path_populates_ai_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mock worker returns valid JSON → feedback.md gets populated ai_* fields."""
        root = tmp_path / "root"
        project_dir = tmp_path / "project"
        root.mkdir()
        project_dir.mkdir()
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
        monkeypatch.setattr(
            megaplan._core.shutil,
            "which",
            lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
        )

        from tests.conftest import make_args_factory

        make_args = make_args_factory(project_dir)
        response = megaplan.handle_init(
            root, make_args(name="fb-happy", with_feedback=True)
        )
        plan_dir = megaplan.plans_root(root) / response["plan"]

        # Place plan in STATE_REVIEWED
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state["current_state"] = STATE_REVIEWED
        state["idea"] = "test the happy path"
        save_state(plan_dir, state)

        fb_path = feedback_path(plan_dir)
        assert not fb_path.exists(), "feedback.md should not exist before handler"

        # Create a mock WorkerResult with valid feedback JSON
        mock_worker = WorkerResult(
            payload={},
            raw_output=json.dumps({
                "overall": {"rating": 8, "comment": "Solid execution throughout."},
                "stages": {
                    "plan": {"rating": 9, "comment": "Well-structured plan."},
                    "execute": {"rating": 7, "comment": "Followed plan with minor drift."},
                    "review": {"rating": 8, "comment": "Caught key issues."},
                },
            }),
            duration_ms=1000,
            cost_usd=0.01,
            session_id="test-session",
        )

        # Mock _run_worker to return the mock worker result
        with mock.patch(
            "arnold.pipelines.megaplan.handlers.shared._run_worker",
            return_value=(mock_worker, "claude", "low", False),
        ):
            from arnold.pipelines.megaplan.cli import handle_feedback

            result = handle_feedback(
                root,
                Namespace(
                    operation="workflow",
                    plan=response["plan"],
                    actor=None,
                    agent=None,
                    force=False,
                ),
            )

        # Verify response
        assert result["success"] is True
        assert result["state"] == "done"
        assert result["ai_filled"] is True
        assert result["feedback_present"] is True

        # Verify feedback.md was created with ai_* fields
        assert fb_path.exists()
        content = fb_path.read_text(encoding="utf-8")
        assert "ai_rating: 8" in content
        assert "ai_comment: Solid execution throughout" in content
        assert "ai_rating: 9" in content  # plan stage
        assert "ai_rating: 7" in content  # execute stage

        # Verify state transitioned to DONE
        updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert updated_state["current_state"] == STATE_DONE


# ============================================================================
# (g) Handler malformed output — parse fails, empty template, state DONE
# ============================================================================


class TestHandlerMalformedOutput:
    """handle_feedback with invalid worker output."""

    def test_handler_malformed_json_writes_empty_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mock worker returns invalid JSON → empty template written, state DONE."""
        root = tmp_path / "root"
        project_dir = tmp_path / "project"
        root.mkdir()
        project_dir.mkdir()
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
        monkeypatch.setattr(
            megaplan._core.shutil,
            "which",
            lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
        )

        from tests.conftest import make_args_factory

        make_args = make_args_factory(project_dir)
        response = megaplan.handle_init(
            root, make_args(name="fb-malformed", with_feedback=True)
        )
        plan_dir = megaplan.plans_root(root) / response["plan"]

        # Place plan in STATE_REVIEWED
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state["current_state"] = STATE_REVIEWED
        save_state(plan_dir, state)

        fb_path = feedback_path(plan_dir)
        assert not fb_path.exists()

        # Mock worker with invalid JSON output
        mock_worker = WorkerResult(
            payload={},
            raw_output="This is not valid JSON at all {{{{ broken",
            duration_ms=1000,
            cost_usd=0.01,
            session_id="test-session",
        )

        with mock.patch(
            "arnold.pipelines.megaplan.handlers.shared._run_worker",
            return_value=(mock_worker, "claude", "low", False),
        ):
            from arnold.pipelines.megaplan.cli import handle_feedback

            result = handle_feedback(
                root,
                Namespace(
                    operation="workflow",
                    plan=response["plan"],
                    actor=None,
                    agent=None,
                    force=False,
                ),
            )

        # Verify response
        assert result["success"] is True
        assert result["state"] == "done"
        assert result["ai_filled"] is False  # AI fill failed
        assert result["feedback_present"] is True

        # feedback.md was created (empty template)
        assert fb_path.exists()
        content = fb_path.read_text(encoding="utf-8")
        # Should have headings but NO ai_rating values populated
        assert "## Overall" in content
        # ai_rating lines exist but should be blank (no numeric value populated)
        assert "ai_rating:" in content

        # Verify state transitioned to DONE
        updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert updated_state["current_state"] == STATE_DONE

    def test_handler_worker_exception_does_not_raise(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If resolve_agent_mode raises, handler catches it, writes template, transitions."""
        root = tmp_path / "root"
        project_dir = tmp_path / "project"
        root.mkdir()
        project_dir.mkdir()
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
        monkeypatch.setattr(
            megaplan._core.shutil,
            "which",
            lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
        )

        from tests.conftest import make_args_factory

        make_args = make_args_factory(project_dir)
        response = megaplan.handle_init(
            root, make_args(name="fb-exception", with_feedback=True)
        )
        plan_dir = megaplan.plans_root(root) / response["plan"]

        # Place plan in STATE_REVIEWED
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state["current_state"] = STATE_REVIEWED
        save_state(plan_dir, state)

        fb_path = feedback_path(plan_dir)

        # Mock _run_worker to raise an exception
        with mock.patch(
            "arnold.pipelines.megaplan.handlers.shared._run_worker",
            side_effect=RuntimeError("Simulated worker crash"),
        ):
            from arnold.pipelines.megaplan.cli import handle_feedback

            # Should NOT raise — exceptions are caught internally
            result = handle_feedback(
                root,
                Namespace(
                    operation="workflow",
                    plan=response["plan"],
                    actor=None,
                    agent=None,
                    force=False,
                ),
            )

        assert result["success"] is True
        assert result["state"] == "done"
        assert result["ai_filled"] is False

        # Template was created
        assert fb_path.exists()
        assert "## Overall" in fb_path.read_text(encoding="utf-8")

        # State is DONE
        updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert updated_state["current_state"] == STATE_DONE


# ============================================================================
# (h) Handler --force merge — preserves user fields, overwrites ai_*
# ============================================================================


class TestHandlerForceMerge:
    """handle_feedback --force with existing user-edited feedback."""

    def test_force_preserves_user_rating_overwrites_ai_rating(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--force with existing user rating:7 and AI rating 8 → user:7, ai:8."""
        root = tmp_path / "root"
        project_dir = tmp_path / "project"
        root.mkdir()
        project_dir.mkdir()
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
        monkeypatch.setattr(
            megaplan._core.shutil,
            "which",
            lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
        )

        from tests.conftest import make_args_factory

        make_args = make_args_factory(project_dir)
        response = megaplan.handle_init(
            root, make_args(name="fb-force", with_feedback=True)
        )
        plan_dir = megaplan.plans_root(root) / response["plan"]

        # Place plan in STATE_REVIEWED, pre-create feedback.md with user fields
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state["current_state"] = STATE_REVIEWED
        state["idea"] = "force merge test"
        save_state(plan_dir, state)

        fb_path = feedback_path(plan_dir)
        original_content = textwrap.dedent("""\
            ## Overall
            ai_rating: 6
            ai_comment: old ai judgment
            rating: 7
            comment: user thinks it's decent

            ## plan
            rating: 8
            comment: user liked the plan
        """)
        fb_path.write_text(original_content, encoding="utf-8")

        # Mock worker to return new AI ratings
        mock_worker = WorkerResult(
            payload={},
            raw_output=json.dumps({
                "overall": {"rating": 8, "comment": "Better than expected."},
                "stages": {
                    "plan": {"rating": 9, "comment": "Excellent plan structure."},
                    "execute": {"rating": 6, "comment": "Adequate execution."},
                },
            }),
            duration_ms=500,
            cost_usd=0.005,
            session_id="test-force",
        )

        with mock.patch(
            "arnold.pipelines.megaplan.handlers.shared._run_worker",
            return_value=(mock_worker, "claude", "low", False),
        ):
            from arnold.pipelines.megaplan.cli import handle_feedback

            result = handle_feedback(
                root,
                Namespace(
                    operation="workflow",
                    plan=response["plan"],
                    actor=None,
                    agent=None,
                    force=True,
                ),
            )

        assert result["success"] is True
        assert result["ai_filled"] is True

        # Parse the resulting file
        content = fb_path.read_text(encoding="utf-8")
        fb = parse_feedback(content)

        # User rating:7 preserved
        assert fb.overall.rating == 7, "User rating should be preserved"
        assert fb.overall.comment == "user thinks it's decent"

        # AI rating overwritten with new value (was 6, now 8)
        assert fb.overall.ai_rating == 8
        assert fb.overall.ai_comment == "Better than expected."

        # Stage: user rating preserved
        assert "plan" in fb.stages
        assert fb.stages["plan"].rating == 8
        assert fb.stages["plan"].comment == "user liked the plan"
        assert fb.stages["plan"].ai_rating == 9
        assert fb.stages["plan"].ai_comment == "Excellent plan structure."

        # New stage from AI response also present
        assert "execute" in fb.stages
        assert fb.stages["execute"].ai_rating == 6


# ============================================================================
# (i) Idempotency — second run without --force is a no-op
# ============================================================================


class TestHandlerIdempotency:
    """Re-running feedback without --force on populated feedback.md."""

    def test_second_run_with_user_fields_is_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second run without --force on feedback.md with user rating is a no-op.

        NOTE: State must be reseeded to STATE_REVIEWED before the second call
        because the real first run transitions to STATE_DONE. See comment above.
        """
        root = tmp_path / "root"
        project_dir = tmp_path / "project"
        root.mkdir()
        project_dir.mkdir()
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
        monkeypatch.setattr(
            megaplan._core.shutil,
            "which",
            lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
        )

        from tests.conftest import make_args_factory

        make_args = make_args_factory(project_dir)
        response = megaplan.handle_init(
            root, make_args(name="fb-idem2", with_feedback=True)
        )
        plan_dir = megaplan.plans_root(root) / response["plan"]

        # Pre-populate with user rating set (triggers skip-AI guard)
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state["current_state"] = STATE_REVIEWED
        save_state(plan_dir, state)

        fb_path = feedback_path(plan_dir)
        original = textwrap.dedent("""\
            ## Overall
            ai_rating: 8
            ai_comment: AI rated this
            rating: 7
            comment: user reviewed

            ## plan
            rating: 6
            comment: user notes on plan
        """)
        fb_path.write_text(original, encoding="utf-8")

        # Reseed state (simulate first run completed, now re-running)
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        state["current_state"] = STATE_REVIEWED
        save_state(plan_dir, state)

        # Worker must NOT be called
        with mock.patch(
            "arnold.pipelines.megaplan.handlers.shared._run_worker",
            side_effect=RuntimeError("Worker should NOT be invoked"),
        ) as mock_run:
            from arnold.pipelines.megaplan.cli import handle_feedback

            result = handle_feedback(
                root,
                Namespace(
                    operation="workflow",
                    plan=response["plan"],
                    actor=None,
                    agent=None,
                    force=False,
                ),
            )
            mock_run.assert_not_called()

        assert result["success"] is True
        assert result["ai_filled"] is False
        assert "skipped AI pass" in result.get("summary", "")

        # Content preserved
        assert fb_path.read_text(encoding="utf-8") == original

        updated_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert updated_state["current_state"] == STATE_DONE


# ============================================================================
# (j) Display — _render_feedback_table, format_summary with AI ratings
# ============================================================================


class TestDisplay:
    """_render_feedback_table and format_summary show AI ratings."""

    def test_render_table_shows_ai_rating(self) -> None:
        """_render_feedback_table shows AI rating when only ai_* is set."""
        from arnold.pipelines.megaplan.cli import _render_feedback_table

        rows = [
            {
                "plan": "test-plan",
                "profile": "thoughtful",
                "backend": "cl",
                "repo": "/tmp/repo",
                "feedback": {
                    "overall": {
                        "rating": None,
                        "comment": None,
                        "ai_rating": 8,
                        "ai_comment": "Solid run overall",
                    },
                },
            },
        ]

        table = _render_feedback_table(rows)
        assert "8/10 (AI)" in table, (
            f"Table should show '8/10 (AI)' for AI-only rating, got:\n{table}"
        )
        assert "(AI) Solid run overall" in table

    def test_render_table_shows_user_rating(self) -> None:
        """_render_feedback_table shows user rating without AI suffix."""
        from arnold.pipelines.megaplan.cli import _render_feedback_table

        rows = [
            {
                "plan": "test-plan",
                "profile": "thoughtful",
                "backend": "cl",
                "repo": "/tmp/repo",
                "feedback": {
                    "overall": {
                        "rating": 9,
                        "comment": "Great work",
                        "ai_rating": 8,
                    },
                },
            },
        ]

        table = _render_feedback_table(rows)
        assert "9/10" in table
        # No (AI) suffix since user rating exists
        assert "9/10 (AI)" not in table

    def test_render_table_handles_no_rating(self) -> None:
        """_render_feedback_table shows '—' when no rating is set."""
        from arnold.pipelines.megaplan.cli import _render_feedback_table

        rows = [
            {
                "plan": "empty-plan",
                "profile": "basic",
                "backend": "cl",
                "repo": "/tmp/repo",
                "feedback": {
                    "overall": {
                        "rating": None,
                        "comment": None,
                        "ai_rating": None,
                    },
                },
            },
        ]

        table = _render_feedback_table(rows)
        assert "—" in table

    def test_render_table_empty_rows(self) -> None:
        """_render_feedback_table returns (no matches) for empty rows."""
        from arnold.pipelines.megaplan.cli import _render_feedback_table

        result = _render_feedback_table([])
        assert result.strip() == "(no matches)"

    def test_format_summary_shows_ai_suffix(self) -> None:
        """format_summary shows (AI) suffix when only ai_* is set."""
        fb = PlanFeedback(
            overall=StageFeedback(ai_rating=8, ai_comment="AI verdict"),
            stages={
                "plan": StageFeedback(ai_rating=9, ai_comment="Great plan"),
                "execute": StageFeedback(rating=7, comment="user exec rating", ai_rating=6),
            },
        )
        summary = format_summary(fb)

        # Overall: AI-only
        assert "8/10 (AI)" in summary
        assert "AI verdict" in summary

        # plan: AI-only
        assert "9/10 (AI)" in summary
        assert "Great plan" in summary

        # execute: user rating, no AI suffix
        assert "plan" in summary  # plan stage listed
        # User rating line for execute
        assert "7/10" in summary

    def test_format_summary_no_ai_suffix_for_user_rating(self) -> None:
        """format_summary does NOT show (AI) suffix when user rating is set."""
        fb = PlanFeedback(
            overall=StageFeedback(rating=7, ai_rating=9),
        )
        summary = format_summary(fb)
        assert "7/10" in summary
        assert "7/10 (AI)" not in summary

    def test_format_summary_handles_empty_feedback(self) -> None:
        """format_summary handles empty PlanFeedback."""
        fb = PlanFeedback()
        summary = format_summary(fb)
        assert "—" in summary


# ============================================================================
# (k) Filter — _filter_feedback_rows with AI ratings
# ============================================================================


class TestFilter:
    """_filter_feedback_rows matches ai_rating with --min-rating."""

    def test_min_rating_matches_ai_rating(self) -> None:
        """--min-rating 7 matches ai_rating: 8 with no user rating."""
        from arnold.pipelines.megaplan.cli import _filter_feedback_rows

        rows = [
            {
                "plan": "ai-rated-plan",
                "profile": "thoughtful",
                "repo": "/tmp/repo",
                "backend": "cl",
                "feedback": {
                    "overall": {
                        "rating": None,
                        "comment": None,
                        "ai_rating": 8,
                        "ai_comment": "Solid run",
                    },
                },
            },
            {
                "plan": "user-rated-plan",
                "profile": "basic",
                "repo": "/tmp/repo2",
                "backend": "cx",
                "feedback": {
                    "overall": {
                        "rating": 5,
                        "comment": "Meh",
                        "ai_rating": 7,
                    },
                },
            },
            {
                "plan": "no-rating-plan",
                "profile": "led",
                "repo": "/tmp/repo3",
                "backend": "cl",
                "feedback": {
                    "overall": {
                        "rating": None,
                        "ai_rating": None,
                    },
                },
            },
        ]

        args = Namespace(
            min_rating=7,
            max_rating=None,
            profile=None,
            repo=None,
            stage=None,
            has_comment=False,
        )

        filtered = _filter_feedback_rows(rows, args)
        assert len(filtered) == 1, (
            f"Expected 1 match (ai_rating:8), got {len(filtered)}"
        )
        assert filtered[0]["plan"] == "ai-rated-plan"

    def test_max_rating_filters_out_high_ratings(self) -> None:
        """--max-rating 6 filters out ai_rating: 8."""
        from arnold.pipelines.megaplan.cli import _filter_feedback_rows

        rows = [
            {
                "plan": "high-rated",
                "profile": "thoughtful",
                "repo": "/tmp/repo",
                "backend": "cl",
                "feedback": {
                    "overall": {"ai_rating": 8},
                },
            },
            {
                "plan": "low-rated",
                "profile": "basic",
                "repo": "/tmp/repo2",
                "backend": "cx",
                "feedback": {
                    "overall": {"ai_rating": 4},
                },
            },
        ]

        args = Namespace(
            min_rating=None,
            max_rating=6,
            profile=None,
            repo=None,
            stage=None,
            has_comment=False,
        )

        filtered = _filter_feedback_rows(rows, args)
        assert len(filtered) == 1
        assert filtered[0]["plan"] == "low-rated"

    def test_stage_filter_uses_effective_rating(self) -> None:
        """--stage plan filter matches ai_rating on stage entry."""
        from arnold.pipelines.megaplan.cli import _filter_feedback_rows

        rows = [
            {
                "plan": "with-plan-ai",
                "profile": "thoughtful",
                "repo": "/tmp/repo",
                "backend": "cl",
                "feedback": {
                    "overall": {},
                    "stages": {
                        "plan": {"ai_rating": 8, "ai_comment": "good plan"},
                    },
                },
            },
        ]

        args = Namespace(
            min_rating=None,
            max_rating=None,
            profile=None,
            repo=None,
            stage="plan",
            has_comment=False,
        )

        filtered = _filter_feedback_rows(rows, args)
        assert len(filtered) == 1, (
            f"Stage filter should match ai_rating on plan, got {len(filtered)}"
        )

    def test_has_comment_matches_ai_comment(self) -> None:
        """--has-comment matches when only ai_comment is set."""
        from arnold.pipelines.megaplan.cli import _filter_feedback_rows

        rows = [
            {
                "plan": "ai-comment-only",
                "profile": "basic",
                "repo": "/tmp/repo",
                "backend": "cl",
                "feedback": {
                    "overall": {
                        "ai_rating": 5,
                        "ai_comment": "Mediocre performance",
                    },
                },
            },
        ]

        args = Namespace(
            min_rating=None,
            max_rating=None,
            profile=None,
            repo=None,
            stage=None,
            has_comment=True,
        )

        filtered = _filter_feedback_rows(rows, args)
        assert len(filtered) == 1

    def test_user_rating_overrides_ai_in_filter(self) -> None:
        """User rating 5 overrides ai_rating 9 → --min-rating 7 rejects it."""
        from arnold.pipelines.megaplan.cli import _filter_feedback_rows

        rows = [
            {
                "plan": "user-overrides",
                "profile": "thoughtful",
                "repo": "/tmp/repo",
                "backend": "cl",
                "feedback": {
                    "overall": {
                        "rating": 5,
                        "ai_rating": 9,
                    },
                },
            },
        ]

        args = Namespace(
            min_rating=7,
            max_rating=None,
            profile=None,
            repo=None,
            stage=None,
            has_comment=False,
        )

        filtered = _filter_feedback_rows(rows, args)
        assert len(filtered) == 0, (
            "User rating 5 should override ai_rating 9, so min-rating 7 rejects it"
        )


# ============================================================================
# Integration: load_feedback / feedback_path helpers
# ============================================================================


class TestLoadFeedback:
    """load_feedback reads and parses feedback files."""

    def test_load_feedback_ai_only(self, tmp_path: Path) -> None:
        """load_feedback parses a feedback.md with only ai_* fields."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        fb_path = plan_dir / FEEDBACK_FILENAME
        fb_path.write_text(
            textwrap.dedent("""\
                ## Overall
                ai_rating: 8
                ai_comment: AI analysis
                rating:
                comment:
            """),
            encoding="utf-8",
        )

        fb = load_feedback(plan_dir)
        assert fb is not None
        assert fb.overall.ai_rating == 8
        assert fb.overall.ai_comment == "AI analysis"
        assert fb.overall.rating is None

    def test_load_feedback_missing_file_returns_none(self, tmp_path: Path) -> None:
        """load_feedback returns None when no feedback.md exists."""
        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        fb = load_feedback(plan_dir)
        assert fb is None
