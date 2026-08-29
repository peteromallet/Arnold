# PLAN EVOLUTION REVISION BRIEF — ledger entry 13 (p2 prior_cgroup_oom cooldown)

You are the PLANNER (read-only). Update the plan-of-record based on a NEW failure.
Decide: ADD a new DEEP fix task, AMEND an existing task/criterion, or answer
NO-CHANGE. Do not widen scope beyond .oracle/agent_goal.md.

## Read first
- .oracle/northstar.md (direction + anti-patterns)
- .oracle/agent_goal.md (plan-of-record §Objective, criteria 1–6)
- docs/nbf-failure-ledger.md entry #13 (bottom of file)

## The failure (verbatim ledger entry 13)
P2 gate-bootstrap revise: typed `prior_cgroup_oom` refusal ×3 → deterministic
breaker blocked the plan. Root: glm-5.3-flash revise dispatched into a
cgroup-OOM cooldown window (pre-16G deaths recorded for the spec); the caller
fed a TIME-BOUNDED scheduling refusal into the deterministic-failure breaker
instead of sleeping the cooldown — exactly what
`arnold_pipelines/megaplan/runtime/memory_headroom.py::memory_cooldown_wait_secs`
docstring warns callers against ("Callers sleep this long and retry instead of
feeding the refusal to the deterministic-failure / repeated-signature
breakers, which would permanently block the plan on a condition that
expires"). Cooldown expired on its own; plan recovered via supported seam.

## Decision requested
1. ADD or AMEND or NO-CHANGE?
2. If ADD: write the new task (id, objective, files, acceptance criteria) —
   candidate shape: cooldown-aware revise dispatch (call
   `memory_cooldown_wait_secs`, sleep+retry instead of breaker-feeding) plus a
   typed `scheduling_condition` class exempt from deterministic breakers.
3. If AMEND: which criterion (1–6) and the exact amended text.
4. One line: why this is DEEP vs ADHERENCE per the Grok verdict framework.
