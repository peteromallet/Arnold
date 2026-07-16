---
type: brief
slug: domain-specific-critique-finding-ledger
title: Cumulative Domain-Specific Critique Finding Ledger
epic: session-knowledge-compiler
created_at: '2026-07-16T20:37:02Z'
updated_at: '2026-07-16T21:35:06Z'
status: canonical-planning-source
---

# Cumulative Domain-Specific Critique Finding Ledger

## Outcome

Give every Megaplan critique/revise/gate loop a cumulative, evidence-linked
memory of what its critics have found and what happened to each finding. The
critique evaluator remains responsible for deciding which domain critics to
run. Every selected domain's context-aware pass automatically receives its
applicable prior domain instructions, all relevant findings and occurrences,
explicit evaluator dispositions, revision actions, evidence, remaining
questions, and reopen conditions. A critic may validly conclude that it found
nothing additional.

The first implementation should treat this primarily as a context and custody
problem. Preserve independent discovery where it is useful, then reconcile it
against the cumulative record. Do not begin with a semantic database, embedding
index, hard-coded similarity threshold, or elaborate lineage graph.

This is the canonical source brief for the critique-ledger epic within the
Durable Session Knowledge Compiler initiative. The executable implementation
plan lives under `../../critique-ledger/`; this brief does not itself perform a
cutover, deploy, restart, or mutate an in-flight plan.

## Why this initiative is the canonical home

The supported initiative search identifies `session-knowledge-compiler` as the
closest canonical initiative for durable, evidence-linked, append-only,
correctable knowledge. The initiative already requires primary evidence to
survive synthesis, derived records to remain distinguishable from facts, and
source observations to survive consolidation. A critique finding ledger is a
specialized application of those invariants.

Workflow Boundary Contracts is the integration substrate: it owns durable
attempt/effect evidence, payload references, receipts, persistence, and
compatibility boundaries. The critique ledger owns immutable critic occurrences,
semantic finding identities, disposition/reopen events, bounded history
briefings, and derived projections. Existing Megaplan components retain critic
selection, revision, gate, and lifecycle authority.

## Decision posture

### Settled conclusions from the conversation and M6 evidence

1. **Use a cumulative domain-specific finding ledger.** Every critique round
   contributes to one cumulative record. Domain briefings are bounded views of
   that record, not independent memories that can disagree silently.
2. **The critique evaluator chooses the critics.** A permanent always-on critic
   roster is not the chosen design. The evaluator selects relevant domains and
   supplies purpose-built instructions for the current plan revision.
3. **Selected context-aware critics receive the complete applicable history.**
   That includes prior domain instructions; every relevant finding, including
   ignored, deferred, rejected, accepted, minor, and cross-domain findings;
   evaluator conclusions and rationale; revision actions; evidence; unanswered
   questions; and conditions under which a prior conclusion may be reopened.
4. **No finding may disappear by omission.** “Ignored” is not a stored terminal
   meaning. It must become an explicit disposition with rationale, evidence or
   acknowledged evidence limits, and reopen conditions.
5. **“No additional findings” is valid.** Critics are not rewarded for
   manufacturing novelty. A clean result records the domain and evidence scope
   examined and may affirm or challenge prior dispositions without inventing a
   new finding.
6. **Preserve blind discovery where it is useful.** History can anchor a critic
   or prematurely close a question. An independent pass may therefore run
   without finding history before a context-aware reconciliation pass. No blind
   output is allowed to bypass reconciliation and become the gate's whole view.
7. **Semantic recurrence is model judgment; custody is deterministic.** The
   harness must prove which occurrence was produced, retained, reconciled, and
   briefed. The evaluator/curator judges whether occurrences are the same
   concern, a refinement, a regression, or unrelated.
8. **Context loss is proven in the preserved M6 case.** One round-4 minor
   prerequisite-ordering concern was not carried into revision/gate context.
   Four round-5 lenses then raised the same semantic conflict, while the gate's
   exact-text metric reported zero recurrence.

### Locked architecture for the coordinated migration

- Use a two-stage domain task by default: optional blind discovery followed by
  mandatory context-aware reconciliation. The evaluator may omit the blind pass
  when the task is purely verification or the novelty budget is low.
