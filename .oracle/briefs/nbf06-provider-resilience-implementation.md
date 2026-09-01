# NBF-06 — Provider resilience through the shared dispatch seam

## Contract status and provenance

This is the consolidated implementation contract for Batch 4 / NBF-06. It is
planning guidance only: it does not edit the tasklist, status, source tree,
NBF-04/NBF-05 signal authority, or the deferred NBF-08 chain-control ledger.

Frozen inputs:

| Input | SHA-256 |
| --- | --- |
| `.oracle/tasklist.md` | `a4f574ce02421226a0f4610ffc503918e54cd8b5f8ee28ca8e7805afaf1e3959` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/research/nbf06-provider-resilience-seam.md` | `0f00ca460f1f7d19d1a2c85adf96fddb49378ec34e3ec31f9f07e617d58f168d` |
| `.oracle/research/nbf06-architecture-adversarial.md` | `6903b3b4ca70a5f64e9bf78349f34557edcb5ee6807ecda3f9beca7637740f9f` |
| authoritative A01–A38 matrix | final SHA recorded by the enclosing packet; no circular brief↔matrix digest |
| Round-22 adjudication, input to this repair | `467366deaef4d7056fce9b70a596b26282789d4ae56ad1564e9c2c47d10cc4ca` (prior Round-21 input retained as historical provenance: `b7fdcbd50ef19437273aa62049a6c4c2f87e2ad7942114f9ff6336649da6a67b`) |

This file and `.oracle/research/nbf06-acceptance-test-matrix.md` are the single
consolidated contract, currently the Round-22 repair candidate. Former Round-6–21
amendment sections,
duplicate definitions, and superseded 452-byte child proposal/old committed
vectors are historical provenance only and are not part of the contract. The
matrix is authoritative for node names, exact commands, and A01–A38. The
current adjudication SHA above is the Round-22 custody input; final review
records the resulting artifact SHAs. Round-22 is the current authority boundary.

Authority precedence is frozen tasklist/plan, then this brief and matrix, then
bound research, then live source as descriptive preimplementation evidence.
NBF-06 depends on NBF-01 through NBF-05 and executes only after their sync
barrier. NBF-08 remains deferred.

## Settled Decisions

- **SD-001** — One T8 provider policy is selected at the shared dispatch seam; every production door consumes that decision. _load_bearing: true_
  Rationale: one authority prevents duplicate observation, terminal, and route decisions.
- **SD-002** — Extend the existing IncidentLedger, schema, projection, lock, and CAS APIs only; add no provider store, persistent cache, journal, scheduler, projection, rotator, admission door, or terminal writer. _load_bearing: true_
  Rationale: NBF-01 remains the durable authority and NBF-08 is deferred.
- **SD-003** — Exhaustion comes only from structured post-acceptance adapter evidence with `availability` or `idle_timeout`; prose, stderr, retry chatter, auth, quota, rate-limit, unsupported, context, internal, and timeout classes never create T8 exhaustion. _load_bearing: true_
  Rationale: the typed DispatchOutcome contract is fail-closed.
- **SD-004** — One accepted exhausted logical dispatch yields exactly one linked provider terminal and provider observation; internal attempts are evidence only. _load_bearing: true_
  Rationale: cardinality must survive callbacks and replay.
- **SD-005** — The provider-failure key is phase, normalized selected spec, typed failure class, and authoritative provider epoch; volatile fields are excluded. _load_bearing: true_
  Rationale: time or liveness changes cannot authorize an identical retry.
- **SD-006** — The first matching exhaustion commits hold/streak one, waits for `retry_not_before`, and allows exactly one bounded probe lease under key/parent/epoch/route CAS; unavailable or `leased` state is held/unresolved, and only an explicitly closed lease permits the bounded post-close retry. _load_bearing: true_
  Rationale: the mandatory first probe is durable and single-use.
- **SD-007** — Only a passed result whose exact probe lease has been closed by the single-use close CAS, then consumed as evidence-bound `provider_recovery_verified`, authorizes one linked same-route child through `reserve_provider_route_child`; admission remains canonical. _load_bearing: true_
  Rationale: route changes require source/target identity binding.
- **SD-008** — Configured fallback uses one typed authority delegated through `_advance_configured_spec_fallback`; all other selectors are adapters and ambient fallback is suppressed when a configured chain exists. _load_bearing: true_
  Rationale: two routing authorities can bypass streak and admission invariants.
- **SD-009** — Malformed, duplicate, ambiguous, conflicting, reordered, or cross-phase chain entries fail closed; canonical bytes and origin identity bind to receipts. _load_bearing: true_
  Rationale: first-match parsing cannot be authoritative.
- **SD-010** — `execute` and `loop_execute` never advance beyond the first configured spec; `ExecuteFallbackUnsafe` is typed/observable before target resolution or side effects. _load_bearing: true_
  Rationale: retries can duplicate mutations and checkpoints.
- **SD-011** — Provider scheduling bypasses generic failure/breaker/blocked accounting; genuine internal errors retain existing breaker behavior. _load_bearing: true_
  Rationale: provider hold is not ordinary phase failure.
- **SD-012** — NBF-04/NBF-05 physical signal, confirmation, custody, worker-disposition, and shell authority remain untouched; NBF-08 owns the later chain-control ledger. _load_bearing: true_
  Rationale: NBF-06 adds provider policy at existing typed seams only.

## Scope, ownership, and non-goals

NBF-06 owns T8 provider observations, keyed consecutive streaks, bounded
hold/probe, evidence-bound recovery, degradation, configured fallback, scalar
pin, return-to-primary, and replay/crash/race/execute prohibitions. It uses
NBF-01 IncidentLedger/projection/CAS and NBF-02
`arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission`. NBF-01 owns generic
schema/event serialization and the admission receipt; NBF-06 owns policy,
provider adapters, and provider tests. NBF-04/05 own all physical signal and
shell doors. NBF-08 owns chain-control. No second authority is permitted. A missing configured
chain identity is explicit null (U64BE(0)); all-zero raw32 is never a no-chain
sentinel. Auth, quota, rate-limit, unsupported, context, internal, and timeout
classes produce no `PreToolNextTarget`, no configured-chain advancement, and no
typed exception authorizing a target under v1; only eligible operational classes
reach a pre-tool decision. Accepted-launch T8 exhaustion remains a separate
post-tool rule.

| Owner | File-qualified symbol | Contract |
| --- | --- | --- |
| admission seam | `arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission` | one typed policy call after accepted terminal normalization and the sole NBF-01 terminal append |
| adapter | `arnold_pipelines/megaplan/cloud/worker_dispatch.py:_outcome_from_terminal_exception` | structured evidence only; never prose classification |
| provider policy | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_route(request, ledger_view)` | sole pure decision over typed request and immutable ledger view |
| effect door | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:apply_provider_route_decision_locked` | sole locked applier for T8 effects |
| generic recovery | `arnold_pipelines/megaplan/orchestration/recovery_policy.py:RecoveryPolicy.classify`, `RecoveryPolicy.classify_with_circuit` | non-T8 retry/escalation and repeated-internal-error circuit owner; T8 is intercepted before it |
| typed classification adapter | `arnold_pipelines/megaplan/orchestration/phase_result_classify.py:classify_dispatch_outcome`, `classify_external_error_payload` | lossless typed adapter only; no breaker, terminal, observation, or route authority |
| configured chain | `arnold_pipelines/megaplan/workers/_impl.py:_advance_configured_spec_fallback` | sole configured alternate-selection authority |
| canonical CHAIN codec | `arnold_pipelines/megaplan/orchestration/provider_resilience.py:serialize_configured_fallback_chain_v1`, `deserialize_configured_fallback_chain_v1`, `derive_configured_fallback_chain_identity` | sole framed CHAIN V1 serializer/inverse/identity producer; pure bytes only |
| legacy chain persistence | `arnold_pipelines/megaplan/fallback_chains.py:encode_fallback_specs`, `decode_fallback_specs` | compatibility JSON adapter only; never canonical identity or a selector |
| execute adapters | `arnold_pipelines/megaplan/execute/batch.py:_run_execute_worker_with_configured_fallback`, `arnold_pipelines/megaplan/_core/worker_fanout.py:_next_fallback_index`, `arnold_pipelines/megaplan/loop/engine.py:run_loop_worker` | delegate and preserve refusal before second resolution |
| durable state | `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome`, `reserve_provider_route_child`, named provider/CAS/probe methods | additive locked methods only; these are the sole physical terminal and route-child writers |
| compatibility | `arnold_pipelines/megaplan/cloud/babysitter/launch.py:_admit_managed_launch`, `arnold_pipelines/megaplan/handlers/shared.py`, `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`, `arnold_pipelines/megaplan/auto.py`, `arnold_pipelines/megaplan/workers/omp.py` | transport typed results; no policy duplication |
| signal/disposition | `arnold_pipelines/megaplan/incident/disposition.py:record_disposition`, `record_before_signal`, `_ladder_terminal`, `_record_ladder_stage` | NBF-01 signal/disposition and ordinary terminal projection only; never NBF-06 terminal/observation/route |

`PlanningControlBinding` (`arnold_pipelines/megaplan/planning/control_binding.py` class/factory and its
maintenance consumers) is outside NBF-06. Memory-headroom selection and phase
model propagation are adapters. Direct client/WBC/RPC/tool/worker launch after
refusal, direct signal, NBF-04/05 imports, NBF-08 storage, a provider cache,
generic `append_event`, or an unlocked write are forbidden.

For the generic append boundary the explicit allow set for NBF-06 is empty:
no NBF-06 symbol may call `append_event`. The checker resolves every AST call
and import to a repository-relative file-qualified symbol and fails on any
NBF-06 generic call or any unlisted caller reaching an `NBF06-*` domain; the
five unrelated callers in the matrix are denylist-only fixtures and cannot
emit NBF-06 events.

## Canonical protocol

### Chain, epoch, receipt, and evidence

The canonical chain vocabulary is **`configured_fallback_chain_identity`**;
`chain_digest` is a non-serializable display alias only. Every encoded field is
named `configured_fallback_chain_identity`. The one canonical CHAIN V1 codec
owner is `arnold_pipelines/megaplan/orchestration/provider_resilience.py`:
`serialize_configured_fallback_chain_v1` and its exact inverse
`deserialize_configured_fallback_chain_v1`; `derive_configured_fallback_chain_identity`
hashes those bytes. Chain bytes are
`NBF06-CHAIN-ID-V1`, length-prefixed UTF-8/NFC text fields in order
`domain, phase, parser_version, origin_bytes`, the raw 32-byte
`SHA256(origin_bytes)`, then a raw U64BE `spec_count` followed by each
`normalized_spec_1...spec_n` as U64BE(length)||UTF-8/NFC. NUL/invalid UTF-8
reject. In the `CHAIN(175)` fixture, the raw `spec_count` field occupies eight
bytes (16 hex digits) and is `0000000000000001` (U64BE decimal 1); the following
`000000000000001a` is the 26-byte length of the single displayed normalized
spec. Thus the fixture is a scalar one-spec chain, not a sixteen-spec chain;
the 16-digit field is not the integer count 16.
The identity is SHA-256 of the complete bytes; origin and canonical bytes are
stored in the reservation/receipt and replayed byte-for-byte. A scalar is a
one-spec chain. The legacy `arnold_pipelines/megaplan/fallback_chains.py:
encode_fallback_specs`/`decode_fallback_specs` pair remains a compatibility
persistence adapter for its reserved `__fallback_json__:` representation only;
those JSON bytes are never accepted as CHAIN V1 identity bytes and the adapter
does not select a target. `_advance_configured_spec_fallback` remains the sole
configured-chain selection door and consumes the canonical codec output.
The exact rejection fixture is
`LEGACY_CHAIN_JSON(48)=5f5f66616c6c6261636b5f6a736f6e5f5f3a5b226f6d703a646565707365656b2f646565707365656b2d63686174225d`,
SHA-256 `ea4479ea855450f2987f003338d57d63215e18e317e0c6fe232122f8c3e1a4cf`;
it must never be accepted as CHAIN V1.

At every non-null transition, receipt, refusal, and branch field, this chain
identity is exactly the raw32 SHA-256 digest of the canonical chain bytes;
hex/text is never serialized. Absence is exactly explicit `null` (`U64BE(0)`).
For precommit `DispatchOutcome`, staged nullable postcommit IDs remain `None`
on the typed object and are omitted from the wire payload. Explicit U64BE(0)
null is used only where that schema declares a nullable field; omission is not
null and no decoder infers an omitted postcommit ID.

`provider_epoch_identity` is one typed value everywhere: a raw32 SHA-256
digest of stable epoch-identity bytes. Display labels such as `epoch-1` are
non-serializable diagnostics only. The NBF-01 failure-key JSON exception
receives the lowercase hex rendering of that same raw32 value because its
existing API is string-valued; no second identity is created. Stable epoch
identity excludes route-liveness and membership-refresh digests. Those values
remain separate claim/binding fencing evidence and are compared under the
ledger lock, so a refresh alone cannot rekey, reset, or authorize.

The canonical provider-family vocabulary is upstream-provider based, never the
`omp` transport: direct `codex:<model>` → `codex`, `claude:<model>` →
`claude`, `premium:<model>` → `premium`, aliases `openai-codex:<model>` →
`codex` and `grok:<model>` → `xai`, and `omp:<upstream>/<model>` → lowercase
upstream (including the registered `deepseek`, `fireworks`, `mimo`, and
`openai` families). Bare/unknown/malformed provider forms reject closed, with
no guessed family or fallback. This same normalized family is used in epoch
identity, claim/binding, failure key, route/return and child proofs, and probe
bindings; liveness/membership remain fencing-only.

The stable source `NBF06-PROVIDER-EPOCH-ID-V2` fields are
`domain,family,normalized_spec,provider_epoch_generation`; its digest is raw32
`540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28`.
The target `codex:gpt-5.6`/`provider_epoch_generation=8` digest is raw32
`03d2b74947128e3da10aa9353e41f8dd3fcf6fc76c798eb67cbe8495da1919ea` and
its independently derived NBF-01 target failure key is
`dfee816bba50394763112667ab7e56da7fe567a33e2a97b99dcaaf7eca0ed96e`.
Neither target value may inherit source identity.

At the locked reservation boundary,
`arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission`
supplies the accepted reservation context and
`arnold_pipelines/megaplan/incident/ledger.py:bind_provider_epoch_locked` is
the exact locked producer of the provider epoch claim:
`epoch_version, provider_epoch_identity, provider_family, normalized_spec,
route_liveness_identity, route_liveness_digest, provider_membership_snapshot_digest,
admission_generation, provider_epoch_generation, claim_bytes, claim_digest`. The
stable identity fields are
stable identity; liveness/membership fields are fencing evidence only. Wall clock, caller strings,
unbound config, reservation ID, and receipt ID are excluded from the claim.
After reservation commit,
`arnold_pipelines/megaplan/incident/ledger.py:repair_provider_epoch_binding_locked`
adds reservation event ID and admission receipt ID. Its typed fence result is
exactly `bound|replaced|stale|pending|durability_unknown`: replaced/stale,
missing, or forged claims are held and cannot route, probe, child, or launch;
pending is repaired only by the locked binding CAS; durability-unknown stays
held until exact replay/reconciliation. Stable `provider_epoch_generation`
belongs to the epoch identity bytes and is an authoritative non-negative U64
from the route/admission producer. `admission_generation` is a separate
reservation-metadata U64 and is excluded from stable identity and failure-key
derivation. Native liveness `proof_generation` is independent fencing evidence
and is never substituted for either value. Protocol `epoch_version` is the
codec/domain version, not a generation. Only these frozen names and types are
in scope.

`WorkerAdmissionReceipt` remains the NBF-01/02 receipt. Required provider
extensions are `configured_fallback_chain_identity` (non-null exactly raw32
chain digest; absent exactly explicit null), `provider_epoch_identity`,
`projection_key`, `projection_version`, and route linkage; nullable legacy
fields are explicit `null`. Its ID is derived only after reservation commit.
The receipt's custody binding is honest: NBF-01 owns and signs the canonical
receipt bytes/ID, including chain, origin, epoch-claim, and epoch-binding
fields; NBF-06 only stores/links those bytes and never derives a receipt ID or
claims custody authority. Cloud transport is bytes-only and cannot mint,
rewrite, or reinterpret that binding.
NBF-06's distinct `ProviderEvidenceEnvelope` carries plan, phase, logical
dispatch, admission receipt, reservation, raw chain/fingerprint digests,
selected spec, epoch, failure key, terminal/observation linkage, result,
broad `retryability_class`, and T8 `provider_failure_class`; unknown fields
reject and raw digests are exactly 32 bytes.

The NBF-02 handoff is one append-first ordered seam at
`arnold_pipelines/megaplan/cloud/worker_dispatch.py:dispatch_with_admission`.
The existing NBF-01 `IncidentLedger.append_terminal_outcome` call remains the
sole physical terminal writer and is completed before T8 selection; the T8
applier never calls a second terminal writer. The exact transaction is:
(1) pre-tool request admission/reservation creates the canonical
`WorkerAdmissionReceipt`; (2) `bind_provider_epoch_locked` fences the claim;
(3) accepted launch produces structured typed adapter evidence; (4) terminal
normalization produces the accepted `DispatchOutcome`; (5) the adapter invokes
`IncidentLedger.append_terminal_outcome` once, committing or replaying the
terminal; (6) under the ledger lock, a fresh immutable `ProviderLedgerView`
is rebuilt from the committed terminal, admission receipt/reservation,
provider evidence, epoch claim/binding, and current projection data; (7)
exactly one pure `select_provider_route(request, ledger_view)` consumes that view; (8)
`apply_provider_route_decision_locked` commits the observation/hold/route CAS;
and only then (9) postcommit envelope or child/return application is allowed.
The typed values crossing these edges are admission request/receipt, epoch
claim/binding, adapter evidence/`DispatchOutcome`, committed terminal plus
immutable view, `ProviderRouteDecision`, and committed envelope/view.
Policy selection before terminal append, a second policy invocation,
scheduler/launch/intake replacement, or any seam bypass is forbidden.

The append-first crash cutpoints are deterministic and replay-safe: before
append, replay re-runs admission/evidence and appends once; terminal-only,
terminal-plus-observation, and post-policy crashes reload the committed
terminal/view and return existing records through digest/CAS idempotency.
No cutpoint may create a duplicate terminal, observation, streak increment,
lease, or child. A terminal-only record is not route authorization until its
same-parent observation/policy reconciliation completes; torn/conflicting
bytes become `durability_unknown` and remain held.

The lifecycle is cycle-free and staged: pre-tool canonical admission performs
one locked reservation append, creating the admission receipt and epoch claim;
post-append binding repairs only the claim/receipt seam; accepted-launch
adapter evidence is then preterminal evidence referencing that receipt; the
sole terminal writer appends/replays the terminal before T8 selection; T8
rebuilds its immutable view and commits observation/hold/route CAS; postcommit
evidence, envelope, and derived child receipt/view follow. `provider_observation`
is terminal-derived and the sole count input. `provider_hold` is held/zero-count. `provider_success`
requires the exact terminal/observation/key parent, resets only that key, and
creates no observation or child. Duplicate payload bytes return the existing
record; conflicting or torn records become `durability_unknown`/permanent
hold. `DispatchOutcome` precommit IDs may be null only where the schema says
so; postcommit IDs are never inferred from caller prose.

The adapter precommit schema is the separate `PRECOMMIT_EVIDENCE` fixture: it
contains no terminal, observation, ledger event, or derived receipt ID.
The deterministic live bridge maps `DispatchOutcome.kind` to wire `result`,
`launch_state=accepted` to precommit eligibility (other launch states stay in
typed refusal/no-launch handling), `plan_id`, `phase`, `logical_dispatch_id`,
and `admission_receipt_id` to their same-named wire fields,
while `dispatch_family_id` remains typed transport metadata and is not an
NBF-06 precommit field,
`semantic_dispatch_fingerprint` to `fingerprint`, and nested
`provider_evidence.provider_epoch_identity`, `provider_failure_key`,
`retryability_class`, and `provider_failure_class` to the corresponding epoch,
raw32 key, retryability, and provider-class fields. Nullable terminal,
observation, event, and derived-receipt IDs remain `None` on the typed object
and are omitted from precommit wire; they are never inferred. The live
`DispatchOutcome` crosses an
explicit `serialize_dispatch_outcome_precommit` conversion: its typed fields
are mapped/re-encoded and the bridge receives its own domain. “Byte-for-byte
unchanged” applies only after this conversion to the bridge payload; it does
not claim that `DispatchOutcome.to_dict()` bytes equal NBF06 wire bytes. Only
after the terminal and
observation writers commit does `PROVIDER_ENVELOPE` carry the postcommit links.
The matrix publishes all three literal payloads and hashes, with no postcommit
ID entering a precommit digest.

The nested live `DispatchOutcome.provider_evidence` contract is closed as
`NBF06-PROVIDER-EVIDENCE-NESTED-V1`: `observation_id` (non-empty text),
`retryability_class` (known enum), `exhausted_attempt_count` (positive U64),
`terminal_provider_evidence_id` (non-empty text), `precondition_identity`
(non-empty text), `provider_epoch_identity` (exact raw32 identity),
`provider_failure_key` (canonical raw32 identity, lowercase-hex live form), `observed_at`
(ISO timestamp), and `provider_failure_class` (known enum) are required for a
provider-exhausted outcome; no unknown nested members are accepted. The
precommit adapter forwards this complete nested record as one framed
`nested_provider_evidence` field and the inverse reconstructs every field
byte-for-byte. Nested `observation_id` and `terminal_provider_evidence_id` are
evidence-local IDs, not postcommit ledger IDs; outer terminal/observation/
reconciliation/derived-receipt IDs remain omitted. Missing member, unknown
enum/version, malformed raw32, conflicting top-level `provider_failure_key`
alias, or class disagreement rejects; this nested record is evidence only and
cannot write a terminal, ChangedPrecondition, observation, or child.

The complete positive fixture is normative (all fields populated; U64BE for
numeric fields, U64BE-length UTF-8/NFC for text, U64BE(32)||raw32 for digests):

```text
NESTED_PROVIDER_EVIDENCE(285)=000000000000000100000000000000214e424630362d50524f56494445522d45564944454e43452d4e45535445442d5631000000000000000e6f62732d65766964656e63652d31000000000000000c617661696c6162696c6974790000000000000001000000000000001c7465726d696e616c2d70726f76696465722d65766964656e63652d31000000000000000e707265636f6e646974696f6e2d310000000000000020540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28000000000000002035f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c0000000000000014323032362d30392d30315430303a30303a30305a000000000000000c617661696c6162696c697479
NESTED_PROVIDER_EVIDENCE_SHA=8983d7f08de52ab98310c0db1eafbfff46688b48caa92b9e52abef69319b4094
NESTED_PROVIDER_EVIDENCE_FIELDS=schema_version=1,domain=NBF06-PROVIDER-EVIDENCE-NESTED-V1,observation_id=obs-evidence-1,retryability_class=availability,exhausted_attempt_count=1,terminal_provider_evidence_id=terminal-provider-evidence-1,precondition_identity=precondition-1,provider_epoch_identity=540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28,provider_failure_key=35f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c,observed_at=2026-09-01T00:00:00Z,provider_failure_class=availability
NESTED_NEGATIVE_FIXTURES=missing_provider_epoch_identity(245,5833944cbb69cdf6ed837f1c9adb6914ff151b7c1b5c41ff5544f3344af75215)|unknown_nested_member(310,541c2f05fb5bc1658aaa949b2c7fc60485deace53bf7aca5005d25a24f1fe590)|conflicting_nested_provider_failure_key(285,c781a9c85af03e85a509a2ba921094f2a3439489297f0f7d311f2ddd66328f52)|top_level_alias_mismatch(PRECOMMIT_EVIDENCE key bytes replaced by aa*32;656,2914faedea361bfbe815093f6fb95fe373290d52518f9a91e1b308992967d9aa)|unknown_nested_version(285,09f9d115122b3312f898c000240a9e4c40bbdaf8d559683f5009627e6663e21f)
NESTED_NEGATIVE_MUTATIONS=missing_provider_epoch_identity=delete ordered member 8;unknown_nested_member=append U64BE(17)||"unexpected_member";conflicting_nested_provider_failure_key=replace ordered raw32 key with aa*32;top_level_alias_mismatch=replace outer provider_failure_key raw32 at byte offset 265 with aa*32;unknown_nested_version=replace schema_version U64BE(1) with U64BE(2)
```

Provider recovery has one canonical NBF-01 bridge. The V2
`provider_recovery_verified` payload is transport evidence, not a second
precondition authority: after the exact passed probe lease is closed, the
locked seam calls `arnold_pipelines/megaplan/incident/schema.py:produce_provider_recovery_verified`
with typed provider-recovery source handles and the cited evidence event.
`provider_failure_key_before` and `provider_failure_key_after`,
`before_content_id`/`after_content_id`, and `evidence_digest` are all derived
from authoritative snapshots/evidence (the recovery keys must be equal),
while plan/phase/logical-dispatch/admission/epoch/route/closed-lease links are
carried in the evidence snapshot. The producer assigns the canonical identity
and fixed `provider_probe:1`; the sole writer is
`arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_changed_precondition`,
exactly once. `consume_changed_precondition` is the single-use locked CAS
consumed by the atomic child reservation and recorded in
`authorizing_event_id` plus `consumed_changed_precondition_event_id`. A decoder
cannot mint this event from hashes or V2 bytes; an uncommitted/unconsumed
event, open/foreign lease, mismatched key/evidence/parent/epoch, replay
conflict, or cycle rejects and remains held.

The complete live-field conversion is closed: `schema_version` is checked as
the adapter-version gate; `kind→result`, `launch_state`, `plan_id`, `phase`,
`logical_dispatch_id`, `admission_receipt_id`,
`semantic_dispatch_fingerprint→fingerprint`, and `selected_spec` are mapped.
`reservation_event_id` is not a live `DispatchOutcome` field: it is supplied
only by the accepted `dispatch_with_admission` reservation context, and a
missing or mismatched context rejects. Nested
`provider_evidence.provider_failure_key` is authoritative; top-level
`provider_failure_key` is an optional compatibility alias that must match or
reject. `retryability_class→retryability` is the sole retryability alias;
missing, unknown, or conflicting values reject. `dispatch_family_id`,
`worker_identity`, `provider`, route-liveness fields, timestamps, success/
terminal payloads, disposition, reconciliation ID, and terminal-event ID are
transport or postcommit metadata ignored by the precommit wire. Typed staged
IDs remain `None` and are omitted from the precommit payload; explicit
U64BE(0) null is used only where a schema declares a nullable field. A
not-started or ambiguous outcome remains typed refusal/no-launch and cannot
bypass conversion, create precommit evidence, resolve a target, or launch.

The generic recovery boundary is explicit: typed `provider_exhausted` is
intercepted at the NBF-02/T8 seam after the sole terminal append and before
generic breaker or blocked accounting. `arnold_pipelines/megaplan/orchestration/phase_result_classify.py:classify_dispatch_outcome`
and `classify_external_error_payload` are lossless typed adapters only;
`arnold_pipelines/megaplan/orchestration/recovery_policy.py:RecoveryPolicy.classify`
and `classify_with_circuit` remain the generic owners for non-T8 outcomes,
including repeated `internal_error`. Signal/disposition authority remains
`arnold_pipelines/megaplan/incident/disposition.py:record_disposition` and
its `record_before_signal`, `_ladder_terminal`, `_record_ladder_stage`, and
`recover_worker_disposition_outcome` terminal-projection helpers; those helpers never
write an NBF-06 terminal, observation, or route. No compatibility delegate
may bypass T8 into a second breaker, terminal, observation, or route writer.

Planned deliverables are owned at the packet boundary: NBF-01 owns shared
schema codecs/inverses and `WorkerAdmissionReceipt`; NBF-06 owns provider
vectors, `scripts/check_nbf06_a38.py`, and
`tests/arnold_pipelines/megaplan/fixtures/nbf06_a38`; NBF-07 invokes that
checker during final validation. The script and fixture paths are expected to
be absent before implementation and are not a present-gate failure. Absent
future A01–A38 tests, the checker, and negative fixtures are therefore not
required to pass this packet validation; they become implementation and
final-validation obligations after NBF-06 is built.

### Provider route decision and configured vocabulary

The one pure selector is the exact signature
`arnold_pipelines/megaplan/orchestration/provider_resilience.py:select_provider_route(request, ledger_view)`.
It is called only by the dispatch seam with a typed immutable request and
`ProviderLedgerView`; it is pure and has no append, launch, cache, lock, or
observation side effect. Its
closed union is `Hold`, `Probe`, `PreToolNextTarget`, `SameRouteRecoveryChild`,
`PostTerminalConfiguredFallbackChild`, `ReturnPrimary`, `Noop`, `Refusal`, and
`DurabilityUnknown`. The configured post-terminal child is a cross-family
composite door, not a pre-tool selector. `PreToolNextTarget` is the only
pre-tool target choice and contains only `source_admission_receipt_id`,
`target_index`, `target_family`, `target_normalized_spec`,
`target_epoch_claim_digest`, `target_epoch_binding_digest`, and
`target_admission_proof_digest`; it cannot carry post-terminal observation or
child fields. The selector never appends, launches, or mutates. The
locked applier validates all source/target receipt, key, epoch, chain,
evidence, reservation, and door fields and calls only named `_locked` ledger
methods. `serialize_provider_route_proposal` and its inverse are the sole
route-proposal codec. `reserve_provider_route_child` is the sole locked durable
route-transition writer; `reserve_provider_route_locked` and
`append_provider_route_decision` are not NBF-06 authorities and must not be
called or imported by this policy.

`select_provider_probe` is a pure adapter over the same immutable parent
`ProviderLedgerView`, not a second selector. Its typed request must carry and
match the parent admission receipt, reservation event, configured-chain
identity, provider-failure key, provider epoch identity plus claim/binding
digests, route-liveness/fence identity, and the single-use probe lease fence.
It returns only a typed probe request; it cannot choose a route or target,
launch a client/worker, create a child, or append durable state. The request
serializer/inverse ends before `record_provider_probe_result_locked`; only
that locked result writer may persist the executor result, and mismatched or
missing parent bindings fail closed.

`ReturnPrimary` is a locked source-target composite door. It validates the
source terminal/observation/receipt, source failure key, source epoch and
family/spec against the parent, then independently validates the target
primary family/spec, target failure key, target epoch claim/binding, target
admission proof, and return proof. Source identity is never inherited as the
target identity; the matrix's `RETURN(510)` fixture is the literal replay case.

`_advance_configured_spec_fallback` is the only configured chain vocabulary
and authority. It normalizes persisted forms, records canonical origin bytes,
source/profile/parser identity, selected index, and chain identity. Scalar
presence suppresses ambient fallback. `execute` and `loop_execute` raise the
sole `arnold_pipelines/megaplan/fallback_chains.py:ExecuteFallbackUnsafe` before a second resolution,
metadata patch, client/WBC/RPC call, or worker launch; the refusal is carried
through broad exception handling as typed transport. Other paths delegate and
cannot repair `AgentMode` or construct a target.

### Probe and recovery

`start_provider_probe_locked`, `record_provider_probe_result_locked`,
`close_provider_probe_locked`, and `reconcile_provider_probe_locked` use
`ProbeExecutor.run(request, deadline, cancellation_token)` with an injected
clock. The frozen `probe_status` projection states are exactly
`none|leased|passed|failed`;
executor results are `passed|failed|unknown`, and unknown/expiry reconcile to
the existing held/unresolved (`failed` projection) state rather than adding a
new enum. The existing `retry_not_before` and executor `deadline` are integer
nanoseconds from the injected monotonic clock (`MonotonicClock.now_ns()`), and
the only derivation is
`retry_not_before_ns=max(parent_retry_not_before_ns,terminal_observed_ns)`;
the lease deadline is the supplied executor deadline, which must be
`deadline_ns >= retry_not_before_ns`. Eligibility is inclusive
`now_ns >= retry_not_before_ns`; expiry is inclusive `now_ns >= deadline_ns`.
There is one bounded lease and one single-use close/reconcile CAS. Before the
deadline the result is held; at the exact deadline the one CAS winner closes
the lease, and after it a late result is held/unresolved. A monotonic clock
rollback or ambiguous jump never authorizes a lease; a forward jump applies
the same inclusive boundary. Probe execution
occurs outside the ledger lock, then a fenced CAS records the typed result. A
failed, unknown, or expired probe launches nothing, does not mutate the streak,
and cannot authorize a child. A passed result is still open until
`close_provider_probe_locked` performs the exact single-use close CAS; only a
passed closed lease may produce `provider_recovery_verified`, and that closed
proof must be consumed before `reserve_provider_route_child` runs.
Passed-but-open, duplicate-close, late, duplicate, unknown, or expired results
remain held/unresolved and cannot authorize recovery, a child, a route, or a
launch. Close/recovery/child retries return the existing proof/event by parent
and digest rather than allocating another record.

The probe clock contract uses only existing fields: `retry_not_before` and
executor `deadline` are unsigned integer nanoseconds from injected
`MonotonicClock.now_ns()`; UTC is evidence-only. The exact derivation is
`retry_not_before_ns=max(parent_retry_not_before_ns,terminal_observed_ns)` and
the supplied executor `deadline_ns` must satisfy
`deadline_ns >= retry_not_before_ns`. Ledger-lock reconciliation checks the
lease/parent/key/epoch/route/attempt fence, replays an already closed record,
accepts an explicit result only while `now_ns < deadline_ns`, and then applies
inclusive expiry at `now_ns >= deadline_ns`. Unknown/conflict closes as
held/unresolved (`probe_status=failed`) without streak or retry mutation; only
exact byte reconciliation may resolve it. Boundaries are
`(99,100,200)→held/no_lease`, `(100,100,200)→one_lease_CAS`,
`(199,200)→result_accepted`, `(200,200)→expired_close/no_launch`,
`unknown@150→durability-held/no_retry`, `late@201→held-unresolved/no_write`,
and backward sample `90` after `100`→held/no_authorization. A passed result
requires close CAS and then single-use recovery consumption; it never
authorizes a child directly.

## Additive NBF-01 handoff

NBF-01 remains the owner of `arnold_pipelines/megaplan/incident/schema.py` generic event codecs,
`WorkerAdmissionReceipt`, canonical `worker_terminal_outcome` and its sole
physical writer `IncidentLedger.append_terminal_outcome`, lock/CAS,
and the physical ledger. NBF-06 requests additive provider codecs and fields
through that owner; it does not redefine classes or append paths. NBF-06 owns
`arnold_pipelines/megaplan/orchestration/provider_resilience.py`, adapter integration, provider fixture
and policy tests. Old ordinary records deserialize as ordinary, legacy
provider records never upgrade by inference, and unknown/torn records remain
held/unresolved. Cloud transports canonical receipt bytes but does not derive
IDs.

## Fixture registry and migration

The authoritative literal registry is in the matrix. Every event/branch
fixture uses U64BE-framed UTF-8/NFC text and raw 32-byte digests; the one
exception is the NBF-01 `ProviderFailureKey` canonical sorted-JSON codec.
All fixtures use explicit `null` versus omission and a version/domain tag.
Current vectors (length, SHA-256) are:

| Fixture | Ordered fields / sample | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| chain | `domain,phase,parser,origin,origin_digest,spec_count,specs`; `run`, `NBF06-PARSER-V1`, `omp:deepseek/deepseek-chat` | 175 | `4fd9bda5df6d1e33879fb46cdb5e92cd86c19d802a67b14d7b14269df663ab25` |
| precommit adapter evidence (supersedes 363-byte vector) | outer fields plus one framed `nested_provider_evidence` carrying the complete lossless nested record; no postcommit ledger IDs | 656 | `93abaf0c39d87ed58fd62c901f45e6d11320b139534dbfab26336f898b74cb25` |
| precommit `DispatchOutcome` bridge (supersedes 351-byte vector) | live fields explicitly mapped/re-encoded and nested evidence preserved as framed bytes under `NBF06-DISPATCH-OUTCOME-BRIDGE-V1` | 644 | `71574e243d25afed41c8c2636968bc35c79b8a0d99f59f479f3f8e320fc40384` |
| postcommit provider envelope | precommit fields plus terminal/observation linkage; chain raw32-or-explicit-null; epoch raw32 | 393 | `e579db42c62a9e5560211193f45961b7325dd743c37040157577b255fa795363` |
| failure key | NBF-01 `ProviderFailureKey.derive` canonical JSON uses lowercase-hex display of source raw epoch `540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28` | 205 | `35f30d3d84bfed63905458c7ab3a5e34d491e61c88af513ebe1e12e7814b905c` |
| epoch identity | `NBF06-PROVIDER-EPOCH-ID-V2:domain,family,normalized_spec,provider_epoch_generation`; liveness/membership are fencing evidence only | 93 | `540c8db6d9f7e40a162f06aa6ff1c9e6a6be3c031378e77346f192b9657cbf28` |
| epoch claim | `domain,version,identity,family,spec,liveness,liveness_digest,membership_digest,provider_epoch_generation,claim_digest` | 280 | `f4028a7a2850021c459f64df2308423747a89e34ceb36fc6054d31a0352c594f` |
| epoch binding | `domain,claim_digest,reservation,admission,identity(raw32),binding_digest` | 199 | `9c86a3449a8c3666a9a77f838dd0c717c15c0e34ac1df89904b6cc87e8ae37ec` |
| observation | `domain,terminal,reservation,admission,configured_fallback_chain_identity(raw32-or-explicit-null),key(raw32),epoch(raw32),evidence(raw32),dispatch,result` | 267 | `011d8fb2d42bf5ba0c27a18d64252aa999cf974b5efd3e403cdfa080b6216194` |
| hold | `domain,terminal,observation,admission,configured_fallback_chain_identity(raw32-or-explicit-null),epoch(raw32),key(raw32),evidence(raw32),reason,state` | 253 | `c272a82bd725258e5cac1568b0bae2a3d7de38ad6ba720165b21c9ddf3673ba2` |
| success | same hold order; `reason=provider_success,state=success`; chain=null, epoch/key/evidence raw32 | 258 | `9571aa2db8a820be679cfbba40770007b3dec62ad1971747788997180ba6f71f` |
| child proposal | source reservation/receipt/observation, explicit-null chain, raw source/target keys and epoch/claim/binding/proof digests, target index/family/spec, decision | 475 | `a0322ec6a5cf4b8c65a583c717e3b5e543c71a5a2775b503ce3e0d6c4f22c9c7` |
| child event | proposal linkage plus raw32 `proposal_digest`; source links included; self/event/receipt excluded | 475 | `ecf5bf5602f816752e27f7e921cd188acd236faf49f7b9c1d115c8456147c270` |
| child event identity | `event_id == child_reservation_event_id` is lowercase-hex SHA-256 of child payload including proposal digest, assigned after serialization | 80 | `edbd1c4a77d3486893c9f4bed803356ecc23ea10e9852573449c2aa67d063e52` |
| committed child view | own view domain plus child-event fields, canonical event_id, and derived child receipt; never a ledger event | 581 | `e406af5f60e6a75ac93c574bfaab12de0617ca5e791a67476bbc30c81f936257` |
| recovery branch | terminal, observation, lease, receipt, explicit-null chain, raw key/epoch/evidence/proof | 284 | `64f72fa89c6d7eb745e54466bb9d36e398730e85fa8437ca74c026dd0cd8d8b6` |
| configured branch | source IDs, explicit-null chain, raw source/target key/epoch claim+binding/proof, target index/family/spec, decision | 486 | `abdb020fa2498d4a8463356b0efb9009a15ea1ac948bb01133cc8cf2053ed148` |
| return branch | source and independently derived target fields, raw keys/epochs/claims/binding/proof; explicit-null chain | 510 | `f5e0cb4d2a2fcb0e7c90e9b805d8dd487fc222b355ad9f03cc5ff4ea33560056` |

The matrix contains full literal hex for the principal, child, branch, and
current nested/precommit fixtures. The former 363-byte flattened precommit and
351-byte bridge payloads are superseded by the 656-byte and 644-byte payloads
above; no postcommit ID was added. The
old 452-byte proposal and old committed vector are superseded.

Migration is file-qualified and no-upgrade; every row names both codec directions and preserves field/null/omission, unknown-field rejection, replay, and CAS behavior:

| Input | Codec/inverse | Null/unknown/upgrade/replay rule |
| --- | --- | --- |
| legacy `DispatchOutcome` | `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome.to_dict` ↔ `arnold_pipelines/megaplan/orchestration/phase_result.py:DispatchOutcome.from_dict` | map live kind/launch_state/fingerprint/nested provider evidence; reservation comes from accepted admission context; staged postcommit IDs remain typed `None` and are omitted on precommit wire; unknown rejects; byte replay exact |
| ordinary legacy `event_type=worker_terminal_outcome` / NBF-01 `schema_version=1` | `arnold_pipelines/megaplan/incident/schema.py:serialize_worker_terminal_outcome` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_worker_terminal_outcome` | retain the NBF-01 ordinary domain/version and codec; preserve fields and omission versus null; unknown rejects; never provider-upgraded; replay/CAS exact |
| V1 provider precommit | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_adapter_evidence_precommit` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_adapter_evidence_precommit` | exact precommit fields, raw32 digests, explicit-null chain, no postcommit IDs; unknown rejects; replay exact |
| V1 accepted terminal | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_terminal` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_terminal` | terminal/receipt IDs are postcommit fields; null/omission preserved; unknown rejects; replay/CAS idempotent |
| provider envelope | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_evidence` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_evidence` | terminal/observation links populated only postcommit; raw32 chain/key or explicit null; unknown rejects; replay/CAS idempotent |
| admission receipt | `arnold_pipelines/megaplan/incident/schema.py:serialize_worker_admission_receipt` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_worker_admission_receipt` | NBF-01-owned bytes; raw32 chain or explicit null; omission/null preserved; unknown rejects; cloud replay exact |
| child event | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_event` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_route_child_event` | source linkage IDs included; `event_id == child_reservation_event_id` generated after payload and excluded; derived receipt absent; unknown rejects; CAS/replay exact |
| committed child view | `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_route_child_view` ↔ `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_route_child_view` | canonical event ID and derived receipt are postcommit view fields; null/omission preserved; unknown rejects; replay exact |
| legacy provider terminal | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_terminal` ↔ `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_terminal` | explicit null extension; ordinary/provider class preserved; byte replay only |
| legacy provider observation | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_observation` ↔ `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_observation` | derived IDs/count absent remain null; no inferred count |
| legacy provider hold/success | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_hold_success` ↔ `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_hold_success` | exact parent/state mapping; omission differs from null; no upgrade |
| legacy recovery evidence | `arnold_pipelines/megaplan/incident/schema.py:deserialize_legacy_provider_recovery` ↔ `arnold_pipelines/megaplan/incident/schema.py:serialize_legacy_provider_recovery` | explicit legacy version/nulls; byte-preserving decode/re-encode; read/repair evidence only; no V1 upgrade or inferred proof |
| V2 recovery verified | `arnold_pipelines/megaplan/incident/schema.py:deserialize_provider_recovery_verified` ↔ `arnold_pipelines/megaplan/incident/schema.py:serialize_provider_recovery_verified` | exact passed-and-closed lease plus all parent/evidence fields required; torn/unknown held/unresolved; replay/CAS idempotent |
| torn/unknown/ambiguous | no inverse upgrade | `durability_unknown`; recover before allocation |

