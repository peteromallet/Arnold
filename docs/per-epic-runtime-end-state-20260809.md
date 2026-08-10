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

## The systemic problem this feeds into (2026-08-09, codex + 12-slice swarm)

Every safety mechanism is undermined the same way: **deviations are cheap,
silent, and unrecorded** — absence = allow, fallback = silence, override = no
memory. ~200 instances mapped across 12 slices. Headlines:

- **SHADOW_PASS**: the production action gate (`custody/action_validator.py`)
  defaults `ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=0` — runs every check,
  passes anyway. A parallel dead gate exists (`custody/action_gate.py`).
- **Attestation opt-in**: `MEGAPLAN_RUNTIME_ATTESTATION_REQUIRED` defaults 0;
  the box's env files conflict (0 vs 1).
- **Env-var zoo**: 6 runtime selectors + 3 SYNC_BRANCH vars + ~45 resident
  vars + ~12 feature flags + a generic `config_resolver` env layer +
  `.cloud-hot-env` (3 conflicting env files on the box).
- **Duplication**: manifest reader re-implemented 7 ways; ~30 twin modules
  across `arnold` vs `arnold_pipelines`; wrappers copied ~40x; 5 hardcoded
  expected_head SHAs; the active scheduler pins a local-only commit.
- **Recurrence**: 31 problems / 29 open; stale_active_step ×53; "nothing
  expires" codified in research/m9-compatibility-expiry-map.md.
- **13 tests bless the fallbacks**; 3 of 4 new enforcement gates have only
  text-presence tests.

Strategy (codex): exceptions as declared expiring permits, fallbacks as typed
state transitions, one config source, deny-by-default, watcher verifies
absence. Refined to **four primitives**: (1) one manifest admission path,
(2) one typed deviation/fallback event path, (3) deny-by-default gates,
(4) expiring exception records.

## Implementation plan (codex-refined; one commit per phase, oracle gates between)

| Phase | Deliverable | Key files |
|---|---|---|
| P1 Admission kernel | `deviations[]` + expiry in manifest; `chain override --allow-manifestless --reason --expires-at --actor --evidence` (24h max, `.runtime_policy.json` sidecar); consolidate 7 manifest readers onto the lib; absent manifest blocks unless permit | `cloud/runtime_manifest.py`, `chain/spec.py`, `chain/__init__.py`, `arnold-supervisor-runtime-lib`, 6 wrappers, `resident/scheduler.py` |
| P2 Typed transitions | 5 ledger events emitted before dispatch (`manifest_selected`, `deviation_declared`, `fallback_considered/taken/rejected`); write-failure blocks dispatch; watchdog/auditor flag absence | `incident/ledger.py`, `cloud/watchdog.py`, `cloud/six_hour_auditor.py` |
| P3 Default deny | Enforcement + attestation default on; SHADOW_PASS never authorizes | `custody/action_validator.py`, `controlled_writer_registry.py`, `canary.py`, `compatibility.py`, `runtime_attestation.py` |
| P4 Config cleanup | `.cloud-hot-env` credentials-only; delete 6 selectors + 3 SYNC_BRANCH vars + baked pins; delete `_core/config_resolver.py` | `cloud_hot_upload.py`, `entrypoint.sh.tmpl`, `_core/io.py`, `feature_flags.py` |
| P5 Deletion + deploy | Delete dead `action_gate.py` + tests; deploy manifest-based scheduler `-r7` to box; masked/duplicate units = blocking | `custody/action_gate.py`, 5 adapters, box `/usr/local/bin` |
| **P6 Reconcile milestone** | **End-of-epic reconciliation as a default megaplan stage (below)** | `chain/spec.py`, `chain/reconcile.py`, `chain/git_ops.py`, `managed_agent.py`, `arnold-close/gc-sweep` |

