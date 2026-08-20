# T1.2 Stage-A implementation delta — Luna

Status: read-only coding handoff; **not implemented and not complete**. Start only after the T1.3 pass-5 repair freezes an unforgeable authenticated-capture interface.

## Frozen scope

Implement exactly one configured physical critic route, no fallback, for the finite `plan -> critique -> gate -> finalize` Stage-A slice. Do not generalize every model route, pipeline/review hook, historical artifact format, or platform owner.

The route is admitted by configuration as one tuple `{provider,model,tool_mode,adapter/runtime generation,credential-set ID}`. T1.2 receives an authenticated immutable T1.3 receipt; it never calls `ProviderTranscript.capture_transport`, parses raw bytes, reconstructs route identity, or copies bundle/registry logic.

## Minimal domain model

Add one neutral-to-domain port module, preferably
`arnold_pipelines/megaplan/orchestration/critique_attempts.py`:

```text
AttemptTerminal = SUCCEEDED | PROVIDER_FAILED | PRODUCER_CONTRACT_FAILED |
                  PARSER_FAILED | SANDBOX_FAILED | CANCELLED
SemanticResult  = FINDING | NO_FINDING | EXTERNAL_UNVERIFIABLE
```

Immutable records:

- `CritiqueSelectionManifest`: plan/binding/iteration/round, exact single route, bundle ID/digest, ordered mandatory lens occurrences and digest.
- `CritiqueAttempt`: occurrence/attempt/parent retry IDs, route, start/terminal timestamps, terminal state, typed cause, T1.3 capture/health/receipt digests, WBC attempt/GLEK, no semantic field.
- `CritiqueSemanticResult`: only for `SUCCEEDED`; occurrence/attempt, exact T1.3 admitted payload/binding/raw receipt, result enum and finding IDs.
- `CritiqueRoundReceipt`: exact selected set, one accepted terminal attempt/result per mandatory occurrence, completeness digest, retry accounting and `admitted`.

Use canonical JSON + content digest and append-only attempt-specific paths. Never overwrite `iteration/lens` evidence on retry.

## Exact transition rules

1. Freeze selection before dispatch. Stage A may use the current configured mandatory set, but it must be explicit and ordered.
2. Reserve one attempt and WBC model-call GLEK before invoking the sole route.
3. Map transport/provider rejection before valid raw receipt to `PROVIDER_FAILED`; T1.3 producer/bundle incompatibility to `PRODUCER_CONTRACT_FAILED`; strict raw parse/framing failure to `PARSER_FAILED`; execution/container/path/permission isolation failure to `SANDBOX_FAILED`; authoritative cancellation to `CANCELLED`.
4. Only accepted T1.3 binding for the exact attempt becomes `SUCCEEDED`.
5. Only `SUCCEEDED` may create semantics. Any flagged finding -> `FINDING`; complete explicit unflagged set -> `NO_FINDING`; policy-scoped successful statement that external evidence is unavailable -> `EXTERNAL_UNVERIFIABLE`. The last is not clean.
6. One optional retry at most, only if the frozen Stage-A policy names the terminal class. It gets a new attempt ID/child GLEK under the same occurrence. No provider/model/tool/auth fallback and no ambient Hermes retry.
7. Reducer admits only exact selected-set equality and exactly one accepted succeeded result per mandatory occurrence. Failed/unknown/missing/duplicate occurrences reject the round.
8. Gate receives only `CritiqueRoundReceipt(admitted=true)`. It never consumes synthetic unverifiable checks, flags alone, latest files, or worker prose. `EXTERNAL_UNVERIFIABLE` blocks clean proceed under Stage A.

Provider response loss after dispatch remains WBC `INDETERMINATE`/unknown and no-redispatchable. It must not be mapped to `PROVIDER_FAILED`, retried, or given semantics until the owner adopts an exact authenticated receipt.

## Exact files/functions

### Add

- `arnold_pipelines/megaplan/orchestration/critique_attempts.py`: schemas, append-only store/reducer, exact-set validation.
- `tests/arnold_pipelines/megaplan/test_critique_attempts_stage_a.py`: pure state/reducer/fault matrix.
- `tests/arnold_pipelines/megaplan/test_critique_stage_a_installed.py`: wheel/installed finite-slice parity.

### Modify narrowly

