# Pre-mortem P3 — Self-reference / dogfooding hazard

**Lens:** the epic modifies the machinery (`auto.py`, the executor, the state schema, `chain`)
*while a `megaplan chain` built on that same machinery is driving it.* Worked backward from a
mid-epic (≈m3) corruption/deadlock.

**Verdict (one line):** Driving this epic ON megaplan itself, off an **editable install** of the
working tree, with `git pull` of merged milestone code into that same tree between milestones, is
**unsafe as written**. It must be driven by a **pinned, frozen engine** (a copy/branch that the
epic never modifies), and the **state schema must be frozen until the last milestone**.

---

## How the chain actually drives an epic (ground truth from code)

- `megaplan chain` → `run_chain` (`megaplan/chain/__init__.py:1132`) is a **single long-lived Python
  process**. At import it binds `from megaplan.auto import drive as auto_drive` (`chain/__init__.py:65-74`).
- Per milestone it calls `auto_drive(...)` **in-process** (`_drive_plan`, `:909-930`). So the *chain
  driver loop and the auto driver loop are old in-memory bytecode* for the life of the process.
- BUT each plan phase inside `auto.drive` shells out `[sys.executable, "-m", "megaplan", *args]`
  (`auto.py:266,287`, via `_run_megaplan` `:238`) — a **fresh subprocess that re-imports from disk**.
  `megaplan init` (`chain:821`) and `megaplan status` (`chain:747`, `auto:476`) are also subprocesses.
- Install is **editable**: `pip show megaplan` → `Editable project location:
  /Users/peteromalley/Documents/megaplan`; `megaplan.__file__` resolves into the working tree. So
  `-m megaplan` in a subprocess imports **live working-tree source**, not a frozen copy.
- Between milestones, `_refresh_base_branch` (`chain/git_ops.py:23`) runs
  `git fetch && git checkout main && git pull --ff-only origin main` **on that same working tree**
  (`chain:1277`), pulling each merged milestone's code onto disk *under the running process*.
