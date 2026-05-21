---
name: megaplan-observe
description: Observe an in-flight or stuck megaplan run — status, watch, progress, drift detection. Consult when a plan is quiet, blocked, misbehaving, or burning budget faster than expected.
---

# Megaplan Observe

When megaplan is running and something feels off — too quiet, too expensive, or outright blocked — this skill tells you where to look and what to do next. Every question you have about a running plan starts with the same one command: `megaplan status --plan <plan>`.

## When to reach for this skill

- The user asks "is it still going?" or "what's it doing right now?"
- A plan transitioned to `blocked` and you don't know why.
- Cost is climbing faster than expected and you need to see which model is chewing tokens.
- You suspect a binary or rubric has drifted from what the plan expects.
- A phase has been quiet for longer than its timeout and you need to decide whether to wait or intervene.

Do **not** use this skill for:
- Working with the plan — that's the main `megaplan` skill.
- Filing bugs or observations — that's `megaplan-tickets`.
- Picking a profile or robustness level — that's `megaplan-decision`.

## The four signals from `megaplan status --plan <plan>`

`status` returns a JSON payload. Four fields matter more than the rest:

| Signal | Source field | What it tells you | Gotcha |
|---|---|---|---|
| **Wall clock** | none — fetch `date -u` separately | The server's clock at status time. | **Never** infer recency from `active_step.last_activity_at` without subtracting from current `date -u`. A stale read on disk looks current. |
| **Liveness** | `active_step.health` + `worker_pid_alive` + `idle_seconds` + `recommended_action` | The harness already computes this for you. `health: "healthy"` + `recommended_action: "wait"` means stop second-guessing it. Also surfaces `progress_pct`, `phase_progress_summary` (e.g. "revise running (14m elapsed, typically completes within 15m)"), `attempt: N/3` for retry visibility. | Don't manually re-derive these from raw timestamps — read the computed fields. Cross-check with `ps -p <pid>` only when `worker_pid_alive` itself is `False`. |
| **Next valid actions** | `valid_next` | Ordered list of step names the harness will accept next. For `blocked` states, this is the recovery menu. | Never run an action not in this list — `megaplan override` will reject it with `invalid_transition`. |
| **Cost so far** | `total_cost_usd` | Cumulative reported cost. | This figure has known accounting bugs (see tickets `01KRZYNK45GA4VS2KCA6JYZAXK`, `01KRZZ28CPKA2C32VQFQHDJ45S`) — persistent codex sessions and review session-id leaks cause it to over-count by 3–6×. Treat as upper bound, not truth. |

For **binary / rubric drift** (the highest-ROI check), there's no built-in command yet. Use `git -C <megaplan-repo> status` and compare your installed version with `megaplan --version`. The local rubric source-of-truth is in `~/.claude/skills/megaplan-*/SKILL.md` (each symlinked into `megaplan/megaplan/data/*_skill.md`).

## The observation hierarchy

When something seems wrong, work through these in order. Each step is cheaper and safer than the next.

1. **`megaplan status --plan <plan>`** — one call, full picture. Start here every time.
2. **`megaplan watch --plan <plan>`** — if `status` says active or quiet but you want to watch state evolve in near-real-time.
3. **`megaplan progress --plan <plan>`** — once the plan has finalized, shows batch/task progress through `execute`. (Returns "no finalize.json yet" before finalize.)
4. **`megaplan audit query --plan <plan>`** — query historic step receipts. Useful after the fact, when you want to know what each phase cost or how long it ran.
5. **`ps -p <pid> -o pid,etime,stat`** + worker process listing — confirm the auto driver and any worker is alive.
6. **Direct filesystem inspection** — last resort. If you find yourself reaching for `cat state.json`, consider filing a ticket asking for the missing `status` field. Direct state read often shows fields like `active_step.last_activity_detail` that `status` does surface, so check `status` JSON first.

### Watching evolution

```bash
megaplan watch --plan <plan>
```

`watch` prints state-transition events as they happen. Ctrl-C to exit. There's no `--follow` flag here — `watch` is the follow.

