# Fixer recovery task list (2026-08-11)

- Legend: `FLASH` = mechanical/well-scoped DeepSeek-flash task; `CODEX` = genuinely hard invariant work; `OPERATOR` = human-authorized external mutation. Tasks in one batch run in parallel; batches run sequentially. The plan uses 14 oracle gates, `G1`–`G14`; G14 is re-entrant for operational windows.
- Source anchors are the current checkout on 2026-08-11. Re-resolve symbols with `rg -n` if edits move a line; do not substitute a similarly named twin module.
- Execution root is `/Users/peteromalley/Documents/Arnold`. Focused tests only; do not run formatters or the project-wide suite. Every implementation task ends with `git diff --check` and preserves unrelated dirty files.
- Authority boundary: the 30-minute loop may observe, append evidence, enqueue/join one canonical deduplicated repair request, reclaim an expired fenced claim, invoke an already-approved allowlisted retry/relaunch, and schedule independent verification. It may not push `main`, deploy/promote, rebind a manifest/runtime, uncancel hourly work, resolve a PR gate, change profiles/budgets, introduce a repair class, force-proceed/waive, directly edit plan/chain JSON, or perform destructive Git/provider actions.
- Absolute prohibitions: no `git reset --hard`; no hand-edit of a manifest pin; no blanket refresh of runtime trees; no disabling enforcement/attestation; no autonomous `ARNOLD_META_REPAIR_ENABLED=1`; no recovery claim based only on a commit, passing test, agent completion, PID/tmux, fresh activity, or a green status label.
- Durable execution evidence goes under `docs/fixer-recovery-evidence/`. Each receipt records UTC time, actor/model, command, exit code, input/output SHA-256, and the relevant Git SHA or occurrence IDs. A gate is read-only and never fixes what it reviews.

## Phase 0 (DONE — stop making it worse) — coherent runtime truth, fail-closed divergence, and reference-safe GC

### Batch 0.1 — DONE — S1–S12 read-only census and test baseline

- [x] T-0001 `FLASH` Census S1–S4: manifests, recorded roots, live imports, and wrapper provenance
    Files: `/workspace/.megaplan/*.json`; `/workspace/**/.megaplan/plans/.chains/chain-*.json`; `/workspace/.megaplan/cloud-sessions/*.json`; `/workspace/runtime-candidates/*`; `/workspace/megaplan-maintenance/Arnold/.megaplan/initiatives/megaplan-maintenance/cloud.yaml`; `docs/fixer-recovery-evidence/census-S1-S4.md`
    Change: Read only. S1 inventories every runtime manifest and its `runtime_id`, state, branch, expected head, runtime root, repair bin, dependency/venv field, and generation. S2 inventories every recorded `metadata.execution_environment.engine_root` and classifies it `present`, `missing`, `conflicted`, `shared`, or `null`. S3 resolves the actual imports for chain, watchdog, and resident interpreters with `python -c 'import arnold_pipelines; print(arnold_pipelines.__file__)'`. S4 hashes the invoked wrappers and compares recorded root = manifest root = live import root = wrapper source; any missing/torn/cross-environment value is `UNKNOWN` or `INCOHERENT`, never green. Record the exact known four-tree split and the v3-r7/megaplan-maintenance shared-root collision.
    Acceptance: `python -m arnold_pipelines.megaplan cloud status --all --compact --cloud-yaml .megaplan/initiatives/megaplan-maintenance/cloud.yaml` exits 0; `docs/fixer-recovery-evidence/census-S1-S4.md` contains headings `S1` through `S4`, exact paths and SHAs for the executed candidate, epic worktree, watchdog tree, and resident tree, plus a non-green coherence verdict for every mismatch; `git diff --check` passes.

- [x] T-0002 `FLASH` Census S5–S8: liveness, repair identity, queue relations, and mutation gates
    Files: `/workspace/watchdog-reports/*.json`; `/workspace/watchdog-report.json`; `/workspace/.megaplan/repair-queue/requests/*`; `/workspace/.megaplan/repair-queue/decisions/*`; `/workspace/.megaplan/repair-queue/claims/*`; `/workspace/.megaplan/repair-queue/attempts/*`; `/workspace/.cloud-hot-env`; `/workspace/.megaplan/cloud-sessions/*`; `docs/fixer-recovery-evidence/census-S5-S8.md`
    Change: Read only. S5 records runner lease/fence/process-birth evidence and distinguishes authoritative liveness from legacy PID/tmux diagnostics. S6 joins the current occurrence across request → decision → claim → attempt and explicitly records absent IDs and `zero_authority_rejected`. S7 records ordinary/meta/audit repair gates (`ARNOLD_AUTONOMY`, `ARNOLD_REPAIR_TRIGGER_ENABLED`, `ARNOLD_META_REPAIR_ENABLED`) without printing secret values. S8 inventories PAUSED/BLOCKED sessions, `alive_sessions`, the current failure signature, and whether an approved canonical request path exists. Redact credentials and tokens.
    Acceptance: `docs/fixer-recovery-evidence/census-S5-S8.md` contains headings `S5` through `S8`, the `megaplan-maintenance` session/plan/failure identity, all available request/blocker/claim/attempt IDs, `alive_sessions`, and an explicit `claimable: yes|no|unknown`; `rg -n '(TOKEN|API_KEY|SECRET)=.' docs/fixer-recovery-evidence/census-S5-S8.md` returns no matches; `git diff --check` passes.

- [x] T-0003 `FLASH` Census S9–S12: dependency, GC, schedule, and reconciliation references
    Files: `/workspace/runtime-candidates/*`; `/workspace/**/.megaplan/runtime/editable-engine`; `/workspace/.megaplan/ops/schedules/*`; `/workspace/arnold/.megaplan/resident/scheduled_jobs/*`; `/workspace/.megaplan/*.json`; `/workspace/**/.megaplan/plans/.chains/chain-*.json`; origin branch refs for `fixer/*`, `reconcile/*`, and `editible-install`; `docs/fixer-recovery-evidence/census-S9-S12.md`
    Change: Read only. S9 lists every declared venv/dependency field and proves whether the path exists; include empty editable-engine shells. S10 computes the union of runtime-root references from manifests, live/paused chain states, markers, schedules/jobs, and repair claims, separately reporting dangling targets. S11 records hourly job state plus whether a due-job consumer and launch receipt exist. S12 records reconcile outcomes/branches, orphan fixer branches, broken worktrees/conflicted candidates, close/restore/GC receipts, and the legacy `editible-install` branch reference.
    Acceptance: `docs/fixer-recovery-evidence/census-S9-S12.md` contains headings `S9` through `S12`, all nine known dangling engine roots, the broken `critique-session-binding-20260723` worktree, cancelled hourly jobs, and `P6 live successes: 0` unless contrary receipts are cited by path+digest; no command in the receipt mutates Git, schedules, manifests, or runtime trees; `git diff --check` passes.

- [x] T-0004 `FLASH` Capture focused baseline test counts and fallback inventory
    Files: `tests/cloud/test_watchdog_wrappers.py`; `tests/cloud/test_cloud_chain_command.py`; `tests/cloud/test_editable_install_sync.py`; `tests/arnold_pipelines/megaplan/test_chain_execution_binding.py`; `tests/arnold_pipelines/megaplan/test_epic_chain.py`; `tests/cloud/test_runtime_lifecycle.py`; `docs/fixer-recovery-evidence/baseline-tests.md`
    Change: Run each named file separately so failures are attributable; record passed/failed/skipped counts and every remaining positive fallback assertion for `ENGINE_DIR`, `/workspace/arnold`, manifestless production, `SYNC_BRANCH`, `MEGAPLAN_*_SRC`, editable installs, or compatibility-pointer selection. Do not modify tests in this task.
    Acceptance: the six `pytest -q <file>` commands are present with exit codes in `docs/fixer-recovery-evidence/baseline-tests.md`; `rg -n 'ENGINE_DIR|/workspace/arnold|manifestless|SYNC_BRANCH|MEGAPLAN_(LAUNCH_)?RUNTIME_SRC|pip install -e|compatibility_only' tests/cloud tests/arnold_pipelines/megaplan` output is attached; `git status --short` shows no task-created source changes.

### Oracle gate G1 — DONE — census completeness and safe starting point

