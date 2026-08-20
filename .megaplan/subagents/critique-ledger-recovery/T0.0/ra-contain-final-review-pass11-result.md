# RA-CONTAIN Final Independent Review — Pass 11

## Overall verdict: FAIL

This is a hard FAIL. The local candidate has two authority-safety blockers that
are not covered by the green repository tests, plus an incomplete stale-CAS
durability check.

## Exact target and tree evidence

- Reviewed worktree: `/private/tmp/arnold-critique-recovery-ra-contain-20260802`
- Required commit and observed HEAD: `6ec8066041687fa45c3e2b71760ec7874f8d027a`
- Clean worktree before review: yes; `git status --porcelain=v1 --untracked-files=all` emitted no entries.
- Clean worktree after review: yes; the same command emitted no entries.
- Source bytes were read with `git show <exact-commit>:<path>` and independently matched the worktree bytes.
- `arnold_pipelines/run_authority/containment.py` SHA-256: `0c0d6c15b64956d3a79d6065fadb35da66c0487d22be8b787e6efc235e30e862`
- `tests/arnold_pipelines/run_authority/test_containment.py` SHA-256: `027da07cef262a3429438dd9ca386f3ddcbd6a7e36c4f0293510891bc33cb847`
- Exact-commit `git show` SHA-256 values matched those two worktree values.

## Ranked findings

| Rank / severity | Exact code | Independent reproduction | Result and consequence |
|---|---|---|---|
| 1 — Critical | `containment.py:1266-1275`, `_transition`; also `1282-1291`, `_finish_pending`, and `1384-1392`, `_resume_durable_reconcile` | Disposable inline probe command: `PYTHONDONTWRITEBYTECODE=1 python - <<'PY' ... ClaimsExactNoDurable ... PY` | A backend returned a fully authenticated exact prepared committed head but did not change its durable head. `issue()` returned `active`; durable owner head remained `pending`; subsequent `status()` raised `IndeterminateState`. `_validate_committed_cas_response()` (`1216-1221`) validates only the returned object and never rereads durable owner state/journal after a successful CAS. This is false positive authority and a head/journal divergence. |
| 2 — Critical | `containment.py:1159-1198`, `_mark_unknown`; `489-501`, `InMemoryOwnerAnchorBackend.record_indeterminate` | Same independent probe, `RaceConflict`: `read()` returned the expected pending head and then installed a different valid committed direct child before `record_indeterminate()` ran. | The call failed with `StorageError`, but the durable conflicting committed head was replaced by `indeterminate`. The client-side read/check at `1173-1190` is TOCTOU; the backend acknowledgement accepts any direct child matching only predecessor revision/sequence at `496-501`, not the exact authenticated head/transition identity. A stale acknowledgement can overwrite a concurrent conflicting authority head. |
| 3 — High | `containment.py:1223-1250`, `_accept_already_committed_cas`; especially `1235-1243` | Independent `CorruptingStale` probe after a durable exact commit deleted/changed `used_nonces` or deleted `identities`, then raised `StaleCAS`. | `_accept_already_committed_cas()` returned success for `nonce_missing`, `nonce_wrong`, and `identity_missing`. It checks current head and selected journal fields, but not the durable nonce binding or all identity/result rows. Exact replay can later become `IndeterminateState`, and nonce/idempotency safety is not proven at the stale linearization point. Result/tuple/hash-chain corruption, missing record, malformed record, fork, and predecessor mutations were rejected. |
| 4 — High / contract gap | `containment.py:1201-1203`, `_head_fields_equal`; `648-658`, `_validate_head`; test backend `542-553`, `verify_receipt` | Independent `ReceiptSwapStale` probe replaced the backend receipt with a different valid self-signed key/signature while preserving all non-receipt head fields and raised `StaleCAS`. | The stale path accepted the byte/receipt-different head. The comparison deliberately excludes `backend_receipt`, while the shipped test verifier trusts the public key supplied inside that receipt. An accepted production backend must pin and independently authenticate its receipt key and durable receipt; this local candidate does not demonstrate that invariant. This compounds finding 1 for backend dishonesty. |

## Pass-8 through pass-10 blocker reproduction matrix