- Maintain one logical cumulative finding set with domain-specific projections,
  rather than one isolated physical ledger per domain.
- Let an evaluator or a dedicated curator produce a bounded natural-language
  briefing, initially targeting roughly 2,000–4,000 tokens per selected domain.
- Keep deterministic infrastructure minimal: immutable occurrence addresses,
  input hashes, completeness/freshness checks, and evidence references.
- Start with a small disposition vocabulary described below, but keep the exact
  serialized enum/version open until existing flag, gate, WBC, and knowledge
  contracts are reconciled.

### Rejected or premature complexity

- A semantic lineage database or graph as the first intervention.
- Embedding similarity, Jaccard thresholds, or exact-text matching as semantic
  authority.
- A large ontology that attempts to encode every possible critique relation
  before the M6 implementation gate passes.
- Preloading full history into every initial critic pass.
- Dropping minor, rejected, deferred, failed-producer, or accepted-tradeoff
  findings from reviser/gate context merely because they are non-blocking.
- Calling the current adjacent exact-text intersection “semantic recurrence.”
- Treating all repetition as failure: some later findings are legitimate
  refinements or regressions caused by a changed plan.

## Goals

- Stop findings from being silently lost between critic, evaluator, reviser,
  gate, and later iterations.
- Reduce redundant rediscovery and duplicate revision work without suppressing
  genuinely new findings.
- Give each domain critic focused, evidence-grounded memory instead of an
  unbounded transcript dump.
- Make every non-action and closure auditable and safely reopenable.
- Let evaluator routing use prior learning across both the same domain and
  overlapping domains.
- Make the gate's claims about recurrence, resolution, and accepted risk honest.
- Preserve complete evidence and provenance while allowing bounded synthesized
  briefings to evolve.
- Validate reconstruction and the semantic loop early, then complete one
  coordinated cutover and retire the replaced path.

## Non-goals

- Replacing raw critique outputs, plan versions, evaluator verdicts, revision
  metadata, gate artifacts, or repository evidence with summaries.
- Making ledger state an execution-authority, plan-state, or mutation grant.
- Requiring every critic to run in every round.
- Automatically closing a finding because wording is similar or a reviser says
  it was addressed.
- Preventing rediscovery when a new revision contradicts closure evidence.
- Solving general project memory, general RAG, or all session-knowledge storage
  in this slice.
- Changing severity policy or forcing every minor finding to block the gate.
- Inventing semantic relationships while importing historical plans.

## Conceptual record and briefing shape

The terms below describe product semantics, not a frozen implementation schema.
The implementation planner must first reconcile them with existing flag,
critique-custody, gate, WBC finding, and session-knowledge contracts.

### Immutable occurrence receipt

Every producer output that asserts or discusses a finding gets an immutable
occurrence address. At minimum it records:

- plan/run identity, plan content hash, brief hash, repository/runtime revision,
  iteration, phase, and producer artifact reference;
- critic domain/lens, exact instructions, model/profile, prompt generation, and
  evidence/search scope;
- the raw concern, severity suggestion, evidence references, remaining
  questions, and the producer's `no_additional_findings` result when applicable;
- input ledger revision and briefing hash, or an explicit marker that the pass
  was blind;
- generation time and custody receipt.

Occurrence receipts are never merged away. If four critics repeat one concern,
four occurrences remain auditable even when the evaluator associates them with
one cumulative finding.

### Cumulative finding entry

A finding entry is the evaluator-maintained semantic record. A useful initial
shape is:

```yaml
finding_id: stable evaluator-assigned identity
summary: concise semantic concern
domains: [primary-domain, overlapping-domain]
occurrences: [immutable occurrence references]
first_seen: {iteration: 4, plan_hash: "..."}
last_evaluated: {iteration: 5, plan_hash: "..."}
relationship_of_latest: duplicate | refinement | regression | reopened | new
current_disposition: open
evaluator_conclusion: what is believed and why
revision_actions:
  - revision: plan_v5
    action: what changed, or explicit no-action
    evidence: [artifact references]
closure_or_non_action_evidence: [artifact references]
remaining_questions: [questions]
reopen_conditions: [testable conditions]
cross_domain_links: [finding references]
freshness: {input_set_hash: "...", briefing_revision: "..."}
```

