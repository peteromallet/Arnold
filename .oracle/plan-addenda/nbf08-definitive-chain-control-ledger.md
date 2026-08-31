# NBF-08 plan addendum — definitive chain-control ledger

## Change requested

Add a new epic suffix, NBF-08, for a definitive chain-control journal. NBF-08
must execute after NBF-01 through NBF-06 and before the current NBF-07
finalizer. The later authorized suffix rebind must change NBF-07's dependency
set to include NBF-08. This addendum is preparatory and does not mutate the
tasklist, status, source, branch, or active chain.

## Fixed architecture

Use one typed `ChainControlJournal` facade over the existing
`IncidentLedger` `events.jsonl` and lock. Do not add another journal, root,
lock, sequence, signal authority, scheduler, or terminal writer. Chain-control
events form a hash-chained `chain_control.*` suffix anchored to the accepted
incident prefix tip/digest. File authority is explicit per run; DB is a
projection unless a future authority-selection event says otherwise. Readers
are strict and fail into typed holds on ambiguity, fork, tamper, stale CAS,
projection drift, or missing identity.

The physical IncidentLedger sequence is global and may interleave ordinary
incident events with chain-control events. Each chain-control event also has a
per-chain `evidence_sequence` for every chain-control evidence event and an
accepted-only `semantic_sequence`. Readers verify the physical predecessor,
the prior evidence event/digest, and the derived semantic state; these cursors
must never be conflated. The exact event hash is the SHA-256 of a
domain-separated, length-framed preimage:

```text
NBF08-CHAIN-CONTROL-EVENT-V1\0 +
    F(authority_mode, ledger_id, chain_id, U64BE(physical_sequence),
      U64BE(evidence_sequence), U64BE(semantic_sequence),
  event_id, event_kind, operation_id, causation_id, correlation_id,
  recovery_id, previous_physical_digest, previous_evidence_digest,
  payload_digest, canonical_payload_without_event_hash)
```

`U64BE(n)` is exactly eight bytes, unsigned, big-endian (`n.to_bytes(8,
"big")`); it is used for all three sequence fields and never as a decimal
string. `F(s)` is an unsigned-64-bit big-endian byte length followed by the
UTF-8 bytes of `s`. The domain prefix ends in one literal separator byte
`0x00`; no escaped two-character `\\0` is accepted. Canonical JSON is UTF-8,
`sort_keys=true`, compact separators `(',', ':')`, and has no trailing
newline. Timestamps are not hash identity inputs. This framing is frozen by
S1.

The separator is one literal byte `0x00` in every domain-separated preimage
(event, payload, and physical-record). The common envelope is a fixed schema;
all keys are emitted in every record, with `null` for a known-but-unset
nullable value. An absent optional value is represented only by the reserved
canonical object `{"__nbf08_absent__":true}`; it is distinct from JSON
`null`, omitted keys are invalid, and user payloads may not use that reserved
key. The envelope field names are exactly `schema_version`, `event_id`,
`event_kind`, `operation_id`, `causation_id`, `correlation_id`, `recovery_id`,
`chain_id`, `parent_chain_id`, `child_id`, `run_id`, `actor`, `authority_mode`,
`ledger_id`, `created_at`, `physical_sequence`, `evidence_sequence`,
`semantic_sequence`, `previous_physical_digest`, `previous_evidence_digest`,
`payload_digest`, `event_hash`, `intent`, `semantic_effect`,
`expected_cursor`, `expected_revision`, `actual_cursor`, `actual_revision`,
`pre_state_digest`, `post_state_digest`, `source_identity`, `spec_identity`,
`config_identity`, `runtime_identity`, `linked_receipts`, `outcome`,
`failure_class`, and `payload`. `semantic_effect` is mandatory and is one of
`advance`, `metadata_only`, or `no_change`. S1 must publish golden UTF-8
preimage bytes, field lengths, payload bytes, payload digest, and event hash;
aliases or timestamp-derived identities fail the gate.

S2 must also compute a domain-separated physical digest for every ordinary and
legacy record, not only chain-control records:

