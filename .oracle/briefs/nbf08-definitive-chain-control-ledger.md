# NBF-08 — Definitive chain-control ledger

## Status and intent

This brief defines the next epic suffix after NBF-06 and before the current
NBF-07 finalizer. It turns chain-control history from a collection of mutable
snapshots and best-effort projections into a definitive, replayable, tamper
evident operation history. It is implementation guidance, not an instruction
to alter the current tasklist, status, source tree, or active run.

The implementation must extend the existing physical incident ledger rather
than introduce another journal, root, lock, sequence, signal authority, or
parallel event store. The new API is a typed `ChainControlJournal` facade over
the existing `IncidentLedger` `events.jsonl` and lock. Chain-control records
are a typed `chain_control.*` suffix in that ledger, with their own schema and
projection rules but the same physical serialization authority.

NBF-08 depends on NBF-01 through NBF-06. It executes before the current NBF-07
finalizer. A later authorized suffix rebind must change NBF-07's dependency to
include NBF-08; this brief does not edit the tasklist or perform that rebind.

## Settled Decisions

- **SD-001** — Extend the existing IncidentLedger events.jsonl and lock through a typed ChainControlJournal facade; create no second journal, root, lock, sequence, or signal authority. _load_bearing: true_
- **SD-002** — Chain-control events form a hash-chained chain_control suffix anchored to the accepted incident prefix tip and digest. _load_bearing: true_
- **SD-003** — File-backed ledger authority is explicit per run; DB records are projections unless an authority-selection event explicitly selects DB authority. _load_bearing: true_
- **SD-004** — Strict readers turn malformed, forked, duplicate, ambiguous, missing-anchor, or mismatched records into typed holds and never infer a cursor or success. _load_bearing: true_
- **SD-005** — Accepted, rejected, CAS-conflict, tamper, intent, claim, result, and reconciliation events are durable evidence. _load_bearing: true_
- **SD-006** — Actors and operation IDs are stable, minimally identifying, and redacted; secrets, prompts, raw provider content, and arbitrary user data never enter the journal. _load_bearing: true_
- **SD-007** — Domain ledgers remain separate and cross-reference the chain operation ID rather than being copied into a second journal. _load_bearing: true_
- **SD-008** — A chain operation commits its journal event and authoritative local-state transition under one lock/CAS boundary, or records an unresolved hold; no lock gap may imply success. _load_bearing: true_
- **SD-009** — Legacy history is imported only through deterministic genesis or suffix-rebind evidence; ambiguity becomes a hold and is never treated as an accepted prefix. _load_bearing: true_
- **SD-010** — Snapshots and projections are derived evidence; the strict reader reconstructs semantic state from accepted chain-control events and verifies every projection identity. _load_bearing: true_
- **SD-011** — Config, source, anchor, ticket, feedback, runtime, and backend digests are captured at admission and on active-chain rebound while content histories remain in their domain stores. _load_bearing: true_
- **SD-012** — NBF-08 covers control and authority evidence, not conversational, provider, or raw log content; pure reads remain outside chain mutation history. _load_bearing: false_

## Problem and current evidence

The current implementation has several useful but non-definitive histories:

- `chain/spec.py:2247` atomically writes mutable chain state and then appends a
  non-fatal projection. The state JSON remains authoritative; a projection
  failure can leave the operation without durable chain history.
- `chain/epic_chain.py:355` persists parent epic-chain state independently,
  without one shared append-only operation sequence.
- `.chains/projections`, supervisor state, runtime markers, and incident
  bridges are supplemental or best effort.
- `observability/events.py` provides per-plan `events.ndjson`, but it is not a
  chain-wide authority and may lack a run context.
- `store/_db/operations.py` provides idempotent control messages and claims,
  while file and DB stores remain separate histories.
- `resident/schedules.py:786` has append-only schedule definition receipts,
  but occurrence transitions are not chain operations by default.
- Cloud markers and launch outcomes, bakeoff state/WBC evidence, migration
  records, and source documents each have their own identity model.

This leaves user-visible controls with no definitive, cross-surface answer to
“who changed the chain, from which state, using which authority, and what was
the result?” The most important gaps are active-plan commands invoked outside
the chain runner, blocked/committed resets, cloud and scheduled controls,
bakeoff merges, backend cutovers, configuration rebinding, and manual/admin
state mutation.

## Architecture

### Physical authority

Add a typed facade in the incident package, preferably alongside the existing
ledger/schema modules:

```text
ChainControlJournal
  -> IncidentLedger events.jsonl
  -> IncidentLedger lock / sequence / append / replay primitives
  -> typed chain_control.* schema and verifier
```

The facade must accept an explicit authority context containing chain ID,
operation ID, actor class, run ID, parent/child relation, source/spec identity,
expected cursor and revision, and authority mode. It must never infer a chain
from the current working directory, an ambient environment variable, an
unbound plan name, or a first matching record.

For each run, the first accepted chain-control event records the physical
ledger root, authority mode (`file` initially), accepted prefix tip event ID,
prefix digest, schema version, and chain-control sequence. The next
`chain_control.*` event includes `previous_chain_control_event_id`,
`previous_chain_control_digest`, and a canonical payload digest. A reader
verifies the incident prefix, the suffix anchor, every suffix link, monotonic
sequence, event ID uniqueness, and operation idempotency before returning a
cursor.

DB rows may mirror events for querying, but a DB projection mismatch is a
projection failure/hold, not an alternate truth. If DB authority is ever
enabled, it requires a separately recorded authority-selection event and the
same lock/CAS and hash-chain invariants.

### Operation lifecycle

Every mutating operation follows:

```text
intent -> authority validation -> CAS/claim -> state effect -> result
                                      \-> reconciliation/hold on uncertainty
```

The implementation may combine events transactionally where the existing
ledger supports it, but must retain typed evidence for the intent, claim,
result, and any external effect. A crash between an external effect and its
result leaves `reconcile_required`, never a fabricated success. Replay of an
already committed operation returns the exact prior result and emits at most a
typed replay reference, without repeating the external effect.

### Canonical event taxonomy

At minimum implement these event kinds:

- `chain_control.genesis_accepted` — establishes prefix tip, authority mode,
  schema, and initial source/config/runtime identities.
- `chain_control.authority_selection` — selects or explicitly changes the
  authority mode/identity under a validated selection or cutover precondition.
- `chain_control.suffix_rebound` — closes one verified suffix identity and
  binds its successor; it changes authority metadata but never advances a
  milestone or infers execution success.
- `chain_control.legacy_imported` — imports a deterministic legacy prefix;
  includes source paths, hashes, importer version, and ambiguity verdict.
- `chain_control.intent` — requested operation and expected precondition.
- `chain_control.authority_validated` — validated source, actor, runtime,
  cursor, and permission identities.
- `chain_control.claimed` — single-use operation claim/idempotency ownership.
- `chain_control.committed` — authoritative state transition and post-state
  hash.
- `chain_control.rejected` — invalid target, policy, identity, cursor, or
  permission, with no state effect.
- `chain_control.cas_conflict` — stale revision/cursor or competing claim.
- `chain_control.tamper_detected` — state, marker, projection, or journal
  mismatch; includes evidence hashes and enters hold.
- `chain_control.external_effect_intent` / `external_effect_result` — cloud,
  provider, scheduler, signal, Git, or deployment effect and its receipt.
- `chain_control.reconcile_required` / `reconciled` — crash or uncertain
  external result and the authoritative resolution.
