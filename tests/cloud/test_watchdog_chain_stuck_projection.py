from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.cloud.test_watchdog_wrappers import _run_chain_health, _write_chain_state, _write_plan


def test_chain_health_status_ignores_stale_blocked_chain_when_plan_is_nonterminal() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 1,
            "current_plan_name": "m1-demo-plan",
            "last_state": "blocked",
            "pr_state": "",
            "completed": [{"label": "m0"}],
        },
    )
    _write_plan(
        ws / ".megaplan" / "plans" / "m1-demo-plan",
        {
            "current_state": "critiqued",
            "active_step": None,
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] resuming existing plan m1-demo-plan for m1\n",
        encoding="utf-8",
    )

    first = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )
    second = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )

    assert first["CHAIN_HEALTH_STATUS"] == "ok"
    assert second["CHAIN_HEALTH_STATUS"] == "ok"
    artifact_path = second.get("CHAIN_HEALTH_ARTIFACT_PATH")
    if artifact_path:
        artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        assert artifact.get("issue_kind") != "chain_stuck_nonterminal"
