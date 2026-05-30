"""Tests for T14: verification delta plumbing into the revise prompt.

Covers:
- ``extract_failure_details``: correct parsing, sentinel fallback, no-dropped-entries
- ``_build_verification_delta_block``: newly_failing with tracebacks, still_red
  name-only, absent verdict → empty block, char-capped at ~5000
- ``_revise_prompt``: delta block injection, raw log path never exposed
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from megaplan._core import atomic_write_json, atomic_write_text
from megaplan.prompts.critique import (
    _build_verification_delta_block,
    _revise_prompt,
)
from megaplan.orchestration.suite_runner import extract_failure_details
from megaplan.types import PlanState


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _state(project_dir: Path, *, iteration: int = 1) -> PlanState:
    return {
        "name": "test-plan",
        "idea": "collapse the workflow",
        "current_state": "critiqued",
        "iteration": iteration,
        "created_at": "2026-03-20T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": iteration,
                "file": f"plan_v{iteration}.md",
                "hash": "sha256:test",
                "timestamp": "2026-03-20T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [3.5] if iteration > 1 else [],
            "plan_deltas": [42.0] if iteration > 1 else [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }


def _scaffold(tmp_path: Path, *, iteration: int = 1) -> tuple[Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    state = _state(project_dir, iteration=iteration)

    atomic_write_text(plan_dir / f"plan_v{iteration}.md", "# Plan\nDo the thing.\n")
    atomic_write_json(
        plan_dir / f"plan_v{iteration}.meta.json",
        {
            "version": iteration,
            "timestamp": "2026-03-20T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "questions": ["question"],
            "assumptions": ["assumption"],
        },
    )
    atomic_write_json(
        plan_dir / f"critique_v{iteration}.json",
        {"flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
    )
    atomic_write_json(
        plan_dir / f"gate_signals_v{iteration}.json",
        {
            "robustness": "standard",
            "signals": {
                "iteration": iteration,
                "weighted_score": 2.0,
                "weighted_history": [3.5] if iteration > 1 else [],
                "plan_delta_from_previous": 25.0,
                "recurring_critiques": ["same issue"] if iteration > 1 else [],
                "loop_summary": "Iteration summary",
                "scope_creep_flags": [],
            },
            "warnings": ["watch it"],
            "criteria_check": {"count": 1, "items": ["criterion"]},
            "preflight_results": {
                "project_dir_exists": True,
                "project_dir_writable": True,
                "success_criteria_present": True,
                "claude_available": True,
                "codex_available": True,
            },
            "unresolved_flags": [
                {
                    "id": "FLAG-001",
                    "concern": "still open",
                    "category": "correctness",
                    "severity": "significant",
                }
            ],
        },
    )
    atomic_write_json(plan_dir / "gate.json", {"recommendation": "ITERATE"})

    return plan_dir, state


def _write_verdict(
    plan_dir: Path,
    *,
    newly_failing: list[str] | None = None,
    still_red: list[str] | None = None,
    raw_log_path: str = "/tmp/raw_abc.log",
    computable: bool = True,
) -> None:
    """Write a ``completion_verdict.json`` with a green_suite delta."""
    delta: dict = {
        "computable": computable,
        "newly_failing": newly_failing or [],
        "newly_passing": [],
        "still_red": still_red or [],
        "still_green": [],
        "deleted_tests": [],
        "added_tests": [],
        "flakes": [],
        "tests_collected": 10,
        "duration": 1.5,
        "flake_retry_skipped": False,
        "flake_retry_reason": "",
    }
    verdict = {
        "mode": "shadow",
        "subject": {"kind": "plan", "name": "test", "to_state": "done"},
        "evidence": [
            {
                "kind": "green_suite",
                "status": "failed" if newly_failing else "passed",
                "summary": "verification suite",
                "details": {
                    "delta": delta,
                    "raw_log_path": raw_log_path,
                    "failures": newly_failing or [],
                },
            }
        ],
        "accepted": True,
        "failures": [],
        "green_suite": {"delta": delta},
    }
    atomic_write_json(plan_dir / "completion_verdict.json", verdict)


def _write_raw_log(path: Path, content: str) -> Path:
    """Write a raw pytest log and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# extract_failure_details — direct unit tests