- `chain_control.source_rebound`, `config_rebound`, `runtime_rebound`, and
  `backend_rebound` — deliberate identity change with before/after digests.
- `chain_control.replay` — idempotent repeat resolved to an existing operation.
- `chain_control.hold` / `hold_released` — unresolved authority or migration
  state, requiring explicit evidence to release.
- `chain_control.sequence_reserved_tombstone` — closes a durable physical
  sequence reservation after an append crash; it is physical evidence only.

The semantic reducer has a frozen eligibility table. `genesis_accepted` and
`legacy_imported` initialize semantic state at sequence zero. The following
accepted events advance `semantic_sequence` exactly once after validating
their pre/post semantic digests: `authority_selection`, `suffix_rebound`,
`committed`, `reconciled`, `hold_released`, `source_rebound`, `config_rebound`,
`runtime_rebound`, and `backend_rebound`. `intent`, `authority_validated`,
`claimed`, `rejected`, `cas_conflict`, `tamper_detected`,
`external_effect_intent`, `external_effect_result`, `reconcile_required`,
`replay`, `hold`, and `sequence_reserved_tombstone` advance only
`evidence_sequence`. An accepted event with no semantic pre/post change is
still evidence and must be marked `semantic_effect=no_change`; callers cannot
choose eligibility by label. `authority_selection` changes only authority
metadata; `suffix_rebound` changes authority/suffix identity and leaves the
lifecycle/milestone cursor unchanged. Both require exact old-tip CAS and
replay to the same result.

The common envelope includes `schema_version`, `event_id`, `event_kind`,
`operation_id`, `causation_id`, `correlation_id`, `recovery_id`, `chain_id`,
`parent_chain_id`, `child_id`, `run_id`, `actor` (redacted stable ID and
class), `authority_mode`, `ledger_id`, `created_at`, `physical_sequence`,
`evidence_sequence`, `semantic_sequence`, `previous_physical_digest`,
`previous_evidence_digest`, `payload_digest`, `event_hash`, `intent`,
`semantic_effect`,
`expected_cursor`, `expected_revision`, `actual_cursor`, `actual_revision`,
`pre_state_digest`, `post_state_digest`, `source_identity`, `spec_identity`,
`config_identity`, `runtime_identity`, `linked_receipts`, `outcome`, and
`failure_class`. Payloads are canonical JSON with sorted keys and normalized
paths; timestamps are evidence fields, not identity inputs.

## Surface coverage

### Chain and epic chain (authoritative)

Cover local chain start/resume, milestone advance, retry, skip, pause,
completion, failure, invalid jump, cursor reconciliation, child selection,
epic-chain parent/child start and completion, and all `save_chain_state` /
`save_epic_chain_state` callers. Parent and child operations share linked IDs
and independently verify their cursors. A direct mutable save without an
operation context must fail closed or produce `unattributed_state_change`.

### Cloud and supervisor (authoritative control, linked runtime evidence)

Cover cloud chain start, resume, pause/resume-chain, retire, reset, down,
destroy, sync, supervise/repair, launch/relaunch, runtime rebind, and cutover.
Reset must journal the request, reference census, blocked/clear verdict, and
every deletion or preserved state. Cloud markers, provider receipts, and
supervisor lifecycle logs remain linked evidence. `status`, `logs`, `attach`,
`preflight`, `doctor`, `audit`, `trace`, and `introspect` are pure reads.

### Active plan and operator controls (authoritative when chain-bound)

Link override actions (`abort`, `adopt-execution`, `cutover`, `replan`,
`recover-blocked`, `resume-clarify`, force-proceed, profile/model/vendor/
robustness changes), `auto`, standalone phase commands, and control-message
application. The chain identity must be explicit; an unbound invocation may
operate only in the existing plan domain and must not alter a bound chain.

### Configuration and source material (snapshot/rebind)

Global config `set`, `use-profile`, and `reset`, project profile/config changes,
brief/anchor/strategy/ticket/feedback edits, and source migration remain in
their own histories. At chain admission and materialization, capture effective
config/profile/vendor/model/robustness, chain/spec/brief/anchor/strategy/ticket/
feedback digests. Active-chain changes require an explicit rebound event;
unmaterialized future content is admitted only with a new source identity.

### Scheduling and control queues (linked domain authorities)

Keep schedule definition and occurrence journals, Store control-message claim /
process/recovery records, and job/run histories as separate authorities. Every
chain-affecting occurrence or message must carry `chain_operation_id`,
`chain_event_id`, schedule/occurrence/job/message IDs, idempotency key, and
result. Recovered stale messages and rejected targets are chain evidence when
they concern a bound chain.

### Bakeoff and candidate integration

Bakeoff profile execution, comparison, and judge telemetry remain in the
bakeoff ledger. `pick` and `merge` are chain operations when their winner is
used by a chain: record experiment ID, base SHA, winner/profile, patch or doc
digest, actor, clean-tree proof, and merge receipt. A merge outside a chain
does not pollute chain history.

### Store, migration, provider, incident, and deployment

Store transactions, DB/file backend migrations, resident provider sessions,
incident disposition/confirmation/terminal events, WBC, Git commits, and
deploy receipts retain their specialized schemas. Cross-reference them from
chain operations. Backend migration or authority cutover must record old/new
backend identities, snapshot hashes, migration run ID, and reconciliation
result. Signal events are not duplicated by chain-control events.

### Manual, plugin, and admin mutation

Audit direct JSON/marker writes, direct Store calls, plugin actions, admin
tools, and SQL paths at the API boundary. For chain-bound objects, require an
operation context or emit a durable `unattributed_state_change` and hold the
chain. Pure diagnostics and read-only searches remain outside the ledger.

## Staged implementation and ownership

1. **Primitive and schema seam — NBF08-S1.** Own the typed envelope,
   canonicalization, redaction, hash-chain verifier, authority context, and
   facade in `incident/ledger.py`, `incident/schema.py`, and a focused
   `incident/chain_control.py` module. Reuse the existing ledger lock and
   append/CAS primitive. Add no second physical store.
2. **Reader, genesis, and migration — NBF08-S2.** Implement strict replay,
   accepted-prefix anchoring, deterministic legacy import/rebind, ambiguity
   holds, projection checks, and idempotent replay. Own migration utilities and
   tests, not ad-hoc repair scripts.
3. **Local and epic chain wiring — NBF08-S3.** Instrument
   `chain/spec.py`, `chain/epic_chain.py`, `chain/operator_pause.py`,
   `chain/execution_binding.py`, occurrence adoption/join, target rebind,
   seed rematerialization, and cursor reconciliation. Every mutation receives
   expected cursor/revision and operation context.
4. **Plan/operator/config/source wiring — NBF08-S4.** Instrument override and
   control handlers, `auto.py`, CLI config/profile use, source/anchor
   materialization, and active input rebind. Preserve separate domain logs.
5. **Cloud/supervisor/schedule wiring — NBF08-S5.** Instrument cloud CLI
   lifecycle/reset/sync/repair, supervisor transitions, resident control
   messages, schedules, occurrence launches, and cloud-run receipts.
6. **Bakeoff/store/admin boundaries — NBF08-S6.** Link bakeoff pick/merge,
   Store migrations, backend cutover, plugin/admin paths, and direct-write
   detection. Add explicit chain-bound operation context to public APIs.
7. **Projection and rollout — NBF08-S7.** Add DB/query projections and
   derived snapshots, replay/audit CLI surfaces, metrics, and staged legacy
   migration. Keep file authority explicit until a separately authorized
   authority selection exists.

