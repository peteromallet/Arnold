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

from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipelines.megaplan._core.state import write_plan_state
from arnold.pipelines.megaplan.pipeline_contracts import (
    LOGICAL_EXECUTE_PAYLOAD,
    consume_payload_result,
    register_production_planning_contracts,
)
from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep
from arnold.pipelines.megaplan._pipeline.types import StepContext


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


def _fake_execute_handler(root: Path, args: Namespace) -> Mapping[str, Any]:
    plan_dir = root / ".megaplan" / "plans" / args.plan
    execution_json = plan_dir / "execution.json"
    execution_json.write_text('{"status":"ok"}', encoding="utf-8")
    write_plan_state(
        plan_dir,
        mode="executor-key-merge",
        state={"current_state": "executed"},
        executor_owned_keys=["current_state"],
    )
    return {}


def _fake_execute_handler_with_untyped_artifacts(
    root: Path, args: Namespace,
) -> Mapping[str, Any]:
    plan_dir = root / ".megaplan" / "plans" / args.plan
    execution_json = plan_dir / "execution.json"
    review_json = plan_dir / "review.json"
    plan_v2 = plan_dir / "plan_v2.md"
    execution_json.write_text('{"status":"ok"}', encoding="utf-8")
    review_json.write_text('{"verdict":"pass"}', encoding="utf-8")
    plan_v2.write_text("# plan v2\n", encoding="utf-8")
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state["current_state"] = "executed"
    state["plan_versions"] = [
        {"version": 1, "file": "plan_v1.md"},
        {"version": 2, "file": "plan_v2.md"},
    ]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return {}


def test_inprocess_handler_attaches_contract_result_and_preserves_legacy_fields(
    tmp_path: Path,
) -> None:
    plan_name = "p2"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan_name, "current_state": "finalized"}),
        encoding="utf-8",
    )

    step = InProcessHandlerStep(
        name="execute",
        kind="produce",
        handler=_fake_execute_handler,
    )
    ctx = StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name},
        profile={"root": tmp_path, "project_dir": tmp_path},
        mode="test",
        inputs={},
    )

    result = step.run(ctx)

    assert result.outputs == {}
    assert result.state_patch == {"current_state": "executed"}
    assert result.next == "review"
    assert result.contract_result is not None
    registry = ContractSchemaRegistry(tmp_path / "registry")
    contracts = register_production_planning_contracts(registry)
    contract = contracts[LOGICAL_EXECUTE_PAYLOAD]
    payload, diagnostics = consume_payload_result(registry, contract, result.contract_result)
    assert diagnostics == ()
    assert payload is not None
    assert payload["logical_type"] == LOGICAL_EXECUTE_PAYLOAD
    assert payload["metadata"]["output_keys"] == ["execution.json"]
    assert payload["metadata"]["state_patch_keys"] == ["current_state"]
    assert [ref["name"] for ref in payload["artifact_refs"]] == ["execution.json"]


def test_inprocess_handler_strips_only_step_duplicate_loose_outputs_after_contract_capture(
    tmp_path: Path,
) -> None:
    plan_name = "p3"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan_v1.md").write_text("# plan v1\n", encoding="utf-8")
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": "finalized",
                "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
            }
        ),
        encoding="utf-8",
    )

    step = InProcessHandlerStep(
        name="execute",
        kind="produce",
        handler=_fake_execute_handler_with_untyped_artifacts,
    )
    ctx = StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name},
        profile={"root": tmp_path, "project_dir": tmp_path},
        mode="test",
        inputs={},
    )

    result = step.run(ctx)

    assert result.outputs == {
        "plan_version:plan_v2.md": plan_dir / "plan_v2.md",
        "review.json": plan_dir / "review.json",
    }
    registry = ContractSchemaRegistry(tmp_path / "registry-2")
    contracts = register_production_planning_contracts(registry)
    contract = contracts[LOGICAL_EXECUTE_PAYLOAD]
    payload, diagnostics = consume_payload_result(registry, contract, result.contract_result)
    assert diagnostics == ()
    assert payload is not None
    assert payload["metadata"]["output_keys"] == [
        "plan_version:plan_v2.md",
        "execution.json",
        "review.json",
    ]
    assert [ref["name"] for ref in payload["artifact_refs"]] == [
        "plan_version:plan_v2.md",
        "execution.json",
        "review.json",
    ]
