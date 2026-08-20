# RA-CONTAIN Pass 11 repair result

## Verdict

**PASS — implementation repair complete in the authorized local review worktree.**

This is not formal T0.0 completion, production-owner/install proof, or cloud/remote
verification. The accepted production Release Authority backend is not shipped in
this checkout and no cloud mutation was authorized or performed.

## Commits and files

- Exact starting commit: `6ec8066041687fa45c3e2b71760ec7874f8d027a`
- Final commit: `78641320e491a0f173efbba9e69b7981dd11e260`
- Commit message: `Harden RA-CONTAIN durable authority proofs`
- Changed files only:
  - `arnold_pipelines/run_authority/containment.py`
    - SHA-256: `8c92e9dbd2ed99d641da130bc747d56855be30943c9bfba31139affe6f0068f5`
  - `tests/arnold_pipelines/run_authority/test_containment.py`
    - SHA-256: `1c90cb7e9d05eb9eae3549f458014d0d6741242c06029b322730118a22d2cff2`

The final commit contains exactly those two files; the result report is outside
the review worktree and was not committed there.

## Finding repairs and linearization contract

1. **Durable final CAS proof.** The old response-object validation could accept an
   exact authenticated response without proving that the owner head changed. The
   backend interface now requires `verify_durable_commit()`. Every issue,
   terminate, ordinary reconciliation, and durable reconciliation final CAS path
   validates the exact prepared head including its pinned receipt, then validates
   the complete SQLite record/request/nonce/identity/result bundle inside a
   `BEGIN IMMEDIATE` transaction held across the backend proof. The local backend
   atomically locks and compares its durable head and rejects a no-op head. Thus an
   exact but non-mutating CAS response becomes `IndeterminateState`; a response
   loss after a true commit remains recoverable through exact stale adoption.

   The linearization point is the backend's atomic durable-proof operation while
   the journal writer transaction is held. An accepted external adapter must
   implement that operation as an owner-side atomic verification of the exact
   head and supplied bundle; a plain unbound post-read is not a valid adapter.

2. **Atomic `_mark_unknown`.** The old read-then-ack path supplied only revision
   and sequence and could replace a competing child. `record_indeterminate()` now
   receives the complete authenticated expected head and authenticated attempted
   transition, validates the exact head under the backend lock, binds transition
   operation/state/sequence/predecessor/target/candidate/request fields, and
   rejects concurrent or altered heads without mutation. The acknowledgement is
   followed by atomic `verify_indeterminate()`; a fake marker response is not
   accepted.

3. **Complete stale-CAS bundle validation.** `_accept_already_committed_cas()`
   now requires exact full head and receipt equality, full replayed journal/hash
   chain and record bytes, an exact persisted signed request, unique nonce
   membership and request binding, and the complete expected identity/result
   rows. Missing, wrong, duplicate, malformed, forked, truncated, or predecessor-
   mutated state remains typed indeterminate (while a genuine conflicting head
   remains `StaleCAS`).

4. **Receipt identity/content pinning.** Backend receipts are now deterministic
   canonical content, included in head identity comparison, and verified against
   the backend's independently configured public key rather than a key supplied
   only by the receipt. The journal stores the trusted receipt identity. The local
   restart adapter additionally persists `.test-receipt-authority` beside its
   `.test-key`; replacement key material or a changed identity fails closed, and
   the store checks the pinned identity on every anchor read.

Pass-9 expiry behavior remains intact: authenticated expired history can be
reconciled without re-evaluating historical TTL, while a later `check()` still
denies authorization after expiry.

## Regression and validation results

All commands used `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` where
pytest was used.

- Start gate:
  `pwd && test "$(pwd)" = "/private/tmp/arnold-critique-recovery-ra-contain-20260802" && test "$(git rev-parse HEAD)" = "6ec8066041687fa45c3e2b71760ec7874f8d027a" && git status --porcelain=v1 --untracked-files=all`
  — exit 0; exact path, exact commit, and empty status.
- `pytest -q -p no:cacheprovider tests/arnold_pipelines/run_authority/test_containment.py`
  — exit 0; **68 passed**.
- `pytest -q -p no:cacheprovider tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py`
  — exit 0; **99 passed**.
- `pytest -q -p no:cacheprovider tests/arnold_pipelines/run_authority/test_containment.py -k 'final_cas or stalecas or rollback or wrong_target or state_specific or response_loss or external_anchor_uncertainty or expired_candidate or unknown or receipt or nonce or identity or restart'`
  — exit 0; **45 passed, 23 deselected**.
- `PYTHONDONTWRITEBYTECODE=1 python -c 'import ast, pathlib; [ast.parse(pathlib.Path(p).read_text()) for p in ("arnold_pipelines/run_authority/containment.py", "tests/arnold_pipelines/run_authority/test_containment.py")]'`
  — exit 0.
- `PYTHONDONTWRITEBYTECODE=1 python -m py_compile arnold_pipelines/run_authority/containment.py tests/arnold_pipelines/run_authority/test_containment.py`
  — exit 0; generated scoped bytecode was removed afterward.
- `git diff --check` and final `git diff HEAD^ HEAD --check`
  — exit 0; no whitespace errors.
- `ruff check arnold_pipelines/run_authority/containment.py tests/arnold_pipelines/run_authority/test_containment.py`
  — exit 1 with 67 findings, all from the repository's pre-existing compact-style/import baseline (including existing semicolon/E701/E702 findings and the existing unused test local); no new repair-specific blocking finding was introduced.
- `mypy arnold_pipelines/run_authority/containment.py`
  — exit 1 with 9 repository-baseline findings: 8 in unchanged `contracts.py` and the existing `argparse.ArgumentParser.error` override; the repair-specific temporary type error was removed.

The Pass-11 adversarial probes are encoded as independent regressions, including
`test_exact_authenticated_final_cas_noop_is_not_success`, true response-loss
recovery tests, concurrent-child and altered-head marker races, fake marker
acknowledgement, missing/wrong/duplicate nonce and identity provenance state,
receipt byte/self-key/equivalent-head substitutions, pinned restart identity,
and the existing malformed/fork/truncation/predecessor and issue/terminate/
reconcile/durable-reconcile/expired-history coverage.

## Trust model and explicit limitation

The local adapter's receipt authority is the generated Ed25519 key persisted in
`.test-key`, independently pinned in `.test-receipt-authority`, and cross-bound
to journal metadata. Restart restores and checks that identity; it never adopts a
replacement public key from a head receipt. The production contract requires the
same properties from GEN-DEPLOY's accepted Release Authority adapter, including
an atomic durable-proof operation. This checkout intentionally has no production
adapter, so production owner/install proof remains an explicit external
prerequisite.

## Final worktree

`git status --porcelain=v1 --untracked-files=all` is empty at final verification.
No remote, cloud, owner store, checklist, evidence manifest, unrelated worktree,
or external system was mutated.
