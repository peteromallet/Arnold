# a01-s10-authority-ownership-legacy-cli-wrappers: authority-ownership × legacy-cli-wrappers

## Verdict

FAIL. The repository has a defined canonical contract, but legacy wrapper code still contains independently executable authority writers and projection-to-decision bypasses.

Findings:

- P1 authority mutation: repair-loop stale-state and blocked-recovery helpers directly rewrite plan/chain state outside the canonical state writer.
- P1 authority-increasing decision: `classify_repair_dispatch()` accepts a read-only recovery projection as its preferred dispatch authority.
- P1 status misreporting with action impact: watchdog, supervisor, meta-repair, CLI, and auditor paths still select “current” state by mtime or fallback location.
- P2 conformance false-negative: `tests/test_state_reader_audit.py` scans a nonexistent tree and does not cover cloud wrappers.

## Intended canonical contract

`source_to_owner_matrix.json` assigns one mutating owner per surface: Run Authority owns authority facts, routing, and execution verdicts; Maintenance owns lifecycle/status/repair mutation; projections are explicitly non-authoritative (`arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json:3-26`).

The canonical plan-state writer is `write_plan_state()`: it acquires the dedicated state lock, reads/modifies/validates state, and atomically replaces `state.json` (`arnold_pipelines/megaplan/_core/state.py:1093-1106`, `:1430-1451`, `:1454-1463`, `:1630-1636`). `state.json` is explicitly not an independent authority for manifest-backed callers (`:85-89`).

For repair classification, the canonical path is `resolve_run_state()` plus `classify_repair_dispatch(canonical_run_state=…, event_plan_dir=…)`; missing canonical provenance is intended to fail closed (`arnold_pipelines/megaplan/cloud/repair_contract.py:1770-1822`). Repair queue mutation belongs to `enqueue_occurrence_bound_repair_request()`, which requires the complete occurrence tuple and rejects partial identity (`arnold_pipelines/megaplan/cloud/repair_requests.py:2381-2421`, `:2457-2486`).

## Evidence and complete path inventory

I searched with `rg --files` for all wrapper, cloud, test, schema, and documentation paths; then used `rg -n` for `state.json`, `chain_state`, `current_state`, `last_state`, `write_text`, `atomic_write_json`, `classify_repair_dispatch`, `resolve_run_state`, and wrapper function calls. I inspected the resulting files with numbered ranges. No services or cloud state were accessed.

Writers:

- Canonical: `_core/state.py:1430-1636`.
- Repair-loop direct writers: `arnold-repair-loop:5521`, `:5548`, and `:5638-5639`, `:5780`, `:5800-5802`.
- Canonical repair queue writer: `repair_requests.py:2381-2505`.

Readers/callers/consumers:

- `arnold-watchdog` resolves legacy chain candidates and mtime-selects plan state (`:527-559`, `:676-711`), exports status (`:955-978`), computes dispatch status (`:1303-1523`), and uses terminal status to skip repair/relaunch (`:4690-4733`, `:8613-8621`).
- `arnold-supervise` mtime-selects a chain, reads raw plan state, and derives a failure reason (`:115-157`); the result queues through the canonical supervisor queue (`:201-240`).
- `arnold-meta-repair-loop` claims an “authoritative” post-retrigger snapshot but selects the newest chain and plan by mtime (`:1932-2012`), then can append `verified_recovered` (`:2091-2134`).
- Cloud CLI duplicates latest-plan reduction (`cloud/cli.py:6110-6151`, `:6330-6338`); cloud supervision maps effective status to actions (`cloud/supervise.py:416-431`).
- `arnold-progress-auditor` reads raw state to decide dispositions (`:344-415`) but later has a canonical resolver path (`:5194-5237`).
- Positive canonical callers exist: `arnold-repair-trigger:1277-1358`, `cloud/status_snapshot.py:1873-1881`, and resolver-enforcement tests (`tests/cloud/test_resolver_enforcement.py:277-337`).

## Adherence gaps

1. **P1 — direct authority mutation, currently dormant but still executable.**  
   `repair_clear_stale_state_if_needed()` claims stale cleanup cannot become authority outside canonical delegation (`arnold-repair-loop:5364-5372`), but directly changes chain state and plan state using `atomic_write_json()` (`:5489-5524`, `:5531-5548`). `recover_blocked_after_dev_fix_if_possible()` similarly reads raw state, sets `current_state="finalized"`, clears failure, and writes plan/chain JSON directly (`:5602-5802`). These paths do not call `write_plan_state()`, do not perform a canonical semantic transition, and do not emit an authority-owned transition.

   Repository search found only the function definitions for these helpers. The existing test proves the blocked-recovery helper is not called after the dev-fix path (`tests/cloud/test_watchdog_wrappers.py:946-960`), but that is reachability evidence, not retirement proof. A sourced wrapper or future caller can still invoke the functions.

