# GOAL: Babysit both epics to completion (partnered-codex era)

Charge: watch `megaplan-maintenance` and `astrid-first` on the Hetzner agentbox
(`root@159.69.51.216`, container `megaplan-cloud-agent-resident-only`) until **both chains
complete** — mega through `reconcile`, astrid through m6 → m7 → m8 → `reconcile`. When either
epic stalls or repeats a failure, deploy a bounded DeepSeek Flash swarm to understand the
failure at the root, hand the packed context to Grok (or Codex) for a strategy judged against
the agent philosophy, implement the narrowest source-level fix, ship it, rebind, and relaunch —
then prove movement. Never hand a blocker back; never settle for a symptom fix.

## Non-negotiables (from the operator)

- **All milestones run the `partnered-codex` profile** — the operator has approved relaunching
  either chain to apply it. Codex is the intended workhorse; deepseek-led routing is a
  fallback while codex auth on the box is broken, not a preference.
- **Both epics must reach `chain_complete: true`.** Mega: m1-m5 done, `reconcile` remaining
  (in progress as of 2026-08-19 ~21:00Z). Astrid: m1-m5 done, m6 in execute, m7/m8/reconcile
  remaining.
- **Escalate on repeat**: one failure = observe; same failure twice = swarm + Grok; three
  distinct verified fix attempts without movement = escalate to operator with evidence.

## The fixer loop (what "babysitting" means operationally)

1. **Watch** — every ~8 min, probe both chains: plan state, active phase, latest_failure,
   engine tip, babysitter liveness. Log deltas to `/workspace/.megaplan/fixer-issue-log.md`
   (I52 series) so state survives compaction.
2. **Understand** — on stall/repeat, deploy a bounded read-only DeepSeek Flash swarm
   (`~/.claude/skills/subagent-launcher/fan.py`, one brief per scoping question, terminal
   toolset for ssh access) over the failure evidence. Pack the findings.
3. **Judge** — hand the packed context to Grok (`~/.grok/bin/grok --single` with the strategy
   brief, `--output-format plain --sandbox read-only --reasoning-effort high`) for a decisive
   strategy: root vs symptom, narrowest fix, what to defer, acceptance proof per fix.
4. **Implement** — apply the narrowest source-level fix on the box engine candidate
   (`/workspace/runtime-candidates/astrid-first`), run the focused regression, commit on the
   fixer branch, ship to main via the stored credential
   (`git -c credential.helper="store --file=/workspace/.creds/git-credentials" push origin
   fixer/<branch>:main`), reset the candidate to origin/main, update the manifest
   `epic.expected_head`, and verify runtime provenance passes.
5. **Relaunch + prove** — let the chain driver/auto retry resume the plan; verify the plan
   leaves the blocked state and the same failure fingerprint does not recur. Log the outcome.

## What the fixer machine (babysitter/superfixer) handles

The box's watchdog dispatches a status-trigger "babysitter" (managed hermes agent) per
occurrence. It follows the same swarm → codex → implement → relaunch → prove flow with the
rendered goal at `/tmp/superfixer-goal-*.md`. I coordinate with it: verify its fixes, ship
mine, and ensure the two don't clobber each other (engine candidate is a shared git worktree —
check `git status` before committing).

## Known constraints (as of 2026-08-19 21:10Z)

- **Codex auth on the box is BROKEN**: `/root/.codex/auth.json` apikey has $0 balance
  (verified 429 insufficient_quota); the OAuth seed's refresh token was revoked. Until the
  operator tops up/replaces the API key or re-runs `codex login`, codex-routed phases must
  fall back to deepseek (33c858ff8, 7725d96ab already do this). Restoring codex auth is an
  operator action, not mine.
- **Provider health**: glm-5.2 (zhipu) out of quota all day; Fireworks glm-5p2 flaky (timeouts,
  no-credits); deepseek-v4-pro streams slowly (large finalize prompts time out at ~5-7 min).
  DeepSeek Flash is the reliable worker.
- **Engine fixes shipped this session** (all on main):
  - `aaeaedf85` — finalize retry preserves rejected candidate (no-clobber template +
    seed-from-raw + repair-identity mint on `planner_repair_required`).
  - `c257b3a6b` — CAS marker relaunch rebind on same-root revision advance.
  - `33c858ff8` — codex no-credits → quota_exceeded; deepseek-led fallback.
  - `7725d96ab` / `9da6501f3` — reconcile phases pinned to deepseek-led routing.
- **Epic state** (21:10Z): mega reconcile `tiebreaker_pending`→iterating (fail NONE);
  astrid m6 `finalized`/execute (5th+ attempt, pre-dispatch VJ3 narrow_recheck gate cycling —
  babysitter 3740245 investigating the validation-gate class).

## Current status update (written 2026-08-19 ~21:10Z)

### Mega (megaplan-maintenance) — 6/7 milestones, final reconcile in progress
- m1-m5 all `done`; m5 review **approved** (15/15 must criteria) at ~17:28Z.
- `reconcile-outcome-select-and-20260819-1828` born 18:28Z; advanced through
  planned→critiqued→gate→**tiebreaker_pending** (20:41Z, re-run 20:53Z) — critique and gate
  disagreeing, harness running a tiebreaker. fail NONE. On track for chain completion.
- Fixer shipped `7725d96ab` pinning reconcile phases to deepseek-led routing (codex is dead).

### Astrid (astrid-first) — 5/9 milestones, m6 in execute
- m1-m5 `done`. m6 finalize **passed** 19:59Z with a 16-task admitted graph (the 3-hour
  empty-template loop was broken by `aaeaedf85` — verified end to end: gated→finalized→execute).
- Execute is cycling on a **pre-dispatch VJ3 narrow_recheck gate** (T1's test file doesn't
  exist until the task writes it; pre-dispatch pytest exit 1). The harness's bounded recovery
  re-drives execute each cycle (5+ attempts), and babysitter 3740245 is investigating the
  gate class. `fail: pre_dispatch_validation_failed` persists on the record but the plan keeps
  relaunching — the milestone is not wedged, just gated.

### What I'm doing right now
- Switching BOTH chains to the `partnered-codex` profile per operator instruction (approved
  relaunch). Verifying the profile exists on the box engine, then rewriting both chain.yaml
  files, committing, rebinding, and relaunching each chain.
- Updating this goal doc to reflect the partnered-codex directive (this rewrite).

## Done when
- Mega chain: `chain_complete: true` (reconcile merged to main).
- Astrid chain: `chain_complete: true` (m6, m7, m8, reconcile all done).
- Both runs fail-free on the `partnered-codex` profile, with the fixer demonstrably repairing
  any stall it encounters along the way.