```text
SHA256(b'NBF08-PHYSICAL-RECORD-V1\\x00' +
      F(ledger_id) + U64BE(physical_sequence) + F(record_type) +
      F(stored_record_bytes) + F_BYTES(previous_physical_digest))
```

`previous_physical_digest` is stored as lowercase ASCII hex but decoded to raw
32-byte digest material before `F_BYTES`; `physical_record_digest` is emitted
as lowercase ASCII hex. Legacy bytes are preserved exactly; malformed or ambiguous records hold. S2
must pass both physical-record verification and accepted-only semantic replay.

Every event has mandatory non-empty causation, correlation, and recovery IDs;
root events use `recovery_id=none`, while replays preserve operation/correlation
and point causally to the existing result. Intent/claim/result/reconciliation
are one idempotent saga. No distributed transaction is claimed: local ledger
and state CAS are one lock-bound contract where possible, projections are
post-commit, and external effects are intent → claim → effect → result. Any
uncertain cutpoint becomes `DURABILITY_UNKNOWN`, which fail-closes all further
effects until strict reconciliation.

The file ledger is explicit authority per run. DB rows must enforce unique
authority/event/physical-sequence/hash and chain/evidence/semantic-sequence
identities, store source hashes, and pass ordered parity verification; DB drift
is a hold, not a fallback authority.

## Ordered work packages

1. **NBF08-S1: typed primitive.** Add envelope, canonical payload, redaction,
   hash-chain, authority context, append/CAS, and verifier seams in the
   incident package. Preserve all NBF-01 semantics.
2. **NBF08-S2: replay and legacy import.** Add accepted-prefix genesis,
   deterministic legacy import/rebind, strict reconstruction, ambiguity holds,
   and idempotent replay/crash recovery.
3. **NBF08-S3: local/epic chain.** Route chain and epic-chain cursor writes,
   pause/retry/skip/advance, adoption, target/source/runtime rebind, and reset
   decisions through operation context and journal results.
4. **NBF08-S4: plan/config/source.** Link bound overrides, `auto`, standalone
   controls, config/profile changes, source/anchor/ticket/feedback digests,
   and active input rebinding. Keep content histories separate.
5. **NBF08-S5: cloud/supervisor/schedule.** Link cloud start/resume/pause,
   sync/reset/down/destroy/retire/repair, supervisor transitions, resident
   control messages, schedules, occurrences, and cloud-run receipts.
6. **NBF08-S6: bakeoff/store/admin.** Link chain-affecting bakeoff pick/merge,
   Store backend migration/cutover, plugin/admin APIs, and direct-write
   detection. Record unattributed bound mutations as tamper/hold.
7. **NBF08-S7: projections/rollout.** Derive snapshots and DB projections,
   add audit/replay CLI surfaces, classify legacy histories, and provide a
   staged enablement/rollback plan without deleting accepted evidence.

The dependency graph is exact: `NBF-01..NBF-06 -> S1 -> S2 -> (S3, S4,
S5, S6) -> S7 -> authorized NBF-07 suffix rebind`. S3–S6 may be parallelized
only after S2 passes, but S7 waits for all four. No S3–S7 task may modify the
NBF-06 provider policy or NBF-04/NBF-05 signal/disposition ownership; those
surfaces receive operation links only at their existing seams.

The exact closure vocabulary is `authority_class` =
`chain-authoritative|linked-domain|read-only|external-unknown` and
`closure_status` = `planned|implemented|verified|held|excluded`. S7 must load
`.oracle/research/nbf08-control-surface-inventory.md`, compute and record its
SHA-256, assert exactly 83 stable IDs `CC-001..CC-083` occur exactly once, and
reject any missing, orphan, or duplicate ID. Every output row must carry
`ambiguity_ids`, `gate_ids`,
exact `coverage_tests`, exact commands, evidence paths/digests, authority mode,
replay contract, and closure status.

S1–S7 are strict binary gates, in dependency order. S1 freezes the schema,
framing, redaction, cursor, and facade vectors. S2 freezes strict replay,
legacy import, and `DURABILITY_UNKNOWN` cutpoints. S3 freezes local/epic CAS
and cursor wiring. S4 freezes plan/config/source linkage. S5 freezes cloud,
supervisor, schedule, and control-message linkage. S6 freezes bakeoff, Store,
projection, manual/API/plugin/admin boundaries. S7 reruns every prior focused
command, inventory `--check`, strict parity/replay, compile/static checks, and
the exact candidate manifest. Any nonzero command, missing test node, stale
digest, parity mismatch, or unresolved durability-unknown state blocks the
next stage.

