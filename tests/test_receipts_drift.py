from __future__ import annotations

import subprocess
from pathlib import Path

from megaplan.execute.quality import _capture_git_status_snapshot
from megaplan.receipts.drift import collect_loc_by_file, compute_scope_drift


def test_scope_drift_none_when_diff_is_claimed() -> None:
    report = compute_scope_drift(
        files_claimed={"a.py"},
        files_in_diff={"a.py"},
        loc_by_file={"a.py": 3},
    )

    assert report.files_added == []
    assert report.files_missing == []
    assert report.severity == "none"


def test_scope_drift_benign_only_is_none() -> None:
    report = compute_scope_drift(
        files_claimed={"a.py"},
        files_in_diff={"a.py", ".megaplan/state.json"},
        loc_by_file={"a.py": 1, ".megaplan/state.json": 50},
    )

    assert report.files_added == []
    assert report.severity == "none"


def test_scope_drift_benign_missing_claims_are_none() -> None:
    report = compute_scope_drift(
        files_claimed={
            ".megaplan/plans/demo/execution_batch_1.json",
            ".megaplan/plans/demo/execution_batch_2.json",
            ".megaplan/plans/demo/execution_batch_3.json",
            ".megaplan/plans/demo/execution_batch_4.json",
        },
        files_in_diff=set(),
        loc_by_file={},
    )

    assert report.files_missing == []
    assert report.severity == "none"


def test_scope_drift_low_for_small_unclaimed_file() -> None:
    report = compute_scope_drift(
        files_claimed={"a.py"},
        files_in_diff={"a.py", "extra.py"},
        loc_by_file={"a.py": 1, "extra.py": 5},
    )

    assert report.files_added == ["extra.py"]
    assert report.loc_added_outside_claimed == 5
    assert report.severity == "low"


def test_scope_drift_high_for_unclaimed_tracked_modification() -> None:
    report = compute_scope_drift(
        files_claimed={"a.py"},
        files_in_diff={"a.py", "tracked_extra.py"},
        loc_by_file={"a.py": 1, "tracked_extra.py": 25},
    )

    assert report.files_added == ["tracked_extra.py"]
    assert report.loc_added_outside_claimed == 25
    assert report.severity == "high"


def test_collect_loc_by_file_counts_untracked_file_for_high_drift(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, check=True, stdout=subprocess.DEVNULL)
    (tmp_path / "b.py").write_text("".join(f"line {index}\n" for index in range(30)), encoding="utf-8")

    snapshot, error = _capture_git_status_snapshot(tmp_path)
    assert error is None
    assert set(snapshot) == {"b.py"}
    loc_by_file = collect_loc_by_file(tmp_path, set(snapshot))
    report = compute_scope_drift(
        files_claimed={"a.py"},
        files_in_diff=set(snapshot),
        loc_by_file=loc_by_file,
    )

    assert loc_by_file["b.py"] == 30
    assert report.loc_added_outside_claimed == 30
    assert report.severity == "high"