Suggested ownership files are the existing `incident/*`, `chain/*`,
`cloud/cli.py`, `cloud/operator_control.py`, `cloud/incident_bridge.py`,
`supervisor/*`, `resident/profile.py`, `resident/schedules.py`, `control.py`,
`auto.py`, `cli/__init__.py`, `handlers/override.py`, `briefs.py`,
`bakeoff/{state,lifecycle,merge}.py`, `store/*`, and new focused tests under
`tests/arnold_pipelines/megaplan/` and `tests/cloud/`. Avoid changing NBF-04/
NBF-05 signal helper ownership except to add operation links at their existing
seams.

## Migration and rollout

1. Freeze the candidate and record the exact IncidentLedger prefix tip,
   schema/version, chain state, epic state, markers, plan state, and source
   digests.
2. Run a read-only verifier over all candidate ledgers and classify each chain
   as clean, legacy-importable, or held. Never infer a clean prefix from a
   mutable snapshot alone.
3. For clean histories, append one deterministic genesis/import event anchored
   to the accepted incident tip. For ambiguous histories, append only a hold
   report and require operator resolution.
4. Enable local chain and epic-chain writes behind an explicit feature/authority
   mode. Verify replay from the journal against derived snapshots before
   allowing continuation.
5. Add cloud/resident/schedule/operator links, then bakeoff/store/admin links.
   Roll back by disabling new consumers; never delete accepted events.
6. Reconcile DB projections from the file authority, verify hashes and counts,
   and expose divergence as a hold. Only after NBF-08 acceptance may the
   authorized NBF-07 suffix rebind update dependencies and finalization inputs.

## Invariants and failure semantics

- One physical ledger, lock, sequence, and append authority.
- Every accepted mutating chain operation has exactly one stable operation ID,
  an accepted intent/claim, a result or explicit reconciliation hold, and a
  linked authoritative state digest.
- A stale cursor, revision, spec, source, config, runtime, actor, or backend
  identity produces rejection/CAS conflict, never an implicit merge.
- Hash-chain forks, missing events, duplicate IDs, invalid transitions,
  projection divergence, and manual mutation produce tamper/hold evidence.
- Persistence failure prevents external chain-affecting effects where the
  effect can be gated; otherwise it records `reconcile_required` and never
  claims success.
- Replay is idempotent and returns the existing result; it does not relaunch,
  re-signal, re-merge, re-delete, or re-advance.
- Parent/child, schedule/occurrence, control-message, cloud-run, bakeoff,
  migration, and domain receipt links resolve to exactly one matching identity.
- Redaction is deterministic and irreversible; secrets and arbitrary content
  never become journal payloads.

## Exhaustive test plan

Test the facade and verifier with canonical event vectors, hash-chain tamper,
fork, truncation, duplicate, out-of-order, missing-anchor, redaction, and
legacy ambiguity fixtures. Test idempotent intent/claim/result replay and
crash windows around append, CAS, state write, projection, and external effect.

Test local and epic-chain start/resume/pause/retry/skip/advance, invalid jumps,
parent-child linkage, reset/retire/destroy, source/config/runtime/backend
rebind, occurrence adoption, seed rematerialization, and concurrent stale
cursor writers. Include direct mutable-save and manual-file/DB mutation tests.

Test plan overrides, `auto`, standalone phase controls, control-message claim
and stale recovery, schedule-triggered starts, cloud pause/resume/reset/sync/
destroy, supervisor recovery, marker replacement, and provider/session
receipt linkage. Test pure reads remain side-effect free.

Test bakeoff pick/merge linkage, Store migration/cutover, file/DB projection
rebuild, plugin/admin API context enforcement, redacted actor identity,
operation ID collisions, and cross-chain/cross-reservation rejection.

Required checks include focused pytest suites for every stage, Python compile,
static inventory/no-bare checks, strict journal replay, deterministic
source/input manifests, DB projection verification where available, and
concurrency tests that prove one accepted operation and one state transition.

## Hardened wire contract

### Physical, evidence, and semantic cursors

The incident ledger has one physical append sequence. `physical_sequence` is
the position assigned by `IncidentLedger` while holding its existing lock and
is strictly increasing across incident, signal, and chain-control events.
Chain-control events may therefore be interleaved with ordinary incident
events. They carry two additional, deliberately distinct per-chain cursors:

- `evidence_sequence` increments for every `chain_control.*` evidence event,
  including intent, rejection, CAS conflict, tamper, hold, replay, and
  external-effect records.
- `semantic_sequence` increments only for accepted control events eligible to
  affect the chain's semantic state. Rejected, held, replay-only, and
  diagnostic evidence consumes evidence sequence but does not advance semantic
  sequence.

The cursor forms are `physical_cursor = (ledger_id, physical_sequence,
physical_tip_digest)`, `evidence_cursor = (chain_id, evidence_sequence,
evidence_tip_event_id, evidence_tip_digest)`, and `semantic_cursor = (chain_id,
semantic_sequence, current_child_or_milestone, lifecycle_state, state_revision,
state_digest)`. Genesis records the accepted incident prefix physical tip and
digest and starts both per-chain sequences at zero. Readers verify the prior
physical record/digest and prior evidence event/digest while allowing ordinary
incident records to interleave. Only accepted semantic events enter the
semantic reducer. Forks, gaps, duplicate sequences, or different claimed
interleavings are holds. Any earlier reference to `control_sequence` means
`evidence_sequence` for evidence ordering and `semantic_sequence` for
accepted-only ordering; they must never be collapsed.

### Exact event hash

`event_hash` is domain-separated and independent of wall-clock formatting. Let
`J(x)` be UTF-8 canonical JSON (`sort_keys=true`, separators `(',', ':')`,
`ensure_ascii=false`, no trailing newline), let `U64BE(n)` be exactly eight
unsigned big-endian bytes, and let `F(x)` be an unsigned-64-bit big-endian
byte length followed by UTF-8 bytes. The exact preimage is:

```text
NBF08-CHAIN-CONTROL-EVENT-V1\0
F(authority_mode)
F(ledger_id)
F(chain_id)
U64BE(physical_sequence)
U64BE(evidence_sequence)
U64BE(semantic_sequence)
F(event_id)
F(event_kind)
F(operation_id)
F(causation_id)
F(correlation_id)
F(recovery_id)
F(previous_physical_digest)
F(previous_evidence_digest)
F(payload_digest)
F(J(payload_without_event_hash))
```

`event_hash = SHA256(preimage)`. `payload_digest` is
`SHA256(b'NBF08-CHAIN-CONTROL-PAYLOAD-V1\\0' + J(payload_without_event_hash))`.
The literal separator is one byte `0x00` in every preimage; an escaped
two-character `\\0` is invalid. `created_at` is retained in the envelope but is
not part of either digest. A changed hash algorithm, framing rule, or canonical
JSON rule requires
a new schema version and explicit migration event.

The golden S1 vector must publish the exact UTF-8 preimage bytes (including the
NUL), each framed field length, payload bytes, payload digest, and event hash.
The common envelope must use the same names everywhere:
`authority_mode`, `ledger_id`, `chain_id`, `physical_sequence`,
`evidence_sequence`, `semantic_sequence`, `event_id`, `event_kind`,
`operation_id`, `causation_id`, `correlation_id`, `recovery_id`,
`previous_physical_digest`, `previous_evidence_digest`, `payload_digest`,
`event_hash`, `created_at`, and `payload`. Aliases such as `control_sequence`,
`previous_control_digest`, or a second timestamp-derived identity are invalid.