Criteria: Codex reads `docs/fixer-recovery-evidence/census-S1-S4.md`, `census-S5-S8.md`, `census-S9-S12.md`, and `baseline-tests.md`; checks the live evidence against `cloud/cli.py:3549-3606`, `chain/epic_chain.py:373-379,667-699`, `arnold-gc-sweep:90-230`, and `repair_requests.py:954-968`; and returns GO only if all S1–S12 slices are timestamped, content-addressed, non-mutating, and every missing/torn/cross-root condition is non-green. NO-GO if any tree, queue seam, schedule, or GC reference class is unobserved.

### Batch 0.2 — DONE — fail-closed contracts and deletion safety

- [x] T-0010 `FLASH` Specialize `ObservationEnvelope` for coherent multi-source decisions
    Files: `arnold_pipelines/run_authority/contracts.py:160-194`; `arnold_pipelines/run_authority/reducer.py`; `arnold_pipelines/run_authority_store.py`; `tests/arnold_pipelines/run_authority/test_contracts.py`; `tests/arnold_pipelines/run_authority/test_reducer.py`; `tests/run_authority/test_dependency_closure.py`
    Change: Extend `ObservationEnvelope` with validated source identities/versions/cursors/content hashes and a typed coherence result (`COHERENT`, `UNKNOWN`, `INCOHERENT`) plus reasons. Preserve legacy deserialization only as explicitly typed unknown evidence. Add a runtime-observation validator requiring one capture to agree on recorded engine root, manifest runtime root/expected head, live import root, wrapper digest, dependency generation, and environment/session identity; incomplete, stale, cross-environment, or contradictory input must not construct a dispatchable coherent envelope. The reducer must never collapse unknown/incoherent evidence to success.
    Acceptance: `pytest -q tests/arnold_pipelines/run_authority/test_contracts.py tests/arnold_pipelines/run_authority/test_reducer.py tests/run_authority/test_dependency_closure.py` passes; tests prove complete agreement → coherent, missing source → unknown, disagreement → incoherent, legacy record → unknown, and no non-coherent envelope can authorize dispatch; `git diff --check` passes.

- [x] T-0011 `FLASH` Remove launch fallback and enforce recorded/manifest/live root equality before relaunch
    Files: `arnold_pipelines/megaplan/cloud/cli.py:3549-3606,3944-3980`; `arnold_pipelines/megaplan/chain/epic_chain.py:373-379,667-699`; `arnold_pipelines/megaplan/chain/execution_binding.py`; `tests/cloud/test_cloud_chain_command.py`; `tests/cloud/test_editable_install_sync.py`; `tests/arnold_pipelines/megaplan/test_epic_chain.py`; `tests/arnold_pipelines/megaplan/test_chain_execution_binding.py`
    Change: Delete the `ENGINE_DIR=<caller/shared path>` fallback. Every production chain start must have a readable per-session `ARNOLD_RUNTIME_MANIFEST`, nonempty `epic.runtime_root` and `epic.expected_head`, and a successful `runtime_provenance` check, regardless of `isolated_chain_runner`. At child relaunch, re-read persisted `metadata.execution_environment.engine_root`; require it to exist and equal the manifest root and `megaplan_engine_root()` live import root before state load/spawn, then prepend only that accepted root to `PYTHONPATH`. Exit with typed runtime-binding drift before `load_chain_state`, `bind_execution_identity`, or `subprocess.run` on any missing/dangling/mismatch input.
    Acceptance: `! rg -n 'if \[ -z "\$ENGINE_DIR" \]; then ENGINE_DIR=' arnold_pipelines/megaplan/cloud/cli.py`; `pytest -q tests/cloud/test_cloud_chain_command.py tests/cloud/test_editable_install_sync.py tests/arnold_pipelines/megaplan/test_epic_chain.py tests/arnold_pipelines/megaplan/test_chain_execution_binding.py -k 'runtime or engine_root or manifest or binding'` passes; behavioral spies prove rejected admission calls neither state load nor bind/spawn; `git diff --check` passes.

- [x] T-0012 `FLASH` Make runtime GC reference-complete and fail closed on unreadable reference state
    Files: `arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep:84-278`; `arnold_pipelines/megaplan/cloud/runtime_references.py` (new); `tests/cloud/test_runtime_lifecycle.py`
    Change: Add one canonical, injectable reference census used before every worktree/branch/dependency deletion. Normalize exact runtime-root paths from runtime manifests; active/paused/blocked chain `metadata.execution_environment.engine_root`; cloud-session and chain-health markers; resident/ops schedules and jobs; occurrence requests, decisions, active claims, attempts, and leases. A reference hard-skips deletion; a dangling reference emits `NEEDS-RECONCILE`; unreadable/corrupt reference stores make the decision `UNKNOWN` and block deletion. Preserve existing closed-only, origin, open-PR, and restore-proof gates; never use slug/SHA substring matching as the only predicate.
    Acceptance: `bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep` passes; `pytest -q tests/cloud/test_runtime_lifecycle.py -k 'gc_sweep'` passes with one no-delete fixture per reference class plus dangling and corrupt-store cases; a spy proves `git worktree remove` and branch deletion are not called on reference/unknown; `git diff --check` passes.

### Batch 0.3 — DONE — prior admission and action-boundary regression lock

- [x] T-0013 `FLASH` Lock in prior admission, journal-before-effect, default-deny, and selector-removal guarantees
    Files: `arnold_pipelines/megaplan/cloud/runtime_manifest.py`; `arnold_pipelines/megaplan/chain/spec.py`; `arnold_pipelines/megaplan/chain/__init__.py:6988-7005`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-supervisor-runtime-lib`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-run`; `arnold_pipelines/megaplan/cloud/feature_flags.py`; `tests/cloud/test_runtime_manifest.py`; `tests/cloud/test_watchdog_wrappers.py`; `tests/cloud/test_feature_flags.py`
    Change: Add/repair regression tests, without inventing a compatibility path, proving: per-session manifest binding has no global-pointer selection; `compatibility_only` survives create→promote→close and stays non-authoritative; unbound trusted production and direct leaf wrappers block before effects; required runtime transition writes precede meta/manual/mechanical/`arnold-run` launches and ledger failure blocks them; `SHADOW_PASS`, explicit-disable values, or missing attestation never authorize a WBC effect; deleted source selectors are absent. Fix only the concrete regressions exposed by these tests.
    Acceptance: `pytest -q tests/cloud/test_runtime_manifest.py tests/cloud/test_watchdog_wrappers.py tests/cloud/test_feature_flags.py -k 'compatibility_only or manifest or ledger or transition or shadow or attestation or selector'` passes; `rg -n 'MEGAPLAN_SUPERVISOR_SOURCE|MEGAPLAN_LAUNCH_RUNTIME_SRC|MEGAPLAN_RUNTIME_SRC|SYNC_BRANCH' arnold_pipelines/megaplan/cloud --glob '!templates/entrypoint.sh.tmpl'` has no selector reads (fixed literal diagnostic exports may remain and must be commented as non-selecting); `git diff --check` passes.

### Oracle gate G2 — DONE — Phase 0 exit: fail-closed hardening complete

Criteria: Codex reviews `contracts.py:178`, `cloud/cli.py:3549-3606`, `epic_chain.py:373-379,667-699`, `arnold-gc-sweep:84-278`, `runtime_manifest.py:60-102`, `chain/__init__.py:6988-7005`, all T-0013 regression results, and the full Phase 0 diff. GO requires root mismatch/missing pin to block before launch/state load, no silent shared-root fallback, non-coherent envelopes to be non-dispatchable, GC to refuse every referenced/unknown root, compatibility pointer cannot select, ledger failure blocks all covered effects, `SHADOW_PASS` cannot authorize, and deleted selectors stay absent. NO-GO on any production manifestless path, raw fallback, delete-on-unknown behavior, regression, or unreviewed overlap. Phase 0 must be committed before Phase 1 publication.

## Supersession and sequencing decision

