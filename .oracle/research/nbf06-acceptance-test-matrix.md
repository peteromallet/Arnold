# NBF-06 acceptance and test matrix — authoritative A01–A38 registry

This Round-22 repair candidate is the sole machine-facing registry for NBF-06 acceptance
nodes. It is bound to tasklist `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959`, plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`, NorthStar `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`, and Round-22 adjudication input `467366deaef4d7056fce9b70a596b26282789d4ae56ad1564e9c2c47d10cc4ca` (prior Round-21 input: `b7fdcbd50ef19437273aa62049a6c4c2f87e2ad7942114f9ff6336649da6a67b`). The brief references this registry; canonical provider-family aliases are defined below, while no alias creates a second authority. Prior Round-6–21 amendment stacks and old vectors are historical and removed from the current contract.

## Scope and authority

NBF-06 owns T8 provider exhaustion, observations, keyed streaks, bounded
hold/probe, evidence-bound recovery, degradation, configured fallback,
scalar pin, return, and replay/race/execute safety. It extends the existing
NBF-01 IncidentLedger and NBF-02 `dispatch_with_admission`; it creates no
provider store/cache, journal, scheduler, projection, rotator, admission door,
or terminal writer. NBF-04/NBF-05 own signal/custody/shell authority. NBF-08
owns chain-control. Generic `append_event` is forbidden to NBF-06 policy. A
non-null `configured_fallback_chain_identity` is exactly the raw32 SHA-256
digest of canonical chain bytes; it is never text or hex. Absent chain identity
is explicit null (U64BE(0)); all-zero raw32 is reserved for real digests and is
never a no-chain sentinel. `provider_epoch_identity` is exactly one raw32
digest in every NBF06 wire field; display labels are non-serializable. Route
liveness and membership digests remain separate fencing evidence in the epoch
claim/binding, excluded from stable identity and failure-key preimages; refresh
alone cannot rekey, reset, or authorize. Probe projection state is frozen to
`probe_status=none|leased|passed|failed`; unknown and expiry reconcile to held/unresolved
(`failed`) with no launch. `retry_not_before` and executor `deadline` are
integer nanoseconds from injected `MonotonicClock.now_ns()`; the exact formula
is `retry_not_before_ns=max(parent_retry_not_before_ns,terminal_observed_ns)`
and the lease deadline is the supplied executor deadline with
`deadline_ns >= retry_not_before_ns`. Eligibility and expiry are inclusive:
`now_ns >= retry_not_before_ns` and `now_ns >= deadline_ns`. Rollback or an
ambiguous clock jump holds/unresolves; no new state or policy constant is
introduced. One bounded lease and one close/reconcile CAS are allowed.
Uniform nullability rule: a typed `DispatchOutcome` may carry staged nullable
postcommit IDs as `None`, but precommit wire omits those IDs entirely. Every
wire field that is declared nullable uses exactly one U64BE(0) null; omission
is distinct and is permitted only where the schema explicitly omits the field.
No decoder infers an omitted postcommit ID or treats omission as explicit null.

Canonical provider family is the upstream provider, not transport `omp`:
direct `codex:<model>` → `codex`, `claude:<model>` → `claude`,
`premium:<model>` → `premium`, aliases `openai-codex:<model>` → `codex` and
`grok:<model>` → `xai`, and `omp:<upstream>/<model>` → lowercase upstream
(`deepseek`, `fireworks`, `mimo`, `openai`, and every registered upstream).
Empty, malformed, and unknown forms reject closed; no family is guessed. The
normalized family is used consistently in epoch identity, claim/binding,
failure key, target/return/child proofs, and probe bindings; liveness and
membership are fencing-only evidence.

`DispatchOutcome.provider_evidence` is a closed nested
`NBF06-PROVIDER-EVIDENCE-NESTED-V1` record. Required fields are
`observation_id` (non-empty text), `retryability_class` (known enum),
`exhausted_attempt_count` (positive U64), `terminal_provider_evidence_id`
(non-empty text), `precondition_identity` (non-empty text),
`provider_epoch_identity` (raw32), `provider_failure_key` (canonical
raw32 identity, lowercase-hex live form), `observed_at` (ISO timestamp), and
`provider_failure_class` (known enum); version/domain are fixed and unknown
members reject. The forward adapter maps this entire nested record to the
typed precommit epoch/key/retryability/provider-class fields; the inverse
reconstructs the nested record with the same required fields. Missing members,
unknown enum/version, bad raw32, conflicting top-level key alias, or class
disagreement reject. Staged terminal/observation IDs are omitted until
postcommit, and nested evidence never writes a ledger record.

V2 provider recovery is bridged to the canonical NBF-01
`ChangedPrecondition`, not treated as a second authority. After the exact
passed probe result is closed, the locked seam invokes
`incident/schema.py:produce_provider_recovery_verified` with typed source
handles and the cited evidence event. Before/after content IDs and both
provider-failure-key fields are producer-derived from authoritative snapshots
(the recovery key is unchanged); evidence digest and plan/phase/logical,
admission, epoch, route, and closed-lease links come from the cited evidence
snapshot. `IncidentLedger.append_changed_precondition` is the one append writer
and runs once. The atomic child reservation consumes it once through
`consume_changed_precondition`, recording both `authorizing_event_id` and
`consumed_changed_precondition_event_id`. Decoders cannot mint the event from
V2 bytes or hashes; uncommitted/unconsumed, open/foreign-lease, mismatched,
conflicting, replay, and cyclic cases reject and hold.

Planned deliverables and handoff are explicit: NBF-01 owns shared schema
codecs/inverses and `WorkerAdmissionReceipt`; NBF-06 owns the provider literal
vectors, `scripts/check_nbf06_a38.py`, and
`tests/arnold_pipelines/megaplan/fixtures/nbf06_a38` negative fixtures; NBF-07
invokes the checker during final validation. Those script/fixture paths are
expected to be absent in this preimplementation tree and are not a current
failure.

Custody binding is explicit and honest: NBF-01 owns the canonical
`WorkerAdmissionReceipt` bytes/ID and its chain, origin, epoch-claim, and
epoch-binding fields. NBF-06 may link and verify those raw bytes only; it has
no receipt-ID derivation or custody authority. Cloud transport is bytes-only
and cannot mint, rewrite, or reinterpret the NBF-01 binding.

### NBF-02 dispatch-seam handoff order

The only scheduler/launch/intake integration seam is the exact NBF-02 symbol
`arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission`.
The protocol deliberately retains the append-first source cutpoint: NBF-01's
`IncidentLedger.append_terminal_outcome` is the one physical terminal writer
and completes before T8 selection. The T8 applier never creates a second
terminal writer.

| Order | Typed value and exact edge | Forbidden alternate |
| ---: | --- | --- |
| 1 | pre-tool request → `dispatch_with_admission` admission/reservation → NBF-01 `WorkerAdmissionReceipt` | policy/target selection before admission |
| 2 | accepted receipt/context → `arnold_pipelines/megaplan/incident/ledger.py:bind_provider_epoch_locked` → epoch claim/binding | caller epoch or second reservation |
| 3 | accepted launch → `arnold_pipelines/megaplan/cloud/worker_dispatch.py:_outcome_from_terminal_exception` → structured typed adapter evidence | prose/stderr T8 classification |
| 4 | normalized accepted evidence → typed `DispatchOutcome` → `serialize_dispatch_outcome_precommit` | direct provider-event write |
| 5 | accepted bridge → one `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` → committed/replayed terminal event | second terminal writer or policy before append |
| 6 | committed terminal + receipt/reservation + evidence/epoch/projection → locked immutable `ProviderLedgerView` | caller-supplied/mutable view or stale projection |
| 7 | typed provider request + immutable `ProviderLedgerView` → exactly one `select_provider_route(request, ledger_view)` → `ProviderRouteDecision` | second selector or scheduler |
| 8 | decision → `apply_provider_route_decision_locked` → observation/hold/route CAS (terminal writer is not called) | unlocked terminal/observation writer |
| 9 | committed terminal/observation → `ProviderEvidenceEnvelope` or child/return composite | postcommit effect before commit |

Every compatibility entrance in the A38 alternate registry delegates to this
seam and cannot replace scheduler, launch, or intake ownership. Missing,
non-accepted, or ambiguous typed outcomes stop before steps 4–7.

`select_provider_probe` is a pure adapter over the same immutable parent
`ProviderLedgerView`, never a second selector. Its request must carry and
match the parent admission receipt, reservation event, configured-chain
identity, provider-failure key, provider epoch identity and claim/binding
digests, route-liveness/fence identity, and the single-use probe lease fence.
It returns only a typed probe request: it cannot choose a route or target,
launch a client/worker, create a child, or append durable state. The typed
probe request serializer/inverse ends before
`arnold_pipelines/megaplan/incident/ledger.py:record_provider_probe_result_locked`;
that locked writer alone persists the executor result, and any missing or
mismatched parent binding fails closed.

### Terminal transaction and crash/replay vectors

The append-first ledger view is rebuilt under the ledger lock from the committed
terminal event, `reservation_event_id`, `admission_receipt_id`, logical and
semantic dispatch identifiers, normalized selected spec, provider failure key
and class, raw32 epoch identity plus claim/binding fences, configured-chain
identity, structured provider evidence, route fence, and current observation /
hold / probe projection. Caller prose, a mutable caller view, wall clock, and
postcommit IDs are not policy inputs. The terminal writer is invoked exactly
once; matching bytes replay the existing event and conflicting bytes yield
`durability_unknown`.

| Crash cutpoint | Replay result | Cardinality invariant |
| --- | --- | --- |
| before terminal append | re-run the accepted adapter and append the one terminal | one terminal, no observation/child yet |
| after terminal append, before T8 view | reload terminal and rebuild the immutable view | no duplicate terminal |
| terminal plus observation CAS | replay terminal and observation by parent/digest CAS | one terminal, one observation/count |
| after policy decision, before postcommit effect | replay committed decision/effect and continue postcommit | no duplicate terminal, observation, lease, or child |

All four cutpoints are fail-closed on torn/conflicting bytes and remain held
until exact reconciliation; a terminal-only record cannot authorize a route
effect until its observation/policy reconciliation is committed.

Accordingly, absent future A01–A38 tests, the checker, and its negative
fixtures are not required to pass this packet validation; they become
implementation/final-validation obligations after NBF-06 is built.

## Canonical contract and literal fixture registry

Every current event/branch fixture is `U64BE(length)||UTF-8/NFC bytes`; the
chain fixture's `spec_count` is the one raw U64BE field, and the NBF-01
`ProviderFailureKey` fixture is the other exception and uses its existing
canonical sorted JSON codec. Raw digests are exactly 32 bytes; `null` is
explicit and differs from omission; the event-ID field is excluded from its
own preimage. Canonical chain vocabulary is
`configured_fallback_chain_identity` (display alias `chain_digest` only; the alias is never serialized).
The sole canonical CHAIN V1 codec is
`arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_configured_fallback_chain_v1`
with inverse `deserialize_configured_fallback_chain_v1`; the sole identity
producer is `derive_configured_fallback_chain_identity`. The legacy
`arnold_pipelines/megaplan/fallback_chains.py:encode_fallback_specs` /
`decode_fallback_specs` pair is compatibility-only for reserved
`__fallback_json__:` persistence, cannot supply CHAIN V1 bytes, and cannot
select a target. `_advance_configured_spec_fallback` remains the sole
configured-chain selection authority.

The `CHAIN(175)` tail is unambiguous: the count is a raw U64BE field, not a framed text field. After the raw 32-byte origin digest,
the eight-byte (16-hex-digit) `spec_count` field is
`0000000000000001` (U64BE decimal 1), and
`000000000000001a` is U64BE length 26 for the one displayed normalized spec.
The scalar fixture therefore has one spec; the 16-digit hex field is not the
integer count 16, and the next framed field is the 26-byte spec text. A missing
configured chain is always explicit null; never infer it from current config.
The complete CHAIN V1 field order is
`domain,phase,parser_version,origin_bytes,origin_digest(raw32),spec_count(U64BE),normalized_spec_1..N`;
the canonical serializer/inverse above owns this exact order and normalization.
The exact compatibility rejection fixture is
`LEGACY_CHAIN_JSON(48)=5f5f66616c6c6261636b5f6a736f6e5f5f3a5b226f6d703a646565707365656b2f646565707365656b2d63686174225d`
with SHA-256 `ea4479ea855450f2987f003338d57d63215e18e317e0c6fe232122f8c3e1a4cf`;
it is compatibility persistence only and must fail the canonical CHAIN codec.

The exact chain, precommit adapter-evidence, `DispatchOutcome` bridge, and postcommit envelope hex vectors are:

```text
CHAIN(175)=00000000000000114e424630362d434841494e2d49442d5631000000000000000372756e000000000000000f4e424630362d5041525345522d5631000000000000001a70726f66696c653d64656661756c740a70686173653d72756e0a00000000000000208fd29563dbc4e40b032a68f0435a78c86a5077da6dcee8c433590ddf57cda4d00000000000000001000000000000001a6f6d703a646565707365656b2f646565707365656b2d63686174
CHAIN_SHA=4fd9bda5df6d1e33879fb46cdb5e92cd86c19d802a67b14d7b14269df663ab25
PRECOMMIT_EVIDENCE_FIELDS=domain,plan,phase,logical_dispatch_id,admission_receipt_id,reservation_event_id,configured_fallback_chain_identity(raw32-or-explicit-null),fingerprint(raw32),normalized_spec,provider_epoch_identity(raw32),provider_failure_key(raw32),result,retryability,provider_failure_class,nested_provider_evidence(framed-NBF06-PROVIDER-EVIDENCE-NESTED-V1); no postcommit terminal/observation/event/derived receipt IDs
DISPATCH_OUTCOME_FIELDS=DispatchOutcome._FIELDS={schema_version,kind,launch_state,plan_id,phase,dispatch_family_id,logical_dispatch_id,admission_receipt_id,semantic_dispatch_fingerprint,selected_spec,provider,route_liveness_kind,route_liveness_identity,route_liveness_digest,worker_identity,started_at,finished_at,success_payload,terminal_failure,provider_evidence,provider_failure_key,disposition_id,reconciliation_event_id,terminal_outcome_event_id} → explicit map/ignore/stage table below; bridge has its own domain and bytes
DISPATCH_OUTCOME_STAGE=typed live object stages nullable terminal_outcome_event_id and reconciliation_event_id only after commit; precommit wire omits both; admission_receipt_id is supplied by accepted admission context; no observation_id/event_id/derived_receipt_id fields exist on DispatchOutcome; to_dict/from_dict is lossless live-object compatibility, while the precommit bridge is one-way mapped/re-encoded
PROVIDER_ENVELOPE_FIELDS=domain,plan,phase,logical_dispatch_id,admission_receipt_id,reservation_event_id,configured_fallback_chain_identity(raw32-or-explicit-null),fingerprint(raw32),normalized_spec,provider_epoch_identity(raw32),provider_failure_key(raw32),terminal_event_id,observation_id,result,retryability,provider_failure_class
DISPATCH_OUTCOME_FIELD_RULES=schema_version:mapped(version gate);kind:mapped(result);launch_state:mapped(accepted gate);plan_id:mapped;phase:mapped;dispatch_family_id:ignored transport metadata;logical_dispatch_id:mapped;admission_receipt_id:mapped and must equal accepted context;semantic_dispatch_fingerprint:mapped(fingerprint);selected_spec:mapped(normalized_spec);provider:ignored;route_liveness_kind:ignored precommit;route_liveness_identity:ignored precommit;route_liveness_digest:ignored precommit;worker_identity:ignored precommit;started_at:ignored precommit;finished_at:ignored precommit;success_payload:ignored for provider precommit;terminal_failure:ignored for provider precommit;provider_evidence:mapped nested epoch/key/retryability/provider class;provider_failure_key:mapped optional compatibility alias and must match nested key;disposition_id:ignored for provider precommit;reconciliation_event_id:staged-after-commit and omitted precommit;terminal_outcome_event_id:staged-after-commit and omitted precommit;reservation_event_id:supplied only by accepted admission context, never a DispatchOutcome field
NESTED_PROVIDER_EVIDENCE_FIELDS=schema_version(U64=1),domain(fixed NBF06-PROVIDER-EVIDENCE-NESTED-V1),observation_id(text),retryability_class(enum),exhausted_attempt_count(U64>0),terminal_provider_evidence_id(text),precondition_identity(text),provider_epoch_identity(raw32),provider_failure_key(raw32 identity, lowercase-hex live form),observed_at(ISO-8601),provider_failure_class(enum); no nullable nested members; staged terminal/observation/reconciliation/derived-receipt IDs omitted
NESTED_PROVIDER_EVIDENCE_PRODUCER=accepted `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome` → `arnold_pipelines/megaplan/orchestration/phase_result_classify.py:classify_dispatch_outcome` → `arnold_pipelines/megaplan/incident/schema.py:serialize_dispatch_outcome_precommit`; inverse `deserialize_dispatch_outcome_precommit` requires accepted admission context equality and reconstructs all 11 nested members from the framed `nested_provider_evidence` field
NESTED_PROVIDER_EVIDENCE_ENCODING=U64BE(schema_version=1), then each ordered member as U64BE(length)||UTF-8/NFC text, U64BE(positive integer), or U64BE(32)||raw32; exactly 11 members, no nullable nested member; nested observation/provider-evidence IDs are evidence-local and not postcommit ledger IDs
NESTED_PROVIDER_EVIDENCE_COMPLETE_FIXTURE=all fields populated; negative fixtures=`missing_provider_epoch_identity|unknown_nested_member|conflicting_nested_provider_failure_key|top_level_alias_mismatch|unknown_nested_version`; reject closed
NESTED_PROVIDER_EVIDENCE(285)=000000000000000100000000000000214e424630362d50524f56494445522d45564944454e43452d4e45535445442d5631000000000000000e6f62732d65766964656e63652d31000000000000000c617661696c6162696c6974790000000000000001000000000000001c7465726d696e616c2d70726f76696465722d65766964656e63652d31000000000000000e707265636f6e646974696f6e2d310000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000014323032362d30392d30315430303a30303a30305a000000000000000c617661696c6162696c697479
NESTED_PROVIDER_EVIDENCE_SHA=8983d7f08de52ab98310c0db1eafbfff46688b48caa92b9e52abef69319b4094
NESTED_PROVIDER_EVIDENCE_FIELDS=schema_version=1,domain=NBF06-PROVIDER-EVIDENCE-NESTED-V1,observation_id=obs-evidence-1,retryability_class=availability,exhausted_attempt_count=1,terminal_provider_evidence_id=terminal-provider-evidence-1,precondition_identity=precondition-1,provider_epoch_identity=540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28,provider_failure_key=35f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c,observed_at=2026-09-01T00:00:00Z,provider_failure_class=availability
NESTED_NEGATIVE_FIXTURES=missing_provider_epoch_identity(245,5833944cbb69cdf6ed837f1c9adb6914ff151b7c1b5c41ff5544f3344af75215)|unknown_nested_member(310,541c2f05fb5bc1658aaa949b2c7fc60485deace53bf7aca5005d25a24f1fe590)|conflicting_nested_provider_failure_key(285,c781a9c85af03e85a509a2ba921094f2a3439489297f0f7d311f2ddd66328f52)|top_level_alias_mismatch(PRECOMMIT_EVIDENCE key bytes replaced by aa*32;656,2914faedea361bfbe815093f6fb95fe373290d52518f9a91e1b308992967d9aa)|unknown_nested_version(285,09f9d115122b3312f898c000240a9e4c40bbdaf8d559683f5009627e6663e21f)
NESTED_NEGATIVE_MUTATIONS=missing_provider_epoch_identity=delete ordered member 8;unknown_nested_member=append U64BE(17)||"unexpected_member";conflicting_nested_provider_failure_key=replace ordered raw32 key with aa*32;top_level_alias_mismatch=replace outer provider_failure_key raw32 at byte offset 265 with aa*32;unknown_nested_version=replace schema_version U64BE(1) with U64BE(2)
The current PRECOMMIT_EVIDENCE and DISPATCH_OUTCOME payloads append one
U64BE-length-framed copy of this nested payload; their exact 656-byte and
644-byte bytes/hashes are published below. The five negative fixtures are
exact byte mutations of the positive fixture (or the named outer alias
mutation) and each must fail closed before terminal/route writes.
SUPERSEDED_PRECOMMIT_EVIDENCE_V0(363)=000000000000002c4e424630362d50524f56494445522d414441505445522d45564944454e43452d505245434f4d4d49542d56310000000000000006706c616e2d31000000000000000372756e000000000000000a64697370617463682d31000000000000000b61646d697373696f6e2d31000000000000000d7265736572766174696f6e2d31000000000000000000000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000001a6f6d703a646565707365656b2f646565707365656b2d636861740000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c000000000000001270726f76696465725f657868617573746564000000000000000c617661696c6162696c697479000000000000000c617661696c6162696c697479
SUPERSEDED_PRECOMMIT_EVIDENCE_V0_SHA=f01620b3172103e5d4adbb8c3e35ba00e57b0aba0dc09f5c8b9965b1204ca3e2
SUPERSEDED_DISPATCH_OUTCOME_V0(351)=00000000000000204e424630362d44495350415443482d4f5554434f4d452d4252494447452d56310000000000000006706c616e2d31000000000000000372756e000000000000000a64697370617463682d31000000000000000b61646d697373696f6e2d31000000000000000d7265736572766174696f6e2d31000000000000000000000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000001a6f6d703a646565707365656b2f646565707365656b2d636861740000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c000000000000001270726f76696465725f657868617573746564000000000000000c617661696c6162696c697479000000000000000c617661696c6162696c697479
SUPERSEDED_DISPATCH_OUTCOME_V0_SHA=71843a62890fdf03ab3e370b3e904dcb6fde63258e8dd760abfa1a842888a534
PRECOMMIT_EVIDENCE(656)=000000000000002c4e424630362d50524f56494445522d414441505445522d45564944454e43452d505245434f4d4d49542d56310000000000000006706c616e2d31000000000000000372756e000000000000000a64697370617463682d31000000000000000b61646d697373696f6e2d31000000000000000d7265736572766174696f6e2d31000000000000000000000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000001a6f6d703a646565707365656b2f646565707365656b2d636861740000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c000000000000001270726f76696465725f657868617573746564000000000000000c617661696c6162696c697479000000000000000c617661696c6162696c697479000000000000011d000000000000000100000000000000214e424630362d50524f56494445522d45564944454e43452d4e45535445442d5631000000000000000e6f62732d65766964656e63652d31000000000000000c617661696c6162696c6974790000000000000001000000000000001c7465726d696e616c2d70726f76696465722d65766964656e63652d31000000000000000e707265636f6e646974696f6e2d310000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000014323032362d30392d30315430303a30303a30305a000000000000000c617661696c6162696c697479
PRECOMMIT_EVIDENCE_SHA=93abaf0c39d87ed58fd62c901f45e6d11320b139534dbfab26336f898b74cb25
DISPATCH_OUTCOME(644)=00000000000000204e424630362d44495350415443482d4f5554434f4d452d4252494447452d56310000000000000006706c616e2d31000000000000000372756e000000000000000a64697370617463682d31000000000000000b61646d697373696f6e2d31000000000000000d7265736572766174696f6e2d31000000000000000000000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000001a6f6d703a646565707365656b2f646565707365656b2d636861740000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c000000000000001270726f76696465725f657868617573746564000000000000000c617661696c6162696c697479000000000000000c617661696c6162696c697479000000000000011d000000000000000100000000000000214e424630362d50524f56494445522d45564944454e43452d4e45535445442d5631000000000000000e6f62732d65766964656e63652d31000000000000000c617661696c6162696c6974790000000000000001000000000000001c7465726d696e616c2d70726f76696465722d65766964656e63652d31000000000000000e707265636f6e646974696f6e2d310000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000014323032362d30392d30315430303a30303a30305a000000000000000c617661696c6162696c697479
DISPATCH_OUTCOME_SHA=71574e243d25afed41c8c2636968bc35c79b8a0d99f59f479f3f8e320fc40384
PROVIDER_ENVELOPE(393)=00000000000000234e424630362d50524f56494445522d45564944454e43452d454e56454c4f50452d56310000000000000006706c616e2d31000000000000000372756e000000000000000a64697370617463682d31000000000000000b61646d697373696f6e2d31000000000000000d7265736572766174696f6e2d31000000000000000000000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000001a6f6d703a646565707365656b2f646565707365656b2d636861740000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c000000000000000a7465726d696e616c2d31000000000000000d6f62736572766174696f6e2d31000000000000001270726f76696465725f657868617573746564000000000000000c617661696c6162696c697479000000000000000c617661696c6162696c697479
PROVIDER_ENVELOPE_SHA=e579db42c62a9e5560211193f45961b7325dd743c37040157577b255fa795363
```

The failure-key, epoch, and refusal payloads are also literal current vectors:

```text
FAILURE_KEY_JSON_FIELDS=version,phase,selected_spec,provider_failure_class,provider_epoch_identity; sorted keys; provider_epoch_identity is lowercase-hex display of raw32 epoch identity; separators=(',',':'); UTF-8; no U64 framing
FAILURE_KEY_JSON_BYTES(205)=7b227068617365223a2272756e222c2270726f76696465725f65706f63685f6964656e74697479223a2235343063386462366439663765343061313632663036616136666631633965366136626533633033313337386537373334366631393262393635376362663238222c2270726f76696465725f6661696c7572655f636c617373223a22617661696c6162696c697479222c2273656c65637465645f73706563223a226f6d703a646565707365656b2f646565707365656b2d63686174222c2276657273696f6e223a317d
FAILURE_KEY_SHA=35f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c
EPOCH_CLAIM(280)=000000000000001d4e424630362d50524f56494445522d45504f43482d434c41494d2d56320000000000000001320000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000008646565707365656b000000000000001a6f6d703a646565707365656b2f646565707365656b2d636861740000000000000007726f7574652d310000000000000020222222222222222222222222222222222222222222222222222222222222222200000000000000203333333333333333333333333333333333333333333333333333333333333333000000000000000137000000000000002052884d9a49be95a5d5092a5e5b68129e9ee689b1ae42ca8f022b0a0d0a91ca1c
EPOCH_CLAIM_SHA=f4028a7a2850021c459f64df2308423747a89e34ceb36fc6054d31a0352c594f
EPOCH_BINDING(199)=000000000000001f4e424630362d50524f56494445522d45504f43482d42494e44494e472d5632000000000000002052884d9a49be95a5d5092a5e5b68129e9ee689b1ae42ca8f022b0a0d0a91ca1c000000000000000d7265736572766174696f6e2d31000000000000000b61646d697373696f6e2d310000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf2800000000000000206bae26026095fc80771f13b0230673ed4f8386ad7e9153b6e9636d2ae07c2f68
EPOCH_BINDING_SHA=9c86a3449a8c3666a9a77f838dd0c717c15c0e34ac1df89904b6cc87e8ae37ec
EPOCH_ID(93)=000000000000001a4e424630362d50524f56494445522d45504f43482d49442d56320000000000000008646565707365656b000000000000001a6f6d703a646565707365656b2f646565707365656b2d63686174000000000000000137
EPOCH_ID_SHA=540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28
EPOCH_ID_FIELDS=domain,family,normalized_spec,provider_epoch_generation; protocol epoch_version is codec/domain version; stable provider_epoch_generation is authoritative non-negative U64 identity material; admission_generation is reservation metadata and excluded; native proof_generation is separate liveness fencing evidence; route_liveness_identity/digest and provider_membership_snapshot_digest are fencing-only claim/binding fields, excluded from stable identity and failure-key preimage
EPOCH_ID_ENCODING=U64BE(length)||UTF-8/NFC for domain,family,normalized_spec,provider_epoch_generation; stable identity is raw32 SHA256(EPOCH_ID bytes); fencing evidence is separately raw32 and never substituted
The rename from bare `generation` is terminology-only: the existing EPOCH_ID
value bytes and SHA remain valid because the encoded U64 value is unchanged;
only dependent vectors whose ordered value bytes change may be regenerated.
EPOCH_PRODUCER=arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission supplies accepted reservation context → arnold_pipelines/megaplan/incident/ledger.py:bind_provider_epoch_locked (locked claim producer) → arnold_pipelines/megaplan/incident/ledger.py:repair_provider_epoch_binding_locked (locked binding CAS)
EPOCH_FENCE_RESULTS=bound|replaced|stale|pending|durability_unknown; replaced/stale/missing/forged hold with no route/probe/child/launch; pending permits only exact binding CAS; durability_unknown permits only exact replay/reconciliation
REFUSAL_ENCODING=U64BE(length)||UTF-8/NFC for non-null fields; each null is exactly U64BE(0) with no payload; fields are in REFUSAL_FIELDS order
REFUSAL(335)=00000000000000214e424630362d455845435554452d46414c4c4241434b2d5245465553414c2d56310000000000000001310000000000000007657865637574650000000000000006706c616e2d3100000000000000126c6f676963616c2d64697370617463682d310000000000000000000000000000002d6f6d703a646565707365656b2f646565707365656b2d636861742c6f6d703a6f70656e61692f6770742d352e3600000000000000013100000000000000013200000000000000126f6d703a6f70656e61692f6770742d352e3600000000000000154578656375746546616c6c6261636b556e73616665000000000000000e7072655f7265736f6c7574696f6e00000000000000067374617475730000000000000006736368656d6100000000000000066566666563740000000000000000000000000000000000000000000000000000000000000000
REFUSAL_SHA=01f1c6907bfbaf936f2e425d71edb4b87846e8c28e9c08fdad6c66565ca2aa3d
```

The lifecycle bridge is ordered and one-way: accepted admission/reservation creates the receipt and epoch claim; the adapter emits `PRECOMMIT_EVIDENCE` with no terminal, observation, event, or derived receipt IDs; an explicit `serialize_dispatch_outcome_precommit` adapter maps the live typed `DispatchOutcome` and re-encodes/retags it as `DISPATCH_OUTCOME`; the one locked NBF-01 terminal writer appends/replays the terminal before T8 selection, then the T8 observation/link applier commits its CAS and emits the postcommit `PROVIDER_ENVELOPE` with terminal/observation links. No postcommit ID participates in either precommit digest.

The bridge is deterministic against the live `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome`: `kind` maps to wire `result`; only `launch_state=accepted` enters precommit (not-started/ambiguous remain typed refusal/no-launch outcomes); `plan_id`, `phase`, `logical_dispatch_id`, and `admission_receipt_id` retain their names; `dispatch_family_id` is transport metadata and is ignored by NBF-06 wire encoding; `semantic_dispatch_fingerprint` maps to `fingerprint`; nested `provider_evidence.provider_epoch_identity`, `provider_failure_key`, `retryability_class`, and `provider_failure_class` map to epoch, raw32 key, retryability, and provider-class fields. The typed bridge re-encodes mapped fields under its own domain; only resulting bridge bytes are transported unchanged.

The complete live-field conversion is closed: `schema_version` is checked and
preserved as an adapter-version gate; `kind→result`, `launch_state`, `plan_id`,
`phase`, `logical_dispatch_id`, `admission_receipt_id`,
`semantic_dispatch_fingerprint→fingerprint`, and `selected_spec` are mapped;
`reservation_event_id` is not a live field and must come only from the accepted
`dispatch_with_admission` reservation context (missing or mismatched context
rejects). `provider_evidence.provider_failure_key` is authoritative; the
top-level `provider_failure_key` is a compatibility alias that may be omitted
but, if present, must match or reject. `retryability_class→retryability` is
the sole alias normalization; missing, unknown, or conflicting retryability
rejects. `worker_identity`, `provider`, route-liveness fields, timestamps,
success/terminal payloads, disposition, reconciliation ID, and terminal-event
ID are ignored for the precommit wire (postcommit IDs are never inferred).
Nullable staged IDs are `None` on the typed object and omitted on precommit
wire; explicit U64BE(0) null is used only for fields declared nullable by a
schema, such as configured chain identity. Non-accepted `not_started` and
ambiguous outcomes must remain typed refusal/no-launch results and cannot
bypass the adapter, create precommit evidence, resolve a target, or launch.

`arnold_pipelines/megaplan/incident/schema.py:ProviderFailureKey.derive` is
the sole failure-key producer: it calls the NBF-01 `_digest(canonical_json(material))`
codec, so the failure key is not a second U64BE event codec. The current
event/branch fixtures use the same framed serializer (the failure key is the
NBF-01 JSON exception) and these exact
ordered tuples, lengths, and full-payload hashes:

| ID/domain | Ordered sample fields | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| precommit adapter evidence `NBF06-PROVIDER-ADAPTER-EVIDENCE-PRECOMMIT-V1` (supersedes 363-byte vector) | outer fields plus one framed lossless `nested_provider_evidence`; no postcommit ledger IDs | 656 | `93abaf0c39d87ed58fd62c901f45e6d11320b139534dbfab26336f898b74cb25` |
| precommit `DispatchOutcome` bridge `NBF06-DISPATCH-OUTCOME-BRIDGE-V1` (supersedes 351-byte vector) | live typed fields mapped/re-encoded; nested evidence preserved as framed bytes; only resulting bridge bytes are byte-preserved | 644 | `71574e243d25afed41c8c2636968bc35c79b8a0d99f59f479f3f8e320fc40384` |
| postcommit provider envelope `NBF06-PROVIDER-EVIDENCE-ENVELOPE-V1` | precommit fields plus terminal/observation links; raw32 key/fingerprint/epoch; explicit-null chain | 393 | `e579db42c62a9e5560211193f45961b7325dd743c37040157577b255fa795363` |
| failure key `arnold_pipelines/megaplan/incident/schema.py:ProviderFailureKey.derive` | canonical JSON uses lowercase-hex display of source raw epoch `540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28`; digest is value field | 205 | `35f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c` |
| epoch identity `NBF06-PROVIDER-EPOCH-ID-V2` | domain,family,normalized_spec,provider_epoch_generation; liveness/membership are fencing-only evidence | 93 | `540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28` |
| epoch claim `NBF06-PROVIDER-EPOCH-CLAIM-V2` | version,identity(raw32),family,spec,liveness,liveness_digest,membership_digest,provider_epoch_generation,claim_digest | 280 | `f4028a7a2850021c459f64df2308423747a89e34ceb36fc6054d31a0352c594f` |
| epoch binding `NBF06-PROVIDER-EPOCH-BINDING-V2` | claim_digest,reservation,admission,identity(raw32),binding_digest | 199 | `9c86a3449a8c3666a9a77f838dd0c717c15c0e34ac1df89904b6cc87e8ae37ec` |
| observation `NBF06-PROVIDER-OBSERVATION-V2` | terminal,reservation,admission,configured_fallback_chain_identity(null),key(raw32),epoch(raw32),evidence(raw32),dispatch,result | 267 | `011d8fb2d42bf5ba0c27a18d64252aa999cf974b5efd3e403cdfa080b6216194` |
| hold `NBF06-PROVIDER-HOLD-V2` | terminal,observation,admission,configured_fallback_chain_identity(null),epoch(raw32),key(raw32),evidence(raw32),reason,state | 253 | `c272a82bd725258e5cac1568b0bae2a3d7de38ad6ba720165b21c9ddf3673ba2` |
| success `NBF06-PROVIDER-SUCCESS-V2` | terminal,observation,admission,configured_fallback_chain_identity(null),epoch(raw32),key(raw32),evidence(raw32),reason,state | 258 | `9571aa2db8a820be679cfbba40770007b3dec62ad1971747788997180ba6f71f` |
| child proposal `NBF06-PROVIDER-ROUTE-PROPOSAL-V2` | source links, configured_fallback_chain_identity(null), raw source/target key+epoch and claim/binding/proof digests, target index/family/spec, decision | 475 | `a0322ec6a5cf4b8c65a583c717e3b5e543c71a5a2775b503ce3e0d6c4f22c9c7` |
| child event `NBF06-PROVIDER-ROUTE-CHILD-EVENT-V2` | proposal_digest(raw32), source links, target fields; excludes decision, self/event identity, derived receipt | 475 | `ecf5bf5602f816752e27f7e921cd188acd236faf49f7b9c1d115c8456147c270` |
| child event identity `NBF06-PROVIDER-ROUTE-CHILD-ID-V2` | lowercase-hex SHA-256 of CHILD_EVENT bytes including proposal_digest; post-serialization assignment | 80 | `edbd1c4a77d3486893c9f4bed803356ecc23ea10e9852573449c2aa67d063e52` |
| child committed view `NBF06-PROVIDER-ROUTE-CHILD-COMMITTED-VIEW-V2` | own view domain, child fields, canonical event_id and derived receipt; never ledger event | 581 | `e406af5f60e6a75ac93c574bfaab12de0617ca5e791a67476bbc30c81f936257` |
| recovery branch `NBF06-PROVIDER-RECOVERY-VERIFIED-V2` | terminal, observation, lease, receipt, null chain, raw key/epoch/evidence/proof | 284 | `64f72fa89c6d7eb745e54466bb9d36e398730e85fa8437ca74c026dd0cd8d8b6` |
| configured branch `NBF06-PROVIDER-CONFIGURED-CHILD-PROPOSAL-V2` | source links, null chain, raw source/target key/epoch/claim/binding/proof, target index/family/spec, decision | 486 | `abdb020fa2498d4a8463356b0efb9009a15ea1ac948bb01133cc8cf2053ed148` |
| return branch `NBF06-PROVIDER-RETURN-PRIMARY-V3` | independent source/target receipt/key/epoch/claim/binding/proof; null chain | 510 | `f5e0cb4d2a2fcb0e7c90e9b805d8dd487fc222b355ad9f03cc5ff4ea33560056` |

Full current observation/hold/success literal payloads:

```text
OBSERVATION(267)=000000000000001d4e424630362d50524f56494445522d4f42534552564154494f4e2d5632000000000000000a7465726d696e616c2d31000000000000000d7265736572766174696f6e2d31000000000000000b61646d697373696f6e2d310000000000000000000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf2800000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000000a64697370617463682d31000000000000001270726f76696465725f657868617573746564
HOLD(253)=00000000000000164e424630362d50524f56494445522d484f4c442d5632000000000000000a7465726d696e616c2d31000000000000000d6f62736572766174696f6e2d31000000000000000b61646d697373696f6e2d3100000000000000000000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c00000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000001177616974696e675f666f725f70726f6265000000000000000468656c64
SUCCESS(258)=00000000000000194e424630362d50524f56494445522d535543434553532d5632000000000000000a7465726d696e616c2d31000000000000000d6f62736572766174696f6e2d31000000000000000b61646d697373696f6e2d3100000000000000000000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c00000000000000201111111111111111111111111111111111111111111111111111111111111111000000000000001070726f76696465725f73756363657373000000000000000773756363657373
```

### Current child and branch literal vectors

Each line below is an actual U64BE-framed payload; digests are raw 32-byte fields and all other fields are UTF-8/NFC text. These are the only current child/branch fixtures; old vectors are historical.

Exact tuple order for the bytes is fixed here: child proposal is `domain,source_reservation_event_id,source_admission_receipt_id,source_observation_id,configured_fallback_chain_identity(raw32-or-explicit-null),source_provider_failure_key,source_provider_epoch_identity(raw32),target_index,target_family,target_normalized_spec,target_provider_failure_key,target_provider_epoch_identity(raw32),target_epoch_claim_digest,target_epoch_binding_digest,target_admission_proof_digest,decision_kind`; child event is `domain,proposal_digest(raw32),source_reservation_event_id,source_admission_receipt_id,source_observation_id,configured_fallback_chain_identity(raw32-or-explicit-null),source_provider_failure_key,source_provider_epoch_identity(raw32),target_index,target_family,target_normalized_spec,target_provider_failure_key,target_provider_epoch_identity(raw32),target_epoch_claim_digest,target_epoch_binding_digest,target_admission_proof_digest`. Source links and the non-circular proposal digest are included; decision text, self/event identity, and derived receipt are excluded. The canonical ledger `event_id == child_reservation_event_id` is lowercase hex SHA-256 of those payload bytes, assigned after serialization and before append, and never included in them. The committed view uses its own `NBF06-PROVIDER-ROUTE-CHILD-COMMITTED-VIEW-V2` domain, those event fields, canonical `event_id`, then `child_admission_receipt_id`. Recovery and return fields use raw32 epoch identities; digest fields are raw32 and no child receipt is in the child event preimage.

```text
CHILD_PROPOSAL(475)=00000000000000204e424630362d50524f56494445522d524f5554452d50524f504f53414c2d5632000000000000000d7265736572766174696f6e2d31000000000000000b61646d697373696f6e2d31000000000000000d6f62736572766174696f6e2d320000000000000000000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000001310000000000000005636f646578000000000000000d636f6465783a6770742d352e360000000000000020dfee816bba50394763112667ab7e56da7fe567a33e2a97b99dcaaf7eca0ed96e000000000000002003d2b74947128e3da10aa9353e41f8dd3fcf6fc76c798eb67cbe8495da1919ea0000000000000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000000000000020bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb0000000000000020cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc0000000000000023506f73745465726d696e616c436f6e6669677572656446616c6c6261636b4368696c64
CHILD_PROPOSAL_SHA=a0322ec6a5cf4b8c65a583c717e3b5e543c71a5a2775b503ce3e0d6c4f22c9c7
CHILD_EVENT(475)=00000000000000234e424630362d50524f56494445522d524f5554452d4348494c442d4556454e542d56320000000000000020a0322ec6a5cf4b8c65a583c717e3b5e543c71a5a2775b503ce3e0d6c4f22c9c7000000000000000d7265736572766174696f6e2d31000000000000000b61646d697373696f6e2d31000000000000000d6f62736572766174696f6e2d320000000000000000000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000001310000000000000005636f646578000000000000000d636f6465783a6770742d352e360000000000000020dfee816bba50394763112667ab7e56da7fe567a33e2a97b99dcaaf7eca0ed96e000000000000002003d2b74947128e3da10aa9353e41f8dd3fcf6fc76c798eb67cbe8495da1919ea0000000000000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000000000000020bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb0000000000000020cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
CHILD_EVENT_SHA=ecf5bf5602f816752e27f7e921cd188acd236faf49f7b9c1d115c8456147c270
CHILD_VIEW(581)=000000000000002c4e424630362d50524f56494445522d524f5554452d4348494c442d434f4d4d49545445442d564945572d56320000000000000020a0322ec6a5cf4b8c65a583c717e3b5e543c71a5a2775b503ce3e0d6c4f22c9c7000000000000000d7265736572766174696f6e2d31000000000000000b61646d697373696f6e2d31000000000000000d6f62736572766174696f6e2d320000000000000000000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000001310000000000000005636f646578000000000000000d636f6465783a6770742d352e360000000000000020dfee816bba50394763112667ab7e56da7fe567a33e2a97b99dcaaf7eca0ed96e000000000000002003d2b74947128e3da10aa9353e41f8dd3fcf6fc76c798eb67cbe8495da1919ea0000000000000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000000000000020bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb0000000000000020cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc00000000000000403035303265383036623565346161353066623337323931383531666534666464626335373533376232653638353231316465626633623136633838666461316100000000000000116368696c642d61646d697373696f6e2d31
CHILD_VIEW_SHA=e406af5f60e6a75ac93c574bfaab12de0617ca5e791a67476bbc30c81f936257
CHILD_EVENT_ID_FORMULA=lowercase_hex(SHA256(CHILD_EVENT_BYTES)); event_id is assigned from this digest before append; it is excluded from CHILD_EVENT_BYTES
CHILD_ID(80)=00000000000000204e424630362d50524f56494445522d524f5554452d4348494c442d49442d56320000000000000020ecf5bf5602f816752e27f7e921cd188acd236faf49f7b9c1d115c8456147c270
CHILD_ID_SHA=edbd1c4a77d3486893c9f4bed803356ecc23ea10e9852573449c2aa67d063e52
RECOVERY(284)=00000000000000234e424630362d50524f56494445522d5245434f564552592d56455249464945442d5632000000000000000a7465726d696e616c2d31000000000000000d6f62736572766174696f6e2d3100000000000000076c656173652d31000000000000000b61646d697373696f6e2d310000000000000000000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002011111111111111111111111111111111111111111111111111111111111111110000000000000020cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
RECOVERY_SHA=64f72fa89c6d7eb745e54466bb9d36e398730e85fa8437ca74c026dd0cd8d8b6
CONFIGURED(486)=000000000000002b4e424630362d50524f56494445522d434f4e464947555245442d4348494c442d50524f504f53414c2d5632000000000000000d7265736572766174696f6e2d31000000000000000b61646d697373696f6e2d31000000000000000d6f62736572766174696f6e2d320000000000000000000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000001310000000000000005636f646578000000000000000d636f6465783a6770742d352e360000000000000020dfee816bba50394763112667ab7e56da7fe567a33e2a97b99dcaaf7eca0ed96e000000000000002003d2b74947128e3da10aa9353e41f8dd3fcf6fc76c798eb67cbe8495da1919ea0000000000000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000000000000020bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb0000000000000020cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc0000000000000023506f73745465726d696e616c436f6e6669677572656446616c6c6261636b4368696c64
CONFIGURED_SHA=abdb020fa2498d4a8463356b0efb9009a15ea1ac948bb01133cc8cf2053ed148
RETURN(510)=00000000000000204e424630362d50524f56494445522d52455455524e2d5052494d4152592d5633000000000000000a7465726d696e616c2d31000000000000000d6f62736572766174696f6e2d31000000000000000b61646d697373696f6e2d310000000000000000000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000008646565707365656b000000000000001a6f6d703a646565707365656b2f646565707365656b2d636861740000000000000005636f646578000000000000000d636f6465783a6770742d352e360000000000000020dfee816bba50394763112667ab7e56da7fe567a33e2a97b99dcaaf7eca0ed96e000000000000002003d2b74947128e3da10aa9353e41f8dd3fcf6fc76c798eb67cbe8495da1919ea0000000000000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000000000000020bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb0000000000000020cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc0000000000000020dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
RETURN_SHA=f5e0cb4d2a2fcb0e7c90e9b805d8dd487fc222b355ad9f03cc5ff4ea33560056
```

## Round-21 transition fixture registry

The following literal fixtures close the pending, reconciled, probe, and
durability-unknown transitions. Text fields are U64BE(length)||UTF-8/NFC;
digests are raw 32-byte fields; absent chain identity is explicit null.

```text
PENDING(148)=000000000000002a4e424630362d50524f56494445522d4f42534552564154494f4e2d4c494e4b2d50454e44494e472d5632000000000000000a7465726d696e616c2d31000000000000000d7265736572766174696f6e2d31000000000000000b61646d697373696f6e2d3100000000000000201111111111111111111111111111111111111111111111111111111111111111
PENDING_SHA=d74235049b9203ff3e61a735e5c9692a3d481a1b0edd22dd298473c0515b5cbb
PENDING_FIELDS=domain,terminal_event_id,reservation_event_id,admission_receipt_id,evidence_digest(raw32); SHA256=d74235049b9203ff3e61a735e5c9692a3d481a1b0edd22dd298473c0515b5cbb
RECONCILED(266)=00000000000000284e424630362d50524f56494445522d4f42534552564154494f4e2d5245434f4e43494c45442d56320000000000000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa000000000000000a7465726d696e616c2d31000000000000000d6f62736572766174696f6e2d31000000000000000b61646d697373696f6e2d31000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf2800000000000000201111111111111111111111111111111111111111111111111111111111111111
RECONCILED_SHA=28496dac6588069eb019f6e857c86b469484a723cea13d358919c90b071cf3cf
RECONCILED_FIELDS=domain,legacy_event_digest(raw32),terminal_event_id,observation_id,admission_receipt_id,provider_failure_key(raw32),provider_epoch_identity(raw32),evidence_digest(raw32); SHA256=28496dac6588069eb019f6e857c86b469484a723cea13d358919c90b071cf3cf
PROBE_START(201)=000000000000001d4e424630362d50524f56494445522d50524f42452d53544152542d5632000000000000000d6f62736572766174696f6e2d31000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000007726f7574652d31000000000000001072657472795f6e6f745f6265666f726500000000000000013100000000000000076c656173652d31
PROBE_START_SHA=d8054a0fefdc74ffff97781446d68fc170a6f2af91a572905f5ba5f0040676f4
PROBE_START_FIELDS=domain,observation_id,provider_failure_key(raw32),provider_epoch_identity(raw32),route_liveness_identity,retry_not_before,attempt,probe_lease_id; SHA256=d8054a0fefdc74ffff97781446d68fc170a6f2af91a572905f5ba5f0040676f4
PROBE_RESULT(250)=000000000000001e4e424630362d50524f56494445522d50524f42452d524553554c542d563200000000000000076c656173652d31000000000000000d6f62736572766174696f6e2d31000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf280000000000000007726f7574652d31000000000000000a6578656375746f722d3100000000000000067061737365640000000000000001310000000000000020cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
PROBE_RESULT_SHA=ab39697a711bd43a5c8db807521bf1266ce31d5a1fa6e8e3f3d5595d0492a30e
PROBE_RESULT_FIELDS=domain,probe_lease_id,observation_id,provider_failure_key(raw32),provider_epoch_identity(raw32),route_liveness_identity,executor_id,result,attempt,evidence_digest(raw32); SHA256=ab39697a711bd43a5c8db807521bf1266ce31d5a1fa6e8e3f3d5595d0492a30e
PROBE_CLOSED(117)=000000000000001e4e424630362d50524f56494445522d50524f42452d434c4f5345442d563200000000000000076c656173652d31000000000000000d6f62736572766174696f6e2d3100000000000000067061737365640000000000000006706173736564000000000000000772657472792d32
PROBE_CLOSED_SHA=6ae9a2be782658def534025342edf8e1853e37f31931fe7fdedc6b092f7a43cc
PROBE_CLOSED_FIELDS=domain,probe_lease_id,observation_id,result,close_reason,next_retry_boundary; SHA256=6ae9a2be782658def534025342edf8e1853e37f31931fe7fdedc6b092f7a43cc
UNKNOWN(189)=00000000000000244e424630362d50524f56494445522d4455524142494c4954592d554e4b4e4f574e2d56320000000000000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa000000000000000a7465726d696e616c2d31000000000000000d6f62736572766174696f6e2d3100000000000000126475726162696c6974795f756e6b6e6f776e0000000000000020bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
UNKNOWN_SHA=6a700ce3c087b32546db3caf9e6005555556a29bbf2afdb9b7b52edc52909522
UNKNOWN_FIELDS=domain,source_event_digest(raw32),terminal_event_id,observation_id,reason,raw_payload_digest(raw32); SHA256=6a700ce3c087b32546db3caf9e6005555556a29bbf2afdb9b7b52edc52909522
```

Probe timing is a pure contract over existing fields, not a new state or
constant. `retry_not_before` and `deadline` are unsigned integer nanoseconds
from the injected `MonotonicClock.now_ns()`; UTC timestamps are evidence-only.
The derived boundary is
`retry_not_before_ns=max(parent_retry_not_before_ns,terminal_observed_ns)` and
the executor lease uses its supplied `deadline_ns`, requiring
`deadline_ns >= retry_not_before_ns`. Reconciliation takes the ledger lock,
checks lease/parent/key/epoch/route/attempt fence, returns an existing closed
record for an idempotent duplicate, otherwise applies explicit result before
expiry, and closes expired/late results at inclusive `now_ns >= deadline_ns`.
Unknown closes to held/unresolved (`probe_status=failed`) without streak or
retry mutation; only exact byte reconciliation may resolve it. No result or
closure authorizes a child directly.

```text
PROBE_BOUNDARY_FIXTURES=before_eligibility(now_ns=99,retry_not_before_ns=100,deadline_ns=200)->held/no_lease;at_eligibility(now_ns=100,retry_not_before_ns=100,deadline_ns=200)->one_lease_CAS;before_expiry(now_ns=199,deadline_ns=200)->result_accepted;at_expiry(now_ns=200,deadline_ns=200)->expired_close/no_launch;unknown(now_ns=150)->durability-held/no_retry;late(now_ns=201)->held-unresolved/no_write;rollback(now_ns=90,prior_now_ns=100)->held/no_authorization
PROBE_RECONCILIATION_PRECEDENCE=lease_fence>duplicate_closed_replay>explicit_result_if_now<deadline>inclusive_expiry_if_now>=deadline>unknown_or_conflict_held; passed_requires_close_CAS_then_recovery_consume; failed|expired|unknown never launch
```

## Migration, transitions, and the A01–A38 registry

| Input | File-qualified codec/inverse | Null/unknown/upgrade/replay |
| --- | --- | --- |
| legacy `DispatchOutcome` V1 | `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome.to_dict` ↔ `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome.from_dict` → `arnold_pipelines/megaplan/incident/schema.py:serialize_dispatch_outcome_precommit` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_dispatch_outcome_precommit` → one `serialize_provider_adapter_evidence_precommit` handoff | `to_dict/from_dict` is lossless live-object compatibility; bridge maps/re-encodes `kind→result`, `launch_state=accepted` eligibility, same-named plan/phase/dispatch/logical/admission fields, reservation from accepted admission context (inverse requires that context and rejects missing/mismatch), `semantic_dispatch_fingerprint→fingerprint`, and nested provider evidence to epoch/raw32 key/retryability/provider class; typed staged IDs remain `None` but are omitted on precommit wire; unknown fields reject; JSON/byte replay exact |
| ordinary legacy `event_type=worker_terminal_outcome` / NBF-01 `schema_version=1` | `arnold_pipelines/megaplan/incident/schema.py:serialize_worker_terminal_outcome` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_worker_terminal_outcome` | retain the NBF-01 ordinary `worker_terminal_outcome` domain/version and codec; map fields byte-for-byte; omission differs from explicit null; unknown rejects; never provider-upgrade; replay exact |
| V1 provider precommit / `NBF06-PROVIDER-ADAPTER-EVIDENCE-PRECOMMIT-V1` | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_adapter_evidence_precommit` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_adapter_evidence_precommit` | exact `PRECOMMIT_EVIDENCE_FIELDS`; postcommit IDs are omitted from wire (typed object may hold nullable staged IDs); unknown rejects; no-upgrade; bytes replay exact |
| V1 accepted terminal / `NBF06-PROVIDER-TERMINAL-V1` | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_terminal` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_terminal` | terminal domain/version; receipt/claim parent equality; terminal ID assigned postcommit and excluded from preimage; unknown rejects; replay/CAS idempotent |
| provider envelope V1 / `NBF06-PROVIDER-EVIDENCE-ENVELOPE-V1` | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_evidence` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_evidence` | exact envelope fields with terminal/observation linkage populated only postcommit; raw32 chain/key fields or explicit null; unknown rejects; replay/CAS idempotent |
| admission receipt V1 | `arnold_pipelines/megaplan/incident/schema.py:serialize_worker_admission_receipt` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_worker_admission_receipt` | NBF-01 owns receipt bytes/ID; chain extension raw32-or-explicit-null; NBF-02 consumes; cloud transports bytes only; omission/null preserved; replay exact |
| child event V2 / `NBF06-PROVIDER-ROUTE-CHILD-EVENT-V2` | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_event` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_route_child_event` | proposal digest(raw32) binds the explicit decision/proposal; source links included; decision text, self/event identity, and derived child receipt excluded; unknown rejects; CAS/replay exact |
| child committed view V2 / `NBF06-PROVIDER-ROUTE-CHILD-COMMITTED-VIEW-V2` | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_view` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_route_child_view` | postcommit view only; canonical event ID and derived receipt populated after append; never ledger event; unknown rejects; replay exact |
| legacy provider terminal | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_terminal` ↔ `serialize_legacy_provider_terminal` | map `event_id,plan,phase,logical_dispatch_id,provider_failure_class,provider_epoch_identity`; absent provider fields are explicit `null`; unknown fields reject; ordinary records never upgrade; replay compares legacy bytes |
| legacy provider observation | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_observation` ↔ `serialize_legacy_provider_observation` | map terminal/receipt/key/epoch/evidence/count fields; missing derived IDs remain `null`; no inferred count; torn/conflict held |
| legacy provider hold/success | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_hold_success` ↔ `serialize_legacy_provider_hold_success` | map exact parent key/epoch and state; omission is not `null`; no provider upgrade; replay byte-identical |
| legacy recovery evidence | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_recovery` ↔ `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_recovery` | explicit legacy version/nulls; byte-preserving decode/re-encode; read/repair evidence only; no V1 upgrade or inferred proof |
| V2 recovery verified / `NBF06-PROVIDER-RECOVERY-VERIFIED-V2` | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_recovery_verified` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_recovery_verified` | exact passed-and-closed lease plus all parent/evidence fields required; raw32 chain/key/proof or explicit null; unknown/torn → held/unresolved; no-upgrade; replay/CAS idempotent |
| V2 recovery → canonical changed precondition | `arnold_pipelines/megaplan/incident/schema.py:produce_provider_recovery_verified` → `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_changed_precondition` ↔ `consume_changed_precondition` | V2 is evidence transport only; typed producer derives equal before/after failure keys and content/evidence digests; append once, child consumes once through authorizing/consumed IDs; decoder cannot mint; open/uncommitted/conflicting/cyclic proof rejects |
| torn/unknown/ambiguous V2 / `NBF06-PROVIDER-DURABILITY-UNKNOWN-V2` | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_durability_unknown` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_durability_unknown` | raw payload digest and parent IDs only; unknown remains held; no inverse allocation/upgrade; byte replay or explicit conflict |