| Prior thread | Independent Pass 11 disposition | Evidence |
|---|---|---|
| Pass 8: wrong signed reconcile target could mutate unresolved issue | Fixed | `_validate_reconcile_target()` at `1036-1044` runs before nonce/journal/CAS; repository regression and independent review of pending/indeterminate paths showed no mutation. |
| Pass 8: wrong signed reconcile target could mutate unresolved terminate | Fixed | Same target binding plus terminate target check at `1461-1465`; focused regression passed. |
| Pass 8: wrong target during durable reconcile/response-loss retry | Fixed | `_validate_reconcile_record()` at `1061-1070`, durable lookup at `1314-1360`, and pre-mutation checks; repository regressions passed. |
| Pass 8: `envelope_type=provision` accepted `issue`, `terminate`, or `reconcile` | Fixed | Exact map at `49-52` and `_verify_envelope()` at `332-336`; three wrong-operation regressions passed with no anchor/journal/nonce mutation. |
| Pass 9: reconciliation could commit and then fail due to expiry/policy/status | Fixed locally | Preflight and one evaluation time at `1395-1430`; expired candidate adoption and post-CAS-read regression passed. The expiry policy is correctly separated from later `check()` denial. |
| Pass 10: final CAS response/no-effect response was ignored | Still present, transformed | Response-field validation was added at `1216-1221`, but no durable reread follows a response that is exact yet never applied. Independent `ClaimsExactNoDurable` produced false `active` success with a pending durable head. |
| Pass 10: genuine final `StaleCAS` lost its type | Fixed for tested exact/conflicting stale cases, but incomplete | Exact durable stale was accepted; conflicting stale propagated `StaleCAS`; read-after-stale failure produced `IndeterminateState`. The stale acceptance still ignores durable nonce/identity state and accepts a receipt-different equivalent head. |

## Explicit answer: `_mark_unknown`

Yes, it can advance or overwrite a concurrently committed/conflicting head.

- Exact response loss after a committed candidate: the independent
  `ResponseLoss` probe returned `StorageError` and changed the exact committed
  candidate to an `indeterminate` child (`head_sequence=3`, occurrence present).
  That is an intentional recovery transition, but it is still an overwrite of
  the committed head and must be guarded by an atomic exact-head predicate.
- Conflicting concurrent head: the independent `RaceConflict` probe installed
  a different valid committed direct child after `_mark_unknown()` read the
  expected head. The final durable state was `indeterminate`, not the
  conflicting committed head. This reproduces an actual overwrite, not merely
  a rejected stale response.
- Altered head observed before acknowledgement is safer: the safe-head equality
  check refuses it. A stale owner read raises `IndeterminateState` and leaves the
  pending head unchanged. Those checks do not close the read-to-acknowledgement
  race.
- A dishonest `record_indeterminate()` response that claims a marker while
  leaving the durable head pending still caused the operation to fail closed,
  but `_mark_unknown()` accepted the unverified response and did not reread it.

Required correction: make owner-side indeterminate acknowledgement a
linearizable CAS over the complete expected authenticated head/transition
identity (including operation, target digest, candidate fields, predecessor,
and request/record digests), and verify the durable post-result head. Do not
allow a generic “direct child of this revision” marker to replace another
writer’s child. If the exact candidate is already durably committed, reconcile
that exact candidate or create a marker only through an owner-side exact CAS.

## Explicit answer: `_accept_already_committed_cas`

Partially. It rejects many mismatched records, but it can accept mismatched
durable idempotency state.

- Accepted correctly: exact durable commit after `StaleCAS` returned `active`
  and `status()` was committed.
- Rejected: missing record, malformed record, altered result, altered tuple,
  predecessor/fork mutation, and journal truncation all raised
  `IndeterminateState` in the independent probe. The authenticated head-field
  comparison is strict for every `_HEAD_FIELDS` member except
  `backend_receipt`.
- Incorrectly accepted: deleting `used_nonces`, changing its request digest,
  or deleting all `identities` still produced success (`ACCEPTED`) because
  `1235-1243` checks only the current head and a matching journal record hash,
  request digest, operation, and result. It does not independently compare the
  nonce and identity rows at the stale linearization point.
- Incorrectly accepted: a different valid self-signed backend receipt with the
  same non-receipt fields was accepted because `_head_fields_equal()` excludes
  `backend_receipt` and the test verifier trusts the receipt’s embedded key.

