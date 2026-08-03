# a02-s05-identity-version-provenance-review-chain: identity-version-provenance × review-chain

## Verdict

FAIL. Multiple independently evidenced gaps violate the invariant.

The strongest canonical identity model exists in `arnold/workflow/execution_attempt_ledger.py:424-495,508-570,587-666,830-846`: immutable run/attempt identity, causal provenance, runtime adapter version, version set, and authority grant. However, review, acceptance, epic aggregation, status projection, and release manifests do not consistently consume it.

Critical gaps are:

- P0 — authority mutation: stale, unverifiable, or missing review evidence can authorize review→done.
- P0 — authority mutation: acceptance records do not bind attempt, incarnation, launch provenance, or provider/version identity.
- P0 — authority mutation: legacy epic aggregation advances the parent despite an authoritative child-completion disagreement.
- P1 — status misreporting and conditional authority exposure: status snapshots treat any receipt-shaped dictionary as accepted.
- P1 — authority mutation: direct no-review, feedback, human-verification, auto-approval, and force-proceed paths write `done` without the canonical acceptance transaction.
- P2 — authority mutation/bypass: a public receipt setter can overwrite receipts without validation; no production callers were found.

## Intended canonical contract

Every review or acceptance decision should carry a content-addressed identity capsule containing:

`AttemptIdentity` (`workflow_id`, `run_id`, `graph_revision`, `attempt_ordinal`, `attempt_id`), `AttemptProvenance`, runtime adapter/version, `VersionSet`, authority grant/decision, runner incarnation, launch/process-custody provenance, and provider identity/version.

The decision must be rejected if any identity coordinate is missing, mismatched, stale, unverifiable, or mutated after evidence collection. Chain, epic, completion-manifest, successor, resume, supervisor, wrapper, and downstream-release consumers must validate the same capsule.

The repository has useful canonical pieces, but no complete cross-pipeline implementation. The attempt ledger is the canonical identity model; `AcceptanceSnapshot` plus CAS commit and `ChainState.validate_acceptance_receipt` are the canonical acceptance/mutation path. Consolidation should extend and route through these pieces.

## Evidence and complete path inventory

I searched with `rg --files` and recursive `rg -n` over `arnold`, `arnold_pipelines`, `tests`, schemas, docs, wrappers, scripts, and tools for review/acceptance/chain/epic/release, decision writers, receipt readers, `run_id`, attempt/incarnation/version/provider/launch provenance, PID namespaces, and completion manifests. I then inspected every production call site found for `TransitionDecision`, `AcceptanceSnapshot`, `prepare_acceptance_commit`, `has_acceptance_receipt`, `set_acceptance_receipt`, epic completion, and manifest validation.

Writers:

- Review handler evaluates and writes `TransitionDecision` in `arnold_pipelines/megaplan/handlers/review.py:1794-1904`; the handler then applies the selected state projection at `2178-2190`.
- Acceptance canary constructs `AcceptanceSnapshot` and commits it through the CAS helper in `arnold_pipelines/megaplan/cloud/m11_workflow_canary_runner.py:284-328`.
- Canonical chain mutation is `_append_completed_with_guard` in `arnold_pipelines/megaplan/chain/__init__.py:3339-3425`; fail-closed mutation uses acceptance CAS, while shadow/warn/off append directly.
- Epic aggregation writes parent completion records in `arnold_pipelines/megaplan/chain/epic_chain.py:755-813`.
- Completion manifests are written by `arnold_pipelines/megaplan/chain/__init__.py:1240-1390`.

Readers/consumers:

- `ChainState.validate_acceptance_receipt` validates receipt, snapshot, transaction, commit, and runtime fields in `arnold_pipelines/megaplan/chain/spec.py:1646-1746`.
- Successor, supervisor, wrapper, and resume gates call `has_acceptance_receipt` in `arnold_pipelines/megaplan/chain/__init__.py:8207-8265`, `supervisor/chain_runner.py:961-998`, `cloud/wrapper_acceptance_gate.py:239-258`, and `runtime/resume.py:88-118`.
- Status projection reads raw receipt presence in `cloud/status_snapshot.py:1539-1554,1582-1621` and passes that result into advancement at `1678-1693`.
- Epic aggregation reads child `completed` labels and preserves legacy completion despite authority drift in `chain/epic_chain.py:438-518`.
- Downstream launch preconditions validate manifest schema, chain hash, statuses, proofs, and manifest hash, but not acceptance identity, in `chain/spec.py:2712-2777,2910-2932`.

Tests independently confirm the stale-review and fail-open behaviors in `tests/arnold_pipelines/megaplan/test_transition_policy.py:201-225,284-318` and `tests/test_append_completed_atomic.py:128-147`, `tests/test_chain_completion_guard.py:2893-3015`.

## Adherence gaps

- **P0 — authority mutation: review freshness is advisory.** `evaluate_review_done` appends stale/unverifiable evidence to advisory rather than denial (`arnold_pipelines/megaplan/orchestration/transition_policy.py:188-201,251-269`). The test explicitly asserts stale evidence still allows the decision (`tests/arnold_pipelines/megaplan/test_transition_policy.py:201-225`). Provider errors and missing evidence are also advisory (`284-318`). Because the handler applies `next_state` after only a denial check (`handlers/review.py:2040-2055,2178-2180`), review→done can mutate authority without fresh evidence.

