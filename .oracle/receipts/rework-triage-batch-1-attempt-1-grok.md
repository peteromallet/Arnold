# Receipt — NBF-01 Batch 1 rework triage, attempt 1 (Grok 4.6)

- Oracle: Grok 4.6 (manager/validator only)
- Date: 2026-08-30
- Role: supplemental rework triage after `ACCEPTED_ISSUES`
- Implementation performed: **none**
- Commit / push / merge / Batch 2: **none authorized, none performed**

## Source identities (verified this turn)

| Artifact | SHA-256 / git identity |
| --- | --- |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen working tree) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/checkins/batch-1-grok.md` | `916356111c7882e23f00df2bc50d92e533329895760aca3b890d6771fc1c4514` |
| `.oracle/checkins/batch-1-luna.md` | `7d19a34bc086df1d383d8083ed07f6214151ec55d3b3317609c4506a7af1ede7` |
| `.oracle/receipts/execution-nbf01-luna.md` | `82ae9d7568c96bb9fdc9caa617721d61a18f6d850994f5d1d35236f47e6ddc99` |
| `.oracle/findings/execution-nbf01-luna.md` | `845fb92798b4cafbd2768a587672d617827f25f400d9315a63834009aca59f97` |
| `.oracle/custody.md` (unchanged this turn) | `29f7ad58cfa9057ccc02006d70fede01ab5f4a38a3e351acd762a545ed3ae608` |
| `.oracle/receipts/oracle-nbf01-grok.md` | `38eb9880caba5125adc55338b05267d77db3f18e0bbd7251d78573e09858ab59` |
| `.oracle/receipts/model-policy-grok-switch.md` | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Merge-base with `origin/main` | `798c50619204010ed3f4297fbb57988fe9381924` |

Supplemental tasklist written this turn:

- Path: `.oracle/rework/batch-1-attempt-1.md`
- SHA-256: `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c`

That path previously held foreign onboarding residue (`detect.py` / `catalog.py`). It was replaced with this NBF-01 rework tasklist only. Frozen `.oracle/tasklist.md` was not mutated.

## Triage result

NBF-01 remains **unaccepted**. The eight Grok-accepted issues collapse to **six
Luna implementation tasks**, **one separately authorized custody-document
task**, and **one Oracle gate**. `[XHARD]` items: **none**.

Executor for RW-01..RW-06 and RW-CUSTODY: GPT-5.6 Luna. Grok 4.6 remains
Oracle and RW-GATE only. This follows the user-pinned model policy in
`.oracle/receipts/model-policy-grok-switch.md` without rewriting the frozen
tasklist (which still historically names Sol as Oracle).

## Eight-to-task mapping

| Issue | Severity | Task | Classification | Executor |
| --- | --- | --- | --- | --- |
| 1 Atomic CAS / one ledger door | blocker | RW-01 | normal | Luna |
| 4 Forgeable terminal/reconciliation context | blocker | RW-01 | normal | Luna |
| 2 Strict schema and illegal-state matrix | blocker | RW-02 | normal | Luna |
| 3 Evidence-bound changed-precondition producers | blocker | RW-03 | normal | Luna |
| 5 Global/incomplete keyed provider replay | major | RW-04 | normal | Luna |
| 6 Timestamp-only two-scan confirmation | major | RW-05 | normal | Luna |
| 7 Incomplete disposition CLI contract | major | RW-05 | normal | Luna |
| 8 Thin/mutated acceptance evidence | major | RW-06 | normal | Luna |
| Custody `f8725af...` vs `798c506...` | evidence | RW-CUSTODY | normal | Luna |
| Fresh review + Oracle decision | gate | RW-GATE | Oracle | Luna review, Grok verdict |

Merge rationale: issues 1 and 4 share the `IncidentLedger` lock/read/compare
append seam (binding *is* the compare). Issues 6 and 7 share Contract G
(CLI status 5 requires consumed confirmation; status 4 requires ledger-location
validation). Issue 5 stays separate so keyed `projection()` cannot be declared
done by only wrapping the current global streak in a lock. Issue 3 stays
schema-side producer derivation, consuming the RW-01 locked door.

Ordinary deterministic contract/test breadth is not an exceptional threshold.
Plan §7 already classified NBF-01 schemas/projection/CAS as Normal / Luna.

## Custody-source correction

`.oracle/custody.md` still opens with Base SHA
`f8725af516da8d4249eb0d63563c37776d80daf8` and later records refreshed
`798c50619204010ed3f4297fbb57988fe9381924`. The live immutable source base is
the latter.

**Decision:** this is **not** an in-band production fix and **not** silent
receipt-only labeling. It requires the separately authorized evidence-only
task **RW-CUSTODY**, which may edit `.oracle/custody.md` only to mark
`f8725af...` historical and keep `798c506...` current. This triage did **not**
edit custody.md. Frozen tasklist, candidate code, and git source base must not
be altered by that task.

Until RW-CUSTODY lands, every new receipt must still treat `f8725af...` as
historical and `798c506...` as current.

## Evidence-mutation correction

The executor receipt is internally contradicted and must not be rewritten:

- Same path `.oracle/receipts/execution-nbf01-luna.md` claimed focused **52**
  passed at start-gate, then mutated to focused **61** passed.
- Luna independently reproduced focused `61 passed` and legacy `78 passed`.
- Claimed owned production digest
  `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`
  does not reproduce.
- Luna computed
  `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`
  for `git diff origin/main --` over the five modified owned production files
  at the failed handoff.

This is evidence mutation / integrity work (RW-06 + RW-GATE), not a typo.
New command transcripts and a digest bound to the **post-rework** candidate
must be written to new paths
`.oracle/findings/execution-nbf01-rework-attempt-1-luna.md` and
`.oracle/receipts/execution-nbf01-rework-attempt-1-luna.md`. Do not fabricate
a 52-test history or retarget test count.

## Remaining blockers

Production blockers until RW-01..RW-05 pass and RW-06/RW-GATE evidence is
internally consistent:

- Unlocked compare-then-append on reservation, terminal, child, change,
  probe, and reconciliation.
- Incomplete DispatchOutcome payload matrix and permissive OOM / unknown-death
  codecs.
- Caller-forgeable changed-precondition identities.
- Unkeyed provider streak reducer.
- Timestamp-only confirmation and dead/missing CLI statuses 4/5.
- Thin sequential tests plus mutated executor evidence.

Non-blockers for this triage: later-batch admission/scheduler/T7/T8/physical
doors/signal wiring remain correctly out of scope. File-scope of the failed
candidate was MET.

## Final recommendation

Dispatch GPT-5.6 Luna on `.oracle/rework/batch-1-attempt-1.md` in order
RW-02 → RW-01 → RW-03 → RW-04 → RW-05 → RW-06 (RW-CUSTODY parallel). Then one
independent Luna review and a separate Grok Oracle decision. Do not commit,
push, merge, or start Batch 2 on this candidate until that Oracle returns
`PASS_BATCH_1`.

```text
REWORK_TASKLIST_READY
NBF-01_UNACCEPTED
BATCH_2_PROHIBITED
NO_IMPLEMENTATION_PERFORMED
```