Required correction: validate one exact durable receipt/record bundle before
accepting stale success: authenticated head including a pinned backend receipt,
record cursor/prior hash/full field set/hash/result/tuple, nonce-to-request
binding, and every operation identity-to-request/result binding. Any missing,
altered, malformed, or unreadable member must remain typed indeterminate or
stale, never success.

## Branch and attack coverage matrix

| Required case | Result | Evidence |
|---|---|---|
| Exact prepared CAS response | Response fields validated; durable application not proven | `1216-1221`; no-op exact-response independent FAIL probe. |
| Unchanged/no-effect CAS response | Rejected when it is the old head | Focused `test_final_cas_response_must_be_the_exact_authenticated_candidate`; 18-test negative rerun passed. |
| Altered CAS response | Rejected and routed to uncertainty | Focused regression passed. |
| Malformed/missing receipt CAS response | Rejected and routed to uncertainty | Focused regression passed. |
| Backend claims exact success but durable head disagrees | FAIL | Independent `ClaimsExactNoDurable`: returned active, durable pending, later status indeterminate. |
| Durable commit but response loss | Recoverable, but `_mark_unknown` advances exact commit to indeterminate | Independent `ResponseLoss`; exact replay/reconcile repository tests passed. |
| Exact commit followed by `StaleCAS` | PASS for exact head + journal record; incomplete for side records/receipt | Independent exact stale and corruption probes. |
| Conflicting `StaleCAS` | PASS in covered honest path; typed `StaleCAS`, no overwrite | Focused test and dependency suite passed. |
| Stale-read failure | PASS fail-closed; `IndeterminateState`, no mutation | Independent `StaleRead` and focused regression. |
| `record_indeterminate` response loss/dishonesty | FAIL as a proof boundary: response is validated but not durably reread | Independent fake-response probe left durable head pending while `_mark_unknown` accepted the fake response; operation still failed closed. |
| Exact-head concurrency for `_mark_unknown` | FAIL | Independent `RaceConflict` overwrote a different direct-child committed head. |
| Rollback of paired journal/head | PASS | Focused rollback and snapshot tests passed. |
| Journal fork/truncation/predecessor mutation | PASS for detected corruption; stale helper rejected probes | Focused rollback/fork tests and independent corruption modes. |
| Nonce reuse | PASS for ordinary replay/conflict tests | Focused replay and divergent identity tests passed. |
| Nonce mutation/missing nonce durable state | FAIL in stale acceptance | Independent `nonce_missing` and `nonce_wrong` were accepted. |
| Head/journal mutation | PASS when digest/authentication changes are visible; FAIL for exact response with no head mutation | Focused rollback/schema tests plus independent no-op durable probe. |
| Restart and durable replay | PASS for covered local adapter exact replay | Focused restart tests and dependency suite passed; does not cure stale side-row acceptance. |
| Issue branches | FAIL on dishonest exact final CAS; normal, response-loss, expiry, replay branches otherwise exercised | `1266-1275`, focused 55/55 plus independent issue probe. |
| Terminate branches | Normal/wrong-target/response-loss/replay pass locally; shared final-CAS and stale-side-row defects remain | `1461-1470`, shared `_transition` path, focused suite. |
| Reconcile normal branch | Expiry/adoption and pre-CAS validation pass; shared `_finish_pending` exact-response defect remains | `1472-1521`, focused expiry/post-CAS tests, independent no-op class. |
| Durable reconcile replay | Target/result/hash checks pass; shared final-CAS proof and stale-side-row checks remain incomplete | `1379-1392`, focused durable recovery tests. |
| Expired candidate reconciliation | PASS locally: adopts authenticated result | Focused expiry test passed; independent prior-result reproduction was reviewed. |
| Later policy denial after expiry | PASS locally: `check()` refuses expired active receipt | Focused expiry test passed. |
| Wrong signed tuple/target | PASS for issue/terminate/reconcile pre-mutation checks | `1036-1070`, `1461-1465`, focused wrong-target tests. |
| Wrong decision/result tuple | Result/tuple corruption rejected; stale side metadata is not complete | Independent `result_mismatch`/`tuple_mismatch` rejected; nonce/identity mismatch accepted. |
| Wrong nonce/request identity | FAIL in `_accept_already_committed_cas` | Independent nonce and identity corruption modes accepted. |
| Wrong predecessor/head/fork | PASS when journal/head digest changes are detected; TOCTOU conflict is FAIL | Independent predecessor/fork rejection plus `RaceConflict`. |
| Fixed-clock, NaN, bool, multiple-clock bypass | PASS in local candidate | `_evaluation_time()` at `1395-1399`, finite parsing, focused nonfinite/TTL tests. |
| All seven effects | PASS locally: observe allowed while six denied; terminated/expired states fail closed | `DENIED_EFFECTS`/policy code and focused policy tests. |
| Production fail-closed owner absence | PASS for this local candidate | Production constructor/provisioning reject at `757-758`, `774-781`; CLI rejects absent accepted GEN-DEPLOY backend at `1588-1590`. This is not production-owner proof. |

