# Execute failure-driven tier escalation

Spec: `partnered//medium` (`--profile partnered --robustness full --depth medium`)

## 1. Outcome

Make execute-stage tier escalation **failure-category-aware** and **per-task**.

Today `auto.py` already escalates, but bluntly: it counts *every* consecutive execute
failure into one streak and, once `execute_fail_streak >= escalate_after_fails`
(default 2), pins the **entire execute phase** to the next distinct tier
(`--phase-model execute=<spec>`). This is category-blind (it counts failures a stronger
model can't fix, e.g. external prereq blocks) and coarse (one hard task drags every
trivial task up to Opus).

Replace it with: classify each execute failure by category, escalate **only** the
categories where a stronger model is plausibly the fix, and pin **only the failing
task(s)** to a bumped effective complexity tier — leaving cheap tasks on cheap models.
Mental model: **failure-driven complexity re-rating** — certain failures are evidence the
planner under-rated a task's tier; bump that task and re-run.

A reviewer checks: a failing escalatable task re-runs at the next distinct tier while
sibling cheap tasks stay cheap; non-model failures (external prereq) never escalate and
route to manual_review; escalation events are recorded for diagnosis.

## 2. Scope

IN:
- Thread the failure **category** (`ExitKind` + the `blocked_by_quality` sub-reason) to
  the escalation decision point in `auto.py`.
- A **category policy** governing, per category: escalate at all? how many same-tier
  retries first? jump size.
- **Per-task** (not per-phase) escalation: bump the failing task's effective complexity
  tier and re-run; let existing per-batch routing pick the model.
- Reuse `_next_escalation_tier` (already skips same-spec tiers; already returns None →
  manual_review at the ceiling).
- Record escalation events `{category, retries_before_escalation, from_tier, to_tier,
  reason}` in run history.
- Two guardrails (see §5).

OUT / anti-scope:
- Do NOT change the 1–5 complexity **scoring** in finalize.
- Do NOT touch plan/critique/revise/review escalation or the `override` commands.
- Do NOT edit the tier-ladder definitions in `megaplan/profiles/*.toml`.
- Do NOT add new user-facing CLI flags beyond what's strictly required; reuse
  `--escalate-after-fails` semantics.
- `external_error` (quota/balance) handling: map to a lateral provider switch at most;
  if a clean provider-switch mechanism doesn't already exist, record the category and
  defer the switch rather than building a provider-routing subsystem.

## 3. Locked decisions

- **Governing principle:** escalate only when a stronger model is plausibly the fix.
- **Category policy table:**

  | Category | Escalate? | Policy |
  |---|---|---|
  | `context_exhausted` | yes, immediately | next bigger-context tier, 0 same-tier retries |
  | `blocked_by_quality` (semantic sub-reasons: all-skipped / wrong-approach / sense-check fail / missing evidence) | yes, after 1 retry | 1 same-tier retry, then +1 tier |
  | `internal_error` | retry-then-escalate | 1 same-tier retry, then +1 tier |
  | `timeout` | remediate-then-escalate | first `batch=1` + widened idle cap on SAME model, then +1 tier |
  | `external_error` (quota/balance/auth) | lateral | provider switch if available, else record + defer |
  | `blocked_by_prereq` | NO | route to manual_review; never increments the streak |

- **Per-task pin** over per-phase pin.
- **Reuse** `_next_escalation_tier` + the manual_review ceiling.
- **Backward compatible:** when category info is absent, behavior degrades to the current
  streak-based escalation.

## 4. Open questions (planner must resolve — do not invent silently)

- Exact mechanism to pin a single task's effective tier given current per-batch routing
  (`execute/batch.py:1094-1140`): is the failing task pulled into its own batch, or is a
  tier-override carried on the task record that `compute_batch_complexity` reads?
- How `retries_first` interacts with the existing `--retry-blocked-tasks` /
  fresh-invocation retry semantics so retries aren't double-counted.
- Where category tagging best lives: emitted in the execute handler's `phase_result`, or
  recomputed in `auto.py` from `phase_result.json`.

## 5. Constraints / guardrails

- **Never strand a run:** `blocked_by_prereq` never escalates → manual_review.
- **Scope-drift false-positive guard:** a `blocked_by_quality` from scope drift escalates
  only if the drift is in files the run *claimed to touch* — don't escalate on inherited
  dirty-base noise (see prior incident: worktree carries main's dirty state into review).
- **False-stall timeout guard:** remediate with `batch=1` / widened idle cap on the SAME
  model before spending a tier — that's what fixed the real Shannon/Codex stall incidents,
  not bigger models.
- **Monotonic + capped:** escalation only goes up, never oscillates, terminates at the
  ceiling (manual_review) — no infinite loop.

## 6. Done criteria

- A failing task of an escalatable category re-runs at the next distinct tier; sibling
  cheap tasks are unaffected. (test)
- `blocked_by_prereq` does not increment escalation and routes to manual_review. (test)
- `context_exhausted` escalates on first occurrence. (test)
- Escalation events recorded in history with category + from/to tier. (test/inspection)
- All existing escalation tests still pass.

## 7. Touchpoints (file:line anchors)

- `megaplan/auto.py:2573-2582` — failure detection (`execute_failed`, `exit_kind`)
- `megaplan/auto.py:2605-2687` — escalation trigger (streak → next tier)
- `megaplan/auto.py:727-755` — `_read_execute_tier_ladder`
- `megaplan/auto.py:758-786` — `_latest_execute_max_tier`
- `megaplan/auto.py:789-825` — `_next_escalation_tier` (skips same-spec; ceiling→None)
- `megaplan/auto.py:2070-2083` — escalation pin application (`--phase-model execute=`)
- `megaplan/execute/batch.py:517-551` / `1094-1140` — per-batch tier routing
- `megaplan/_core/io.py:133-165` — `compute_batch_complexity`
- `megaplan/_core/state.py:808-877` — `make_history_entry`
- `megaplan/orchestration/phase_result.py:19-32` — `ExitKind` enum

## 8. Anti-scope (restate)

Don't refactor the finalize scorer, the tier ladders, the `override` commands, or the
prep/critique/review escalation. This sprint changes only the **execute** failure→tier
path and its history recording.