| Transition ID | Preconditions | Durable result | Forbidden consequence |
| --- | --- | --- | --- |
| `provider_terminal_committed` / V1 / `NBF06-PROVIDER-TERMINAL-V1` | accepted structured evidence | one terminal | no observation in terminal preimage |
| `provider_observation_link_pending` / V2 / `NBF06-PROVIDER-OBSERVATION-LINK-PENDING-V2` | terminal; fixture `PENDING` (148 bytes, SHA `d74235049b9203ff3e61a735e5c9692a3d481a1b0edd22dd298473c0515b5cbb`) | link intent | no route/launch |
| `provider_observation_committed` / V2 / `NBF06-PROVIDER-OBSERVATION-V2` | exact terminal/receipt/evidence | one count input | no duplicate count |
| `provider_observation_reconciled` / V2 / `NBF06-PROVIDER-OBSERVATION-RECONCILED-V2` | exact stored bytes; fixture `RECONCILED` (266 bytes, SHA `28496dac6588069eb019f6e857c86b469484a723cea13d358919c90b071cf3cf`) | idempotent repair | no inferred IDs |
| `provider_hold_committed` / V2 / `NBF06-PROVIDER-HOLD-V2` | first matching exhaustion | held/streak one | zero-count child |
| `provider_probe_started` / V2 / `NBF06-PROVIDER-PROBE-START-V2` | deadline + one CAS lease; fixture `PROBE_START` (201 bytes, SHA `d8054a0fefdc74ffff97781446d68fc170a6f2af91a572905f5ba5f0040676f4`) | leased projection | no worker launch |
| `provider_probe_result` / V2 / `NBF06-PROVIDER-PROBE-RESULT-V2` | fenced executor result; fixture `PROBE_RESULT` (250 bytes, SHA `ab39697a711bd43a5c8db807521bf1266ce31d5a1fa6e8e3f3d5595d0492a30e`) | passed/failed/unknown | unknown cannot route |
| `provider_probe_closed` / V2 / `NBF06-PROVIDER-PROBE-CLOSED-V2` | result/expiry; fixture `PROBE_CLOSED` (117 bytes, SHA `6ae9a2be782658def534025342edf8e1853e37f31931fe7fdedc6b092f7a43cc`) | closed lease | no attempt 3 |
| `provider_recovery_verified` / V2 / `NBF06-PROVIDER-RECOVERY-VERIFIED-V2` | passed result whose exact lease has first been closed by `close_provider_probe_locked`; closed result, lease, parent, key, epoch, route, and evidence bind; then canonical `ChangedPrecondition` is produced/committed | one versioned proof, fixture `RECOVERY`, plus one NBF-01 changed-precondition append | passed-but-open, uncommitted, failed, expired, unknown, duplicate, or late result cannot recover/route/launch; replay same proof; child requires consumed canonical event |
| `provider_route_child_reserved` / V2 / `NBF06-PROVIDER-ROUTE-CHILD-EVENT-V2` | locked composite door | `CHILD_EVENT` (475 bytes, SHA `ecf5bf5602f816752e27f7e921cd188acd236faf49f7b9c1d115c8456147c270`) without derived receipt, then `CHILD_VIEW` (581 bytes, SHA `e406af5f60e6a75ac93c574bfaab12de0617ca5e791a67476bbc30c81f936257`) with canonical event_id and receipt | receipt-bearing event rejected |
| `provider_success_committed` / V2 / `NBF06-PROVIDER-SUCCESS-V2` | exact parent | matching-key reset | no observation/child |
| `provider_durability_unknown` / V2 / `NBF06-PROVIDER-DURABILITY-UNKNOWN-V2` | torn/unknown; fixture `UNKNOWN` (189 bytes, SHA `6a700ce3c087b32546db3caf9e6005555556a29bbf2afdb9b7b52edc52909522`) | held/reconcilable | no launch/signal |
| `configured_chain_refusal` / V1 / `NBF06-EXECUTE-FALLBACK-REFUSAL-V1` | malformed/cross-family/unsafe | typed refusal | no second target |
| `provider_return_primary` / V3 / `NBF06-PROVIDER-RETURN-PRIMARY-V3` | exact source terminal/observation/receipt/key/epoch and independent target family/spec/key/epoch claim/binding/admission proof; fixture `RETURN` (510 bytes, SHA `f5e0cb4d2a2fcb0e7c90e9b805d8dd487fc222b355ad9f03cc5ff4ea33560056`) | one return | no source identity inherited as target; no historical widening |

