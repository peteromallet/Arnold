# Frontier-Hardening Runbook — completion record

**Status:** Historical completion record. All frontier-hardening sprints have landed on main.

Last updated: 2026-05-31.

## Merge state

| Sprint | Branch | Commit | Status |
|--------|--------|--------|--------|
| s3-intent-oracle | `frontier-s3-intent` | `9e91dc6` / integrated in `e5772b0` | LANDED |
| s4-capability-fence | `frontier-s4-capability` | `6d5e3e4` / integrated in `e5772b0` | LANDED |
| s5-felt-fidelity-gate | `frontier-s5-felt-fidelity` | `fb192d2` | LANDED via PR #34 |
| s2-dynamic-widget-fence | `frontier-s2-widget-fence` | `92dfdb8` | LANDED via PR #36 |
| s1-oracle-durability | `frontier-s1-oracle` | `38b01ac` | LANDED via PR #35 |

All five frontier-hardening sprints have landed on `main`. The final main commit for the sequence is
`38b01ac5651b5e0877fc426cc783b73a8fa1d46f` (`Harden oracle durability checks`).

Post-merge GitHub checks on that commit:

- `ci`: success, including the Layer-3 Comfy oracle gate.
- `canonical-parity`: success.
- `Strict Ready`: success.

s3 and s4 are the two existential gates (roadmap §14). Both exist on main, and the remaining
durability/trust gates are also landed, so the write-enabled-editor tripwire is satisfiable from
this frontier-hardening sequence's side.

## Launch commands

Historical launch commands were removed from this runbook after completion to avoid stale
"not started" operator guidance. Use the committed sprint ideas under
`.megaplan/ideas/frontier-hardening/` and the merged PR history if a future follow-up needs to
replay or audit the work.

## Babysit/watchdog gotchas

These were discovered during the s3 and s4 runs — both needed manual intervention.

### Idle-watchdog false-kill during `execute`

Megaplan's idle-watchdog can prematurely kill a long `execute` phase. The harness shows
`finalized` while the agent is deep in execution work — the watchdog sees no status change
and fires. **Mitigation:** resume with a raised stall threshold:

```
--stall-threshold 40
```

Both s3 and s4 required this.

### Harness reaches `done` but deliverable is UNCOMMITTED

If the harness loop exits with `done` status but leaves the deliverable staged or unstaged
in the worktree, **do not trust it blindly** — spot-check the deliverable first (tests pass?
code looks real?), then commit and push it yourself. Both s3 and s4 hit this edge case;
the harness considers itself finished but the PR was empty until manual commit+push.

## Shipping tripwire reminder

s3 (intent-oracle) and s4 (capability-fence) are the **two existential gates** that gate a
future write-enabled editor per roadmap §14. With both now landed/landing on main, that
tripwire is satisfiable. No write path to a user's canvas ships until both exist — and
they now do.
