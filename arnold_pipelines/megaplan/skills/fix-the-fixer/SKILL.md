---
name: fix-the-fixer
description: Launch one durable, mutation-authorized meta-fixer to repair a failed automated fixer and its missed backstop, retrigger ordinary repair, and prove the identified epic or session advances. Use when a watchdog, repair loop, meta-repair loop, or progress auditor ran or should have run but the real chain stayed stuck, repeated stale evidence, claimed false success, or failed to self-correct. Invoke with `--target "EPIC_OR_SESSION_TEXT"`.
---

# Fix the fixer

Repair the repair system, not the epic symptom. Keep the failed fixer and the
meta-fixer as distinct processes so the repair has independent custody and
cannot certify itself.

## Invoke

Require one non-empty text flag:

```text
$fix-the-fixer --target "custody-control-plane-20260714 / m6-exact-contract-and-20260716-1303"
```

Render the implementation goal before launch:

```bash
python "<skill-dir>/scripts/render_goal.py" --target "<epic/session text>"
```

Reject an absent or blank `--target`. Preserve the text exactly as target
orientation; require the agent to resolve canonical IDs and current state from
durable evidence rather than treating the flag as proof.

## Compose the existing guidance

Read and apply `../superfixer-debug/SKILL.md` for the custody walk, four axes,
failure shapes, sibling hunt, and close-the-loop method. When the target is a
cloud session, also use `$megaplan-cloud` for supported status and repair
transport. This skill overrides `superfixer-debug` only in these ways:

- Launch exactly one implementation/recovery agent. Do not fan out or let that
  agent delegate further agents.
- Use the current authorization envelope. Never infer push, deployment,
  restart, broad process control, or direct epic-state mutation authority from
  the desire to recover the epic.
- Prefer the current supported resident/cloud commands and receipts over old
  literal host, branch, wrapper-copy, or process commands in historical text.

Read [historical-runs.md](references/historical-runs.md) when selecting prompt
language, proof gates, or precedent. It separates raw artifacts from inference.

## Launch one durable meta-fixer

Use the resident-managed launch boundary when available. It preserves the
origin envelope, manifest, full log, result, target ref, delivery ownership, and
restart-safe continuation. Pass the rendered goal as the task; classify it as
execution, git-backed when source repair is possible, and D8-D10/high. Preserve
the caller's existing synthesis/delivery role instead of inventing a second
user-facing owner.

If the agent surface supports a persistent `/goal` API, create the rendered
goal in that same single agent session. Otherwise retain the leading `/goal`
and terminal contract in its prompt and manifest. Do not launch another session
merely because a goal API is unavailable.

Use a different durable launcher only when no resident boundary exists and it
still provides equivalent manifest/log/result custody and inherited authority.
If no durable implementation transport exists, stop at that exact gate; do not
substitute an ephemeral chat or raw remote shell.

Recursion guard: when the current process is already the one designated by the
rendered goal, execute it directly and launch no child.

## Enforce the terminal contract

Keep the one agent running through ordinary implementation and test failures.
Accept success only when every applicable gate has raw evidence:

1. Resolve the canonical session/epic, current blocker occurrence, pinned
   resident/runtime target, installed boundary, and allowed effects.
2. Establish visibility, then apply TRACKED, FIXED, INTENT, and CONTEXT to the
   failed fixer and the backstop that missed it.
3. Implement the narrow fixer and backstop repair in a clean isolated worktree;
   preserve dirty launch checkouts, add regressions, review the diff, commit,
   revalidate lineage, and locally integrate only when authorized and exact.
4. Use supported transport to refresh/restart only if explicitly authorized and
   required. Record source-to-installed applicability and scoped receipts.
5. Retrigger the ordinary fixer. Do not hand-advance the epic, weaken a guard,
   or replace ordinary repair with the meta-fixer's direct workaround.
6. Prove from authoritative before/after state that the original blocker is
   cleared and the actual epic/session advanced beyond its frozen cursor.
7. Prove the missed L2/L3 backstop detects the same recurrence, or repair it and
   repeat. Distinguish a new blocker from failure of the original repair.

A launch, PID, exit code, commit, green self-report, wrapper restart, or fresh
heartbeat is not recovery proof. If authority or target lineage blocks a
required effect, return the exact gate with the verified commit retained.

## Return evidence

Report the target and blocker occurrence, first broken layer/axis, missed
backstop/axis, raw run/request/attempt IDs, changed artifacts, tests, reviewed
diff, base/commit/target SHAs, clean worktree, ancestry, installed applicability,
ordinary retrigger receipt, and before/after epic cursor. Label raw evidence,
inference, and unknowns separately. Report to the existing synthesis owner when
one exists; only a top-level delivery owner may reply to the user.
