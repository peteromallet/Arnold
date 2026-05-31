# Root cause — Chain state machine: where "done" is written, and why it's wrong

Lens: **where the chain writes `status:"done"` for a milestone**. All paths
verified against source. The chain layer does *zero* independent completion
checking; it copies whatever terminal status `auto.drive()` reports.

## 1. Exactly where `done` is written

There are **two** write sites, both in `run_chain()` in
`megaplan/chain/__init__.py`. For the hardening epic every milestone has
`pr_number: None` (no `branch:` in the spec → `use_pr` is `False`), so the
relevant site is the advance/skip block:

```python
# megaplan/chain/__init__.py:1417-1426
        # advance or skip
        state.completed.append(
            {
                "label": milestone.label,
                "plan": plan_name,
                "status": outcome.status,   # <-- the recorded "done"
                "pr_number": state.pr_number,
                "pr_state": state.pr_state,
            }
        )
```

`outcome.status` is also persisted as `state.last_state` at
`__init__.py:1360` (`state.last_state = outcome.status`). The second write
site (`__init__.py:1231-1239`) hard-codes `"status": "done"` but only fires
on the `STATE_AWAITING_PR_MERGE` resume path, which the no-branch hardening
chain does not take.

The decision to *append at all* is gated by `_handle_outcome`:

```python
# megaplan/chain/__init__.py:1108-1110
        status = outcome.status
        if status == "done":
            return "advance"
```

So the chain's notion of "done" is **purely** `auto.drive`'s
`DriverOutcome.status == "done"`. No diff check, no branch check, no commit
check, no plan-on-disk check anywhere in this block.

## 2. The condition that triggers the write

`outcome.status == "done"` is produced in **one place** —
`megaplan/auto.py:1363-1394`. When the polled plan state is in
`AUTOMATION_TERMINAL_STATES` (auto.py:1307), drive maps it:

```python
# megaplan/auto.py:1363-1369
            terminal_status = {
                STATE_DONE: "done",
                STATE_ABORTED: "aborted",
                ...
            }.get(state, state)
```

So the trigger is: **the plan's `state.json` `current_state` field equals
`STATE_DONE` ("done")** when `megaplan status` is polled. It is *not* an exit
code, not "decompose finished", not "drive() returned". A stall, cap, or
no-next-step returns `stalled`/`cap`/`failed` (auto.py:1492, 1553, 1705,
2243) — never `done`. **`done` is positive: the plan literally reached the
terminal `done` state.**

Legitimately, `done` is only reachable via execute→review:

```python
# megaplan/_core/workflow_data.py:75-76
    STATE_EXECUTED: [
        Transition("review", STATE_DONE),
    ],
```

(or the `with_feedback` rewire executed→reviewed→feedback→done,
workflow.py:206-208; or `verify-human`, workflow_data.py:78-79). **There is
no transition into `done` that skips execute.**

## 3. Why m6a (abandoned after planning) still reports `done`

It cannot via the workflow — so the chain layer did not infer it. The chain
copies `outcome.status`, and `outcome.status=="done"` *requires* the plan to
have hit `current_state="done"`, which requires execute→review to have run.

This means the gap is **not** "absence-of-error read as done." The chain
genuinely believed the plan reached `done` because something wrote
`current_state="done"` into the plan's `state.json` — yet no diff/branch/
commit landed. The plan dirs no longer exist on disk
(`m6a-surface-config-cleanup-*` not found anywhere under the repo), so the
`done` was written in the (now-torn-down) workspace and the chain trusted it
without ever cross-checking landed artifacts. The chain has **no predicate
that ties `done` to a non-empty diff**, so a plan whose execute produced no
real change — or whose state was advanced to `done` without honest
execute/review — sails through.

## 4. Where the gap is + the correct predicate

The gap is the advance block, `megaplan/chain/__init__.py:1379-1432`: on the
no-PR path it records `done` with **no verification step**. The PR path at
least calls `_commit_and_push_phase` + `_pr_state` (1379-1416); the no-PR
path records `done` blind.

Correct completion predicate (what's missing): before appending
`status:"done"`, the chain must positively confirm the milestone *landed
work* — e.g. require `outcome.final_state == STATE_DONE` **and** the plan's
`execute`/`review` history entries exist with successful results, **and** a
non-empty diff/commit was produced for the milestone (the chain already has
`_latest_execute_result` / `_latest_execution_batch_all_tasks_done`,
__init__.py:939-1016, but only uses them for blocked-execute recovery, never
as a done-gate). Without that, "done" = "the plan said done," which is
exactly the unreliable signal observed.

---
**4-line summary**
1. `done` is written at `megaplan/chain/__init__.py:1418-1426` (and
   `state.last_state`, :1360), copied verbatim from `DriverOutcome.status`.
2. The triggering condition is `outcome.status=="done"`, set only at
   `auto.py:1363-1369` when the plan's `state.json` `current_state=="done"`.
3. It's wrong because the chain does **zero** independent verification — no
   diff/branch/commit/execute-history check — it trusts the plan's
   self-reported terminal state.
4. Fix: gate the `done` append on a positive landed-work predicate
   (execute+review history + non-empty diff), reusing
   `_latest_execution_batch_all_tasks_done` instead of trusting `current_state`.
