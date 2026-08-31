# NBF-08 manager-evidence adjudication

Read-only adjudication of the three review blocker families against the
current candidate tree. This file is the only artifact written by this audit;
the NBF-08 brief, addendum, inventory, tasklist, status, and source files were
not changed here.

## Binding note

The requested frozen identities were brief `25ead62a...`, addendum
`62ebfd5a...`, and inventory `e4573a1b...`. The working tree changed while the
audit was in progress. Immediately before this matrix was written, the
observed hashes were:

- brief: `7fa38be65a6923a130216aaf3f6e706711009b26ce2a80bd603c1b9ed686c77f`
- addendum: `62ebfd5aaaad0dc5c958cc3ec10fd71387d2ac0a6f57a631554d9263b9c0f689`
- inventory: `5c274c607c5b78e597f929b1f12adb23ba07db25505619bc9717df5a0c43c9c9`

That is identity drift, not a harmless review rerun. Any acceptance receipt must
bind a fresh, quiescent snapshot.

## Verdict matrix

### Parser warnings — FALSE POSITIVE against current bytes

The earlier malformed settled-decision finding applied to an older multiline
brief. Current `arnold_pipelines/megaplan/runtime/doc_assembly.py` accepts the
current one-line entries: `extract_settled_decisions` returned 12 IDs, 11
load-bearing decisions, and zero warnings. The current brief therefore no
longer has the cited parser blocker. Re-run the parser after freezing the
brief; do not carry the old warning into acceptance.

### Markdown table parse — CONFIRMED REWORK

The current inventory row CC-043 at
`.oracle/research/nbf08-control-surface-inventory.md:87` contains unescaped
pipe characters in the `action == pause-chain|resume-chain|...` expression.
It has 18 pipe delimiters where the nine-column table requires 10. A strict
Markdown/table parser therefore splits that row into extra cells and cannot
reliably bind all fields. Escape the literal pipes or replace them with a
canonical comma/list representation, then make the generator reject malformed
row widths.

### Sequence-before-append crash gap — CONFIRMED REWORK

`arnold_pipelines/megaplan/incident/ledger.py:280-325` writes and fsyncs the
sequence sidecar at lines 297-301 before opening/appending the event at
321-324. A deterministic probe redirected the event path to a directory:

```text
injected_append_error=IsADirectoryError
seq_after_failed_append='1'
next_event_seq=2
```

No event exists for sequence 1, so the next append creates a gap. This violates
the NBF-08 requirement that gaps are held (`brief:332-357`) and that an
unknown byte boundary is `DURABILITY_UNKNOWN` (`brief:395-416`). S1/S2 need a
transactional/recovery rule that cannot silently advance past an uncommitted
sequence, or must persist and surface the failed reservation as a hold.

### Torn-tail behavior — CONFIRMED REWORK for strict NBF-08 replay

`_IncidentEventJournal._read_records` at
`arnold_pipelines/megaplan/incident/ledger.py:264-277` catches
`JSONDecodeError` and continues for every line, not only a final partial line.
Probe input valid-seq-0, malformed-seq-1, valid-seq-2 returned
`incident_read_records=[0, 2]`. The reader can therefore project later data
across a malformed interior record. NBF-08 explicitly requires malformed JSON
or unknown byte boundaries to hold, not be skipped (`brief:397-416`). Strict
replay must distinguish a verified final torn tail from interior corruption
and preserve the exact physical bytes.

### Lock topology — MIXED: existing journal concern FALSE POSITIVE; state seam CONFIRMED

The existing NBF append door does use one sequence-sidecar flock: `_locked` at
`ledger.py:492-507` and `_emit_locked` at `ledger.py:280-325`; no second NBF
append lock was found. That portion of the review is a false positive.

