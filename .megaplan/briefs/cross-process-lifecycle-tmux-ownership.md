# Brief — Own the cross-process lifecycle of detached subagent CLIs (tmux/shannon orphans)

> Ticket: `01KSDJCRSASA09HTABBHWY0FMZ`
> Companion (must land first): `01KSDH58ZPT54VWH7VXQ6PP4X3` → `.megaplan/briefs/subprocess-runtime-centralization.md`
> Suggested run: `partnered//medium +prep` — runs **in the companion's existing worktree** so it builds directly on the companion's `runtime/process.py` (which is not yet on `main`). Both sprints accumulate on the `subprocess-runtime` branch.
>
> ```
> megaplan init .megaplan/briefs/cross-process-lifecycle-tmux-ownership.md \
>   --profile partnered --depth medium --with-prep \
>   --project-dir /Users/peteromalley/Documents/.megaplan-worktrees/subprocess-runtime
> ```
>
> **Do NOT use `--in-worktree`** (that forks a fresh checkout from `main`, which lacks `runtime/process.py`). **Do NOT launch until the companion sprint has fully finished** — two `megaplan` runs in the same worktree concurrently would collide on the same checkout.

## Outcome

megaplan owns the lifecycle of the detached `claude` process that the shannon CLI launches inside a tmux session, so that when a worker is torn down (stall, timeout, kill, normal exit) **zero** orphaned `claude --resume` processes or stray tmux sessions survive. Ownership is deterministic (kill a session megaplan named), not a best-effort sweep. A permanent orphan-detector backstop turns any residual leak into a loud, actionable error instead of a multi-hour silent stall.

## Background — the precise mechanism (verified)

shannon (`@dexh/shannon/index.ts:719`) does NOT spawn `claude` as a normal child. It runs:
```
tmux new-session -d -s <session> -c <cwd> claude … --resume <session-id>
```
So `claude` lives inside a **detached tmux session**, parented to the long-lived **tmux server daemon** — entirely outside megaplan's process tree. `killpg(megaplan_pgid)` structurally cannot reach it; a tmux pane never belongs to the launcher's process group. This is why the 2026-05-24 wedge (plan `vibecomfy-template-refactor-20260524-1400`, ~6h stall) showed orphaned `claude --resume` parented to an unrelated tmux pid: all panes share one server.

The companion sprint (`runtime/process.py`) fixes megaplan's *internal* spawn/kill but cannot close this boundary. The only deterministic way to close a tmux session is by name: `tmux kill-session -t <name>`.

> Note: the original ticket blamed `child_process.spawn(detached:true)`. That is WRONG — there is no such flag; the detachment is the `tmux new-session -d`. Do not implement "remove detached:true." See the corrected ticket body.

## Scope — IN

1. **Deterministic named-session ownership (PRIMARY FIX).**
   - megaplan derives a deterministic tmux session name per worker, keyed to `plan_id` + turn/attempt, and ensures shannon uses *that* name (pass it in if shannon accepts one; otherwise capture the name shannon generates — see prep).
   - On every worker teardown path (stall, timeout, kill, normal completion) megaplan runs `tmux kill-session -t <that-name>` (with the existing SIGTERM→grace→SIGKILL discipline for any residue). This replaces / augments the current `_kill_process_group` teardown in `megaplan/workers/_impl.py`, which only reaches the immediate shannon node wrapper.

2. **Register tmux sessions in the shared external-resource model.** Build on the companion sprint's `megaplan/runtime/process.py`: a named tmux session is an `ExternalProcess` (or equivalent) with a `teardown()` that calls `tmux kill-session`. The same single owner that reaps `Popen` groups and asyncio procs also reaps tmux sessions, so worker exit guarantees reaping uniformly. If the companion's abstraction isn't shaped to admit a non-Popen resource, extend it minimally — do not fork a parallel mechanism.

