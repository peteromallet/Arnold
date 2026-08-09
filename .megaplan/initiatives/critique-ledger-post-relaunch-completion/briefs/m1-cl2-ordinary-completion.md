# F3 — Execute and publish real CL2 work through ordinary custody

## Outcome

Starting from the independently accepted T6.2 finalize-transition handoff and
the joined F1/F2 hardening manifests, consolidate any remaining ordinary
plan/critique/gate/finalize evidence, execute real CL2 feature work, and publish
it exactly once through WBC custody.

## Scope

Completes any residual T6.3 evidence and implements T6.4/T6.5. Preserve the
accepted v3 identity, owner revisions, fence/epoch, GLEKs, installed generation
and contract bundle; do not re-run the accepted finalize canary.

## Locked decisions

- Exact critique completeness is mandatory; failed/unknown attempts are not
  clean results.
- A graph rejection may receive at most one authority-accepted narrow repair for
  the same occurrence; no implementation dispatch occurs before admission.
- Publication intent is durable before push/PR. Provider ambiguity is
  `INDETERMINATE` and reconciled; never create a second PR.
- Authoritative chain cursor movement and feature commits, not logs or process
  liveness, prove progress.
- The first ordinary CL2 slice is a thin end-to-end proof through the canonical
  WBC + Run Authority + Custody owners; feature breadth cannot substitute for
  this architecture-fit proof.

## Bound inputs

The T6.2 handoff supplies the frozen CL2 brief hash, accepted cursor,
completed/unresolved task IDs, graph/contract hash and predecessor manifests.
F3 derives its exact residual slice mechanically from that manifest. Any narrow
graph repair must already be represented as a typed unresolved item; otherwise
it is out of scope and fails closed.

## Constraints

No raw chain start, retired cloud wrapper, tmux, marker edit, watchdog relaunch,
caller-minted authority, duplicate repair or duplicate publication.

## Done criteria

- Ordinary plan/critique/gate/finalize receipts are complete and exact-set.
- Accepted execute receipts bind real feature commits and current dependency
  closure.
- One authoritative CL2 completion manifest advances the chain cursor.
- Publication has one durable WBC intent and one reconciled provider outcome.
- Independent review finds no bypass, false success or duplicate effect.
- The architecture-fit receipt records the one owner/writer for each new
  mutation and any compatibility path retired or fenced during the slice.
- Executed task IDs and brief/graph hashes equal the frozen T6.2 residual-work
  manifest; no milestone planner choice or implicit scope expansion remains.

## Touchpoints

The v3 chain state, Critique Ledger implementation, owner stores, WBC records,
feature branch/PR and `evidence/critique-ledger-recovery/T6.3-T6.5/`.

## Anti-scope

Do not deploy the product, widen launch authority, rewrite v2, or close the
incident in this milestone.
