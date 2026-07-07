"""Smoke test for T10 (io batch artifact helpers) and T15 (semantic_health execute checks)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# T10: io batch artifact helpers
from arnold_pipelines.megaplan._core.io import (
    EXECUTE_BATCHES_DIRNAME,
    batch_artifact_index,
    execute_batch_artifact_path,
    execute_batch_dir,
    legacy_batch_artifact_path,
    list_batch_artifacts,
    resolve_batch_artifact,
    stable_task_id_digest,
)

print("=== T10: io batch artifact helpers ===")

# 1. stable_task_id_digest is order/duplicate insensitive
d1 = stable_task_id_digest(["T1", "T2", "T3"])
d2 = stable_task_id_digest(["T3", "T1", "T2"])
d3 = stable_task_id_digest(["T3", "T1", "T2", "T2"])
assert d1 == d2 == d3, f"digest not stable: {d1} {d2} {d3}"
assert len(d1) == 12, f"digest len {len(d1)}"
print(f"  stable_task_id_digest: OK (digest={d1})")

# 2. execute_batch_artifact_path uses S4 directory layout
p = execute_batch_artifact_path(Path("/plan"), 3, ["T1", "T2"])
expected = Path("/plan") / EXECUTE_BATCHES_DIRNAME / "batch_3" / f"tasks_{stable_task_id_digest(['T1','T2'])}.json"
assert p == expected, f"path mismatch: {p} != {expected}"
print(f"  execute_batch_artifact_path: OK ({p.relative_to('/plan')})")

# 3. legacy path is migration read-only
lp = legacy_batch_artifact_path(Path("/plan"), 5)
assert lp == Path("/plan/execution_batch_5.json"), f"legacy path: {lp}"
print(f"  legacy_batch_artifact_path: OK ({lp.name})")

# 4. batch_artifact_index handles both layouts
assert batch_artifact_index(execute_batch_artifact_path(Path("/p"), 2, ["T1"])) == 2
assert batch_artifact_index(legacy_batch_artifact_path(Path("/p"), 7)) == 7
assert batch_artifact_index(Path("/p/random.json")) is None
print("  batch_artifact_index: OK (S4 + legacy + non-artifact)")

# 5. End-to-end write + resolve + list with tmp dir
import tempfile
with tempfile.TemporaryDirectory() as td:
    plan_dir = Path(td)
    # Write S4 artifact for batch 1 and batch 3
    a1 = execute_batch_artifact_path(plan_dir, 1, ["T1", "T2"])
    a1.parent.mkdir(parents=True, exist_ok=True)
    a1.write_text(json.dumps({"tasks": ["T1", "T2"]}))
    a3 = execute_batch_artifact_path(plan_dir, 3, ["T5"])
    a3.parent.mkdir(parents=True, exist_ok=True)
    a3.write_text(json.dumps({"tasks": ["T5"]}))

    # resolve_batch_artifact finds the new S4 path
    r1 = resolve_batch_artifact(plan_dir, 1, ["T1", "T2"])
    assert r1 == a1, f"resolve batch 1: {r1}"
    r3 = resolve_batch_artifact(plan_dir, 3)
    assert r3 == a3, f"resolve batch 3 (no task_ids): {r3}"
    assert resolve_batch_artifact(plan_dir, 99) is None

    # list_batch_artifacts sorted by index
    listed = list_batch_artifacts(plan_dir)
    assert [batch_artifact_index(p) for p in listed] == [1, 3], f"listed: {listed}"
    print("  resolve_batch_artifact + list_batch_artifacts (S4): OK")

    # Legacy fallback: write a legacy artifact for index 5, must be readable
    legacy5 = legacy_batch_artifact_path(plan_dir, 5)
    legacy5.write_text(json.dumps({"tasks": ["T9"]}))
    r5 = resolve_batch_artifact(plan_dir, 5)
    assert r5 == legacy5, f"legacy resolve: {r5}"
    listed2 = list_batch_artifacts(plan_dir)
    indices = [batch_artifact_index(p) for p in listed2]
    assert indices == [1, 3, 5], f"listed with legacy: {indices}"
    print("  legacy migration read compatibility: OK")

    # When BOTH S4 and legacy exist for same index, S4 wins
    s4_5 = execute_batch_artifact_path(plan_dir, 5, ["T9"])
    s4_5.parent.mkdir(parents=True, exist_ok=True)
    s4_5.write_text(json.dumps({"tasks": ["T9"]}))
    r5b = resolve_batch_artifact(plan_dir, 5)
    assert r5b == s4_5, f"S4 should win over legacy: {r5b}"
    listed3 = list_batch_artifacts(plan_dir)
    for p in listed3:
        if batch_artifact_index(p) == 5:
            assert p == s4_5, f"list should prefer S4 for index 5: {p}"
    print("  S4 preferred over legacy for same index: OK")

print("\n=== T15: semantic_health execute checks ===")
from arnold_pipelines.megaplan.semantic_health import (
    _check_execute_aggregate_promotion,
    _check_execute_approval_authority,
    _check_execute_checkpoint,
    _check_execute_semantics,
    _check_execute_terminal_state,
    _EXECUTE_AGGREGATE_BOUNDARY_IDS,
    _EXECUTE_APPROVAL_BOUNDARY_IDS,
    _EXECUTE_CHECKPOINT_BOUNDARY_IDS,
    _EXECUTE_PHASE,
    _EXECUTE_TERMINAL_BOUNDARY_IDS,
    _EXECUTE_TERMINAL_STATES,
)
from arnold.workflow.boundary_evidence import FindingSeverity
from types import SimpleNamespace


def make_contract(bid: str):
    return SimpleNamespace(boundary_id=bid, phase=SimpleNamespace(value="execute"))


with tempfile.TemporaryDirectory() as td:
    plan_dir = Path(td)
    receipts_dir = plan_dir / "boundary_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Stale checkpoint: receipt references batch_index not on disk.
    # Write a batch artifact for index 1 so on_disk is non-empty, then a
    # receipt for the (missing) index 7.
    ckpt_bid = next(iter(_EXECUTE_CHECKPOINT_BOUNDARY_IDS))
    contract = make_contract(ckpt_bid)
    a_seed = execute_batch_artifact_path(plan_dir, 1, ["Tseed"])
    a_seed.parent.mkdir(parents=True, exist_ok=True)
    a_seed.write_text("{}")
    (receipts_dir / f"{ckpt_bid}.json").write_text(json.dumps({
        "boundary_id": ckpt_bid,
        "batch_index": 7,
    }))
    findings = _check_execute_checkpoint(plan_dir, contract)
    fids = [f.finding_id for f in findings]
    assert any("stale-checkpoint" in fid for fid in fids), f"expected stale-checkpoint: {fids}"
    print(f"  stale-checkpoint finding: OK ({fids})")

    # 2. Missing side-effect ref
    ckpt_bid2 = "execute_batch_checkpoint"
    (receipts_dir / f"{ckpt_bid2}.json").write_text(json.dumps({
        "boundary_id": ckpt_bid2,
        "batch_index": 1,
        "child_trace_path": "execute/missing_trace.json",
    }))
    findings2 = _check_execute_checkpoint(plan_dir, make_contract(ckpt_bid2))
    # Write batch 1 artifact so checkpoint isn't stale, isolate side-effect check
    a1 = execute_batch_artifact_path(plan_dir, 1, ["T1"])
    a1.parent.mkdir(parents=True, exist_ok=True)
    a1.write_text("{}")
    findings2 = _check_execute_checkpoint(plan_dir, make_contract(ckpt_bid2))
    fids2 = [f.finding_id for f in findings2]
    assert any("missing-side-effect-ref" in fid for fid in fids2), f"expected side-effect-ref: {fids2}"
    print(f"  missing-side-effect-ref finding: OK ({fids2})")

    # 3. Stale approval authority
    appr_bid = next(iter(_EXECUTE_APPROVAL_BOUNDARY_IDS))
    (receipts_dir / f"{appr_bid}.json").write_text(json.dumps({
        "boundary_id": appr_bid,
        "invocation_id": "inv-old",
    }))
    state = {"meta": {"current_invocation_id": "inv-new"}}
    findings3 = _check_execute_approval_authority(plan_dir, make_contract(appr_bid), state)
    fids3 = [f.finding_id for f in findings3]
    assert any("stale-approval-authority" in fid for fid in fids3), f"expected stale-approval: {fids3}"
    print(f"  stale-approval-authority finding: OK ({fids3})")

    # 4. Missing approval authority (receipt has no invocation_id)
    (receipts_dir / f"{appr_bid}.json").write_text(json.dumps({
        "boundary_id": appr_bid,
    }))
    findings4 = _check_execute_approval_authority(plan_dir, make_contract(appr_bid), state)
    fids4 = [f.finding_id for f in findings4]
    assert any("missing-approval-authority" in fid for fid in fids4), f"expected missing-approval: {fids4}"
    print(f"  missing-approval-authority finding: OK ({fids4})")

    # 5. Child output without reducer promotion
    agg_bid = next(iter(_EXECUTE_AGGREGATE_BOUNDARY_IDS))
    # batch artifacts exist (from step 2), but no promotion receipt
    if (receipts_dir / f"{agg_bid}.json").exists():
        (receipts_dir / f"{agg_bid}.json").unlink()
    findings5 = _check_execute_aggregate_promotion(plan_dir, make_contract(agg_bid))
    fids5 = [f.finding_id for f in findings5]
    assert any("child-output-without-promotion" in fid for fid in fids5), f"expected child-without-promotion: {fids5}"
    print(f"  child-output-without-promotion finding: OK ({fids5})")

    # 6. Reducer promotion without child evidence
    # Remove all batch artifacts, add promotion receipt
    import shutil
    shutil.rmtree(plan_dir / EXECUTE_BATCHES_DIRNAME, ignore_errors=True)
    (receipts_dir / f"{agg_bid}.json").write_text(json.dumps({
        "boundary_id": agg_bid,
        "reducer_promotion": True,
    }))
    findings6 = _check_execute_aggregate_promotion(plan_dir, make_contract(agg_bid))
    fids6 = [f.finding_id for f in findings6]
    assert any("promotion-without-child-evidence" in fid for fid in fids6), f"expected promotion-without-child: {fids6}"
    print(f"  promotion-without-child-evidence finding: OK ({fids6})")

    # 7. Terminal state check
    term_bid = next(iter(_EXECUTE_TERMINAL_BOUNDARY_IDS))
    findings7 = _check_execute_terminal_state(make_contract(term_bid), {"current_state": "planned"})
    fids7 = [f.finding_id for f in findings7]
    assert any("terminal-state" in fid for fid in fids7), f"expected terminal-state: {fids7}"
    # Clean terminal produces no finding
    findings7b = _check_execute_terminal_state(make_contract(term_bid), {"current_state": "done"})
    assert findings7b == [], f"clean terminal should be empty: {findings7b}"
    print(f"  terminal-state finding: OK (warn on bad, clean on done)")

    # 8. _check_execute_semantics is read-only (no files created)
    files_before = set(p for p in plan_dir.rglob("*"))
    _check_execute_semantics(plan_dir=plan_dir, contract=make_contract(ckpt_bid), state=state)
    files_after = set(p for p in plan_dir.rglob("*"))
    assert files_before == files_after, "semantic checks must be read-only"
    print("  read-only invariant: OK (no files created)")

    # 9. Non-execute phase returns no findings
    non_exec = SimpleNamespace(boundary_id="prep_to_plan", phase=SimpleNamespace(value="prep"))
    assert _check_execute_semantics(plan_dir=plan_dir, contract=non_exec, state=state) == []
    print("  non-execute phase produces no execute findings: OK")

print("\n=== ALL SMOKE TESTS PASSED ===")
