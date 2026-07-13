# C4: Chain, PR, And Repair Boundaries

## Outcome

Authority-increasing chain, publication, repair, and auditor transitions have
declared boundary contracts whose receipts pin the exact accepted decisions and
coherent observations used.

The system detects stale or missing evidence without making WBC a chain driver,
GitHub provider, repair custodian, or transition writer.

## Entry Gate

C3 consumers agree on custody and semantic facts in shadow mode, and the Run
Authority chain/publication/recovery views plus Maintenance transition,
verification, and audit contracts are stable at pinned versions.

## Scope

IN:

- Record chain, publication, repair, independent-verification, escalation, and
  auditor work as ordered attempts, including failure/retry/suspend/resume/
  cancellation. Link their ledger identities to prerequisite authority and
  transition records without replacing either owner.
- Record durable pre-effect intents and idempotency/fencing keys for Git, GitHub,
  CI, deployment/relaunch, repair, and other external mutations, followed by
  complete/failed/unknown outcome refs. Unknown provider outcomes block false
  success and require read-only reconciliation before a safe retry.
- Declare contracts for chain milestone start/completion, child-to-parent
  aggregation, PR ready, PR merged, chain complete, repair dispatch, repair
  attempt handoff, independent verified closure/reopen, escalation/meta repair,
  and six-hour auditor completion.
- Pin plan/chain revision and view hash, base/head/expected-tip/merge SHA, PR and
  CI/check IDs, grant/attempt/decision/quarantine refs, observation-set digest,
  repair request/occurrence/blocker/attempt/verification refs, audit input hash,
  and current invocation/session identity where applicable.
- Express human approval, force-proceed, waiver, blocked/unblocked, resume, and
  manual merge as authority-bearing boundary evidence that adapts
  `HumanGateView` and `TransitionWriter` records.
- Verify PR merge containment of the expected accepted tip where policy
  requires it; a branch name or cached PR state is insufficient.
- Detect milestone/chain advancement without accepted authority, stale PR head,
  mismatched merge commit, stale repair data, orphan/conflicting repair
  decisions, missing independent verification, and audit completion over
  incomplete or mutable input evidence.
- Preserve compatibility reading for old chain/repair JSON as typed
  claim/projection inputs; require current decisions before authority advances.
- Add read-only checker diagnostics and scoped immediate verification at
  prerequisite-owned transition seams.

OUT:

- Replacing chain advancement, Git/GitHub/CI providers, repair custody,
  TransitionWriter, or the auditor reducer.
- Inferring authority from a clean worktree, branch label, process liveness,
  repair-agent completion, or report existence.
- Mutating old runtime JSON to make it conform.

## Locked Ownership

- Run Authority owns accepted decisions, publication/human-gate/recovery views,
  and quarantine.
- Maintenance `TransitionWriter` owns plan/chain mutation; Maintenance owns
  repair verification and audit-report truth semantics.
- WBC declares required evidence, emits receipts, and reports mismatches.
- External provider observations are evidence inputs, never WBC authority.

## Compatibility Fixtures

- current milestone completion with matching revision/view hash;
- child complete while parent aggregation is incomplete;
- cached PR merged but live head/merge ancestry is stale;
- merged PR missing the expected accepted tip;
- legacy chain state without current decision identity;
- repair record without verdict, independent verification, or matching blocker;
- stale repair-data shadowing a current occurrence;
- auditor report with reproducible hash and one with omitted required facts;
- human waiver with correct scope/expiry and stale/superseded waiver.

## Required Acceptance Evidence

1. Every authority-increasing boundary receipt references a current accepted
   decision and coherent observation digest; legacy labels alone fail closed.
2. Chain child aggregation and milestone completion tests prevent parent advance
   from child activity or terminal labels alone.
3. PR/CI fixtures prove exact expected-tip containment and reject stale cached
   publication evidence.
4. Repair closure requires independent verification of the original blocker;
   attempt completion or liveness is insufficient.
5. Auditor completion pins immutable inputs and reproduces the same content
   hash; omitted deterministic facts produce a finding.
6. Human decisions bind actor, role, scope, evidence/view hash, conditions,
   expiry/revocation, and stale-input rejection.
7. Existing chain, publication, repair, verification, and auditor regression
   suites pass without duplicated mutators.
8. Effect fault-injection tests cover crash before call, ambiguous timeout,
   provider success before outcome append, and retry; evidence proves at-most-
   once logical effect or explicit reconciled ambiguity with no false success.
9. Support-manifest evidence shows every C4-assigned step/attempt ledgered and
   every result/verdict/audit input retrievable under its retention policy.

## Automatic Failure Conditions

Fail validation and abort through `stop_chain` if any path needs direct chain/plan writes outside `TransitionWriter`, if a
boundary adapter can grant authority, if provider/cache disagreement is hidden,
if repair closure can be self-authored, or if legacy JSON is silently upgraded
into a current decision.

Real production approvals, waivers, force-proceed actions, and destructive
provider calls are fixture/fake/fenced conformance cases only; the milestone
never waits for such authority.

## Likely Touchpoints

- chain completion/advancement guards and receipts
- Run Authority publication/human-gate/recovery views and decision records
- Maintenance TransitionWriter, repair verification, and audit contracts
- Git/PR/CI observation adapters
- chain, publication, repair, and auditor compatibility tests