### Canonical physical-record verification

The physical verifier covers every line in the shared ledger, not only the
chain-control suffix. For each stored record, including an ordinary legacy
incident record, `stored_record_bytes` is the exact UTF-8 JSON line without its
line ending. The physical digest is:

```text
physical_record_digest = SHA256(
  b'NBF08-PHYSICAL-RECORD-V1\\x00' +
  F(ledger_id) + U64BE(physical_sequence) + F(record_type) +
  F(stored_record_bytes) + F_BYTES(previous_physical_digest))
```

`previous_physical_digest` is stored as lowercase ASCII hex but decoded to raw
32-byte digest material before `F_BYTES`; `physical_record_digest` is emitted
as lowercase ASCII hex.

New records use canonical serialized bytes. Legacy records retain their exact
original bytes and receive a deterministic import digest keyed by line number,
byte offset, record type, and accepted prefix tip; they are never silently
re-serialized. Malformed JSON, ambiguous type/sequence, duplicate identity, or
unknown byte boundary is `DURABILITY_UNKNOWN`/hold. S2 must pass both the
physical verifier over ordinary and chain-control records and the semantic
verifier over filtered, accepted-only control events. Passing one does not
imply passing the other.

### Physical sequence allocation and NBF-01 compatibility

The current `_IncidentEventJournal._emit_locked` writes and fsyncs the
sequence sidecar before appending and fsyncing the JSON line. A crash in that
gap can leave the sidecar ahead of the last complete record. S1 must change
the existing primitive, still under the same IncidentLedger lock, to persist a
structured reservation in that sidecar before allocation. If recovery finds a
reserved number with no complete line, it appends a deterministic
`chain_control.sequence_reserved_tombstone` at that physical number and then
marks the reservation committed. The tombstone contains reservation ID,
intended event ID/kind, byte/line boundary, recovery ID, and reason
`crash_before_append`; it participates in the physical digest chain but never
consumes evidence or semantic sequence. Repeating recovery returns the exact
tombstone. A torn tombstone is the only ignored final tail and is retried by
reservation ID; missing/non-final or conflicting records are holds. If this
cannot be made durable, the primitive returns `DURABILITY_UNKNOWN` and blocks
later appends rather than claiming a gap is safe.

The strict NBF08 reader accepts the complete NBF01 physical prefix and its
existing projected semantics, but recognizes only one final incomplete JSON
line as a torn tail. A malformed complete line, malformed non-tail line,
invalid NBF01 payload, sidecar reservation without a matching tombstone, or
non-contiguous physical sequence is corruption/hold. NBF01 records are
ordinary physical records, never chain-control events; their exact stored
bytes are covered by the legacy physical digest adapter. After NBF08 genesis,
all writers, including ordinary incident writers, use the upgraded allocator.
No NBF08 semantic event is accepted until both the NBF01 prefix and NBF08
suffix pass physical verification.

### Mandatory lineage and replay

Every event has non-empty `operation_id`, `causation_id`, `correlation_id`, and
`recovery_id`. A root operation uses its operation ID for causation and
correlation and the literal typed value `none` for recovery. A child event's
causation is the triggering event ID; all events in the operation saga retain
the same correlation ID. Recovery/reconciliation receives a stable new
recovery ID, and replay retains the original operation/correlation IDs while
recording a `chain_control.replay` event causally linked to the existing
result. Idempotency is keyed by `(authority_mode, chain_id, operation_id,
intent_kind, expected_revision)`; a mismatched reuse is a rejection.

Claim rules are explicit. Every accepted state-changing or external-effect
operation (`committed`, `authority_selection`, `suffix_rebound`, all rebound
events, `reconciled`, and `external_effect_intent`) requires one prior
matching `intent` and one single-use `claimed` event. An external-effect result
references that existing claim and does not claim again. The only claimless
evidence classes are `genesis_accepted`, `legacy_imported`,
`sequence_reserved_tombstone`, `rejected`, `cas_conflict`, `tamper_detected`,
`hold`, and `replay`; each still has mandatory lineage and references the
attempted intent/claim or a deterministic request digest. `replay` references
the original claim/result and may not create an effect. A caller cannot omit a
claim by choosing a different event label.

### Local, state, and external-effect atomicity

No implementation may claim a distributed transaction across the file ledger,
chain-state JSON, DB, provider, cloud, process, or Git. Instead, each action
must satisfy three explicit contracts:

1. **Ledger/local-state contract:** under the IncidentLedger lock, validate
   the expected semantic cursor and revision, append intent/claim, perform the
   local state CAS, append commit/result with pre/post digests, and release.
   If state and event cannot be changed atomically, the claim remains an
   accepted `reconcile_required` boundary and the reader blocks continuation
   until it resolves the cutpoint.
2. **Projection contract:** write DB/snapshot projections only after the file
   authority commit, with source event ID/hash and source tip. Projection
   failure is `DURABILITY_UNKNOWN` for the projection, never success or a
   second authority.
3. **External-effect contract:** append `external_effect_intent`, claim it,
   perform the effect, then append result with the external receipt. An effect
   observed without a result is `DURABILITY_UNKNOWN`; an intent without an
   effect may be retried only through the same operation ID and claim.

### Canonical lock ordering and adapter protocol

The only permitted lock order for a chain-bound local transition is:

```text
IncidentLedger sequence lock
  -> sorted chain-scope locks (parent/child by chain_id)
  -> sorted plan/state locks (absolute path)
  -> in-memory CAS/read/write
```

No adapter may acquire a lock above its declared scope, acquire the ledger
lock while holding a chain/plan lock, or call a public writer that reacquires a
lower lock. Parent/child operations sort both IDs before locking; a single
chain uses one scope lock. DB transactions and projections are outside this
lock stack and run only after the file-authority commit. External effects never
run while a local lock is held.

The facade exposes a `LockedChainControlTransaction` containing the locked
ledger records, verified physical/evidence/semantic cursors, and expected
state digests. `ChainStateAdapter` and `EpicStateAdapter` accept that object
and provide only `read_expected()` and `cas_write()`; they cannot append
events or obtain locks. Public `save_chain_state`/`save_epic_chain_state`
wrappers open the protocol once, while internal callers must reject a missing
transaction context. This makes lock order and append/state coupling
machine-checkable and prevents a legacy callback from creating a deadlock.

The required crash table is:

| Cutpoint | Required replay outcome |
|---|---|
| Before intent durable | no claim/effect; safe retry with same operation ID |
| Intent durable, claim absent | claim or reject under CAS; no effect |
| Claim durable, local CAS absent | resolve claim; commit once or `DURABILITY_UNKNOWN` hold |
| Local CAS durable, commit absent | derive exact post-state and append commit, or hold |
| External intent/claim durable, effect uncertain | `DURABILITY_UNKNOWN`; no second effect until receipt/reconciliation |
| Effect durable, result absent | reconcile by receipt/identity; never repeat blindly |
| Result durable, projection absent | result stands; rebuild projection and verify parity |

`DURABILITY_UNKNOWN` is fail-closed: no cursor advance, retry, signal,
delete, merge, reset, or further external effect is permitted until a strict
reconciliation event resolves it.

### File authority and DB projection constraints