## Required event contract

Each mutating operation must produce an intent and an outcome (`committed`,
`rejected`, `cas_conflict`, `tamper`, `replay`, `reconcile_required`, or
`hold`). Accepted effects additionally carry a claim, pre/post state digest,
expected/actual cursor and revision, stable redacted actor, chain/parent/child
IDs, source/spec/config/runtime/backend identities, idempotency key, and linked
domain receipts. External effects must have explicit intent/result records.

Required taxonomy includes genesis/import, intent, authority validation,
claim, commit, rejection, CAS conflict, tamper, external effect,
reconciliation, source/config/runtime/backend rebound, replay, hold, and hold
release.

All accepted state-changing/effectful events require one matching prior intent
and one single-use claim. External-effect results reference that claim and do
not claim again. Only genesis/import, sequence tombstones, rejection, CAS
conflict, tamper, hold, and replay are claimless evidence classes; they still
carry mandatory lineage and request/claim references (or a deterministic
request digest), and replay cannot create an effect.

Add explicit `chain_control.authority_selection`,
`chain_control.suffix_rebound`, and
`chain_control.sequence_reserved_tombstone` kinds. The semantic reducer
advances `semantic_sequence` only for accepted authority selection, suffix
rebind, committed, reconciled, hold release, or source/config/runtime/backend
rebound events whose pre/post semantic digests differ. Intent, validation,
claim, rejection, conflict, tamper, external-effect evidence, replay, holds,
and sequence tombstones advance only `evidence_sequence`.

The current NBF-01 `_emit_locked` seq-before-line crash gap is an S1 blocker.
The upgraded primitive must durably reserve the number in the existing
sequence sidecar, append an idempotent
`sequence_reserved_tombstone` on recovery when the line is absent, and only
then mark the reservation committed. A single incomplete final JSON line may
be treated as a torn tail; malformed complete/non-tail lines, sidecar
reservations without tombstones, or non-contiguous physical records hold.
NBF01 ordinary records remain an exact-byte physical prefix and must pass
physical verification before any NBF08 semantic event is accepted.

The lock protocol is fixed: IncidentLedger sequence lock, sorted chain-scope
locks (parent/child by chain ID), sorted plan/state locks (absolute path), then
local CAS/write. No reverse acquisition, public writer re-entry, DB
transaction, or external effect is allowed under this stack. A locked journal
transaction object is passed to chain/epic adapters; adapters may read/CAS but
may not append or acquire a lock. DB projections and external effects occur
after local commit under their own intent/claim/result contracts.

The implementation must emit the machine-readable Oracle-only inventory
`.oracle/evidence/nbf08-chain-control-surface-inventory.json` with frozen
schema `nbf08-chain-control-surface-inventory-v1`. Its research input is
`.oracle/research/nbf08-control-surface-inventory.md` at SHA-256
`e7882d57ed32a237ad0aa6f0774ea35776717e6891a5724d4e97360f0618d5d8`, with
exactly 83 IDs in the range `CC-001..CC-083`; missing, orphan, or duplicate
IDs are fatal. Each entry contains stable
surface ID, path, symbol, mutation, authority class, required event kinds,
claim class (`required|linked|evidence-only|claimless-read|held`), linked
receipts, exact commands, evidence paths/digests, authority mode,
replay contract, ambiguity IDs, gate IDs, coverage test IDs, closure status,
and exclusion/hold reason; the top level records base revision, generator
version, research-artifact digest, all stable IDs, and a canonical digest.
The generator's `--check` fails on unclassified mutation, stale research
digest, missing/non-contiguous/duplicate/orphan `CC-001..CC-083` ID, missing
closure field, or stale inputs.

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