- **Recommendation:** complete all of Phase 0B before publishing or deploying. The live epic remains safely blocked on `blocked_no_lease` until G6. G7 then publishes one reviewed lineage containing `53584bb018` plus all Phase 0B closures, stages a new immutable runtime, CAS-rebinds, and resumes the same occurrence. Deploying E4 plus `53584bb018` early is rejected because it could restart effects while launch selection, public views, corrupt-manifest handling, and deletion routes still admit incoherent evidence.
- **Task crosswalk:** old T-0203 is expanded across T-0202/T-0203 to cover `auto.py:2675`, exception swallowing, the six `repair_unavailable` exits, and the watchdog return. Old T-0205 is split: the five-adapter authorization portion moves forward to T-0014–T-0019; atomic lease append and `dispatch_key` remain T-0205. Old T-0207 is strengthened by T-0025 and T-0207. Old T-0208 is expanded by T-0023 and T-0208. Old T-0101/T-0110/T-0120/T-0121 become one operator-owned canary transaction, T-0101. Old T-0301/T-0310–T-0313 become T-0301. Old T-0401/T-0402/T-0410 become T-0401 with the schedule kept cancelled. Old T-0601–T-0604 become T-0601; old T-0610/T-0611/T-0612/T-0620 become T-0610.
- **Parallelism rule:** tasks listed in one batch have disjoint write ownership and may run in parallel. Batches are sequential. Every batch returns to its named gate; G14 is re-entrant for each operational watcher/recovery batch.

## Phase 0B (systemic closure) — close every enumerated fail-open before live motion; BLOCKED-BY: G2 DONE

### Batch 0B.1 — freeze one effect-authorization contract

- [x] T-0014 `CODEX` Define the shared default-deny adapter verdict contract — DONE 2026-08-11 (Codex gpt-5.6-sol): `adapter_effect_authorized(gate_result)` at action_validator.py:164 — identity-only `GateResult.AUTHORIZED` admission; exhaustive enum tests; **202 focused tests passed**, G3 `rg` no matches, `git diff --check` clean; wbc_runtime.py untouched.
    Files: `arnold_pipelines/megaplan/custody/action_validator.py`; `tests/cloud/test_feature_flags.py`; `tests/execute/test_authority_dispatch_validation.py`
    Change: Add one reusable predicate/result helper for raw effect adapters: only an explicit current `GateResult.AUTHORIZED` may dispatch; a missing gate, exception, unknown enum, `SHADOW_PASS`, or any blocked verdict must return a typed denial. Preserve the observation-only authoritative-reread exception inside `wbc_runtime.py`; it must not be expressible by mutation adapters. The helper is pure and performs no effect.
    Acceptance: focused tests prove `AUTHORIZED` alone returns true and that no gate, gate exception, `SHADOW_PASS`, malformed result, and every blocked enum return false; `rg -n 'SHADOW_PASS.*AUTHORIZED|AUTHORIZED.*SHADOW_PASS' arnold_pipelines/megaplan/{resident,chain,cloud,execute}` is attached for G3; `git diff --check` passes.

### Oracle gate G3 — GO 2026-08-11T16:49Z — shared effect policy

Criteria: Codex verifies the helper is the single mutation-adapter interpretation point, is default-deny, cannot authorize observation rereads, and has an exhaustive enum test. GO exposes the frozen helper API to Batch 0B.2; NO-GO changes only T-0014.

### Batch 0B.2 — apply the frozen contract to all raw adapters — parallel tasks

- [x] T-0015 `FLASH` Close resident delivery effects — DONE 2026-08-11 (agent B2ResidentDelivery): all six delivery admission points default-deny via `adapter_effect_authorized`; production constructors install explicit current gates (agentbox_adapter.py:1064/1345, resident/cli.py:1027); **25+6+43+34 = 108 focused tests passed**, `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/resident/delivery_effects.py`; `arnold_pipelines/megaplan/agentbox_adapter.py`; `arnold_pipelines/megaplan/resident/cli.py`; `tests/m10/test_resident_delivery_callers.py`; `tests/resident/test_notification_production_wiring.py`
    Change: Replace `_gate is None -> SHADOW_PASS` and SHADOW_PASS dispatch admission with the T-0014 helper. `open_resident_delivery_effects(production_enabled=True)` must require an installed current gate before any delivery; missing wiring returns typed denial and never calls the provider.
    Acceptance: focused tests spy zero provider calls for missing gate/SHADOW_PASS and one call only for AUTHORIZED; production wiring supplies the gate explicitly; `git diff --check` passes.

- [x] T-0016 `FLASH` Close Git effect routes — DONE 2026-08-11 (agent B2GitEffects): all gate checks and dispatch allowlists routed through `adapter_effect_authorized`; `_gate` fails closed (missing → ERROR, raising → typed denial); **124 focused tests passed** (13e3:20, 13e4_13e5:45, 13e6:31, 13e8:28) **+ 43 batch6**, no `GateResult.SHADOW_PASS` admission branch, `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/chain/git_effect_adapter.py`; `tests/m10/test_git_effect_adapter_13e3.py`; `tests/m10/test_git_effect_adapter_13e4_13e5.py`; `tests/m10/test_git_effect_adapter_13e6.py`; `tests/m10/test_git_effect_adapter_13e8.py`
    Change: Route all gate checks and all four dispatch allowlists through T-0014. Missing gate and SHADOW_PASS must block branch, worktree, commit, push, PR, and cleanup effects before reservation or subprocess invocation.
    Acceptance: the four focused test files pass; negative spies cover every effect family with no gate and SHADOW_PASS; `rg -n 'GateResult.SHADOW_PASS' arnold_pipelines/megaplan/chain/git_effect_adapter.py` finds no admission branch; `git diff --check` passes.

- [x] T-0017 `FLASH` Close publication effects — DONE 2026-08-11 (agent B2Publication + G4-round C2PublicationIndeterminate): `_gate` fail-closed (None), `publish`/`publish_indeterminate` admit only via `adapter_effect_authorized` (try/except for exceptional gates); **11 passed (-k publication), 34 passed (full bypass-gating file), 8 passed (m10 publication)**; zero callbacks/reservations for all non-AUTHORIZED verdicts; `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/cloud/publication_adapter.py`; `tests/cloud/test_wrapper_authority_bypass_gating.py`
    Change: Replace publication adapter fail-open defaults with the shared explicit-authorization predicate. Missing, exceptional, shadow, stale, or blocked gate evidence returns a typed failed publication outcome before protocol reservation or publication callback.
    Acceptance: focused tests prove zero publication callbacks for all non-AUTHORIZED inputs and one for AUTHORIZED; no SHADOW_PASS allowlist remains; `git diff --check` passes.

- [x] T-0018 `FLASH` Close SSH effects and the provider-none bypass — DONE 2026-08-11 (agent B2SshEffects): adapter `_gate` fail-closed (BLOCKED_WBC_MISSING), provider `_adapter is None` now typed denial (CliError ssh_effect_adapter_unavailable); **25+20+87+61 = 193 focused tests passed**, zero transport calls on blocked cases, `git diff --check` OK.
    Files: `arnold_pipelines/megaplan/cloud/ssh_effect_adapter.py`; `arnold_pipelines/megaplan/cloud/providers/ssh.py`; `tests/m10/test_ssh_effect_adapter.py`; `tests/cloud/test_ssh_deploy.py`; `tests/cloud/test_ssh_prelaunch_observation.py`
    Change: Use T-0014 in the adapter and make a missing provider adapter a typed denial rather than direct SSH execution. No gate, SHADOW_PASS, adapter construction failure, or unavailable adapter may call SSH, upload, deploy, or remote-command code.
    Acceptance: focused tests cover `_adapter is None` at `ssh.py:2800-2803`, missing gate, SHADOW_PASS, and AUTHORIZED; blocked cases make zero transport calls; `git diff --check` passes.

- [x] T-0019 `FLASH` Close execute effects — DONE 2026-08-11 (agent B2ExecuteEffects): `_gate` returns None when no gate installed; `route()` admits only via `adapter_effect_authorized` BEFORE reserve/persist/apply; **59 passed (18 new) + 6 batch6**, no `SHADOW_PASS` in effect_gate.py, `git diff --check` OK.
    Files: `arnold_pipelines/megaplan/execute/effect_gate.py`; `tests/execute/test_authority_dispatch_validation.py`; `tests/execute/test_execute_frontier_authority.py`
    Change: Replace `_action_gate_check is None -> SHADOW_PASS` and the two-value allowlist with T-0014. Deny before reserve/start, intent persistence, worker/process, workspace, terminal, or publication-handoff mutation.
    Acceptance: focused tests prove zero protocol/effect calls for missing/exceptional/shadow gates and normal completion for AUTHORIZED; no SHADOW_PASS admission remains; `git diff --check` passes.