For a journal-style timeline, read `state.json` directly or use `audit query`:

```bash
megaplan audit query --plan <plan>
```

## Failure-mode catalog

Each entry: the `status` signature you'll see, the recovery path, and context.

### Stalled critique

**Signature:** `active_step.name` is in critique, multiple `critique_check_*.json` artifacts already exist, but `last_activity_at` is > 15min ago and `active_step.last_activity_detail` shows the same fragment as last poll.

**Recovery:** First check if it's actually stalled vs slow — cross-check the worker PID with `ps -p <pid> -o etime`. If the worker is alive and the LLM is just slow, wait. If `last_activity_detail` ends in `⚠️  API call failed (attempt N/3): TimeoutError`, the harness is retrying — give it the full retry budget before intervening.

If the heartbeat is truly gone (no PID, `last_activity_at` > phase_timeout) the auto driver may have died silently — same pattern as historical bug `01KRY1V1WS7SVN3FPYW29ATVNP`.

**Critique perf optimization:** `full` robustness defines 5 core critique checks. Default `orchestration.max_critique_concurrency = 5` (raised from 2 to handle them in one wave; see ticket `01KS03H13JWMVSED6V4584P1P3`). If you see batched mtimes spanning ~8-9 min between batches, your local override may be lower than 5; check with `megaplan config show`.

### Blocked state

**Signature:** `state: blocked`, `valid_next` is non-empty (typically lists `step` plus 1-2 specific recovery actions).

**Recovery:** Read `valid_next`. Pick the first applicable action. Execute it via `megaplan override --plan <plan> --action <action>` or by re-running the named phase. Verify the state transitioned away from `blocked` with a follow-up `status`. Do not paste an action not in `valid_next`.

**Context:** Blocked is not a failure — it's the harness refusing to proceed on a conflict it can't resolve alone. `valid_next` is the contract. Respect it.

### Rubric / binary drift

**Signature:** A skill doc references a command (`introspect`, `trace`, `doctor`) that returns `invalid choice` when run. A profile name in the doc doesn't appear in `megaplan config profiles list`. The local megaplan repo is on a different branch than when the plan was initialized.

**Recovery:** Trust the binary surface (`megaplan --help`, `megaplan <cmd> --help`), not the doc. Fix the doc to match. If a profile is renamed, use `megaplan config profiles list` to find the closest current name.

**Context:** Rubric drift is silent until it isn't — the skill describes a surface that doesn't ship. The first invocation that needs the missing command surfaces the drift. Check `megaplan --help | grep -E "<cmd-from-doc>"` before trusting any skill recipe.

### Execute loop spinning

**Signature:** `active_step.name == "execute"`, `last_activity_at < 2min` (heartbeat fine), but `megaplan progress` shows `batches_completed` flat across multiple polls and `tasks_done` is not advancing.

**Recovery:** Read `state.json`'s `execution_audit.json` artifact and look for repeated retries on the same task IDs with different worker models. If a particular batch is stalling, the task decomposition may be too fine-grained for the worker to make progress. Escalate to the user with the batch number and a recommendation to increase `execution.max_execute_no_progress` (`megaplan config set execution.max_execute_no_progress 5`) or adjust the task granularity.

**Context:** Execute loops can spin when tasks are decomposed below the model's useful atomicity threshold. The harness counts completions, not impact.

### Accounting inflation

**Signature:** `total_cost_usd` climbs sharply during a single execute phase, or `state.json` history shows two execute entries with identical 6-decimal `cost_usd` but different `duration_ms` / `timestamp`.

**Recovery:** Trust the latest `step_receipt_<phase>_v<iteration>.json` cost field — not the rolled-up `total_cost_usd`. Two filed bugs underlie this: `01KRZYNK45GA4VS2KCA6JYZAXK` (persistent codex session rebills cumulative total each batch) and `01KRZZ28CPKA2C32VQFQHDJ45S` (review session-id leak copies stale token counts).

**Context:** Real provider billing is fine — the harness double-counts in its own ledger. Don't panic at high `total_cost_usd` until the bug fixes land.

