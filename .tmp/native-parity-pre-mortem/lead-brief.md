# Native Megaplan parity: green-but-wrong implementation pre-mortem

Working directory: `/Users/peteromalley/Documents/Arnold`

You are the high-reasoning Sol lead for a read-only implementation pre-mortem.
This is deliberately **not another requirements-coverage audit**. The plan has
already survived two such audits. Your question is:

> How could a competent implementation team execute the revised seven-sprint
> plan, satisfy its written gates, and still deliver the wrong system?

Anchor every judgement in the desired Python-authored end state described in
`docs/arnold/megaplan-native-representation-report.md`, especially its
aspirational whole-workflow Python representation and surrounding semantic
explanations. The sample syntax is illustrative, not sacred. The required
semantic result is the smallest readable Python-authored topology that fully
determines product behavior: branches, loops, runtime fanout/fanin,
suspension/reentry, retry/cap semantics, call-site/model policy, effects,
checkpoint identity, and terminal outcomes.

The composed runtime destination remains:

> One authored semantic topology; one exact authority-decision history; one
> current exclusive custody owner; one durable boundary/effect history; any
> number of disposable projections.

Take as locked that `custody-control-plane` completes through clean, accepted
M11 before this epic starts. Do not reopen generic Run Authority, Custody, WBC,
recovery, query, projection, or conformance substrate. Challenge Native
Parity's binding to that substrate and its actual authoring/runtime result.

## Primary sources

Read the following yourself:

- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/README.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml`
- all seven active `briefs/s1-*.md` through `briefs/s7-*.md`
- the current authored workflow, lowering/compiler/runtime, components,
  handlers, auto/CLI, suspension/resume, proof, scenario, and test surfaces
- `.tmp/native-parity-sensecheck-round2/final-audit.md` only after forming your
  independent view, to avoid merely repeating its findings and to verify its
  bounded amendments are now present

## Mandatory independent delegation

Use the repo's `subagent-launcher` machinery to fan out six isolated reviewers.
Network is enabled. Prefer `fan.py`, five concurrent workers, MiMo/Flash for
mechanical inventory and DeepSeek Pro for judgement-heavy roles. Each reviewer
must inspect primary files and actual code itself, cite exact `path:line`
evidence, and not read another reviewer's output.

### Reviewer 1 — adversarial minimal implementer

For every sprint, design the cheapest plausible implementation that could be
argued to satisfy its wording while preserving a hidden route brain, collapsing
semantic distinctions, instrumenting the wrong carrier, or manufacturing green
proof. Produce concrete green-but-wrong exploits, not generic cautions. State
which exact sentence/gate permits each exploit and the smallest amendment that
would make it impossible.

### Reviewer 2 — concrete PR and migration sequencer

Translate S1-S7 into an ordered sequence of repository-level PR slices. Track
which producer, consumer, adapter, route reader/writer, test oracle, installed
artifact, and compatibility path moves before what. Find phases where the repo
cannot remain runnable, dual-run semantics are ambiguous, deletion is premature,
or a sprint lacks a binary stop/go receipt. Provide a dependency graph and safe
strangler order, not a restatement of sprint objectives.

### Reviewer 3 — golden source-to-runtime trace designer

Derive a compact executable oracle from the aspirational Python representation.
Define exact expected authored-node/child paths, typed decisions, Run Authority
decisions/fences, Custody targets/epochs, WBC attempts/effects, checkpoints,
reentry coordinates, and terminal outcomes for representative end-to-end
scenarios. At minimum cover:

1. ordinary plan/critique/gate/revise/finalize success;
2. dynamic critique fanout with one retry and sequential fallback;
3. human clarification suspension and cross-host resume;
4. partial execute batch crash after external effect but before receipt;
5. review failure, bounded rework, scoped refinalization, and re-review;
6. override/config change, cancellation race, publication, and effect-only note.

Then test whether the plan necessarily produces and executes these traces. The
goal is a proposed golden-trace contract that could become a durable plan asset
and executable S1-S7 acceptance oracle.

### Reviewer 4 — future workflow author and extension test

Imagine maintaining the completed system six months later. Walk concrete changes:
add a new gate outcome, new dynamic review lens, new retry policy, new human
decision, new override, and new external effect. Determine where a competent
developer would naturally edit the system. Find API or ownership ambiguity that
would make handlers, auto-drive, metadata, projections, or compatibility code an
easier path than editing the Python topology. Demand extension tests that prove
the correct path is the easiest and only authoritative path.

### Reviewer 5 — incident responder and operability adversary

Start from actual failure artifacts an operator would see. Simulate stale
coordinator, expired/reassigned custody, source/policy/WBC-version drift during
suspension, crash before/after effect intent/outcome, ambiguous persistence,
cross-host handoff, partial installed-version skew, and forged/stale projections.
Judge whether a human can explain and safely repair the run from the one composed
history without consulting hidden handler state. Find missing diagnostics,
causal joins, quarantine states, or repair invariants that should be plan-level
acceptance requirements rather than incidental implementation detail.

### Reviewer 6 — Python authoring ergonomics and complexity critic

Judge the proposed end state as an API and maintenance experience, not just a
formal model. Sketch what the completed Python representation would plausibly
look like after S1-S7. Identify ceremony, duplicated declarations, identity
plumbing, policy noise, or over-granularity likely to drive future bypasses.
Separate justified semantic compression from dangerous hiding. Propose the
smallest authoring primitives, generated bindings, linting, examples, and
readability/complexity budgets needed to keep the Python topology honest and
pleasant. Do not optimize away required semantics.

You may add one targeted seventh reviewer only if the six expose a material
cross-cutting ambiguity. Do not edit source, docs, plans, tests, or git state.
Writing artifacts only under `.tmp/native-parity-pre-mortem/` is allowed.

## Sol synthesis requirements

Reconcile conflicts against primary sources and actual code. Reject findings
that simply rediscover a bounded amendment already present. Distinguish:

- genuine plan ambiguity that permits a green-but-wrong implementation;
- missing executable oracle or migration stop/go boundary;
- useful sprint-level implementation detail that need not enter the epic;
- authoring ergonomics that materially affects long-term semantic authority;
- completed Custody substrate correctly out of scope.

Produce:

1. `.tmp/native-parity-pre-mortem/final-report.md`
2. `.tmp/native-parity-pre-mortem/golden-trace-contract.md`
3. a concise final response with verdict and paths

The final report must include:

- decisive verdict: **operationally determinate**, **determinate with bounded
  sharpening**, or **gameable in material ways**;
- ranked green-but-wrong exploit catalogue with exact permitting text,
  plausible implementation, why current proof misses it, and exact amendment;
- sprint/PR migration dependency graph and stop/go boundaries;
- future-extension table showing the intended edit point and anti-bypass proof;
- incident/repair observability assessment;
- Python authoring ergonomics assessment with a proposed readability contract;
- an amendment set limited to findings that materially improve the probability
  of reaching and retaining the report's Python-authored end state;
- important findings deliberately left as sprint-planning detail.

The golden trace contract must be concrete enough for S1/S7 to turn into
machine-readable fixtures: stable scenario IDs, authored path, decisions,
fanout children, four identity domains, WBC effects, checkpoint/reentry rules,
expected terminal state, forbidden observations, and mutation assertions.

Take a position. The purpose is to make the plan harder to game and easier to
execute correctly, not to make it longer for its own sake.
