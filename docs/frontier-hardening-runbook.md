# Frontier-Hardening Runbook — operator HOWTO

Last updated: 2026-05-31.

## Merge state

| Sprint | Branch | Commit | Status |
|--------|--------|--------|--------|
| s3-intent-oracle | `frontier-s3-intent` | `9e91dc6` | DONE — merging to main |
| s4-capability-fence | `frontier-s4-capability` | `6d5e3e4` | DONE — merging to main (reconciled against main's existing `vibecomfy/security/`) |
| s1-oracle-durability | (not started) | — | QUEUED — launchable now |
| s2-dynamic-widget-fence | (not started) | — | READY AFTER REGROUND — m4-m7 landed; consume existing `refuse.py` |
| s5-felt-fidelity-gate | (not started) | — | READY AFTER REGROUND — m4-m7 landed; consume existing delta/change-report primitives |

s3 and s4 are the two existential gates (roadmap §14). Both now exist — the write-enabled-editor
tripwire is satisfiable.

## Launch commands (Codex vendor)

All remaining sprints run with `--vendor codex`. Commands are issued from the repo root.

### s1-oracle-durability — launchable NOW

s1 is independent of scratchpad-emitter m4/m5 and can be launched immediately:

```
PYENV_VERSION=3.11.11 megaplan init \
  --in-worktree frontier-s1-oracle \
  --worktree-from origin/main \
  --clean-worktree \
  --idea-file .megaplan/ideas/frontier-hardening/s1-oracle-durability.md \
  --profile directed \
  --robustness full \
  --depth low \
  --vendor codex \
  --auto-start
```

### s2-dynamic-widget-fence — launch after current-main reground

s2 touches the `emit_ui_json` hot zone, but scratchpad-emitter m4-m7 have now landed on main. Its brief
must be grounded against the landed `vibecomfy/porting/refuse.py` module: s2 should add widget-shape
verdicts/reasons into the existing refusal spine, not rebuild the generic detector. Launch with:

```
PYENV_VERSION=3.11.11 megaplan init \
  --in-worktree frontier-s2-widget-fence \
  --worktree-from origin/main \
  --clean-worktree \
  --idea-file .megaplan/ideas/frontier-hardening/s2-dynamic-widget-fence.md \
  --profile partnered \
  --robustness full \
  --depth medium \
  --vendor codex \
  --auto-start
```

### s5-felt-fidelity-gate — launch after current-main reground

s5 also touches `emit_ui_json`. m4-m7 have landed, and current main already has `layout/delta.py`,
`layout/reconcile.py`, `build_change_report(...)`, and `change_report_out`. s5 should consume those
primitives first and add only the minimal missing felt-fidelity classifier/gate. Launch with:

```
PYENV_VERSION=3.11.11 megaplan init \
  --in-worktree frontier-s5-felt-fidelity \
  --worktree-from origin/main \
  --clean-worktree \
  --idea-file .megaplan/ideas/frontier-hardening/s5-felt-fidelity-gate.md \
  --profile directed \
  --robustness full \
  --depth low \
  --vendor codex \
  --auto-start
```

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