- [x] T-0020 `FLASH` Remove latent canary shadow-as-success semantics — DONE 2026-08-11 (agent B2CanaryShadow): `PromotionGateResult.blocked` now True for anything except AUTHORIZED (SHADOW_PASS blocked, never green); **68 passed + 14 subtests (test_custody_canary.py), 226 passed 1 skipped (test_zero_recovery_canary.py), 1 passed (m8 bytecode canary)**, `git diff --check` EXIT=0.
    Files: `arnold_pipelines/megaplan/custody/canary.py`; `tests/arnold_pipelines/megaplan/test_custody_canary.py`; `tests/cloud/test_zero_recovery_canary.py`
    Change: Make `.blocked` and canary aggregation treat SHADOW_PASS as non-authoritative/blocked, even though no production consumer currently uses it. Keep diagnostics visible without allowing a green canary or dispatch receipt.
    Acceptance: tests at the former `canary.py:145-155,430-436,570-571` behavior prove SHADOW_PASS is non-green and AUTHORIZED alone passes; `git diff --check` passes.

### Oracle gate G4 — GO 2026-08-12T05:25Z (18 rounds) — all effect boundaries closed

Criteria: Codex reviews the full adapter diff and runs the six task acceptances. GO requires every missing-gate path and SHADOW_PASS path to stop before any protocol reservation, subprocess, provider, network, filesystem, Git, delivery, or publication effect; all production constructors install a gate explicitly. NO-GO on a raw two-value allowlist or direct-provider fallback.

### Batch 0B.3 — coherent launch, manifest, selector, and public-view truth — parallel tasks

- [x] T-0021 `FLASH` Fail closed in cloud bootstrap/auto command builders — DONE 2026-08-11 (agent B3Bootstrap): `_manifest_pin_fail_closed_prefix` exit-24 drift gate in `_bootstrap_launch_command`/`_plan_auto_command`/`_auto_command`; `spec.megaplan.src_path` and `/workspace/arnold` executable roots removed; **112 passed (cloud_chain_command + editable_install_sync + owner_lease_publisher_parity)** + 335 passed 1 skipped collateral; `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/cloud/cli.py`; `arnold_pipelines/megaplan/cloud/template.py`; `tests/cloud/test_cloud_chain_command.py`; `tests/cloud/test_editable_install_sync.py`
    Change: Remove `spec.megaplan.src_path` and `/workspace/arnold` as executable roots in `_bootstrap_launch_command`, `_plan_auto_command`, and `_auto_command`. Require the per-session manifest root/head plus runtime-provenance validation before auto/bootstrap starts; missing or invalid pins exit before state load or subprocess.
    Acceptance: focused tests prove missing/corrupt/mismatched manifests refuse and valid pins produce manifest-root-only `PYTHONPATH`; no generated command contains a shared-root fallback; `git diff --check` passes.

- [x] T-0022 `FLASH` Re-read recorded engine identity in every wrapper relaunch — DONE 2026-08-11 (agent B3RelaunchIdentity): `chain_engine_root_preflight` in arnold-watchdog/arnold-repair-loop/arnold-cloud-discover — persisted `engine_root` must exist and equal manifest `runtime_root` + live import root before PYTHONPATH build/launch; typed drift exit 24; **63 focused tests passed**, `bash -n` on all three wrappers, `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-cloud-discover`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-supervisor-runtime-lib`; `tests/cloud/test_launcher_manifest_conformance.py`; `tests/cloud/test_current_target_attestation.py`; `tests/cloud/test_wrapper_authority_bypass_gating.py`
    Change: Before watchdog, repair-loop, default-plan, resume, or discover relaunch reads state or constructs a command, require recorded `engine_root` = manifest `runtime_root` = live import root. Delete discover's direct `chain start`, `MEGAPLAN_DISCOVER_ARNOLD_SRC`, and all fixed-root heredoc fallbacks; use the fail-closed wrapper path and typed drift errors.
    Acceptance: `bash -n` passes for all wrappers; spies show zero state loads/spawns on missing/dangling/mismatch roots; `rg -n 'MEGAPLAN_DISCOVER_ARNOLD_SRC|:-/workspace/arnold'` finds no selecting relaunch; focused wrapper tests pass; `git diff --check` passes.

- [x] T-0023 `FLASH` Retire the remaining runtime selectors — DONE 2026-08-11 (agent B3Selectors): `MEGAPLAN_RUNTIME_SRC`, `MEGAPLAN_DISCOVER_ARNOLD_SRC`, `KIMI_GOAL_ARNOLD_SRC`, `MEGAPLAN_DISCORD_DM_ARNOLD_SRC` selector reads removed; resident/kimi/Discord derive from manifest `epic.runtime_root` or fail closed; ghost `ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED` no longer read/forwarded; `ARNOLD_REPAIR_TRIGGER_SESSION_ALLOWLIST` documented nonexistent; `MEGAPLAN_AUDIT_SESSION_ALLOWLIST` report-only; **rg shows zero selection reads (only documented NON-SELECTING `MEGAPLAN_SUPERVISOR_SOURCE_ROOT` binding)**, 15+5+10+57 wrapper/resident tests pass, `bash -n` + `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-resident`; `arnold_pipelines/megaplan/cloud/templates/entrypoint.sh.tmpl`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-kimi-goal-operator`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-discord-dm`; `agentbox/services.py`; `tests/cloud/test_watchdog_wrappers.py`; `tests/resident/test_restart_resident_command.py`; `tests/resident/test_provider_runtime.py`
    Change: Derive resident, Kimi, and Discord runtime identity only from a validated manifest/recorded runtime. Remove selecting reads of `KIMI_GOAL_ARNOLD_SRC`, `MEGAPLAN_DISCORD_DM_ARNOLD_SRC`, and retired `MEGAPLAN_RUNTIME_SRC`; stop hardcoding/exporting `/workspace/arnold`. Preserve `ARNOLD_REPAIR_RUNTIME_SRC` only as a diagnostic child handoff that is overwritten by manifest authority before use, and preserve deny-list/report-only reads as non-authoritative.
    Acceptance: shell syntax and focused tests pass; resident idempotency binds manifest runtime ID+revision; `rg` shows the three selector names only in deny-list/negative-test contexts; missing/corrupt manifest starts no resident/operator/DM effect; `git diff --check` passes.

- [x] T-0024 `FLASH` Make every manifest reader distinguish absent from invalid — DONE 2026-08-11 (agent B3ManifestReaders): `_reconcile_scope_manifest` — absent→None (scope degrades), present-invalid→typed `CliError(reconcile_manifest_invalid)` (reconcile blocked, never waived); gc-sweep `_json_get` corrupt→`NEEDS-RECONCILE` + never delete + continue; **34 passed (reconcile_milestone) + 3 passed (corrupt lifecycle) + 2 passed (launcher conformance) + 11 regression**; `bash -n` gc-sweep, `git diff --check` OK.
    Files: `arnold_pipelines/megaplan/chain/__init__.py`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep`; `tests/arnold_pipelines/megaplan/chain/test_reconcile_milestone.py`; `tests/cloud/test_runtime_lifecycle.py`; `tests/cloud/test_runtime_manifest.py`
    Change: At reconcile scope, a present-but-invalid manifest becomes typed UNKNOWN and cannot waive reconcile or advance. In GC, corrupt state/manifest input blocks the whole candidate instead of becoming `{}`. Add conformance tests for the already raw-but-fail-closed readers in `cli.py`, `epic_chain.py`, `current_target.py`, `arnold-chain`, `arnold-close`, `arnold-promote`, and `arnold-runtime-create` without rewriting them.
    Acceptance: focused tests prove absent/invalid/mismatched cases are distinct and non-green, no reconcile advancement or delete occurs, and each listed raw reader fails closed; `bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep`; `git diff --check` passes.

- [x] T-0025 `CODEX` Gate publication and runner views on coherent current envelopes — DONE 2026-08-11 (agent B3ViewsGate): `_observation_gate_reason()` fail-closed coherence+currency gate on `derive_publication_view`/`derive_runner_view` — UNKNOWN/INCOHERENT/stale → pending/unknown, never ready/live; **38 passed (31 pre-existing + 7 new) + 22 passed (m9 consumers)**, `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/authority/views.py`; `tests/arnold_pipelines/megaplan/test_authority_views.py`; `tests/arnold_pipelines/megaplan/test_cloud_status_authority_shadow.py`
    Change: Make `derive_publication_view` and `derive_runner_view` consume the same coherent/current ObservationEnvelope contract as the reducer. Raw observations, legacy rows, stale `run_revision`, missing provenance/cursors, mixed environments, and incoherent source sets may render diagnostics but cannot emit `ready` or `live`.
    Acceptance: focused tests prove only coherent current envelopes emit ready/live and every stale/legacy/torn case is UNKNOWN/non-authorizing; removing the coherence check makes at least one negative test fail; `git diff --check` passes.

