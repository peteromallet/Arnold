# Blocked-Recovery Runbook

**Evidence id:** `OPS-BLOCKED-RECOVERY`

When a megaplan run enters the **`blocked`** state, the worker (LLM agent) has
either failed a quality gate during execution, reported tasks as blocked, or the
auto-driver has exhausted its retry budget. This runbook walks through
diagnosis, reading `valid_next`, and choosing a recovery path.

---

## 1. Identify the Blocked Plan

```bash
megaplan list --status blocked
```

Or check a specific plan:

```bash
megaplan status --plan <plan-name>
```

### Reading `valid_next`

The `status` output includes a `valid_next` array that lists every CLI action
the state machine will accept from the current state. **The `blocked` state is
terminal** — it has no forward transitions in the standard workflow. The
recovery paths below use resume/override commands that the workflow layer
validates separately.

```json
{
  "state": "blocked",
  "valid_next": [],
  "next_step": null
}
```

When `valid_next` is empty, you must use one of the recovery paths in
§3—§5 below.

> **Note:** Non-terminal states that *precede* a block also show `valid_next`.
> For example, `critiqued` shows `["gate", "revise", "override force-proceed",
> "override abort", "override add-note"]`. Use `valid_next` proactively to
> prevent invalid transitions.

---

## 2. Diagnose the Block Reason

### 2.1 Check the latest phase result

```bash
cat .megaplan/plans/<plan-name>/phase_result.json | python -m json.tool
```

Key fields:

| Field | Meaning |
|-------|---------|
| `exit_kind` | `"blocked_by_quality"` — quality gate deviations |
| | `"blocked_by_prereq"` — prerequisite tasks not done |
| `blocked_tasks` | List of `{task_id, reason, notes}` for blocked tasks |
| `deviations` | List of `{kind, message, task_id}` quality-gate failures |

### 2.2 Inspect execution output

```bash
cat .megaplan/plans/<plan-name>/execution.json | python -m json.tool
```

Look for `result: "blocked"` in the latest history entry, aggregate
`execution.json`, or task-native execution artifacts:

```bash
python -c "
import glob, json
for path in glob.glob('.megaplan/plans/<plan-name>/tasks/*/execution.json'):
    data = json.load(open(path))
    records = data.get('task_updates') if isinstance(data.get('task_updates'), list) else [data]
    for t in records:
        if isinstance(t, dict) and t.get('status') == 'blocked':
            print(f\"Blocked: {t.get('task_id') or t.get('id') or path} - {t.get('reason', 'no reason')}\")
"
```

### 2.3 Review lifecycle failure record

Each block writes a record via `record_lifecycle_failure()` that includes a
`resume_cursor` with the suggested retry strategy:

```bash
python -c "
import json
s = json.load(open('.megaplan/plans/<plan-name>/state.json'))
f = s.get('latest_failure', {})
print(json.dumps(f, indent=2))
"
```

---

## 3. Recovery Decision Tree

```
┌──────────────────────────────────────────────┐
│         Plan is BLOCKED                       │
│  (STATE_BLOCKED in state.json)               │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
     ┌─────────────────────────────┐
     │  Read phase_result.json     │
     │  exit_kind?                 │
     └──────────┬──────────────────┘
                │
    ┌───────────┴───────────┐
    │                       │
    ▼                       ▼
blocked_by_quality      blocked_by_prereq
    │                       │
    │                       ▼
    │           ┌──────────────────────┐
    │           │  Retry with          │
    │           │  --retry-blocked-tasks│
    │           │  (megaplan auto or   │
    │           │  megaplan execute    │
    │           │  --retry-blocked-    │
    │           │  tasks)              │
    │           └──────────┬───────────┘
    │                      │
    ▼                      ▼
┌──────────────────────────────────────────┐
│  Evaluate deviations                     │
│  - Are they fixable by retrying?         │
│  - Do they need a plan revision?         │
│  - Is the worker session poisoned?       │
└──────────┬───────────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
Fixable       Needs human
via retry     intervention
    │             │
    ▼             ▼
┌────────┐  ┌──────────────────────────┐
│Retry   │  │See §5 — Override paths   │
│execute │  │(blocked-valid only):     │
│fresh   │  │abort, add-note,          │
│        │  │set-robustness,           │
│        │  │set-profile               │
└────────┘  │Or resume with fresh      │
            │session (§4.3)            │
            └──────────────────────────┘
```

