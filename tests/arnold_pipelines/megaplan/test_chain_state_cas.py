from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest

from arnold_pipelines.megaplan.chain.spec import (
    ChainState,
    _state_path_for,
    load_chain_state,
    save_chain_state,
)
from arnold_pipelines.megaplan.types import CliError


def _chain(tmp_path: Path) -> Path:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n", encoding="utf-8")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n"
        "  north_star: brief.md\n"
        "milestones:\n"
        "  - label: CL1\n"
        "    idea: brief.md\n"
        "  - label: CL2\n"
        "    idea: brief.md\n",
        encoding="utf-8",
    )
    save_chain_state(
        spec,
        ChainState(
            current_milestone_index=0,
            current_plan_name="cl1-plan",
            last_state="running",
        ),
    )
    return spec


def test_stale_concurrent_writer_cannot_erase_advanced_cursor_or_completion(
    tmp_path: Path,
) -> None:
    spec = _chain(tmp_path)
    advanced = load_chain_state(spec)
    stale = load_chain_state(spec)
    advanced.current_milestone_index = 1
    advanced.current_plan_name = "cl2-plan"
    advanced.last_state = "blocked"
    advanced.completed = [
        {
            "label": "CL1",
            "plan": "cl1-plan",
            "status": "done",
        }
    ]

    writers_ready = Barrier(2)
    advanced_committed = Event()

    def commit_advanced() -> None:
        writers_ready.wait()
        save_chain_state(spec, advanced)
        advanced_committed.set()

    def commit_stale() -> str:
        writers_ready.wait()
        assert advanced_committed.wait(timeout=5)
        with pytest.raises(CliError) as caught:
            save_chain_state(spec, stale)
        return caught.value.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        advanced_future = pool.submit(commit_advanced)
        stale_future = pool.submit(commit_stale)
        advanced_future.result(timeout=5)
        assert stale_future.result(timeout=5) == "chain_state_stale_write"

    state_bytes = _state_path_for(spec).read_bytes()
    recovered = load_chain_state(spec)
    assert recovered.current_milestone_index == 1
    assert recovered.current_plan_name == "cl2-plan"
    assert recovered.completed == advanced.completed
    assert _state_path_for(spec).read_bytes() == state_bytes

    # Even a writer that bypassed the load-token CAS cannot regress durable
    # progress: the monotonic cursor/completed-set guard is independent.
    with pytest.raises(CliError) as caught:
        save_chain_state(
            spec,
            ChainState(
                current_milestone_index=0,
                current_plan_name="cl1-plan",
                last_state="done",
            ),
        )
    assert caught.value.code == "chain_state_regression"
    assert _state_path_for(spec).read_bytes() == state_bytes
