"""Throwaway e2e verification for resolution contract. Will be deleted after run."""
import json, os, tempfile
from pathlib import Path
from megaplan.resolutions import (
    upsert_user_action_resolution,
    load_user_action_resolutions,
    save_user_action_resolutions,
    FALLBACK_STATES,
    HARD_BLOCK_STATES,
    SUPPORTED_USER_ACTION_RESOLUTION_STATES,
    resolution_applies_to_task,
    resolution_recommended_action,
)

# 1. Create temp plan dir with finalize.json
plan_dir = Path(tempfile.mkdtemp())
finalize = {
    "tasks": [
        {"id": "T1", "description": "Do thing", "status": "pending", "depends_on": []},
        {"id": "T2", "description": "Other thing", "status": "pending", "depends_on": ["T1"]},
    ],
    "user_actions": [
        {
            "id": "U1",
            "description": "Approve deployment",
            "phase": "before_execute",
            "blocks_task_ids": ["T1"],
        }
    ],
}
with open(plan_dir / "finalize.json", "w") as f:
    json.dump(finalize, f)

# 2. Upsert resolution
res = upsert_user_action_resolution(
    plan_dir, "U1", state="accepted_blocked",
    reason="Deployment approved manually",
    fallback_mode="skip_deploy_check",
    instructions="Proceed without deployment verification",
)
assert res["U1"]["state"] == "accepted_blocked"
assert "created_at" in res["U1"]
assert res["U1"]["reason"] == "Deployment approved manually"
print("PASS: upsert creates resolution with all fields")

# 3. Load and verify persistence
loaded = load_user_action_resolutions(plan_dir)
assert "U1" in loaded
assert loaded["U1"]["state"] == "accepted_blocked"
print("PASS: load returns persisted resolution")

# 4. Verify upsert preserves created_at
first_ts = res["U1"]["created_at"]
res2 = upsert_user_action_resolution(plan_dir, "U1", state="waived", reason="Changed mind")
assert res2["U1"]["created_at"] == first_ts
assert res2["U1"]["state"] == "waived"
print("PASS: upsert preserves created_at on update")

# 5. Verify helpers
assert resolution_applies_to_task(res["U1"], "T1") is True  # U1 blocks T1
assert resolution_applies_to_task(res["U1"], "T2") is True  # no scoping = applies to all
rec = resolution_recommended_action(res["U1"])
assert rec == "continue_with_fallback"
print("PASS: helper functions work correctly")

# 6. Verify state constants
assert SUPPORTED_USER_ACTION_RESOLUTION_STATES == frozenset({"satisfied", "accepted_blocked", "waived", "manual_required", "rejected"})
assert FALLBACK_STATES == frozenset({"accepted_blocked", "waived"})
assert "manual_required" in HARD_BLOCK_STATES
assert "rejected" in HARD_BLOCK_STATES
print("PASS: state constants are correct")

# 7. Verify CLI handler registered
from megaplan.cli import COMMAND_HANDLERS
assert "user-action" in COMMAND_HANDLERS
print("PASS: user-action registered in COMMAND_HANDLERS")

# 8. Verify _compute_user_action_blockers works
from megaplan.cli import _compute_user_action_blockers
tasks_copy = [dict(t) for t in finalize["tasks"]]
blockers = _compute_user_action_blockers(plan_dir, finalize, tasks_copy)
assert "blocked_tasks_detail" in blockers
assert "user_action_resolution_summary" in blockers
assert "recommended_action" in blockers
# With accepted_blocked, recommended_action should be continue_with_fallback
assert blockers["recommended_action"] == "continue_with_fallback"
print("PASS: _compute_user_action_blockers returns expected structure for fallback")

# 9. Test without resolution (unresolved)
(plan_dir / "user_action_resolutions.json").unlink()
blockers_no_res = _compute_user_action_blockers(plan_dir, finalize, tasks_copy)
assert blockers_no_res["recommended_action"] == "awaiting_human"
print("PASS: unresolved blockers give awaiting_human")

# 10. Test finalize pre-gate task is resolution-aware
from megaplan.handlers.finalize import _ensure_user_actions_pre_gate_task
import copy
finalize_copy = copy.deepcopy(finalize)
state_mock = {"config": {"mode": "code"}, "plan_dir": plan_dir, "current_state": "gated"}
_ensure_user_actions_pre_gate_task(finalize_copy, state_mock)
# Find the gate task
gate_task = None
for t in finalize_copy.get("tasks", []):
    if isinstance(t, dict) and t.get("id", "").startswith("GATE"):
        gate_task = t
        break
assert gate_task is not None, "Gate task should be injected"
assert "user_action_resolutions.json" in gate_task.get("description", ""), "Gate task should mention resolutions"
print("PASS: finalize gate task is resolution-aware")

print("\n=== ALL 10 E2E CHECKS PASSED ===")