- **P0 — authority mutation: acceptance identity is incomplete.** `AcceptanceSnapshot` requires only chain run, milestone, plan, source commit, and runtime identity (`orchestration/acceptance_transaction.py:113-145`); `_validate_acceptance_identity` validates only commit/runtime (`:791-822`). Receipt and transaction schemas likewise omit attempt, incarnation, launch provenance, provider, and version (`:329-435`). `ChainState.validate_acceptance_receipt` compares only milestone/plan/index, source commit, and runtime identity (`chain/spec.py:1691-1741`). Thus an old attempt or provider result can be accepted when those weaker fields happen to match. This is an inference from the schema and validator omission, but the omission is directly observed.

- **P0 — authority mutation: epic completion trusts legacy projection.** `_observe_child_epic` declares complete from completed labels (`chain/epic_chain.py:438-450`), then explicitly preserves that status when the authoritative check disagrees (`:489-518`). The test proves this state (`tests/arnold_pipelines/megaplan/test_epic_chain.py:386-438`). `run_epic_chain` then appends the parent completion record from that status without acceptance or child identity (`:755-813`).

- **P1 — status misreporting, with downstream risk.** `status_snapshot.py` sets acceptance true when `acceptance_receipt` is merely a dictionary (`:1543-1554,1582-1589`), bypassing `ChainState.validate_acceptance_receipt`. It reports accepted progress and supplies the unvalidated boolean to advancement (`:1609-1621,1678-1693`). This can advertise readiness even when the receipt is malformed, stale, or uncommitted.

- **P1 — authority mutation: direct terminal projections bypass acceptance.** No-review execute writes terminal state and emits an explicitly evidence-only receipt (`handlers/execute.py:330-348,1050-1084,1113-1166`). Feedback writes `STATE_DONE` directly (`cli/feedback.py:431-478`); human verification does the same (`handlers/verifiability.py:281-287`); auto-approval writes done directly (`auto.py:1867-1875`); force-proceed writes done despite review issues (`handlers/override.py:1064-1077`). These are legitimate workflow surfaces but are not bound to the canonical attempt/acceptance identity.

- **P1 — downstream release authority is under-bound.** Completion manifests require done records and proof artifacts (`chain/__init__.py:1278-1353`) and launch validation checks manifest structure/hashes/proofs (`chain/spec.py:2723-2777,2910-2932`), but neither carries or validates the full decision identity. Shadow mode intentionally appends without acceptance (`chain/__init__.py:3376-3425`; tests at `test_chain_completion_guard.py:2893-2976`).

- **P2 — bypass implementation.** `ChainState.set_acceptance_receipt` overwrites a receipt without validating the transaction or snapshot (`chain/spec.py:1756-1770`). Recursive search found only test callers, not production callers. It should be removed or made private/unreachable after migration.

## Incident reachability and severity

Observed: stale review evidence is allowed; provider failure and missing evidence are allowed; shadow completion is fail-open; epic authority drift is preserved as complete; status uses raw receipt presence.

Inference: a stale decision can cross attempts or incarnations because the durable review/acceptance schemas do not require those coordinates, and an epic or release consumer can promote status-only evidence. The strongest direct impact is unauthorized review→done and parent-epic advancement: P0. Raw status and shadow/release behavior are P1 where deployment configuration permits them.

## Minimal generalized remediation

1. Add a versioned, content-addressed `DecisionIdentity` envelope based on `AttemptIdentity`, `AttemptProvenance`, `RuntimeAdapter`, `VersionSet`, and `GrantRef`, plus runner incarnation, provider identity/version, and launch-custody reference/digest.
2. Require that envelope in `TransitionDecision`, `AcceptanceSnapshot`, `AcceptanceTransaction`, `AcceptanceReceipt`, chain completed records, epic records, and completion manifests.
3. Change review freshness, missing evidence, provider failure, and identity uncertainty to hard denial for authority transitions.
4. Route status, epic observation, successor, supervisor, wrapper, resume, manifest, and release consumers through one validator. Epic disagreement must become blocked/unknown, not diagnostic-only.
5. Migrate legacy v1 records to v2 only when identity can be reconstructed; otherwise quarantine them. Delete direct terminal writers or route them through the same acceptance boundary. Remove `set_acceptance_receipt`; prove zero production callers and zero raw receipt-dict checks with `rg` and import-level tests.

This is narrower than a rewrite: retain the existing ledger, acceptance CAS, and validator, and make them mandatory.

## Required tests and retirement proof

Add deterministic tests for mismatched run, attempt ID/ordinal, graph revision, incarnation, provider/version, launch custody, commit, runtime, and content hash; mutation after snapshot; stale A→B and A→B→A evidence; provider error/missing provider; restart/reload; concurrent acceptance commits and duplicate idempotency.

Add two-container/PID-namespace tests: same numeric PID in a foreign namespace, PID reuse with changed process-start identity, missing lease, stale lease, and exact `ProcessCustodyReceipt` command/process-group mismatch. Existing incarnation checks are in `megaplan/_core/phase_runtime.py:63-73,180-245`; custody matching is in `runtime/process.py:281-335,477-504`.

Add tests proving malformed receipts yield blocked/unknown status, epic authority drift blocks parent advancement, manifests/releases reject legacy or identity-mismatched records, and every direct terminal path cannot unlock downstream completion without accepted identity.

Retirement proof: zero production callers of `set_acceptance_receipt`; zero direct receipt-dict acceptance checks; zero legacy epic completion append paths; monkeypatch the canonical validator and assert every reader invokes it.

## Unknowns

- Production completion mode per deployment is not established; tests and status defaults show shadow behavior.
- Static inspection cannot prove whether every live review has an active-step identity and launch-custody record.
- External release consumers outside this repository were not inspectable.
- No services, cloud state, or runtime processes were launched; conclusions are from repository code, schemas, call sites, and tests only.