The evaluator may associate, split, or relink semantic findings in a later
append-only reconciliation event. It must never rewrite the underlying
occurrences to pretend an earlier semantic judgment was always known.

### Minimum disposition semantics

The exact enum is an implementation choice, but the following meanings must be
representable from the first accepted target schema:

- `open`: actionable concern remains.
- `addressed_pending_verification`: a revision action claims to respond, but the
  response has not been independently verified.
- `resolved_verified`: evidence supports closure for the pinned plan revision.
- `accepted_tradeoff`: the concern is real and intentionally accepted, with
  rationale, accountable scope, and reopen conditions.
- `deferred`: action is postponed to a named boundary/owner/condition; it is not
  forgotten or treated as fixed.
- `rejected_invalid`: the evaluator concludes the concern is factually or
  logically wrong and cites contradiction evidence.
- `rejected_out_of_scope`: the concern is valid elsewhere but outside this
  plan's authorized outcome; record the owning boundary or unknown owner.
- `wont_fix`: a deliberate non-action distinct from invalidity or deferral,
  with rationale and reopen conditions.
- `uncertain`: evidence is inadequate or contradictory; remaining questions
  are explicit.

The UI or migration layer may accept the word `ignored`, but canonicalization
must require one of the explicit meanings above. Severity and disposition are
orthogonal: a minor finding can remain open, and a significant finding can be
an accepted tradeoff only under the gate's existing authority/policy.

### Domain briefing

The context-aware briefing for each selected domain contains:

1. Current plan/brief/repository identity and freshness markers.
2. The evaluator's current domain instructions and the applicable prior domain
   instructions that explain continuity or changed emphasis.
3. All relevant cumulative findings, not only open significant ones.
4. For each finding: occurrences, current disposition and evaluator rationale,
   revision actions, evidence, remaining questions, and reopen conditions.
5. Cross-domain findings whose causes, changes, or evidence overlap this domain.
6. Areas already examined, evidence limitations, exhausted searches, accepted
   constraints/tradeoffs, and promising directions.
7. The precise requested outcome, including permission to return
   `no_additional_findings`.

Resolved findings may be compressed more aggressively than open findings, but
their disposition, evidence, and reopen predicate must remain available. If the
brief exceeds its budget, the system must use evidence-linked hierarchical
summaries or split the domain task; it must not silently omit findings.

## Lifecycle and state semantics

1. **Capture.** Preserve each critic output as an immutable occurrence receipt,
   including valid no-additional-findings results and failed/dropped producer
   attempts that emitted parseable findings.
2. **Reconcile.** After the selected blind and/or context-aware passes finish,
   the evaluator/curator accounts for every occurrence. It associates it with a
   cumulative finding or creates a new one, records semantic relationship, and
   explains ambiguous merges/splits.
3. **Disposit.** The evaluator records the current conclusion. A disposition is
   incomplete without rationale, applicable evidence/evidence limits,
   remaining questions where relevant, and reopen conditions for any closure or
   non-action.
4. **Revise.** The reviser receives every actionable finding plus the relevant
   disposed history. It records one revision action or explicit non-action per
   finding it was asked to handle. A plan diff alone is not a disposition.
5. **Verify.** A later evaluator/critic compares the claimed revision action to
   the actual plan diff and repository evidence. Only independent verification
   moves an addressed finding to resolved for that revision.
6. **Gate.** The gate receives the current cumulative view, complete occurrence
   accounting, revision actions, verification results, accepted tradeoffs, and
   unresolved questions. It may proceed with explicit non-blocking open or
   disposed findings according to policy, but cannot make a false claim that
   they do not exist.
7. **Carry.** The next evaluator starts from the new plan revision, prior ledger
   revision, prior gate conclusion, and changed evidence. It selects domains
   and constructs fresh briefings.
8. **Reopen.** A resolved/non-action finding reopens only when its recorded
   predicate is met, closure evidence becomes stale/contradicted, the plan
   changes the relevant surface, or a critic cites new evidence. Reopening is an
   append-only event, not deletion of the prior conclusion.