**Oracle gates** (codex check-ins; pause, present diff+test+grep evidence, one
question each): G1 before any edit (baseline + fallback inventory);
G2 P1→P2 (manifest-only selection proven); G3 P2→P3 (ledger failure blocks
dispatch); G4 P4→P5 (nothing can authorize without attestation); G5 final
(deletion safe + one unmasked scheduler path); **G6 before P6 default-on
rollout** (product/no-op fixtures, merge AND reject reach close, idempotent).

**Do NOT build:** heartbeat leases, fencing epochs, quarantine workers, new
event bus/db, generalized permit engine, watcher as action authority.

## P6 — end-of-epic reconcile milestone (default ON, part of the megaplan process)

Reconciliation is a **generated final `kind: reconcile` milestone** in the
chain, not a side hook. `ChainSpec.reconciliation.enabled` defaults `true`
(initiative opt-out = `false`); `scaffold_epic()` appends:

```yaml
- label: reconcile
  kind: reconcile
  idea: briefs/reconcile.md
  branch: reconcile/<epic>-<date>
  target_branch: main
  merge_policy: review          # forced even if chain is auto
  phase_model: [execute=codex]
  depends_on: [<previous-terminal-milestone>]
```

- Legacy chains: idempotent `ensure_reconcile_milestone()` before execution
  identity binding; date/branch persisted, not recomputed.
- **Execute** = `automatic_reconcile` managed-agent run (Codex), given the two
  rubric docs + `git log --first-parent` + candidate commits; outputs **JSON of
  selected commit SHAs** (selection, not narrative — the per-phase commit
  history IS the description). Controller validates reachability, excludes
  chain-control commits, cherry-picks onto `reconcile/<epic>-<date>` from
  `main`; conflicts fail closed.
- **Skip** = controller-computed `compute_reconcile_scope()` (engine-source
  allowlist − promotion-ledger evidence; uncertainty ⇒ PR required). No-op
  still writes `reconcile-verification.json` accepted by the completion guard.
- **PR** = `_ensure_reconcile_pr()` (base `main`); completion guard validates
  against the recorded target. Merged → delete PR branch; **rejected → delete
  PR branch, record per on_failure, proceed to close** (history preserves
  everything; no ticket ceremony). Operator DM via `completion_delivery`.
- **Close/GC** = idempotent terminal finalizer: `arnold-close` (backstop tag
  `box-snapshot/<epic>-<date>`, `state=closed`) → `arnold-gc-sweep
  --restore-proven` (worktree/venv + manifest-declared `fixer/<epic>-<date>`
  branch local+remote).

**Exploration checklist before P6** (all read-only): (1) `chain/spec.py`
writers + `briefs.scaffold_epic()`; (2) `chain/__init__.py` binding +
completion guard with a generated final milestone; (3) `chain/git_ops.py` gh
auth + PR-to-main capability; (4) `workers/_impl.py`/`execute/batch.py`/
`managed_agent.py` custom-execute path; (5) `runtime_manifest.py` +
lifecycle tests (close ordering, restore proof); (6) resident
`awaiting_pr_merge` DM behavior; (7) fixtures: promoted-only, product-change,
cherry-pick conflict, merged/rejected PR, missing gh auth, interrupted
cleanup. **Risks:** spec mutation after binding, base-vs-main completion
checks, false no-op, cherry-pick conflicts, model-selecting chain-control
commits, on_failure vs always-close, GC before restore proof.

## P7 — Live validation (FINAL task of the sequence, operator-ordered)

Terminal acceptance: nothing in P1–P6 counts as done until the whole stack is
proven live. Steps, in order:

1. **Push** current `main` to origin (all committed work; leave other agents'
   dirty files untouched).
2. **Refresh the box runtime**: fast-forward the box runtime tree
   (`/workspace/runtime-candidates/arnold-main-20260809`, or the tree the
   watchdog currently runs from — check `pgrep -af arnold-watchdog` first) to
   latest `main`; re-copy changed wrappers to `/usr/local/bin` (cp + chmod +
   `bash -n` + grep marker check). If the box was reorganized (runtime tree
   renamed/deleted, watchdog restarted from another tree), adapt to the live
   tree and record the change.