- `merge_policy: review` (this epic's `chain.yaml:49`): after each milestone the chain sets
  `STATE_AWAITING_PR_MERGE` and **returns/exits** (`chain:1397-1413`), waiting for a human merge and a
  fresh re-invocation. That re-invocation re-imports the now-updated disk.

**Net architecture today is split-version by accident:** driver loop = bytecode at process start;
phase subprocesses = disk at phase start. The two diverge the instant a milestone merges driver/state
code. m3 *removes the subprocess seam entirely* (ports auto in-process, deletes `_run_megaplan`
dispatch — m3 brief S2), collapsing even that accidental isolation.

---

## Ranked self-reference hazards

### H1 (critical) — m1 `schema_version` split-brain on chain_state.json / state.json
- Today `ChainState.from_dict` (`chain:472`) does ad-hoc field-defaulting with **no version**, and
  `save_chain_state` (`chain:553`) is atomic but **lock-free**. `load_plan_from_dir`
  (`_core/state.py:93`) value-sniffs, no version.
- m1 W2 adds `schema_version` + a **load-time validator that fails on missing/unknown version** to
  both files (m1 brief W2, done-criteria 3). Once m1 merges to main mid-epic:
  - The **in-memory driver** keeps writing chain_state.json with the OLD `to_dict` (no
    `schema_version`), stripping the field on every save after every milestone step.
  - A NEW subprocess phase (or the next `chain` re-invocation after the review-merge seam) runs the
    NEW validator → missing version → `CliError("invalid_chain_state")` /plan-state load failure →
    **chain cannot resume → deadlock.** The old writer perpetually removes the field the new reader
    demands. This is the most likely "around m3 it corrupted/deadlocked" mechanism, *seeded at m1*.

### H2 (critical) — m3 removes the only version-isolation seam; a wedged in-process worker hangs the driver
- m3 ports `auto.drive` in-process and removes `_run_megaplan` subprocess dispatch (m3 S2; Anti/Risk).
  After m3 merges, there is **no fresh-subprocess re-import boundary at all** — every phase runs the
  same in-memory code as the driver. Any half-migrated state contract between driver-version and
  phase-version that the subprocess seam used to paper over now executes in one address space.
- m3's own #1 open question: with the kill-able subprocess gone, **a wedged Codex/Shannon stream now
  wedges the whole `megaplan auto`/`chain` process** (m3 Constraints #1, Risk "highest-likelihood
  regression"). If the half-built m3 watchdog mis-fires while *driving m3 itself*, the driver hangs
  with no SIGKILL-able child — the deadlock.

### H3 (high) — editable-install engine shadow (known issue `project_dogfood_engine_shadow_and_openrouter`)
- The driver process binds old `auto.drive` at startup; the post-`git pull` subprocesses bind new
  disk code. The driver therefore *silently mis-drives*: e.g. m3's new DriverOutcome statuses or
  approval-gate signal (S6 `user_approved_gate`) exist in the subprocess phase but the old in-memory
  `_handle_outcome`/exit-map (`auto:2450-2467`) doesn't know them → mis-classified outcome, silent
  wrong branch. No static check catches it.

### H4 (high) — `git pull --ff-only` mid-epic mutates the running engine's source under it
- `_refresh_base_branch` stomps the working tree the live process runs from. `--ff-only` also means a
  diverged/dirty tree (carried WIP — memory `project_worktree_carry_*`) aborts the refresh with
  `git_refresh_failed` (`git_ops.py:54`), stalling the chain at a milestone boundary.

### H5 (medium) — cloud-supervisor SSH import coupling breaks when the epic refactors `chain`
- `cloud/supervise.py:54` SSHes `python3 -c "from megaplan.chain import _capture_sync_state,
  ChainState, save_chain_state, load_chain_state; ..."`. m1 (schema) and m3 (re-point this) and m4
  (relocation) all touch these symbols; until m3's S5 lands, any rename is a remote-breaking change
  with no static check. If the epic runs IN cloud, the supervisor that drives it can break itself.

### H6 (medium) — m4 drops `_BUILTIN_NAMES={"planning"}` while the running driver still plans
- m4 relocates planning to a discovered pack and removes the builtin (`registry.py:53,415-424`). The
  next `megaplan init`/phase subprocess discovers planning from disk; if discovery fails (m1 guard not
  effective in the *driver's* old code path), planning vanishes for the milestone driving the change.

---

## Why "around m3" specifically

m1 *seeds* the schema landmine but stays parity-green and behavior-neutral, so the chain limps. m2 is
profile-only (independent, low self-reference). By m3 the cumulative state written by old in-memory
driver code is being read by new on-disk validators (H1), the subprocess isolation seam that hid the
divergence is being removed (H2), and the in-process watchdog is unproven (H2) — the failures
co-incide right where the brief itself flags max risk.

---

## Recommendation — how to safely drive this epic

**Do NOT dogfood the live editable tree. Drive with a pinned external engine + a frozen schema.**

1. **Pinned engine, not the tree under change.** Install a *separate, frozen* megaplan into its own
   venv from a tag/commit (`pip install megaplan @ git+...@<pinned-sha>` or a copied checkout) and run
   `megaplan chain` from THAT interpreter against the epic's working tree as the *target repo*. The
   driver/auto/chain/state code that *executes* the epic then never changes mid-flight. Subprocess
   phases must also resolve the pinned engine (own venv on `PATH`/`sys.executable`), not the editable
   target tree — verify `megaplan.__file__` inside a phase points at the pinned copy, defeating H3.
   Equivalent: drive the epic in **megaplan cloud** off a pinned image, with the target repo as an
   `extra_repo` — but only after H5 (supervise SSH coupling) is pinned, else move m3/S5 earlier.

2. **Freeze the state schema until the LAST milestone.** The single most dangerous change is H1.
   Re-sequence so `schema_version` *bump + fail-closed validator* on `state.json`/`chain_state.json`
   lands **last** (or behind a default-off flag the running chain never sets). In m1, ship the
   validator in **report-only / accept-missing-as-v0** mode (the brief already leans this way for
   user-dir packs) so an old writer can never deadlock a new reader. Hard-fail validation flips on only
   after the epic completes and the chain is re-launched on the pinned engine.

3. **Keep the subprocess seam alive through the epic.** m3 must land **strictly behind the default-OFF
   `MEGAPLAN_UNIFIED_DISPATCH` toggle** (m3 Risk/rollback already mandates this) AND the *driving*
   chain must run with the toggle OFF (subprocess auto) for the whole epic. Do not let the epic flip
   its own driver onto the unproven in-process path. The in-process port soaks on throwaway plans, not
   on the chain executing the epic.

4. **Drive off a frozen branch, suppress mid-epic `git pull` into the engine.** Run the chain with
   `--no-git-refresh` (engine source frozen) and land milestone merges only at the review-merge seam,
   re-launching the *pinned* engine deliberately between milestones — never let `--ff-only` stomp the
   running process's source (H4). If cloud, pin the image digest; don't auto-rebuild mid-epic.

**Bottom line:** this epic is the one case where dogfooding is actively unsafe, because the deliverable
*is* the driver. Pin the engine, freeze the schema validator to last/report-only, keep m3 behind a
default-off toggle with the driving chain on the subprocess path, and never `git pull` merged code into
the live process. With those four, it is safe; without #1 or #2, expect the H1/H2 deadlock near m3.
