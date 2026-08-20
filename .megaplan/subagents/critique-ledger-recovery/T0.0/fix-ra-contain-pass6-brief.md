# RA-CONTAIN repair pass 7 (after adversarial review pass 6)

Use GPT-5.6 Luna high reasoning. Work only in:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

Start from commit `611321c79c70d3ec75cf6f7be6ba3df275eb5e81` plus the
currently generated `uv.lock` dependency update. Do not touch the user's main checkout,
cloud, external services, or other worktrees. Do not push/deploy. Read the full review:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-final-review-pass6-result.md`

Repair every confirmed defect at root. Do not delete or weaken tests to get green.

## Binding fixes

1. Remove the self-authorizing production path. A caller-created object with
   `production_capable=True`, caller-supplied trust bundle/key/domain, or self-signed
   backend receipt must never become production authority. If the accepted/pinned
   Release Authority backend is not yet available in this branch, production
   construction/provisioning must explicitly fail closed with a typed reason. Do not
   claim formal T0.0 complete. Design the exact narrow integration interface needed by
   GEN-DEPLOY, but do not replace missing authority with duck typing.
2. Fix both reconciliation uncertainty paths. Any successful reconcile must commit an
   internally consistent `operation="reconcile"` head/record/request digest and then
   reread/authenticate `status()` and `check()` before returning. Pending-CAS and
   final-CAS ambiguity must both become recoverable only through an exact signed owner
   reconciliation; no invalid genesis/non-genesis combination.
3. Globally conflict-fence `decision_id`, `idempotency_key`, nonce, and operation identity
   to canonical request digest/result across termination and restart. Exact replay has a
   deterministic typed result; same identity/different content is `DuplicateConflict`.
4. Add required CLI `check --effect` and pass it through. Prove observe plus all six
   denied effects; no hard-coded observe fallback.
5. Strictly validate the exact backend descriptor shape before lookup. Every expected
   CLI/schema/path error must be traceback-free machine JSON with a stable typed code.
6. Restore the persistence-neutral contract dependency boundary. Scope independence
   checks to the generic contract/reducer modules and keep `pathlib`/`sqlite` forbidden
   there; separately test persistence adapters.
7. Address paired local rollback honestly. An adjacent local test file cannot prove
   rollback resistance. It must be impossible to mistake/use the local adapter as an
   accepted production/security authority. Either remove it from the installed CLI
   authority path or make all outputs conspicuously non-authoritative and keep production
   fail-closed. Add a paired-rollback negative test for the accepted authority path; do
   not assert that restoring both local files is secure.
8. Include `uv.lock` consistently with the `cryptography` dependency if still needed.

## Restore the missing proof surface

The previous rewrite reduced containment coverage drastically. Add adversarial tests for:

- malformed/unknown fields; bool/int confusions; NaN/Infinity; semantic head/receipt
  relationships;
- exact vs divergent replay after active, terminate, restart, and reconcile;
- issue/terminate/reconcile crash boundaries before/after every durable journal/anchor
  transition;
- successful reconcile followed by `status()` and every `check()` effect;
- thread and separate-process races yielding one valid history;
- TTL/revoke semantics across restart and injected wall-clock boundaries;
- journal-only rollback/truncation/replacement and accepted external-anchor rollback/fork
  detection;
- caller-chosen fake production backend refusal;
- installed CLI help/JSON failure behavior and effect queries.

Run targeted tests, dependency-closure tests, installed-wheel tests where applicable, and
`git diff --check`. Inspect your own diff adversarially. Commit only a clean, tested repair
with an intentional message. In the final response, state exact test commands/counts,
commit hash, and what remains formally blocked on the external GEN-DEPLOY/Release Authority
backend. Do not call the task complete merely because test mode works.
