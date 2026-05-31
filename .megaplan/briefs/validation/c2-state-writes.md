# C2 — State-write ownership & schema versioning (CODE-VALIDATION)

Validated against CURRENT code on 2026-05-28. Brief dated 2026-05-23; the
subsystem was substantially refactored May 24–28. The single most important
finding: **the four "divergent write strategies" the brief treats as the core
hazard have since been UNIFIED behind one locked, atomic primitive,
`write_plan_state(mode=...)`** in `megaplan/_core/state.py`. Several of the
brief's hazards are therefore already mitigated; the schema/typing gaps remain.

---

## Claim 1 — `save_state_merge_meta` call-site count & distribution

Brief: "exactly 30 sites, only 1 inside `_finish_step`, rest scattered
(override ~9, execute ~7)."

CURRENT reality:
- Definition: `megaplan/_core/state.py:626` (now a thin wrapper over
  `write_plan_state(mode="merge-meta-list")`, body at :641-648).
- **36 actual call sites** (non-test), not 30. Distribution by file:

| file | calls |
|---|---|
| `megaplan/handlers/override.py` | 10 |
| `megaplan/handlers/execute.py` | 7 |
| `megaplan/execute/batch.py` | 5 |
| `megaplan/handlers/shared.py` | 3 (incl. the one inside `_finish_step`) |
| `megaplan/handlers/review.py` | 3 |
| `megaplan/handlers/critique.py` | 2 |
| `megaplan/cli/resolutions.py` | 2 |
| `megaplan/_core/state.py` | 2 (1 = def at :626, 1 = self-call at :878) |
| `megaplan/handlers/verifiability.py` | 1 |
| `megaplan/execute/timeout.py` | 1 |
| `megaplan/execute/step_edit.py` | 1 |

`megaplan/_core/__init__.py` lines 118/273 are the import + `__all__` export,
not calls. `resolutions.py` lines 32/180 are local imports.

VERDICT: **PARTIALLY CORRECT** — distribution shape is right (override-heavy,
execute next), but the count is 36, not 30, and the "scattered across many
handlers" concern stands. Note: scatter is now lower-risk because every site
funnels through the locked `write_plan_state`.

## Claim 2 — FOUR divergent write strategies with OPPOSITE merge defaults

Brief: `save_state_merge_meta` (in-memory wins), `_merge_state_to_disk` (disk
wins), `touch_active_step` (no merge), `save_state` (blind overwrite).

CURRENT reality — all four still exist as named functions but are now **modes
of a single primitive** `write_plan_state` (`_core/state.py:329-437`), which
holds `plan_state_lock` for the entire read-modify-write and ends in
`atomic_write_json` (`:435-436`). Merge semantics confirmed:

- `save_state` → `write_plan_state(mode="replace")` (`state.py:210-211`). Mode
  `replace`: `next_state = dict(state)` (`:355-358`) — **blind overwrite**.
  CONFIRMED. (Still atomic + locked, unlike a raw write.)
- `save_state_merge_meta` → `mode="merge-meta-list"` (`:641-646`). For the four
  append-only meta lists it takes the **union** (on-disk first, in-memory
  appended; de-duped) via `_merge_meta_lists` (`:596-623`); for all other keys
  **in-memory wins** (`next_state = dict(state)`, `:402`). CONFIRMED — the
  comment at `:613-615` explicitly states on-disk takes precedence for the
  merged lists so a concurrent override is not lost.
- `_merge_state_to_disk` (`megaplan/_pipeline/executor.py:100-134`) →
  `mode="executor-key-merge"` (`:361-372`). **Disk wins** except for keys the
  executor explicitly owns (`executor_owned_keys`), where executor value wins.
  CONFIRMED.
- `touch_active_step` (`state.py:720-745`) → `mode="active-step-heartbeat"`
  (`:383-398`). Reads disk, mutates only the matching `active_step` (guarded by
  `run_id`), preserves everything else — **no merge / no clobber of other
  keys**; skips the write entirely if run_id mismatches (`should_write=False`,
  `:391`). CONFIRMED.

VERDICT: **CONFIRMED on semantics, but the framing is STALE.** The "opposite
defaults" are real and intentional (replace vs disk-wins vs union vs
heartbeat), but they are no longer four independent ad-hoc writers racing on the
file — they are explicit modes of one locked atomic primitive. The brief's
implied hazard ("uncoordinated writers clobber each other") is largely closed.

