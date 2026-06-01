"""T12: _state_meta round-trips transparently through InProcessHandlerStep.

The reserved key ``_state_meta`` (holding the CAS version map maintained by
``apply_delta``) is added to ``_validate_plan_state_for_persist``'s allow-list
and must survive a read/modify/write cycle driven by an InProcessHandlerStep
without being stripped or rejected.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

from megaplan._core.state import write_plan_state
from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep
from megaplan._pipeline.types import StepContext


def _fake_handler(root: Path, args: Namespace) -> Mapping[str, Any]:
    """Mutate state.json's current_state via the public write helper.

    Exercises the executor-key-merge branch (the same code path the real
    handlers use) so we observe the actual round-trip the validator allows.
    """
    plan_dir = root / ".megaplan" / "plans" / args.plan
    new_state = {"current_state": "planned"}
    write_plan_state(
        plan_dir,
        mode="executor-key-merge",
        state=new_state,
        executor_owned_keys=["current_state"],
    )
    return {}


def test_state_meta_roundtrips_through_inprocess_handler(tmp_path: Path) -> None:
    plan_name = "p1"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)

    # Seed state.json with a _state_meta block already on disk.
    seeded: dict[str, Any] = {
        "name": plan_name,
        "current_state": "initialized",
        "_state_meta": {"versions": {"current_state": 7, "other_key": 3}},
    }
    (plan_dir / "state.json").write_text(json.dumps(seeded))

    step = InProcessHandlerStep(
        name="plan", kind="produce", handler=_fake_handler,
    )
    ctx = StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name},
        profile={"root": tmp_path, "project_dir": tmp_path},
        mode="test",
        inputs={},
    )
    step.run(ctx)

    after = json.loads((plan_dir / "state.json").read_text())
    # The reserved key survives the write_plan_state cycle.
    assert "_state_meta" in after
    versions = after["_state_meta"].get("versions", {})
    # other_key was never touched; its version is preserved verbatim.
    assert versions.get("other_key") == 3
    # current_state was rewritten via executor-key-merge.
    assert after.get("current_state") == "planned"
