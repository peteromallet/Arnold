# RA-CONTAIN pass 12 repair result

## Scope and verdict

The requested pass-12 implementation repair is complete in the authorized local
review worktree. This is **not** formal T0.0 completion, an owner-installed
production boundary, a checklist/evidence-manifest completion claim, or a
cloud/provider verification. No cloud, remote, owner store, or checklist state
was mutated.

- Worktree: `/private/tmp/arnold-critique-recovery-ra-contain-20260802`
- Exact starting commit: `78641320e491a0f173efbba9e69b7981dd11e260`
- Repair commit: `88393e2d0da80d76205ba03ddabf7577d864306b`
- Tree: `757f8522c9fc174718d3b8f45d13808bc1f9b2b4`
- Commit subject: `Complete RA containment replay proofs`
- Final worktree status: clean

## Implemented repairs

### 1. Complete ordinary replay proof

Ordinary issue/terminate/reconcile replay now holds a SQLite `BEGIN IMMEDIATE`
transaction while validating the exact canonical bundle:

- all three expected identity keys (nonce, idempotency, operation), with no
  missing or extra identity bound to the request digest;
- the unique nonce row and exact nonce-to-request binding;
- the exact persisted signed request bytes/material;
- one exact operation record, its result digest, the full replayed journal/hash
  chain, and the latest record/head binding;
- the current authenticated owner head through the backend's atomic durable
  proof operation;
- the canonical complete operation receipt and its finalization state.

Any partial projection is treated as corruption/indeterminate state rather than
fresh authority or accepted replay. Conflicting nonce/identity bindings remain
typed duplicate conflicts. The unresolved reconciliation recovery branch is
kept separate: it validates its exact local durable bundle but does not claim a
committed receipt until reconciliation establishes and proves the final head.

### 2. Materialized local proof linearization

`LocalTestOwnerAnchorBackend.verify_durable_commit()` and
`verify_indeterminate()` now:

- acquire the same cross-process file lock used by read/CAS/marker operations;
- reload the persisted anchor, nonce map, key, and pinned receipt identity;
- run exact-head proof while holding that lock;
- compare the durable bytes before/after proof and require the decoded bytes to
  equal the verified in-memory state.

Anchor replacement also fsyncs the containing directory. A peer writer landing
between final CAS and proof is reloaded and causes fail-closed indeterminate
handling; the stale in-memory head is no longer returned as success.

### 3. Canonical complete returned receipts

Issue and terminate now return a canonical operation receipt containing the
decision/result plus:

- canonical target and effect policy;
- full signed request material, request digest, nonce, idempotency key, exact
  operation identity, and all identity bindings;
- exact journal record, cursor, prior hash, record hash, and journal digest;
- backend domain, pinned receipt identity, exact committed backend head and
  backend receipt;
- owner/capability/trust identity;
- decision content digest and a hash over the complete bundle.

The receipt is durably staged with the journal transaction before final CAS and
finalized only after atomic backend proof. This closes the crash window without
turning deletion into silent reconstruction: an unfinalized intent may be
promoted only when it exactly equals the latest authenticated committed head;
a missing finalized receipt or altered receipt fails closed. Exact replay after
restart and after later legitimate history returns the original receipt bytes.

## Adversarial regression coverage

Added tests cover:

- deletion of the operation identity, nonce row, request row, or nonce plus
  idempotency identities;
- an extra forged identity and a wrong nonce binding;
- complete receipt field/hash checks;
- exact replay across restart, simulated crash-before-finalization, termination,
  and later journal history;
- exact terminate receipt replay;
- missing or byte-altered complete receipts;
- a second materialized backend writing a peer child between final CAS and
  durable proof.

Existing response-loss, stale-CAS, reconcile, crash/restart, malformed/forked
journal, receipt-key substitution, two-process race, expiry, and policy tests
remain passing. In particular, authenticated expired history can still be
adopted, while later policy checks deny expired authorization.

## Validation

All Python test commands used `PYTHONDONTWRITEBYTECODE=1` and pytest used
`-p no:cacheprovider`.

- Containment suite: **78 passed**.
- Run-authority plus dependency closure: **109 passed**.
- Focused replay/restart/receipt/nonce/identity/final-CAS/stale-CAS/response-loss/
  expiry/materialized selection: **40 passed, 38 deselected**.
- New pass-12 focused selection: **10 passed, 68 deselected** before the final
  crash-finalization assertion was folded into the complete-receipt test.
- AST parse: passed.
- `git diff --check` and `git diff HEAD^ HEAD --check`: passed.
- Ruff: 63 repository-baseline findings (compact one-line style and two existing
  unused imports/locals); no pass-12-specific blocking finding.
- Mypy: 9 repository-baseline findings: 8 in `contracts.py` and the existing
  `ArgumentParser.error` override in `containment.py`; no pass-12-specific error.

Changed files and SHA-256:

- `arnold_pipelines/run_authority/containment.py`
  `a272bd21a3ca37298f8ebb05753fddfaf7cd2ac0ac8205115b779df587527d28`
- `tests/arnold_pipelines/run_authority/test_containment.py`
  `1b3d772d2248bdad857e54e1526506dd918c6f89bc988b0f387076092908094e`

Only those two files are in the repair commit. This report is outside the review
worktree and is not included in that commit.

## Explicit remaining boundary

The checkout still intentionally has no accepted production Release Authority
adapter. Production owner/install evidence, admission authority, leases/epochs/
fences, cloud/provider ambiguity, observer validation, and formal T0.0 closure
remain external prerequisites. This repair makes the authorized local
test/materialized boundary fail closed; it does not claim those prerequisites
exist.
