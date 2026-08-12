# GOAL: Fix the fixer

The `megaplan-maintenance` epic on the Hetzner box is blocked — m1 plan phase,
deterministic failure `ActionBoundaryDeniedError: dispatch not authorized:
blocked_no_lease` — and neither the ordinary fixer nor the fallback fixer is
repairing it. Your charge is to fix the fixer as it progresses through the epic,
starting with the issue right now.

## WHAT TO DO

1. **Watch the epic.** Check in every ~30 minutes — and KEEP watching it the
   whole way through the epic, from this blocked state through every milestone
   until the chain completes. Determine whether the epic is running and
   advancing; when it stops, identify when and why.
2. **Diagnose the fixer.** Determine IF the ordinary fixer
   (`arnold-repair-loop`) is attempting to fix it, and if not, why not. If the
   fixer isn't triggering, determine whether that cause is specific to this
   epic (e.g. the improved failure plane / deny-by-default custody) or
   systemic.
3. **Fix the fixer.** If the epic stalls and the fixer persistently fails to
   fix it, trigger a swarm of DeepSeek subagents to gather context, then hand
   that context to a Codex subagent to recommend how the fixer should be fixed
   so it can:
   - (1) identify the problem in the first place,
   - (2) understand the root cause — why isn't it automatically fixing the
     on-chain failure,
   - (3) improve the fixer's mechanics or its prompt until it successfully
     fixes the issue and progresses the epic.
4. **Verify the hourly fixer.** If the ordinary fixer isn't triggering for a
   reason this epic is fixing (e.g. the improved failure plane), observe the
   1-hour fixer cadence and make sure it is working properly. First PROVE the
   chain works end to end: schedule exists → due job → launch consumer →
   launch receipt. Note: `superfixer_proactive` currently only writes a
   dispatch plan and raises `PlannedOutcome` — no committed consumer launches
   it (scheduler.py:479), so a restored schedule alone does NOT restore an
   hourly fixer. Re-enabling any paused/cancelled backstop requires human
   authority; do not flip it yourself.

## HOW TO EXECUTE

1. **Baseline first:** `cloud status --all --cloud-yaml
   .megaplan/initiatives/megaplan-maintenance/cloud.yaml`; read
   `/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains/chain-*.json`;
   read the latest `/workspace/watchdog-reports/*.json`; check the repair
   queue (`/workspace/.megaplan/repair-queue/{requests,decisions}/` for this
   session); check fixer env flags in `/workspace/.cloud-hot-env`
   (`ARNOLD_META_REPAIR_ENABLED`, `ARNOLD_REPAIR_TRIGGER_ENABLED`,
   `ARNOLD_AUTONOMY`). Record the baseline.
2. **Loop** every ~30 min: re-check the above — continuing until the chain
   completes, not just until m1 moves — and write findings to a handoff doc
   (`docs/fixer-recovery-<date>.md`) so state survives compaction.
3. **On stall + fixer failure:** fan out the DeepSeek swarm for context —
   READ-ONLY — then Codex (gpt-5.6-sol) recommendation. Make the fix on
   `main`, push, then deploy to the exact executed import root (content-
   addressed, with receipts), create/claim the occurrence-bound repair
   request, retrigger ordinary repair, and use the supported same-occurrence
   resume/rebind path. Do NOT force-proceed, do NOT `git reset --hard`, do NOT
   hand-edit the manifest pin, do NOT blanket-refresh unrelated trees.
   After the read-only diagnosis phase, ONE durable mutation-authorized
   recovery owner applies the fix.
4. **Done when:** the chain completes (all milestones through m6 reconcile) —
   with the fixer demonstrably repairing any stall it encounters along the
   way. The 30-minute watch continues even after m1 advances; it only stops
   at chain completion. At human PR gates, enter durable waiting with a named
   owner and return condition — never claim completion there.

## BOX OPERATING NOTES & CONSTRAINTS

