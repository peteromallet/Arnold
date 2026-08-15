# Babysitter autonomous fixer — working end-to-end (2026-08-14)

## The user's intended flow is now the ONLY repair flow, proven live:
watchdog (detects blocked chain) -> launches ONE DeepSeek-flash babysitter ->
its GOAL drives: swarm explore (fan.py) -> codex consult (gpt-5.6-sol) ->
implement narrowest fix -> relaunch -> prove movement.

## Evidence (box, 2026-08-14)
- Watchdog: "single-flash babysitter launched session=megaplan-maintenance
  digest=a102d8d24045" + "babysitter already running for occurrence" (dedup,
  no relaunch storm, no kimi).
- Run 1 (digest d58701026410): swarm (4 briefs Q1-Q4) -> codex proposal
  (382 lines) -> implemented chain.yaml driver.phase_timeout: 7200 ->
  rebind runtime + marker cutover -> CHAIN ADVANCED: finalize error ->
  finalize SUCCESS (history: finalize success).
- Run 2 (digest a102d8d24045): swarm (5 briefs, 6 workers, failed_count 0) ->
  codex -> fixed runtime_attestation marker/seed drift (26/26 tests) ->
  fixed stale-lease wedge -> rebuilt launch seed (ready true) ->
  chain start succeeded -> resume hit NEW blocker: oversized batch
  (6 tasks > ceiling 5).
- Honest: babysitter explicitly refused to fabricate movement; proof
  criteria documented (chain last_state != blocked, fingerprint not recur).

## What the fixer now does (machinery)
- arnold-watchdog: phase-contract fence (no mechanical relaunch for
  deterministic failures) -> babysitter_policy_dispatch (mode off ->
  babysitter_off; running -> babysitter_running; launch -> babysitter_scheduled;
  fail -> babysitter_launch_failed; NO L1/L2 fallthrough).
- cloud/babysitter/launch.py: one managed hermes:deepseek:deepseek-v4-flash
  agent with file,web,terminal toolsets (can run fan.py + codex exec);
  dedup by occurrence digest; receipts; fail-closed.
- skills/babysitter/render_babysitter_goal.py: single-flash goal:
  STEP 1 DEPLOY THE SWARM (fan.py) / STEP 2 CONSULT CODEX (gpt-5.6-sol) /
  STEP 3 IMPLEMENT / STEP 4 RELAUNCH / STEP 5 PROVE MOVEMENT.
- Deleted: arnold-repair-loop, arnold-meta-repair-loop, arnold-repair-trigger,
  arnold-kimi-goal-operator, orchestrator.py, claim_active_repair_request,
  L1/L2 flags. BabysitterSpec modes superfixer|off, default superfixer.
- maintenance cloud.yaml: driver.babysitter.mode off (NORTHSTAR containment).

## Current frontier
- Chain blocked at execute: oversized batch 2 dispatched 6 tasks (> ceiling 5).
  The babysitter identified it; the next iteration fixes the batch ceiling.
- Durable: finalize SUCCESS (the phase_timeout fix admitted the graph).
