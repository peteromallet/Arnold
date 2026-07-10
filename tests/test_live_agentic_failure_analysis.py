from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.live_agentic_harness.failure_analysis import (
    analyze_failures,
    prepare_failure_analysis,
    recommendations_for_run,
)
from tests.live_agentic_harness.runner import main


def _scenario_summary(tmp_path: Path, scenario_id: str, *, ok: bool) -> dict:
    output_dir = tmp_path / "out" / "agentic" / "tag" / scenario_id
    output_dir.mkdir(parents=True)
    (output_dir / "response.json").write_text(json.dumps({"status": "failed"}), encoding="utf-8")
    return {
        "scenario_id": scenario_id,
        "status": "success" if ok else "failed",
        "output_dir": str(output_dir),
        "guard": {
            "live_agentic_success": ok,
            "assessment": {
                "passed": ok,
                "issues": [] if ok else [{"severity": "error", "detail": "expected graph change"}],
            },
        },
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
    }


def _write_run(tmp_path: Path) -> tuple[Path, Path]:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "passing.json").write_text(json.dumps({"id": "passing"}), encoding="utf-8")
    (scenarios_dir / "failing.json").write_text(
        json.dumps({"id": "failing", "user_task": "Make the graph do the thing"}),
        encoding="utf-8",
    )
    run_summary = {
        "tag": "tag",
        "scenario_count": 2,
        "passed": 1,
        "failed": 1,
        "scenarios": [
            _scenario_summary(tmp_path, "passing", ok=True),
            _scenario_summary(tmp_path, "failing", ok=False),
        ],
    }
    run_summary_path = tmp_path / "out" / "agentic" / "tag" / "run_summary.json"
    run_summary_path.parent.mkdir(parents=True, exist_ok=True)
    run_summary_path.write_text(json.dumps(run_summary), encoding="utf-8")
    return run_summary_path, scenarios_dir


def test_prepare_failure_analysis_writes_brief_index_and_meta(tmp_path: Path) -> None:
    run_summary_path, scenarios_dir = _write_run(tmp_path)

    index = prepare_failure_analysis(run_summary_path, scenarios_dir=scenarios_dir)

    assert index["failed_count"] == 1
    failure = index["failures"][0]
    assert failure["scenario_id"] == "failing"
    assert Path(failure["brief_path"]).exists()
    assert Path(failure["meta_path"]).exists()
    assert (run_summary_path.parent / "failure_analysis" / "index.json").exists()

    brief = Path(failure["brief_path"]).read_text(encoding="utf-8")
    assert "Make the graph do the thing" in brief
    assert "response.json" in brief


def test_analyze_failures_uses_runner_and_preserves_done_status(tmp_path: Path) -> None:
    run_summary_path, scenarios_dir = _write_run(tmp_path)

    def fake_runner(*args, **kwargs):  # noqa: ANN001, ANN202
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="diagnosis body", stderr="")

    index = analyze_failures(
        run_summary_path,
        scenarios_dir=scenarios_dir,
        max_workers=1,
        runner=fake_runner,
    )

    failure = index["failures"][0]
    meta = json.loads(Path(failure["meta_path"]).read_text(encoding="utf-8"))
    assert failure["status"] == "done"
    assert meta["status"] == "done"
    assert Path(failure["diagnosis_path"]).read_text(encoding="utf-8") == "diagnosis body"


def test_analyze_failures_resume_skips_done_and_retries_failed(tmp_path: Path) -> None:
    run_summary_path, scenarios_dir = _write_run(tmp_path)
    index = prepare_failure_analysis(run_summary_path, scenarios_dir=scenarios_dir)
    meta_path = Path(index["failures"][0]["meta_path"])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status"] = "done"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    calls = 0

    def fake_runner(*args, **kwargs):  # noqa: ANN001, ANN202
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="new diagnosis", stderr="")

    analyze_failures(run_summary_path, scenarios_dir=scenarios_dir, runner=fake_runner)

    assert calls == 0

    meta["status"] = "agent_failed"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    index = analyze_failures(run_summary_path, scenarios_dir=scenarios_dir, runner=fake_runner)

    assert calls == 1
    assert index["failures"][0]["status"] == "done"
    assert Path(index["failures"][0]["diagnosis_path"]).read_text(encoding="utf-8") == "new diagnosis"


def test_recommendations_for_run_passes_prompt_content_to_codex(tmp_path: Path) -> None:
    run_summary_path, scenarios_dir = _write_run(tmp_path)
    index = prepare_failure_analysis(run_summary_path, scenarios_dir=scenarios_dir)
    diagnosis_path = Path(index["failures"][0]["diagnosis_path"])
    diagnosis_path.write_text("diagnosed category: model_semantic_miss", encoding="utf-8")

    seen: dict[str, object] = {}

    def fake_runner(cmd, **kwargs):  # noqa: ANN001, ANN202
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="ranked recommendations", stderr="")

    meta = recommendations_for_run(run_summary_path, runner=fake_runner)

    cmd = seen["cmd"]
    assert isinstance(cmd, list)
    assert "Aggregate Live Agentic Failure Recommendations" in cmd[-1]
    assert 'model_reasoning_effort="xhigh"' in cmd
    assert "affected scenario ids" in cmd[-1]
    assert "Recommended Next Bet" in cmd[-1]
    assert "downside risk" in cmd[-1]
    assert "Per-Failure Primary Cause" in cmd[-1]
    assert "Architecture Impact" in cmd[-1]
    assert "every failed scenario must appear exactly once" in cmd[-1]
    assert meta["returncode"] == 0
    assert (run_summary_path.parent / "failure_analysis" / "recommendations.md").read_text(
        encoding="utf-8"
    ) == "ranked recommendations"


def test_runner_can_prepare_existing_summary(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    run_summary_path, scenarios_dir = _write_run(tmp_path)

    rc = main(
        [
            "--analyze-existing-summary",
            str(run_summary_path),
            "--scenarios-dir",
            str(scenarios_dir),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["failure_analysis"]["failed_count"] == 1
    assert Path(payload["failure_analysis"]["analysis_index_path"]).exists()