---

## 4. Recovery Paths

### 4.1 Auto-retry (preferred for simple blocks)

```bash
megaplan auto --plan <plan-name> --max-blocked-retries 2
```

The auto-driver:
1. Detects `blocked` state on the next iteration.
2. Re-dispatches `execute` with `--retry-blocked-tasks` (safe no-op when
   no tasks remain blocked — see `auto.py` lines 323–336).
3. Counts consecutive blocked attempts. When `blocked_retry_count >=
   max_blocked_retries` (default 1), bails with `worker_blocked` status and
   exit code 8.

### 4.2 Manual execute retry

```bash
megaplan execute --plan <plan-name> --confirm-destructive --user-approved
```

This works when the plan is in the `blocked` state because `handle_execute`
accepts `{STATE_FINALIZED, STATE_BLOCKED, STATE_FAILED}` as valid starting
states (see `execute.py` line 77).

If `--retry-blocked-tasks` is needed:

```bash
megaplan execute --plan <plan-name> --confirm-destructive --user-approved --retry-blocked-tasks
```

### 4.3 Resume in the task worktree

When the worker environment is suspected to be poisoned (stale context, wrong
beliefs about filesystem state), resume from the stored cursor:

```bash
megaplan resume --plan <plan-name>
```

The resume mechanism (`workflow.py` `resume_plan()`):
1. Reads the `resume_cursor` from `state.json` (set by
   `record_lifecycle_failure`).
2. Overrides `current_state` to the active pre-phase state (e.g. `finalized`
   for execute resume).
3. Re-runs the task through the task worktree retry path.
4. Clears `latest_failure` and `resume_cursor` on success.

The worktree-native execute resume cursor structure:

```json
{
  "phase": "execute",
  "task_id": "T7",
  "task_key": "t7-0123456789abcdef",
  "task_id_encoded": "VDc",
  "task_id_encoding": "base64url-v1",
  "trailer_encoding_version": "base64url-v1",
  "cursor_schema_version": 1,
  "retry_strategy": "task_worktree"
}
```

Legacy `batch_index` cursors are migration diagnostics only. A
worktree-native plan that still has one must be diagnosed with
`megaplan migrate-plan --diagnose <plan-name>` and closed or restarted before
resuming execute.

### 4.4 Driver-level retry with increased cap

If the auto-driver previously bailed at the default `max-blocked-retries=1`:

```bash
megaplan auto --plan <plan-name> --max-blocked-retries 3
```

The driver's loop (`auto.py` lines 1386–1486) tracks `blocked_retry_count` and
collects `blocking_reasons` from `result.deviations`. When the cap is reached it
writes a `record_lifecycle_failure` with kind `execution_blocked` and returns
`worker_blocked`.

---

## 5. Override Paths (Human Intervention)

When automated retries fail or the plan needs structural changes, use the
override command.

> **Important:** From the `blocked` state, `override force-proceed` and
> `override replan` are **not valid transitions**. `force-proceed` only
> accepts `critiqued` (override.py:181–185); `replan` only accepts
> `gated`/`finalized`/`critiqued`/`failed` (override.py:241–245). The
> overrides listed below are the ones that actually accept `blocked`.

### 5.1 `override add-note`

Attach context to the plan without changing state. Useful for documenting why a
block occurred:

```bash
megaplan override add-note --plan <plan-name> --note "Blocked because external API was down; retry after 15m"
```

Notes are visible in `status` output and in the `meta.notes` array in
`state.json`.

### 5.2 `override abort`

Terminate the run cleanly:

```bash
megaplan override abort --plan <plan-name> --reason "Block unrecoverable; manual fix required"
```

The plan enters `aborted` terminal state, distinct from `blocked`.

### 5.3 `override set-robustness`

Change the quality-gate strictness for subsequent phases without leaving
`blocked` state. Useful when the current robustness level is causing
over-rejections:

