# Agent Goal — make the 24h failure marathon structurally impossible

[North Star](./northstar.md) — this run advances "one door per invariant" and
"deaths speak" by shipping the systemic guard Grok specified in
docs/nbf-grok-verdicts.md (§3), verified by structural tests.

## Objective
Implement, in this repo, the typed worker-disposition control plane that makes the
2026-08-26 NBF failure marathon (11+ failure events, docs/nbf-failure-ledger.md)
impossible to recur:

1. **Unique admission gate.** Extend `require_production_worker_dispatch_runtime`
   (cloud/runtime_attestation.py) into the single production worker-admission door:
   spec translation, catalog row, model-family classification, live omp membership,
   seed/interpreter binding, timeout budget — fail closed before any worker exists.
2. **Wire all three launch doors.** workers/_impl.py raw pair, workers/omp.py
   run_omp_step, cloud/babysitter/launch.py must call the gate; no other
   refresh_/require_ preflight may execute on these paths.
3. **Typed death dispositions.** Every terminate site appends
   `{killer, signal, elapsed_s, disposition_id}` to the incident ledger:
   - launcher TimeoutExpired (subagent-launcher/launch_omp_agent.py)
   - resident/subagent.py worker.terminate()
   - watchdog SIGTERM + wedged-signaling path (wrappers/arnold-watchdog)
   - ensure-megaplan-watchdog restack pkill
4. **Fingerprint redispatch block.** Recovery loop refuses to redispatch an
   identical fingerprint unless a changed precondition is recorded.
5. **Joint model admission test** — one function validates spec↔catalog↔family↔live
   provider simultaneously; a second test asserts expired ids fail typed.
6. **Structural spy test.** Driving `_run_step_with_worker` AND `run_omp_step`
   under a production manifest hits the gate exactly once each; no other preflight.

## In scope / non-goals
- In scope: engine code above + their focused tests; catalog/family wiring already
  on main stays; hot-env pin file gets a comment pointing at the gate (no behavior).
- Non-goals: the 22-milestone NBF chain itself (it runs independently);
  Discord/resident features; CI rework beyond making new tests run.

## Settled decisions
- Model policy (user-pinned): Planner & Oracle & `[XHARD]` = grok-4.6;
  every other role = glm-5.3-flash (`openrouter/z-ai/glm-5.3-flash` via omp).
- Fix delivery = fixer contract: commit in candidate tree, ship to origin/main,
  never hotfix-by-deploy-only.
- Single-scan supervision verdicts are banned; two-scan confirmation pattern is
  the standard for any kill decision.

## Validation
- pytest tests/cloud/test_runtime_attestation.py (existing 42) PLUS new
  disposition/admission/spy suites, all green locally.
- Structural spy asserts exactly-once gating from both doors.
- bash -n on wrapper changes; grep proves no remaining raw refresh_/require_ pair
  on the three doors.

## Done / stop
Done when criteria 1–6 hold with green suites and the structural spy passes after a
fresh `git fetch && git rebase origin/main`. Stop (blocked) only if box evidence
needed for a disposition consumer is unavailable and user cannot grant it.

## Sync policy
Push branch `megado-nbf-guard-0826` to origin when batches pass oracle gates.
Merging to main requires user approval at completion review.