3. **Launch the `megaplan-maintenance` epic** (`.megaplan/initiatives/
   megaplan-maintenance/chain.yaml`, 5 codex milestones,
   `merge_policy: review` + `driver.auto_approve: false` ⇒ human-gated).
   The cloud.yaml lives at `.megaplan/initiatives/megaplan-maintenance/
   cloud.yaml` (gitignored, local-only; `src_path` must point at the live
   box runtime tree). Run `cloud preflight ... --allow-human-gates` then
   `cloud chain ... --fresh --allow-human-gates`. **First check
   `cloud status --all`** — a `megaplan-maintenance` session may already
   exist on the box; never double-launch, resume/observe instead.
4. **Observe**: `cloud status --all` shows the `megaplan-maintenance-<digest>`
   session alive and advancing past init; the watchdog reports it (fresh
   sweep, `codex_repair_enabled=true`); the fixer is active
   (`ARNOLD_REPAIR_TRIGGER_ENABLED=1`, repair-trigger path wired, watchdog
   sweep shows repair enabled); the first milestone moves init → prep/plan or
   halts only at an expected human gate (`merge_policy: review` PR).
5. **Sense-check**: any failure in the first 10–15 min is caught now (the
   operator-loop cadence), not after a day.

## Whole-plan sense-check (gpt-5.6-sol, high — 2026-08-10): verdict + corrections

Verdict: architecture coherent; **execution plan not safe as written**.
Seven blockers must be folded into the plan before autonomous execution:

1. **P7 is not terminal acceptance as written.** Split it: **P7A** = launch
   smoke test through two watchdog sweeps; **P7B** = the epic reaches the
   generated reconcile milestone, resolves its PR / verified no-op outcome,
   runs close+sweep, and leaves durable evidence. Only P7B is whole-stack
   terminal acceptance.
2. **P1 omits the producer its own deny rule requires.** No cloud-launch code
   invokes `arnold-runtime-create` today. P1 must add: runtime creation,
   manifest binding, and launch provenance to the `cloud chain` path before
   enabling manifest-only admission — and the 13 fallback-blessing tests must
   be reclassified in the SAME commit.
3. **P4 contradicts P7.** `cloud chain` still contains editable-install /
   source-sync machinery (with an isolated `src_path` it publishes the local
   launch HEAD, which the dirty worktree blocks). P4 must migrate
   `cloud/cli.py` + remote refresh to manifest/runtime-create semantics
   BEFORE deleting selectors and editable-install support.
   `--no-editable-install-sync` is an escape hatch, not proof.
4. **`cloud chain --fresh` can destroy an existing run** (stops + resets the
   exact session). Launch must be conditional: matching post-P6 identity →
   observe/resume without `--fresh`; old/mismatched identity → record
   evidence, explicitly retire, then fresh; never treat an inherited pre-P6
   session as acceptance.
5. **Move the live box cutover after P6.** P5 keeps deletion/packaging/
   offline deployment verification; the box switch happens only after P6 and
   the final gate (avoids a mixed-version interval).
6. **P6 needs explicit terminal-state rules.** Close+sweep only after
   `merged`, intentionally `rejected`, or verified no-op — never after unknown
   PR state, missing GitHub auth, cherry-pick conflict, or interrupted
   publication. G6 must prove crash-idempotency, non-recursion of
   `kind: reconcile`, persisted branch identity, and generated-milestone
   insertion before binding.
7. **Final pre-P7 gate must verify**: all commits present and origin/main is
   ancestor/exact target; initiative inputs committed or content-hash
   snapshotted; no manifestless production path; no editable-install/SYNC
   selector remains; ledger-write failure blocks dispatch; P6
   merge/reject/no-op fixtures pass; box tree + watchdog executable
   identified; runtime manifest attests the exact SHA; wrapper checksums +
   syntax pass; cloud preflight reports the expected workspace/session/digest.

