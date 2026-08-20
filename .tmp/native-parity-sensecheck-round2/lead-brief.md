# Revised Native Megaplan parity epic: hierarchical end-state challenge

Working directory: `/Users/peteromalley/Documents/Arnold`

You are the high-reasoning Sol lead for a read-only adversarial audit of a
newly revised seven-sprint Megaplan epic. The revision was intended to reach a
precise end state after the separate `custody-control-plane` epic has completed
through M11. Determine whether the revised plan will actually produce that end
state, rather than merely using the right vocabulary.

The required destination is:

> One authored semantic topology; one exact authority-decision history; one
> current exclusive custody owner; one durable boundary/effect history; any
> number of disposable projections.

Take the sequencing assumption as locked: the complete, clean, accepted Custody
M11 end state exists before this epic starts. Do not count today's incomplete
cloud publication state as a Native Parity design gap. Instead challenge whether
the plan admits, pins, consumes, and extends that completed substrate correctly,
without duplicating or weakening it.

## Required primary sources

- `.megaplan/initiatives/megaplan-native-parity-corrective/README.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml`
- `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s1-*.md`
  through `s7-*.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `.tmp/native-parity-sensecheck/final-audit.md`
- `.tmp/native-parity-sensecheck/custody-overlap-audit.md`
- the retained historical `briefs/m1-*.md` through `m10-*.md`, only to detect
  accidental scope loss or misleading active/historical authority
- the actual chain schema/loader/validator implementation
- current native workflow, lowering/runtime, component/handler/auto/CLI,
  Run Authority, Custody, WBC, suspension/resume, proof, scenario, and
  conformance code where feasibility or carrier ownership must be checked

## Locked semantic distinctions

The audit must enforce these distinctions rather than allowing one generic
`attempt_id` or evidence object to blur them:

1. authored semantic node/invocation plus deterministic child path;
2. Run Authority subject attempt plus coordinator fence;
3. WBC execution attempt plus exact boundary-contract version;
4. Custody action target plus lease owner and custody epoch.

WBC evidence is history and conformance, never permission. A lease is exclusive
current responsibility, never permission. An authoritative action requires the
current Run Authority grant/fence and the current Custody lease/epoch, plus the
required exact-version WBC boundary evidence. Projections are disposable views
and cannot trigger or authorize positive action.

The plan may simplify pure computation inside phase bodies, but it must keep
branches, loops, fanout/fanin, suspension/reentry, retry/cap semantics,
model/call-site policy, effects, checkpoint identity, and terminal outcomes
source-authoritative or attached through explicit typed authored constructs.

## Mandatory hierarchical delegation

Spend your own context on synthesis and judgement. Delegate broad evidence
gathering to independent lower-cost Hermes agents using the repo's
`subagent-launcher` machinery. Network is enabled. Prefer `fan.py` with six
focused briefs and at most six workers; if runtime capacity is five, combine the
two most mechanical lenses. Use MiMo/DeepSeek Flash for inventory and DeepSeek
Pro for architectural judgement. Each reviewer must inspect primary files and
return exact file/line evidence. Do not expose one reviewer's conclusions to
another before they finish.

Required non-overlapping lenses:

1. **End-state coverage and scope-loss audit.** Atomize the aspirational report,
   prior audit requirements, and custody-overlap requirements; map every item to
   the revised North Star, plan, sprint, deliverable, and blocking gate. Detect
   omissions, weakened wording, and scope lost during m1-m10 to s1-s7 compression.
2. **Authority/custody/WBC composition audit.** Challenge prerequisite admission,
   non-duplication, four-identity mapping, action validation, producer relocation,
   suspension/reentry, fencing, epochs, effects, recovery, and projection
   non-authority. Find places where the plan could produce parallel histories or
   instrument the wrong semantic carrier.
3. **Sprint architecture, granularity, and dependency audit.** Decide whether the
   seven busy two-week sprints are coherent, correctly ordered, realistically
   scoped, and vertical. Flag over-granular work, unjustified bundling, hidden
   prerequisites, unsafe deletion timing, or a sprint that cannot leave the tree
   in an integrable state.
4. **Executable-gate and false-pass adversary.** Inspect actual chain schema and
   validation code. Verify every declared field is supported and meaningful.
   Challenge launch admission, per-sprint gates, S7 replay, proof maps,
   manifests, set equality, installed artifacts, runtime traces, mutation tests,
   shadow/enforce mode, and negative authority tests. Find any route to a green
   chain that has not achieved the North Star.
5. **Current-state migration feasibility and carrier deletion.** Trace today's
   source-to-runtime route brains and the plan's migration sequence. Verify it can
   move WBC producers and policy ownership to canonical lowered nodes before
   deleting components/handlers/CLI/auto authorities, without a big-bang gap or
   compatibility path retaining control.
6. **Identity, crash, resume, and effects adversary.** Walk representative dynamic
   fanout, task batches, human suspension, crash-before/after-effect,
   cross-host handoff, retry, cancellation, publication, and config-change
   scenarios. Determine whether the planned IDs, fences, leases, WBC events, and
   reentry coordinates are sufficient and testable.

You may add a seventh focused reviewer only if a material cross-cutting ambiguity
requires independent confirmation. Do not edit source, docs, plans, tests, or git
state. Writing audit artifacts only under
`.tmp/native-parity-sensecheck-round2/` is allowed.

## Required synthesis

Reconcile reviewer disagreements by checking primary sources yourself. Do not
credit an aspiration merely because it appears in the North Star; it must have a
correctly placed sprint deliverable and behavioral proof. Do not credit a gate
that the chain/runtime cannot actually execute. Distinguish:

- a genuine gap requiring a plan edit;
- an implementation detail properly deferred to sprint planning;
- a justified semantic compression;
- completed Custody substrate that should remain out of Native Parity scope.

Produce:

1. `.tmp/native-parity-sensecheck-round2/final-audit.md` — the durable report.
2. A concise final response with the verdict and path.

The report must include:

- a decisive verdict: **adheres**, **adheres with bounded amendments**, or
  **materially fails to reach the end state**;
- a stable requirement matrix covering the prior audit and custody-composition
  requirements, with revised-plan location, delivery sprint, executable proof,
  status, and exact evidence;
- a ranked gap register with severity, confidence, consequence, and exact plan
  amendment;
- an explicit audit of all chain fields/preconditions/validation semantics;
- a sprint-by-sprint load/dependency/deletion-risk assessment;
- concrete text-level amendments, scoped to the smallest authoritative assets;
- important areas checked where the revised plan is already sound;
- a final answer to: if all seven sprints execute exactly as written, can hidden
  semantic authority, stale authority/custody, or evidence-as-authority still
  survive while the epic reports success?

Be exhaustive but evidence-dense. Prefer tables and exact paths/line numbers.
Take a position and challenge the plan, not the intent.
