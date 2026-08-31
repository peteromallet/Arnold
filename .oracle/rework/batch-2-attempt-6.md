# Batch 2 attempt 6 — converged Luna rework

Verdict: **IMPLEMENTED**. This attempt is bound to
`.oracle/rework/batch-2-attempt-5.md` and its candidate diff; no additional Sol
oracle was commissioned under the review policy.

Binding digests: attempt-5 brief `50bc12e824643eb2eb8f1690a2b2ccc1a7dbd5c430482745df87a6ee6d319d32`; sealed candidate diff `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`.

- **A6-NATIVE** — authoritative production native proofs now require the
  recomputed family and exact selected-model membership in the backend-owned
  catalog. Production callers cannot replace the construction seam through
  `worker_options`; valid construction is admitted once before work.
- **A6-LIFE** — new controlled markers remain exactly
  `not_started -> entered -> accepted -> closed`; physical doors bind to the
  reservation. Legacy `ambiguous` records are projection-only reconciliation
  holds and never a fifth lifecycle state. Reopen uses the ordered terminal.
- **A6-TERM** — native tuple results, OMP results, and managed int-compatible
  results preserve typed terminal context and metadata; missing typed-exception
  identity and forged/conflicting context fail closed; append/link uncertainty
  remains unresolved.
- **A6-DOORTEST** — stale self-generated production proof coverage now asserts
  rejection; focused authority, lifecycle, reconciliation, dispatch, and
  transport suites pass without adding a second WBC authority.

Scope remains limited to these blockers. No frozen files, status, execution
log, index, commit, push, merge, deploy, or Batch-3 surfaces were changed.