## Evaluator, critic, reviser, and gate flow

### 1. Evaluator selection and task construction

The evaluator reads the current plan, brief, repository/revision evidence,
latest plan diff, prior gate rationale, and cumulative ledger. It selects the
domain critics to run and records:

- why each domain is relevant now;
- which findings and changed surfaces triggered selection;
- which domains are skipped and why;
- whether the domain gets a blind discovery pass, a context-aware verification
  pass, or both;
- the domain-specific questions, evidence targets, and output budget.

Selection is a semantic model decision. Deterministic policy may enforce
mandatory safety/correctness floors or budget ceilings, but must not use a
similarity score as the final routing authority.

### 2. Optional blind discovery

When useful, the domain critic first receives the current plan, brief,
repository, lens, and evidence scope without finding history. This protects
novel discovery and provides a measurable new-family recall baseline. The
occurrence explicitly records `context_mode: blind`.

Blind discovery is optional, not a loophole around the chosen design. Its output
always enters the same reconciliation step, and the domain's context-aware pass
or evaluator sees the full applicable ledger before any revise/gate decision.

### 3. Context-aware domain pass

The selected critic receives the fresh domain briefing automatically. It is
asked to:

- verify whether open/uncertain findings remain true;
- test claimed resolutions and accepted tradeoffs against their evidence;
- identify fulfilled reopen conditions or regressions;
- distinguish duplicate wording from refinement or new evidence;
- report new findings when present; and
- explicitly return `no_additional_findings` when nothing new or reopened is
  supported.

### 4. Evaluator reconciliation

The evaluator/curator compares all selected outputs with the prior cumulative
record. It must produce a completeness map from every occurrence to a finding
and disposition action. Any missing mapping fails reconciliation and prevents a
truthful gate prompt. Semantic uncertainty stays explicit rather than being
forced into a false merge.

### 5. Revision

The reviser receives:

- the complete open/actionable set regardless of severity;
- relevant rejected/deferred/wont-fix/accepted history so it does not reverse or
  repeat a decision accidentally;
- exact evaluator conclusions, requested revision actions, evidence, remaining
  questions, and reopen conditions; and
- the prior and current plan identity.

The reviser returns structured per-finding action notes alongside the revised
plan. An untouched finding remains visible and retains its prior disposition;
it never disappears because it was omitted from the revision prompt.

### 6. Gate

The gate sees the same cumulative truth, optimized for decision-making rather
than discovery. It receives full details for blocking/actionable findings and
bounded summaries plus drill-down references for all other applicable findings.
It records explicit verification, dispute, tradeoff, deferral, rejection, or
continued-open conclusions and updates reopen predicates where needed.

The gate must distinguish:

- no new findings in this pass;
- no open blocking findings;
- no known findings at all; and
- zero adjacent exact-text matches.

Those are different claims and must never be collapsed into “zero recurrence.”

## Domain and cross-domain routing

- Keep the existing critic lens/domain catalog as the starting vocabulary; do
  not freeze it as the only possible taxonomy.
- A finding may belong to multiple domains. One primary domain owns the focused
  briefing, while overlapping domains receive it when the evaluator judges it
  material to their current task.
- Route cross-domain findings when a plan change, dependency, shared evidence,
  or reopen condition crosses the domain boundary. In M6, the blocked-handoff
  conflict belongs to prerequisite ordering but is also relevant to correctness,
  verification, criteria quality, and completeness.
- Include findings from other domains when they constrain the selected critic's
  conclusion, even if that critic did not originally discover them.
- Record why a cross-domain finding was included or excluded. This makes routing
  reviewable without pretending the routing rule itself is deterministic truth.
- Reserve some blind capacity for unexplored surfaces so domain history does not
  become a self-reinforcing map of only previously known concerns.

## Custody, completeness, and freshness requirements

The minimum deterministic machinery is load-bearing:

1. Preserve every producer artifact and occurrence with stable address, hashes,
   domain, iteration, model/profile, instructions, and evidence scope.
2. Bind each ledger revision and domain briefing to exact plan, brief,
   repository/runtime, prior-ledger, evaluator-verdict, and input-set hashes.
