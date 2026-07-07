from arnold_pipelines.megaplan.run_state import (
    resolve_run_state, CanonicalState as S, CanonicalRunState, TypedHumanGate,
)
from arnold_pipelines.megaplan.run_state.classifiers import (
    ORDERED_CLASSIFIERS, ResolverContext, normalize_evidence, classify_unknown,
)

# 1. ordered names unique + UNKNOWN last + all 9 canonical states covered
names = [c[0] for c in ORDERED_CLASSIFIERS]
assert names[-1] == "unknown", names
assert len(names) == len(set(names)), names
outcomes = {s.value for s in S}

# confirm all 9 outcomes are produced by the resolver across crafted evidences
probes = {
    S.RUNNING: {"tmux_process": {"live_status": "running"}},
    S.REPAIRING: {"repair_progress": {"status": "active", "runner_ref": "r"}},
    S.COMPLETED: {"plan_state": {"status": "completed", "plan_name": "p"}, "current_refs": {"target_ref": "main"}},
    S.RETRYABLE_EXECUTION_BLOCK: {"tmux_process": {"live_status": "failed", "exit_code": 1}, "marker": {"session_id": "s"}},
    S.HUMAN_ACTION_REQUIRED: {"needs_human": [{"gate": "approval", "reason": "need signoff"}]},
    S.REAL_IMPLEMENTATION_BLOCK: {"chain_state": {"status": "blocked"}, "plan_state": {"status": "in_progress", "plan_name": "p"}},
    S.STALE_DERIVED_STATE: {"stale_evidence": [{"kind": "missing_plan_state"}], "marker": {"session_id": "s"}},
    S.BROKEN_STATE_MACHINE: {"rationale": ["awf018 detected", "BROKEN_STATE_MACHINE"]},
    S.UNKNOWN: {"tmux_process": {"live_status": "stopped"}},
}
produced = set()
for expected, ev in probes.items():
    got = resolve_run_state(ev).canonical_state
    assert got == expected, (expected, got, ev)
    produced.add(got)
assert produced == outcomes, (sorted(produced ^ outcomes))

# classify_unknown always returns UNKNOWN regardless of context
assert classify_unknown(ResolverContext(normalize_evidence({}))).canonical_state == S.UNKNOWN

# 2. live beats stale: completed labels but live running process -> RUNNING
stale_live = dict(probes[S.COMPLETED]); stale_live["tmux_process"] = {"live_status": "running"}
stale_live["stale_evidence"] = [{"kind": "missing_plan_state"}]
assert resolve_run_state(stale_live).canonical_state == S.RUNNING

# 3. empty/unknown fallback
assert resolve_run_state({"tmux_process": {"live_status": "stopped"}}).canonical_state == S.UNKNOWN

# 4. blocker_verdict MECHANICAL -> HUMAN_ACTION_REQUIRED (USER_ACTION)
r4 = resolve_run_state(probes[S.COMPLETED], blocker_verdict="MECHANICAL_BLOCKER")
assert r4.canonical_state == S.HUMAN_ACTION_REQUIRED and r4.human_required and r4.human_gate == TypedHumanGate.USER_ACTION

print("PASS _verify")
