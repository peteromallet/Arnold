# Per-epic runtime + fixer targeting — desired end state (2026-08-09)

**Status:** implementation review artifact. The operator's goal: every epic has
its own executor (runtime) and its fixer knows to edit **that epic's branch**,
with the whole process streamlined at 10+ concurrent epics.

## The model (three invariants)

1. **A runtime is a manifest, not a path.** Every executing thing resolves
   through one per-epic `runtime-manifest.json` (`epic.branch`,
   `epic.worktree_path`, `epic.runtime_root`, `epic.expected_head`,
   `epic.repair_bin`). One stable bootstrap path
   (`ARNOLD_RUNTIME_MANIFEST` / `/workspace/.megaplan/runtime-manifest.json`);
   legacy launchers (env `*_SRC` aliases, `Path(__file__).with_name(...)`,
   hardcoded pins) are retired, not documented.

2. **The fixer fixes the runtime it was born in.** Dispatch always binds the
   repair loop to a manifest. Its push target is **derived** — the manifest's
   `epic.branch` — never configured. A fail-closed delivery gate refuses any
   repair `git push` whose target is not the manifest-declared epic branch.
   `SYNC_BRANCH` resolves manifest-first in every fixer wrapper, with the
   legacy `editible-install` default applying only to manifest-less runtimes.

3. **Only promotion mutates shared state.** `arnold-promote` is the sole
   writer of the base: staged candidate -> canary generation verified in a
   separate namespace -> CAS push -> promotion journal -> atomic active-
   generation switch, previous generation retained for rollback.
   `arnold-close` (two-phase) + `arnold-gc-sweep` (closed-only, restore-
   proven) own teardown. Nothing else ever advances `base/editable-install`.

## Economics at 10+ epics (decided)

- **Worktrees, never clones** — `git worktree add` shares objects.
- **One frozen deps venv** — requirements do not change; the venv is built
  once from a lockfile, never mutated, shared by all epics. It is still a
  *generation* (content-addressed, pointer-switched) so a future deliberate
  dep change spawns a new generation with canary + rollback.
- **PYTHONPATH, not editable installs** — per-epic code resolves by putting
  the worktree ahead of site-packages. No per-epic `pip install -e`, no
  `.pth` pointers, no install-refresh step in repairs; editing the tree is
  editing the runtime. Console scripts go through `python -m` or thin shims.
- **Per-epic = worktree + manifest only** — creation is seconds; the
  editable-install machinery is deleted.

## What this change set implements (committed diff)

| File | Change |
|---|---|
| `cloud/wrappers/arnold-supervisor-runtime-lib` | `arnold_runtime_manifest_path` + `arnold_runtime_manifest_epic_field` helpers (manifest-first, JSON fallback, silent on absent) |
| `cloud/wrappers/arnold-repair-loop` | `SYNC_BRANCH` resolves from manifest `epic.branch` before env/default; delivery git shim gains a fail-closed push-target gate (`ARNOLD_REPAIR_MANIFEST_BRANCH`) |
| `cloud/wrappers/arnold-kimi-goal-operator` | `SYNC_BRANCH` manifest-first |
| `cloud/wrappers/arnold-meta-repair-loop` | `SYNC_BRANCH` manifest-first |
| `chain/execution_binding.py` | `require_editable_runtime_match` defaults **true** on cloud launches (`MEGAPLAN_TRUSTED_CONTAINER=1`), explicit spec value still wins |
| `tests/cloud/test_watchdog_wrappers.py` | 3 new tests: manifest branch resolution in all fixer wrappers, supervisor-lib helpers, shim behavioral gate (refuses `push origin main`, allows manifest branch, legacy when unset) |
| `tests/.../test_chain_execution_binding.py` | cloud default + explicit-override test |

## Codex review outcome (2026-08-09)

GPT-5 codex reviewed the end state vs the first implementation: **MISS** with
five defect classes. Its top fixes are landed in commit `d62ceef2e8`:

1. **Delivery broker** — the PATH shim bakes the real git path (no env leak),
   refuses `--all`/`--mirror`/force/URL-remote/multi-refspec/non-`origin`
   pushes, and the repair-loop verifies **post-dispatch** that only the
   manifest-declared epic branch moved on the remote (ls-remote before/after
   in the supervisor context — the verifiable control; the shim is a
   deterrent).
2. **Fail-closed manifest authority** — a present manifest without
   `epic.branch` exits 78 in repair-loop/kimi/meta instead of silently
   falling back to the shared branch.
3. **Single-writer create lock** — `arnold-runtime-create` flocks (mkdir
   fallback on macOS) so 10+ concurrent creations cannot race the pointer.

Remaining (documented, not yet implemented): launch routing through
`arnold-runtime-create` (preflight manifest requirement), the frozen-venv
model implementation, and generation-level CAS/fencing for promotion.

## Already present (prior work, verified)

- `arnold-runtime-create` / `arnold-promote` / `arnold-close` /
  `arnold-gc-sweep` wrappers + `tests/cloud/test_runtime_lifecycle.py`.
- Watchdog manifest resolution (`runtime_manifest_field epic.repair_bin` /
  `epic.runtime_root`, fail-closed on non-executable declared bin,
  `ARNOLD_REPAIR_RUNTIME_SRC` threaded at dispatch).
- `base/editable-install` seeded on origin (currently 130 commits behind
  main — a separate decision).

## Not yet enforced (gaps this review should confirm)

- Per-epic manifest **creation at launch**: nothing yet *requires* a manifest
  for a cloud epic (preflight gate).
- `arnold-runtime-create` push-at-creation is implemented but the lifecycle is
  opt-in; launch does not yet route epics through it.
- `SYNC_BRANCH` legacy default still exists by design for manifest-less
  runtimes; the audit/meta-loop should flag any manifest-bound repair that
  falls back to it.

## Live box state (2026-08-09 recovery)

- Resident container recovered (dirty RO runtime tree stashed — 4 box-only
  hot-fixes preserved in `stash@{0}`; stale seed-consumption marker removed).
- Discord resident listener up; scheduler unit pin fixed (was 234ac3524, now
  the r7 runtime HEAD 395a946e) and green; watchdog relaunched from the
  operator-declared tree `arnold-main-20260809` (tmux `watchdog`, 300s sweep).
- Deliberately masked: watchdog-ensure / progress-audit / resident-ensure
  timers (zero-authority design); the fenced `liveness_unknown` session cohort
  and the stale `vj24-migration` worker are parked fail-closed, not repaired.
