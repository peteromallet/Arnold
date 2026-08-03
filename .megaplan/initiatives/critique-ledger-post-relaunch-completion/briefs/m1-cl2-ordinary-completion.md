# F3 — Execute and publish real CL2 work through ordinary custody

## Outcome

Starting from the independently accepted terminal r5 CL2-CL5 chain handoff and
the joined F1/F2 hardening manifests, reconcile and consume any accepted r5 CL2
work before consolidating remaining ordinary evidence. Execute only work not
already accepted, and publish it exactly once through WBC custody.

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
- PR #325 and its r5 branches are predecessor custody. Reconcile exact heads,
  checks, completion records and provider outcomes before any new dispatch;
  duplicate implementation, branch, PR or publication is forbidden.

## Open questions

- Which exact CL2 feature slice remains after the accepted T6.2 transition?
- Does the accepted graph require the single permitted narrow repair?

## Constraints

No raw chain start, retired cloud wrapper, tmux, marker edit, watchdog relaunch,
caller-minted authority, duplicate repair or duplicate publication.

## Done criteria

- Ordinary plan/critique/gate/finalize receipts are complete and exact-set.
- Accepted execute receipts bind real feature commits and current dependency
  closure.
- One authoritative CL2 completion manifest advances the chain cursor.
- Publication has one durable WBC intent and one reconciled provider outcome.
- Accepted r5 work is consumed by content hash; rejected/incomplete work is
  explicitly classified, with zero duplicate dispatch or provider effect.
- Independent review finds no bypass, false success or duplicate effect.

## Touchpoints

The v3 chain state, Critique Ledger implementation, owner stores, WBC records,
feature branch/PR and `evidence/critique-ledger-recovery/T6.3-T6.5/`.

## Anti-scope

Do not deploy the product, widen launch authority, rewrite v2, or close the
incident in this milestone.