- **Four code trees, four commits — the split-brain is a SET, not one place:**
  (a) **engine candidate** `/workspace/runtime-candidates/arnold-r7-fresh-child-
  20260805` (main @ `7f6abcbe42`) — what the chain actually executes
  (recorded `engine_root`); carries untracked box hot-fix `.bak-*` files
  (`arnold-repair-loop.bak-merge`, `arnold-watchdog.bak-statusfix`,
  `arnold-watchdog.bak-superfixer-only`, `batch.py.bak-shadow`, etc.) — never
  blindly overwrite;
  (b) **epic worktree** `/workspace/runtime-candidates/megaplan-maintenance`
  (fixer/megaplan-maintenance-20260811 @ `f410585d56`) — manifest-declared
  runtime/repair target, matches `expected_head`, but NOT executed; its
  declared `.venv` does not exist;
  (c) **watchdog tree** `/workspace/omp-replaces-hermes/Arnold` (main @
  `0cc5ffb6`) — the tmux watchdog's wrapper + PYTHONPATH;
  (d) **resident tree** `/workspace/arnold` (main @ `3299a4f0`, 30 dirty
  files) — what the resident container actually imports (`arnold 0.23.0`
  installed). Local `main` `53584bb018` is 2 commits ahead of box
  `origin/main` (`7f6abcbe42`) — unpushed. Deploy to the exact import root
  the chain uses, content-addressed, with receipts.
- **`cloud.yaml` is gitignored** — always pass
  `--cloud-yaml .megaplan/initiatives/megaplan-maintenance/cloud.yaml`
  explicitly.
- **Human gates are expected, not failures.** The chain is `merge_policy:
  review` + `driver.auto_approve: false`; a halt at `awaiting_pr_merge` /
  PR review is a human gate, not a fixer defect — do not "repair" it.
- **Constraints (no shortcuts):** do NOT flip `ARNOLD_META_REPAIR_ENABLED=1`
  or disable enforcement/attestation to make it green — the 2026-07-27 pause
  and the deny-by-default posture are deliberate. Fix the mechanics/prompt so
  the fixer succeeds under the intended policy.
- **The problem is systemic, not epic-specific:** the watchdog fences repair
  for many sessions (`critique-ledger-*` all show `missing_identity` /
  `liveness_unknown` / "legacy PID/tmux evidence diagnostic-only"). Fixing
  this epic is the test case; fixing the fixer is the deliverable.
- **Verify with focused tests only:** `tests/cloud/test_watchdog_wrappers.py`,
  `tests/arnold_pipelines/megaplan/test_chain_execution_binding.py`, the
  runtime lifecycle tests, plus `bash -n` on any modified wrapper. Skip
  formatters and project-wide suites.

## HOW FIXES REACH THE EPIC (two surfaces — do not conflate)

**Design intent:** each epic gets an isolated runtime branch —
`arnold-runtime-create` does `git worktree add -b fixer/<slug>-<date>`, pushes
it at creation, and the manifest binds `epic.branch` as the fixer's only push
target. The epic worktree (`/workspace/runtime-candidates/megaplan-maintenance`
on `fixer/megaplan-maintenance-20260811`) is that branch. The launch path DOES
invoke `arnold-runtime-create` (cloud/cli.py:5282 `_ensure_chain_runtime_
binding` → :3862 → :3782) — the manifest and worktree exist and match
`expected_head`.

**But the chain's recorded `execution_environment.engine_root` is the SHARED
ENGINE candidate, not the epic worktree.** The failing dispatch runs through
`/workspace/runtime-candidates/arnold-r7-fresh-child-20260805/arnold_pipelines/
megaplan/...` (branch `main`, HEAD `7f6abcbe42`). That divergence — manifest
binds the epic worktree at `f410585d56`, yet execution resolved to the engine
candidate — is a downstream activation/relaunch SPLIT-BRAIN requiring
provenance diagnosis, NOT a "producer gap". Investigate why the executed import
root diverged from the manifest before mutating anything.

