from arnold_pipelines.megaplan.run_state import resolve_run_state, CanonicalState as S, TypedHumanGate

probes = {
    "RUNNING": {"tmux_process": {"live_status": "running"}},
    "REPAIRING": {"repair_progress": {"status": "active", "runner_ref": "r"}},
    "COMPLETED(done)": {"plan_state": {"status": "done", "plan_name": "p"}, "current_refs": {"target_ref": "main"}},
    "COMPLETED(completed)": {"plan_state": {"status": "completed", "plan_name": "p"}, "current_refs": {"target_ref": "main"}},
    "RETRYABLE": {"tmux_process": {"live_status": "failed", "exit_code": 1}, "marker": {"session_id": "s"}},
    "HUMAN(approval)": {"needs_human": [{"gate": "approval", "reason": "need signoff"}]},
    "HUMAN(credential)": {"needs_human": [{"gate": "credential", "reason": "missing AWS key"}]},
    "REAL_IMPL": {"chain_state": {"status": "blocked"}, "plan_state": {"status": "in_progress", "plan_name": "p"}},
    "STALE": {"stale_evidence": [{"kind": "missing_plan_state"}], "marker": {"session_id": "s"}},
    "BROKEN(rationale)": {"rationale": ["awf018 detected", "BROKEN_STATE_MACHINE"]},
    "BROKEN(chain_log)": {"marker": {"session_id": "s"}, "chain_log": [{"event": "BROKEN_STATE_MACHINE"}]},
    "UNKNOWN": {"tmux_process": {"live_status": "stopped"}},
    "EMPTY": {},
}
for name, ev in probes.items():
    r = resolve_run_state(ev)
    print(f"{name:24s} -> {r.canonical_state.name:28s} human={r.human_required} gate={r.human_gate}")

print("--- edge cases ---")
# A: human gate + stale completion label
r = resolve_run_state({"plan_state": {"status": "completed", "plan_name": "p"}, "current_refs": {"target_ref": "main"}, "needs_human": [{"gate": "credential", "reason": "missing AWS key"}]})
print("A human+stale-completed ->", r.canonical_state.name, r.human_gate)
# B: live running + completed plan_state label (live beats stale)
r = resolve_run_state({"plan_state": {"status": "completed", "plan_name": "p"}, "current_refs": {"target_ref": "main"}, "tmux_process": {"live_status": "running"}, "stale_evidence": [{"kind": "missing_plan_state"}]})
print("B live+completed-label ->", r.canonical_state.name)
# C: active repair + stale failed label
r = resolve_run_state({"repair_progress": {"status": "active", "runner_ref": "r"}, "tmux_process": {"live_status": "failed", "exit_code": 1}})
print("C repair+stale-failed ->", r.canonical_state.name)
# E: authority completion + stale failed label
r = resolve_run_state({"plan_state": {"status": "completed", "plan_name": "p"}, "current_refs": {"target_ref": "main", "head_oid": "deadbeef"}, "marker": {"session_id": "s"}, "tmux_process": {"live_status": "failed", "exit_code": 1}})
print("E auth-completed+stale-failed ->", r.canonical_state.name)
# F: mechanical verdict + nothing
r = resolve_run_state({"tmux_process": {"live_status": "stopped"}}, blocker_verdict="MECHANICAL_BLOCKER")
print("F mechanical-verdict ->", r.canonical_state.name, r.human_gate)
