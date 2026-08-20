from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _watchdog_wrapper() -> str:
    return (WRAPPER_DIR / "arnold-watchdog").read_text(encoding="utf-8")


def _extract_wrapper_function(name: str) -> str:
    text = _watchdog_wrapper()
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _run_watchdog_shell(script: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    for name in (
        "DISCORD_BOT_TOKEN",
        "DISCORD_DM_USER_ID",
        "DISCORD_WEBHOOK_URL",
        "REPORT_WEBHOOK",
        "SLACK_WEBHOOK_URL",
    ):
        env.pop(name, None)
    env["DISCORD_DM_BIN"] = "/bin/false"
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _write_plan(plan_dir: Path, state: dict[str, object]) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_chain_state(state_path: Path, state: dict[str, object]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding="utf-8")


def test_watchdog_terminal_plan_does_not_complete_chain_when_health_snapshot_says_incomplete(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "  - label: m2\n",
        encoding="utf-8",
    )
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": "demo-plan",
            "current_milestone_index": 1,
            "last_state": "authority_divergence",
            "completed": [{"label": "m1", "status": "done"}],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {"name": "demo-plan", "current_state": "done"},
    )
    (marker_dir / "demo-session.chain-health.progress.json").write_text(
        json.dumps(
            {
                "status": "chain_inconsistent_done",
                "snapshot": {
                    "chain_complete": False,
                    "completed_count": 1,
                    "milestone_count": 2,
                    "pr_state": "open",
                },
            }
        ),
        encoding="utf-8",
    )
    current_target = {
        "plan_state": {"current_state": "done"},
        "stale_evidence": [{"kind": "stale_chain_state_after_terminal_plan"}],
    }
    script = "\n\n".join(
        [
            _extract_wrapper_function("session_terminal_status"),
            f"MARKER_DIR={str(marker_dir)!r}",
            (
                "session_terminal_status demo-session "
                f"{str(workspace)!r} {str(spec_path)!r} chain "
                f"{shlex.quote(json.dumps(current_target))} {str(marker_dir)!r}"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_watchdog_terminal_plan_ignores_terminal_index_without_completed_milestones(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "  - label: m2\n",
        encoding="utf-8",
    )
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        {
            "current_plan_name": "demo-plan",
            "current_milestone_index": 2,
            "last_state": "done",
            "completed": [{"label": "m1", "status": "done"}],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {"name": "demo-plan", "current_state": "done"},
    )
    current_target = {
        "plan_state": {"current_state": "done"},
        "stale_evidence": [{"kind": "stale_chain_state_after_terminal_plan"}],
    }
    script = "\n\n".join(
        [
            _extract_wrapper_function("session_terminal_status"),
            f"MARKER_DIR={str(marker_dir)!r}",
            (
                "session_terminal_status demo-session "
                f"{str(workspace)!r} {str(spec_path)!r} chain "
                f"{shlex.quote(json.dumps(current_target))} {str(marker_dir)!r}"
            ),
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
