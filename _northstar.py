from arnold_pipelines.megaplan.run_state import (
    resolve_run_state, CanonicalState as S, TypedHumanGate, CanonicalRunState,
)
from arnold_pipelines.megaplan.run_state.classifiers import ORDERED_CLASSIFIERS

# North Star: all 9 states + first-match ordering + AWF018 typed gate + serialization.

# 1. All 9 canonical states reachable (contract coverage)
expected_states = {
    S.RUNNING, S.REPAIRING, S.RETRYABLE_EXECUTION_BLOCK, S.REAL_IMPLEMENTATION_BLOCK,
    S.HUMAN_ACTION_REQUIRED, S.COMPLETED, S.STALE_DERIVED_STATE, S.BROKEN_STATE_MACHINE,
    S.UNKNOWN,
}
probes = {
    S.RUNNING: {"tmux_process": {"live_status": "running"}},
    S.REPAIRING: {"repair_progress": {"status": "active", "runner_ref": "r"}},
    S.RETRYABLE_EXECUTION_BLOCK: {"tmux_process": {"live_status": "failed", "exit_code": 1}, "marker": {"session_id": "s"}},
    S.HUMAN_ACTION_REQUIRED: {"needs_human": [{"gate": "approval", "reason": "x"}]},
    S.COMPLETED: {"plan_state": {"status": "completed", "plan_name": "p"}, "current_refs": {"target_ref": "main"}},
    S.REAL_IMPLEMENTATION_BLOCK: {"chain_state": {"status": "blocked"}, "plan_state": {"status": "in_progress", "plan_name": "p"}},
    S.STALE_DERIVED_STATE: {"stale_evidence": [{"kind": "missing_plan_state"}], "marker": {"session_id": "s"}},
    S.BROKEN_STATE_MACHINE: {"rationale": ["BROKEN_STATE_MACHINE"]},
    S.UNKNOWN: {"tmux_process": {"live_status": "stopped"}},
}
got = {resolve_run_state(ev).canonical_state for ev in probes.values()}
assert got == expected_states, sorted(got ^ expected_states)

# 2. First-match ordering: higher-priority classifiers come first.
priority_order = [s for s in [
    # broken machine first, then live, then typed human gate, then blocks, repair, terminal, stale, unknown
]]
order_names = [n for n, _ in ORDERED_CLASSIFIERS]
assert "broken_state_machine" == order_names[0], order_names
assert "unknown" == order_names[-1], order_names
# live/active (running) must precede stale_derived_state
assert order_names.index("running") < order_names.index("stale_derived_state"), order_names
# human_action_required must precede completed (explicit gate beats stale completion label)
assert order_names.index("human_action_required") < order_names.index("completed"), order_names
# completed must precede stale_derived_state (authority completion beats stale markers)
assert order_names.index("completed") < order_names.index("stale_derived_state"), order_names

# 3. AWF018-style diagnostic code -> typed human gate mapping (verification/policy/user-action)
awf = {"needs_human": [{"gate": "verification", "reason": "AWF018"}], "marker": {"session_id": "s"}}
raw = resolve_run_state(awf)
assert raw.canonical_state == S.HUMAN_ACTION_REQUIRED
assert raw.human_gate == TypedHumanGate.VERIFICATION

# 4. Serialization round-trip preserves classifier output (stable contract for consumers)
d = raw.to_dict()
roundtrip = CanonicalRunState.from_dict(d)
assert roundtrip == raw, (roundtrip.to_dict(), raw.to_dict())

print("PASS _northstar")
