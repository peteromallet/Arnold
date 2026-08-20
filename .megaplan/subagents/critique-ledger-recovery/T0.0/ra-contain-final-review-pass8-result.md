FAIL

Local review of exact candidate `48648b485aa3dc8fc4c5fe9552c31a3df37c61d7` in
`/private/tmp/arnold-critique-recovery-ra-contain-20260802`. No repository source
was edited; `git status --short` was clean.

Pass-7 findings

1. Reconciliation final-CAS response loss: REFUTED for the tested, correctly
   targeted path. The new durable-record matching and retry path in
   `containment.py:1155-1217` recovers both exact replay and a fresh signed
   reconciliation after the response is lost. Covered by
   `test_reconcile_final_cas_response_loss_recovers_by_exact_replay` and
   `test_reconcile_final_cas_response_loss_recovers_by_fresh_signed_reconciliation`.

2. Expiry while waiting for the lock: REFUTED for issue, terminate, and
   reconcile. Each re-verifies the signed envelope after entering the lock
   (`containment.py:1239-1242`, `1258-1260`, `1278-1280`); the three expiry
   tests all reject without mutation.

3. Provisioning genesis response loss: REFUTED for the tested path. The
   provisioning lock, anchor-bound provisioning digest, existing-anchor
   adoption, and journal re-creation make retry with the identical receipt
   recoverable (`containment.py:745-783`, `838-846`). Covered by the genesis
   response-loss, nonce, journal, and metadata failure tests.

4. Terminate ignoring the signed exact target: REFUTED. The active receipt
   target is compared with the signed target before reservation or mutation at
   `containment.py:1264-1267`, and the wrong-target test confirms no mutation.

5. Permissive sequence-zero and pending-head schemas: REFUTED. State-specific
   exact fields, sequence-zero genesis predecessor, and nonzero pending/
   indeterminate sequences are enforced at `containment.py:635-707`; the schema
   regression test passes.

Confirmed blockers

1. Reconcile does not bind the signed exact tuple to the unresolved transition
   or to the result before mutating the owner head.

   A signed reconcile envelope is accepted by `_request` without a target
   (`containment.py:1136-1140`). `reconcile` checks only the signed cursor and
   journal digest against the unresolved head (`1275-1297`), then writes the
   reconcile record and performs the final CAS (`1298-1314`). The later
   `_finish_reconcile_checks` call does not validate the request target for an
   active/terminated result (`1219-1233`), and for an empty result it checks the
   target only after the mutation has already occurred.

   Minimal reproduction: provision a test store, make an issue's final CAS
   response fail so the owner head is unresolved, then sign `reconcile` with
   the same expected cursor/revision but with `workspace="wrong"`. The call
   returns `{"state": "empty", ...}` and `backend.read()["operation"]` becomes
   `"reconcile"`; the wrong tuple is not rejected and the owner sequence
   advances. The same behavior is present for unresolved terminate transitions
   and for durable reconcile-result recovery.

   Probe shape (with the repository test fixture's `SCOPE` and `provision`
   helper):

   ```python
   backend.fail_next("cas_response")
   with pytest.raises(StorageError):
       store.issue(signer.sign_operation(
           operation="issue", journal_path=str(journal),
           anchor_domain=backend.domain_id, target=SCOPE,
           expected_cursor=0, expected_revision=GENESIS_REVISION,
           reason="x"))
   head = backend.read()
   wrong = {**SCOPE, "workspace": "wrong"}
   reconcile = signer.sign_operation(
       operation="reconcile", journal_path=str(journal),
       anchor_domain=backend.domain_id, target=wrong,
       expected_cursor=head["cursor"], expected_revision=head["journal_digest"],
       reason="recover")
   assert store.reconcile(reconcile)["state"] == "empty"
   assert backend.read()["operation"] == "reconcile"  # should be rejected
   ```

   Required correction: persist the original transition's exact tuple (or an
   authenticated target digest) in the pending/indeterminate owner state and
   require the signed reconcile target to match it. Also validate that any
   adopted result's exact tuple equals the signed target before reserving the
   reconciliation nonce or performing either CAS. A target check after the
   CAS is insufficient.

2. Provisioning does not require the provisioning envelope's operation to be
   `provision`.

   `_verify_envelope` accepts `operation` values from `provision`, `issue`,
   `terminate`, or `reconcile` regardless of `expected_type` at
   `containment.py:351-357`. `ContainmentStore.provision` checks mode/genesis
   cursor/revision but never checks `receipt["operation"] == "provision"`
   (`745-755`). A valid owner signature over an envelope with
   `envelope_type="provision"` and `operation="issue"` is therefore accepted
   as the one-time genesis authority and creates the anchor/journal.

   Minimal probe: take a normal `sign_operation(operation="issue", ...)`,
   replace its signed payload's `envelope_type` with `"provision"`, re-sign
   that payload with the same owner key, and call
   `ContainmentStore.provision(..., mode="test")`. It succeeds and creates a
   genesis head whose provisioning envelope still says `operation="issue"`.

   Required correction: make `_verify_envelope` enforce an exact operation for
   each expected envelope type, or add an explicit
   `receipt["operation"] != "provision"` rejection in `provision`, with a
   regression test for a signed wrong-operation provisioning envelope.

Evidence and commands

- `git show --no-ext-diff --stat --oneline 48648b485aa3dc8fc4c5fe9552c31a3df37c61d7`
- `git diff --no-ext-diff --no-renames 25dc026546b9586db63ec0a39e5987321bf4bd0f 48648b485aa3dc8fc4c5fe9552c31a3df37c61d7 --`
- `pytest -q tests/arnold_pipelines/run_authority/test_containment.py` -> 39 passed.
- `pytest -q tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py` -> 70 passed.
- Targeted Python probe: unresolved issue followed by a signed reconcile whose
  target differs only in `workspace`; observed `result empty` and
  `head_operation reconcile`.
- Targeted Python probe: owner-signed `envelope_type="provision"` with
  `operation="issue"`; observed successful genesis provisioning.
- `git diff --check` passed.

The focused tests pass, but this is only a local candidate review. It does not
prove formal T0.0 and does not authorize cloud containment.