2. **P1 — read-only recovery projection becomes dispatch authority.**  
   `MegaplanRecoveryView` is explicitly read-only, shadow, and diagnostic (`arnold_pipelines/megaplan/authority/views.py:1434-1470`; `:1558-1570`). Nevertheless, `classify_repair_dispatch()` gives `recovery_view` precedence and returns its decision before canonical classification (`arnold_pipelines/megaplan/cloud/repair_contract.py:1674-1688`, `:1725-1768`). The test explicitly demonstrates a `read_only=True`, `shadow=True` recovery dict producing L1 dispatch without `canonical_run_state` (`tests/cloud/test_repair_custody.py:1117-1148`). This violates “projection never becomes authority.”

3. **P1 — implicit-latest readers misreport target and can affect actions.**  
   Watchdog selects the newest arbitrary `*/state.json` when no plan name is present (`arnold-watchdog:694-711`, `:1352-1388`), and its terminal helper can then suppress repair/relaunch (`:4705-4730`, `:8613-8621`). Meta-repair and supervisor repeat the same pattern for chain and plan files (`arnold-meta-repair-loop:1958-1979`; `arnold-supervise:123-157`). The meta path can persist a `verified_recovered` event after this selection (`arnold-meta-repair-loop:2126-2154`). This is status misreporting at minimum and an authority/ledger mutation when the false verification is recorded.

4. **P2 — reader-audit proof is invalid for this surface.**  
   `tests/test_state_reader_audit.py` sets `MEGAPLAN_DIR` to `REPO_ROOT / "arnold" / "pipelines" / "megaplan"` (`:24-26`), but that directory is absent; the actual tree is `arnold_pipelines/megaplan`. Its allowlists also enumerate several nonexistent modules (`:28-50`) and `_iter_megaplan_py_files()` therefore does not scan the real wrapper tree (`:185-190`). It cannot prove retirement of legacy wrapper readers or writers.

Negative evidence is real but incomplete: wrapper gates reject legacy installed binaries (`tests/cloud/test_wrapper_authority_bypass_gating.py:120-170`), and projection tests reject forged raw/prose/token/implicit-latest authority (`tests/m9/test_negative_authority_source.py:18-73`). Those tests do not cover the direct semantic writers above.

## Incident reachability and severity

The direct writers are not on the default post-dev-fix call path, so the observed Critique incident is not the sole trigger. Their existence is independently sufficient for a P1 latent authority breach.

The active mtime readers are reachable from watchdog’s normal tick and supervisor failure handling. A newer sibling plan, legacy chain file, restart-created artifact, or partially written JSON can cause the wrong plan to be classified. This can suppress relaunch, queue repair for the wrong occurrence, or append a false recovery event. The exact effect is an inference from the cited control flow; no live deployment was exercised.

Concurrency and restart risk is material: the blocked-recovery helper uses unlocked `read_text()` plus non-atomic `write_text()` (`arnold-repair-loop:5628-5639`), unlike the canonical lock/atomic sequence. Two containers sharing a workspace can lose updates; a crash between plan and chain writes can leave contradictory state.

## Minimal generalized remediation

Delete both direct mutation helpers and all callers; do not wrap them. Any required reconciliation must call the canonical state/chain transition owner with lock, CAS/fence, occurrence identity, and durable event emission.

Remove `recovery_view` as a decision input, or make it diagnostic-only. Require canonical Run State plus exact event provenance for every positive dispatch; delete `_classify_repair_dispatch_legacy()` after callers migrate.

Replace every implicit-latest fallback with target-bound `resolve_current_target()` and `resolve_run_state()`. Missing or contradictory identity must produce `UNKNOWN`/typed escalation, never select a sibling by mtime. Queue effects only through occurrence-bound enqueue.

## Required tests and retirement proof

Add deterministic tests for:

- concurrent writers, stale fence/epoch, CAS failure, restart between plan/chain persistence, malformed/partial JSON, replay/idempotency, and duplicate-effect prevention;
- provider quota/auth/transport failures;
- mutation gates proving projection-only, custody-only, WBC-only, and Run-Authority-only inputs cannot dispatch;
- two containers with shared storage and separate PID namespaces, including PID reuse and liveness mismatch;
- newer sibling plan/chain files proving target binding, not mtime, controls status;
- recovery projection with `read_only=True` proving dispatch is rejected without canonical provenance.

Retirement proof must include static/runtime scans showing zero wrapper writes to plan/chain `state.json`, zero definitions/callers of the deleted helpers, zero legacy reducer call sites, and traces proving status, fixer, advancement, queueing, and verification all use the canonical owner. M11 explicitly requires zero authority readers/writers, replay/restart/projection-rebuild proof, and negative scans for implicit-latest and direct legacy writers (`.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md:229-231`, `:299-303`, `:356-366`).

## Unknowns

This is a static repository audit. I did not inspect deployment images, external shell sourcing, installed `/usr/local/bin` wrappers, or provider runtime configuration. Those may add callers to the dormant mutation helpers.