The genesis/authority-selection event records the canonical ledger path,
authority mode, and authority identity. Authority mode is immutable for the
run except through an explicit suffix-rebind ceremony. The DB projection must
enforce uniqueness of `(authority_id, physical_sequence)`,
`(authority_id, event_id)`, `(authority_id, event_hash)`, and
`(chain_id, evidence_sequence)`, `(chain_id, semantic_sequence)`, plus one source row per operation/event
identity. It stores the source ledger path, source tip, event hash, and schema
version. A parity verifier compares ordered source event IDs, physical,
evidence, and semantic sequences, hashes, payload digests, and accepted/rejected
counts; missing,
extra, reordered, or mismatched rows are projection divergence and a hold.

### Exact bypass controls and gates

- **Store compatibility:** every mutating method in `store/compat.py` receives
  typed chain context when its target is chain-bound. A legacy call without
  context returns `unattributed_state_change`, appends a hold when a ledger is
  available, and performs no bound mutation. S6 calls both compatibility and
  underlying Store paths and asserts one rejection/hold and zero state change.
- **Filesystem bypass:** all in-repo chain/spec/marker/snapshot writers route
  through context-bearing writers. On each lock-acquired read and before each
  accepted commit, the verifier compares the canonical digest set for bound
  files with the last committed set. A raw edit produces
  `chain_control.tamper_detected` and a hold; continuation is forbidden.
  Watchers are diagnostic only. S6 injects raw JSON/marker replacement and
  asserts zero cursor advance.
- **DB/SQL bypass:** chain-bound DB mutations require a transaction-scoped
  operation ID and actor. The adapter rejects missing context; projection
  tables enforce the uniqueness constraints above; direct SQL against a
  projection is detected by source event/hash parity and held. S6 runs direct
  SQL with no context, valid context, and mismatched source hash, asserting
  reject/commit/hold respectively. File authority remains authoritative.
- **Plugin/admin paths:** registered mutators pass through the same context
  guard. Unregistered/raw admin writes are detected at the next strict census
  and cannot release a hold.

These controls require runtime negative fixtures; a static path inventory alone
cannot establish closure.

### Machine-readable surface inventory

S7 must emit the Oracle-only artifact
`.oracle/evidence/nbf08-chain-control-surface-inventory.json`. It is not a
source authority. The top-level schema is:

```json
{
  "schema_version": "nbf08-chain-control-surface-inventory-v1",
  "base_revision": "<git sha>",
  "generator_version": "<frozen id>",
  "research_inventory_path": ".oracle/research/nbf08-control-surface-inventory.md",
  "research_inventory_sha256": "e7882d57ed32a237ad0aa6f0774ea35776717e6891a5724d4e97360f0618d5d8",
  "surface_count": 83,
  "surface_id_range": "CC-001..CC-083",
  "surface_ids": [
    "CC-001", "CC-002", "CC-003", "CC-004", "CC-005", "CC-006", "CC-007", "CC-008", "CC-009", "CC-010",
    "CC-011", "CC-012", "CC-013", "CC-014", "CC-015", "CC-016", "CC-017", "CC-018", "CC-019", "CC-020",
    "CC-021", "CC-022", "CC-023", "CC-024", "CC-025", "CC-026", "CC-027", "CC-028", "CC-029", "CC-030",
    "CC-031", "CC-032", "CC-033", "CC-034", "CC-035", "CC-036", "CC-037", "CC-038", "CC-039", "CC-040",
    "CC-041", "CC-042", "CC-043", "CC-044", "CC-045", "CC-046", "CC-047", "CC-048", "CC-049", "CC-050",
    "CC-051", "CC-052", "CC-053", "CC-054", "CC-055", "CC-056", "CC-057", "CC-058", "CC-059", "CC-060",
    "CC-061", "CC-062", "CC-063", "CC-064", "CC-065", "CC-066", "CC-067", "CC-068", "CC-069", "CC-070",
    "CC-071", "CC-072", "CC-073", "CC-074", "CC-075", "CC-076", "CC-077", "CC-078", "CC-079", "CC-080",
    "CC-081", "CC-082", "CC-083"
  ],
  "surfaces": [
    {
      "surface_id": "<stable id>",
      "path": "<repo-relative path>",
      "symbol": "<function/class/CLI action>",
      "mutation": "<operation>",
      "authority_class": "chain-authoritative|linked-domain|read-only|external-unknown",
      "claim_class": "required|linked|evidence-only|claimless-read|held",
      "required_event_kinds": ["chain_control.intent"],
      "linked_domain_receipts": ["<kind>"],
      "coverage_tests": ["<test id>"],
      "required_commands": ["<exact command>", "<exit contract>"],
      "evidence_paths": ["<repo-relative artifact>"],
      "evidence_digests": ["<sha256>"],
      "authority_mode": "file|db-projection|explicit-db",
      "replay_contract": "<idempotency and crash rule>",
      "ambiguity_ids": ["AMB-001"],
      "gate_ids": ["S1"],
      "status": "covered|held|excluded",
      "closure_status": "planned|implemented|verified|held|excluded",
      "reason": "<required for held/excluded>"
    }
  ],
  "inventory_digest": "<sha256 of canonical content excluding this field>"
}
```

The generator must load exactly
`.oracle/research/nbf08-control-surface-inventory.md` at SHA-256
`e7882d57ed32a237ad0aa6f0774ea35776717e6891a5724d4e97360f0618d5d8`, assert
that its 83 stable IDs are exactly `CC-001..CC-083`, each occurring once, and
reject any missing, orphan, or duplicate ID. It must enumerate local/epic chain, cloud, supervisor, pause,
retry, skip, rebind, cutover, reset, down, destroy, adopt, overrides,
control-message, schedule, config/source, bakeoff, migration, manual/API,
plugin/admin, signal, and read-only surfaces. `--check` must fail on a newly
discovered unclassified mutation or a stale source-input digest.

### Current-source gap sweep is implementation work

The read-only gap sweep `.oracle/research/nbf08-mutation-gap-sweep.md` is
bound at SHA-256
`1909c7a68901d40c7187dd6a4528496042e367de35f159e665b7524e175c1439` as
review evidence only. Its confirmed MG-001 through MG-015 candidates are
implementation work, not closed coverage: S6/S7 must add exact route-matrix
symbols, linked-domain or explicit exclusion decisions, context guards, and
negative tests before claiming closure. The inventory's 83 CC rows are the
current source census; no stale manager adjudication or prior frozen list may
substitute for it.

## Frozen shared contract (brief/addendum text identical)

This section is normative and is reproduced byte-for-byte in the NBF-08 brief.
It supersedes any earlier shorthand in this addendum. `U64BE(n)` is exactly
eight bytes, unsigned, big-endian (`n.to_bytes(8, "big")`), for
`physical_sequence`, `evidence_sequence`, and `semantic_sequence`; sequence
values are never decimal strings. `F(s)` is an unsigned-64-bit big-endian
byte-length followed by UTF-8 bytes. Every domain-separated preimage uses one
literal separator byte `0x00` (not the two characters `\\0`). Canonical JSON
is UTF-8 with `sort_keys=true`, separators `(',', ':')`, and no trailing
newline. Every common-envelope key is emitted: known-but-unset nullable values
are JSON `null`; absent optional values use exactly
`{"__nbf08_absent__":true}`. Omitted keys and user payloads containing the
reserved absent marker are invalid. `created_at` is retained but excluded from
identity hashes.

