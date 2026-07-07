from arnold_pipelines.megaplan.run_state import (
    resolve_run_state, CanonicalState as S, TypedHumanGate,
)

# A) Explicit human gate (typed) must beat stale terminal-completion label (HUMAN_ACTION_REQUIRED > COMPLETED).
ev = {
    "plan_state": {"status": "completed", "plan_name": "p"},          # stale completion label
    "current_refs": {"target_ref": "main"},
    "needs_human": [{"gate": "credential", "reason": "missing AWS key"}],  # explicit typed gate
}
r = resolve_run_state(ev)
assert r.canonical_state == S.HUMAN_ACTION_REQUIRED, r
assert r.human_gate == TypedHumanGate.CREDENTIAL_ACCOUNT, r
assert r.human_required is True

# B) Empty evidence -> conservative UNKNOWN (never None, never COMPLETED).
assert resolve_run_state({}).canonical_state == S.UNKNOWN
assert resolve_run_state(None).canonical_state == S.UNKNOWN

# C) Repair-data advisory stays advisory (REPAIRING), not escalated to a human gate, even with stale failed label.
ev2 = {
    "repair_progress": {"status": "active", "runner_ref": "r"},
    "tmux_process": {"live_status": "failed", "exit_code": 1},  # stale failed label
}
r2 = resolve_run_state(ev2)
assert r2.canonical_state == S.REPAIRING, r2
assert r2.human_required is False

# D) Chain log BROKEN_STATE_MACHINE present + no live/terminal/repair -> BROKEN_STATE_MACHINE, not UNKNOWN.
ev3 = {
    "marker": {"session_id": "s"},
    "chain_log": [{"event": "BROKEN_STATE_MACHINE", "ts": "t"}],
}
assert resolve_run_state(ev3).canonical_state == S.BROKEN_STATE_MACHINE

# E) authority completion beats stale failed label (COMPLETED, not RETRYABLE).
ev4 = {
    "plan_state": {"status": "completed", "plan_name": "p"},
    "current_refs": {"target_ref": "main", "head_oid": "deadbeef"},
    "marker": {"session_id": "s"},
    "tmux_process": {"live_status": "failed", "exit_code": 1},  # stale failed label
}
assert resolve_run_state(ev4).canonical_state == S.COMPLETED

# F) Mechanical blocker_verdict with NO human gate present -> still human (USER_ACTION), per SD3 boundary.
ev5 = {"tmux_process": {"live_status": "stopped"}}
r5 = resolve_run_state(ev5, blocker_verdict="MECHANICAL_BLOCKER")
assert r5.canonical_state == S.HUMAN_ACTION_REQUIRED and r5.human_gate == TypedHumanGate.USER_ACTION

print("PASS _edge")
