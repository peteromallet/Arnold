# Epic-babysitting

The operational job of keeping a Megaplan chain/epic actually moving — not just
firing a fixer, but watching the authoritative state, diagnosing each blocker as
it appears, fixing the fixer/infra when it's genuinely broken, re-driving until
the milestone advances, and proving durable movement (cursor/milestone
advancement, not a PID or a commit).

This is the playbook for what "babysitting" an epic means in practice. It is a
feedback loop, not a one-shot.

## The loop

```
1. OBSERVE authoritative state   → chain/plan/events/tasks
2. DIAGNOSE the blocker          → which gate/task/validator is actually stuck
3. FIX the fixer or infra        → only upstream bugs; otherwise let the fixer fix
4. RE-DRIVE the execute/fixer    → resume the plan / trigger the superfixer
5. VERIFY durable movement       → events advancing, tasks completing, milestone > 0
6. SUMMARIZE the session         → DeepSeek Flash 2-sentence summary → prior context
7. repeat until milestone advances
```

## 1. Observe — the authoritative surfaces

- `megaplan cloud status --all --compact --cloud-yaml <cloud.yaml>` — which
  chains are blocked/executing/repairing, with custody + decision.
- `<plan>/state.json` — `current_state`, `iteration`, `active_step` (phase,
  attempt, worker_pid, last_activity, health), `resume_cursor`, `latest_failure`.
- `.megaplan/plans/.chains/chain-*.json` — `current_milestone_index`,
  `last_state`, `completed[]` (THE success signal).
- `<plan>/events.ndjson` + `.events.seq` — the event timeline; `seq` advancing
  means it's cooking. Filter out `llm_token_heartbeat` and `state_written` (noise).
- `<plan>/execute_batches/*/tasks_*.json` — per-task status (`done`/`blocked`).
- `<plan>/verification/validation_*.json` — validator results (`passed`/
  `deferred_task_output`/`failed`/`runner_error`).

**Golden rule:** a PID, a commit, a "successful" summary, or a live process is
NOT proof. Proof = canonical chain state showing milestone advancement + matching
identities (runtime/request/grant/claim/WBC).

## 2. Diagnose — the blocker taxonomy seen in practice

- **Finalize feasibility** — plan config missing `phase_timeout_seconds`
  (falls back to 60 min; chain is 180). Fix: seed from chain driver.
- **Pre-dispatch full-suite backstop (`post_execute_suite`)** — a 620-file
  blast-radius suite running synchronously at pre-dispatch and gating, even in
  `full_suite_backstop_mode: shadow`. Fix: defer it in shadow mode (non-blocking).
- **cgroup OOM** — the suite exceeds the container's 2 GiB limit. Fix: raise
  memory (`docker update --memory 8g <container>`); host headroom is usually ample.
- **Executor "No module named pytest"** — PATH/site-packages resolution in the
  hermes worker, not a missing install. Fix: rewrite `pytest` to
  `sys.executable -m pytest`; add an import preflight.
- **Runtime binding drift (`worker_launch_preflight_mismatch`)** — the chain is
  CAS-bound to a runtime revision; every code change drifts it. Fix: CAS rebind
  to the new identity, or relax `require_editable_runtime_match` for recovery.
- **Blocked tasks that already pass** — stale-blocked from an earlier gate;
  validation now passes, they just need re-admission by the execute.
- **Source-identity gate (T0)** — baseline pinned to an ancestor; re-pin to the
  descendant via a proper re-finalize (NOT a direct finalize.json edit — that
  breaks the admitted-graph hash).

## 3. Fix the fixer or infra — division of labor

- **Fix upstream engine bugs directly** (shadow-mode not honored, pytest PATH,
  memory ceiling, runtime-match toggle, scheduler/watchdog not running).
- **Let the fixer fix everything else.** The fixer (superfixer) is the recovery
  driver: Sol (gpt-5.6-sol) scopes → DeepSeek Flash swarm → Sol adjudicates →
  fixer executes. The operator's job is to give it authority (rebind) and a
  correct handoff (a durable-restart route, not just a gate).

## 4. Re-drive

- `python3 -P -m arnold_pipelines.megaplan resume --plan <plan> --project-dir <p>`
  — re-drive a blocked plan.
- Trigger the superfixer: `resident schedule add` (one-shot or hourly) with
  `--prompt-file <render_goal>` `--model hermes:deepseek:deepseek-v4-flash`
  `--task-kind autonomous`; then `resident schedule run-once` to fire it.
- The fixer is triggered two ways (both the SAME deepseek → Sol → deepseek flow):
  - **Hourly schedule** — recurring `PT1H` superfixer backstop.
  - **Status trigger** — watchdog `MEGAPLAN_SUPERFIXER_ONLY=1` launches the same
    superfixer on blocked/errored.

## 5. Verify durable movement

- `chain-*.json` `current_milestone_index` moving off 0.
- `.events.seq` advancing; tasks flipping `blocked → done`.
- Exactly one terminal notification; matching identities.

## 6. Summarize + carry context

- After each fixer session, a DeepSeek Flash agent browses the session dir
  (result.md, recovery-evidence.json, final `agent_message` in run.log) and
  writes a 2-sentence summary to `.megaplan/fixer-sessions/summaries/<id>.md` +
  `index.md` (git-committed for durability).
- Every new fixer's `/goal` is injected with the **last 5 summaries** (labeled
  "UNTRUSTED HISTORICAL EVIDENCE — verify against current state") and told to
  account for recurring issues + share the index with any Sol subagents.

## Key automation to keep running

- Resident **scheduler loop** (`resident schedule run-once` every 2 min) — makes
  schedules auto-fire. The resident's `--listener-only` mode does NOT run it.
- **Watchdog** — status detection + trigger. If absent, the status-trigger
  never fires. It snapshots itself at launch; a code change needs a watchdog
  restart to take effect.
- **Fixer-session summarizer** — hooked into the managed-run terminal path so it
  always runs.

## Recurring patterns (the whack-a-mole)

- **Every runtime change needs a rebind** (or `require_editable_runtime_match:false`).
- **Each fix reveals the next blocker** — expect a chain, not a single root cause.
- **The fixer stops at authority gates it can't cross** (rebind) — grant it the
  authority or have it escalate; a handoff that names the gate but not the
  durable-restart route will stall.
- **Blocked tasks are often stale** — validation passes; they need re-admission.

## Success condition

The epic is durably running when the **canonical chain state shows the milestone
advanced** (index > 0) with matching identities and exactly one terminal
notification — not when a fixer exits, a commit lands, or a PID is alive.