## Transition registry and acceptance

The matrix is the authoritative, machine-readable transition registry. Its
full rows bind every version/domain/preimage, exclusion, parent receipt/key/
epoch/evidence, producer, sole writer, replay/CAS result, and literal fixture;
this brief supplies the contract meaning and does not define a competing
transition table.

| Transition ID | Preconditions | Durable result | Forbidden consequence |
| --- | --- | --- | --- |
| `provider_terminal_committed` | accepted structured evidence | one terminal via `arnold_pipelines/megaplan/incident/ledger.py:IncidentLedger.append_terminal_outcome` | no observation ID in terminal preimage; provider wrapper delegates to this writer |
| `provider_observation_link_pending` | terminal committed; fixture `PENDING` (148 bytes, SHA `d74235049b9203ff3e61a735e5c9692a3d481a1b0edd22dd298473c0515b5cbb`) | link intent | no route/launch |
| `provider_observation_committed` | exact terminal/receipt/evidence | one observation/count | no duplicate count |
| `provider_observation_reconciled` | exact stored bytes; fixture `RECONCILED` (266 bytes, SHA `28496dac6588069eb019f6e857c86b469484a723cea13d358919c90b071cf3cf`) | idempotent repair | no inferred IDs |
| `provider_hold_committed` | first matching exhaustion | held/streak one | zero count/child |
| `provider_probe_started` | injected-clock `now >= retry_not_before` + one lease CAS; fixture `PROBE_START` (201 bytes, SHA `d8054a0fefdc74ffff97781446d68fc170a6f2af91a572905f5ba5f0040676f4`) | leased projection | no worker launch |
| `provider_probe_result` | fenced executor result; fixture `PROBE_RESULT` (250 bytes, SHA `ab39697a711bd43a5c8db807521bf1266ce31d5a1fa6e8e3f3d5595d0492a30e`) | passed/failed/unknown | unknown cannot route |
| `provider_probe_closed` | result/expiry; fixture `PROBE_CLOSED` (117 bytes, SHA `6ae9a2be782658def534025342edf8e1853e37f31931fe7fdedc6b092f7a43cc`) | closed lease | no attempt 3 |
| `provider_recovery_verified` | passed result whose exact lease has first been closed by `close_provider_probe_locked` | one recovery proof | no source-key reset or child before closed proof |
| `provider_route_child_reserved` | locked composite door | one `arnold_pipelines/megaplan/incident/ledger.py:reserve_provider_route_child` append: `CHILD_EVENT` (475 bytes, SHA `ecf5bf5602f816752e27f7e921cd188acd236faf49f7b9c1d115c8456147c270`) has proposal digest and no receipt; postcommit `CHILD_VIEW` (581 bytes, SHA `e406af5f60e6a75ac93c574bfaab12de0617ca5e791a67476bbc30c81f936257`) derives receipt | receipt-bearing event rejected; route proposal/decision writers are not separate |
| `provider_success_committed` | exact parent | matching-key reset | no observation/child |
| `provider_durability_unknown` | torn/unknown result; fixture `UNKNOWN` (189 bytes, SHA `6a700ce3c087b32546db3caf9e6005555556a29bbf2afdb9b7b52edc52909522`) | permanent/reconcilable hold | no launch/signal |
| `configured_chain_refusal` | malformed/cross-family/unsafe | typed refusal | no second target |
| `provider_return_primary` | exact source/target composite proof and identities; fixture `RETURN` (510 bytes, SHA `f5e0cb4d2a2fcb0e7c90e9b805d8dd487fc222b355ad9f03cc5ff4ea33560056`) | one return branch | no source identity inherited as target; no historical widening |