3. Reject or rebuild a stale briefing before critic dispatch. Never silently use
   a prior plan's closure evidence after the relevant surface changed.
4. Require a reconciliation row for every occurrence, including non-blocking,
   rejected, deferred, malformed-but-recoverable, and failed-attempt findings.
5. Require evidence and a reopen condition for resolved, accepted-tradeoff,
   deferred, rejected, and wont-fix dispositions. `uncertain` requires explicit
   missing/contradictory evidence.
6. Preserve evaluator, reviser, and gate conclusions as append-only events; do
   not mutate history when a finding is reopened or reclassified.
7. Keep summaries derived and rebuildable from retained findings, occurrences,
   and evidence. Hashes prove identity/integrity, not preservation by
   themselves.
8. Surface incomplete custody, stale context, unmapped occurrences, evidence
   loss, and context-budget truncation as blocking context-health findings.
9. Reuse the supported runtime/WBC attempt and evidence contracts where they
   are authoritative. Do not let this logical finding ledger become a second
   execution ledger, transition writer, repair queue, or authority source.

## M6 worked example and acceptance fixture

The preserved plan
`m6-exact-contract-and-20260716-1303` is the first required migration fixture.

Direct artifact evidence:

- `critique_v4.json` records `CF-CD1C58FBC288E3BBA77C`, a minor
  `prerequisite_ordering` concern: the blocked-prerequisite path skips generated
  artifacts while the drift checker fails on missing artifacts.
- `plan_v5.meta.json` lists four addressed significant findings, but not that
  minor finding.
- `critique_v5.json` contains four semantically equivalent occurrences from
  correctness, verification, criteria quality, and prerequisite ordering. The
  occurrences use distinct current IDs while pointing back to the same prior
  producer/finding identity.
- `gate_signals_v5.json` reports `recurring_critiques: []` and “Recurring
  critiques: 0,” because the runtime compares only normalized concern strings
  in adjacent critique artifacts.
- The pinned runtime builds a revision context at
  `orchestration/critique_runtime.py:782`, but the live parallel path invokes
  `run_parallel_critique` without it. `parallel_critique.py:460-567` builds each
  critic prompt from only the single check. `prompts/gate.py:118-135` injects
  only per-lens flagged counts, while `gate_signals.py:74-85` computes adjacent
  exact-text intersection.

Expected behavior under this plan:

- The round-4 occurrence is retained in the prerequisite-ordering ledger.
- The round-5 evaluator selects the relevant domains and generates a briefing
  that includes the round-4 finding, its still-open evaluator conclusion, what
  plan_v5 changed, what it did not change, and the precise reopen/verification
  question.
- Blind round-5 critics may independently rediscover the concern; reconciliation
  maps all four occurrences to the cumulative finding and records whether each
  adds evidence or only repeats it.
- The context-aware domain pass asks for the exact drift-checker exception or
  cites its continued absence; it is allowed to report no additional finding
  beyond the still-open cumulative one.
- The reviser receives one semantic action request rather than four duplicate
  rewrite requests.
- The gate reports one open cumulative finding with five occurrences, not zero
  recurrence, and then applies ordinary severity/authority policy.

The replay-fixture limitation is the contrasting fixture. M6 accepted it as a
tradeoff because absent source artifacts were represented as unavailable or
`UNKNOWN` rather than invented evidence. Its domain briefing must retain that
disposition and reopen only if the plan later claims successful replay, the
source artifacts become available, or the unavailable-marker contract changes.

## Migration validation and cutover

### Gate 1 — early M6 reconstruction and thin semantic loop

Before durable integration, feed the preserved M6 outputs, evaluator verdicts,
revisions, and gate artifacts through the target record contract. It must retain
every occurrence and disposition, reconstruct the five-occurrence semantic
family, preserve the accepted replay limitation, produce bounded briefings, and
fail closed without lifecycle mutation. This is an implementation gate, not a
long-lived report-only operating mode.

### Gate 2 — WBC-backed integrated loop

After persistence, routing, reconciliation, reviser, and gate adapters exist,
rerun the same oracle through the complete WBC-backed path. Require complete
occurrence/action coverage, deterministic replay/projection hashes, honest zero/
no-new claims, and negative proof that the ledger grants no Megaplan authority.