Operational notes: `cloud.yaml` is gitignored (always pass `--cloud-yaml`
explicitly); its `src_path` must point at the LIVE box runtime tree (the
original `arnold-main-20260809` was deleted and the watchdog now runs from
`arnold-r7-fresh-child-20260805` — re-verify with `pgrep -af arnold-watchdog`
before launch); the megaplan-maintenance briefs/NORTHSTAR carry uncommitted
dirty state that must be committed or content-hash snapshotted before launch.

## P1 oracle gate G1 (gpt-5.6-sol high, 2026-08-10): NO-GO → contract corrections

The admission contract was rejected once; the following corrections are now
part of the P1 contract (the executor must not edit P1 until G1 passes with
these folded in):

1. **Per-session admission, not global.** The shared authority helper must be
   the SOLE resolver and run before `arnold_supervisor_runtime_init`, field
   reads, and dispatch. Watchdog admission is checked PER TARGET
   CHAIN/SESSION, not once against the global active pointer. `cloud chain`
   must bind each launch and session marker to its SPECIFIC manifest path —
   concurrent chains must not cross-select runtimes (the single global pointer
   that `arnold-runtime-create` advances is not a sufficient identity).
2. **Richer permit record.** Minimum fields: `kind`, immutable `id`,
   server-stamped `issued_at`, `expires_at`, `actor`, `reason`, `evidence`,
   and a `chain_digest` of the chain spec. Validate
   `0 < expires_at - issued_at <= 24h` and current-unexpired. Revocation is an
   auditable tombstone (never silent delete). Caller-supplied actor is
   attribution, not authentication. Historical deviations stay loadable after
   expiry — expiry rejects admission/addition, it does not invalidate the
   manifest forever. Schema stays `"1"` only because `deviations` is genuinely
   optional AND preserved by every read/write transition.
3. **Do NOT delete `test_editable_install_sync.py` wholesale.** Its 12 tests
   cover still-live functions in `cloud/cli.py:5142`. Preserve/convert: clean
   runtime mirrors, inherited-pin clearing, exact revision/PYTHONPATH binding,
   dirty-tree refusal, divergent-branch refusal. Legacy selector assertions
   are deleted only alongside the P4 code removal.
4. **Gate placement must be proven before both state loads.** Canonical
   execution loads state at `chain/__init__.py:6343` before binding `:6350`;
   supervisor execution loads at `supervisor/chain_runner.py:337` without the
   same initial binding. The gate fires before BOTH loads, and a regression
   test proves rejected admission calls NEITHER `load_chain_state` NOR
   `bind_execution_identity`; the supervisor binding path is aligned.
5. **Baseline must be reported.** Baseline focused pytest counts (per file
   chunk) must accompany the gate re-run.

### G1 second re-run (2026-08-10): NO-GO → two further amendments

1. **Session-manifest binding must have NO global-pointer fallback.** Per-session
   binding closes cross-selection only if the bound manifest path is MANDATORY
   and the shared resolver has no fallback to
   `/workspace/.megaplan/runtime-manifest.json`. `arnold-runtime-create` must
   either STOP updating the global active pointer or explicitly demote it to
   non-authoritative compatibility state — with tests proving admission,
   dispatch, and watchdog NEVER consult it.
2. **Python-before-init classification corrected (the earlier note was wrong).**
   - `arnold-kimi-goal-operator`: manifest-read heredoc runs before ANY runtime
     init — genuine violation; add Kimi to the runtime-order regression suite.
   - `arnold-meta-repair-loop`: inits at ~line 100, reads manifest at ~118 —
     AFTER init; NOT a violation.
   - The named failing test covers watchdog/repair-loop/meta/progress-auditor
     and fails on **arnold-repair-loop** because python-bearing FUNCTION
     DEFINITIONS appear textually before the init call (though only invoked
     after). Fix: make the test prove EXECUTION ordering, or deliberately
     relocate repair-loop's python-bearing definitions after init.
   - Preserve the supplied baseline (972 passed / 20 failed) while correcting
     this failure classification.