## Claim 3 — InProcessHandlerStep 3-key allowlist diff

Brief: bridge diffs only `("current_state","iteration","last_gate")`.

`megaplan/_pipeline/stages/inprocess_step.py:85-88`:
```python
state_patch: dict[str, Any] = {}
for key in ("current_state", "iteration", "last_gate"):
    if after.get(key) != before.get(key):
        state_patch[key] = after.get(key)
```
Returned as `StepResult(..., state_patch=state_patch)` (`:91-96`).

VERDICT: **CONFIRMED, verbatim.** Any other key a handler mutates on disk
(meta, history, plan_versions, sessions, resume_cursor, latest_failure) is NOT
surfaced to the executor's tracked state. In practice the handler already wrote
those to disk itself, and `executor-key-merge` makes disk win for them, so the
narrow allowlist is consistent with the merge design — but it does mean the
executor's in-memory `current_state` view is deliberately partial.

## Claim 4 — No `schema_version` on state.json / chain_state.json

CURRENT reality: `schema_version` / `SCHEMA_VERSION` exists in
`megaplan/receipts` (`schema.py:25`), `megaplan/bakeoff` (`state.py:12`,
`comparison.py:14`), and `megaplan/agent/hermes_state.py:29` (SQLite, v5 with a
migration ladder). A grep of all of `megaplan/` shows **NO schema_version
marker anywhere on plan `state.json` or `chain_state.json`.**

VERDICT: **CONFIRMED, still missing.** `load_plan_from_dir`
(`state.py:93-101`) does ad-hoc legacy migration by sniffing values
(`current_state in {"clarified","evaluated"}`, missing `last_gate`) rather than
a version number — exactly the brittle pattern a version field would replace.

## Claim 5 — PlanState / PlanMeta TypedDicts incomplete; no load/save validation

Defs in `megaplan/types.py` (NOT `_core/types.py`): `PlanMeta` :113,
`ActivePhase` :140, `PlanState` :206.

Per-field check (written to state at runtime vs present in the TypedDict):
- `last_gate` — written top-level (`state.py:300,306`; `workflow.py:215`) but
  **NOT a field of `PlanState`**. A `LastGateRecord` type exists (`types.py:193`)
  but is marked *deprecated* and is **not referenced by `PlanState`**. GAP CONFIRMED.
- `current_invocation_id` — written into `meta` (`state.py:716`) but **NOT in
  `PlanMeta`**. GAP CONFIRMED.
- `epic_id` — read/written via `meta` and top-level (`workflow.py:374`,
  `control.py:138-146`, `plan_repository.py:402`) but **NOT in `PlanState`/`PlanMeta`**.
  GAP CONFIRMED.
- `worktree` — **brief WRONG**: `worktree` is not a plan-state field; the only
  `worktree` tokens in types.py (:659,661) are sync-status string constants, and
  runtime `worktree` is a hermes CLI arg (`hermes_cli/main.py`). Not a PlanState gap.
- `tiebreaker_count` — **brief WRONG**: not a state.json field at all; it is a
  computed audit metric (`audits/audit_engine.py:72`, `plan_audit.py:72`).
  Not a TypedDict gap.

Validation: NO structural/schema validation on load. `load_plan_from_dir`
only does value-level legacy migration. On write, `write_plan_state` validates
**only** `current_state` against `CANONICAL_PLAN_STATES`
(`_validate_plan_state_for_persist`, `state.py:248-263`, called at :433-434);
no field-presence/type validation of the rest.

VERDICT: **MOSTLY CONFIRMED** (last_gate, current_invocation_id, epic_id all
missing from the TypedDicts; no real load/save schema validation), but TWO of
the five named fields (worktree, tiebreaker_count) are not actually PlanState
fields — the brief mis-attributed them.

## Claim 6 — read_json: raises vs returns {} on corrupt state

`megaplan/_core/io.py:272-273`:
```python
def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
```