The cross-domain state seam is real: `chain/spec.py:2287-2289` replaces the
chain state file, then `:2291-2308` appends a projection in a separate,
non-fatal step. NBF-08 correctly treats this as a required S3/S7 correction:
bind local state/CAS and the authoritative chain event under the existing
ledger lock where possible, otherwise retain an explicit reconciliation hold.
Do not introduce a second journal or lock.

### Event-taxonomy omissions — FALSE POSITIVE in the frozen design; future gate

The brief enumerates genesis/import, intent, authority validation, claim,
commit, rejection, CAS conflict, tamper, external-effect intent/result,
reconciliation, all rebound kinds, replay, hold, and hold release at
`brief:116-141`; the addendum repeats the required taxonomy at `addendum:129-132`.
The absence of an NBF-08 implementation in the current source is expected
because the addendum labels itself preparatory. S1 must still freeze a closed
wire enum and map aliases explicitly; no additional current blocker is proven.

### Inventory duplicate/missing rows — CONFIRMED REWORK (identity/count)

The current inventory has 62 unique rows, no duplicates, and no missing
`CC-001..CC-052`, but it adds `CC-053..CC-062` (rows 93-102). The frozen
contract requires exactly 52 IDs (`brief:544-594`, `addendum:134-148`). Thus
the old “duplicate/missing” wording is partly false—there are no duplicates or
missing IDs—but the exact-count and frozen-inventory digest gate fails. Either
freeze the intended 52-row artifact or explicitly revise the contract and all
bound hashes in a new authorized packet.

### Path/symbol claims — STALE CC-038 FINDING; NORMALIZATION STILL REQUIRED

Current CC-038 at inventory line 82 now names
`arnold/runtime/state_persistence.py`, and the claimed symbols exist at lines
82, 99, and 104 of that file. The prior claim that the path was absent is
therefore false against current bytes. Other rows use package-relative paths
such as `chain/spec.py`; that is acceptable only if the future S7 generator
normalizes them deterministically to repo-relative paths. The machine schema
requires repo-relative paths (`inventory:124-148`), so S7 must reject any
unresolved path/symbol rather than relying on ad hoc prefixing.

### Claim contract — VALID BOUNDARY REQUIREMENT, not an NBF04 defect

`IncidentLedger.claim_signal` at `ledger.py:1015-1044` intentionally records
only the NBF04 physical signal claim keyed by disposition ID and signal. NBF-08
non-goals keep signal/disposition/WBC authority in NBF04/NBF05
(`brief:718-726`), while the inventory requires chain-control records to link
those receipts rather than duplicate them (`inventory:98-112`). The correction
is therefore an NBF-08 implementation requirement: its typed
`chain_control.claimed` event must carry operation/chain/context identity and
the linked disposition/claim receipt. Do not weaken or repurpose the existing
physical claim door.

### Hash separators and envelope — CONFIRMED PRE-S1 SPEC BLOCKER

The brief gives a field-by-field framing at `brief:361-393`, but leaves
sequence integer encoding to a later choice at `:389-391`; the addendum
compresses the same framing into `F(authority_mode, ... payload)` at
`addendum:27-41`. The artifacts also spell the domain separator as `\0` in
one place and as a doubly escaped `\\0` inside Python-looking byte literals at
`brief:388` and `:416`, with no explicit byte-level vector. Null/absent field
encoding is likewise not frozen. This is not a source regression, but it is a
real deterministic-acceptance blocker: S1 must publish a canonical test vector
that fixes NUL bytes, per-field framing, integer/null encoding, and envelope
field inclusion before any hash or replay receipt is accepted.

## Overall decision

`REWORK`. The design has coherent user-end-state criteria, scope boundaries,
and dependency ordering (`NBF-01..06 → S1 → S2 → S3–S6 → S7 → authorized
NBF-07 rebind`). Acceptance remains blocked by the current frozen-identity
drift, malformed CC-043 table row, 62-vs-52 inventory count, sequence gap,
torn-interior skipping, and unfrozen byte-level hash vector. The parser and
old CC-038 warnings should not be treated as current blockers after the latest
artifact rewrites.