```bash
megaplan override set-robustness --plan <plan-name> --robustness light --reason "Current robustness too strict for this domain"
```

### 5.4 `override set-profile`

Swap the model profile for subsequent retry attempts. Useful when a different
agent model may handle the blocked tasks better:

```bash
megaplan override set-profile --plan <plan-name> --profile sonnet --reason "Switch to stronger model for blocked tasks"
```

---

## 6. Common Block Scenarios

### 6.1 "execute returned result=blocked from quality gates"

**Symptom:** `state.json` latest execute entry has `result: "blocked"`.
`phase_result.json` shows `exit_kind: "blocked_by_quality"` with deviations.

**Fix:**
1. Review deviations in `phase_result.json`.
2. If deviations are spurious (model over-rejected its own work), retry with
   fresh session: `megaplan resume --plan <name>`.
3. If deviations are genuine, use `override set-robustness` to loosen gate
   strictness, or `override abort` and redesign from scratch (`override
   replan` is not valid from `blocked`).

### 6.2 "all pending tasks reported status=blocked"

**Symptom:** Auto-driver detects `tasks_blocked > 0 && tasks_pending == 0`.
Placed in `STATE_BLOCKED` with kind `tasks_blocked`.

**Fix:**
1. Check `tasks/<task_key>/execution.json`, `execution.json`, and `finalize.json` for individual task statuses.
2. If tasks are genuinely unsatisfiable (prerequisite never met), revise plan.
3. If tasks were blocked due to transient errors, resume with fresh session.

### 6.3 "Gate recommended PROCEED, but preflight checks are still blocking"

**Symptom:** Gate handler returns `result: "blocked"` with recommendation
`PROCEED` but preflight blocking. Plan stays at `critiqued`.

> **Note:** This occurs at the `critiqued` state, **not** `blocked` — it is a
> pre-block scenario. From `critiqued`, `override force-proceed` is valid.

**Fix:**
```bash
megaplan override force-proceed --plan <plan-name> --user-approved
megaplan execute --plan <plan-name> --confirm-destructive --user-approved
```

### 6.4 "Gate auto-downgraded to ITERATE"

**Symptom:** Blocking flags remained unresolved after reprompt. Gate
auto-downgrades from `PROCEED` to `ITERATE` and returns `result: "blocked"`.

> **Note:** This also occurs during the gate phase (`critiqued` state), not at
> `blocked`. From `critiqued`, revise is available.

**Fix:**
1. Read `faults.json` for unresolved flags.
2. Revise the plan to address flags, or force-proceed if flags are acceptable
   risks (`override force-proceed` works from `critiqued`).

---

## 7. Preventing Blocks

| Practice | Effect |
|----------|--------|
| Use `--retry-blocked-tasks` in auto runs | Fresh execute passes clear stale blocked statuses |
| Set `--max-blocked-retries 2-3` | Gives the worker more attempts before bailing |
| Add explicit success criteria to plans | Quality gates have clear pass/fail boundaries |
| Use `--with-prep` for unfamiliar domains | Prep phase reduces ambiguity in execution |
| Monitor `phase_result.json` deviations | Catch quality issues before they become blocks |

---

## Concrete References

| Module | Key functions/lines |
|--------|---------------------|
| `megaplan/handlers/execute.py` | `handle_execute()` (L75), `_record_execute_blocked()` (L61), `_is_blocked_retry()` (L51) |
| `megaplan/auto.py` | Blocked retry loop (L1333–1486), tasks_blocked detection (L960–993), bail at `max_blocked_retries` (L1386) |
| `megaplan/_core/workflow.py` | `resume_plan()` — L298–373, blocked special-case (L324) |
| `megaplan/_core/workflow_data.py` | `WORKFLOW` dict — canonical state machine transitions |
| `megaplan/handlers/gate.py` | PROCEED-but-blocking (L214–217), auto-downgrade to ITERATE (L361–375) |
| `megaplan/orchestration/phase_result.py` | `phase_result_guard()`, `emit_phase_result()` |
| `megaplan/types.py` | `STATE_BLOCKED` (L23), `TERMINAL_STATES` (L30) |
