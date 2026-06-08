import json
from pathlib import Path

from arnold.pipelines.megaplan.bakeoff.state import (
    BAKEOFF_SCHEMA_VERSION,
    load_bakeoff_state,
    save_bakeoff_state,
    worktree_root,
)


def test_bakeoff_state_round_trip_atomic_and_schema_pinned(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    state = {
        "schema_version": BAKEOFF_SCHEMA_VERSION,
        "experiment_id": "exp-1",
        "base_sha": "abc123",
        "idea_hash": "hash",
        "idea_path": str(root / "idea.md"),
        "mode": "code",
        "profiles": [
            {
                "name": "apex",
                "worktree": str(worktree_root(root, "exp-1") / "apex"),
                "plan_id": "exp-1",
                "pid": None,
                "launched_at": None,
                "terminated_at": None,
                "outcome": None,
                "log_path": str(root / ".megaplan" / "bakeoffs" / "exp-1" / "apex" / "auto.log"),
                "outcome_path": str(root / ".megaplan" / "bakeoffs" / "exp-1" / "apex" / "outcome.json"),
            }
        ],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }

    save_bakeoff_state(root, state)

    path = root / ".megaplan" / "bakeoffs" / "exp-1" / "bakeoff.json"
    assert path.exists()
    assert load_bakeoff_state(root, "exp-1") == state
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert not list(path.parent.glob("*.tmp"))