The common envelope fields, in the same names and meaning everywhere, are:
`schema_version`, `event_id`, `event_kind`, `operation_id`, `causation_id`,
`correlation_id`, `recovery_id`, `chain_id`, `parent_chain_id`, `child_id`,
`run_id`, `actor`, `authority_mode`, `ledger_id`, `created_at`,
`physical_sequence`, `evidence_sequence`, `semantic_sequence`,
`previous_physical_digest`, `previous_evidence_digest`, `payload_digest`,
`event_hash`, `intent`, `semantic_effect`, `expected_cursor`,
`expected_revision`, `actual_cursor`, `actual_revision`, `pre_state_digest`,
`post_state_digest`, `source_identity`, `spec_identity`, `config_identity`,
`runtime_identity`, `linked_receipts`, `outcome`, `failure_class`,
`claim_class`, and
`payload`. `semantic_effect` is mandatory and is exactly `advance`,
`metadata_only`, or `no_change`.

`claim_class` is also a mandatory common-envelope field and is an enum with
exact values `required`, `linked`, `evidence-only`, `claimless-read`, or
`held`. Its canonical mapping is `chain-authoritative` → `required`,
`linked-domain` → `linked`, gate/observation evidence with no domain mutation
→ `evidence-only`, `read-only` → `claimless-read`, and
`external-unknown` → `held`. The mapping and enum are identical in the brief,
addendum, fixture schemas, and machine-readable S7 output; an unknown value,
omitted field, or authority/class mismatch is invalid.

`chain_control.authority_validated` is non-terminal pre-claim evidence: it
advances `evidence_sequence` only, never substitutes for `claimed`, and is
claimless as an event while the operation row's `claim_class` remains
`required` or `linked`.

### Committed S1 golden vector

S1 must commit the fixture at the literal path
`tests/arnold_pipelines/megaplan/incident/fixtures/nbf08_s1_event_v1.json`.
The fixture's payload is
`{"actual_cursor":"c1","optional_absent":{"__nbf08_absent__":true},"optional_null":null,"semantic_effect":"advance"}`.
Its raw canonical JSON payload is exactly 115 bytes (hex below); the fixture
must use these bytes, never a Python `b'...'` representation:

```text
7b2261637475616c5f637572736f72223a226331222c226f7074696f6e616c5f616273656e74223a7b225f5f6e626630385f616273656e745f5f223a747275657d2c226f7074696f6e616c5f6e756c6c223a6e756c6c2c2273656d616e7469635f656666656374223a22616476616e6365227d
```

For `authority_mode=file`, `ledger_id=ledger-demo`, `chain_id=chain-demo`,
`physical_sequence=7`, `evidence_sequence=3`, `semantic_sequence=2`,
`event_id=evt-0007`, `event_kind=chain_control.committed`,
`operation_id=op-0001`, `causation_id=intent-0001`,
`correlation_id=corr-0001`, `recovery_id=none`,
`previous_physical_digest=00` repeated 32 times, and
`previous_evidence_digest=11` repeated 32 times, the payload SHA-256 is
`2e339acd9fd64f238aa7d3ff41902a090b72788aabd910ebd219cf2402625805`.
The exact 551-byte preimage bytes (hex, including the initial domain prefix's
`0x00`) are:

```text
4e424630382d434841494e2d434f4e54524f4c2d4556454e542d563100000000000000000466696c65000000000000000b6c65646765722d64656d6f000000000000000a636861696e2d64656d6f00000000000000070000000000000003000000000000000200000000000000086576742d303030370000000000000017636861696e5f636f6e74726f6c2e636f6d6d697474656400000000000000076f702d30303031000000000000000b696e74656e742d303030310000000000000009636f72722d3030303100000000000000046e6f6e6500000000000000403030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303000000000000000403131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313100000000000000403265333339616364396664363466323338616137643366663431393032613039306237323738386161626439313065626432313963663234303236323538303500000000000000737b2261637475616c5f637572736f72223a226331222c226f7074696f6e616c5f616273656e74223a7b225f5f6e626630385f616273656e745f5f223a747275657d2c226f7074696f6e616c5f6e756c6c223a6e756c6c2c2273656d616e7469635f656666656374223a22616476616e6365227d
```

The preimage SHA-256 golden event hash is
`779052eb2aa68228773cc10e976ecebfb6137d7cbedb652fe72d8c1de6882422`.
The test independently decodes every `U64BE` and `F` component and asserts
these bytes and hashes; a vector copied from implementation output without
independent recomputation fails S1.

### Committed S2 physical-record golden vector

S2 must commit the fixture at the literal path
`tests/arnold_pipelines/megaplan/incident/fixtures/nbf08_s2_physical_record_v1.json`.
Its exact stored JSON envelope bytes are the raw UTF-8 bytes of
`{"event_id":"inc-0008","event_kind":"incident.note","payload":{"message":"ok","nested":[1,null,true]},"physical_sequence":8,"schema_version":1}`
(143 bytes), never a Python `b'...'` representation. The stored
`previous_physical_digest` is lowercase ASCII hex `22` repeated 32 times, but
the physical preimage decodes that field to the 32 raw bytes `0x22` repeated
32 times. This ASCII-hex-at-rest versus raw-byte-in-preimage rule applies to
every SHA-256 digest field; no ASCII hex is hashed where raw digest bytes are
specified.

The physical preimage is the literal `0x00`-terminated prefix
`NBF08-PHYSICAL-RECORD-V1` followed by `F(ledger_id)`, `U64BE(physical_sequence)`,
`F(record_type)`, `F(stored_record_bytes)`, and `F_BYTES(previous_digest)`,
where the U64BE sequence is `0000000000000008` and the byte lengths are
`ledger_id=11`, `record_type=8`, `stored_record_bytes=143`, and
`previous_digest=32`. Its exact stored-envelope bytes (hex) are:

```text
7b226576656e745f6964223a22696e632d30303038222c226576656e745f6b696e64223a22696e636964656e742e6e6f7465222c227061796c6f6164223a7b226d657373616765223a226f6b222c226e6573746564223a5b312c6e756c6c2c747275655d7d2c22706879736963616c5f73657175656e6365223a382c22736368656d615f76657273696f6e223a317d
```

The exact 259-byte physical preimage (including the one literal prefix
separator byte `0x00` and raw 32-byte predecessor digest) is:

```text
4e424630382d504859534943414c2d5245434f52442d563100000000000000000b6c65646765722d64656d6f00000000000000080000000000000008696e636964656e74000000000000008f7b226576656e745f6964223a22696e632d30303038222c226576656e745f6b696e64223a22696e636964656e742e6e6f7465222c227061796c6f6164223a7b226d657373616765223a226f6b222c226e6573746564223a5b312c6e756c6c2c747275655d7d2c22706879736963616c5f73657175656e6365223a382c22736368656d615f76657273696f6e223a317d00000000000000202222222222222222222222222222222222222222222222222222222222222222
```

The precomputed physical-record SHA-256 digest is
`5e2e79572b23e7459b0e14f09b7af869d94279baec6eb99aa447f6cb7f308f48`.
This S2 digest protects the complete stored envelope byte-for-byte (including
all fields and their canonical ordering), whereas `event_hash` protects only
the explicitly selected stable event fields and canonical payload defined by
S1. Changing any stored envelope byte must fail physical verification even if
the selected event fields still produce the same event hash.

### Locked legacy `.events.seq` upgrade

S2 must acquire the existing IncidentLedger sequence lock before reading the
legacy integer `.events.seq` sidecar. While holding that lock it must parse the
single non-negative decimal integer, compare it with the highest complete
physical record and any reservation, and atomically convert it to the
structured `nbf08-sequence-reservation-v1` sidecar with a migration receipt
that preserves the original bytes and integer. It must then fsync the new
sidecar and directory before releasing the lock. Empty, non-decimal,
negative, overflowing, multi-line, stale, or ahead-of-ledger values, a
reservation mismatch, or a repeated conversion with different source bytes
is a typed `DURABILITY_UNKNOWN` hold; no allocation or tombstone inference is
allowed until an explicit reconciliation records the mismatch. Concurrent
readers cannot observe a partially converted sidecar.

