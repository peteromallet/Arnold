# Critique Ledger Epic

## Status at a glance

The epic on Megaplan Cloud is **Critique Loop / Cumulative Finding Ledger** (`critique-ledger`).

The original run has been cancelled and retained as an inert audit/source
archive. It completed CL1 and accumulated partial uncommitted CL2 work, but that
CL2 plan predates the reconciliation-safety amendment and will not be resumed.

A replacement is staged, preflighted, and deliberately **not launched**:

- branch: `megaplan/critique-ledger-accountability-v2-20260728`
- workspace: `/workspace/critique-ledger-accountability-v2-20260728/Arnold`
- profile: `partnered-5-glm`
- completed prerequisite: the landed CL1 contract and M6 oracle
- remaining chain: four sprints, CL2–CL5

Nothing has been cut over to production yet. The existing critique system
remains authoritative.

## The idea in one sentence

Turn critique from a series of loosely related documents into a cumulative, durable record in which every critic attempt is preserved, semantically reconciled into logical findings, explicitly acted on or dispositioned, and carried forward into revision and gating.

## The evaluator and critic hierarchy

The intended model architecture is deliberately asymmetric:

- A **stronger, premium evaluator/director model** reads the plan, prior critique history, coverage, revisions, gate signals, and unresolved questions.
- That evaluator decides which critique domains or lenses need attention and constructs bounded briefings for them.
- It then dispatches **cheaper or more specialized critic models** to perform the parallel, detail-heavy critique work.
- The stronger evaluator reconciles their output: it decides whether an occurrence is a new finding, duplicate, refinement, regression, split, or reopened issue.
- The reviser must record an action or an explicit justified non-action for every relevant finding.
- The gate judges the cumulative state, rather than only the wording of the latest critique pass.

In the partnered configuration, this can mean a premium Claude/Codex-class evaluator directing cheaper DeepSeek/Kimi-style critics. The important property is not a particular vendor: it is that the model making the routing and reconciliation decisions is stronger than, or at least independently calibrated against, the models doing most of the parallel search.

```text
Plan + prior ledger + revision and gate evidence
                       |
             Strong evaluator/director
             selects lenses and briefings
                       |
          +------------+------------+
          |            |            |
       critic A     critic B     critic C
       cheaper / specialized parallel passes
          |            |            |
          +------------+------------+
                       |
              Immutable occurrences
                       |
             Evaluator reconciliation
       logical findings, dispositions, reopen rules
                       |
              Reviser action coverage
                       |
          Cumulative, evidence-aware gate
```

The evaluator is a **semantic authority**, not a workflow authority. It may judge equivalence, novelty, severity, refinement, or reopening. Deterministic code still owns identity, hashes, completeness, freshness, idempotency, persistence, and phase transitions.

## The five machine-defined milestones

### CL1 — Contract and oracle freeze — complete

Defines the authority boundaries and freezes the M6 content-addressed oracle. This establishes what the ledger owns and, just as importantly, what it does not own.

### CL2 — Durable append-only ledger — current, paused

Builds the WBC-backed append-only occurrence ledger, replay, rebuildable projections, compatibility boundaries, and legacy import.

Raw critic occurrences are immutable. Views and projections can be rebuilt. Accepted events are idempotent, so replaying the same accepted event cannot silently append it twice.

### CL3 — Evaluator routing and bounded briefings

Connects adaptive critique routing to the cumulative ledger. Each selected critic receives enough relevant history to understand prior findings, dispositions, revisions, evidence, unanswered questions, and reopen conditions.

An optional blind pass preserves the chance of discovering genuinely new families of problems, but reconciliation against history is mandatory before revision or gating.

### CL4 — Reconciliation, revision, and gate truth

Introduces durable logical findings and explicit dispositions such as:

- open
- resolved
- rejected
- deferred
- duplicate
- accepted risk
- unknown

It also defines when a finding should reopen and requires the reviser and gate to account for the cumulative finding set. This prevents wording changes or omission from masquerading as convergence.

### CL5 — Atomic cutover and legacy retirement

Backs up the old state, cuts authority over to the ledger-backed path, proves restore behavior, and retires the legacy path.

This is why the epic can sensibly be discussed as **four build sprints plus one release/cutover sprint**.