The exact closure vocabulary is `authority_class` =
`chain-authoritative|linked-domain|read-only|external-unknown` and
`closure_status` = `planned|implemented|verified|held|excluded`. Every row
must carry ambiguity IDs, gate IDs, exact test IDs and commands, evidence
paths/digests, authority mode, and replay contract. S7 must prove all
`CC-001..CC-083` rows are present exactly once and bind the research digest;
the six ambiguity IDs must each be verified or held, with held ambiguity
blocking S7.

S6's bypass gates are executable: a context-free `store/compat.py` mutation
must reject/hold with zero bound state change; a raw chain/marker file edit
between lock-acquired reads must produce tamper/hold with zero cursor advance;
and direct SQL without transaction-scoped operation ID must reject while valid
context commits and a mismatched projection source hash holds. Plugin/admin
mutators use the same context guard; unregistered writes are found by the
strict digest census.

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

## Future-suffix rebind ceremony

The implementation must provide a non-interactive `chain-control rebind-suffix`
API/CLI (command spelling frozen in S2) accepting ledger, chain, expected
physical/control tips, old/new authority IDs, source manifest, expected base,
source, and manifest SHA-256 digests, reason, actor, and receipt paths. The
ceremony quiesces writers; verifies old authority, prefix/suffix hashes,
snapshots, branch/base, manifest, and dependencies;
appends rebind intent; CASes both tips under the existing ledger lock; appends
one `chain_control.suffix_rebound` event; writes/verifies new projections and
receipt; and leaves the old authority untouched on drift or uncertainty.
Changing NBF-07's dependency is a separate authorized operation after this
receipt.

That later operation targets the exact NBF-07 dependency field in canonical
`.oracle/tasklist.md` and the active chain specification's dependency field.
It records expected old hashes/values, new hashes, both paths/selectors,
NBF-08 suffix tip, and a receipt. It verifies quiescence and CASes both files
under the existing ledger lock; uncertain partial writes are
`DURABILITY_UNKNOWN` and cannot be treated as committed. The receipt freezes
fresh NBF-07 candidate/base SHA, source-input, surface-inventory, framed-diff,
and suffix-tip inputs, requiring fresh NBF-07 validation.

The exact Oracle-only commands are frozen as:

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

The dedicated suffix surface is
`python -m arnold_pipelines.megaplan.incident.chain_control rebind-suffix`;
generic overrides and manual edits cannot perform a suffix rebind. The
dedicated `rebind-nbf07-dependency` command is unavailable until suffix
physical, semantic, and parity verification passes.

Its exact non-interactive invocation is:

```text
python -m arnold_pipelines.megaplan.incident.chain_control rebind-suffix \
  --ledger <path> --chain-id <id> \
  --expected-physical-tip <event/hash> --expected-control-tip <event/hash> \
  --from-authority <id> --to-authority <id> --source-manifest <path> \
  --expected-base-sha256 <sha256> --expected-source-sha256 <sha256> \
  --expected-manifest-sha256 <sha256> --reason <code> --actor <redacted-id> \
  --receipt <output>
```

The suffix command's required preconditions and receipt fields are exact:
`--expected-base-sha256`, `--expected-source-sha256`, and
`--expected-manifest-sha256` are mandatory, and the receipt must echo those
three values under `expected_base_sha256`, `expected_source_sha256`, and
`expected_manifest_sha256`, alongside matching observed `base_sha256`,
`source_sha256`, and `manifest_sha256`. A missing, non-matching, or stale
expected/receipt digest is rejection/hold and leaves the old authority intact.

The separately authorized NBF-07 dependency handoff is:

```text
python -m arnold_pipelines.megaplan.incident.chain_control rebind-nbf07-dependency \
  --ledger <path> --chain-id <id> --tasklist .oracle/tasklist.md \
  --chain-spec <path> --expected-tasklist-sha256 <sha256> \
  --expected-chain-spec-sha256 <sha256> --suffix-tip <event/hash> \
  --expected-base-sha256 <sha256> --expected-source-sha256 <sha256> \
  --expected-manifest-sha256 <sha256> --candidate-sha <sha> \
  --inventory-sha256 <sha256> --framed-diff-sha256 <sha256> \
  --actor <redacted-id> \
  --receipt <output>
```

