# Grok deep-plan brief (planner phase) — megado-nbf-guard-0826

You are the PLANNER for this run. Read, in order:
- .oracle/northstar.md (durable direction + anti-patterns)
- .oracle/agent_goal.md  (frozen objective/scope/validation — the contract)
- docs/nbf-failure-ledger.md and docs/nbf-grok-verdicts.md in repo root
  (the 11+ event ledger and your own prior systemic-guard specification, §3)

Produce `.oracle/plan.md` containing:
1. A tasklist covering the ENTIRE agent goal: unique admission gate extension,
   three-door wiring, typed death dispositions at all four kill sites,
   fingerprint redispatch block, joint model admission function + expired-id test,
   structural spy test asserting exactly-once gating from both doors.
2. Batch design with natural seams (suggest 3–4 batches), each batch ending at a
   green-test checkpoint; name per-batch acceptance criteria.
3. Additional areas to explore for full clarity (files/tests you need read first),
   marked for the glm explorer wave.
4. Open questions you cannot resolve from the repo.
5. Explicit check: how each batch advances the North Star principles ("one door
   per invariant", "deaths speak") without reproducing listed anti-patterns.
6. Best-effort total implementation effort estimate with a >2-weeks huge-run
   determination or not.

Bias toward elegance: reuse existing runtime_attestation surfaces; delete
duplicate preflights rather than adding parallel ones. Est. ~1500 words max.

## ADDENDUM — Sol sense-check findings (VERDICT: REVISE) — incorporate ALL
Read .oracle/findings/sensecheck-sol.txt. Non-negotiables from the independent
review (evidence-cited there):
1. Spy: use run_step_with_worker (workers/_impl.py:7347), not _run_step_with_worker;
   no mock early-return; intercept final spawn/RPC only; cover ALL THREE doors incl
   babysitter/launch.py; assert gate-before-spawn ordering.
2. Avoid double-gating: _impl.py:7698-7713 delegates to run_omp_step — gate non-OMP
   routes in _impl, OMP at backend entry, babysitter pre-launch; nested OMP path =
   one total hit.
3. Reuse existing admission pieces (omp.py:1144-1149 static validation, classify at
   render, timeout at :1248). Expired-ID test must prove "static accepts, live
   catalog rejects typed" (ox-alpha accepted statically today — omp.py:98-105,
   model_seam.py:502-506).
4. Kill paths: signal_hung_fixer_children (arnold-watchdog:1917-1942) and
   ensure-restack (ensure-megaplan-watchdog:47-58) still single-observation — extend
   two-observation + live-pid/advancing-seq proof to BOTH.
5. Dispositions: launcher TimeoutExpired kills child pre-exception
   (launch_omp_agent.py:251-261); resident has two ladders (subagent.py:4818,
   5065); route through ONE typed helper over IncidentLedger.append_event
   (incident/ledger.py:338-361); test every signal branch.
6. Fingerprint: projection flags at 3rd repeat (incident/projection.py:452-478) —
   add PRE-LAUNCH enforcement against last terminal fingerprint with durable
   changed-precondition identity.
7. docs/nbf-grok-verdicts.md restored to full text on branch (was truncated).
