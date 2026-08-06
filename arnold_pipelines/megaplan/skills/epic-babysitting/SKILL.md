---
name: epic-babysitting
description: Keep a Megaplan chain/epic actually moving — observe authoritative state, diagnose each blocker as it appears, fix the fixer/infra when genuinely broken, re-drive until the milestone advances, and prove durable movement (cursor/milestone advancement, not a PID/commit/summary). Use when a chain is blocked, stalled, or not advancing despite fixes, and you need to drive it to running.
---

# Epic-babysitting

The operational loop for keeping an epic running. A feedback loop, not a one-shot.

## The loop

1. OBSERVE authoritative state → chain/plan/events/tasks
2. DIAGNOSE the blocker → which gate/task/validator is actually stuck
3. FIX the fixer or infra → only upstream bugs; otherwise let the fixer fix
4. RE-DRIVE the execute/fixer → resume the plan / trigger the superfixer
5. VERIFY durable movement → events advancing, tasks completing, milestone > 0
6. SUMMARIZE the session → DeepSeek Flash 2-sentence summary → prior context
7. repeat until milestone advances

## 1. Observe — authoritative surfaces

- `megaplan cloud status --all --compact --cloud-yaml <cloud.yaml>`
- `<plan>/state.json` — current_state, iteration, active_step (attempt, worker_pid, health), latest_failure
- `.megaplan/plans/.chains/chain-*.json` — current_milestone_index, last_state, completed[] (THE success signal)
- `<plan>/events.ndjson` + `.events.seq` — seq advancing = cooking (filter out llm_token_heartbeat / state_written noise)
- `<plan>/execute_batches/*/tasks_*.json` — per-task status (done/blocked)
- `<plan>/verification/validation_*.json` — validator results

**Golden rule:** a PID, commit, "successful" summary, or live process is NOT proof.
Proof = canonical chain state showing milestone advancement + matching identities.

## 2. Blocker taxonomy (seen in practice)

- Finalize feasibility — plan config missing `phase_timeout_seconds` (60-min default vs 180-min chain).
- Pre-dispatch full-suite backstop (`post_execute_suite`) running synchronously and gating in shadow mode.
- cgroup OOM — suite exceeds the container's memory limit; raise it (`docker update --memory 8g`).
- Executor "No module named pytest" — PATH/site-packages issue, not a missing install; use `sys.executable -m pytest`.
- Runtime binding drift (`worker_launch_preflight_mismatch`) — CAS-bound revision vs current; rebind or relax the match.
- Stale-blocked tasks — validation passes but they need re-admission.
- Source-identity gate — baseline pinned to ancestor; re-pin via re-finalize (NOT a direct finalize.json edit).

## 3. Fix the fixer or infra — division of labor

- Fix upstream engine bugs directly (shadow mode, pytest PATH, memory, runtime-match, scheduler/watchdog).
- Let the fixer fix everything else. Give it authority (rebind) and a durable-restart handoff, not just a gate.

## 4. Re-drive

- `python3 -P -m arnold_pipelines.megaplan resume --plan <plan> --project-dir <p>`
- Trigger the superfixer: `resident schedule add` (one-shot or hourly) with
  `--prompt-file <render_goal>` `--model hermes:deepseek:deepseek-v4-flash`
  `--task-kind autonomous`; then `resident schedule run-once`.
- Two triggers, SAME deepseek → Sol → deepseek flow: hourly schedule + status
  trigger (watchdog `MEGAPLAN_SUPERFIXER_ONLY=1`).

## 5. Verify durable movement

- `chain-*.json` current_milestone_index moving off 0; events advancing; tasks
  flipping blocked → done; exactly one terminal notification.

## 6. Summarize + carry context

- After each fixer session, DeepSeek Flash browses the session dir and writes a
  2-sentence summary to `.megaplan/fixer-sessions/summaries/` + `index.md`
  (git-committed). The last 5 are injected into each new fixer's /goal as
  "UNTRUSTED HISTORICAL EVIDENCE — verify against current state", with the
  recurring-issues instruction shared with Sol subagents.

## Automation to keep running

- Resident scheduler loop (`resident schedule run-once` every ~2 min) — schedules auto-fire
  (`--listener-only` mode does NOT run it).
- Watchdog — status detection + trigger; it snapshots at launch, so a code change
  needs a watchdog restart to take effect.
- Fixer-session summarizer — hooked into the managed-run terminal path.

## Recurring patterns

- Every runtime change needs a rebind (or `require_editable_runtime_match:false`).
- Each fix reveals the next blocker — expect a chain, not one root cause.
- The fixer stops at authority gates (rebind) — grant authority or have it escalate;
  a handoff that names the gate but not the durable-restart route will stall.
- Blocked tasks are often stale — validation passes; they need re-admission.

## Success condition

The epic is durably running when the canonical chain state shows the milestone
advanced (index > 0) with matching identities and exactly one terminal
notification — not when a fixer exits, a commit lands, or a PID is alive.