# ---------------------------------------------------------------------------


class TestExtractFailureDetails:
    """Tests for ``extract_failure_details`` in suite_runner.py."""

    def test_two_newly_failing_produce_both_nodeids_and_details(self, tmp_path: Path):
        """Both nodeids appear in the output with parsed error details."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            textwrap.dedent("""\
                collected 5 items
                FAILED tests/test_foo.py::test_a - AssertionError: expected 2 but got 1
                FAILED tests/test_foo.py::test_b - ValueError: bad value
                2 failed, 3 passed
            """),
        )
        results = extract_failure_details(log, ["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"])
        assert len(results) == 2

        a = next(r for r in results if r["nodeid"] == "tests/test_foo.py::test_a")
        assert a["error_type"] == "AssertionError"
        assert a["message"] == "expected 2 but got 1"

        b = next(r for r in results if r["nodeid"] == "tests/test_foo.py::test_b")
        assert b["error_type"] == "ValueError"
        assert b["message"] == "bad value"

    def test_unparsed_traceback_yields_sentinel(self, tmp_path: Path):
        """When no traceback present (--tb=no), traceback_head is the sentinel."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            "FAILED tests/test_foo.py::test_bar - AssertionError: boom\n",
        )
        results = extract_failure_details(log, ["tests/test_foo.py::test_bar"])
        assert len(results) == 1
        assert results[0]["traceback_head"] == "<could not extract>"

    def test_traceback_extracted_when_present(self, tmp_path: Path):
        """When a traceback header is found, traceback_head is populated."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            textwrap.dedent("""\
                ___________________ tests/test_foo.py::test_bar ___________________
                tests/test_foo.py:10: in test_bar
                    assert 1 == 2
                E   assert 1 == 2
                FAILED tests/test_foo.py::test_bar - AssertionError: assert 1 == 2
            """),
        )
        results = extract_failure_details(log, ["tests/test_foo.py::test_bar"])
        assert len(results) == 1
        assert results[0]["error_type"] == "AssertionError"
        assert "assert 1 == 2" in results[0]["traceback_head"]
        assert results[0]["traceback_head"] != "<could not extract>"

    def test_nodeid_not_in_log_uses_full_sentinel(self, tmp_path: Path):
        """A nodeid not found anywhere gets all sentinel values."""
        log = _write_raw_log(tmp_path / "raw.log", "collected 1 item\n1 passed\n")
        results = extract_failure_details(log, ["tests/test_foo.py::test_missing"])
        assert len(results) == 1
        assert results[0]["nodeid"] == "tests/test_foo.py::test_missing"
        assert results[0]["error_type"] == "<unknown>"
        assert results[0]["message"] == "<unparsed>"
        assert results[0]["traceback_head"] == "<could not extract>"

    def test_never_drops_entries(self, tmp_path: Path):
        """Every input nodeid produces exactly one output entry."""
        nodeids = ["tests/a.py::test_1", "tests/b.py::test_2", "tests/c.py::test_3"]
        log = _write_raw_log(tmp_path / "raw.log", "")
        results = extract_failure_details(log, nodeids)
        assert len(results) == 3
        out_ids = {r["nodeid"] for r in results}
        assert out_ids == set(nodeids)

    def test_unreadable_log_uses_full_sentinel(self, tmp_path: Path):
        """An unreadable log path triggers the per-entry sentinel for all nodeids."""
        results = extract_failure_details(tmp_path / "nonexistent.log", ["tests/test_foo.py::test_x"])
        assert len(results) == 1
        assert results[0]["error_type"] == "<unknown>"
        assert results[0]["message"] == "<unparsed>"
        assert results[0]["traceback_head"] == "<could not extract>"

    def test_error_type_without_colon(self, tmp_path: Path):
        """When the FAILED line has no colon-separated error type, message gets the detail."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            "FAILED tests/test_foo.py::test_x - some message without colon structure\n",
        )
        results = extract_failure_details(log, ["tests/test_foo.py::test_x"])
        assert len(results) == 1
        assert results[0]["error_type"] == "<unknown>"
        assert results[0]["message"] == "some message without colon structure"


