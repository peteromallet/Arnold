# PLAN EVOLUTION REVISION BRIEF — ledger entry 14 (glm-5.3-flash upstream idle-timeout flap)

You are the PLANNER (read-only). Update the plan-of-record based on a NEW failure.
Decide: ADD a new DEEP fix task, AMEND an existing task/criterion, or NO-CHANGE.
Do not widen scope beyond .oracle/agent_goal.md.

## Read first
- .oracle/northstar.md
- .oracle/agent_goal.md (plan-of-record §Objective criteria 1–7; note T7
  cooldown-aware scheduling conditions covers cgroup-OOM cooldowns only)
- docs/nbf-failure-ledger.md entry #14

## The failure (verbatim ledger entry 14)
P2 gate-bootstrap revise: `server_error: Upstream idle timeout exceeded`
(openrouter/z-ai/glm-5.3-flash) ×126 over ~3h → revise failed 3× → plan blocked
→ invalid_transition cascade on retries. Provider-side upstream degradation for
the glm-5.3-flash route (the model worked fine earlier the same day; a later
probe recovered on its own). Dispatch kept targeting the degraded route with no
failover/rotation and no typed provider-degraded scheduling condition. Block
cleared via fixer recover-blocked + chain start --one after recovery.

## Decision requested
1. ADD (new task T8?) or AMEND T7/criterion or NO-CHANGE?
2. If ADD: task id, objective, files, acceptance criteria. Candidate shape:
   typed `provider_degraded` scheduling condition joining T7's temporal class —
   consecutive upstream timeouts for a spec flip the route to a configured
   fallback (same-family alternate or last-known-good), with flip/return
   evidence in the ledger; joint model admission (criterion 5) still applies.
3. If AMEND: which criterion (1–7) and the exact amended text.
4. One line: DEEP vs ADHERENCE per the Grok verdict framework.