### Gate 3 — coordinated cutover and retirement

Against the exact cutover revisions, create and verify one content-addressed
backup, prove whole-cutover restore in isolation, quiesce admission, account for
in-flight attempts, import retained history once, and switch every critique-loop
consumer together. Run the bounded healthy/failure smoke checks, resume only on
complete WBC and ledger custody, then retire the replaced writers, readers,
flags, and fallback path.

Recovery stops admission and restores the complete verified pre-cutover bundle
and prior runtime/config revision. It preserves failed append-only evidence and
never resumes a mixed state. Canaries, prolonged shadow authority, dual-write
windows, per-boundary rollback, broad mixed-version support, and rollout
dashboards are not part of this migration.

## Success measures and failure criteria

Migration gates, grounded in the evidence-led context investigation:

- zero dropped flagged producer outputs;
- 100% recall of the named M6 regressions/rediscoveries in the curated record;
- at least 50% fewer duplicate revision actions;
- no more than a five-percentage-point loss in independent new-family recall;
- at least 95% of closure/non-action dispositions supported by cited evidence;
- bounded, reported context-token and latency overhead;
- correct distinction between semantic recurrence, refinement, regression, and
  adjacent exact-text matches; and
- valid no-additional-findings outcomes without novelty pressure.

Fail the migration gate on any suppressed significant concern, silent occurrence
loss, unsupported closure, false semantic merge that prevents review, stale
briefing used as current, materially lower novel-finding recall, or any ledger
state that incorrectly grants execution/gate authority.

Longer-run success additionally requires lower semantic recurrence after
revision, fewer reopened “resolved” findings caused by missing context, complete
disposition coverage, and stable results across model/profile changes.

## Risks and mitigations

- **Anchoring and premature closure.** Use blind discovery where valuable,
  preserve an unseeded exploration budget, require evidence and reopen
  predicates, and measure new-family recall.
- **Hallucinated semantic merges.** Keep occurrences immutable, make merge/split
  decisions explicit, permit `uncertain`, and adjudicate the fixed migration
  fixture before cutover.
- **Context-window pressure.** Use domain routing, relevance explanations,
  hierarchical evidence-linked summaries, and explicit overflow/split behavior;
  never silently truncate.
- **Stale closure evidence.** Hash all inputs, rebuild briefings after relevant
  plan/evidence changes, and evaluate reopen predicates before dispatch.
- **Taxonomy rigidity.** Start from current domains but allow evaluator-created
  cross-domain areas; do not encode semantic identity into fixed infrastructure.
- **Novelty gaming.** Make no-additional-findings valid and assess evidence
  quality rather than finding count.
- **Disposition laundering.** Keep severity independent from disposition,
  require rationale/evidence, and preserve accepted/rejected/deferred findings
  in gate context.
- **Competing authority.** Enforce the settled WBC/critique-ledger/Megaplan
  ownership split and keep projections non-authoritative for execution.
- **Model/profile confounding.** Use crossed fixed-input experiments and blind
  judging before attributing gains to the context design.

## Unresolved questions

1. Should the evaluator itself curate the ledger, or should it launch a
   dedicated curator with the evaluator retaining final disposition authority?
2. What is the smallest target disposition schema after existing flag and
   gate states are inventoried? Which meanings are projections versus stored
   events?
3. How is a stable evaluator-assigned finding identity represented without
   turning model judgment into an opaque, irreversible semantic merge?
4. What domain catalog and mandatory safety/correctness floors apply at each
   robustness level?
5. When is the blind pass worth its cost, and what minimum exploration budget
   prevents history from narrowing discovery too aggressively?
6. How are cross-domain relevance and briefing overflow explained and audited?
7. What evidence change automatically satisfies a reopen predicate, and what
   still requires evaluator judgment?
8. How should failed or malformed producer attempts with partially recoverable
   findings enter custody without promoting invalid output?
9. What retention/redaction/access rules apply when a finding links to private
    repository, transcript, tool, or external evidence?
10. How will historical flag registries be imported without falsely reconstructing
    semantic relationships that were never recorded?