VERDICT: **RAISES** `json.JSONDecodeError` (and `UnicodeDecodeError`) on
corrupt/garbled content; never returns `{}`. The write path wraps it:
`_read_state_for_write` (`state.py:266-290`) catches both and converts to
`CliError("corrupt_state_write", "M3B_HALT_CORRUPT_STATE_WRITE: …")`, and the
executor takes a forensic backup before re-raising
(`executor.py:129-134`). But **direct `read_json` callers** —
`load_plan_from_dir` (`state.py:94`), `PlanRepository.load_state`
(`plan_repository.py:175`), `tiebreaker.py:259`,
`prompts/tiebreaker_orchestrator.py:296` — get the raw exception with no graceful
fallback. So corrupt state surfaces loudly (good) but inconsistently
(handled-with-backup on write, bare-traceback on several reads).

## Claim 7 — External current_state writers & atomicity

| writer | location | path | atomic? | locked R-M-W? |
|---|---|---|---|---|
| `_mark_blocked_execute_as_executed` | `chain/__init__.py:1019-1033` | `write_plan_state(mode="patch-many")` | YES | YES (re-reads under lock) |
| `resume_plan` | `_core/workflow.py:339-368` | `repo.save_state` → `mode="replace"` | YES | NO — writes a `dict(previous_state)` snapshot read earlier; replace clobbers |
| `record_lifecycle_failure` | `store/plan_repository.py:368-400` | `load_state()` then `save_state()` (replace) | YES (per write) | NO — load and save take the lock separately; read-modify-write race window |
| `_recover_execute_callback_failure_state` | `auto.py:818-866` | reads raw un-locked `json.load`, writes `write_plan_state(mode="patch-many")` | WRITE YES | decision read is lock-free dirty read; write re-reads under lock |

All four EXIST. All four now end their write through `write_plan_state` /
`atomic_write_json`, so **no torn writes**. The residual hazard is **lock-free
read-modify-write**: `resume_plan` and `record_lifecycle_failure` snapshot
state, mutate in memory, then `mode="replace"` — which blind-overwrites any
concurrent override/heartbeat append that landed in between (the very window
`save_state_merge_meta` was built to defend, but these paths don't use it).
`chain_state.json` (`save_chain_state`, `chain/__init__.py:553-557`) is atomic
(tmp + rename) but has NO lock and NO schema_version.

---

## ASSESSMENT — is "fix state-write discipline + add schema_version FIRST" the right pre-Phase-0 foundation?

Position: **Half-right, and the half that's right is narrower than the brief assumes.**

1. **Write-atomicity / single-writer discipline is already largely done.** The
   `write_plan_state(mode=...)` unification (post-brief) closed the headline
   "four uncoordinated writers" hazard: every plan-state mutation is now locked
   + atomic. Re-spending a pre-Phase-0 to "fix state-write discipline" broadly
   would mostly re-litigate solved ground. The *remaining* discipline gap is
   specific and small: the two **lock-free read-modify-write replace paths**
   (`resume_plan`, `record_lifecycle_failure`) that can blind-overwrite a
   concurrent meta append, plus `chain_state.json` having no lock. Those are
   worth a targeted fix, not a foundational phase.

2. **`schema_version` is genuinely absent and genuinely foundational** — if any
   later phase changes the state shape, the current value-sniffing migration in
   `load_plan_from_dir` is the brittle thing that breaks, and adding a version
   marker is cheap, low-risk, and pays off the moment a migration is needed.
   This part of "do it first" holds.

3. **The TypedDict gaps (last_gate, current_invocation_id, epic_id) are
   correctness-adjacent, not foundational** — they make refactors error-prone
   (no type coverage on fields the code actually reads/writes) but nothing
   *breaks* if deferred; they can ride alongside the schema_version work.

What breaks if skipped entirely: the lock-free replace paths can silently drop
an operator override/note that lands during a resume or failure-record; and the
first state-shape change in a later phase lands without a migration spine,
forcing another round of value-sniffing. Neither is a hard blocker, so the
honest recommendation is a **lean pre-Phase-0**: add `schema_version` + a
load-time validator, and convert the two replace-based external writers to
`merge-meta` or a locked R-M-W — rather than a broad "fix all state writes" phase
that the unification already obsoleted.

Unknown-unknown: `mode="replace"` (`save_state`) is the default for the most
generic writer and is a blind overwrite. I did not enumerate **every**
`save_state`/`mode="replace"` caller to confirm none of them snapshot-then-replace
across a long-held lock window the way `resume_plan` does — that population
(not just the four named external writers) is the place a silent-clobber
regression would most plausibly hide.