- [x] T-0026 `FLASH` Lock the stale legacy-label semantic decision — DONE 2026-08-11 (agent B3LegacyLabel): test corrected to reducer's actual precedence — legacy label with old revision → `stale_observation_cannot_authorize_dispatch`; legacy label carrying view revision → `unknown_observation_cannot_authorize_dispatch`; doc-only reducer comment; **32 passed** (dependency_closure + test_reducer), `git diff --check` clean.
    Files: `tests/run_authority/test_dependency_closure.py`; `docs/goal-fix-the-fixer.md`
    Change: Fix `test_legacy_done_label...` to agree with the reducer: a legacy done label tied to an old revision is `stale_observation_cannot_authorize_dispatch`; a legacy label without revision is UNKNOWN. Document this decision without changing reducer behavior.
    Acceptance: the targeted test and the full dependency-closure file pass with both negative cases; `git diff --check` passes.

### Oracle gate G5 — GO 2026-08-12T05:25Z (18 rounds) — launch and truth closure

Criteria: Codex verifies every production launch/relaunch is manifest-pinned and recorded/manifest/live-equal before state read, invalid manifests cannot collapse to absence, public views cannot green raw/stale evidence, and all five E5 selection instances are gone. Diagnostic deny-lists, fixed non-selecting exports, and report-only allowlists must be explicitly classified. NO-GO on any shared-root selector or success from an incomplete envelope.

### Batch 0B.4 — reference-complete deletion authorization

- [x] T-0027 `FLASH` Put every destructive route behind the complete census — DONE 2026-08-12 (three parallel slices T27CensusStores/T27WrapperRoutes/T27ChainRoutes): census extended with four new store families (per-plan custody/leases, managed-subagent runs, status snapshots, ops schedule-inputs; missing dir ≠ reference, corrupt → UNKNOWN); all eight former delete sites require fresh readable CLEAR verdict before deletion (supervisor venv rebuild, agentbox `_apply_delete`, CLI `--fresh`, chain-reset rmtree, reconcile PR branch deletes, rollback branch delete, git-adapter worktree removal); `--force`/`--fresh`/`--restore-proven` are never evidence; **75 (wrapper/agentbox/lifecycle) + 137 (chain/rebind) + 31 (gc_sweep incl. 5 new store fixtures) focused tests passed**, spies prove zero delete calls on REFERENCED/UNKNOWN, `bash -n` + `git diff --check` clean.
    Files: `arnold_pipelines/megaplan/cloud/runtime_references.py`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-supervisor-runtime`; `agentbox/cleanup.py`; `arnold_pipelines/megaplan/cli/__init__.py`; `arnold_pipelines/megaplan/chain/git_ops.py`; `arnold_pipelines/megaplan/chain/target_rebind.py`; `arnold_pipelines/megaplan/cloud/cli.py`; `arnold_pipelines/megaplan/chain/git_effect_adapter.py`; `arnold_pipelines/megaplan/custody/worker_dispatch_wbc.py`; `arnold_pipelines/megaplan/custody/phase_wbc.py`; `arnold_pipelines/megaplan/resident/subagent.py`; `tests/cloud/test_runtime_lifecycle.py`; `tests/agentbox/test_cleanup.py`; `tests/arnold_pipelines/megaplan/test_chain_target_rebind.py`; `tests/m10/test_git_effect_adapter_13e8.py`
    Change: Extend the canonical census with per-plan custody/lease stores, managed-subagent runs, status snapshots, and ops schedule-inputs, then require a fresh readable zero-reference verdict plus route-specific authority before supervisor venv rebuild, agentbox cleanup, `--fresh`, reconcile/rollback branch deletion, chain-reset plan-dir removal, or Git-adapter worktree removal. Unknown/corrupt/unreadable state blocks; no route may treat `--force`, `--fresh`, or `--restore-proven` as evidence.
    Acceptance: focused tests exercise every enumerated former delete site (`arnold-supervisor-runtime:103`, cleanup `_apply_delete`, CLI `3087/3099`, git_ops `2133/2175/2593`, target_rebind `522`, cloud CLI `4405`, Git adapter) and every new store; spies show zero delete calls on reference or UNKNOWN; shell syntax and `git diff --check` pass.

### Oracle gate G6 — Phase 0B exit — **GO** 2026-08-12T09:02Z (11 rounds; rounds 9–11 closed Q1 template schema-gate, Q2 cli default_runtime_src fallback, Q3 repair-rematerialization census; round-11 oracle: "safe to commit Phase 0+0B and proceed to Phase 1, T-0101"; receipt sha256 d0f01b36…, see phase0b-receipts.md §3)

Criteria: Codex reviews the complete Phase 0B diff and focused receipts. GO only if all E1–E8 enumerated production defects are either fixed here or explicitly assigned to later phases, every effect is default-deny, every launch/view is coherent/current, and every destructive route has fresh reference proof. This is the publication boundary: no live deploy before G6 GO.

## Phase 1 (human-gated canary unblock) — publish one coherent lineage and resume the same occurrence; BLOCKED-BY: G6 GO

### Batch 1.0 — REVISE (Codex verdict 2026-08-12T09:45Z, two independent passes) — tooling T-0101 cannot run through supported interfaces yet

Codex verdict: **REVISE** — do not run T-0101 after only prep items. Blockers found: `chain runtime-rebind` cannot initialize an unbound progressed chain (`persisted runtime identity is missing`); adding `execution_binding: required` alone makes load/pause fail closed on progressed state; `runtime-rebind` updates `runtime_binding` but not `metadata.execution_environment.engine_root` (relaunch requires it); supervisor venv builder hardcodes `/workspace/arnold` (no source override); `last-prepare.json` is not the `arnold.megaplan.runtime_provenance_receipt.v1` schema rebind requires; manifest writer `advance_generation` has no expected-hash CAS and changes only expected/verified head; `megaplan-watchdog-ensure.timer` (systemd) recreates watchdog from `/workspace/arnold` (tmux kill insufficient); occurrence/claim is circular with T-0201-05. The canary must use a NEW final SHA (90775c4403 becomes an ancestor).

- [x] T-0101a `MAIN` Repair durable G6 evidence — tasklist G6 line + phase0b-receipts §2/§3 updated with rounds 9–11 and round-11 GO, receipt sha256 `d0f01b36…` — DONE 2026-08-12T09:3xZ
- [x] T-0101b `FLASH` Guarded legacy execution-binding migration command (`chain execution-binding-migrate`) — DONE 2026-08-12 (round 3: accepts paused identity-less marker under marker-SHA+relaunch-root guards; round 5: request-scoped decision lock; 18 migrate tests, 67 binding suite)
- [x] T-0101c `FLASH` Chain runtime cutover (`chain runtime-cutover`) — DONE 2026-08-12 (rebind + `metadata.execution_environment.engine_root` in one CAS; direction cutover|rollback; external receipt verification; 23+20+8 tests)
- [x] T-0101d `FLASH` Manifest CAS cutover (`runtime_manifest cutover`) — DONE 2026-08-12 (CAS sha+generation; root-relative rewrite incl. deps_lockfile/base.venv_path; path existence/containment/executable gates; rollback receipt alias-protected + post-verified; 98 manifest + 14 provenance tests)
- [x] T-0101e `FLASH` Operator exact-occurrence join/claim command (`chain occurrence-join`) — DONE 2026-08-12 (decision==accepted + latest under shared `decision_admission_lock`; occurrence-digest flock; WBC admission atomic with STARTED; cross-process idempotent rejoin; evidence-root-constrained hardened receipt; 29 tests)
- [x] T-0101f `MAIN` Full binding policy in chain.yaml — DONE 2026-08-12 (execution_binding: required, pin placeholder 4b5d6fd…, initiative_path, require_editable_runtime_match, assets; final P/F two-commit pin constructed at T-0101h GO: P=bundle commit, F=pin-only child, canary=F, chain pin=P)
- [x] T-0101g `FLASH` Copied-state rehearsal tests — DONE 2026-08-12 (real CLI for every step in exact live order incl. legacy marker migration; P/F two-commit verified ready=True from clean checkout; failure injection at every effect boundary incl. crash-durability fsync ordering; six-way root equality with real `.venv/bin/python3 -P` observation; 3/3 deterministic)
- [ ] T-0101h Oracle gate (REVISE) — **rounds 1–6 NO-GO, round 6 down to 1 blocker (marker-migration dir-fsync crash durability)**: R1 5 blockers (composition) → R2 7 (custody semantics; 8-scout swarm found 2 more) → R3 2 (marker contradiction, receipt boundary) → R4 6 (transactional: crash-retry, atomicity, receipt aliasing, zero-mutation) → R5 3 (decision TOCTOU, supersession zero-mutation, receipt alias) → R6 1 (fsync durability); GO publishes P/F; canary uses F

### Batch 1.1 — operator-owned canary transaction

- [ ] T-0101 `OPERATOR` Publish, stage, bind, and resume the immutable canary (supersedes T-0110/T-0120/T-0121) — **REVISED per Codex verdict 2026-08-12** (see Batch 1.0): the canary uses the T-0101h-approved FINAL SHA (NOT 90775c4403, which becomes an ancestor); flow is: disable systemd watchdog restarter → quiesce watchdog/chain/repair/incident-ledger writers (prove via writer-FD census) → verify stable hashes → single flock → `operator_control pause` under old optional spec → independently prove old runtime → legacy binding migration → marker legacy migration → install required-binding bundle by digest → chain rebind → chain runtime cutover → manifest CAS cutover → marker runtime_cutover → exact occurrence join/claim → `operator_control resume` (gate resume cursor byte-equivalent, fresh typed progress required, NOT tmux/PID liveness) → restart watchdog from candidate-compatible runtime only; do NOT re-enable `megaplan-watchdog-ensure.timer` until its script no longer restarts from `/workspace/arnold`.
    Files: T-0101h-approved final SHA; `origin/main`; `/workspace/runtime-candidates/arnold-<SHA12>`; `/workspace/.megaplan/megaplan-maintenance.json`; the exact chain record and repair request/decision/claim/attempt stores; `docs/fixer-recovery-evidence/main-publication.json`; `docs/fixer-recovery-evidence/canary-rebind-resume.json`
    Change: As one guarded transaction, ordinary-fast-forward push only the approved lineage, stage a new content-addressed runtime without mutating the shared candidate or `.bak-*`, create/join the exact blocked occurrence, obtain a current fenced claim, CAS-rebind recorded/manifest/live identity (all six roots equal: chain execution root = chain recorded engine_root = manifest runtime_root = marker runtime root = independently observed import root = candidate), and use supported same-occurrence resume. Never hand-edit JSON, force, blanket-refresh, use a global pointer, or mint a fresh occurrence.
    Acceptance: receipts prove `53584bb018`, `90775c4403`, and the final SHA are ancestors of origin, exact source/deployed hashes match, request→decision→claim→attempt IDs are relationally equal, recorded=manifest=live roots (six-way equality), one current lease/fence exists, cursor is preserved (gate resume cursor byte-equivalent), and fresh progress clears `blocked_no_lease` or produces a new typed blocker; `git diff --check` passes.

### Oracle gate G7 — live canary authorization

Criteria: Codex compares G6, origin, deployment, binding, custody, and fresh progress. GO requires one immutable coherent runtime and the same occurrence; NO-GO on shared-tree mutation, unreviewed publication, split-brain, zero authority, blind fresh, or liveness-only proof.

## Phase 2 (fixer mechanics) — close enqueue, identity, claims, lease, diagnosis, and ghost controls; BLOCKED-BY: G7

### Batch 2.1 — request and claim mechanics — parallel tasks

- [ ] T-0201 `FLASH` Route deterministic claimable failures and fail closed without decisions
    Files: `arnold_pipelines/megaplan/cloud/repair_contract.py`; `tests/cloud/test_repair_contract.py`; `tests/cloud/test_repair_dispatch_classifier.py`
    Change: Route deterministic mechanical failures with a canonical request to L1, and change request-without-decision from ACCEPTED to typed pending/blocked. Human gates and unsupported repair classes remain non-claimable.
    Acceptance: focused tests cover deterministic L1, absent decision, rejected decision, human gate, and unknown class; absent decision never dispatches; `git diff --check` passes.

- [ ] T-0202 `FLASH` Persist lifecycle identity and propagate every enqueue result in auto
    Files: `arnold_pipelines/megaplan/auto.py`; `tests/cloud/test_repair_dispatch_identity.py`; `tests/cloud/test_repair_occurrence_identity_v2.py`
    Change: Bind normalized occurrence/request/blocker identity before custody release; capture the dropped return at former `auto.py:2675`; stop swallowing enqueue exceptions; and make all six `repair_unavailable` exits carry or join the canonical request result instead of returning identity-free.
    Acceptance: tests cover all six former exits and the main enqueue path, assert returned IDs survive, exceptions become typed failure, and no lifecycle release precedes persistence; `git diff --check` passes.

- [ ] T-0203 `FLASH` Bind watchdog enqueue returns to custody
    Files: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`; `tests/cloud/test_watchdog_wrappers.py`; `tests/cloud/test_repair_enqueue_producers.py`
    Change: Capture the former dropped return at watchdog `1648`, validate status and IDs, and bind request/blocker/decision identifiers into the subsequent claim/attempt path. Failure to enqueue is not successful repair scheduling.
    Acceptance: `bash -n` and focused tests pass; spies prove returned IDs are used and absent/error results dispatch nothing; `git diff --check` passes.

