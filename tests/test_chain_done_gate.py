from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.chain_done_gate import check_chain_done


def _write_chain(tmp_path: Path, *, mode: str = "enforce", backstop: str = "enforce") -> tuple[Path, Path, Path]:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        yaml.safe_dump({"milestones": [{"label": "m1", "idea": "m1.md"}]}),
        encoding="utf-8",
    )
    plans_root = tmp_path / ".megaplan" / "plans"
    plan_dir = plans_root / "plan-m1"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "plan-m1", "current_state": "done"}) + "\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "chain-state.json"
    state_path.write_text(
        json.dumps(
            {
                "completion_contract_mode": mode,
                "full_suite_backstop_mode": backstop,
                "completed": [{"label": "m1", "plan": "plan-m1", "status": "done"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return spec_path, state_path, plans_root


def test_chain_done_gate_passes_when_plan_state_and_modes_are_blocking(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(tmp_path)

    assert check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    ) == []


def test_chain_done_gate_fails_shadow_modes_and_non_done_plan_state(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(
        tmp_path, mode="shadow", backstop="shadow"
    )
    (plans_root / "plan-m1" / "state.json").write_text(
        json.dumps({"name": "plan-m1", "current_state": "planned"}) + "\n",
        encoding="utf-8",
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
    )

    assert any("completion_contract_mode" in error for error in errors)
    assert any("full_suite_backstop_mode" in error for error in errors)
    assert any("current_state='planned'" in error for error in errors)


def test_chain_done_gate_fails_open_review_blockers(tmp_path: Path) -> None:
    spec_path, state_path, plans_root = _write_chain(tmp_path)
    blockers_path = tmp_path / "blockers.json"
    blockers_path.write_text(
        json.dumps(
            {
                "blockers": [
                    {
                        "id": "b1",
                        "title": "dynamic import trap",
                        "source": "review.txt",
                        "status": "open",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    errors = check_chain_done(
        spec_path=spec_path,
        state_path=state_path,
        plans_root=plans_root,
        blockers_path=blockers_path,
    )

    assert any("unresolved blocker 'b1'" in error for error in errors)
