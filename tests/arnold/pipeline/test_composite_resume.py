from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from arnold.pipeline import (
    COMPOSITE_RESUME_CURSOR_FILENAME,
    persist_composite_resume_cursor,
    read_composite_resume_cursor,
)
from arnold.pipeline.native.checkpoint import classify_resume_cursor, read_native_cursor
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.native import compile_pipeline, decision, phase, pipeline, workflow
from arnold.pipelines.evidence_pack.pipeline import build_pipeline
from arnold.pipelines.evidence_pack.resume import resume_evidence_pack
from arnold.pipelines.evidence_pack.verifier import make_evidence_pack_payload
from arnold.pipeline.types import ContractResult, ContractStatus, StepResult, Suspension


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _failing_evidence_pack(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            },
        ],
    )


def test_evidence_pack_resume_interoperates_with_shared_composite_cursor(
    tmp_path: Path,
) -> None:
    pack_path = tmp_path / "input_pack.json"
    _write_json(pack_path, _failing_evidence_pack("pack-composite"))

    result = run_native_pipeline(
        build_pipeline().native_program,
        artifact_root=tmp_path,
        initial_state={"evidence_pack_path": str(pack_path)},
    )

    assert result.suspended is True
    assert classify_resume_cursor(tmp_path) == "native"
    native_cursor = read_native_cursor(tmp_path)
    assert native_cursor is not None

    persist_composite_resume_cursor(
        tmp_path,
        children={"human_review": {"cursor": native_cursor}},
        shared_awaitable="approval/pack-composite",
    )

    composite = read_composite_resume_cursor(tmp_path)
    assert composite["kind"] == "composite_suspension"
    assert composite["version"] == 1
    assert composite["shared_awaitable"] == "approval/pack-composite"
    assert composite["children"]["human_review"]["cursor"]["native"]["pc"] == native_cursor["native"]["pc"]
    assert (tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME).exists()

    resumed = resume_evidence_pack(
        tmp_path,
        envelope=result.envelope,
        human_input={"approved": True, "comment": "ship it"},
    )

    assert resumed.resumed is True
    assert (tmp_path / "attestation.json").exists()
    assert (tmp_path / COMPOSITE_RESUME_CURSOR_FILENAME).exists()


def test_evidence_pack_resume_module_has_no_continuation_builder() -> None:
    from arnold.pipelines.evidence_pack import resume as resume_module

    source = inspect.getsource(resume_module)
    assert "build_continuation_pipeline" not in source


def test_child_suspend_resume_does_not_duplicate_parent_or_child_side_effects(
    tmp_path: Path,
) -> None:
    calls = {"parent_before": 0, "child_prepare": 0, "child_wait": 0, "parent_after": 0}
    release_child = {"value": False}

    @phase
    def parent_before(ctx: dict) -> dict:
        calls["parent_before"] += 1
        return {"seed": "alpha"}

    @phase
    def child_prepare(ctx: dict) -> dict:
        calls["child_prepare"] += 1
        return {"prepared": ctx["state"]["seed"]}

    @phase
    def child_wait(ctx: dict) -> StepResult | dict[str, str]:
        calls["child_wait"] += 1
        if release_child["value"]:
            return {"child_value": f"done:{ctx['state']['prepared']}"}
        return StepResult(
            outputs={"child_wait_seen": calls["child_wait"]},
            contract_result=ContractResult(
                status=ContractStatus.SUSPENDED,
                suspension=Suspension(
                    kind="human",
                    resume_cursor=f"child-wait-{calls['child_wait']}",
                ),
            ),
        )

    @phase
    def parent_after(ctx: dict) -> dict:
        calls["parent_after"] += 1
        return {"final": ctx["state"]["merged_child"]}

    @workflow(
        name="child_flow",
        inputs={"type": "object", "required": ["seed"]},
        outputs={"type": "object", "required": ["child_value"]},
    )
    def child(ctx: dict) -> dict:
        state = yield child_prepare(ctx)
        state = yield child_wait(ctx)
        return state

    @pipeline
    def parent(ctx: dict) -> dict:
        state = yield parent_before(ctx)
        state = yield child(ctx, id="child_call", outputs={"child_value": "merged_child"})
        state = yield parent_after(ctx)
        return state

    program = compile_pipeline(parent)

    first = run_native_pipeline(program, artifact_root=tmp_path)
    assert first.suspended is True
    assert calls == {
        "parent_before": 1,
        "child_prepare": 1,
        "child_wait": 1,
        "parent_after": 0,
    }

    cursor = read_native_cursor(tmp_path)
    assert cursor is not None
    assert cursor["native_cursor_kind"] == "composite_parent_child"
    assert cursor["native"]["suspension_kind"] == "child_suspended"
    assert cursor["composite"]["parent"]["pc"] == 1
    assert cursor["composite"]["child"]["cursor_path"] == "_child_child_call/resume_cursor.json"
    assert (tmp_path / cursor["composite"]["child"]["cursor_path"]).exists()

    second = run_native_pipeline(program, artifact_root=tmp_path, resume=True)
    assert second.suspended is True
    assert calls == {
        "parent_before": 1,
        "child_prepare": 1,
        "child_wait": 2,
        "parent_after": 0,
    }

    release_child["value"] = True
    final = run_native_pipeline(program, artifact_root=tmp_path, resume=True)

    assert final.suspended is False
    assert final.state["final"] == "done:alpha"
    assert calls == {
        "parent_before": 1,
        "child_prepare": 1,
        "child_wait": 3,
        "parent_after": 1,
    }