Each node below is stable and each command is exact, independent, and
fail-fast. Existing related tests are supplemental, never aliases.

The compact state table above is expanded by this closed serialization
registry. Every ID uses `SHA256(domain || U64BE(field)...)`; `event_id`,
wall-clock timestamps, caller prose, and derived postcommit IDs are excluded
unless explicitly listed. Parent bindings are equality checks under the same
ledger lock. A matching payload returns the prior record; a CAS loser returns
that record; a byte conflict/torn append becomes `durability_unknown` and
blocks route/launch until reconciliation.

| ID / version / domain | Ordered preimage fields and exclusions | Producer → sole writer | Parent binding / replay / fixture |
| --- | --- | --- | --- |
| `provider_terminal_committed` / V1 / `NBF06-PROVIDER-TERMINAL-V1` | nested extension of canonical `worker_terminal_outcome`: plan, phase, logical dispatch, admission receipt, reservation, configured_fallback_chain_identity raw32-or-explicit-null, fingerprint raw32, selected spec, provider_epoch_identity raw32, failure key, retryability, provider class; excludes terminal/observation IDs and time | adapter → `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` (sole physical writer); `record_provider_terminal_with_observation_locked` is a delegating locked adapter only | accepted reservation/claim equality; one terminal, replay exact; `PRECOMMIT_EVIDENCE` → `PROVIDER_ENVELOPE` |
| `provider_observation_link_pending` / V2 / `NBF06-PROVIDER-OBSERVATION-LINK-PENDING-V2` | terminal, reservation, receipt, evidence digest; excludes observation ID | sole terminal writer → `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` / repair link | exact terminal; pending is no-route; CAS/replay exact; `PENDING` (148, `d74235049b9203ff3e61a735e5c9692a3d481a1b0edd22dd298473c0515b5cbb`) |
| `provider_observation_committed` / V2 / `NBF06-PROVIDER-OBSERVATION-V2` | domain, terminal, reservation, admission, configured_fallback_chain_identity raw32-or-explicit-null, key raw32, epoch, evidence raw32, logical dispatch, result; excludes event/observation ID and time | atomic terminal writer → observation link writer | terminal/evidence/receipt/key/epoch equality; one count; `OBSERVATION` |
| `provider_observation_reconciled` / V2 / `NBF06-PROVIDER-OBSERVATION-RECONCILED-V2` | legacy event digest, terminal, observation, receipt, key, raw32 epoch, evidence; excludes new IDs/time | locked repair → `reconcile_provider_observation_locked` | pre-existing terminal/link required; idempotent or conflict hold; `RECONCILED` (266, `28496dac6588069eb019f6e857c86b469484a723cea13d358919c90b071cf3cf`) |
| `provider_hold_committed` / V2 / `NBF06-PROVIDER-HOLD-V2` | terminal, observation, admission, configured_fallback_chain_identity raw32-or-explicit-null, epoch, key raw32, evidence raw32, reason, state; excludes hold ID/time | policy → `record_provider_hold_locked` | exact observation/key/epoch; zero count/child; `HOLD` |
| `provider_probe_started` / V2 / `NBF06-PROVIDER-PROBE-START-V2` | parent, key, raw32 epoch, route, retry deadline, attempt number, lease ID; excludes executor result/time sample | `select_provider_probe` → `start_provider_probe_locked` | injected clock must satisfy `now >= retry_not_before`; one active parent/key/epoch/route lease; CAS loser replay; `PROBE_START` (201, `d8054a0fefdc74ffff97781446d68fc170a6f2af91a572905f5ba5f0040676f4`) |
| `provider_probe_result` / V2 / `NBF06-PROVIDER-PROBE-RESULT-V2` | lease, parent, key, raw32 epoch, route, executor ID, result, attempt, evidence; excludes live recomputation | `ProbeExecutor.run` → `record_provider_probe_result_locked` | lease/start identity equality; unknown is held/unresolved and cannot route; replay exact; `PROBE_RESULT` (250, `ab39697a711bd43a5c8db807521bf1266ce31d5a1fa6e8e3f3d5595d0492a30e`) |
| `provider_probe_closed` / V2 / `NBF06-PROVIDER-PROBE-CLOSED-V2` | lease, parent, result, close reason, next retry boundary; excludes new attempt ID | `close_provider_probe_locked` | exact lease; failed/expired/unknown closes once and maps to held/unresolved `failed`; no attempt 3; `PROBE_CLOSED` (117, `6ae9a2be782658def534025342edf8e1853e37f31931fe7fdedc6b092f7a43cc`) |
| `provider_recovery_verified` / V2 / `NBF06-PROVIDER-RECOVERY-VERIFIED-V2` | terminal, observation, **closed** probe lease/result, admission, configured_fallback_chain_identity raw32-or-explicit-null, key raw32, epoch, evidence raw32, recovery proof raw32; excludes child receipt/ID | passed close CAS → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_recovery_verified_locked` | exact single-use passed-and-closed lease and parent; replay same proof; child reservation is forbidden until this proof commits; `RECOVERY` |
| `provider_route_child_reserved` / V2 / `NBF06-PROVIDER-ROUTE-CHILD-EVENT-V2` | proposal_digest raw32, source reservation/receipt/observation, explicit-null chain, raw source/target key/epoch claim+binding/proof digests, target index/family/spec; recovery child additionally requires committed `provider_recovery_verified` from a passed-and-closed lease; decision text, canonical event_id/self identity, and derived child receipt excluded | pure selector → `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` (sole route-transition writer) | source/target admission/CAS equality; proposal digest binds decision; CHILD_EVENT has no receipt/self-ID; append/CAS/replay returns same event; unclosed/duplicate/foreign recovery proof rejects |
| `provider_route_child_committed_view` / V2 / `NBF06-PROVIDER-ROUTE-CHILD-COMMITTED-VIEW-V2` | own view domain, child event fields plus derived child receipt | locked reservation owner → postcommit view/`arnold_pipelines/megaplan/incident/ledger.py:derive_receipt` | CHILD_EVENT contains no receipt or event_id; CHILD_VIEW gets canonical event_id and receipt only after locked append+derivation; `CHILD_VIEW` |
| `provider_success_committed` / V2 / `NBF06-PROVIDER-SUCCESS-V2` | terminal, observation, admission, configured_fallback_chain_identity raw32-or-explicit-null, epoch, key raw32, evidence raw32, reason, state; excludes observation/child creation | adapter → `record_provider_success_locked` | exact parent/key; matching-key reset only; `SUCCESS` |
| `configured_chain_refusal` / V1 / `NBF06-EXECUTE-FALLBACK-REFUSAL-V1` | domain, version, phase, plan, logical dispatch, configured_fallback_chain_identity(raw32-or-explicit-null), configured specs, attempted index/total, selected spec, cause, boundary, status/schema/effect, explicit null receipt/fingerprint/client/worker fields | `fallback_chains.py:ExecuteFallbackUnsafe` → execute/fanout/loop transport | no reservation/launch; replay exact; `REFUSAL` |
| `provider_return_primary` / V3 / `NBF06-PROVIDER-RETURN-PRIMARY-V3` | source terminal, observation, admission receipt, explicit-null chain, source key/epoch/family/spec; independent target family/primary spec/key/epoch claim/binding/admission proof; return proof; all digests raw32 | pure selector → locked composite applier/`arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` | source-target equality under one lock; reject inherited source claim/key/epoch; one return; `RETURN` |
| `provider_durability_unknown` / V2 / `NBF06-PROVIDER-DURABILITY-UNKNOWN-V2` | failed operation domain, source event digest, parent IDs, reason, raw payload digest; excludes inferred IDs | ledger recovery → named reconcile method | no route/launch; permanent hold or exact repair; `UNKNOWN` (189, `6a700ce3c087b32546db3caf9e6005555556a29bbf2afdb9b7b52edc52909522`) |

Probe close/recovery rejection vectors are explicit: a passed result with an
open lease is held and cannot produce recovery; a duplicate close returns the
existing close event without a second proof; a late or foreign result fails the
lease/parent/key/epoch/route fence; unknown or expired closure maps to held /
unresolved `failed`; and no rejected case may route, launch, allocate a child,
or mutate the streak. Only the exact passed close CAS may feed the recovery
proof, and only a committed proof may feed the child reservation CAS.

Target-key derivation is canonical and independently replayable: the target
fixture uses sorted JSON bytes
`{"phase":"run","provider_epoch_identity":"03d2b74947128e3da10aa9353e41f8dd3fcf6fc76c798eb67cbe8495da1919ea","provider_failure_class":"availability","selected_spec":"codex:gpt-5.6","version":1}`;
`SHA256` of those 192 UTF-8 bytes is the raw target key
`dfee816bba50394763112667ab7e56da7fe567a33e2a97b99dcaaf7eca0ed96e`.


| ID | Frozen requirement | Stable node | Exact command | Risk |
| --- | --- | --- | --- | --- |
| NBF06-A01 | One accepted exhausted dispatch emits exactly one terminal and observation. | `test_accepted_exhaustion_emits_one_terminal_and_observation` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_accepted_exhaustion_emits_one_terminal_and_observation` | high |
| NBF06-A02 | Only accepted exhaustion advances the streak. | `test_only_accepted_exhaustion_advances_streak` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_only_accepted_exhaustion_advances_streak` | high |
| NBF06-A03 | Internal retry chatter deduplicates. | `test_internal_retry_chatter_deduplicates_observation` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_internal_retry_chatter_deduplicates_observation` | high |
| NBF06-A04 | Exhaustion is not ordinary failure. | `test_exhaustion_is_not_ordinary_failure` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_exhaustion_is_not_ordinary_failure` | high |
| NBF06-A05 | Non-T8/auth/quota/rate-limit classes remain ordinary; only availability/idle_timeout exhausts. | `test_non_exhaustion_typed_errors_stay_ordinary` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_non_exhaustion_typed_errors_stay_ordinary` | high |
| NBF06-A06 | Worker disposition never degrades provider. | `test_worker_disposition_never_degrades_provider` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_worker_disposition_never_degrades_provider` | high |
| NBF06-A07 | Stderr alone never drives policy. | `test_stderr_only_cannot_emit_provider_exhaustion` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_stderr_only_cannot_emit_provider_exhaustion` | high |
| NBF06-A08 | First exhaustion holds/streaks one; one deadline-gated lease. | `test_first_matching_exhaustion_holds_at_streak_one` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_first_matching_exhaustion_holds_at_streak_one` | high |
| NBF06-A09 | Volatile changes/probe success cannot reset or authorize identical retry. | `test_volatile_changes_cannot_authorize_or_reset` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_volatile_changes_cannot_authorize_or_reset` | high |
| NBF06-A10 | One active probe lease; failed probe is no-launch. | `test_probe_lease_is_single_and_failed_probe_is_no_launch` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_probe_lease_is_single_and_failed_probe_is_no_launch` | high |
| NBF06-A11 | Passed probe preserves key/streak and yields recovery evidence. | `test_passed_probe_preserves_key_and_streak` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_passed_probe_preserves_key_and_streak` | high |
| NBF06-A12 | One recovery proof authorizes one same-route child. | `test_recovery_verified_authorizes_one_same_route_child` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_recovery_verified_authorizes_one_same_route_child` | high |
| NBF06-A13 | Recovery create/consume preserves streak. | `test_recovery_create_consume_replays_streak_one` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_recovery_create_consume_replays_streak_one` | high |
| NBF06-A14 | Forged precondition/key transitions reject. | `test_t8_rejects_forged_precondition_and_key_transition` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_t8_rejects_forged_precondition_and_key_transition` | high |
| NBF06-A15 | Unresolved/no-launch parent creates no child. | `test_unresolved_or_no_launch_parent_creates_no_child` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_unresolved_or_no_launch_parent_creates_no_child` | high |
| NBF06-A16 | Authorized child exhaustion is observation two. | `test_authorized_child_matching_exhaustion_is_observation_two` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_authorized_child_matching_exhaustion_is_observation_two` | high |
| NBF06-A17 | Accepted success resets applicable streak/key. | `test_accepted_worker_success_resets_applicable_streak` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_accepted_worker_success_resets_applicable_streak` | medium |
| NBF06-A18 | Different-key exhaustion rekeys at one. | `test_different_key_exhaustion_rekeys_at_one` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_different_key_exhaustion_rekeys_at_one` | medium |
| NBF06-A19 | Ordinary failure/disposition breaks without degradation. | `test_ordinary_failure_or_disposition_breaks_without_degradation` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_ordinary_failure_or_disposition_breaks_without_degradation` | high |
| NBF06-A20 | Only authoritative key change rekeys. | `test_changed_precondition_rekeys_only_when_key_changes` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_changed_precondition_rekeys_only_when_key_changes` | high |
| NBF06-A21 | Key-preserving redispatch preserves observations. | `test_key_preserving_redispatch_preserves_observations` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_key_preserving_redispatch_preserves_observations` | high |
| NBF06-A22 | Key is phase/spec/class/authoritative epoch; volatile fields excluded. | `test_provider_failure_key_uses_only_canonical_fields` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_provider_failure_key_uses_only_canonical_fields` | high |
| NBF06-A23 | One strict configured-chain door; scalar suppresses ambient fallback. | `test_configured_chain_is_single_strict_selection_door` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_configured_chain_is_single_strict_selection_door` | high |
| NBF06-A24 | Fallback/return targets use canonical joint admission. | `test_dispatch_with_admission_validates_fallback_and_return_targets` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_dispatch_with_admission_validates_fallback_and_return_targets` | high |
| NBF06-A25 | Rejected targets cause zero transition/reservation/receipt/WBC/client/RPC/worker effects. | `test_rejected_target_has_zero_second_resolution_client_wbc_rpc_worker_effects` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_rejected_target_has_zero_second_resolution_client_wbc_rpc_worker_effects` | high |
| NBF06-A26 | Flip/return use one composite child event. | `test_flip_and_return_use_one_composite_route_event` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_flip_and_return_use_one_composite_route_event` | high |
| NBF06-A27 | Child receipt is postcommit and replay-identical. | `test_child_receipt_is_post_commit_and_replay_identical` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_child_receipt_is_post_commit_and_replay_identical` | high |
| NBF06-A28 | Target supplies its own epoch/key; no source inheritance. | `test_route_target_epoch_and_key_are_isolated_from_source` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_route_target_epoch_and_key_are_isolated_from_source` | high |
| NBF06-A29 | Scalar pin never widens to historical route. | `test_scalar_pin_does_not_widen_to_historical_route` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_scalar_pin_does_not_widen_to_historical_route` | high |
| NBF06-A30 | Scheduling bypasses breaker and blocked accounting. | `test_provider_scheduling_never_enters_breaker_or_blocked` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_provider_scheduling_never_enters_breaker_or_blocked` | high |
| NBF06-A31 | Genuine internal errors retain ordinary breaker behavior. | `test_repeated_internal_errors_retain_breaker_behavior` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_repeated_internal_errors_retain_breaker_behavior` | medium |
| NBF06-A32 | Batch, fanout, and direct loop never advance execute fallback; refusal is pre-side-effect. | `test_execute_and_loop_execute_fallback_are_typed_pre_side_effect_refusals` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_execute_and_loop_execute_fallback_are_typed_pre_side_effect_refusals` | high |
| NBF06-A33 | Crash/two-process races yield one route/observation/streak/lease and at most one child. | `test_two_process_observation_lease_recovery_child_races_are_idempotent` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_two_process_observation_lease_recovery_child_races_are_idempotent` | high |
| NBF06-A34 | Fresh-ledger replay preserves streak one through probe/recovery. | `test_fresh_ledger_replay_preserves_streak_one_through_recovery` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_fresh_ledger_replay_preserves_streak_one_through_recovery` | high |
| NBF06-A35 | Only authorized child outcome mutates streak. | `test_unauthorized_child_and_foreign_replay_cannot_mutate_streak` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_unauthorized_child_and_foreign_replay_cannot_mutate_streak` | high |
| NBF06-A36 | Unresolved reservations block route advance. | `test_unresolved_reservation_blocks_provider_route_advance` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_unresolved_reservation_blocks_provider_route_advance` | high |
| NBF06-A37 | Lost/mismatched disposable projection repairs from IncidentLedger. | `test_ledger_replay_repairs_lost_or_mismatched_cache` | `pytest -q tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_ledger_replay_repairs_lost_or_mismatched_cache` | high |
| NBF06-A38 | Exactly one policy/selector/effect graph; no second writer, cache, door, journal, or leakage. | `test_t8_ownership_has_one_policy_and_no_second_authority` | `python scripts/check_nbf06_a38.py --matrix .oracle/research/nbf06-acceptance-test-matrix.md --allowlist .oracle/research/nbf06-acceptance-test-matrix.md --negative-fixtures tests/arnold_pipelines/megaplan/fixtures/nbf06_a38` | high |

## A32 standalone commands and A38 checker

The A32 aggregate node is a fail-closed conjunction, not an independent
shortcut: it is PASS if and only if all three named standalone commands below
collect the named test and return zero with the pre-resolution/no-side-effect
refusal assertions proven. Missing collection, skip, xfail, error, or any
nonzero result is FAIL; a green aggregate without those three doors is not
evidence. Run each literal command as its own process. `--maxfail=1` makes
each pytest invocation fail-fast; do not join them with `;`, `&&`, or a shell
loop, and do not mask one result with shell composition:

```text
python -m pytest -q --maxfail=1 tests/arnold_pipelines/megaplan/test_tiered_execute_provider_fallback.py::test_execute_fallback_refusal_is_pre_resolution_and_side_effect_free
python -m pytest -q --maxfail=1 tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py::test_loop_execute_fallback_refusal_is_pre_resolution_and_side_effect_free
python -m pytest -q --maxfail=1 tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py::test_loop_engine_fallback_refusal_is_pre_resolution_and_side_effect_free
```

Run A38 as its own process from the repository root with the exact command in
row A38. It must read the file-qualified allowlist and named negative fixtures
and print exactly
`A38 checker: ALLOWLIST PASS; forbidden=0; negative_fixtures=PASS`.

```text
python scripts/check_nbf06_a38.py --matrix .oracle/research/nbf06-acceptance-test-matrix.md --allowlist .oracle/research/nbf06-acceptance-test-matrix.md --negative-fixtures tests/arnold_pipelines/megaplan/fixtures/nbf06_a38
```
No `timeout(1)` wrapper is part of the canonical command: that utility is not
portable across macOS/POSIX environments, and `pytest-timeout` is not a
declared dependency. An invoking harness may impose its own bounded timeout;
the command and exit status remain unchanged. Final review will rebind this
candidate's artifact SHA after these repairs.

### Auth/quota/rate-limit disposition and replacement manifest

These existing tests are explicitly classified here so a green generic
classifier test cannot be mistaken for NBF-06 v1 evidence. The first three
remain low-level compatibility characterization only. The direct advancement
positives are inverted into no-advance/no-side-effect tests with the exact
replacement paths below; availability/infrastructure remains the only
eligible operational class and execute remains prohibited.

| A05/A23 | Existing test (exact path) | Disposition | Replacement/inversion (exact path) | NBF-06 gate meaning |
| --- | --- | --- | --- | --- |
| A23 | `tests/arnold_pipelines/megaplan/test_fallback_chains.py::test_cross_family_advance_membership` | retain as generic classifier characterization; remove from T8 authority evidence | none | quota/auth/rate-limit classification does not authorize T8 routing |
| A05 | `tests/arnold_pipelines/megaplan/test_fallback_chains.py::test_codex_auth_error_surface_classifies_as_auth` | retain as generic classifier characterization; remove from T8 authority evidence | none | auth remains ordinary and no configured-chain advance |
| A05 | `tests/arnold_pipelines/megaplan/test_fallback_chains.py::test_codex_no_credits_surface_classifies_as_quota` | retain as generic classifier characterization; remove from T8 authority evidence | none | quota remains ordinary and no configured-chain advance |
| A25/A32 | `tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py::test_cross_family_quota_advances` | replace; positive direct fanout advancement is incompatible | `tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py::test_cross_family_quota_is_no_advance_no_side_effect` | typed quota yields no second resolution, worker, client, WBC, RPC, or route effect |
| A25/A32 | `tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py::test_launch_time_quota_advances_non_read_only_plan` | replace; GPT-5.6 launch-time quota cannot advance | `tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py::test_launch_time_quota_is_no_advance_no_side_effect` | quota is ordinary; no pre-tool target or side effect |
| A23/A25 | `tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py::test_sequential_same_family_fallback_is_non_writing_and_operational_only` (rate-limit/unsupported parameter cases) | split parameterization; retain availability characterization only | `tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py::test_rate_limit_and_unsupported_are_no_advance_no_side_effect` | rate-limit and unsupported are ordinary; no configured fallback target |
| A25 | `tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py::test_scatter_worker_unit_does_not_advance_cross_family_for_rate_limit_or_auth` | retain as compatible negative coverage | none | confirms non-T8 classes cannot advance fanout |

Each replacement is a standalone A01–A38 acceptance command once implemented;
missing future NBF-06 test files are not a present source failure. No generic
positive quota/rate-limit/auth assertion may be promoted into the T8 gate.

## A38 file-qualified allow/deny graph

Every path below is repository-relative. The refusal owner is explicitly
`arnold_pipelines/megaplan/fallback_chains.py:ExecuteFallbackUnsafe`; there is
no abbreviated or duplicate owner.

The checker reports definitions, imports, calls, and writes separately. Each
row is literal and file-qualified; no grouped/inherited owner is accepted.

| File-qualified symbol | Role / allowed edge | Forbidden edge |
| --- | --- | --- |
| `arnold_pipelines/megaplan/cloud/worker_dispatch.py:_outcome_from_terminal_exception` | typed adapter → dispatch seam | prose/stderr classification |
| `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` | shared seam → pure selector | second selector/writer |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_provider_route_proposal` ↔ `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_provider_route_proposal` | proposal transport → `select_provider_route(request, ledger_view)` → `apply_provider_route_decision_locked` → `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` (sole route-transition append) | `reserve_provider_route_locked`, `append_provider_route_decision`, caller-created view |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProviderRouteDecision` | closed union: `Hold|Probe|PreToolNextTarget|SameRouteRecoveryChild|PostTerminalConfiguredFallbackChild|ReturnPrimary|Noop|Refusal|DurabilityUnknown` | untyped branch or pre-tool choice outside union |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_route(request, ledger_view)` | typed request + immutable view read → decision | append/launch/write |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:apply_provider_route_decision_locked` | decision → named locked ledger methods | unlocked append |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProviderLedgerView` | locked view constructor → selector | persistent cache authority |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py:classify_dispatch_outcome` | lossless typed outcome adapter → NBF-02/T8 interception | generic breaker, T8 terminal, observation, or route writer |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py:classify_external_error_payload` | external payload adapter → typed non-T8 classification | prose-driven T8 exhaustion or configured-target advance |
| `arnold_pipelines/megaplan/orchestration/recovery_policy.py:RecoveryPolicy.classify` | generic retry/escalation owner for non-T8 cases, including repeated `internal_error` | intercepting `provider_exhausted`, T8 breaker, terminal, observation, or route write |
| `arnold_pipelines/megaplan/orchestration/recovery_policy.py:RecoveryPolicy.classify_with_circuit` | generic circuit wrapper → `RecoveryPolicy.classify` for non-T8 outcomes | T8-before-generic ordering bypass or blanket internal-error exemption |
| `arnold_pipelines/megaplan/incident/disposition.py:record_disposition` | NBF-01 signal/disposition append authority | NBF-06 terminal, observation, route, or provider breaker write |
| `arnold_pipelines/megaplan/incident/disposition.py:record_before_signal` | signal claim and terminal-projection helper → NBF-01 disposition/terminal APIs | provider T8 writer, observation/route append, or policy bypass |
| `arnold_pipelines/megaplan/incident/disposition.py:_ladder_terminal` | signal-ladder terminal projection delegates to canonical NBF-01 writer | duplicate terminal authority or NBF-06 route/observation write |
| `arnold_pipelines/megaplan/incident/disposition.py:_record_ladder_stage` | signal-ladder stage delegates to `record_before_signal` and canonical NBF-01 writer | duplicate terminal authority or NBF-06 route/observation write |
| `arnold_pipelines/megaplan/incident/disposition.py:recover_worker_disposition_outcome` | ordinary disposition terminal recovery/reconciliation → NBF-01 terminal API | provider T8 terminal/observation/route write or inferred provider exhaustion |
| `arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback` | strict chain → typed choice/refusal | target launch |
| `arnold_pipelines/megaplan/workers/_impl.py:resolve_agent_mode` | propagation preserving chain identity | alternate selection |
| `arnold_pipelines/megaplan/workers/_impl.py:run_step_with_worker` | typed accepted outcome transport | duplicate provider policy |
| `arnold_pipelines/megaplan/fallback_chains.py:FallbackSpecChain` | canonical chain type/codec | launch/route write |
| `arnold_pipelines/megaplan/fallback_chains.py:normalize_fallback_spec_list` | strict list normalization | silent filtering |
| `arnold_pipelines/megaplan/fallback_chains.py:normalize_fallback_spec_value` | strict scalar/list normalization | ambient override |
| `arnold_pipelines/megaplan/fallback_chains.py:validate_fallback_spec_value` | reject malformed/duplicate/cross-phase | target selection |
| `arnold_pipelines/megaplan/fallback_chains.py:map_fallback_spec_value` | canonical origin mapping | client/WBC effect |
| `arnold_pipelines/megaplan/fallback_chains.py:select_fallback_spec` | characterization only | second authority |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_configured_fallback_chain_v1` | sole canonical CHAIN V1 serializer; framed bytes and identity producer | legacy JSON or target selection |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_configured_fallback_chain_v1` | exact CHAIN V1 inverse/replay | inference upgrade or mutable config |
| `arnold_pipelines/megaplan/fallback_chains.py:encode_fallback_specs` | reserved-JSON compatibility persistence only | canonical identity bytes or selector |
| `arnold_pipelines/megaplan/fallback_chains.py:decode_fallback_specs` | reserved-JSON compatibility inverse only | CHAIN V1 identity or target selection |
| `arnold_pipelines/megaplan/fallback_chains.py:encode_phase_model_value` | persistence bridge | direct state mutation |
| `arnold_pipelines/megaplan/fallback_chains.py:decode_phase_model_value` | persistence bridge inverse | ambient fallback |
| `arnold_pipelines/megaplan/fallback_chains.py:configured_fallback_chain_for_phase` | canonical phase lookup | launch |
| `arnold_pipelines/megaplan/fallback_chains.py:provider_family` | family classifier | route mutation |
| `arnold_pipelines/megaplan/fallback_chains.py:classify_retryability` | typed class map | prose class |
| `arnold_pipelines/megaplan/fallback_chains.py:is_retryable_classification` | availability/infrastructure boundary | auth/quota advancement |
| `arnold_pipelines/megaplan/fallback_chains.py:is_cross_family_retryable_classification` | cross-family guard | same-family fallback |
| `arnold_pipelines/megaplan/fallback_chains.py:is_same_family_operational_classification` | ordinary classification | exhaustion |
| `arnold_pipelines/megaplan/fallback_chains.py:is_retryable_failure` | typed adapter classifier | second execute target |
| `arnold_pipelines/megaplan/fallback_chains.py:ExecuteFallbackUnsafe` | sole refusal owner + codec/inverse | alternate owner |
| `arnold_pipelines/megaplan/execute/batch.py:_run_execute_worker_with_configured_fallback` | delegate/refuse before resolution | second target/effect |
| `arnold_pipelines/megaplan/_core/worker_fanout.py:_next_fallback_index` | delegate index | independent selection |
| `arnold_pipelines/megaplan/_core/worker_fanout.py:_run_worker_unit_with_ordered_fallback` | typed refusal transport | worker effect after refusal |
| `arnold_pipelines/megaplan/loop/engine.py:run_loop_worker` | direct loop refusal | fall-through target |
| `arnold_pipelines/megaplan/incident/ledger.py:provider_ledger_view_locked` | locked immutable view | external cache |
| `arnold_pipelines/megaplan/incident/ledger.py:start_provider_probe_locked` | one lease CAS at injected-clock `now >= retry_not_before`; frozen projection `none→leased` | launch or second active lease |
| `arnold_pipelines/megaplan/incident/ledger.py:record_provider_probe_result_locked` | fenced typed result; writes one `provider_probe_result` | unlocked result or late/foreign result |
| `arnold_pipelines/megaplan/incident/ledger.py:close_provider_probe_locked` | one single-use close CAS; failed/expired/unknown map to held/unresolved `failed` projection | third attempt or new state enum |
| `arnold_pipelines/megaplan/incident/ledger.py:reconcile_provider_probe_locked` | exact unknown/expiry repair under same lease/key/epoch/route fence | inferred pass or new lease |
| `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` | sole physical terminal append before T8 selection; matching bytes replay the existing terminal; observation/link CAS follows from the rebuilt ledger view | duplicate terminal writer, policy before append |
| `arnold_pipelines/megaplan/incident/ledger.py:record_provider_terminal_with_observation_locked` | locked NBF-06 adapter delegating to `IncidentLedger.append_terminal_outcome`; no independent append | second terminal authority |
| `arnold_pipelines/megaplan/incident/ledger.py:append_provider_observation_link` | locked T8 observation/link applier after the sole terminal append, or exact reconciliation replay | direct policy writer/new count |
| `arnold_pipelines/megaplan/incident/ledger.py:reconcile_provider_observation_locked` | legacy repair/import only; cannot create a V1 observation or inferred count | direct legacy-to-provider write |
| `arnold_pipelines/megaplan/incident/ledger.py:record_provider_hold_locked` | hold/zero-count writer | child/count |
| `arnold_pipelines/megaplan/incident/ledger.py:record_provider_success_locked` | exact parent reset | child/count |
| `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` | sole locked route-child append; assigns event identity from proposal-bound payload, then derives postcommit view receipt | route proposal/decision append, receipt-bearing event |
| `arnold_pipelines/megaplan/incident/ledger.py:derive_receipt` | postcommit derivation | caller receipt ID |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_worker_admission_receipt` | NBF-01 canonical receipt | NBF-06 redefinition |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_adapter_evidence_precommit` | precommit evidence codec | circular postcommit ID |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_terminal` | terminal codec | observation in preimage |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_observation` | derived link codec | caller ID |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_hold` | exact parent codec | generic alias |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_success` | exact parent codec | count/child write |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_event` | event without receipt | view in event |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_view` | event + derived receipt | ledger-event receipt |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_execute_fallback_refusal` | refusal transport | second exception owner |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_provider_probe_request` ↔ `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_provider_probe_request` | `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` → `arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_probe` → `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProbeExecutor.run`; transport only, no durable write | caller-supplied live target or incident-store append |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_provider_probe_result` ↔ `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_provider_probe_result` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProbeExecutor.run` → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_probe_result_locked`; typed transport boundary before locked write | inferred pass, duplicate result, or unlocked write |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProbeExecutor` | abstract executor → `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProbeExecutor.run` | client/tool/worker launch |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:LedgerBoundProbeExecutor` | lease/parent/key/epoch-bound executor → result | unbound executor or second authority |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_evidence` | envelope serializer → terminal/link adapter | missing inverse/unknown upgrade |
| `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_evidence` | envelope inverse → terminal/link adapter | unknown upgrade |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_epoch_claim` | claim serializer → locked reservation | receipt/reservation circular input |
| `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_epoch_claim` | claim inverse → locked reservation | receipt/reservation circular input |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_epoch_binding` | binding serializer → locked repair | stale replacement accepted |
| `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_epoch_binding` | binding inverse → locked repair | stale replacement accepted |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_recovery_verified` | recovery serializer → passed-and-closed-probe applier | child without closed proof |
| `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_recovery_verified` | recovery inverse → passed-and-closed-probe applier | child without closed proof |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_probe_result` | probe result serializer → fenced CAS | result outside lease |
| `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_probe_result` | probe result inverse → fenced CAS | result outside lease |
| `arnold_pipelines/megaplan/chain/source_admission.py:_append_event` | unrelated chain-state writer; explicitly excluded | NBF-06 policy edge |
| `arnold_pipelines/megaplan/cloud/incident_bridge.py:IncidentBridge.append_event` | unrelated cloud bridge writer; explicitly excluded | NBF-06 provider event |
| `arnold_pipelines/megaplan/agentbox_adapter.py:append_event` | unrelated AgentBox lifecycle writer; explicitly excluded | NBF-06 provider event |
| `arnold_pipelines/megaplan/custody/wbc_runtime.py:WBCExecutor._append_event` | unrelated WBC custody writer; explicitly excluded | NBF-06 provider event |
| `arnold_pipelines/megaplan/workers/omp.py:_append_event` | unrelated OMP retry trace; explicitly excluded | provider observation/count |
| `arnold_pipelines/megaplan/planning/control_binding.py:PlanningControlBinding` | maintenance-owned planning binding; NBF-06 may consume provenance only | NBF-06 mutation, bypass, reinterpretation |
| `arnold_pipelines/megaplan/planning/control_binding.py:planning_control_binding` | maintenance-owned factory; exact deny boundary | NBF-06 policy override/selector |
| `arnold_pipelines/megaplan/planning/operations.py:planning_control_binding` | maintenance consumer; provenance passthrough only | NBF-06 write/override |
| `arnold_pipelines/megaplan/control_interface.py:planning_control_binding` | maintenance consumer; no NBF-06 edge | policy reinterpretation |