- `orchestration/parallel_critique.py::_run_check`, `run_parallel_critique`: create per-occurrence attempts; remove `_unverifiable_check_payload` and broad error-to-semantic behavior from the Stage-A path; return round receipt plus payload, not `raw_output="parallel"` authority.
- `orchestration/critique_runtime.py::handle_critique`: freeze the selection manifest, invoke only Stage-A attempt service, prohibit outer sequential/model fallback for this route, persist content-addressed receipt.
- `orchestration/critique_custody.py::write_critique_production_receipt`, `_validate_production_receipt`, `validate_gate_input_custody`: bind selection/attempt/result/T1.3 receipt digests; require exact completeness even with zero findings.
- `handlers/gate.py::handle_gate` and the earliest gate-input seam: require admitted round receipt before reading flags/signals; operational-unverifiable prose cannot proceed.
- `_core/worker_fanout.py` and/or `runtime/batch.py` only as necessary to preserve attempt ID and typed terminal cause across the single selected worker boundary.
- selected worker adapter (`workers/hermes.py`, `workers/shannon*.py`, or `_impl.py` after route freeze): expose frozen T1.3 receipt and disable internal/ambient fallback/retry for Stage A. Do not implement a second capture authority.
- packaging exports only for the new module and installed CLI path.

Do not edit generic `arnold.pipeline.model_seam`, unrelated review hooks, other providers, T1.3 registry/manifests/parser, or platform-wide WBC owners.

## Minimal T1.3 ports to consume

Freeze names after the active repair, but require these semantics:

```text
AuthenticatedProviderReceipt  # unforgeable by ordinary caller
ContractAuthority.bind_output(step, payload, authenticated_receipt, expected_ids)
ContractHealth                # accepted/code/outcome/bundle/raw digest
ContractBinding               # exact bundle/output/raw/runtime identity
```

T1.2 stores immutable references/digests plus admitted payload; it does not trust the current public `adapter_authenticated` boolean. If the repair exposes verification separately, call `verify_authenticated_capture(expected_route, expected_attempt, receipt)` before binding.

## Finite tests

1. Each of six terminal states persists exactly once and has no semantic row.
2. `SUCCEEDED` plus explicit findings/unflagged/external-unverifiable produces the three exact semantics.
3. Six failed critics, mixed success/failure, missing/duplicate/wrong occurrence, wrong plan/round/route/bundle/raw receipt all reject custody and make zero gate calls.
4. Provider applied/ack-lost remains indeterminate, sticky and no-redispatchable across restart.
5. One eligible retry creates a distinct attempt/child GLEK; second retry and every route/model fallback reject.
6. Caller-minted/forged/stale T1.3 receipt, swapped session/attempt/channel/runtime/raw bytes reject before semantics.
7. Crash before reservation/start/terminal/result/round commit replays to one canonical state without overwrite.
8. Current `_on_unit_error`, `_unverifiable_check_payload`, ID rewrite, missing-question synthesis, first-check selection, flags-only and latest-file recovery cannot enter Stage-A authority.
9. Gate/finalize slice accepts a complete all-`NO_FINDING` round, routes `FINDING`, and blocks `EXTERNAL_UNVERIFIABLE`/incomplete.
10. Source, fresh wheel and installed entrypoint produce byte-equivalent manifests/receipts and identical rejection codes.

Run focused T1.3 source/installed parity first, then the new reducer/custody/gate suites and existing `parallel_critique`, `critique_custody`, gate/finalize regressions. Static scan must show the Stage-A path has one configured dispatch and no fallback chain.

## Deferred Stage B

Defer multi-route policy, every configured provider, adaptive route selection, platform-wide attempt ledger, generic non-Megaplan review semantics, historical artifact migration, universal owner-store adoption, broad legacy fallback cleanup and arbitrary process-compromise resistance. Unused routes must be unavailable—not silently supported by legacy behavior.

## Coding order

1. Freeze repaired T1.3 receipt verifier and single route tuple.
2. Add domain records/reducer and pure tests.
3. Port `_run_check`/`run_parallel_critique` to typed attempts with no fallback.
4. Bind custody exact-set completeness.
5. Gate fail-closed on admitted receipt.
6. Add crash/UNKNOWN and installed parity tests.

No source, Git, cloud, checklist or owner state was mutated. SHA-256 is recorded externally.
