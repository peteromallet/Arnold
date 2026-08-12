# Phase 0B completion receipts — T-0014..T-0027, gates G3–G6

Recorded 2026-08-12 ~06:00 UTC by the completion-recording agent (deepseek-v4-flash).
Source of truth: per-task yields from the implementing agents (B2*/B3*/T27* subagents
and the Codex T-0014 run) plus the oracle gate verdicts held in the Main session
transcript. All counts are **as reported by the implementing agents** at their yield;
none were re-run for this receipt. Repo: `/Users/peteromalley/Documents/Arnold`,
base SHA `53584bb018` (unpushed local main). No commit/push performed by this paperwork.

## 1. Per-task completion evidence

### T-0014 — shared default-deny adapter verdict contract (CODEX) — DONE 2026-08-11

- Actor: Codex (`gpt-5.6-sol`, high reasoning) via `codex exec`; Main dispatched and verified.
- Files: `arnold_pipelines/megaplan/custody/action_validator.py` (helper at :164), `tests/cloud/test_feature_flags.py`, `tests/execute/test_authority_dispatch_validation.py`.
- Deliverable: `adapter_effect_authorized(gate_result: object) -> bool` — identity-only `gate_result is GateResult.AUTHORIZED`; None/exception/SHADOW_PASS/malformed/blocked all deny; pure, performs no effect; `wbc_runtime.py` untouched (observation-only reread carve-out preserved).
- Acceptance: focused tests **202 passed**; G3 `rg -n 'SHADOW_PASS.*AUTHORIZED|AUTHORIZED.*SHADOW_PASS'` → no matches; `git diff --check` passed.

### T-0015 — resident delivery effects (FLASH) — DONE 2026-08-11 (agent `B2ResidentDelivery`)

- Files: `arnold_pipelines/megaplan/resident/delivery_effects.py`, `arnold_pipelines/megaplan/agentbox_adapter.py`, `arnold_pipelines/megaplan/resident/cli.py`, `tests/m10/test_resident_delivery_callers.py`, `tests/resident/test_notification_production_wiring.py`, `tests/m10/test_batch6_integration.py`, `tests/arnold_pipelines/megaplan/test_agentbox_adapter.py`.
- Change: `_gate` fails closed (None → `BLOCKED_MISSING_GRANT`, raising gate → ERROR); `deliver`/`deliver_async` admit ONLY via `adapter_effect_authorized`; production constructors install explicit current gates (agentbox_adapter.py:1064/1345, resident/cli.py:1027).
- Acceptance (reported): 25 + 6 + 43 + 34 = **108 passed**; `git diff --check` clean. Verdict: Ready for G4.

### T-0016 — Git effect routes (FLASH) — DONE 2026-08-11 (agent `B2GitEffects`)

- Files: `arnold_pipelines/megaplan/chain/git_effect_adapter.py`, `tests/m10/test_git_effect_adapter_13e3.py`, `tests/m10/test_git_effect_adapter_13e4_13e5.py`, `tests/m10/test_git_effect_adapter_13e6.py`, `tests/m10/test_git_effect_adapter_13e8.py`, `tests/m10/test_batch6_integration.py` (git sections).
- Change: `_gate` fails closed (missing → ERROR, raising → typed denial); all three dispatch sites route through `adapter_effect_authorized`; no `GateResult.SHADOW_PASS` admission branch remains.
- Acceptance (reported): **124 passed** (13e3:20, 13e4_13e5:45, 13e6:31, 13e8:28) + batch6 git sections **43 passed**; `rg 'GateResult.SHADOW_PASS' git_effect_adapter.py` → no matches; `git diff --check` clean. Verdict: Ready for G4.

### T-0017 — publication effects (FLASH) — DONE 2026-08-11 (agent `B2Publication` + G4-round `C2PublicationIndeterminate`)

