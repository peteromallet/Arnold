import json
from pathlib import Path

import auto_improve.compare as compare


def _write_watch_scores(results_root: Path, task_payloads: dict[str, dict]) -> None:
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root / "_watch_scores.json").write_text(
        json.dumps({"tasks": task_payloads}, indent=2) + "\n",
        encoding="utf-8",
    )


def test_compare_main_reports_regressions_and_improvements(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    base_dir = tmp_path / "results" / "auto-improve"
    _write_watch_scores(
        base_dir / "iteration-021",
        {
            "task-stable-pass": {"resolved": True},
            "task-stable-fail": {"resolved": False},
            "task-regression": {"resolved": True},
            "task-improvement": {"resolved": False},
        },
    )
    _write_watch_scores(
        base_dir / "iteration-022",
        {
            "task-stable-pass": {"resolved": True},
            "task-stable-fail": {"resolved": False},
            "task-regression": {"resolved": False},
            "task-improvement": {"resolved": True},
        },
    )
    monkeypatch.setattr(compare, "DEFAULT_RESULTS_BASE", base_dir)

    exit_code = compare.main(["iteration-021", "iteration-022"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "shared tasks : 4" in output
    assert "regressions  : 1" in output
    assert "improvements : 1" in output
    assert "task-regression: pass -> fail" in output
    assert "task-improvement: fail -> pass" in output
