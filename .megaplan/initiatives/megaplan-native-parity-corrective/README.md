# Megaplan Native Parity Corrective

Twelve serial milestones, preceded by one chain-gate bootstrap sprint, make
canonical Megaplan's authored Python
topology the complete product-semantic authority and bind every resulting
authoritative action to the already-completed Run Authority, Custody, and
Workflow Boundary Contracts (WBC) control plane.

This epic starts **after** the generic pre-merge milestone-gate bootstrap and
`custody-control-plane` reach their completed states. `chain.yaml` enforces
both with content-addressed
`chain_completed` prerequisite and `require_manifest: true`. The prerequisite
manifest/proof map must cover M11's accepted enforcement cohort, exact contract
and schema versions, installed-runtime attestation, projection rebuild,
captured replay, cross-host handoff, and zero-bypass conformance. Intermediate
M8/M9 receipts, shadow-only guards, status labels, and auto-publish commits do
not satisfy admission.
The same validated Custody manifest must bind the exact
`bounded-incident-projection-handoff.json`: crash-safe bounded/incremental
projection, full-rebuild parity, and the 57,000-event latency/peak-memory
benchmark. Custody owns that implementation and receipt. Native only consumes
and rechecks the handed-off API; it must not build a substitute projector.

The gate bootstrap itself is non-self-hosted: its one PR requires external
pre-merge CI, independent review, and manual merge, with the old final gate
used only as a post-merge backstop. Native may rely on its completion manifest
only when those records and the new gate schema are bound. The schema supplies
one fixed milestone lifecycle:
pre-merge validation → merge → merge-HEAD readiness validation → optional
typed receipt-consuming transition → post-transition verification →
completion. A transition is a declared non-shell handler, not arbitrary YAML
execution.

## Destination

> One authored semantic topology; one exact authority-decision history; one
> current exclusive custody owner; one durable boundary/effect history; any
> number of disposable projections.

The contracts stay distinct:

- native source owns semantic node and child-path identity and product routes;
- Run Authority owns grants, subject attempts, decisions, and coordinator
  fences;
- Custody owns exact action targets, exclusive leases, and custody epochs;
- WBC owns exact-version execution-attempt and effect history;
- projections are rebuildable explanations and never authority.

Every authored typed decision occurrence and terminal acceptance must have
exactly one accepted Run Authority Decision whose ID, outcome, and CAS sequence
are consumed by the corresponding runtime transition. Subject-attempt/fence
evidence alone is not a decision history.

WBC evidence is not a grant or a lease. An authoritative action requires the
current Run Authority grant/fence **and** current Custody lease/epoch, plus the
required exact-version WBC evidence for the applicable boundary.

Checkpoints and reentry also bind the authored program/topology digest,
call-site-policy digest, exact WBC contract version, and the normalized
product/Plan Contract digest wherever it changes evidence obligations. Drift
requires an explicit typed migration, new-attempt, or quarantine decision;
matching a semantic path string is not enough.

Native means more than Python syntax. The topology uses a deterministic,
compiler-fenced Python subset and is the only product route owner. Ambient
nondeterminism and I/O cross declared typed durable boundaries; generated
manifests, Megaplan Plan Contracts, handlers, status, and projections cannot
add routes or authority. Source-local diagnostics and a lightweight harness
using the production lowerer keep that restriction usable during development.
The canonical authored suffix is `.pype`: the epic migrates every live
`.pypeline` source and every compiler, loader, package, source-map, manifest,
CLI, validator, generator, test, example, and editor/tooling reference that
recognizes it. `.pypeline` remains permissible only as historical text or an
expiry-bound reader for an exactly pinned pre-cutover artifact; it cannot admit
new source or satisfy completion.