- [ ] T-0204 `FLASH` Unify active and occurrence claim namespaces
    Files: `arnold_pipelines/megaplan/cloud/simple_fixer.py`; `arnold_pipelines/megaplan/cloud/repair_lock.py`; `tests/cloud/test_repair_lock_namespace_fencing.py`; `tests/cloud/test_repair_claim_cleanup.py`
    Change: Before acquiring fingerprint-keyed occurrence custody, consult blocker-keyed active claims through one canonical alias/index and current fence. Competing namespaces must converge on one owner; stale claims may be reclaimed only with a newer fence.
    Acceptance: focused concurrency tests prove one winner across both namespaces, same-owner join, fenced stale reclaim, and no double launch; `git diff --check` passes.

### Oracle gate G8 — request/claim closure

Criteria: Codex requires every claimable path to have one request, a non-missing decision, one current claim/fence, and propagated enqueue IDs. The previously FENCE-OK `alive_sessions=0` structural behavior must remain unchanged. NO-GO on accepted-without-decision, swallowed enqueue, or namespace double ownership.

### Batch 2.2 — custody and diagnosis closure — parallel tasks

- [ ] T-0205 `FLASH` Make lease append atomic and include `dispatch_key` in custody identity
    Files: `arnold_pipelines/megaplan/custody/lease_store.py`; `arnold_pipelines/megaplan/custody/worker_dispatch_wbc.py`; `tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py`; `tests/execute/test_execute_wbc_identity.py`
    Change: Hold one lock across lease load/check/append and include `dispatch_key` in `CustodyTargetKey` digest and all joins. This retains the old T-0205 custody scope; adapter authorization was moved earlier to T-0014–T-0019.
    Acceptance: race tests prove one lease winner; different dispatch keys never collide; replay of the same key joins; focused tests and `git diff --check` pass.

- [ ] T-0206 `FLASH` Diagnose runtime split-brain as the root cause
    Files: `arnold_pipelines/megaplan/cloud/repair_investigation.py`; `tests/cloud/test_repair_investigation.py`
    Change: Add recorded/manifest/live/wrapper/dependency comparison and make any missing or mismatch a typed root-cause finding that precedes victim patching. Never recommend editing a pin or shared tree.
    Acceptance: fixtures cover coherent, missing, dangling, and four-tree split; only coherent can proceed to code diagnosis; `git diff --check` passes.

- [ ] T-0207 `FLASH` Replace raw repair-loop status authority with cursor-validated observation
    Files: `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`; `arnold_pipelines/megaplan/cloud/current_target.py`; `tests/cloud/test_repair_loop_summary.py`; `tests/cloud/test_current_target.py`
    Change: Replace the raw status-snapshot decision with a fresh envelope tied to session/environment/revision/cursor. Stale, unreadable, or mixed snapshots remain diagnostic and cannot authorize repair or completion.
    Acceptance: shell syntax and focused freshness/torn-read tests pass; stale snapshot makes zero effect calls; `git diff --check` passes.