# ---------------------------------------------------------------------------
# _build_verification_delta_block
# ---------------------------------------------------------------------------


class TestBuildVerificationDeltaBlock:
    """Tests for ``_build_verification_delta_block``."""

    def test_absent_delta_yields_empty_string(self):
        """None delta → empty block."""
        result = _build_verification_delta_block(None, None)
        assert result == ""

    def test_non_dict_delta_yields_empty_string(self):
        """Non-dict delta → empty block."""
        result = _build_verification_delta_block("not-a-dict", None)
        assert result == ""

    def test_non_computable_delta_yields_empty_string(self):
        """Delta with computable=False → empty block."""
        delta = {"computable": False, "newly_failing": ["a"], "still_red": []}
        result = _build_verification_delta_block(delta, None)
        assert result == ""

    def test_empty_newly_failing_and_still_red_yields_empty_string(self):
        """No failures → empty block."""
        delta = {
            "computable": True,
            "newly_failing": [],
            "still_red": [],
        }
        result = _build_verification_delta_block(delta, None)
        assert result == ""

    def test_newly_failing_appear_with_details(self, tmp_path: Path):
        """Two newly_failing nodeids produce entries with error details."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            textwrap.dedent("""\
                FAILED tests/test_foo.py::test_a - AssertionError: boom
                FAILED tests/test_foo.py::test_b - ValueError: bad
            """),
        )
        delta = {
            "computable": True,
            "newly_failing": ["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"],
            "still_red": [],
        }
        block = _build_verification_delta_block(delta, str(log))
        assert "Mechanical post-execute verification" in block
        assert "Newly failing tests (2)" in block
        assert "tests/test_foo.py::test_a" in block
        assert "AssertionError: boom" in block
        assert "tests/test_foo.py::test_b" in block
        assert "ValueError: bad" in block

    def test_still_red_is_name_only(self):
        """still_red tests appear as comma-separated nodeids only."""
        delta = {
            "computable": True,
            "newly_failing": [],
            "still_red": [
                "tests/test_foo.py::test_old1",
                "tests/test_foo.py::test_old2",
                "tests/test_bar.py::test_old3",
            ],
        }
        block = _build_verification_delta_block(delta, None)
        assert "Mechanical post-execute verification" in block
        assert "do NOT fix" in block
        assert "test_old1" in block
        assert "test_old2" in block
        assert "test_old3" in block
        # still_red is name-only (comma-separated, not one-per-line)
        assert "Pre-existing failures" in block

    def test_still_red_truncated_at_20_names(self):
        """More than 20 still_red names are truncated with …[N more]."""
        still_red = [f"tests/test_{i}.py::test_fail" for i in range(50)]
        delta = {
            "computable": True,
            "newly_failing": [],
            "still_red": still_red,
        }
        block = _build_verification_delta_block(delta, None)
        assert "…[30 more]" in block, block

    def test_delta_block_capped_at_approx_5000_chars(self, tmp_path: Path):
        """A huge number of newly_failing tests is truncated."""
        many = [f"tests/test_{i}.py::test_long_failure_name_{i}" for i in range(500)]
        log = _write_raw_log(
            tmp_path / "raw.log",
            "\n".join(
                f"FAILED {nid} - AssertionError: failure message {i}"
                for i, nid in enumerate(many)
            ),
        )
        delta = {
            "computable": True,
            "newly_failing": many,
            "still_red": [],
        }
        block = _build_verification_delta_block(delta, str(log))
        assert len(block) < 5500  # within ~5000 + some slack
        assert "…[" in block  # truncation present

    def test_raw_log_path_never_exposed(self, tmp_path: Path):
        """The raw log path string is never present in the delta block."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            "FAILED tests/test_foo.py::test_a - AssertionError: boom\n",
        )
        delta = {
            "computable": True,
            "newly_failing": ["tests/test_foo.py::test_a"],
            "still_red": [],
        }
        block = _build_verification_delta_block(delta, str(log))
        assert str(log) not in block
        assert "raw_" not in block
        assert ".log" not in block

    def test_traceback_included_when_available(self, tmp_path: Path):
        """Traceback snippet appears when parseable from the raw log."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            textwrap.dedent("""\
                _________________ tests/test_foo.py::test_a _________________
                tests/test_foo.py:10: in test_a
                    assert False
                E   assert False
                FAILED tests/test_foo.py::test_a - AssertionError: assert False
            """),
        )
        delta = {
            "computable": True,
            "newly_failing": ["tests/test_foo.py::test_a"],
            "still_red": [],
        }
        block = _build_verification_delta_block(delta, str(log))
        assert "Traceback:" in block

    def test_unparsed_traceback_not_included(self, tmp_path: Path):
        """When traceback is <could not extract>, no Traceback: line appears."""
        log = _write_raw_log(
            tmp_path / "raw.log",
            "FAILED tests/test_foo.py::test_a - AssertionError: boom\n",
        )
        delta = {
            "computable": True,
            "newly_failing": ["tests/test_foo.py::test_a"],
            "still_red": [],
        }
        block = _build_verification_delta_block(delta, str(log))
        assert "Traceback:" not in block


# ---------------------------------------------------------------------------
# _revise_prompt integration
# ---------------------------------------------------------------------------


class TestRevisePromptDeltaIntegration:
    """Tests that the delta block appears (or doesn't) in the revise prompt."""

    def test_absent_verdict_yields_no_delta_block(self, tmp_path: Path):
        """When completion_verdict.json is absent, the revise prompt has no delta block."""
        plan_dir, state = _scaffold(tmp_path)
        prompt = _revise_prompt(state, plan_dir)
        assert "Mechanical post-execute verification" not in prompt

    def test_verdict_with_newly_failing_injects_delta_block(self, tmp_path: Path):
        """A verdict with newly_failing tests injects the labeled section."""
        plan_dir, state = _scaffold(tmp_path)
        _write_verdict(
            plan_dir,
            newly_failing=["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"],
            raw_log_path=str(
                _write_raw_log(
                    tmp_path / "ver_log.log",
                    "FAILED tests/test_foo.py::test_a - AssertionError: boom\n"
                    "FAILED tests/test_foo.py::test_b - ValueError: bad\n",
                )
            ),
        )
        prompt = _revise_prompt(state, plan_dir)
        assert "Mechanical post-execute verification" in prompt
        assert "fix these new regressions" in prompt
        assert "do NOT scope-creep into still_red" in prompt
        assert "tests/test_foo.py::test_a" in prompt
        assert "tests/test_foo.py::test_b" in prompt

    def test_verdict_with_still_red_injects_name_only(self, tmp_path: Path):
        """still_red tests appear as names only in the revise prompt."""
        plan_dir, state = _scaffold(tmp_path)
        _write_verdict(
            plan_dir,
            newly_failing=[],
            still_red=["tests/test_foo.py::test_old1", "tests/test_foo.py::test_old2"],
        )
        prompt = _revise_prompt(state, plan_dir)
        assert "Mechanical post-execute verification" in prompt
        assert "do NOT fix" in prompt
        assert "test_old1" in prompt
        assert "test_old2" in prompt

    def test_raw_log_path_never_exposed_in_prompt(self, tmp_path: Path):
        """Raw log path is never surfaced in the revise prompt text."""
        plan_dir, state = _scaffold(tmp_path)
        log_path = _write_raw_log(
            tmp_path / "raw_verification.log",
            "FAILED tests/test_foo.py::test_a - AssertionError: boom\n",
        )
        _write_verdict(
            plan_dir,
            newly_failing=["tests/test_foo.py::test_a"],
            raw_log_path=str(log_path),
        )
        prompt = _revise_prompt(state, plan_dir)
        assert str(log_path) not in prompt
        assert "raw_verification.log" not in prompt

    def test_non_computable_verdict_yields_no_delta_block(self, tmp_path: Path):
        """A verdict with computable=False produces no delta block."""
        plan_dir, state = _scaffold(tmp_path)
        _write_verdict(
            plan_dir,
            newly_failing=["tests/test_foo.py::test_a"],
            computable=False,
        )
        prompt = _revise_prompt(state, plan_dir)
        assert "Mechanical post-execute verification" not in prompt
