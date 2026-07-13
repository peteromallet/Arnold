from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WATCHDOG = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-watchdog"


def _session_terminal_status() -> str:
    text = WATCHDOG.read_text(encoding="utf-8")
    start = text.index("session_terminal_status() {")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _terminal_status_for_missing_spec(tmp_path: Path, state: dict[str, object]) -> str:
    workspace = tmp_path / "workspace"
    marker_dir = tmp_path / "markers"
    repair_dir = marker_dir / "repair-data"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    marker_dir.mkdir()
    repair_dir.mkdir()
    chain_dir.mkdir(parents=True)
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"chain-{digest}.json").write_text(json.dumps(state), encoding="utf-8")
    script = "\n\n".join(
        [
            _session_terminal_status(),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            (
                "session_terminal_status demo-session "
                f"{str(workspace)!r} {str(spec_path)!r} chain"
            ),
        ]
    )
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_missing_spec_does_not_promote_milestone_done_to_chain_complete(tmp_path: Path) -> None:
    status = _terminal_status_for_missing_spec(
        tmp_path,
        {
            "last_state": "done",
            "chain_complete": None,
            "current_milestone_index": 1,
            "current_plan_name": "",
            "completed": [{"label": "m1", "status": "done"}],
            "events": [],
        },
    )

    assert status == ""


def test_missing_spec_accepts_explicit_all_milestones_complete_event(tmp_path: Path) -> None:
    status = _terminal_status_for_missing_spec(
        tmp_path,
        {
            "last_state": "done",
            "current_plan_name": "",
            "events": [{"msg": "all milestones complete"}],
        },
    )

    assert status == "complete\tchain complete"
