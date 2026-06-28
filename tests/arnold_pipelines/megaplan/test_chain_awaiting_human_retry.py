from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan.auto import DriverOutcome
from arnold_pipelines.megaplan.chain import _handle_outcome
from arnold_pipelines.megaplan.chain.spec import ChainState


def test_handle_outcome_retries_stale_awaiting_human_with_satisfied_resolutions(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "stale-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        (
            '{"name":"stale-plan","current_state":"awaiting_human","meta":{},'
            '"resume_cursor":{"phase":"execute"}}'
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        '{"user_actions":[{"id":"ua-1","phase":"before_execute"}]}',
        encoding="utf-8",
    )
    (plan_dir / "user_action_resolutions.json").write_text(
        '{"ua-1":{"action_id":"ua-1","state":"satisfied","created_at":"2026-06-28T00:00:00Z","created_by":"test"}}',
        encoding="utf-8",
    )

    spec = SimpleNamespace(
        on_failure_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        on_escalate_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        robustness="standard",
    )
    milestone = SimpleNamespace(label="m7", profile=None, robustness=None)
    state = ChainState()

    decision = _handle_outcome(
        DriverOutcome(
            status="awaiting_human",
            plan="stale-plan",
            final_state="awaiting_human",
            iterations=1,
            reason="stale blocked gate",
        ),
        spec=spec,
        writer=lambda _message: None,
        milestone=milestone,
        state=state,
        root=tmp_path,
    )

    assert decision == "retry"
    assert state.retry_counts == {"m7": 1}
