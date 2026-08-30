# Receipt — NBF-01 Batch 1 rework triage, attempt 2 (Grok 4.6)

- Oracle: Grok 4.6 (manager/validator only)
- Date: 2026-08-30
- Role: second supplemental rework triage after attempt-1 `ACCEPTED_ISSUES`
- Implementation performed: **none**
- Production / test / frozen-plan / custody / historical-receipt edits: **none**
- Commit / push / merge / Batch 2 / second reviewer: **none authorized, none performed**

## Source identities (verified this turn)

| Artifact | SHA-256 / git identity |
| --- | --- |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen working tree) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/custody.md` (unchanged this turn) | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Attempt-1 rework tasklist `.oracle/rework/batch-1-attempt-1.md` | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Attempt-1 executor receipt | `1acba71b835c7bb2d854773d200c988f1fd344fa4ecdfab8eb64306ba7c69143` |
| Attempt-1 executor finding | `e7607cf15818e2c05b1fc997d92a06f133fe98e12d543e6d8555ddea96192f91` |
| Custody receipt | `48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9` |
| Attempt-1 Luna review `.oracle/checkins/batch-1-rework1-luna.md` | `cdc6cd9b0ecfc3097c0c2940bb9ce85b810a84ab81ceb777ead97dfdc86ec89b` |
| Attempt-1 Grok check-in `.oracle/checkins/batch-1-rework1-grok.md` | `2d82e2d09e1ff7e49ac895878a5cbabc19e19dda4d109bd528da54c83e6b79a8` |
| `.oracle/receipts/model-policy-grok-switch.md` | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Merge-base with `origin/main` | `798c50619204010ed3f4297fbb57988fe9381924` |
| Current owned production diff (observation) | `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801` |

The attempt-2 Oracle brief bound `cdc6cd9b...` under the label "attempt-1 Grok
check-in". Independent hashing shows that digest is the **Luna** review; the
Grok check-in digest is `2d82e2d0...`. Both identities are recorded. This is
brief labeling, not a custody or history mutation.

Supplemental tasklist written this turn:

- Path: `.oracle/rework/batch-1-attempt-2.md`
- SHA-256: `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721`

Frozen `.oracle/tasklist.md` and settled plan v8 were not mutated.

## Triage result

NBF-01 remains **unaccepted**. The seven still-accepted findings collapse to
**four Luna implementation tasks** and **one Oracle gate**. `[XHARD]` items:
**none**.

Executor for RW2-01..RW2-04: GPT-5.6 Luna. Grok 4.6 remains Oracle and
RW2-GATE only. Custody correction is already MET; it is **not** in this
tasklist.

## Seven-to-task mapping

| Finding | Severity | Task | Classification | Executor |
| --- | --- | --- | --- | --- |
| 1 One-door CAS / reservation-bound context | blocker | RW2-01 | normal | Luna |
| 2 Incomplete strict schema matrix | blocker | RW2-01 | normal | Luna |
| 3 Caller-controlled changed-precondition authority | blocker | RW2-01 | normal | Luna |
| 4 Keyed provider replay | major | RW2-02 | normal | Luna |
| 5 Durable two-scan confirmation and CLI | major | RW2-03 | normal | Luna |
| 6 Thin acceptance evidence | major | RW2-04 | normal | Luna |
| 7 Generic aliases/constructors | minor | RW2-04 | normal | Luna |
| Fresh execution + Oracle decision | gate | RW2-GATE | Oracle | Luna review, Grok verdict |

Merge rationale: findings 1–3 share the existing journal lock plus the
decode/append validators and producers that feed it. Finding 4 stays a
separate reducer so keyed replay cannot be declared done by wrapping the
current broadcast-reset in a lock. Finding 5 is Contract G
(confirmation + CLI). Findings 6 and 7 are evidence-protocol plus unofficial
surface deletion on existing types, not a new abstraction.

Ordinary deterministic contract/test breadth is not an exceptional threshold.
Plan §7 already classified NBF-01 as Normal / Luna. Attempt 1 did not meet
`[XHARD]`; attempt 2 does not either.

## Custody and historical-evidence decisions (preserved)

- `f8725af516da8d4249eb0d63563c37776d80daf8` is **historical**.
- Current immutable source base remains
  `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- RW-CUSTODY is **MET**. No further custody edit is requested or performed.
- Original handoff 52→61 focused-count mutation and unreproducible
  `4aee815d...` remain historical evidence-integrity failures. Do not rewrite
  those receipts.
- Failed-handoff Luna digest `50c86490...` remains a historical snapshot.
- Attempt-1 focused **78** / legacy **78** and production digest `e060f650...`
  are observations, not waivers or targets. Bound current attempt-1 transcripts
  live under `/tmp/oracle-nbf01-rework1-luna/` (focused stdout SHA-256
  `9cf73370...`; legacy `84f2299b...`). They do not satisfy the missing named
  behavioral matrix.

## Remaining work (not implemented this turn)

Independent re-read of the candidate confirmed the seven findings still hold.
Prior-MET work to preserve includes `_locked` wrapping, C03–C06/C08/C12/
C15–C18/C25/C26-shape/C35, one journal, and the real two-process reservation
race. Remaining holes include: provider-exhaustion logical-ID skip and empty
reservation-field bypass; marker-ID reconciliation; invalid-replay filter
rather than fail-closed; ordinary-failure+`success_payload` and
provider-exhausted+`terminal_failure`; generic `**kwargs` producers and
incoherent forged-hash test; same-base broadcast streak reset and ignored
key before/after; optional confirmation identity plus helper-side
`projection()`; missing required pytest names (terminal races, recovered
disposition, keyed isolation-by-value, CLI named statuses, torn composite);
and unofficial aliases at `ledger.py:761-772`.

## Final recommendation

Dispatch GPT-5.6 Luna on `.oracle/rework/batch-1-attempt-2.md` in order
RW2-01 → RW2-02 → RW2-03 → RW2-04 (RW2-02 and RW2-03 may run in parallel after
RW2-01). Require one fresh Luna execution receipt/finding with complete
argv/cwd/exit/stdout/stderr and per-command SHA-256 bound to the actual
candidate, then one separate Grok Oracle decision. Do not commit, push,
merge, mutate the frozen tasklist or plan, rewrite historical evidence, edit
custody, or start Batch 2 until that Oracle returns `PASS_BATCH_1`.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
XHARD_NONE
CUSTODY_MET_NO_FURTHER_EDIT
NO_IMPLEMENTATION_PERFORMED
```