## Do-not rules

These are hard rules derived from real failure modes. Don't break them.

1. **Do not infer wall time from JSON timestamps without `date -u` cross-check.** A stale read looks current. Always compute the delta against current wall clock.
2. **Do not retry actions that returned `invalid_transition` — read `valid_next` first.** The list is exhaustive. If your action isn't there, it won't work.
3. **Do not stash / checkout in the megaplan source repo without user consent.** Editable installs make repo state load-bearing. A `git checkout` in the megaplan repo can silently change the tool the running plan is using.
4. **Do not trust `total_cost_usd` until the accounting tickets close.** Persistent codex sessions and review session-id leaks inflate it 3–6×. Use individual step receipts.
5. **Do not assume "the in-flight run can't benefit from a fix."** The orchestrator reads many settings (e.g. `max_critique_concurrency`) **per call**, not once at start. A `megaplan config set <key> <value>` BEFORE the next phase starts is picked up by the next invocation.

## Worked invocation chains

### "Is it still going?"

```bash
megaplan status --plan <plan>   # state + active_step
date -u                          # current wall clock to delta against last_activity_at
ps -ef | grep megaplan | grep -v grep   # confirm worker PIDs alive
```

Narrate back:

> "It's in critique, last activity 3 min ago, worker PID 18053 alive 17m. Looks healthy."

If `last_activity_at` is older than ~10 min AND no worker PID, escalate to the failure-mode catalog above.

### "Plan went blocked, what now?"

```bash
megaplan status --plan <plan>   # read valid_next
```

Pick the first recovery action, run it, verify:

```bash
megaplan override --plan <plan> --action <first-valid-action>
megaplan status --plan <plan>   # confirm state is no longer blocked
```

### "Cost is climbing faster than expected"

```bash
megaplan status --plan <plan>   # total_cost_usd (treat as upper bound)
megaplan audit query --plan <plan>   # per-step receipt costs (authoritative)
```

Compare the per-step receipt costs to the rolled-up total. If they diverge wildly, you're hitting one of the known accounting bugs — trust receipts.

### "The next critique is going to be slow — can I speed it up before it starts?"

```bash
megaplan config set orchestration.max_critique_concurrency 5
# verify what the orchestrator will read next:
python -c "from megaplan._core import get_effective; print(get_effective('orchestration', 'max_critique_concurrency'))"
```

The orchestration call site reads this per invocation, so the next critique phase picks it up live — even mid-run.

## Quick reference

| You want to … | Run |
|---|---|
| Check if a plan is alive | `megaplan status --plan <plan>` + `date -u` |
| Watch a plan as it runs | `megaplan watch --plan <plan>` |
| Diagnose a blocked plan | `megaplan status --plan <plan>` → read `valid_next` |
| See per-step costs (authoritative) | `megaplan audit query --plan <plan>` |
| See execute batch progress | `megaplan progress --plan <plan>` |
| Override a blocked transition | `megaplan override --plan <plan> --action <action>` (action must be in `valid_next`) |
| Push a setting to the next phase | `megaplan config set <key> <value>` before the phase fires |

Start with `status`. The answer is almost always in that first payload.

## How this skill fits with the others

| Skill | When to reach for it |
|---|---|
| `megaplan` (main) | Driving the harness — init, plan, execute, review. The operator skill. |
| `megaplan-decision` | Before invocation — profile, robustness, depth. The pre-flight skill. |
| `megaplan-observe` (this skill) | During or after a run — status, watch, progress, audit. The dashboard skill. |
| `megaplan-tickets` | Capture out-of-scope problems found during observation. The note-taking skill. |
| `megaplan-epic` | Work bigger than one sprint — chain multiple megaplan runs. The scaling skill. |

The typical flow: **decide** (megaplan-decision) → **drive** (megaplan) → **observe** (this skill, whenever something feels off) → **ticket** (megaplan-tickets, for anything out-of-scope). If the work is multi-sprint, wrap it in an **epic** (megaplan-epic).