- Files: `arnold_pipelines/megaplan/cloud/publication_adapter.py`, `tests/cloud/test_wrapper_authority_bypass_gating.py`, `tests/m10/test_batch6_integration.py` (publication sections).
- Change: `_gate` returns None (fail-closed) instead of SHADOW_PASS; `publish` admits only via `adapter_effect_authorized` with try/except for exceptional gates; zero callbacks/reservations for missing/shadow/stale/blocked/error/exception/foreign verdicts; `publish_indeterminate` likewise gated (G4 round).
- Acceptance (reported): `-k publication` **11 passed**; full bypass-gating file **34 passed**; m10 publication **8 passed**; `git diff --check` clean.

### T-0018 — SSH effects and provider-none bypass (FLASH) — DONE 2026-08-11 (agent `B2SshEffects`)

- Files: `arnold_pipelines/megaplan/cloud/ssh_effect_adapter.py`, `arnold_pipelines/megaplan/cloud/providers/ssh.py`, `tests/m10/test_ssh_effect_adapter.py`, `tests/cloud/test_ssh_deploy.py`, `tests/cloud/test_ssh_prelaunch_observation.py`, `tests/cloud/test_isolated_chain_runner.py` (collateral).
- Change: adapter `_gate` returns `BLOCKED_WBC_MISSING` on None gate and ERROR on exception; admission `if not adapter_effect_authorized(verdict)` before protocol reservation/apply_fn; `ssh.py:2800-2803` None-adapter branch now raises `CliError('ssh_effect_adapter_unavailable')` instead of direct execution.
- Acceptance (reported): **25 + 20 + 87 + 61 = 193 passed**; blocked cases make zero transport calls; `git diff --check` OK. Verdict: Ready for G4.

### T-0019 — execute effects (FLASH) — DONE 2026-08-11 (agent `B2ExecuteEffects`)

- Files: `arnold_pipelines/megaplan/execute/effect_gate.py`, `tests/execute/test_authority_dispatch_validation.py`, `tests/execute/test_execute_frontier_authority.py`, `tests/m10/test_batch6_integration.py`.
- Change: `_gate` returns None (not SHADOW_PASS) when no gate installed; `route()` wraps gate call (exception → typed denial) and admits ONLY via `adapter_effect_authorized` before reserve_and_start/persist_intent/apply_fn/accept_outcome.
- Acceptance (reported): **59 passed** (18 new: 7 gate-variant denials with protocol spy, AUTHORIZED completion, missing-gate typed denial; 8 family×{missing,SHADOW_PASS} denials) + batch6 `TestExecuteEffectGate` **6 passed**; `rg 'SHADOW_PASS' effect_gate.py` → no matches; `git diff --check` OK. Verdict: Ready for G4.

### T-0020 — canary shadow-as-success removal (FLASH) — DONE 2026-08-11 (agent `B2CanaryShadow`)

- Files: `arnold_pipelines/megaplan/custody/canary.py`, `tests/arnold_pipelines/megaplan/test_custody_canary.py`.
- Change: `PromotionGateResult.blocked` now True for anything except AUTHORIZED (SHADOW_PASS is blocked/non-green; enforcement-off SHADOW_PASS stays a visible diagnostic that resolves blocked); exhaustive 12-value matrix test; stale 'not SHADOW' docstrings fixed.
- Acceptance (reported): `test_custody_canary.py` **68 passed + 14 subtests**; `test_zero_recovery_canary.py` **226 passed, 1 skipped**; m8 bytecode canary **1 passed**; `git diff --check` EXIT=0. Verdict: Ready for G4.

### T-0021 — bootstrap/auto command fail-closed (FLASH) — DONE 2026-08-11 (agent `B3Bootstrap`)

