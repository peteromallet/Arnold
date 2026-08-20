# Native Megaplan parity: hierarchical gap audit

Working directory: `/Users/peteromalley/Documents/Arnold`

You are the high-reasoning lead for a read-only architectural audit. The goal is
to determine whether the articulated native Megaplan end state actually lines up
with (a) the corrective epic plan, (b) the seven active sprint briefs and what
they delivered, and (c) the current implementation. Identify every material gap,
including cases where the plan itself omits an end-state requirement, where a
sprint claims work that the current code does not embody, or where conformance
evidence can false-pass.

## Required primary sources

- `docs/arnold/megaplan-native-representation-report.md`
  - especially the aspirational whole-workflow representation and its explicit
    constructs/semantics
- `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml`
- `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s1-*.md`
  through `s7-*.md`
- the retained original `briefs/m1-*.md` through `m10-*.md`
- `arnold_pipelines/megaplan/workflows/workflow.pypeline` and all native
  subworkflows/policies it imports
- relevant lowering/compiler/runtime, handler, component, auto-drive, resume,
  override, test, scenario, and conformance/evidence-generation code
- git history for the seven sprint auto-publish commits when needed to
  distinguish planned/delivered/current state

## Mandatory hierarchical delegation

Spend your own context on synthesis and judgement. Delegate the broad evidence
gathering to independent lower-cost Hermes agents. Use the repo's
`subagent-launcher` tools directly from this process; network access is enabled.
Prefer `fan.py` with 5 focused briefs and at most 5 workers. Use MiMo/Flash for
mechanical inventory and DeepSeek Pro for judgement-heavy lenses. Each reviewer
must inspect files itself and return conclusions with exact file/line evidence.

At minimum fan out these non-overlapping lenses:

1. **End-state contract inventory**: atomize the aspirational report into a
   numbered requirement matrix covering every phase, branch, loop, fanout/fanin,
   policy, suspension/resume path, checkpoint identity, and semantic-authority
   constraint.
2. **Plan and sprint coverage**: map every requirement to the corrective plan,
   active s1-s7 brief, original m1-m10 brief, deliverable, and proof gate; flag
   absent, vague, or weakened coverage.
3. **Current source/topology**: inspect `workflow.pypeline` plus native
   subworkflows and establish which requirements are visibly source-authoritative
   today versus hidden in components, handlers, metadata, route tables, runtime,
   CLI, or auto-drive.
4. **Runtime/control semantics**: trace execution, retries/timeouts/model routing,
   execute DAG batching, review/rework, override/human gates, suspension/resume,
   and path-addressed checkpoints from authored source through lowering/runtime;
   find semantic divergence or double-route-brain behavior.
5. **Proof/conformance adversary**: inspect scenarios, evidence generation,
   validators, mutation/deletion tests, installed-package tests, and final reports;
   find false-pass mechanisms and requirements that are asserted narratively
   rather than behaviorally.

You may add a sixth targeted reviewer if the first five expose a cross-cutting
gap that needs independent confirmation. Do not ask the user questions. Do not
edit source, docs, tests, plans, or git state. Writing audit artifacts only under
`.tmp/native-parity-sensecheck/` is allowed.

## Required synthesis

Reconcile disagreements between reviewers by checking primary sources yourself.
Do not accept milestone names, completion commits, generated reports, or green
tests as proof without tracing the underlying semantic carrier.

Produce:

1. `.tmp/native-parity-sensecheck/final-audit.md` — the full durable report.
2. A concise final response summarizing the verdict and pointing to that file.

The full report must contain:

- a decisive top-line verdict: aligned, partially aligned, or materially
  misaligned;
- a requirement matrix with stable IDs and columns for articulated end state,
  plan/brief coverage, current implementation carrier, proof quality, status,
  and exact evidence;
- a ranked gap register separating:
  - articulation → plan gaps;
  - plan → delivered/current-code gaps;
  - current-code → runtime-behavior gaps;
  - proof/conformance gaps;
- severity (`critical/high/medium/low`), confidence, consequence, and smallest
  corrective action for each gap;
- explicit confirmation of which old false-pass patterns are genuinely blocked
  and which can still recur;
- a proposed amendment set for the plan/briefs and the minimum regression gates
  needed before claiming native parity;
- a short section listing important areas checked with no gap found.

Be exhaustive but evidence-dense. Prefer tables and exact paths/line numbers over
narrative. Take a position; do not hedge merely because the system is complex.