**Known root cause of `blocked_no_lease` (codex-verified):** the executed
engine `7f6abcbe42` builds `WbcRuntimeProducerFacade` WITHOUT `lease_store`/
`outbox` (worker_dispatch_wbc.py:206-220) → store `MISSING` →
`BLOCKED_NO_LEASE`. Local main `53584bb018` wires `_ensure_dispatch_leases`
and passes both stores (worker_dispatch_wbc.py:258) — the fix EXISTS locally
but is UNPUSHED (origin/main is still `7f6abcbe42`) and undeployed to the
executed engine. Residual defects at `53584bb018` (not the present failure):
lease_store.py:592 check-then-append race; worker_dispatch_wbc.py:520
`dispatch_key` omitted from custody target digest. `53584bb018` is an
immediate unblock, not category closure.

So:

- **Engine fixes (custody, leases, workers — incl. the current
  `blocked_no_lease` blocker):** land + test on `main` locally, push
  `origin/main`, then deploy to the EXACT engine import root the chain
  executes from (`arnold-r7-fresh-child-20260805`), content-addressed with
  receipts — verify import-root applicability first, do not blanket-refresh
  unrelated trees. No wrapper changed between `7f6abcbe42` and `53584bb018`,
  so blanket wrapper re-copy is unnecessary for the lease fix.