- [ ] T-0208 `FLASH` Turn ghost controls into enforced gates or explicit non-controls
    Files: `arnold_pipelines/megaplan/cloud/feature_flags.py`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`; `scripts/cloud_hot_upload.py`; `tests/cloud/test_progress_auditor.py`; `tests/cloud/test_feature_flags.py`
    Change: Enforce `ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED` at the actual commit effect boundary, not only in prompt text. Remove `ARNOLD_REPAIR_TRIGGER_SESSION_ALLOWLIST` from configuration/docs because it has no reader. Label `MEGAPLAN_AUDIT_SESSION_ALLOWLIST` and plan allowlist as report filters, never authority; keep mutation and push separately default-off.
    Acceptance: focused tests prove commit flag off makes zero commit calls even with a persuasive agent result, report filters cannot authorize, absent ghost name is rejected by hot-env validation, and shell syntax/`git diff --check` pass.

### Oracle gate G9 — Phase 2 exit

Criteria: Codex verifies atomic custody, collision-free dispatch identity, coherent diagnosis/status, and hard effect-boundary enforcement of every advertised control. GO requires negative controls that fail when each guard is removed.

## Phase 3 (frozen dependency generation) — one immutable dependency identity; BLOCKED-BY: G9

### Batch 3.1 — dependency-generation transaction

- [ ] T-0301 `FLASH` Replace per-epic venv/editable-install fiction end to end (supersedes T-0310–T-0313)
    Files: `arnold_pipelines/megaplan/cloud/runtime_manifest.py`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-runtime-create`; `arnold_pipelines/megaplan/cloud/cli.py`; `arnold_pipelines/megaplan/cloud/install_sync.py`; `arnold_pipelines/megaplan/cloud/runtime_references.py`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep`; `tests/cloud/test_runtime_manifest.py`; `tests/cloud/test_editable_install_sync.py`; `tests/cloud/test_runtime_lifecycle.py`
    Change: Define a content-addressed dependency-generation ID/path/digests, build/verify it once under a single-writer lock, bind it into runtime identity, launch from its interpreter with worktree-first `PYTHONPATH`, retire editable sync and per-worktree `.venv`, and delete a generation only after the canonical census proves zero references. Unknown proof blocks publication and GC.
    Acceptance: focused create/launch/migration/GC tests pass; no production manifest requires `<runtime>/.venv`; no `pip install -e` fallback remains; two runtimes may share an immutable generation without sharing mutable source; `git diff --check` passes.

### Oracle gate G10 — dependency-generation exit

Criteria: Codex requires a verifiable immutable generation at every launch, no editable/per-epic-venv selector, and reference-safe generation GC. NO-GO on mutable shared dependencies or compatibility fallback.

## Phase 4 (hourly backstop, action-off) — build the consumer without enabling it; BLOCKED-BY: G10

### Batch 4.1 — complete the dormant backstop

- [ ] T-0401 `FLASH` Implement plan→due→claim→managed launch→receipt while keeping the schedule cancelled (supersedes T-0402/T-0410)
    Files: `arnold_pipelines/megaplan/resident/scheduler.py`; `arnold_pipelines/megaplan/resident/schedules.py`; `arnold_pipelines/megaplan/resident/subagent.py`; `tests/resident/test_scheduler_notifications.py`; `tests/resident/test_resident_schedules.py`; `tests/resident/test_scheduled_turn_provenance.py`
    Change: Add the missing consumer for `superfixer_proactive`, with atomic due claim, managed run, effect gate, occurrence custody, and durable launch/final receipt. The distinct hourly launch flag defaults off and the existing jobs remain CANCELLED; the single-shot records `keep_cancelled`, not an enablement.
    Acceptance: fake-clock tests prove one launch per due occurrence, crash-safe reclaim, receipt linkage, no launch when disabled/cancelled, and no schedule mutation; `git diff --check` passes.

### Oracle gate G11 — hourly action-off exit

Criteria: Codex proves the end-to-end chain exists and is default-off. GO does not authorize uncancelling; any future enablement remains a separate OPERATOR decision.

## Phase 5 (reconcile real) — preserve completed epics and prove terminal cleanup; BLOCKED-BY: G11

### Batch 5.1 — fixtures and invariant correction — parallel tasks

- [ ] T-0501 `FLASH` Add reconcile-scope fixtures
    Files: `tests/arnold_pipelines/megaplan/chain/test_reconcile_milestone.py`
    Change: Add real-Git fixtures for product change, fully promoted change, verified no-op, invalid evidence, and a completed legacy chain lacking reconcile; missing/uncertain evidence requires reconcile and no-op never dispatches an agent.
    Acceptance: the file passes and the completed-legacy regression stays terminal; `git diff --check` passes.

- [ ] T-0502 `FLASH` Add reconcile-PR fixtures
    Files: `tests/arnold_pipelines/megaplan/chain/test_reconcile_pr.py`
    Change: Cover merged, intentionally rejected, open, auth failure, unreachable selection, interrupted publication, and cherry-pick conflict using recorded target and persisted branch identity.
    Acceptance: the file passes; only merged/rejected are branch-delete eligible; every unknown/open state remains blocked; `git diff --check` passes.

- [ ] T-0503 `FLASH` Add close/finalizer/restore fixtures
    Files: `tests/arnold_pipelines/megaplan/chain/test_reconcile_terminal_finalizer.py`; `tests/cloud/test_runtime_lifecycle.py`
    Change: Prove close precedes restore-proven GC, repeated crash recovery is idempotent, standalone close refuses unresolved reconcile, and a CLI flag alone is not restore evidence.
    Acceptance: focused tests pass and spies show zero close/delete on missing proof; `git diff --check` passes.

- [ ] T-0504 `CODEX` Guard `ensure_reconcile_milestone` and terminal cleanup
    Files: `arnold_pipelines/megaplan/chain/__init__.py`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-close`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-gc-sweep`
    Change: Check durable chain completion before appending a synthetic reconcile milestone, so rerunning a completed legacy epic is an idempotent terminal observation rather than a regression to pending reconcile. Move/repair the dead later completion guard, add a reconcile-resolution guard to standalone close, and require content-addressed restore evidence in GC rather than trusting `--restore-proven`.
    Acceptance: all T-0501–T-0503 tests pass after integration; removing the early completion guard reproduces the regression; shell syntax and `git diff --check` pass.

### Oracle gate G12 — reconcile readiness

Criteria: Codex requires completed legacy epics to stay complete, active epics to reconcile default-on, only merged/rejected/verified-noop to close, and close before evidence-backed GC. `editible-install` at `8c4b2c9561` remains retained because `cloud.yaml` references it.

## Phase 6 (deploy once, then watch to P7B) — operational proof; BLOCKED-BY: G12

### Batch 6.1 — coherent predeploy tooling

- [ ] T-0601 `FLASH` Build the baseline, watermarked watcher, canonical router, and predeploy receipt (supersedes T-0602–T-0604)
    Files: `scripts/fixer_recovery_baseline.py`; `scripts/fixer_recovery_predeploy.py`; `tests/scripts/test_fixer_recovery_baseline.py`; `tests/scripts/test_fixer_recovery_predeploy.py`; `.megaplan/initiatives/megaplan-maintenance/chain.yaml`; `.megaplan/initiatives/megaplan-maintenance/NORTHSTAR.md`
    Change: Capture one content-addressed coherent envelope across exact chain/session/runtime/queue/schedule/reconcile sources, enforce half-open cursored windows, allow only canonical request/join/reclaim actions, and emit a predeploy verdict that fails on missing proof, mixed versions, selectors, editable installs, ledger bypass, or unsnapshotted initiative inputs.
    Acceptance: both focused test files pass; corrupting any one receipt makes predeploy fail; no effect occurs in collector mode; `git diff --check` passes.

### Oracle gate G13 — predeploy hard gate

Criteria: Codex verifies the final source SHA, focused receipts, initiative hashes, runtime/dependency/wrapper provenance, exact live session classification, and default-off mutation. GO authorizes only T-0610's named operator transaction.

### Batch 6.2 — terminal publication and immutable rollout

- [ ] T-0610 `OPERATOR` Publish, deploy, CAS-rebind, and guardedly resume the final lineage (supersedes T-0611/T-0612/T-0620)
    Files: G13-approved commits; `origin/main`; new `/workspace/runtime-candidates/arnold-<SHA12>`; exact installed wrappers named by the diff; runtime manifest and chain binding; `docs/fixer-recovery-evidence/final-main-publication.json`; `docs/fixer-recovery-evidence/box-rollout.json`; `docs/fixer-recovery-evidence/final-runtime-rebind.json`; `docs/fixer-recovery-evidence/p7a-launch.json`
    Change: Ordinary-fast-forward publish only approved commits, stage a new immutable runtime, copy only changed wrappers with hashes, CAS-rebind without moving the cursor, and resume the matching session; if identity is irreconcilably old, use guarded retirement before fresh launch. Preserve dirty/shared trees, `.bak-*`, rollback roots, and exactly one session.
    Acceptance: four JSON receipts validate; origin/deployed/import/manifest/recorded identities and dependency/wrapper digests equal G13; exactly one current lease/fence/session exists; no blanket copy, hand edit, global pointer, force, or blind fresh appears.

### Oracle gate G14 — re-entrant deployed-runtime, watcher, recovery, and terminal gate

Criteria: After every following operational batch, Codex rereads fresh coherent evidence. It routes accepted progress or durable human waiting back to T-0630; a typed claimable stall to T-0640; an approved repair to T-0650; a terminal reconcile candidate to T-0690; and final evidence to T-0691. GO/STOP only after P7B. The gate performs no mutation.

### Batch 6.3 — P7A smoke (then return to G14)

- [ ] T-0621 `FLASH` Observe two complete watchdog sweeps
    Files: `/workspace/watchdog-reports/*.json`; `/workspace/.megaplan/cloud-sessions/*megaplan-maintenance*`; `/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains/chain-*.json`; `/workspace/.megaplan/repair-queue/requests/*`; `/workspace/.megaplan/repair-queue/decisions/*`; `/workspace/.megaplan/repair-queue/claims/*`; `/workspace/.megaplan/repair-queue/attempts/*`; `docs/fixer-recovery-evidence/p7a-two-sweeps.json`
    Change: Read only; prove current lease/fence, coherent identity, progress beyond init or expected human gate, and typed occurrence creation for any failure.
    Acceptance: the receipt has two increasing cursors and is explicitly `smoke_only`; repeated stall without canonical custody is NO-GO.

### Batch 6.4 — one watermarked window (repeat; then return to G14)

- [ ] T-0630 `FLASH` Capture and classify one `[start,end)` window
    Files: `/workspace/watchdog-reports/*.json`; `/workspace/.megaplan/cloud-sessions/*megaplan-maintenance*`; `/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains/chain-*.json`; `/workspace/.megaplan/repair-queue/{requests,decisions,claims,attempts}/*`; `/workspace/.megaplan/ops/schedules/*`; `/workspace/arnold/.megaplan/resident/scheduled_jobs/*`; `docs/fixer-recovery-evidence/windows/window-<UTC_START>-<UTC_END>.json`; `docs/fixer-recovery-20260811.md`
    Change: Classify exactly advancing, expected human gate, new claimable occurrence, repair in progress, incoherent unknown, or P7B candidate. Only enqueue/join/reclaim through canonical custody; never push, deploy, rebind, force-proceed, enable hourly, or edit state.
    Acceptance: endpoint envelopes have non-overlapping cursors/hashes; unknown is non-green; progress cites a newer accepted receipt; human wait names owner/return; P7B cites reconcile/close/GC.

### Batch 6.5 — oracle-scoped systemic repair, only after G14 NO-GO (then return to G14)

- [ ] T-0640 `FLASH` Apply the exact G14-scoped root-cause fix
    Files: `<G14_EXACT_SOURCE_PATHS>`; `<G14_EXACT_TEST_PATHS>`; `/workspace/.megaplan/repair-queue/{requests,decisions,claims,attempts}/<OCCURRENCE_RECORDS>`; `docs/fixer-recovery-evidence/repairs/<OCCURRENCE_ID>.json`
    Change: Preserve occurrence/claim/fence and make the smallest systemic source or mechanic fix with a blocker-specific negative control. No victim-only box patch, authority weakening, external mutation, or completion claim.
    Acceptance: named focused tests and `git diff --check` pass; the receipt binds exact before/after digests to the same occurrence; the negative control fails without the fix.

### Batch 6.6 — publish an approved stall repair, only after G14 GO (then return to G14)

- [ ] T-0650 `OPERATOR` Publish, deploy, rebind, and retrigger the same occurrence
    Files: `<G14_APPROVED_EXACT_DIFF_PATHS>`; `origin/<G14_APPROVED_BRANCH>`; `/workspace/runtime-candidates/arnold-<G14_SHA12>` when engine code changed; `/workspace/.megaplan/megaplan-maintenance.json`; `/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains/chain-c511d8baf7d7.json`; `/workspace/.megaplan/repair-queue/{requests,decisions,claims,attempts}/<OCCURRENCE_RECORDS>`; `docs/fixer-recovery-evidence/repairs/<OCCURRENCE_ID>-publication.json`
    Change: Use ordinary push to the approved target, content-addressed deploy, fenced cursor-preserving CAS rebind, and supported same-occurrence retrigger. Never force, blanket-refresh, edit a pin, or use fresh identity.
    Acceptance: receipt proves approved branch/SHA, coherent live import, unchanged IDs/fence lineage, and later independent accepted progress.

### Batch 6.7 — reconcile human outcome (then return to G14)

- [ ] T-0690 `OPERATOR` Resolve generated reconcile and disposition orphan branches
    Files: `origin/reconcile/<EPIC>-<DATE>`; its PR and reconcile receipts; origin refs `fixer/critique-epoch-invalidation-20260806`, `fixer/fixer-unification-20260807`, `fixer/megaplan-maintenance-20260811`, and `editible-install`; `docs/fixer-recovery-evidence/p7b-reconcile-outcome.json`
    Change: Human records exactly merged, intentionally rejected, or digest-verified no-op. Delete an orphan fixer branch only after zero-reference census, main containment, no open PR, and explicit approval. Never delete `editible-install` while `cloud.yaml` references it.
    Acceptance: receipt validates the allowed outcome and each branch's retain/delete rationale; open/auth/conflict/unknown remains blocked and cannot close.

### Batch 6.8 — P7B evidence and stop (then final G14)

- [ ] T-0691 `FLASH` Collect reconcile→close→restore-proven GC evidence
    Files: `/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains/chain-c511d8baf7d7.json`; `/workspace/megaplan-maintenance/Arnold/.megaplan/plans/<FINAL_PLAN>/`; `/workspace/.megaplan/megaplan-maintenance.json`; `/workspace/watchdog-reports/*.json`; reconcile/close/GC receipts named by T-0690; `docs/fixer-recovery-evidence/p7b-final.json`; `docs/fixer-recovery-20260811.md`
    Change: Read only; prove all milestones, allowed reconcile outcome, close before GC, content-addressed restore proof, zero references for each deletion, no unresolved claim, and later independent verification of terminal progress.
    Acceptance: JSON validates; every missing/torn datum is UNKNOWN; G14 GO/STOP requires all predicates and cannot be satisfied by a commit, test, process, agent report, or status label alone.

## Execution summary

- **Total tasks:** 45: 8 completed Phase 0 tasks plus 37 remaining tasks.
- **Model split:** 38 `FLASH`, 3 `CODEX`, 4 `OPERATOR`. The only CODEX implementation tasks are T-0014 (shared adapter authorization), T-0025 (view coherence/currency), and T-0504 (completed-chain reconcile guard). Oracle gates remain read-only Codex reviews and are not counted as implementation tasks.
- **Three riskiest tasks:** T-0014 because one incorrect predicate can authorize every effect family; T-0025 because a superficially green public view can bypass the coherent-envelope invariant; T-0504 because ordering mistakes can regress completed epics or delete terminal assets prematurely.
- **Execution order:** completed G1/G2 → T-0014/G3 → T-0015–T-0020 in parallel/G4 → T-0021–T-0026 in parallel/G5 → T-0027/G6 → T-0101/G7 → T-0201–T-0204 in parallel/G8 → T-0205–T-0208 in parallel/G9 → T-0301/G10 → T-0401/G11 → T-0501–T-0504 in parallel/G12 → T-0601/G13 → T-0610/G14 → T-0621/G14 → repeating T-0630/G14, with conditional T-0640/G14 and T-0650/G14, then T-0690/G14 → T-0691/final G14 GO/STOP.