### Complete reservation-sidecar and tombstone contract

The existing sequence sidecar stores this complete structured reservation
envelope before any number is allocated:

```json
{
  "schema_version":"nbf08-sequence-reservation-v1",
  "reservation_id":"<stable-id>", "ledger_id":"<id>",
  "authority_mode":"file", "physical_sequence":0,
  "status":"reserved|committed|tombstoned",
  "scope":"chainless|chain_control",
  "chain_id":null, "event_id":null, "event_kind":null,
  "operation_id":null, "causation_id":null, "correlation_id":null,
  "recovery_id":"<id-or-none>", "evidence_sequence":null,
  "semantic_sequence":null, "record_type":"<type>",
  "intended_record_sha256":"<sha256>",
  "previous_physical_digest":"<sha256>", "byte_offset":0,
  "line_number":0, "created_at":"<evidence-only>",
  "reservation_digest":"<sha256>"
}
```

For `scope=chainless`, the chain/event/operation lineage and both per-chain
sequences are explicitly `null`. For `scope=chain_control`, all of those
fields are non-null except a deliberately absent optional child, and the
reservation records the intended event identity and unchanged prior evidence
and semantic sequence. Recovery appends one deterministic structured
`chain_control.sequence_reserved_tombstone` envelope at the reserved physical
number, containing `reservation_id`, every copied reservation field,
`event_id`, `event_kind`, `chain_id`, `operation_id`, `causation_id`,
`correlation_id`, `recovery_id`, `previous_physical_digest`,
`reservation_status="tombstoned"`, `reason="crash_before_append"`,
`evidence_sequence` and `semantic_sequence` unchanged, and
`semantic_effect="no_change"`. A chainless tombstone has the explicit nulls
above and `chain_control` lineage is not invented. Tombstones participate in
the physical hash chain but consume neither evidence nor semantic sequence.
This is an explicit typed carveout from chain-saga lineage: a chainless
tombstone uses `lineage_class="physical_reservation"`, keeps chain-scoped
`chain_id`, `operation_id`, `causation_id`, and `correlation_id` null, and
provides `physical_lineage={"ledger_id":"<id>","reservation_id":"<id>","physical_sequence":0,"previous_physical_digest":"<sha256>","recovery_id":"<id>"}`.
It is therefore attributable physical evidence without inventing a chain
operation; a chain reservation instead retains its non-null typed saga
lineage.
The tombstone also emits every fixed common-envelope key (`schema_version`,
`event_id`, `event_kind`, all lineage/authority identities, both digests,
`payload_digest`, `event_hash`, `created_at`, `intent`, `expected_cursor`,
`expected_revision`, `actual_cursor`, `actual_revision`, all state/source
identities, `linked_receipts`, `outcome`, `failure_class`, and `payload`),
using explicit `null` or the reserved absent marker where applicable.

Before the next allocation of any kind (chainless or chain), recovery under
the IncidentLedger lock must enumerate every reservation, verify its intended
line or exact tombstone, and mark it committed/tombstoned. Any unresolved,
ambiguous, conflicting, non-contiguous, or sidecar-only reservation blocks the
next allocation with `DURABILITY_UNKNOWN`; no caller may skip recovery,
allocate another number, or infer success. Recovery is idempotent by
`reservation_id` and returns the exact existing line/tombstone on replay.

### Static lock-order and direct-save acceptance

S7 must run the committed static checker
`python .oracle/scripts/nbf08_static_contract_check_v1.py --root . --check-lock-order --check-sequence-migration --reject-direct-save`.
It must prove the only lock order is
IncidentLedger sequence lock → sorted chain-scope locks → sorted absolute-path
plan/state locks → local CAS/write; reject reverse acquisition, public-writer
re-entry, DB/external work under the stack, and any adapter lock acquisition.
The same check must reject `save_chain_state` or `save_epic_chain_state` without
a `LockedChainControlTransaction` (and reject any direct mutable-save path),
with a focused negative test asserting zero state/cursor change. A missing
checker, an unclassified lock edge, an unverified `.events.seq` migration, or
a context-free direct save is a binary S7 failure.

### Executable future-suffix rebind ceremony

The implementation must provide a dedicated, exact, non-interactive surface
in `arnold_pipelines/megaplan/incident/chain_control.py`, exposed through
`python -m arnold_pipelines.megaplan.incident.chain_control`. Generic override,
manual file editing, or ordinary rebind APIs must not implement this ceremony.
The suffix command is:

```text
python -m arnold_pipelines.megaplan.incident.chain_control rebind-suffix \
  --ledger <path> --chain-id <id> --expected-physical-tip <event/hash> \
  --expected-control-tip <event/hash> --from-authority <id> \
  --to-authority <id> --source-manifest <path> \
  --expected-base-sha256 <sha256> --expected-source-sha256 <sha256> \
  --expected-manifest-sha256 <sha256> --reason <code> \
  --actor <redacted-id> --receipt <output>
```

The ceremony is: quiesce writers; verify source ledger, prefix, suffix,
snapshot, manifest, branch/base, and dependency identities; append rebind
intent; reacquire the existing ledger lock and CAS both tips; append one
`chain_control.suffix_rebound` event with old/new authority and all hashes;
write the new authority marker/projection; verify parity; emit a receipt. Any
tip drift, ambiguity, or persistence uncertainty emits rejection/hold and
leaves the old authority untouched. NBF-07's dependency change is a separate
authorized operation after this receipt, never an implicit side effect.

The suffix receipt must echo exact matching fields
`expected_base_sha256`, `expected_source_sha256`, and
`expected_manifest_sha256`, alongside observed `base_sha256`, `source_sha256`,
and `manifest_sha256`; a missing, stale, or mismatched expected/observed digest
is rejection/hold and leaves the old authority untouched.

The NBF-07 mutation is a separate dedicated command on the same module:

```text
python -m arnold_pipelines.megaplan.incident.chain_control rebind-nbf07-dependency \
  --ledger <path> --chain-id <id> --tasklist .oracle/tasklist.md \
  --chain-spec <path> --expected-tasklist-sha256 <sha256> \
  --expected-chain-spec-sha256 <sha256> --suffix-tip <event/hash> \
  --expected-base-sha256 <sha256> --expected-source-sha256 <sha256> \
  --expected-manifest-sha256 <sha256> --candidate-sha <sha> \
  --inventory-sha256 <sha256> \
  --framed-diff-sha256 <sha256> --actor <redacted-id> --receipt <output>
```

This command is unavailable until `rebind-suffix` has passed strict physical,
semantic, and parity verification.

The later dependency rebind has one canonical mutation target: the exact
NBF-07 dependency field in `.oracle/tasklist.md` and the active chain
specification's dependency representation. The operation records both paths,
stable section/field selectors, expected old SHA-256s and value digests, new
SHA-256s, the NBF-08 suffix tip, and operation/receipt IDs. Under the existing
ledger lock it verifies quiescence and all digests, claims the operation,
writes both files through temporary fsync-and-rename paths, verifies both
post-hashes, and appends commit. Any uncertain write or verification is
`DURABILITY_UNKNOWN`; no partial dependency is committed and reconciliation is
required. The receipt freezes fresh NBF-07 inputs: candidate/base SHA,
source-input digest, final surface/inventory digest, framed diff digest, and
NBF-08 suffix tip. Its receipt must echo the validated `actor`, `operation_id`,
and `idempotency_key`, and bind them to the exact suffix tip and expected
base/source/manifest hashes; replay with the same tuple returns the same
receipt without rewriting either dependency. NBF-07 must rerun exact
rebase/freeze validation from those inputs.

