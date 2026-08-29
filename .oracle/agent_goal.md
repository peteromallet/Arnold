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
2. **Wire all three launch doors — exactly once each.** workers/_impl.py non-OMP
   routes, workers/omp.py run_omp_step (backend entry; _impl delegates to it at
   _impl.py:7698-7713 — the nested OMP path must total ONE hit), and
   cloud/babysitter/launch.py pre-managed-launch. No other refresh_/require_
   preflight may execute on these paths.
3. **Typed death dispositions — every real signal branch.** Route ALL terminate
   sites through one typed helper over `IncidentLedger.append_event`
   (incident/ledger.py:338-361), appending
   `{killer, signal, elapsed_s, disposition_id}`:
   - launcher: the child is killed BEFORE TimeoutExpired raises
     (subagent-launcher/launch_omp_agent.py:251-261) — disposition at the kill,
     not the exception
   - resident/subagent.py: two terminate→kill ladders (:4818-4824, :5065-5072)
   - watchdog: SIGTERM + wedged-signaling path (wrappers/arnold-watchdog)
   - ensure-megaplan-watchdog restack pkill
4. **Fingerprint redispatch block — pre-launch.** Admission refuses to launch a
   worker whose dispatch fingerprint matches the last terminal fingerprint
   (incident/projection.py:452-478 currently only diagnoses at the 3rd repeat)
   unless a durable changed-precondition identity is recorded.
5. **Joint model admission — and expired-ID proof.** One admission function
   validates spec↔catalog↔family↔live provider membership simultaneously; a
   test proves the discriminating case: static catalog ACCEPTS an expired id
   (ox-alpha, workers/omp.py:98-105 / model_seam.py:502-506) while the joint
   admission REJECTS it typedly against the live provider.
6. **Structural spy test — three doors, gate-before-spawn.** Driving
   `run_step_with_worker` (workers/_impl.py:7347 — NOT the underscore name)
   and `run_omp_step` under a production manifest hits the gate exactly ONCE
   per dispatch (the nested OMP delegation totals one hit), the babysitter
   pre-launch door is covered, the spy intercepts only final spawn/RPC (no
   mock early-return), and a door-bypass today would make it fail.

## In scope / non-goals
- In scope: engine code above + their focused tests; catalog/family wiring already
  on main stays; hot-env pin file gets a comment pointing at the gate (no behavior).
- Non-goals: the 22-milestone NBF chain itself (it runs independently);
  Discord/resident features; CI rework beyond making new tests run.

## Settled decisions
- Model policy (user-pinned, superseding the earlier staged declaration):
  Planner, Oracle, and any justified `[XHARD]` task = GPT-5.6 Sol
  (`gpt-5.6-sol`, high reasoning); every normal exploration, critique,
  execution, and independent review task = GPT-5.6 Luna (`gpt-5.6-luna`).
  No model switch is authorized without user approval.
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

## Source custody for resumed execution

Build on refreshed `origin/main` at immutable source SHA
`798c50619204010ed3f4297fbb57988fe9381924`; preserve the five branch-only
planning/evolution commits and the protected untracked artifacts named in
`custody.md`. The source update does not widen scope or authorize a main merge.

7. **Cooldown-aware scheduling conditions (T7, added via plan evolution — ledger
   entry 13).** Treat an active same-phase/spec cgroup-OOM cooldown as a typed,
   time-bounded `scheduling_condition`, never a worker/phase failure: shared
   pre-dispatch seam calls `memory_cooldown_wait_secs`, emits `retry_wait`
   evidence, sleeps via injectable clock/sleeper, reruns admission. A
   scheduling condition increments neither deterministic-phase-failure nor
   repeated-signature counters and cannot set the plan to `blocked`; genuine
   repeated internal_errors still open their breakers. Foundation shipped to
   main: a9e1c7d0d6 (death expiry) + af370f5ec6 (defer refusals; recover
   repeated-failure blocks).

8. **Typed `provider_degraded` scheduling condition (T8, plan evolution — ledger
   entry 14).** Consecutive upstream idle-timeouts/availability errors for one
   spec become a typed, time-bounded `scheduling_condition`
   (`reason=provider_degraded`, carrying `phase`/`spec`/`retry_after_s`) —
   never a worker/phase failure. Breaker-exempt like T7. If a configured
   fallback exists (same-family alternate or last-known-good), flip through the
   existing fallback-chain door (`fallback_chains.py`,
   `_advance_configured_spec_fallback`) with the flip target passing joint
   admission (criterion 5); if the pin is scalar, hold with a bounded health
   probe and redispatch once after recovery. Flip AND return-to-primary append
   ledger evidence. Files: fallback_chains.py, workers/_impl.py,
   handlers/shared.py, orchestration/phase_result.py, recovery_policy.py,
   auto.py breakers, incident/ledger.py. DEEP verdict (Grok 4.6, full spec in
   .oracle/findings/evolution-entry14.txt).