11. Which component owns the honest replacement name and UX for the current
    `recurring_critiques` exact-text signal?

## Successor implementation-planning work packages

These are dependent planning packages, not authorized implementation tasks.

1. **Authority and cutover inventory.** Map current critique custody,
   flag registry, evaluator verdict, revision metadata, gate signals/output,
   WBC finding/evidence, and session-knowledge contracts. Decide the one writer
   and projection boundaries before proposing storage changes.
2. **M6 fixture and semantic-loop oracle.** Freeze the exact M6 artifact/repository
   revisions, expected 20-family audit, blocked-handoff cluster, accepted replay
   limitation, and failed/dropped-producer cases. Build an evaluation protocol
   that does not change live plan state.
3. **Minimal record contract.** Specify immutable occurrence custody,
   append-only reconciliation/disposition events, briefing freshness, evidence
   references, and no-additional-findings. Include migration and unknown-state
   behavior.
4. **Routing and briefing design.** Specify evaluator inputs/outputs, selected
   domain instructions, cross-domain relevance, context budgets, blind-pass
   policy, overflow behavior, and curator authority.
5. **Role-flow integration plan.** Trace the exact evaluator → parallel critic
   → reconciler → reviser → gate call sites and define fail-closed behavior
   without creating another transition authority.
6. **Cutover and retirement plan.** Define the exact-build gates, one-time import,
   minimum backup/restore proof, atomic checklist, custody smoke checks, and
   replaced-path retirement evidence.

The successor should not begin implementation until work packages 1–3 agree on
authority, target schema, and M6 acceptance fixtures.

## Evidence and source audit

### Raw resident conversation

Authoritative conversation: `rconv_85a1c2bfd5f1`.

- `msg_36239b6f5529` (2026-07-16T19:58:34.129432Z): reports 20 semantic
  finding families across five rounds; identifies five occurrences of the M6
  blocked-handoff/drift-checker concern and the false zero-recurrence claim.
- `msg_b68fdfab56a4` (2026-07-16T20:00:42.116960Z): user reframes the problem as
  context loss and asks for a model-led rather than prematurely technical fix.
- `msg_c84217638697` (2026-07-16T20:10:24.821122Z): evidence-led investigation
  supports context loss, blind-then-reconcile, bounded natural-language memory,
  full unresolved-finding carry, and minimal custody/freshness machinery.
- `msg_df0503d04815` (2026-07-16T20:12:43.676802Z): user proposes evaluator-led
  domain briefing with prior instructions and relevant findings.
- `msg_55c8cff71d0e` (2026-07-16T20:13:10.395577Z): defines the domain briefing
  contents and the blind-discovery/context-aware-reconciliation nuance.
- `msg_fa04a09ef55d` (2026-07-16T20:20:53.624153Z): asks for an actual M6 example.
- Discord ancestor `1527410018222211172`: gives the M6 prerequisite-ordering
  briefing example and records that current behavior is only partially
  coordinated.
- `msg_19220d1f228b` (2026-07-16T20:23:32.277529Z): requires ignored/non-acted-on
  findings, per-finding conclusions, and a valid nothing-additional outcome.
- `msg_742eb5f14076` (2026-07-16T20:24:09.101839Z): settles the cumulative ledger,
  explicit dispositions, evidence, and reopen-condition example.
- `msg_fb1babd8e3c3` (2026-07-16T20:27:09.960616Z): chooses the domain-specific
  ledger direction and requests this canonical plan.

The immutable reply chain for source Discord message `1527411267797778673` was
read in two pages (depths 1–10, then 11–12); it was complete to the root.

### M6 artifacts directly inspected

Checkout: `/workspace/custody-control-plane-20260714/Arnold`, revision
`ea2be1fe36c42c4f19afedd2c096b5dcec7c56df`.

Plan directory:
`.megaplan/plans/m6-exact-contract-and-20260716-1303/`.

- `critique_v4.json` and `critique_v5.json`;
- `critique_check_*_producer_v1.json` through `v5.json` inventory;
- `evaluator_verdict_v4.json` and `evaluator_verdict_v5.json`;
- `plan_v5.meta.json`;
- `gate_signals_v4.json` and `gate_signals_v5.json`;
- `faults.json`;
- the complete plan-directory file inventory, including five plan versions,
  five critique custody receipts, raw critic outputs, gate receipts, revision
  receipts, and state/events.

