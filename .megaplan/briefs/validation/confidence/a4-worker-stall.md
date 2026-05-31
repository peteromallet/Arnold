# A4 — Does m2 "dispatch as a shared service" keep workers under stall protection?

**Verdict: YES, there is a real stall-protection gap in the shared-dispatch path.**
The seam m2 wants to reuse (`run_loop_worker` in `loop/engine.py:489`) already
demonstrates the bug today: it dispatches with a `shim_state={config,sessions}`
that has **no `active_step`**, and **never calls `set_active_step`**. Every
liveness/heartbeat signal in the worker layer is gated on `active_step.run_id`,
so a service-dispatched worker is invisible to the watchdog.

## 1. How stall/idle/heartbeat detection works today, and what it depends on

There are **two cooperating layers**, and they are joined by exactly one shared
piece of mutable state: `state["active_step"]["run_id"]` and the `state.json`
file mtime in `plan_dir`.

### Inner layer — per-invocation watchdogs (`workers/_impl.py:run_command`)
- **Idle-output watchdog** (`idle_timeout`, used by shannon, `_impl.py:1085/1117`)
  and **pre-first-byte watchdog** (`pre_first_byte_timeout`, used by codex,
  `_impl.py:1864`). Both poll `process.wait()` in ≤1s slices and kill the group
  on a stall, raising `worker_stall` / `codex_pre_first_byte_stall`.
- Crucially these are reset ONLY by real stdout/stderr chunks (`last_output`,
  `first_byte_seen`), never by the liveness heartbeat (`_impl.py:443-450`). That
  separation is the deliberate fix for the codex-wedge masking bug.
- **These bounds do NOT depend on `active_step` or `state.json`.** They are pure
  subprocess-output timers. So a subprocess worker (codex/shannon) dispatched via
  the service still gets its inner kill-on-hang. **The hermes path has no
  subprocess and no `run_command`, so it has NO inner watchdog at all** — its
  only stall protection is the outer layer (below).

### Outer layer — phase-idle monitor (`auto.py:_plan_liveness_mtime`, ~298-362)
- The `megaplan auto` driver watches the **newest mtime of `plan_dir/state.json`
  (+ `execution_batch_*.json`)** as proof a quiet phase is alive. If that mtime
  stops advancing for `idle_timeout` (generous backstop, ~1800s) it kills the
  whole phase. **This is the only net for the in-process hermes path.**

### The bridge — what makes state.json mtime advance during a long quiet turn
- `touch_active_step(plan_dir, run_id=…)` (`state.py:720`) bumps `state.json`.
- Subprocess workers reach it via `_activity_callback_for_state(state, plan_dir)`
  (`_impl.py:583`), which **returns `None` unless `state["active_step"]` is a dict
  with a non-empty `run_id`**. The heartbeat thread routes through this callback.
- The hermes worker reaches it via `_start_heartbeat(..., run_id=run_id)` and
  `_ActivityStream`, where `run_id = state["active_step"]["run_id"]`
  (`hermes.py:835-838, 960`). If `active_step` is absent, `run_id` is `None`, and
  the heartbeat's `if run_id and progress:` guard (`hermes.py:287`) **never
  touches state.json.**

So the whole liveness chain is keyed on `active_step.run_id`. No `active_step` →
the bridge between "worker is alive" and "state.json mtime advances" is severed.

## 2. Does the service path get the same protection, or bypass it?

**It BYPASSES the outer layer and the hermes path entirely.** `run_step_with_worker`
(`_impl.py:2478`) is agnostic — it just forwards `state` to the per-agent worker.
It is the *workers* that read `state["active_step"]`. The m2 service seam
(`run_loop_worker`) hands them `shim_state={config,sessions}`:

- **hermes via service:** `run_id=None` → `_start_heartbeat` no-ops on
  state.json, `_ActivityStream` no-ops → state.json mtime frozen at phase start →
  outer monitor false-stalls a healthy long batch (the exact 2026-05-24
  DeepSeek-V4 silent-false-stall failure mode), AND a genuine wedge is invisible
  except to the elapsed wall-clock. hermes has no inner watchdog, so this is a
  **total loss of stall protection** for the most stall-prone agent.
