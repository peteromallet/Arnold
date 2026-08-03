# a01-s05-authority-ownership-review-chain: authority-ownership × review-chain

## Verdict

Non-conformant. No P0 was found. Four reachable P1 gaps can either mutate completion authority through non-canonical paths or misreport acceptance to downstream consumers; two P2 documentation/coverage gaps remain.

The canonical acceptance implementation exists, but shadow/legacy callers and projections bypass parts of it.

## Intended canonical contract

The source-to-owner contract assigns authority facts, routing decisions, and execution verdicts to Run Authority; WBC and projections provide declarations/evidence only (`arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json:3-20`).

The canonical completion path is:

1. validate an acceptance boundary and identity;
2. stage state, immutable snapshot, and committed transaction together;
3. apply them through CAS;
4. validate receipts through `ChainState.validate_acceptance_receipt`.

That implementation is in `arnold_pipelines/megaplan/orchestration/completion_io.py:584-638`, `:677-775`, `:796-806`, and `arnold_pipelines/megaplan/chain/spec.py:1646-1746`.

WBC evidence, chain projections, cloud status, and sidecars must not independently authorize completion. The chain persistence code explicitly says `state.json` is authority and projection history is supplemental (`arnold_pipelines/megaplan/chain/spec.py:1866-1885`, `:2117-2135`).

## Evidence and complete path inventory

I searched the repository with `rg --files` and focused `rg` queries over `arnold_pipelines`, `tests`, `scripts`, and `docs` for `completed.append`, `save_chain_state`, `save_epic_chain_state`, `acceptance_receipt`, `TransitionPolicy`, `review_done`, WBC transition writers, `status_snapshot`, `candidate_ready`, and release-validator call sites. I then inspected each definition and caller directly.

- Review writer: `handlers/review.py` evaluates policy and writes `transition_decision_review_done.json` (`:1769-1917`), then mutates state via `apply_state_projection` and `save_state_merge_meta` (`:2178-2202`, `:2344-2345`).
- Canonical chain acceptance writer: `completion_io.py` CAS-journals state, transaction, and snapshot (`:731-806`); `_append_completed_with_guard` mirrors only the committed result in atomic/enforce mode (`chain/__init__.py:3477-3613`).
- Legacy chain writers: shadow mode directly appends `state.completed` (`chain/__init__.py:3372-3425`); supervisor paths append completed records and call `save_chain_state` (`supervisor/chain_runner.py:678-690`, `:818-830`).
- Epic writer: `epic_chain.py` loads and atomically replaces its own JSON state (`:339-355`); `run_epic_chain` appends child completion and advances the parent (`:755-813`).
- Canonical readers/gates: chain successor gate (`chain/__init__.py:8207-8267`), supervisor gates (`supervisor/chain_runner.py:890-1025`), cloud wrapper gate (`cloud/wrapper_acceptance_gate.py:221-285`), and resume gate (`runtime/resume.py:80-119`).
- Bypass readers: epic observation reads plan `state.json` directly (`epic_chain.py:382-407`); cloud status treats any receipt-shaped dictionary as accepted (`cloud/status_snapshot.py:1529-1580`).
- Release consumer: `scripts/validate_post_m11_release_evidence.py` validates a release record but explicitly does not interpret release policy (`:1-2`). No production caller of this script or a downstream release mutation was found by repository-wide `rg`.

## Adherence gaps

- **P1 — authority mutation: review acceptance is advisory when it must be authoritative.** `TransitionPolicy` allows an approved, complete review with missing review evidence (`orchestration/transition_policy.py:194-207`); provider failures are explicitly advisory (`:194-201`). Tests assert both behaviors (`tests/arnold_pipelines/megaplan/test_transition_policy.py:284-318`). The review handler then applies the next state and persists it (`handlers/review.py:2178-2202`, `:2344-2345`). Observed behavior is therefore “provider unavailable/missing evidence, yet review may reach done.” Inference: this violates the documented “validated done decision” contract (`docs/arnold/megaplan-boundary-turn-design.md:247-258`) whenever provider/review evidence is required for acceptance.

- **P1 — authority mutation and status misreporting: epic completion trusts a legacy projection after detecting authority disagreement.** `_observe_child_epic` marks a child complete solely because completed-label coverage reaches the milestone count (`chain/epic_chain.py:438-449`). If `_plan_terminal_completion_is_authoritative` disagrees, it records drift but deliberately preserves `effective_status == "complete"` (`:489-518`). `run_epic_chain` then validates only that observed status and appends/advances the parent (`:755-813`). Existing tests explicitly prove this state (`tests/arnold_pipelines/megaplan/test_epic_chain.py:405-445`). This is a reachable false-positive parent mutation.