Prior evidence synthesis inspected:
`.megaplan/plans/resident-subagents/subagent-20260716-200134-e96290ae/result.md`
and its manifest/log. That read-only run reports direct inspection of 27
producer artifacts, 39 canonical findings, five evaluator verdicts, five
revisions, and all gate signals. This brief relies on its broader classification
only where consistent with the direct artifact checks above.

### Runtime sources inspected

Pinned resident runtime source:
`/workspace/arnold-runtime-resident-scheduling-1e76dbe` at
`a06e434a838b7932c9e7a45fb409772e9a2849a4`.

- `arnold_pipelines/megaplan/orchestration/critique_runtime.py:782-835`;
- `arnold_pipelines/megaplan/orchestration/parallel_critique.py:460-567`;
- `arnold_pipelines/megaplan/orchestration/gate_signals.py:74-85`;
- `arnold_pipelines/megaplan/prompts/critique.py:513-555`;
- `arnold_pipelines/megaplan/prompts/critique_evaluator.py` selection and prior
  resolution context construction;
- `arnold_pipelines/megaplan/prompts/gate.py:95-180`.

### Initiative, ticket, and document searches

Supported initiative searches were run before writing with these keyword sets:

- `critique ledger domain evaluator context findings`;
- `knowledge compiler recurrence briefing revision`;
- `session knowledge` with `--keywords-all`; and
- `critique evaluator reviser gate findings ledger context`.

They established `session-knowledge-compiler` as the closest canonical durable
knowledge initiative. Git ref inspection confirmed it is committed on
`origin/main`; the local `main` checkout is behind and exposes the tree as
untracked concurrent work. The initiative README, North Star, chain, brief/tree
inventory, directly relevant M3 brief, conversation audit, and `origin/main`
tree/index were inspected. Adjacent `megaplan-maintenance` and
`workflow-boundary-contracts` README/North Star files were inspected for
authority boundaries.

Supported ticket searches were attempted for:

- `critique ledger domain evaluator context findings`; and
- `recurrence briefing revision critic`.

Both failed read-only with a YAML `ScannerError` in the existing ticket
`shannon-claude-2-1-169-transcript-regression.md` (an unquoted colon in its
frontmatter). A fallback read-only search of `.megaplan/tickets` found only the
unrelated parallel-critique SQLite/transcript recurrence ticket and no ticket
for this domain-ledger proposal. No ticket was created or edited.

Resident document search for `critique` found the Custody critique-contract
research record plus repository critique documentation; initiative search for
`knowledge` returned `session-knowledge-compiler`. The current checkout does
not contain the indexed Custody research file, so this brief cites the preserved
M6 artifacts and resident run evidence rather than inventing its contents.

### Conversation searches recorded

Constrained resident conversation search was repeated with the terms
`critique`, `recurrence`, `domain-specific`, `ledger`, `evaluator`, `reopen`,
`blind`, `M6`, `context loss`, `same critique`, `already raised`, `domain
instructions`, `critic selection`, `ignored`, `deferred`, `rejected findings`,
`no additional findings`, `blind discovery`, `reopen conditions`, `cumulative
finding ledger`, `20 semantic finding families`, and `all unresolved findings,
including minor ones`. The first broad batch used an invalid limit of 100 and
was repeated with the supported maximum of 25. Broad M6 results were narrowed
to the exact 19:58–20:27 UTC proposal thread and then verified through immutable
reply ancestry.

## Original planning provenance and current canonical assets

- `.megaplan/initiatives/session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md`
- `.megaplan/initiatives/session-knowledge-compiler/README.md` (one canonical
  index entry only)

The original creation wrote only the two files above. The superseding big-bang
decision is implemented by the canonical `../../critique-ledger/README.md`,
`NORTHSTAR.md`, `chain.yaml`, `cloud.yaml`, milestone briefs, WBC annex, and M6
validation record. Those planning assets authorize no cutover, deployment, or
restart outside an executed and reviewed chain milestone.