- **codex/shannon via service:** the inner subprocess watchdogs still fire
  (they're output-timer based, `state`-independent), so a hard hang is caught.
  But `_activity_callback_for_state` returns `None` → the liveness heartbeat
  never touches state.json → the **outer** phase-idle monitor still false-stalls a
  legitimately-long quiet tool turn (e.g. a 25-min codex test run). So even the
  subprocess agents lose the outer "provably-alive" net that prevents premature
  phase kills.

This is not theoretical: the loop engine path ships today with this gap.

## 3. Where do liveness signals go for a non-plan tenant (Arnold), no plan state.json?

Today: **nowhere.** Both layers' liveness write target is `plan_dir/state.json`
via `touch_active_step` / `write_plan_state(mode="active-step-heartbeat")`. For a
tenant with no plan `state.json`:
- `touch_active_step` is a `run_id`-gated, `plan_dir`-scoped write. With no
  `active_step` it's never even called; with no plan dir it has nothing canonical
  to bump.
- The outer monitor's `_plan_liveness_mtime(plan_dir)` has no file to stat.

The liveness contract is **structurally coupled to a plan directory**. A non-plan
caller must supply an equivalent: a `run_id`-bearing active-step record AND a
writable heartbeat sink (a `plan_dir`-shaped scratch dir, or an injected
liveness callback) that whatever supervises the tenant actually watches. Absent
that, Arnold's workers run with subprocess-level kill-on-hang only (codex/shannon)
or **zero** stall protection (hermes), and no supervisor false-stall net.

## 4. What the shared dispatch service MUST carry

The service cannot just carry `{config, sessions}`. To keep workers watched
regardless of caller it must carry/establish, per dispatch:

1. **An `active_step` with a non-empty `run_id`** in the state object handed to
   the worker. This is the single load-bearing field both layers gate on. The
   service should own a `set_active_step`-equivalent at dispatch entry (the plan
   handlers do this via `set_active_step` in `handlers/shared.py:225`,
   `handlers/execute.py:155`, etc. — the loop path skips it, which is the bug).
2. **A liveness sink + the monitor that watches it.** Either (a) a real
   `plan_dir` whose `state.json` the dispatching supervisor polls
   (`_plan_liveness_mtime`), or (b) a caller-injected liveness callback so the
   `touch_active_step` write target is not hard-coded to a plan file. For a
   non-plan tenant, (b) is required; the heartbeat's destination must become a
   parameter, not a constant.
3. **The subprocess watchdog bounds unchanged** (`idle_timeout`,
   `pre_first_byte_timeout`) — these already travel correctly because they're
   `state`-independent, but the service must NOT drop the `activity_callback`
   (today it goes `None` because `active_step` is missing). The callback is what
   converts "subprocess alive" into "supervisor-visible liveness."
4. **hermes-specific:** because hermes has no subprocess watchdog, the service
   MUST guarantee items 1–2 for hermes or hermes loses ALL stall protection.
   This is the highest-severity slice.

## Concrete plan change

- **Target milestone: m2 (the dispatch-as-a-service milestone), as a blocking
  acceptance criterion — not a later hardening pass.** The gap is in the core
  dispatch contract, so it must be designed in.
- The shared dispatch service's request object must include (and the service must
  populate before invoking `run_step_with_worker`): `active_step={run_id, step,
  agent, mode, model, last_activity_at}` AND a `liveness_sink` (plan_dir or
  callback). Add a dispatch-entry call equivalent to `set_active_step` so every
  caller — plan, loop, Arnold — goes through one place that establishes the
  `run_id` and the heartbeat target.
- Make `touch_active_step` / the hermes `_start_heartbeat` and `_ActivityStream`
  accept an injected sink rather than only `plan_dir`, so non-plan tenants get a
  real liveness channel.
- **Regression guard:** add a test that dispatches a hermes step through the
  service with a stubbed streaming provider and asserts the liveness sink is
  written on token progress (and NOT written when the stream is silent). The
  current `run_loop_worker` path would fail this test today — fixing the loop path
  and the service path is the same fix.

## Residual uncertainty

- I confirmed the loop-engine seam empirically reproduces the missing-`active_step`
  shape; I did **not** find an existing megaplan-loop false-stall incident report,
  so the loop path's exposure may be masked by short loop turns or by it not
  running under `megaplan auto`'s outer monitor. Worth a one-line check of whether
  loop runs under the auto driver at all — if it doesn't, only the inner watchdog
  matters for loop, but the m2/Arnold conclusion is unchanged.
- The exact m2 design doc wasn't read here (reasoned from the `run_loop_worker`
  seam the task names as m2's intended path). If m2 already plans to thread an
  `active_step`/run-context through the service, the gap closes — but nothing in
  the current seam does so, and the plan must state it explicitly.