def test_loop_inside_repeated_child_call_sites_restores_iteration_paths(
    tmp_path: Path,
) -> None:
    seen_paths: list[str] = []
    counts_by_call_site: dict[str, int] = {}

    @phase
    def body(ctx: dict) -> dict:
        call_site = ctx["call_site_path"][0]
        counts_by_call_site[call_site] = counts_by_call_site.get(call_site, 0) + 1
        seen_paths.append(ctx["run_path"])
        return {"count": counts_by_call_site[call_site]}

    @decision(name="critique_loop", vocabulary={"again", "done"})
    def guard(ctx: dict) -> str:
        call_site = ctx["call_site_path"][0]
        return "again" if counts_by_call_site.get(call_site, 0) < 2 else "done"

    @workflow(name="child_flow", outputs={"type": "object", "required": ["count"]})
    def child(ctx: dict) -> dict:
        state: dict = {}
        while guard(ctx) == "again":
            state = yield body(ctx)
        return state

    @pipeline
    def parent(ctx: dict) -> dict:
        state = yield child(ctx, id="child_a", outputs={"count": "a_count"})
        state = yield child(ctx, id="child_b", outputs={"count": "b_count"})
        return state

    result = run_native_pipeline(compile_pipeline(parent), artifact_root=tmp_path)

    assert result.state["a_count"] == 2
    assert result.state["b_count"] == 2
    assert seen_paths == [
        "root/child_a/critique_loop[1]",
        "root/child_a/critique_loop[2]",
        "root/child_b/critique_loop[1]",
        "root/child_b/critique_loop[2]",
    ]


def test_depth_three_nested_child_resume_preserves_cursor_chain(
    tmp_path: Path,
) -> None:
    calls = {"leaf_wait": 0}
    release_leaf = {"value": False}

    @phase
    def leaf_wait(ctx: dict) -> StepResult | dict[str, str]:
        calls["leaf_wait"] += 1
        if release_leaf["value"]:
            return {"leaf": "ok"}
        return StepResult(
            outputs={},
            contract_result=ContractResult(
                status=ContractStatus.SUSPENDED,
                suspension=Suspension(kind="human", resume_cursor="leaf-review"),
            ),
        )

    @workflow(name="leaf_flow", outputs={"type": "object", "required": ["leaf"]})
    def leaf(ctx: dict) -> dict:
        state = yield leaf_wait(ctx)
        return state

    @workflow(name="middle_flow", outputs={"type": "object", "required": ["middle"]})
    def middle(ctx: dict) -> dict:
        state = yield leaf(ctx, id="leaf_call", outputs={"leaf": "middle"})
        return state

    @pipeline
    def parent(ctx: dict) -> dict:
        state = yield middle(ctx, id="middle_call", outputs={"middle": "result"})
        return state

    program = compile_pipeline(parent)
    first = run_native_pipeline(program, artifact_root=tmp_path)

    assert first.suspended is True
    parent_cursor = read_native_cursor(tmp_path)
    assert parent_cursor is not None
    child_cursor_path = tmp_path / parent_cursor["composite"]["child"]["cursor_path"]
    child_cursor = json.loads(child_cursor_path.read_text(encoding="utf-8"))
    assert parent_cursor["composite"]["child"]["run_path"] == "root/middle_call"
    assert child_cursor["run_path"] == "root/middle_call/leaf_call"
    assert child_cursor["step_path"] == "root/middle_call/leaf_call/leaf_wait"

    release_leaf["value"] = True
    resumed = run_native_pipeline(program, artifact_root=tmp_path, resume=True)

    assert resumed.suspended is False
    assert resumed.state["result"] == "ok"
    assert calls["leaf_wait"] == 2
