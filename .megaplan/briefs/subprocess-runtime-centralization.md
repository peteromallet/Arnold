# Brief — Centralize subprocess spawn/kill behind a shared runtime API

> Ticket: `01KSDH58ZPT54VWH7VXQ6PP4X3`
> Suggested run: `partnered//medium` — `megaplan init .megaplan/briefs/subprocess-runtime-centralization.md --profile partnered --depth medium --in-worktree subprocess-runtime`

## Outcome

A single shared module — `megaplan/runtime/process.py` — owns subprocess spawning and group-killing for the whole codebase, and every long-running-subprocess call site is migrated to it. After this sprint, spawning a child the orphan-safe way is the path of least resistance and the orphan-grandchild bug cannot recur by copy-paste. A reviewer checks: the module exists with `spawn()` + `kill_group()`, all listed call sites import them, a lint rule bans bare `subprocess.Popen`/`shell=True` outside the module, and tests cover the group-kill semantics.

## Background — why this exists

When megaplan spawns a long-running subprocess it has historically done:

```python
proc = subprocess.Popen(cmd, ...)   # no start_new_session
proc.terminate(); proc.kill()       # signals only the immediate child
```

Grandchildren (e.g. `shannon → bun → claude`) survive `proc.kill()`, get reparented to PID 1, and hold leases/panes that wedge the next attempt. This is the **exact failure mode that wedged a real run on 2026-05-24** — five consecutive 1800s stalls before `auto` bailed to `manual_review`, ~3 hours lost.

Commits `d1f3a725` (worker) and `1ec7caab` (loop engine) fixed this for two paths by adding `start_new_session=True` + a `_kill_process_group()` helper. But the fix was applied **by copy-paste, not by abstraction** — there are now *two* copies of `_kill_process_group` (`auto.py:157`, `workers/_impl.py:313`) and the raw pattern still lives in ~12 other sites. This sprint replaces the copies with one shared module and migrates the rest.

## Scope — IN

1. **Create `megaplan/runtime/process.py`** exposing:
   - `spawn(*args, **kw)` — wraps `subprocess.Popen`, always `kw.setdefault("start_new_session", True)`, and **raises `ValueError` on `shell=True`** (callers must pass a list, or pass `["/bin/sh", "-c", cmd]` explicitly — still safe under process-group isolation).
   - `kill_group(proc, *, grace_s=3.0)` — SIGTERM the whole process group via `os.killpg(os.getpgid(proc.pid), ...)`, wait `grace_s`, then SIGKILL. This is the existing `_kill_process_group` logic, lifted and generalized; preserve its current label/logging behavior.
   - An async-friendly path covering `asyncio.create_subprocess_exec` (see `rl_training_tool.py:1169`) — either a sibling `spawn_async()` or a `kill_group` that accepts the asyncio process handle. Planner decides the shape; it must cover both sync `Popen` and asyncio handles.

2. **Migrate the existing two helpers** (`auto.py`, `workers/_impl.py`) to import from the shared module; delete the duplicated definitions.

3. **Migrate the remaining vulnerable spawn/kill sites** to `spawn` + `kill_group`:
   - `megaplan/agent/tools/environments/persistent_shell.py:117-120` — `bash -l` login shell; **highest-priority gap per audit** (killing only the shell orphans everything inside it).
   - `megaplan/agent/tools/browser_tool.py` (~824, 838, 1695) — agent-browser CLI + daemon; daemon spawns child browser procs.
   - `megaplan/agent/tools/rl_training_tool.py` — env / trainer / api processes and their `.terminate()/.kill()` sites; plus the `asyncio.create_subprocess_exec` at ~1169/1203.
   - `megaplan/agent/agent/copilot_acp_client.py:179, 183, 239` — `copilot --acp` subprocess.
   - `megaplan/agent/tools/process_registry.py` (~569) — POSIX fallback when PTY terminate fails; route through `kill_group`.

4. **Remove gratuitous `shell=True`** where args are static, converting to list form:
   - `megaplan/loop/engine.py:111` — `_run_user_command()`.
   - `megaplan/handlers/finalize.py:517` — `_capture_test_baseline()` (`pytest --tb=no -q --no-header`).
   - `megaplan/agent/tools/transcription_tools.py:350` — local STT command.
   - `megaplan/agent/environments/patches.py:155` — `RexCommand(shell=True)` to swerex. **Investigate before changing**: orphan risk depends on swerex internals and the args may be intentionally shell-formed. If it can't be safely de-shelled, document why and leave it — do not force it.