The format itself is fixed by
`docs/arnold/pype-authoring-contract.md`: one canonical `@workflow` per
`.pype`, one file per durable root or child workflow, optional private
file-local steps/helpers, reusable leaves in `.py`, canonical-only static
workflow imports, and preview-only `.py @workflow`. “Subworkflow” describes a
workflow's hosting role, not a second authored kind. Paths are provenance;
logical identity, executable digests, and explicit migration records govern
resume.

LLM/tool boundaries bind prompt content, model/tool configuration, budgets,
cache policy, and durable results. Checkpoints inline only bounded control data
and otherwise carry immutable artifact references. Exact pinned artifacts stay
resolvable for suspended runs, and all durable namespaces derive from run and
semantic occurrence coordinates so repeated or concurrent invocations cannot
collide.

The durable subset also includes named enclosing-loop exits that close the
target ledger, terminalize intervening scopes and reenter as an explicit fresh
loop instance; immutable attempt terminals distinguished from the one aggregate
child terminal; canonical decision
values, completion-order-independent keyed reducers, frozen fanout bindings,
closed typed phase errors, checkpointed typed reconfiguration, and a declared
agentic-phase protocol for variable inner tool calls. Open-ended streams are
deliberately unsupported. The normalized product/Plan Contract digest is pinned
whenever it changes evidence obligations.

Migration comparisons run only in a quarantined, non-resumable and non-effect-
capable namespace. Every old or candidate live plane remains registered behind
the one admitted validator, with one admitted writer at a time. M11 must already
prove restore-resistant fences/epochs and canonical repair-request revalidation.
S1 runs executable capability probes; missing required M11 behavior stops for a
new upstream point release rather than creating a Native substitute.

## Scope and schedule

The active launch contracts are `briefs/s1-*.md`, `briefs/s2f-*.md`,
`briefs/c1-*.md`, `briefs/c2-*.md`, `briefs/s2r-*.md`,
`briefs/s3a-*.md`, `briefs/s3b-*.md`, and `briefs/s4-*.md` through
`briefs/s7-*.md`:

1. custody admission, staged `.pype` suffix migration, and semantic-
   preservation gate without changing the selected authoring suffix;
2. `.pype` compiler, canonical identity and durable-boundary call-site
   templates, converter, preview, GO-FORMAT, and authoring/admission switch;
3. C1 experimental neutral completion contract/identity kernel, shadow
   generation, negative fixture, and content-addressed divergence ledger;
4. C2 immutable binding/evaluation kernel, internal wire/decoder contract,
   restore/projection-invariance proof, and shadow acceptance integration;
5. generic durable control primitives, concrete aggregation instances, and
   the sole authoritative kernel-enablement GO-0 receipt;
6. prep/plan/critique cutover, execution-plane binding, and GO-1A;
7. gate/revise front-half completion and GO-1B;
8. tiebreaker, finalize, human decisions, and durable reentry;
9. complete delivery/completion vertical slice plus exhaustive per-effect-class
   GO-2 proof in shadow;
10. GO-2-consuming live delivery/completion cutover, admitted review/rework,
    and 57k bounded-query consumption;
11. override, recovery, auto-drive, and projection adoption;
12. native-topology/completion and zero-live-`.pypeline` conformance plus the
   Platformization handoff manifest.

S7 creates a new corrective target gate:
`docs/arnold/megaplan-native-parity-conformance.yaml`,
`docs/arnold/megaplan-native-parity-traceability.yaml`, and
`scripts/validate_megaplan_native_parity_conformance.py`. The older
`megaplan-native-representation-*` ledger remains immutable pre-corrective
baseline evidence and is not the chain's final validator.