- **Epic-code fixes (the fixer's own repairs during the epic):** edit the epic
  worktree on `fixer/megaplan-maintenance-20260811` directly and push to that
  branch (the delivery shim fail-closes to `epic.branch`).
- **Manifest pin:** do NOT bump `expected_head` merely because the engine
  candidate moved. Update it only through the canonical manifest/rebind path
  when the manifest-bound epic worktree itself changes; direct JSON bumps lose
  custody/lineage.

Guardrails: the fixer's delivery shim only allows repair `git push` to the
manifest `epic.branch`, never `main`, force, `--all`, or non-origin. The epic's
own milestone work flows through the chain's reconcile → PR machinery. Only
`arnold-promote` mutates shared state.

## PREREQUISITES — do these before starting the 30-min loop
(Codex-refined 2026-08-11: the loop is only safe after the systemic fixer/
binding defects are closed. Order matters; each step needs a receipt.)

1. **Push the committed fix to origin.** Local `main` (`53584bb018`: WBC
   lease/outbox store wiring `5547f6867c` + gate-blocker fix `53584bb018`) is
   UNPUSHED; `origin/main` is still `7f6abcbe42`. Push and verify.
2. **Fix the write-only engine_root defect (systemic, code-level).** Recorded
   chain `engine_root` is never re-read at relaunch (epic_chain.py:374 reads
   only project_root; chain/__init__.py:668 + cli/__init__.py:2183 do live
   self-hosted compares) — relaunch SILENTLY re-binds to whatever tree
   imports. Add a relaunch preflight that validates recorded engine_root vs
   manifest runtime_root vs live import root and fails closed on divergence.
3. **Close the silent ENGINE_DIR fallback.** cloud/cli.py:3580-3581 falls back
   to the shared engine when the manifest pin is unreadable
   (`_pinned_manifest_field_read ... 2>/dev/null || true`), and the drift gate
   is opt-in (cli.py:3583, 3965 `isolated_chain_runner`); cli.py:3957/3968 and
   spec.py:81 keep the fixed `/workspace/arnold` fallback. Make launch fail
   closed: manifest pin must resolve or launch refuses (no silent shared-
   candidate execution).
4. **Deploy the executed engine candidate** (`arnold-r7-fresh-child-
   20260805`, the chain's recorded engine_root): ff to `origin/main`,
   preserving the untracked `.bak-*` hot-fix files, verify
   `_ensure_dispatch_leases` (worker_dispatch_wbc.py:258) is present, record
   SHA before/after. Do NOT blanket-refresh the epic worktree or watchdog
   tree.
5. **Fix per-epic binding + split-brain:** megaplan-maintenance records
   engine_root = SHARED candidate while the manifest binds the epic worktree
   (f410585d56); v3-r7 shares the same candidate (cross-epic runtime
   mutation). Rebind the chain to the manifest runtime through the canonical
   path; audit/retire shared-candidate references so no two live epics resolve
   to one mutable tree.
6. **Restore repair identity.** The current run has NO occurrence-bound repair
   request and the classifier returns `broken_superfixer` (not
   `dispatch_l1_repair`) → L1 dies at `missing_identity`. Route deterministic
   mechanical+request cases to L1 (repair_contract.py:2205-2260) with
   normalized occurrence identity persisted before lifecycle custody is
   released (auto.py:2453-2704); validate enqueue (arnold-watchdog:1648-1687)
   and bind returned IDs.
7. **Fix residual lease defects (category closure):** lease_store.py:592
   check-then-append race (lock load/check/append ~586-620) and
   worker_dispatch_wbc.py:520 `dispatch_key` omitted from custody target
   (~520-550). Land, push, deploy, run focused behavioral tests.
8. **Frozen-venv model (design contradiction):** manifest schema REQUIRES
   per-epic `venv_path` (runtime_manifest.py:81-88) but `arnold-runtime-create`
   never builds one, and the end-state doc mandates ONE shared frozen venv
   (per-epic-runtime-end-state-20260809.md:34-39, "not yet implemented":74-76).
   Replace per-worktree .venv fields with the content-addressed shared
   dependency generation + worktree-first PYTHONPATH.
9. **GC reference checks:** arnold-gc-sweep is manifest-driven + closed-only
   and never checks chain-*.json engine_root references — 9 recorded engine
   roots are already dangling (v2/v3-r2/r3/r4/v3-r6/bigbang/custody-control-
   plane/m10-stable/repository-strategy-roadmap) + 1 broken worktree gitdir
   (critique-session-binding-20260723). Make gc-sweep refuse any root
   referenced by live/paused chain state, markers, schedules, claims, or jobs;
   report dangling references instead of deleting.
10. **Fixer must diagnose split-brain, not patch victims:** add manifest/
    recorded/live runtime comparison to repair_investigation.py:699-910 and
    :1249-1373 so the fixer identifies the divergence itself.
11. **Delivery-proof rebind:** locked per-epic CAS rebind coupled to chain
    runtime-rebind (chain/__init__.py:10239-10275); never mutate the
    compatibility/global pointer. Repair push must fail closed unless target ==
    manifest epic.branch (already enforced arnold-repair-loop:806-808).
12. **Then unblock this epic:** push epic branch, CAS-rebind, resume via the
    supported same-occurrence path; require request → decision → claim →
    attempt → branch-only push → rebind → manifest-bound relaunch → fresh
    progress receipts. Do NOT force-proceed, do NOT hand-edit the manifest,
    do NOT `git reset --hard`.
13. **Hourly fixer stays DISABLED unless human-authorized** (L2 pause
    deliberate; `superfixer_proactive` has no launch consumer). It is not a
    loop-start gate. If re-enabled later, build the consumer + receipt chain
    first.
14. **Termination:** stop only after P7B — reconcile outcome (merge/reject/
    verified no-op), close, restore-proven GC, durable receipts.

## END STATE + GAP + PHASES (Codex north-star verdict, 2026-08-11)

**End state:** one coherent per-epic ObservationEnvelope (recorded root = manifest
root = live import root = wrapper digest = dep generation; mismatch = typed
UNKNOWN, never green); a fixer that requests→claims→diagnoses→repairs→rebinds→
proves via independent verification; no silent fallbacks or dangling refs; one
frozen content-addressed dep generation; hourly backstop real-or-off;
reconcile-to-main on every epic with receipts; no loop becomes a second
authority; human gates for publication/promotion/force-proceed/new repair
classes.

### Legacy-label semantics (locked)

Legacy labels (records captured before ObservationEnvelope coherence fields
existed, i.e. with no `coherence`/`runtime_observation`) have locked semantics —
do not re-derive or reorder them:

- (a) A legacy label without coherence fields deserializes as UNKNOWN-typed:
  `coherence == UNKNOWN`, `is_dispatchable is False`, `runtime_observation is
  None` — it is never green and never dispatchable.
- (b) A legacy label carrying an old `run_revision` is STALE
  (`stale_observation_cannot_authorize_dispatch`). In the reducer the stale
  branch precedes the unknown branch, so an old revision makes even an UNKNOWN
  record stale — never merely unknown (locked decision: never reordered to
  unknown).
- (c) A legacy label carrying the current revision falls through to the unknown
  branch (`unknown_observation_cannot_authorize_dispatch`).
- (d) Neither stale nor unknown legacy labels can authorize dispatch; both are
  preserved as observations for auditability and surfaced as
  `non_coherent_observation` diagnostics only.

Reference: the reducer's stale-precedes-unknown ordering
(`arnold_pipelines/run_authority/reducer.py:391-415`) and the locking test
`test_legacy_done_label_is_explicitly_typed_unknown_evidence`
(`tests/run_authority/test_dependency_closure.py:342-365`).

**15 gaps** (see context block): write-only engine_root (9 dangling roots);
silent ENGINE_DIR fallback (cli.py:3581); GC blind to chain refs; shared mutable
candidate cross-epic (v3-r7 + megaplan-maintenance); executed engine lacks
lease/outbox + residual races; missing occurrence identity → missing_identity;
zero valid liveness (alive_sessions=0); 4-tree import split; venv schema lies;
repair-queue identity at 3 seams; P6 reconcile zero instances; hourly backstop
cancelled/consumerless; unguarded status-snapshot read (repair-loop:5670);
orphan fixer branches; ghost controls (07-27 pause ineffective).

**Phases (North-Star rollout: contracts → shadow → canary → human-gated):**
- **Phase 0 — stop making it worse (GO today):** specialize ObservationEnvelope
  (contracts.py:178); delete cli.py:3581 fallback; re-read recorded engine_root
  at relaunch (epic_chain.py:373); GC reference checks before delete
  (arnold-gc-sweep:133); read-only census S1–S12. Exit: root mismatch blocks
  before launch; no silent fallback; GC refuses referenced roots.
- **Phase 1 — human-gated canary unblock (conditional GO):** human pushes
  tested main; stage immutable candidate with WBC wiring (worker_dispatch_wbc:
  258); do NOT fast-forward shared candidate in place; occurrence request →
  claim → fence → branch-only push → CAS rebind (chain/__init__.py:10239) →
  supported resume. BLOCKED-BY Phase 0 + human approval.
- **Phase 2 — fixer mechanics:** deterministic L1 routing (repair_contract:
  2205); persist lifecycle identity (auto.py:2453-2704); split-brain diagnosis
  in repair_investigation.py:699; lock lease append; dispatch_key in
  CustodyTargetKey (worker_dispatch_wbc:520); queue relational completeness.
- **Phase 3 — frozen dep generation:** replace venv_path fields
  (runtime_manifest.py:81, arnold-runtime-create:273) with dep-generation ID;
  worktree-first PYTHONPATH; retire editable sync (install_sync.py:250-355).
- **Phase 4 — hourly backstop (operator-only, action-off):** build consumer for
  scheduler.py:479 plan → due → claim → launch → receipt; uncancelling is a
  separate human gate.
- **Phase 5 — reconcile real:** fixtures for merged/rejected/no-op
  (compute_reconcile_scope:6661, ensure_reconcile_milestone:6805) BEFORE loop;
  first live instance = Phase 6 terminal gate.
- **Phase 6 — 30-min watcher:** fresh coherent baseline (6A); watermark windows
  + canonical request path (6B); drive to P7B reconcile/close/GC (6C).

**Loop scope (D4):** push main = operator-only; deploy/promote = operator-only;
create repair requests = conditional-autonomous via approved canonical path
only; rebind manifests = operator-only; force-proceed = forbidden to loop;
enable hourly = operator-only.

## CONTEXT (known at goal creation)

- **Box:** `root@159.69.51.216`, `docker exec megaplan-cloud-agent-resident-only`.
  Epic repo: `/workspace/megaplan-maintenance/Arnold`; chain at
  `.megaplan/initiatives/megaplan-maintenance/chain.yaml`; runtime pinned at
  commit `f410585d56`.
- **Epic state:** blocked, milestone 0/6 (`chain-c511d8baf7d7.json`), plan
  `m1-containment-and-truthful-20260811-0640`. Latest live failure (plan
  state.json) is at phase `gate`, recorded 07:35:34Z — same deterministic
  `blocked_no_lease`, count 3; chain ground-truth record says phase `plan`
  (07:21:26Z). Chain supervisor loop STOPPED 07:40:52Z (rc=20, authority-gap,
  streak ×5); runner liveness lease expired. Watchdog alive (tmux `watchdog`,
  ~9min sweeps, reports to `/workspace/watchdog-reports/`).
- **Fixer stack:** L1 `arnold-repair-loop` — watchdog claim fails with
  `missing_identity` (classifier returned `broken_superfixer`, not
  `dispatch_l1_repair`, so no request/blocker identity is bound; no repair
  request exists for the current run). L2/L3 `arnold-meta-repair-loop` —
  disabled deliberately: `/workspace/.cloud-hot-env` sets
  `ARNOLD_META_REPAIR_ENABLED=0` (durable 2026-07-27 pause). Hourly job —
  absent and incompletely wired: `sched_superfixer_hourly_v2`/`_global` are
  CANCELLED; resident container runs `--listener-only` so the scheduler worker
  is never built; `superfixer_proactive` has no launch consumer.
- **Root cause (codex-verified):** executed engine `7f6abcbe42` builds the
  WBC dispatch facade without lease/outbox stores → `BLOCKED_NO_LEASE`. The
  lease/outbox wiring fix is committed locally (`5547f6867c` + `53584bb018`)
  but UNPUSHED and undeployed to the executed engine. Residual defects at
  `53584bb018` (lease_store race, dispatch_key custody-target omission) remain
  open. The dropped session `019fe834` (`omp --resume
  019fe834-5052-7000-b204-466654320887`) was mid-fix on these.
- **Systemic breakage found by 6-scout swarm + Codex (2026-08-11):** the
  split-brain is one instance of a broad pattern:
  - Recorded chain `engine_root` is WRITE-ONLY — never re-read at relaunch,
    so 9 recorded engine roots are DANGLING (dirs gone): v2-20260728,
    v3-r2/r3/r4, v3-r6, bigbang, custody-control-plane, m10-stable,
    repository-strategy-roadmap. Relaunch silently re-binds to whatever tree
    imports.
  - Shared-candidate execution: v3-r7 AND megaplan-maintenance both record
    engine_root=`arnold-r7-fresh-child-20260805` (cross-epic mutable runtime);
    megaplan-native-parity-corrective records `/workspace/arnold` (the dirty
    resident tree); v3-r5 records `arnold-wbc-full-20260804` which has
    UNRESOLVED MERGE CONFLICTS (UU attempt_ledger_store.py,
    DU worker_dispatch_wbc.py).
  - 3 empty `.megaplan/runtime/editable-engine` shells (legacy per-epic
    editable-install locations) + broken worktree gitdir
    (critique-session-binding-20260723).
  - NO per-epic `.venv` exists anywhere: `arnold-runtime-create` declares
    venv_path but never builds it (only the shared supervisor venv exists);
    manifest schema REQUIRES the field — a false contract vs the frozen-venv
    design.
  - Fixer inert box-wide: `alive_sessions=0`; every dispatch/relaunch fenced
    on liveness-unknown; PAUSED plans never dispatch (watchdog:9030-9034);
    L1 needs an occurrence-bound request that no session has;
    `ARNOLD_REPAIR_TRIGGER_SESSION_ALLOWLIST` does NOT exist in code (the
    earlier allowlist suspicion was refuted).
  - Orphan branches: fixer/critique-epoch-invalidation-20260806 and
    fixer/fixer-unification-20260807 content DID land in main (via manual
    merges, not P6 reconcile) but refs were never deleted; NO reconcile/*
    branches exist on origin — the P6 merge-at-end machinery has zero
    successful instances; `editible-install` @ 8c4b2c9561 has 67 commits never
    in main, still referenced by canonical-run-state-control-plane/cloud.yaml
    megaplan.ref.
- **Reference docs:** `docs/per-epic-runtime-end-state-20260809.md` (plan +
  P7A/P7B terminal validation), `docs/megaplan-reference-architecture-20260807.md`.