3. **Orphan-detector backstop (PERMANENT, not the primary fix).** At the start of every execute attempt, assert there are no untracked `claude --resume` processes or unknown tmux sessions belonging to this plan. On violation, raise a concrete `OrphanDetectedError(pid/session, cmd, remediation="…")` rather than proceeding into a silent stall. This is the alarm that proves the ownership model is holding; it must never be the thing doing the actual cleanup in the happy path.

4. **Regression test** in `tests/test_workers.py`: a fake shannon-like wrapper that launches a child inside a detached tmux session (real `tmux new-session -d`, skippable if `tmux` absent in CI), then assert megaplan's teardown reaps it by name within the grace window and the detector reports clean afterward.

## Scope — OUT / Anti-scope

- **Do not "remove `detached:true`"** — it does not exist; that path is a dead end.
- **Do not depend on an upstream shannon change.** A shannon PR (kill its own tmux session on teardown) is a *nice-to-have* and may be mentioned in the plan, but the deliverable must be fully megaplan-side and effective with the shannon version installed today.
- Do not re-do the companion sprint's internal `Popen`/`killpg` centralization — consume it.
- Do not change shannon turn-duration caps, retry policy, or session-id invalidation logic (the d1f3a725 stall-invalidation stays as is).
- Do not broaden to non-shannon CLIs beyond what the shared abstraction naturally covers; the codex path already has its own resume handling.

## Locked decisions

- Primary mechanism is **named tmux session + `tmux kill-session -t`**, owned by megaplan. Not pgrep-by-CLI-args sweeping.
- The detector is a backstop that raises, never the primary cleanup.
- Build on `runtime/process.py` from the companion sprint; one resource-owner, not a parallel tmux-only path.
- Lives primarily in `megaplan/workers/_impl.py` + `megaplan/runtime/process.py`.

## Open questions — resolve in prep (why this run uses --with-prep)

- Does shannon accept an externally-supplied `-s <session-name>`/equivalent, or always self-generate? Read `@dexh/shannon/index.ts` around the tmux launch + arg parsing to confirm. This determines whether "supply the name" or "capture the generated name" is the implementation.
- If megaplan must capture rather than supply: where is the name observable (shannon stdout, a predictable derivation, `tmux list-sessions` diffing)? Pick the least racy.
- Can the companion `ExternalProcess`/registry admit a tmux-session resource cleanly, or does it need a small extension? Inspect whatever `runtime/process.py` shipped.

## Constraints

- Teardown must be idempotent and safe when the session is already gone (`kill-session` on a missing target must not error the worker).
- Must not kill tmux sessions belonging to *other* plans or unrelated projects — scope strictly by the megaplan-owned name. (The wedge involved an unrelated project's tmux; over-broad killing would be a serious regression.)
- POSIX-target; degrade cleanly where `tmux` is unavailable.
- Behavior-preserving for the existing shannon happy path — only teardown/ownership changes.

## Done criteria

- Induced wedge: `pkill -KILL -f "megaplan execute.*<plan>"` mid-flight → **zero** surviving `claude --resume` processes and zero orphaned megaplan-owned tmux sessions within 5s. Proven by the new regression test.
- Teardown addresses the session **by megaplan-chosen/-captured name**, verifiable in the code (no `pgrep "claude --resume"` regex as the primary path).
- Orphan-detector raises a concrete error on a planted orphan and passes clean otherwise.
- tmux sessions reaped through the same owner as Popen/asyncio resources (shared abstraction, not a fork).
- Full existing suite green; no other-plan/other-project tmux session is ever targeted.

## Touchpoints

`megaplan/workers/_impl.py` (teardown + detector), `megaplan/runtime/process.py` (extend resource model for tmux), shannon invocation site (wherever the worker builds the shannon command), `tests/test_workers.py` (new regression test + detector test).

## Evidence

- `/tmp/wedge_diagnostic_report.md`, `/tmp/megaplan_audit_results/03_kill_paths.md` (may not survive to run time).
- shannon source: `~/.nvm/versions/node/v20.19.4/lib/node_modules/@dexh/shannon/index.ts:719` — the `tmux new-session -d … claude --resume` launch confirming the mechanism.