Its receipt must echo `expected_base_sha256`, `expected_source_sha256`, and
`expected_manifest_sha256` plus matching observed `base_sha256`,
`source_sha256`, and `manifest_sha256`; digest drift is a hold and cannot
partially mutate either dependency field. It must also echo the validated
`actor`, `operation_id`, and `idempotency_key`, and bind them to the exact
suffix tip and expected hashes; replay with the same tuple returns the same
receipt without rewriting either dependency.

The complete surface identity list is exactly:
`CC-001, CC-002, CC-003, CC-004, CC-005, CC-006, CC-007, CC-008, CC-009,
CC-010, CC-011, CC-012, CC-013, CC-014, CC-015, CC-016, CC-017, CC-018,
CC-019, CC-020, CC-021, CC-022, CC-023, CC-024, CC-025, CC-026, CC-027,
CC-028, CC-029, CC-030, CC-031, CC-032, CC-033, CC-034, CC-035, CC-036,
CC-037, CC-038, CC-039, CC-040, CC-041, CC-042, CC-043, CC-044, CC-045,
CC-046, CC-047, CC-048, CC-049, CC-050, CC-051, CC-052, CC-053, CC-054,
CC-055, CC-056, CC-057, CC-058, CC-059, CC-060, CC-061, CC-062, CC-063,
CC-064, CC-065, CC-066, CC-067, CC-068, CC-069, CC-070, CC-071, CC-072,
CC-073, CC-074, CC-075, CC-076, CC-077, CC-078, CC-079, CC-080, CC-081,
CC-082, CC-083`.

The historical manager adjudication `.oracle/research/nbf08-review-adjudication.md`
(`66fda12f9b9c30acbdb6ab6724543b09f671ab7a296526a4aa45dea4d0ff0776`) is
stale, non-authoritative context only. It is not S7 evidence, must not be
recorded or checked by the generator, and cannot select authority, override the
research inventory, waive a held row, or substitute for the inventory digest.

## Acceptance gate

NBF-08 is complete only when the strict reader reconstructs all accepted chain
operations from the one physical ledger; all in-scope controls have durable
success or failure evidence; legacy ambiguity is held; replay is idempotent;
crash windows cannot duplicate effects; direct/manual bound mutation is
detected or rejected; and DB/projection divergence is visible and fail-closed.
The gate must cover local/epic, cloud/supervisor, pause/retry/skip/rebind/
cutover/reset/down/destroy/adopt, active overrides, schedules/control
messages, config/source digests, bakeoff linkage, migrations, and admin/plugin
boundaries.

Pure status/doctor/audit/introspect/trace/log/attach/preflight reads remain
outside the mutation ledger. Incident signal, WBC, plan, provider, schedule,
bakeoff, Store, migration, Git, and deployment records remain separate linked
domain evidence.

## Exact focused commands

The expected gate commands are:

```text
uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_journal.py
uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_replay.py
uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_chain.py
uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_plan.py
uv run pytest -q tests/cloud/test_chain_control_cloud.py tests/arnold_pipelines/megaplan/test_chain_control_schedule.py
uv run pytest -q tests/arnold_pipelines/megaplan/test_chain_control_domains.py
```

S7 reruns all six commands, then runs the surface-inventory generator with
`--check`, strict journal replay/parity verification, Python compile, relevant
shell syntax/static checks, and `git diff --check`. Each command must record
exit code, test-node totals, source-input/research digests, covered
`CC-001..CC-083` IDs, gate/ambiguity IDs, and artifact digest. The generator
must prove exactly 83 research IDs `CC-001..CC-083` are present exactly once
and every `AMB-001..AMB-006` is
verified with evidence or explicitly held (with S7 failing while held). Any
nonzero exit, missing test node, stale digest, orphan ID, unresolved
ambiguity, or unresolved `DURABILITY_UNKNOWN` is a binary failure.

## Review and sequencing constraints

The physical-authority, legacy-import, lock/CAS, and integrated cross-surface
gates are `[XHARD]`. Require independent semantic review of each stage and a
final integrated replay/tamper/concurrency review. Do not begin NBF-07 final
rebase/freeze/push work until NBF-08 passes and its exact suffix identity is
frozen. Do not edit the current tasklist/status or perform the dependency
rebind until separately authorized.