S2F ends with a mandatory `GO-FORMAT` receipt covering exact-one files, private
boundaries, leaf laws, static imports, cycles/recursion, identity/migrations,
source/package correspondence, preview/legacy isolation, and checkout/install/
wheel/cloud equivalence. C1 and C2 are blocked until it is green. S2R is
blocked until GO-FORMAT and both shadow-kernel receipts are independently
revalidated; S3A is blocked until S2R's typed transition closes GO-0 and emits
the sole authoritative completion-kernel enablement receipt.
The machine boundary is
`scripts/validate_pype_authoring_contract.py` over
`docs/arnold/pype-authoring-conformance.yaml` and
`.megaplan/initiatives/megaplan-native-parity-corrective/go-format-receipt.json`
(`arnold.megaplan.go_format_receipt.v1`); S2R reconsumes it rather than trusting
milestone status.

Every milestone uses the bootstrap's typed pre-merge/post-merge validation:
S1 through S6 use `conformance_gate`, including C1/C2, split S2F/S2R and
S5A/S5B; S7
uses `final_conformance_gate`. Every authority-changing milestone declares its
cutover in the chain's typed transition slot; the transition consumes the exact
accepted readiness receipt and a separate post-transition verifier must pass
before the milestone completes. `depends_on`, a filename, a product-side
convention, or later S7 validation does not grant authority. S5A proves the
complete future-live behavior matrix and all effect-protocol classes in shadow,
while S5B alone may make effects live through that lifecycle.

## Completion sequencing and ownership

```text
accepted/consolidated Custody M11 + bounded-projection handoff
  -> S1 -> S2F -> C1 -> C2 -> S2R GO-0
  -> S3A -> S3B -> S4 -> S5A -> S5B -> S6 -> S7
  -> Platform S1 -> S2A -> S2B -> S3 -> S4 -> S5 -> S6
```

S2F owns authored/component/graph identity and durable-boundary call-site
templates. C1/C2 own the experimental neutral completion contracts and remain
non-authoritative. Admission and S2R instantiate runtime occurrences; S2R owns
concrete child sets and aggregation instances, and its GO-0 transition is the
only live enablement. Every later Native gate consumes the exact kernel
receipts and current divergence-ledger hash. S5A/S5B own the complete
finalize/admit/execute/evidence/accept/review/reopen-or-new-work/aggregate
slice; S5B alone makes it live and consumes Custody's bounded projection.

The former standalone Completion M1–M5 chain is retired as a launch target.
Its proposal, briefs, and exhaustive redistribution map remain normative at
`../standardized-completion-specifications/`.

The intended organization is:

```text
arnold_pipelines/megaplan/workflows/
  workflow.pype
  plan_quality/
    cycle.pype
    critique.pype
    gate.pype
    tiebreaker.pype
    steps.py
    policies.py
    types.py
  delivery/
    cycle.pype
    execute.pype
    execute_batch.pype
    review.pype
    steps.py
    policies.py
    types.py
  control/
    steps.py
    policies.py
```

`control/` deliberately has no `.pype`: control operations remain leaf steps
whose resulting routes stay visible in the calling workflow. A new workflow
file is created only when a region has its own durable outcome/lifecycle,
reuse, or independent provenance need.

The older `briefs/m*.md` files are historical pre-custody decomposition
appendices. They are not launch contracts and cannot narrow the active briefs.

Primary anchors:

- `NORTHSTAR.md`
- `GOLDEN_TRACE_CONTRACT.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/megaplan-native-current-codebase-map.md`
- `docs/arnold/megaplan-native-oracle-synthesis.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `docs/arnold/pype-authoring-contract.md`
- `../standardized-completion-specifications/SUPERSESSION_CROSSWALK.yaml`

`GOLDEN_TRACE_CONTRACT.md` is the human-reviewed normative composition oracle.
An independent source oracle checks authored topology and a separately
implemented verifier checks raw primary-store multiplicity before approved
normalization. It compares one same-run ordered/partial-order history across lowering, Run
Authority decisions, Custody, WBC, checkpoints, effects, and terminal
acceptance. It is proof only: it never supplies a route or runtime authority.

Run only after the custody prerequisite manifest exists and validates:

```bash
python -m arnold_pipelines.megaplan chain start \
  --spec .megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml
```
