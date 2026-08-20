# T2.3 isolated deployed-canary implementation — Luna preparation

Date: 2026-08-02  
Ticket: `01KYVJ7A47TMH4BRGEV9JFTK10`  
Base: `6787d6363e8fc0603092913ae877db14f3b9fff8`  
Verdict: **NOT COMPLETE; preparation only**

## Canonical contract

The exact ticket is `.megaplan/tickets/01KYVJ7A47TMH4BRGEV9JFTK10-implement-an-honest-backend-neutral-deployed-workflow-canary-runner.md` at `6787...`. It is `status: open` (lines 2–4). Lines 17–30 require: no caller-authored proof; pre-launch target/deployment/source/runtime/evidence-root binding; read-only deployed WBC access; one non-stitchable manifest/journal/window/WBC/acceptance/snapshot/plan/source/runtime join; fresh completion; suspension/resume with distinct reentry; three real gate iterations; all four tiebreaker phases and ordered decision; frozen stores plus independent re-derivation; bounded timestamps/unique roots/accepted transaction checks; adversarial forgery tests; and exact commands, fixture, rollback and runbook integration.

Acceptance is explicitly production-only: four independently re-derived deployed proofs (line 32). The narrowed current-backend scope is lines 43–62. Existing implementation claims are lines 64–82, but lines 84–87 keep the ticket open until the exact deployed runtime performs `admit`, `run`, and `verify`.

## Evidence ledger

Current reusable code/tests at `6787...`:

```text
arnold_pipelines/megaplan/cloud/m11_workflow_canary.py
arnold_pipelines/megaplan/cloud/m11_workflow_canary_runner.py
arnold_pipelines/megaplan/cloud/m11_workflow_canary_verifier.py
arnold_pipelines/megaplan/cloud/m11_canary_cohort.py
arnold_pipelines/megaplan/cloud/m11_live_canary.py
tests/cloud/test_m11_workflow_canary.py
tests/cloud/test_m11_canary_cohort.py
tests/cloud/test_m11_live_canary.py
```

Classification:

- **Current implementation baseline:** `admit/run/verify` code and local fixtures above; code existence is not acceptance.
- **Honest pending evidence:** `5f30fb0c0f...` removes fake placeholders and cannot emit verified; accepted only as a pending obligation.
- **Rejected:** `c88ebe00ac...` trusts producer-authored booleans/labels; `667b76115f...` permits event cross-stitching, caller-selected identity/timestamps and forged verdict. Neither may enter a proof map.
- **Stale:** all July-31 local/worktree receipts and canary branches are revision/runtime-specific and predate the integrated recovery candidate.
- **Missing:** one accepted T1 portfolio, T2.2 exact offline candidate, isolated exact-generation receipt, independent hostile verification receipt, and later exact installed T3 run.

## Authority and dependencies

T2.3 depends directly on accepted T2.2. T2.2 depends on accepted T1.1–T1.10. RA/Custody/WBC contracts must be the accepted platform-wide interfaces; the canary may not mint grants, leases, epochs, GLEKs or success. Release Authority selects the tested generation but T2.3 grants no deployment. T3 supplies separate mutation authority and T3.6 alone may accept the installed result and close tickets.

The isolated run must use a disposable SQLite backend and disabled production adapters. It binds candidate commit/tree, package/runtime digest, manifest ID/hash, unique scenario/run/attempt IDs, evidence window and rollback snapshot before execution. No Discord, webhook, Git, model provider, SSH, deployment, selector, marker or production-store effect is permitted.

Provider acceptance with lost response is WBC `UNKNOWN`/`INDETERMINATE`: freeze evidence, prohibit redispatch, and require owner reconciliation. It is never ordinary failure, fallback success or a new attempt under the same GLEK.

## Finite acceptance matrix

| Gate | Required isolated result |
|---|---|
| I1 identity | Exact clean integrated commit/tree, installed package/runtime and immutable evidence root |
| I2 admit | Signed owner inputs checked; wrong target/runtime/schema/window rejected before effects |
| I3 fresh | Canonical admission through atomic accepted terminal, one non-stitchable identity root |
| I4 gate | Two ITERATE decisions then third real authored gate; no route-event proxy |
| I5 resume | Durable checkpoint/cursor, SUSPENDED→RESUMED, distinct reentry/backend invocation, terminal |
| I6 tiebreaker | All four authored phases plus projected decision ordered before terminal |
| I7 WBC | Exact lifecycle/GLEKs; no duplicate; lost acknowledgement remains UNKNOWN/no redispatch |
| I8 freeze | Producer freezes SQLite/snapshot/verdict inputs and cannot write verified verdict |
| I9 verify | Separate process opens stores read-only, re-derives all four proofs, alone writes immutable verdict |
| I10 hostile | Reject cross-stitch, reused IDs, wrong window/runtime/source, future time, missing row, forged self-hash/pass boolean and mutable store |
| I11 isolation | Runtime spies prove zero production/provider calls and unchanged repo/owner state |
| I12 rollback | Disposable generation/store rollback restores exact snapshot; rollback receipt is not production proof |
| I13 parity | Source/wheel/installed isolated CLI schemas/help/results match exact candidate |
| I14 authority | Receipt says `deployment_authorized=false`, `production_identity_satisfied=false`, ticket remains open |

Any missing/unknown/unbound item is FAIL. `UNKNOWN` effect outcome is preserved and makes scenario verification pending, never retried into PASS.

## Launch-ready implementation brief

1. Wait for accepted T1 portfolio and T2.2 manifest; create one clean descendant of `6787...`.
2. Audit existing canary code against I1–I14; remove every caller-authored verdict path and bind the accepted RA/Custody/WBC interfaces.
3. Materialize four deterministic scenarios in a disposable installed environment with production adapters structurally unavailable.
4. Implement `admit` as the sole pre-execution binder; `run` may emit/freeze raw evidence but never verdict; `verify` is a fresh read-only process and sole verdict writer.
5. Inject crashes and lost responses at every WBC/acceptance boundary; preserve UNKNOWN and prove no redispatch.
6. Run source, wheel and installed suites, hostile substitutions, two-process uniqueness, frozen-store mutation, rollback and zero-effect spies.
7. Emit `evidence/critique-ledger-recovery/T2.3/{manifest,admit,run,freeze,verify,hostile,rollback,isolation,applicability}.json`, all bound by digest to one candidate.
8. Independent verifier rehashes and reruns from Git archive. A local PASS only makes implementation eligible for T2.6/T3; leave `deployed_proof_status=pending` and the ticket open.
9. T3 later repeats exact `admit/run/verify` on the Release-Authority-selected installed generation under a separate scoped grant, with production rollback and independent receipt. No local artifact substitutes for it.

## Custody statement

Read-only Git/filesystem inspection only. No tests, code, Git, cloud, provider, process, owner, ticket or checklist state was mutated. This report is the sole write. T2.3 is not complete.

The report SHA-256 is recorded externally after finalization.