- Files: `arnold_pipelines/megaplan/cloud/cli.py`, `arnold_pipelines/megaplan/cloud/template.py`, `tests/cloud/test_cloud_chain_command.py`, `tests/cloud/test_editable_install_sync.py`, `tests/cloud/test_owner_lease_publisher_parity.py` (migrated caller).
- Change: `_manifest_pin_fail_closed_prefix` (exit-24 / `isolated_chain_runtime_binding_drift`) in `_bootstrap_launch_command`, `_plan_auto_command`, `_auto_command`; ENGINE_DIR only from pinned manifest `epic.runtime_root` (+ `expected_head` + runtime-provenance `--expected-root/--expected-revision`); `spec.megaplan.src_path` and `/workspace/arnold` executable roots removed; manifest-root-only `PYTHONPATH`; dead `MEGAPLAN_SRC_PATH` placeholder removed from template.
- Acceptance (reported): **112 passed** (cloud_chain_command + editable_install_sync + owner_lease_publisher_parity); collateral sanity 335 passed, 1 skipped; generated commands `bash -n` clean; `git diff --check` clean.

### T-0022 — wrapper relaunch re-reads recorded engine identity (FLASH) — DONE 2026-08-11 (agent `B3RelaunchIdentity`)

- Files: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`, `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`, `arnold_pipelines/megaplan/cloud/wrappers/arnold-cloud-discover`, `tests/cloud/test_watchdog_wrappers.py`.
- Change: `chain_engine_root_preflight` (watchdog/repair-loop) and `_chain/_plan_engine_root_preflight` (discover) re-read persisted `metadata.execution_environment.engine_root` from chain-state JSON and require it to exist (dir + `.git`) and equal manifest `epic.runtime_root` AND live import root before state load/PYTHONPATH/launch; missing/dangling/mismatch → typed `chain_runtime_binding_drift` exit 24, zero state loads/spawns; only accepted root on PYTHONPATH.
- Acceptance (reported): **63 focused tests passed** (10 new + 11 updated fixtures + helper registration); `bash -n` on all three wrappers; `git diff --check` clean. Two unrelated full-wrapper attestation failures confirmed pre-existing on pristine wrappers (stash proof). Verdict: Ready for G5.

### T-0023 — retire remaining runtime selectors (FLASH) — DONE 2026-08-11 (agent `B3Selectors`)

- Files: `agentbox/services.py`, `arnold_pipelines/megaplan/cloud/feature_flags.py`, `arnold_pipelines/megaplan/cloud/runtime_attestation.py`, `arnold_pipelines/megaplan/cloud/runtime_census.py`, `arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-resident`, `arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl`, `arnold_pipelines/megaplan/cloud/wrappers/arnold-cloud-discover`, `arnold_pipelines/megaplan/cloud/wrappers/arnold-discord-dm`, `arnold_pipelines/megaplan/cloud/wrappers/arnold-kimi-goal-operator`, `arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`, `scripts/cloud_hot_upload.py`, `tests/agentbox/test_services.py`, `tests/cloud/test_ssh_deploy.py`, `tests/cloud/test_watchdog_wrappers.py`.
- Change: `MEGAPLAN_RUNTIME_SRC`, `MEGAPLAN_DISCOVER_ARNOLD_SRC`, `KIMI_GOAL_ARNOLD_SRC`, `MEGAPLAN_DISCORD_DM_ARNOLD_SRC` selection reads removed; resident/kimi/Discord runtime identity derives from `ARNOLD_RUNTIME_MANIFEST → epic.runtime_root` or fails closed (exit 78 / SystemExit); entrypoint tmux launches gated on the manifest pin; ghost `ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED` no longer read/forwarded (L3 policy is a static heredoc); `ARNOLD_REPAIR_TRIGGER_SESSION_ALLOWLIST` documented as nonexistent (no reader created); `MEGAPLAN_AUDIT_SESSION_ALLOWLIST` report-only comments; retired selector names added to deny-lists.
- Acceptance (reported): `rg 'MEGAPLAN_RUNTIME_SRC|MEGAPLAN_LAUNCH_RUNTIME_SRC|MEGAPLAN_SUPERVISOR_SOURCE'` over systemd/templates/wrappers → zero selection reads (only documented NON-SELECTING `MEGAPLAN_SUPERVISOR_SOURCE_ROOT` internal binding, E5 item 15); `bash -n` on all touched shells + rendered entrypoint rc=0; `py_compile` OK; wrapper/resident suites 15+5+10+27 pass; `git diff --check` clean. Verdict: Ready for G5.

### T-0024 — manifest readers distinguish absent from invalid (FLASH) — DONE 2026-08-11 (agent `B3ManifestReaders`)

- Files: `arnold_pipelines/megaplan/chain/__init__.py` (`_reconcile_scope_manifest` :6661 wired at :8073), `arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep` (`_json_get` + per-manifest loop), `tests/arnold_pipelines/megaplan/chain/test_reconcile_milestone.py`, `tests/cloud/test_runtime_lifecycle.py`, `tests/cloud/test_launcher_manifest_conformance.py`.
- Change: reconcile-scope reader — absent → None (scope degrades to pr_required/uncertain), present-but-invalid (corrupt/schema) → typed `CliError('reconcile_manifest_invalid')` (reconcile blocked, never waived); gc-sweep — corrupt manifest → `NEEDS-RECONCILE` + continue, tree never deletable; raw-but-fail-closed readers (cli.py:3513/3708, epic_chain.py:411, current_target.py:96, arnold-chain/close/promote/runtime-create) verified, not rewritten.
- Acceptance (reported): reconcile_milestone **34 passed** (3 new); lifecycle corrupt cases **3 passed**; launcher conformance **2 passed**; gc-sweep regression sweep **11 passed**; `bash -n` gc-sweep OK; `git diff --check` OK; `py_compile` OK. Verdict: Ready for G5.

### T-0025 — publication/runner views gated on coherent current envelopes (CODEX) — DONE 2026-08-11 (agent `B3ViewsGate`)

- Files: `arnold_pipelines/megaplan/authority/views.py`, `tests/arnold_pipelines/megaplan/test_authority_views.py`.
- Change: `_observation_gate_reason()` fail-closed coherence+currency gate (uses `ObservationEnvelope.is_dispatchable` + reducer run_id/run_revision/source_cursor semantics); gated envelopes excluded from projection, surfaced as `non_coherent_observation`/`stale_observation`, force `ready`/`live` → `pending`/`unknown`; plain mappings carry no coherence claim and are admitted as before (existing callers unaffected); read-only.
- Acceptance (reported): test_authority_views.py **38 passed** (31 pre-existing + 7 new); m9 consumers **22 passed**; `git diff --check` clean. Verdict: Ready for G5.

### T-0026 — stale legacy-label semantic decision locked (FLASH) — DONE 2026-08-11 (agent `B3LegacyLabel`)

- Files: `tests/run_authority/test_dependency_closure.py`, `arnold_pipelines/run_authority/reducer.py` (doc-only comment).
- Change: test corrected to the reducer's actual precedence — legacy label with old `run_revision` → `stale_observation_cannot_authorize_dispatch`; legacy label carrying the view's revision → `unknown_observation_cannot_authorize_dispatch`. Reducer behavior unchanged (stale branch precedes unknown; comment now states precedence explicitly).
- Acceptance (reported): dependency_closure + test_reducer **32 passed**; `git diff --check` clean. Verdict: Ready for G5.

### T-0027 — every destructive route behind the complete census (FLASH) — DONE 2026-08-12 (three parallel slices)

See section 4 for the census store/route summary. Slice-level evidence:

- **Slice 1 — census stores** (agent `T27CensusStores`): `arnold_pipelines/megaplan/cloud/runtime_references.py` + `arnold_gc_sweep` comment updates + `tests/cloud/test_runtime_lifecycle.py`. Acceptance: `py_compile` OK; `bash -n` gc-sweep OK; `pytest -q tests/cloud/test_runtime_lifecycle.py -k 'gc_sweep'` → **31 passed** (26 pre-existing + 5 new: per-plan lease REFERENCED no-delete, managed-run REFERENCED no-delete, status-snapshot REFERENCED no-delete, ops schedule-input REFERENCED no-delete, corrupt per-plan lease → UNKNOWN exit 5); CLI smoke: each new store returns `STATUS REFERENCED`, corrupt `.history.jsonl` → `STATUS UNKNOWN`; `git diff --check` clean.
- **Slice 2 — wrapper + agentbox + cli routes** (agent `T27WrapperRoutes`): `arnold_pipelines/megaplan/cloud/wrappers/arnold-supervisor-runtime`, `agentbox/cleanup.py`, `arnold_pipelines/megaplan/cli/__init__.py`, `arnold_pipelines/megaplan/cloud/cli.py` (chain-reset heredoc), `tests/agentbox/test_cleanup.py`, `tests/cloud/test_runtime_lifecycle.py`. Acceptance: `bash -n` OK; lifecycle + cleanup **75 passed** (63 + 12); focused `-k 'supervisor_runtime or fresh_reset or chain_state_reset or apply_delete or survey_cleanup'` **16 passed**; m10 mutation-inventory `-k 'TestActionOffRows or test_no_stale_anchor'` **10 passed**; watchdog `-k 'supervisor or runtime_prepare'` **3 passed**; cloud_chain_command **99 passed**; spies: zero `rm -rf`/`branch -D`/`worktree remove` on REFERENCED/UNKNOWN, exact single delete on CLEAR; `git diff --check` OK.
- **Slice 3 — chain/rebind routes** (agent `T27ChainRoutes`): `arnold_pipelines/megaplan/chain/git_ops.py` (3 reconcile PR branch-delete sites + auto-merge `--delete-branch`), `arnold_pipelines/megaplan/chain/target_rebind.py` (`_restore_git` rollback), `arnold_pipelines/megaplan/chain/git_effect_adapter.py` (worktree removal), `tests/arnold_pipelines/megaplan/chain/test_reconcile_pr.py`, `tests/arnold_pipelines/megaplan/test_chain_worktree_safety.py`, `tests/arnold_pipelines/megaplan/test_chain_target_rebind.py`, `tests/m10/test_git_effect_adapter_13e8.py`. Acceptance: **137 passed, 1 deselected** (pre-existing cherry-pick SHA-collision flake, confirmed on pristine sources via stash); worktree_safety 46, target_rebind 38, 13e8 28; spies prove zero branch delete / push `--delete` / worktree remove on REFERENCED/UNKNOWN and CLEAR-proceeds-with-authority for every route; `git diff --check` clean.

## 2. Oracle gate verdicts

| Gate | Verdict | Oracle run | Evidence |
|---|---|---|---|
| G3 (shared effect policy) | **GO** | 2026-08-11T16:49Z | Main verified the frozen helper directly (identity-only `GateResult.AUTHORIZED`, broad input type, pure, exhaustive enum tests at test_feature_flags.py:719-724 + test_authority_dispatch_validation.py); Batch 0B.2 dispatched 16:49:50Z on the frozen API. |
| G4 (all effect boundaries closed) | **GO** | 2026-08-12T05:25Z (after 18 rounds) | All six adapters PASS (`adapter_effect_authorized` sole admission, no direct-provider/SHADOW_PASS admission, production constructors gate explicitly); full verdict in Main session: "G4 fully PASS — all 6 adapters." |
| G5 (launch and truth closure) | **GO** | 2026-08-12T05:25Z (after 18 rounds) | All six launch/truth criteria green — manifest-pinned launches before state read, invalid manifests cannot collapse to absence, public views cannot green raw/stale evidence, all five E5 selection instances gone; oracle: "Safe to proceed to T-0027? Yes. Safe to proceed to G6? Yes." |
| G6 (Phase 0B exit) | **NO-GO — after 8 rounds** | 2026-08-12 (first run 05:56Z; rounds 2–8 same day) | 13 real defects closed by N1–N3, O1–O5, P1–P4, P5 + paperwork by N4 (see section 3); three recurring false positives documented (action_validator.py:331, raw-but-fail-closed class, ops-store test proof); re-run pending round-8 fix verification. |

## 3. G6 gate runs (rounds 1–8, Codex oracle) — findings and closing fixes

Every round ended **NO-GO**; the round number is the oracle re-run ordinal. Each real
finding was closed by the named fixer before the next round; rounds 5 and 7 produced
no code fix (verified-sanctioned / false positive). Fixer yields are the source of
truth for the file/acceptance details; all 14 fixer tasks (N1–N4, O1–O5, P1–P4, P5)
reported "Ready for G6 re-run".

- **Round 1 (first run, 2026-08-12T05:56Z) — 3 real T-0027 census holes + paperwork:**
  1. Per-plan leases contain **no path field** — census only matches JSON path values, so `chain reset` can return CLEAR and `rmtree(plan_dir)` even with a live lease (worker_dispatch_wbc.py:613 vs runtime_references.py matching) → **N1PlanLeaseNoPath** (store-presence-is-the-reference for `<plan>/custody/leases`; files parsed first, corrupt → UNKNOWN; empty store still CLEAR).
  2. Managed-run manifests use `context_directory.resident_runtime_source` — absent from `_PATH_KEYS` (runtime_references.py:117) → **N2ManagedRunPathKey** (dotted managed-run keys matched by `walk()`; missing key is not a reference).
  3. Epic-chain `--fresh` directly `state_path.unlink()` with no census (cloud/cli.py:5749) → **N3EpicChainFreshCensus** (embedded canonical census before any unlink/rmtree; non-CLEAR → blocked, state + plan dir untouched; wrapper raises `epic_chain_state_reset_blocked`).
  - Paperwork missing (no receipts) → **N4RecordCompletion** (this document + tasklist).
  - False positive noted: `action_validator.py:331` blocked property (verified correct — see below).

- **Round 2 — 5 findings:**
  1. `arnold-discord-dm` raw `json.loads` of a schema-less/compatibility_only manifest before importing production code → **O1DiscordDmCanonical** (canonical manifest validation in a child interpreter BEFORE any sys.path mutation/import; schema-less/compatibility_only/missing-root → typed SystemExit, fail closed).
  2. `cli.py:3503` raw `json.load(...).get('epic',{}).get(field,'')` drives ENGINE_DIR → **O2CliBootstrapCanonical** (`_pinned_manifest_field_read` gated on the canonical manifest schema; schema-invalid → empty read → existing pin gate exit 24, no launch).
  3. `bakeoff/worktree.py:165` + `lifecycle.py:164` uncensused worktree delete → **O3BakeoffCensus** (`remove_worktree` runs the reference census before any git command; REFERENCED/DANGLING/UNKNOWN → typed `WorktreeDeleteRefused`; raw `shutil.rmtree` fallback re-censused, refuses on non-CLEAR).
  4. `arnold-watchdog:7371` `gh pr merge --delete-branch` without census → **O4WatchdogGhMerge** (watchdog `_reference_census` mirrors `git_ops.py`; non-CLEAR omits `--delete-branch` from both the `--auto` attempt and the `--squash` fallback, with a durable refusal note).
  5. `runtime_references.py:341` dangling store symlink collapsed to CLEAR → **O5CensusDanglingSymlink** (dangling store symlink / dangling plan-lease root → UNKNOWN fail-closed; only true ENOENT stays not-a-reference).

- **Round 3 — 2 collapse-to-success findings:**
  1. `arnold-gc-sweep` returns success after a REFERENCED/DANGLING census skip and the finalizer records `swept:true` → **P1GcSweepSkipOutcome** (per-slug stdout markers `SWEPT=YES` / `SWEPT=NO:<verdict>`; exit codes unchanged; dry-run emits no markers).
  2. Terminal finalizer writes `swept:true` unconditionally → **P2FinalizerSweptTruth** (`_parse_gc_sweep_outcome` keys on the SWEPT= marker protocol with legacy fallback; `swept:true` ONLY on proven CLEAR removal — every skip/block → `swept:false` + blocked, never false completion).

- **Round 4 — 1 finding:** non-GC census callers pass the active manifest as `current_manifest` (excluded from the scan → REFERENCED/UNKNOWN collapse to CLEAR) at `agentbox/cleanup.py:67`, `cli/__init__.py:3065`, `cloud/cli.py:4562,5835` → **P3NonGcCurrentManifest** (`current_manifest=''` everywhere; active manifest scanned as a reference; 8 new route tests REFERENCED-refuse + corrupt-UNKNOWN).

- **Round 5 — 1 finding, VERIFIED SANCTIONED (no fix):** raw-but-fail-closed readers (`cli.py:3513/3708`, `epic_chain.py:411`, `current_target.py:96`, `arnold-chain/close/promote/runtime-create`) plus the kimi manifestless permit — verified as the T-0024 sanctioned fail-closed class (absent → None/absence, present-but-invalid → typed failure); no code change, addendum clarified.

- **Round 6 — 1 finding:** `chain reset` AND `epic-chain --fresh` corrupt STATE file degrades to `{}` → `plan_dir=None` → CLEAR → unlink (cli.py:4521,5783) → **P4ResetCorruptState** (parent-state path: `status=blocked`, `reason='state_unreadable: <exc>'`, `plan_dir=null`, zero unlink/rmtree; non-dict JSON root also flagged).

- **Round 7 — 1 finding, FALSE POSITIVE (no fix):** ops schedule-input store flagged "unproved" — the existing test `test_runtime_lifecycle.py:1157` uses the exact production shape `schedule-inputs/<input-id>/payload.json` and passes; no defect, no fix.

- **Round 8 — 1 finding:** epic-chain reset CHILD chain-state corrupt → `child_raw={}` → `plan_dir=None` → CLEAR → parent `state_path.unlink()` (cli.py:5844) → **P5ChildStateReset** (this fix: unreadable/non-dict CHILD state → `status=blocked`, `reason='child_state_unreadable: <exc>'`, `plan_dir=null`, parent state + plan dir preserved, zero unlink/rmtree; valid child state keeps the existing census+CLEAR delete path).

### Recurring false positives (NOT defects — do not "fix")

- `SHADOW_PASS.blocked` at `arnold_pipelines/megaplan/custody/action_validator.py:331` — `return self.gate_result not in {GateResult.AUTHORIZED, GateResult.SHADOW_PASS}` — verified correct across 5 prior rounds (round 1 and re-runs). This IS the blocked classification: `SHADOW_PASS` is shadow-mode non-blocking **by design** (enforcement disabled → shadow observation), and **no adapter admits it** — `adapter_effect_authorized` at :164 is the only admission path and it is identity-only. The oracle has repeatedly misread this property despite the G4/G5 addendum; it must not be changed.
- `canary.py:423` — `PromotionGateResult.blocked` returns `self.gate_result != PromotionGateDecision.AUTHORIZED`. This is the T-0020 fixed behavior: `SHADOW_PASS` is a visible diagnostic but resolves **blocked / never green** — it can never yield a green canary or a dispatch receipt. It is deliberately stricter than `action_validator.py:331` (the canary has no shadow-mode observation carve-out). Correct as-is; must not be changed.
- Raw-but-fail-closed readers (round 5) — verified sanctioned (T-0024): absent → None/absence, present-but-invalid → typed failure; never a silent success. Do not "fix" into eager validation.
- Ops schedule-input store (round 7) — "unproved" was a false positive; `tests/cloud/test_runtime_lifecycle.py:1157` exercises the exact production `schedule-inputs/<input-id>/payload.json` shape and passes.

## 4. T-0027 census store/route summary

New store families wired into `runtime_references.py` `run_census` (env-var defaults + CLI; each: missing dir is NOT a reference, present-but-unreadable/corrupt → UNKNOWN which blocks deletion):

| Store | Default paths | Notes |
|---|---|---|
| plan-lease | `ARNOLD_REFERENCE_PLAN_LEASE_ROOT` = `/workspace/.megaplan/plans` (+ workspace-relative globs at 3 depths) | per-plan `<plan>/custody/leases` — matches worker_dispatch_wbc.py:613 / phase_wbc.py:937 open paths |
| managed-run | `ARNOLD_REFERENCE_MANAGED_RUN_STORE` = `/workspace/arnold/.megaplan/plans/resident-subagents` + `fixer-sessions` | nested depth 1 (per-run `manifest.json`); matches resident/subagent.py `DEFAULT_MANAGED_RUN_ROOT` |
| status | `ARNOLD_REFERENCE_STATUS_DIR` = `/workspace/.megaplan/status` | cloud-status.json / .previous.json / progress-history.jsonl |
| ops | `ARNOLD_REFERENCE_OPS_STORE` = `/workspace/.megaplan/ops/schedules` + `/workspace/.megaplan/schedule-inputs` | recurses depth 2 for `<input-id>/SKILL.md` payload dirs; matches probe_records.py + docs/recoverability-20260807.md |

Destructive routes now gated on a fresh readable zero-reference (CLEAR) census verdict; REFERENCED/DANGLING/UNKNOWN refuse with zero deletion; `--force`/`--fresh`/`--restore-proven` are never evidence:

| Route | Site | Gate |
|---|---|---|
| supervisor venv rebuild `rm -rf` | `wrappers/arnold-supervisor-runtime:103` | census on exact runtime root before rebuild (exit 5 non-CLEAR) |
| agentbox cleanup `_apply_delete` (branch -D + worktree remove) | `agentbox/cleanup.py` | CLEAR required before any destructive git call |
| CLI `--fresh` (worktree remove --force + branch -D) | `arnold_pipelines/megaplan/cli/__init__.py:3087,3099` | `worktree_reset_refused` CliError on non-CLEAR |
| chain-reset `rmtree(plan_dir)` | `cloud/cli.py:4405` (generated script, embedded census) | non-CLEAR leaves state file AND plan dir untouched |
| reconcile PR branch deletes (`gh pr merge --delete-branch`, `push origin --delete`, `branch -D`) | `chain/git_ops.py:2133,2175,2593` | `_reference_census` gate; non-CLEAR drops delete |
| rollback `git branch --delete --force` | `chain/target_rebind.py:522` | `PROJECT_SOURCE_REBIND_ERROR` on non-CLEAR |
| Git-adapter worktree removal | `chain/git_effect_adapter.py` `route_worktree action=remove` | FAILED outcome + census evidence before reservation |

## 5. File digests (this paperwork)

| File | SHA-256 |
|---|---|
| docs/fixer-recovery-tasklist-20260811.md | `5bf875a4388d5bc9f54acb0a3868f8f308d6673be678942894e40a0ae8dda65e` |
| docs/fixer-recovery-evidence/phase0b-receipts.md | `8c3b7e7c56fe2fe42b0c8bc863b80bfd061c6cf2c62bc33dfe6897886ee74fd3` (of sections 1–4, excluding this self-referential section 5) |

Digests are recorded here so the oracle can content-address this receipt; recompute with
`shasum -a 256 docs/fixer-recovery-tasklist-20260811.md docs/fixer-recovery-evidence/phase0b-receipts.md`.
