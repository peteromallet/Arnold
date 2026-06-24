from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan.auto import DriverOutcome
from arnold_pipelines.megaplan.chain import _drive_plan


def test_chain_drive_plan_opts_into_self_hosted_editable_for_engine_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "megaplan"
    root.mkdir()
    seen_provider: list[str | None] = []

    def fake_auto_drive(*_args, **_kwargs):
        seen_provider.append(os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER"))
        return DriverOutcome(
            status="done",
            plan="self-hosted-plan",
            final_state="done",
            iterations=1,
        )

    monkeypatch.delenv("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", raising=False)
    monkeypatch.setattr("arnold_pipelines.megaplan.chain.megaplan_engine_root", lambda: root.resolve())
    monkeypatch.setattr("arnold_pipelines.megaplan.chain.auto_drive", fake_auto_drive)

    outcome = _drive_plan(
        root,
        "self-hosted-plan",
        SimpleNamespace(
            stall_threshold=1,
            max_iterations=1,
            escalate_action="force-proceed",
            poll_sleep=0,
            phase_timeout=1,
            status_timeout=1,
        ),
        writer=lambda _message: None,
    )

    assert outcome.status == "done"
    assert seen_provider == ["self_hosted_editable"]
    assert os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER") is None