- **P1 — authority mutation: shadow/legacy completion writers remain live beside the CAS writer.** `ChainState` defaults to `completion_contract_mode="shadow"` (`chain/spec.py:1287-1288`), and shadow/warn/off mode intentionally appends directly (`chain/__init__.py:3372-3425`). Supervisor completion paths also append directly (`supervisor/chain_runner.py:683-689`, `:824-830`). `save_chain_state` is atomic replacement but has no CAS guard around the read/modify/write operation (`chain/spec.py:2073-2115`). These are duplicate mutation implementations, not merely projections. Atomic/enforce mode blocks missing acceptance (`chain/__init__.py:3477-3497`), so the gap is primarily the still-reachable legacy mode.

- **P1 — status misreporting: cloud status equates receipt shape with validated acceptance.** `status_snapshot.py` reads the latest chain JSON directly and sets acceptance true when `acceptance_receipt` is merely a dictionary (`:1529-1545`, `:1573-1580`), without calling `validate_acceptance_receipt`. That boolean feeds `assess_advancement` (`:1669-1684`). The function says this is “purely a status projection” (`:1549-1554`), so it does not directly mutate authority; however watchdog/resident/operator consumers can receive successor-ready status from forged, stale, or uncommitted receipt data. Canonical gates elsewhere correctly validate receipts, proving this caller bypasses an existing solution.

- **P2 — status/conformance misreporting: review receipt inventory is stale and incomplete.** The handler emits receipts for human verification, rework, cap, and reducer promotion (`handlers/review.py:1529-1578`), and tests prove durable emission (`tests/arnold_pipelines/megaplan/test_phase_wbc_adoption.py:279-309`). The C1 document still reports all five review contracts as absent (`docs/workflow-boundary-contracts/c1/coverage_and_exceptions.md:73-83`); additionally, no producer for `review_child_outputs` was found. This does not itself mutate authority, but it causes audit results to be wrong and leaves one declared review boundary without evidenced ownership.

- **P2 — downstream release ownership is not connected in-repository.** The release validator accepts `candidate_ready` and `complete` records after structural checks (`scripts/validate_post_m11_release_evidence.py:568-591`) and exits successfully after validation (`:594-607`), but no in-repo release mutation/consumer was found. Observed fact: validation is isolated. Inference: an external caller could mistake validator success or `candidate_ready` for release authority. The external release consumer and its owner are unknown.

## Incident reachability and severity

No P0 path was found where a projection or WBC sidecar directly writes canonical completion. WBC registration/validation produces evidence, not mutation (`chain/wbc.py:135-242`), and the atomic acceptance path is fail-closed and CAS-protected.

P1 paths are reachable through normal review success, epic polling, default shadow-mode chain execution, and cloud status generation. The most severe consequences are false parent advancement, successor-ready status, and review completion without required provider evidence. Epic state replacement also has no lock/CAS (`epic_chain.py:352-355`), so two concurrent containers can last-writer-win independently of PID namespaces.

## Minimal generalized remediation

Consolidate all authoritative completion writes on `prepare_acceptance_commit`/`commit_acceptance_commit` and all acceptance reads on `validate_acceptance_receipt`.

- Remove direct completion appends from shadow and supervisor paths; shadow mode may emit diagnostics but must not create authoritative completed records. Migrate existing legacy records by attaching valid committed transactions or marking them non-authoritative.
- Make epic completion require a validated child acceptance receipt; authority disagreement or read failure must produce `blocked/unknown`, never `complete`. Protect parent state with CAS or an owner lease, not only atomic replacement.
- Make review→done require explicit required evidence and successful required providers. Persist the transition decision and state mutation under one transaction or make state re-check the decision’s identity/hash before mutation.
- Change cloud status to call canonical receipt validation; malformed/uncommitted receipts become false/unknown.
- Add one release gate consuming canonical chain acceptance plus the release record; keep the structural validator read-only.
- Retire `set_acceptance_receipt`, which has no production callers in the searched tree (`chain/spec.py:1756-1770`), or make it private and unreachable.

## Required tests and retirement proof

Add deterministic tests for:

- two concurrent processes and two containers sharing the state volume: exactly one CAS acceptance wins; no PID namespace assumption;
- crash/restart after journal prepare and before commit: recovery cannot expose completion;
- provider unavailable, provider error, stale evidence, and provider identity mismatch: review cannot reach done;
- forged receipt dictionaries, edited sidecars, WBC evidence, or cloud projections: canonical state and gates remain unchanged;
- epic authority disagreement and concurrent parent updates: no false completion or lost update;
- static/AST call-graph assertions that direct completion appends and `set_acceptance_receipt` are absent or unreachable from production entry points;
- release validator success with `candidate_ready` cannot authorize release without the canonical acceptance gate.

## Unknowns

The external release consumer is not present in this repository. Production values for `completion_contract_mode`, whether provider diagnostics are intentionally advisory, and the deployment’s shared-volume/locking guarantees require operational confirmation.