## Binary S1–S7 gates

Each gate is pass/fail and must record command, exit code, exact test node
counts, source-input digest, research-inventory digest, covered `CC-*` IDs,
ambiguity/gate IDs, and artifact digest. A failed gate stops the suffix; no
subjective “mostly green” promotion is allowed. The only closure vocabulary is
`authority_class` = `chain-authoritative|linked-domain|read-only|external-unknown`
and `closure_status` = `planned|implemented|verified|held|excluded`; legacy
labels must be explicitly mapped or rejected.

The exact Oracle-only tools are frozen as
`.oracle/scripts/nbf08_surface_inventory_v1.py` and
`.oracle/scripts/nbf08_replay_parity_v1.py`. S7 invokes them exactly as:

```bash
python .oracle/scripts/nbf08_surface_inventory_v1.py \
  --research .oracle/research/nbf08-control-surface-inventory.md \
  --expected-sha256 e7882d57ed32a237ad0aa6f0774ea35776717e6891a5724d4e97360f0618d5d8 \
  --expected-ids CC-001..CC-083 \
  --output .oracle/evidence/nbf08-chain-control-surface-inventory.json --check

python .oracle/scripts/nbf08_replay_parity_v1.py \
  --ledger <incident-ledger-root> --projection <db-or-snapshot-projection> \
  --authority file --check-physical --check-semantic --check-parity
```

The replay tool must verify the NBF01 torn-tail compatibility boundary, the
physical digest chain, the evidence sequence, the accepted semantic reducer,
and file-authority-to-projection parity. A missing tool, changed path,
changed argument, or unrecorded output is an S7 failure.

The historical manager adjudication
`.oracle/research/nbf08-review-adjudication.md` at SHA-256
`66fda12f9b9c30acbdb6ab6724543b09f671ab7a296526a4aa45dea4d0ff0776` is stale,
non-authoritative context only. It is not S7 evidence; S7 must not record or
check this digest. It cannot select implementation authority, override the
research inventory, waive a held row, or replace the IncidentLedger as source
of truth.

- **S1 primitive:**
  `uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_journal.py`
  plus `python -m compileall` on the new incident modules and `git diff --check`.
- **S2 replay/migration:**
  `uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_replay.py`
  and the strict reader/import CLI against clean, forked, truncated, legacy,
  and `DURABILITY_UNKNOWN` fixtures.
- **S3 chain/epic:**
  `uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_chain.py`
  covering cursor/CAS/interleaving, parent-child, pause/retry/skip/rebind,
  reset, and direct-save rejection.
- **S4 plan/source:**
  `uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_plan.py`
  covering overrides/auto/control, effective config and source digests,
  invalid controls, and active rebind.
- **S5 cloud/schedule:**
  `uv run pytest -q tests/cloud/test_chain_control_cloud.py tests/arnold_pipelines/megaplan/test_chain_control_schedule.py`
  covering cloud lifecycle/reset, supervisor, schedule occurrences, and
  control-message linkage.
- **S6 domain/API:**
  `uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_domains.py`
  covering bakeoff, migrations, projections, manual/API/plugin/admin context,
  and unattributed mutation holds.
- **S7 integration:** run every S1–S6 command from a quiescent checkout, then
  run the inventory generator with `--check`, strict replay/parity verification,
  Python compile, relevant shell syntax/static checks, and `git diff --check`.
  The generator must prove exactly 83 research IDs `CC-001..CC-083` are present
  exactly once,
  every row has ambiguity/gate/test/command/evidence/authority/replay fields,
  and every `AMB-001..AMB-006` is either verified with evidence or explicitly
  held (with S7 failing while held). The machine-readable inventory and rebind
  receipt must verify against their recorded hashes. Any nonzero exit, missing
  node, stale digest, orphan CC ID, unresolved ambiguity, or unresolved
  `DURABILITY_UNKNOWN` is a binary failure.

## [XHARD] review flags

- **XHARD-1:** Prove the existing IncidentLedger can safely host a second typed
  hash-chain suffix without weakening NBF-01 incident replay or signal ordering.
- **XHARD-2:** Prove one lock/CAS boundary covers journal append and all local
  chain state transitions without deadlock or lock inversion across file/DB
  stores.
- **XHARD-3:** Prove deterministic legacy genesis/rebind classification; an
  ambiguous old snapshot must remain held rather than being normalized into a
  false history.
- **XHARD-4:** Prove no standalone CLI, resident, cloud, schedule, bakeoff,
  plugin, or admin mutation can alter a bound chain without an operation ID.
- **XHARD-5:** Prove external effects and crashes yield reconciliation holds,
  not duplicate launch, signal, merge, delete, or cursor advancement.
- **XHARD-6:** Prove DB projections cannot be mistaken for file authority and
  that projection drift is visible and fail-closed.

## Success criteria

- A strict reader reconstructs every accepted chain and epic-chain cursor from
  the IncidentLedger chain-control suffix and verifies the accepted prefix
  anchor, links, hashes, and state digests.
- Every in-scope mutating control has an accepted, rejected, conflict, tamper,
  replay, or hold record with stable operation identity.
- Local, epic, cloud, supervisor, schedule, resident control, plan override,
  source/config, bakeoff, migration, and admin boundaries have deterministic
  positive and negative tests.
- DB/projection snapshots are reproducible and divergence is held, not
  silently repaired.
- Legacy histories are either deterministically imported or explicitly held;
  no guessed cursor or success is emitted.
- Replay and crash tests demonstrate no duplicate external effect and exact
  prior-result recovery.
- The S1 golden byte vectors pass for the shared NUL/framing/common-envelope
  contract, including physical-record, evidence-sequence, semantic-sequence,
  and hash verification.
- The dedicated `incident.chain_control` suffix/rebind surface and its
  separately guarded `rebind-nbf07-dependency` command pass their CAS,
  receipt, and fresh-input tests; generic overrides cannot substitute for
  either command.
- NBF-07 can be re-bound to depend on NBF-08 with a frozen, auditable suffix;
  current NBF-07 remains unchanged until that authorized rebind.

## Non-goals

NBF-08 does not replace the IncidentLedger, signal/disposition authority,
WBC, scheduler, admission layer, provider policy, Store, DB, schedule ledger,
bakeoff ledger, or plan event journal. It does not absorb raw logs, prompts,
provider transcripts, ticket/brief/feedback content, Git history, or deployment
telemetry. It does not silently rewrite `.oracle/tasklist.md`, current status,
main, NBF-06, or NBF-07. It does not make pure reads into mutations or permit
manual event deletion.

## Estimated decomposition

Seven implementation stages above are expected to produce approximately
12–16 focused tasks: 3–4 primitive/schema/replay tasks, 3 chain/epic wiring
tasks, 2 plan/config/source tasks, 2 cloud/schedule/operator tasks, 1
bakeoff/store/admin task, and 2 migration/projection/acceptance tasks. Each
task must carry its own deterministic tests and remain within one ownership
surface. A Sol/XHARD review is required for the physical-authority, migration,
and final cross-surface gates; Luna reviews should cover each implementation
stage and the integrated replay/authority gate.