## Tests and commands

All test commands used `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.

- `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/arnold_pipelines/run_authority/test_containment.py` — exit 0; **55 passed in 1.98s**.
- `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py` — exit 0; **86 passed in 2.11s**. This covered the Run Authority contracts, reducer, store, and dependency-closure tests; no repository caller imports the containment API beyond the public package export.
- `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/arnold_pipelines/run_authority/test_containment.py -k 'final_cas or stalecas or rollback or wrong_target or state_specific or response_loss or external_anchor_uncertainty or expired_candidate'` — exit 0; **18 passed, 37 deselected in 0.32s**.
- Independent probe command: `PYTHONDONTWRITEBYTECODE=1 python - <<'PY' ... PY` from the exact worktree, using only in-memory backends and disposable `tempfile` directories. Exit 0. Key output: `cas_response_exact_but_no_durable_mutation: active durable_head= pending post_status= IndeterminateState`; `mark_unknown_concurrent_conflict: outcome= StorageError durable_head_after= indeterminate flipped= True`; `mark_unknown_exact_response_loss: outcome= StorageError head_state= indeterminate head_sequence= 3 occurrence= True`; `mark_unknown_stale_read: outcome= IndeterminateState durable_head= pending`; `mark_unknown_fake_response_no_mutation: outcome= StorageError durable_head= pending`; exact stale `active status= committed`; `accept_mismatch_missing_record: IndeterminateState`; `accept_mismatch_nonce_missing: ACCEPTED`; `accept_mismatch_nonce_wrong: ACCEPTED`; `accept_mismatch_identity_missing: ACCEPTED`; result/tuple/predecessor/malformed modes all `IndeterminateState`.
- Independent receipt probe: `PYTHONDONTWRITEBYTECODE=1 python - <<'PY' ... ReceiptSwapStale ... PY` — exit 0; `accept_receipt_byte_difference: ACCEPTED state= active`.
- `git diff --check 6ec8066041687fa45c3e2b71760ec7874f8d027a -- arnold_pipelines/run_authority/containment.py tests/arnold_pipelines/run_authority/test_containment.py` — exit 0; no output.
- Final `git rev-parse HEAD; git status --porcelain=v1 --untracked-files=all` — exit 0; exact HEAD and no status entries.

## Required corrections

1. Replace response-object-only final-CAS success with an owner-side
   linearizable durable commit receipt, or reread and authenticate the owner
   head and journal after every successful CAS before returning any positive
   issue/terminate/reconcile result. A response that is exact but not durable
   must become typed indeterminate, never success.
2. Replace `_mark_unknown` read-then-`record_indeterminate` with an atomic
   exact-head/transition CAS. The owner operation must reject any competing
   child, altered head, changed target, changed candidate, predecessor, nonce,
   or record identity; verify the durable result after acknowledgement.
3. Make `_accept_already_committed_cas` validate the complete durable bundle,
   including pinned backend receipt, full record/hash-chain/result/tuple,
   nonce binding, and all identity rows. Missing or altered side state must
   remain stale/indeterminate.
4. Add independent regressions for exact-success/no-durable-effect,
   read-to-marker concurrent conflict, nonce/identity corruption during stale
   recovery, and receipt-key/receipt-byte substitution.

Local PASS is not formal T0.0 completion, an accepted Run Authority
containment decision, or production-owner/install proof. This review does not
authorize cloud mutation.
