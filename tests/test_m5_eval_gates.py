from __future__ import annotations

from pathlib import Path

from megaplan.chain.m5_eval_gates import (
    assert_m5_eval_gates_before_calibration,
    check_better_join_is_pure,
    check_calibration_guard_targets,
    check_no_bare_float_judgments,
    check_no_second_eval_journals,
    replay_oracle_corpus_marker,
    run_m5_eval_gates,
)


def _write(root: Path, rel_path: str, source: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_m5_eval_gate_passes_current_repo() -> None:
    result = run_m5_eval_gates()

    assert result.passed, "\n".join(
        f"{finding.path}:{finding.line}: {finding.code}: {finding.detail}"
        for finding in result.findings
    )


def test_m5_eval_gate_rejects_bare_float_judgment_in_new_eval_module(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from megaplan._pipeline.types import PipelineVerdict

def run():
    return PipelineVerdict(score=0.72)
""",
    )

    findings = check_no_bare_float_judgments(tmp_path, paths=[rel_path])

    assert [finding.code for finding in findings] == [
        "M5_EVAL_BARE_FLOAT_JUDGMENT"
    ]


def test_m5_eval_gate_allows_old_path_bare_float_surface(tmp_path):
    rel_path = "megaplan/_pipeline/demo_judges.py"
    _write(
        tmp_path,
        rel_path,
        """
from megaplan._pipeline.types import PipelineVerdict

def run():
    return PipelineVerdict(score=0.72)
""",
    )

    assert check_no_bare_float_judgments(tmp_path, paths=[rel_path]) == ()


def test_m5_eval_gate_allows_evaluand_record_score_literals(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from megaplan.observability import EvaluandRecord

def run():
    return EvaluandRecord(
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash",
        score=0.72,
        piece_version="piece-v1",
    )
""",
    )

    assert check_no_bare_float_judgments(tmp_path, paths=[rel_path]) == ()


def test_m5_eval_gate_rejects_second_eval_specific_journal(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from pathlib import Path

def write(plan_dir):
    (Path(plan_dir) / "evaluand.ndjson").write_text("{}\\n")
""",
    )

    findings = check_no_second_eval_journals(tmp_path, paths=[rel_path])

    assert [finding.code for finding in findings] == ["M5_EVAL_SECOND_JOURNAL"]


def test_m5_eval_gate_allows_events_ndjson_path(tmp_path):
    rel_path = "megaplan/_pipeline/new_eval_judge.py"
    _write(
        tmp_path,
        rel_path,
        """
from pathlib import Path

def write(plan_dir):
    return Path(plan_dir) / "events.ndjson"
""",
    )

    assert check_no_second_eval_journals(tmp_path, paths=[rel_path]) == ()


def test_m5_eval_gate_rejects_better_cost_import_judge_call_and_vendor_heuristic(
    tmp_path,
):
    rel_path = "megaplan/observability/evaluand.py"
    _write(
        tmp_path,
        rel_path,
        """
def better(*, plan_dir, judge):
    from megaplan.observability.cost import _classify_vendor

    vendor = _classify_vendor("claude-opus")
    return judge(plan_dir, vendor)
""",
    )

    findings = check_better_join_is_pure(tmp_path, rel_path=rel_path)
    codes = {finding.code for finding in findings}

    assert "M5_EVAL_BETTER_COST_IMPORT" in codes
    assert "M5_EVAL_BETTER_LIVE_JUDGE_CALL" in codes
    assert "M5_EVAL_BETTER_VENDOR_HEURISTIC" in codes


def test_replay_oracle_corpus_marker_matches_guarded_fixture() -> None:
    assert replay_oracle_corpus_marker() == 4


def test_calibration_guard_passes_current_repo() -> None:
    assert_m5_eval_gates_before_calibration()


def test_calibration_guard_rejects_guarded_target_without_markers(tmp_path) -> None:
    rel_path = "megaplan/observability/cost.py"
    _write(
        tmp_path,
        rel_path,
        """
from megaplan.observability import better

def route(plan_dir):
    return better("a", "b", plan_dir=plan_dir, judge_version="j", rubric_version="r", input_set_hash="i")
""",
    )
    _write(
        tmp_path,
        "megaplan/observability/evaluand.py",
        """
def better(*, plan_dir, judge_version, rubric_version, input_set_hash):
    return plan_dir, judge_version, rubric_version, input_set_hash
""",
    )
    _write(
        tmp_path,
        "megaplan/_pipeline/eval_judge_wrapper.py",
        """
from megaplan._pipeline.types import PipelineVerdict

def run():
    return PipelineVerdict(score=0.72)
""",
    )

    findings = check_calibration_guard_targets(tmp_path)
    codes = {finding.code for finding in findings}

    assert "M5_EVAL_CALIBRATION_GUARD_GREP_GATE" in codes
    assert "M5_EVAL_CALIBRATION_GUARD_REPLAY_MARKER" in codes


def test_calibration_guard_allows_guarded_target_once_gate_and_marker_exist(
    tmp_path,
) -> None:
    _write(
        tmp_path,
        "megaplan/observability/cost.py",
        """
from megaplan.observability import better

def route(plan_dir):
    return better("a", "b", plan_dir=plan_dir, judge_version="j", rubric_version="r", input_set_hash="i")
""",
    )
    _write(
        tmp_path,
        "megaplan/observability/evaluand.py",
        """
def better(*, plan_dir, judge_version, rubric_version, input_set_hash):
    return {
        "plan_dir": plan_dir,
        "judge_version": judge_version,
        "rubric_version": rubric_version,
        "input_set_hash": input_set_hash,
    }
""",
    )
    _write(
        tmp_path,
        "tests/oracles/test_evaluand_replay_oracle.py",
        """
REPLAY_ORACLE_CORPUS_SIZE = 4
""",
    )

    assert check_calibration_guard_targets(tmp_path) == ()
    assert_m5_eval_gates_before_calibration(tmp_path)
