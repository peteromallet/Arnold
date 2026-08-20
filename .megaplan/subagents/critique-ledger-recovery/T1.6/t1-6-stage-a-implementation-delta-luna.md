# T1.6 Stage-A WBC implementation delta — Luna

Status: read-only coding handoff; **not implemented or complete**.

## Frozen scope

One neutral dispatcher owns exactly five Stage-A effect families:

1. `MODEL_CALL` — the one admitted physical critic route;
2. `GENERATION_UPLOAD` — exact spec/archive/generation bytes to one target;
3. `PROCESS_CONTROL` — exact start and pre-issued stop operations;
4. `SIMPLE_FIXER` — one canonical fixer occurrence/effect;
5. `INCIDENT_NOTIFICATION` — one canonical incident message/card, with stable child chunks.

Every other effect family is `UNAVAILABLE_IN_GENERATION`, not a legacy fallback. In particular Git/PR/publication, arbitrary SSH, deploy/destroy, webhook, additional model routes, generic subprocess and auxiliary notifications cannot be invoked by the Stage-A installed generation.

## Core port

Add `arnold/workflow/effect_dispatcher.py` and `provider_capabilities.py`. Reuse vocabulary from `arnold/workflow/execution_attempt_ledger.py`; replace optional/shadow authorization in `effect_protocol.py` for the Stage-A composition.

```text
EffectEnvelope:
  family, occurrence_id, GLEK, parent/child GLEK
  exact target/provider/request bytes+digest/schema
  RA grant/revision/fence
  Custody occurrence/lease/epoch
  WBC attempt/store generation/intent digest
  installed generation/runtime/contract-bundle digest
  idempotency key/nonce, capability ID, reconciliation policy

dispatch(envelope, registered_capability) -> canonical EffectReceipt
reconcile(GLEK, independent_observation) -> canonical EffectReceipt
```

The raw transport is reachable only with an unforgeable dispatcher-issued capability. No caller `apply_fn`, optional adapter, boolean grant, projection or synthetic test context can satisfy production dispatch.

## Mandatory ordering

1. Validate exact supported family and immutable request bytes.
2. Read authoritative RA, Custody, generation and contract-bundle heads.
3. Durably reserve occurrence/GLEK and persist full intent (including notification chunk manifest).
4. Reread coherent owner heads immediately before dispatch.
5. Mark WBC `STARTED` durably.
6. Make exactly one registered raw call.
7. Persist terminal receipt or sticky `INDETERMINATE`.

No provider lock is held during owner reads. Missing/throwing/stale/mixed owner, ENOSPC before durable start, wrong target/generation/bundle or unavailable family makes zero calls.

Provider acceptance followed by timeout/disconnect/ack loss is `INDETERMINATE`, never `FAILED`; it is permanently no-redispatchable until an independent observation proves exact `APPLIED` or definite `NOT_APPLIED`. Adoption requires exact provider request/idempotency/payload/target/GLEK proof. Observation unavailable/conflicting remains unknown. No model fallback, alternate upload, second start, fixer child, or notification resend.

## Exact integrations

- `arnold/workflow/effect_protocol.py`: Stage-A production construction requires dispatcher/envelope; remove optional-true and action-off/shadow success.
- `arnold/workflow/execution_attempt_ledger.py`: strengthen `GlobalEffectIdentity` with family, target/version, request bytes, boundary schema and generation; add sticky unknown/no-redispatch reducer.
- `arnold_pipelines/megaplan/custody/common_worker_dispatch.py`: delegate model invocation to neutral dispatcher; never own raw callback.
- `custody/worker_dispatch_wbc.py`: delete synthetic fence-zero/action-off Stage-A facade; consume accepted owner ports.
- `workers/_impl.py` and selected Hermes/Shannon/Codex adapter: missing envelope hard-denies; remove `_run_step_with_worker_legacy` fallback for configured route.
- T1.3 authenticated adapter port: dispatcher capability/receipt is the trust root for raw physical capture.
- `cloud/cli.py` upload/start/stop call sites and provider factory: route only exact T1.9 operations; generic provider methods unavailable.
- T1.5 canonical `simple_fixer` runner: one predeclared occurrence/GLEK; no investigator/meta/child effect.
- T1.10 incident delivery: one parent GLEK plus deterministic child GLEKs; aggregation remains T1.10-owned.
- T1.8 generation: bind installed runtime and capability registry digest; old generation capabilities reject.
- T1.1/RA and Custody ports: read-only authoritative lookups/reconciliation; do not duplicate stores.

T1.9 owns upload/start/stop lifecycle and names; T1.6 owns only effect admission/ambiguity. T1.5 owns fixer policy. T1.10 owns message content/throttling. T1.8 owns generation selection.

## Tests

Add `tests/arnold/workflow/test_stage_a_effect_dispatcher.py` plus installed integration tests:

1. Each missing/stale/forged RA, fence, lease, epoch, WBC store, generation, bundle, capability or target causes zero raw calls.
2. Crash/ENOSPC before reserve/start: zero calls; after start/before call: pending/no call; after call: INDETERMINATE/no resend.
3. Response loss at every boundary; exact replay returns one receipt. Conflicting replay rejects.
4. Provider applied/ack-lost remains unknown across restart; exact independent observation adopts once.
5. One model call, no same/cross-model retry; caller-minted T1.3 capture rejects.
6. Upload bytes/target/generation substitution rejects; lost upload ack never uploads again.
7. Start response loss queries exact process identity; adopts one process or remains unknown. Stop uses pre-issued capability; PID reuse rejects.
8. Immediate/reconciler fixer race yields one occurrence/effect.
9. Two observers/200 scans yield one notification parent and at most one accepted child per chunk; renderer change reuses persisted bytes.
10. Enumerate every unused effect family and direct source/editable/wheel/wrapper/container alias: all unavailable and zero calls.
11. Runtime spies prove the dispatcher is the sole raw-call owner for the five families.
12. Source/fresh-wheel/installed entrypoints emit identical GLEKs, receipts and rejection codes.

## Integration order

1. Freeze T1.1 RA lookup, T1.3 authenticated capture, T1.5 occurrence, T1.8 generation and T1.9 launch ports.
2. Implement neutral types/reducer/capability registry and pure fault tests.
3. Migrate model call first; prove T1.2 route.
4. Migrate exact upload/start/stop; integrate T1.9.
5. Migrate one fixer and one notification.
6. Install explicit unavailable registry for all other families; run static/runtime bypass scan and wheel parity.

## Deferred Stage B

Defer Git/PR/publication, general SSH/cloud/deploy, all model routes, webhooks, native pipelines, auxiliary agents/tools, universal subprocess custody, platform-wide owner-store migration and full 1,328-row boundary inventory. They remain unavailable until migrated; “deferred” never means direct fallback.

No code, Git, cloud, provider, checklist or owner state was mutated. SHA-256 is recorded externally.