Generic `append_event` has zero allowed NBF-06 callers. The five exact
repository-relative symbols listed above are the complete unrelated-caller
denylist; they may retain their existing domains but must not emit any
`NBF06-*` event. The A38 checker must enumerate AST definitions, imports,
calls, and writes, resolve each caller/target to a repository-relative
file-qualified symbol, and fail on any NBF-06 generic call or any unlisted
generic caller that reaches an NBF-06 domain—there is no implicit “all other”
exception. Negative fixtures must reject direct signal, NBF-04/05, NBF-08,
provider store/cache, duplicate selectors/writers, unlocked writes, missing
inverse, and aliases.

### A38 primary exact serializer/inverse/applier/write registry

The table below is the sole primary A38 registry. Each edge names the exact
file-qualified serializer and inverse, transport consumer, locked applier,
and durable write; preceding role-only prose and grouped denylist rows are
non-authoritative boundaries, not substitutes for these entries.

| Serializer | Exact inverse | Transport → consumer/applier → write |
| --- | --- | --- |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_provider_route_proposal` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_provider_route_proposal` | `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` → `arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_route(request, ledger_view)` → `arnold_pipelines/megaplan/orchestration/provider_resilience.py:apply_provider_route_decision_locked` → `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` (sole route transition append) |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_provider_probe_request` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_provider_probe_request` | `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` → `arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_probe` → `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProbeExecutor.run`; typed transport only, no durable write |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_provider_probe_result` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_provider_probe_result` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProbeExecutor.run` → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_probe_result_locked`; typed transport ends before the incident writer |
| `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_configured_fallback_chain_v1` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:deserialize_configured_fallback_chain_v1` | `arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback` → typed target/refusal applier → no direct NBF-06 durable write; sole CHAIN V1 identity producer is `derive_configured_fallback_chain_identity` |
| `arnold_pipelines/megaplan/fallback_chains.py:encode_fallback_specs` | `arnold_pipelines/megaplan/fallback_chains.py:decode_fallback_specs` | compatibility-only reserved-JSON persistence adapter → canonical CHAIN V1 codec; JSON bytes cannot be an identity or select a target |
| `arnold_pipelines/megaplan/fallback_chains.py:encode_phase_model_value` | `arnold_pipelines/megaplan/fallback_chains.py:decode_phase_model_value` | phase persistence bridge → `arnold_pipelines/megaplan/handlers/override.py:save_state_merge_meta` → `arnold_pipelines/megaplan/loop/engine.py:save_loop_state`; no provider-event write |
| `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome.to_dict` | `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome.from_dict` | legacy compatibility decode only; current live typed `DispatchOutcome` → `arnold_pipelines/megaplan/incident/schema.py:serialize_dispatch_outcome_precommit` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_dispatch_outcome_precommit` → one `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_adapter_evidence_precommit` handoff |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_worker_terminal_outcome` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_worker_terminal_outcome` | NBF-01 ordinary `worker_terminal_outcome` reader → ordinary terminal applier → NBF-01 canonical writer; legacy domain/version retained; no provider upgrade |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_terminal` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_terminal` | legacy provider reader → provider terminal migration applier → `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_terminal` legacy-byte rewrite only |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_observation` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_observation` | legacy observation reader → `arnold_pipelines/megaplan/incident/ledger.py:reconcile_provider_observation_locked` → observation repair write |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_hold_success` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_hold_success` | legacy hold/success reader → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_hold_locked` / `arnold_pipelines/megaplan/incident/ledger.py:record_provider_success_locked` → state write; no upgrade |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_recovery` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_recovery` | legacy recovery reader → evidence-only repair → `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_recovery` legacy-byte rewrite only; no V1 allocation |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_adapter_evidence_precommit` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_adapter_evidence_precommit` | cloud worker dispatch → terminal adapter → `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_dispatch_outcome_precommit` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_dispatch_outcome_precommit` | typed adapter bridge → terminal adapter → `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_evidence` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_evidence` | terminal/link adapter → observation writer → `arnold_pipelines/megaplan/incident/ledger.py:append_provider_observation_link` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_terminal` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_terminal` | terminal adapter → terminal applier → `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_observation` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_observation` | observation linker → observation applier → `arnold_pipelines/megaplan/incident/ledger.py:append_provider_observation_link` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_hold` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_hold` | hold policy → hold applier → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_hold_locked` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_success` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_success` | success policy → success applier → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_success_locked` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_epoch_claim` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_epoch_claim` | `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` → `arnold_pipelines/megaplan/incident/ledger.py:bind_provider_epoch_locked` (locked claim producer) → claim validator; `admission_generation` excluded from identity/key |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_epoch_binding` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_epoch_binding` | `arnold_pipelines/megaplan/incident/ledger.py:repair_provider_epoch_binding_locked` (locked binding CAS) → exact `bound|replaced|stale|pending|durability_unknown` result |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_probe_start` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_probe_start` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_probe` → `arnold_pipelines/megaplan/incident/ledger.py:start_provider_probe_locked` → `arnold_pipelines/megaplan/incident/ledger.py:append_provider_probe_start` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_probe_result` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_probe_result` | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:ProbeExecutor.run` → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_probe_result_locked` → `arnold_pipelines/megaplan/incident/ledger.py:append_provider_probe_result` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_probe_closed` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_probe_closed` | `arnold_pipelines/megaplan/incident/ledger.py:close_provider_probe_locked` → `arnold_pipelines/megaplan/incident/ledger.py:append_provider_probe_closed` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_recovery_verified` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_recovery_verified` | passed-probe applier → `arnold_pipelines/megaplan/incident/ledger.py:record_provider_recovery_verified_locked` → one proof write |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_observation_link_pending` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_observation_link_pending` | terminal linker → `arnold_pipelines/megaplan/incident/ledger.py:append_provider_observation_link` → pending write |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_observation_reconciled` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_observation_reconciled` | replay repair → `arnold_pipelines/megaplan/incident/ledger.py:reconcile_provider_observation_locked` → reconciled write |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_durability_unknown` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_durability_unknown` | recovery classifier → `arnold_pipelines/megaplan/incident/ledger.py:reconcile_provider_durability_unknown_locked` → unknown hold write |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_event` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_route_child_event` | pure selector → `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` → `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_view` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_route_child_view` | postcommit owner → `arnold_pipelines/megaplan/incident/ledger.py:derive_receipt` → committed view |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_return_primary` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_return_primary` | return selector → locked composite applier → `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_execute_fallback_refusal` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_execute_fallback_refusal` | `arnold_pipelines/megaplan/execute/batch.py:_run_execute_worker_with_configured_fallback` / `arnold_pipelines/megaplan/_core/worker_fanout.py:_run_worker_unit_with_ordered_fallback` / `arnold_pipelines/megaplan/loop/engine.py:run_loop_worker` → typed refusal applier → no durable target write |
| `arnold_pipelines/megaplan/incident/schema.py:serialize_worker_admission_receipt` | `arnold_pipelines/megaplan/incident/schema.py:deserialize_worker_admission_receipt` | NBF-01 receipt owner `arnold_pipelines/megaplan/incident/schema.py:WorkerAdmissionReceipt` → `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` → `arnold_pipelines/megaplan/incident/schema.py:write_worker_admission_receipt` |

Primary A38 deny edges are also exact and file-qualified: legacy readers
`arnold_pipelines/megaplan/incident/schema.py:deserialize_worker_terminal_outcome`,
`arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_terminal`,
`arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_observation`,
`arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_hold_success`,
and `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_recovery`
may only perform their named legacy-byte repair paths and may not upgrade or
emit current NBF06 domains. The planning boundary symbols
`arnold_pipelines/megaplan/planning/control_binding.py:PlanningControlBinding`,
`arnold_pipelines/megaplan/planning/control_binding.py:planning_control_binding`,
`arnold_pipelines/megaplan/planning/operations.py:planning_control_binding`, and
`arnold_pipelines/megaplan/control_interface.py:planning_control_binding` are
provenance-only consumers: no NBF06 selector, mutation, override, or write may
import, call, or reinterpret them. Generic
`arnold_pipelines/megaplan/incident/ledger.py:append_event` has zero NBF06
callers; all five unrelated append symbols above are denylist-only.

### A38 alternate entrance and alias registry

Every compatibility entrance delegates to the one NBF-02 dispatch seam or the
one configured-chain refusal owner. These are standalone file-qualified edges,
not inherited role prose:

| Entrance | Producer → transport → consumer/policy/effect | Forbidden bypass |
| --- | --- | --- |
| `arnold_pipelines/megaplan/workers/_impl.py:resolve_agent_mode` | persisted configured-chain value → `arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback` metadata propagation → `dispatch_with_admission` | alternate selection or launch |
| `arnold_pipelines/megaplan/workers/_impl.py:run_step_with_worker` | typed worker request → `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` → `select_provider_route(request, ledger_view)` → `apply_provider_route_decision_locked` | second provider policy or direct target |
| `arnold_pipelines/megaplan/execute/batch.py:_run_execute_worker_with_configured_fallback` | typed outcome → `arnold_pipelines/megaplan/fallback_chains.py:ExecuteFallbackUnsafe` transport → no second resolution/effect | fallback target, metadata patch, client/WBC/RPC/worker effect |
| `arnold_pipelines/megaplan/_core/worker_fanout.py:_next_fallback_index` | ordered chain index → `_run_worker_unit_with_ordered_fallback` → typed refusal before worker dispatch | independent selector or launch after refusal |
| `arnold_pipelines/megaplan/_core/worker_fanout.py:_run_worker_unit_with_ordered_fallback` | worker unit → `run_step_with_worker` → NBF-02 dispatch seam | direct second target/effect |
| `arnold_pipelines/megaplan/loop/engine.py:run_loop_worker` | loop worker request → typed refusal or `dispatch_with_admission` → one policy call | fall-through target or ambient fallback |
| `arnold_pipelines/megaplan/handlers/shared.py:_run_worker` | handler request → `arnold_pipelines/megaplan/workers/_impl.py:run_step_with_worker` → NBF-02 seam | handler-local selector/writer |
| `arnold_pipelines/megaplan/auto.py:_project_auto_dispatch` | auto phase dispatch → `arnold_pipelines/megaplan/handlers/shared.py:_run_worker` → `arnold_pipelines/megaplan/workers/_impl.py:run_step_with_worker` → NBF-02 seam | auto-local provider policy or launch |
| `arnold_pipelines/megaplan/cloud/babysitter/launch.py:_admit_managed_launch` | managed launch request → `dispatch_with_admission` → one receipt/terminal seam | cloud-local admission, launch, or provider writer |
| `arnold_pipelines/megaplan/workers/omp.py:_run_omp_with_admission` | OMP typed worker request → `dispatch_with_admission` → one policy/applier path | OMP-local retry, selector, or append |

Canonical aliases are explicit: `chain_digest→configured_fallback_chain_identity`
(display-only, non-serializable); `retryability_class→retryability` (nested
provider evidence is authoritative); `provider_class→provider_failure_class`
(wire normalization); `_advance_configured_spec_fallback` resolves to
`arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback`
and is distinct from the `fallback_chains.py:ExecuteFallbackUnsafe` refusal
owner; `serialize_dispatch_outcome` resolves only to
`arnold_pipelines/megaplan/incident/schema.py:serialize_dispatch_outcome_precommit`.
Aliases must not introduce a selector, writer, receipt authority, or generic
`append_event` edge. The alternate paths above are the complete entrance set;
an unlisted caller reaching an NBF06 domain fails A38.

## Validation contract

Run each A01–A38 command independently with `pytest -q`; run the three
standalone A32 commands independently; run literal-vector length/SHA checks,
Python compile checks for changed NBF-06 files, the deterministic AST/import
checker, and `git diff --check`. No semicolon may mask a failure. The required
checker output is:

```text
A38 checker: ALLOWLIST PASS; forbidden=0; negative_fixtures=PASS
```

The enclosing packet records the final matrix SHA and avoids circular
brief↔matrix digests. Any changed row, command, vector, or edge requires a new
reviewed rewrite rather than an appended amendment.