The matrix's A01–A38 commands are the acceptance registry. Its A38 section has one
file-qualified row for every serializer and inverse plus producer→transport→
consumer→locked-applier→write edges; generic `append_event` remains denied. Required outcomes
include one terminal writer, one observation writer, one child reservation
writer, byte-identical replay, exact A38 allowlist, and zero policy edges to
NBF-04/05/NBF-08. The final checker must print:

The A32 aggregate is fail-closed: PASS is the conjunction of all three named
standalone commands collecting and passing their exact tests with
pre-resolution/no-side-effect refusal evidence. Missing collection, skip,
xfail, error, or any nonzero result is FAIL; an aggregate green result alone
cannot substitute for a missing door. The three A32 commands and the A38 checker are standalone, fail-fast
processes; they are never joined with shell separators or loops. The canonical
commands intentionally omit `timeout(1)` because it is not portable across
macOS/POSIX environments and `pytest-timeout` is not a declared dependency;
an invoking harness may supply a bounded timeout.

```text
A38 checker: ALLOWLIST PASS; forbidden=0; negative_fixtures=PASS
```

Implementation slices are: additive NBF-01 codecs/locked APIs; pure selector
and locked applier; structured adapter/projection/replay integration; strict
configured-chain and execute/loop refusal wiring; and deterministic vectors,
crash, race, migration, epoch, receipt-tamper, and probe tests. A changed
vector, command, row, or ownership edge requires a new adjudication/rewrite,
not an amendment appended to this contract.