5. **Add a lint guard** banning direct `subprocess.Popen(...)` and `shell=True` outside `megaplan/runtime/process.py` (ruff rule, custom check, or grep-based CI test — planner picks the lightest mechanism that already fits the repo). The guard is the load-bearing deliverable: it's what prevents recurrence. Migrations alone only fix today's instances.

6. **Tests** for `spawn`/`kill_group`: assert `start_new_session=True` is set, assert `shell=True` raises, and assert a spawned process *with a real grandchild* is fully reaped by `kill_group` (the grandchild does not survive). Cover the asyncio path too.

## Scope — OUT / Anti-scope

- **`megaplan/loop/engine.py` process-group fix (audit site #2) is ALREADY DONE** by commit `1ec7caab` (`start_new_session=True` present at `loop/engine.py:265`). Do **not** re-fix its kill path. The only loop/engine change in scope is removing the `shell=True` at line 111 (`_run_user_command`). Skip the already-isolated spawn at ~254.
- Do not refactor the *callers'* surrounding logic, retry policies, timeout values, or shutdown ordering — migrate the spawn/kill calls only.
- Do not change subprocess behavior on Windows or add cross-platform abstraction beyond what POSIX `os.killpg` needs; this codebase is POSIX-target. A clean no-op/fallback on non-POSIX is fine but not the focus.
- Do not touch test-only `shell=True` usages.
- No new dependencies.

## Locked decisions

- Module path: `megaplan/runtime/process.py`. Create the `runtime/` package if it doesn't exist.
- `spawn()` forbids `shell=True` (raises `ValueError`); list-args or explicit `["/bin/sh","-c",...]` only.
- `kill_group` semantics: SIGTERM group → grace → SIGKILL group, default grace 3.0s, lifted from the existing `_kill_process_group`.
- One shared definition — the two current copies are deleted, not left as wrappers.

## Open questions for the planner to resolve

- Single `spawn` + handle-polymorphic `kill_group`, vs. separate sync/async entry points? Decide and justify; constraint is one obvious orphan-safe path per spawn style.
- Lint mechanism: existing ruff config, a custom AST check, or a grep-based CI test — pick what's already wired in this repo with least new machinery.
- `patches.py:155` swerex `RexCommand` — can it be de-shelled safely, or is it out of our control? Investigate and document the verdict.

## Constraints

- Behavior-preserving: existing kill timing/logging on the auto and worker paths must not regress (those are the two paths already proven in prod).
- The grandchild-reaping test must actually spawn a grandchild and prove it dies — not just assert flags.
- Net change is expected to be small (~80–150 lines plus tests); a sprawling diff is a signal the refactor drifted into caller logic.

## Done criteria

- `megaplan/runtime/process.py` exists with `spawn` + `kill_group` (+ async coverage), unit-tested incl. the grandchild-reaping case.
- All call sites in Scope §3 import from it; no duplicate `_kill_process_group` definitions remain (`grep -rn "def _kill_process_group" megaplan/` returns nothing outside the shared module).
- All Scope §4 `shell=True` sites are list-form or documented-as-unavoidable.
- The lint guard fails CI on a newly-introduced bare `subprocess.Popen`/`shell=True` outside the module (prove it by a deliberate violation in a throwaway check, then revert).
- Full existing test suite green.

## Touchpoints

`megaplan/runtime/process.py` (new), `megaplan/auto.py`, `megaplan/workers/_impl.py`, `megaplan/loop/engine.py`, `megaplan/handlers/finalize.py`, `megaplan/agent/tools/environments/persistent_shell.py`, `megaplan/agent/tools/browser_tool.py`, `megaplan/agent/tools/rl_training_tool.py`, `megaplan/agent/agent/copilot_acp_client.py`, `megaplan/agent/tools/process_registry.py`, `megaplan/agent/tools/transcription_tools.py`, `megaplan/agent/environments/patches.py`, plus lint config + new tests.

## Evidence (pre-existing audit, on disk at run time)

- `/tmp/wedge_diagnostic_report.md` — root-cause investigation.
- `/tmp/megaplan_audit_results/01_popen_audit.md`, `02_alt_spawn_paths.md`, `03_kill_paths.md` (NEEDS GROUP KILL table), `04_fix_verification.md`.

> Note: `/tmp` evidence may not survive to run time. The call sites and line numbers above are reproduced from the audit and were re-verified against HEAD on 2026-05-24; line numbers may drift slightly — match on symbol/pattern, not line number.