## Would this have solved the recent repeated-critique problem?

It would have **materially ameliorated it, but not completely prevented its root cause**.

The recent M11 failure involved an orchestration cursor/recovery bug that caused critique to be repeated against an unchanged plan version. The ledger design would have made that repetition immediately visible and much less harmful:

- exact input hashes would show that the target plan had not changed;
- every repeated attempt would remain visible instead of overwriting history;
- the evaluator could mark repeated content as duplicate, refinement, or regression;
- the reviser could not repeatedly “fix” the same logical finding without recording why;
- the gate would see cumulative truth rather than treating each critique document as a fresh universe;
- replay of the same accepted event would be idempotent.

But the ledger explicitly does **not** own the workflow cursor or decide whether another critique attempt may be dispatched. A new attempt against an unchanged plan could still be launched and then correctly recorded.

Preventing that specific failure also requires a small orchestration guard outside the epic:

1. Refuse a normal critique dispatch unless the plan content hash/version differs from the last critiqued target.
2. Permit unchanged input only when the operation is explicitly identified as a retry.
3. Give the attempt a stable idempotency key.
4. Advance the phase/cursor with compare-and-swap semantics.

The exact cursor recovery bug has already been repaired in the current fixer runtime. The ledger epic addresses the broader semantic-custody problem: it makes duplicate execution diagnosable and prevents it from becoming duplicate reasoning or duplicate revision.

## Does the design make sense?

Yes. Its central design is sound:

- **Immutable evidence, rebuildable views** is the right persistence model.
- **Semantic judgment in models, custody invariants in deterministic code** is a clean boundary.
- It distinguishes “no new findings,” “no open blockers,” “no known findings,” and “no matching text.” Those are not the same claim.
- Exact hashes and fail-closed handoffs make stale or incomplete context visible.
- A stronger evaluator directing cheaper parallel critics is a sensible quality/cost tradeoff.
- Explicit dispositions and reopen conditions prevent unresolved issues from disappearing through paraphrase.

The main concern is scope. The current five-stage design is large, and its atomic big-bang cutover is operationally riskier than the core idea needs to be.

## Recommended simpler shape

Preserve the architecture, but prove it first as a narrow vertical slice:

1. Add the exact-plan-hash dispatch guard.
2. Record immutable critique occurrences.
3. Reconcile them into logical findings with dispositions and reopen rules.
4. Require revision and gating to cover every relevant logical finding.

Measure whether this reduces duplicate actions, lost findings, and false convergence. Only then complete broad legacy import and irreversible legacy retirement.

This also gives the project a clearer four-sprint story: the first four milestones deliver the working critique-ledger system; the fifth is a separately governed production migration.

## Reconciliation-safety amendment

The plan has now been amended around a simpler rule:

> Preserve observations; let models propose meaning; let deterministic hashes decide freshness and audit selection; let the gate trust only current, independently reviewable decisions.

The amended design adds:

- a mandatory blind discovery lane in every critique round;
- raw occurrences that contain no evaluator-assigned semantic identity;
- append-only reconciliation decisions that can be audited, disputed, and superseded;
- deterministic region-hash, evidence-change, near-match, and audit-disagreement tripwires;
- three bounded work projections: `must_act`, `must_revalidate`, and `context_only`;
- structured non-action with evidence and reopen conditions;
- one finding history linking critique, response, independent outcome verification, and later staleness;
- a per-round accountability receipt showing what was found, what happened because of it, whether it was dealt with, and why anything remains unresolved.

The lifecycle is deliberately small:

```text
occurrence
  -> reconciliation decision
  -> response or structured non-action
  -> independent outcome: dealt with / partial / not dealt with / unknown
  -> later input change may mark that outcome stale
```

The round receipt is rebuilt from these events. It is not another ledger or authority.

## Bottom line

The epic is not merely “run more critiques.” It creates memory and accountability across critique rounds.

Its most valuable pattern is:

> A strong evaluator decides where weaker or cheaper critics should search, then reconciles their work into a durable cumulative truth that revision and gating cannot silently ignore.

That would have made the recent failure easier to detect, safer to recover from, and far less likely to generate repeated semantic work. The separate unchanged-input cursor guard is what prevents the same orchestration failure from being dispatched in the first place.
