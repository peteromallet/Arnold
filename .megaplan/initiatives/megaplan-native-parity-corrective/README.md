# Megaplan Native Parity Corrective

Eight busy two-week milestones that make canonical Megaplan's authored Python
topology the complete product-semantic authority and bind every resulting
authoritative action to the already-completed Run Authority, Custody, and
Workflow Boundary Contracts (WBC) control plane.

This epic starts **after** `custody-control-plane` reaches its full M11 end
state. `chain.yaml` enforces that sequencing with a content-addressed
`chain_completed` prerequisite and `require_manifest: true`. The prerequisite
manifest/proof map must cover M11's accepted enforcement cohort, exact contract
and schema versions, installed-runtime attestation, projection rebuild,
captured replay, cross-host handoff, and zero-bypass conformance. Intermediate
M8/M9 receipts, shadow-only guards, status labels, and auto-publish commits do
not satisfy admission.

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

The active launch contracts are `briefs/s1-*.md`, `briefs/s2-*.md`,
`briefs/s3a-*.md`, `briefs/s3b-*.md`, and `briefs/s4-*.md` through
`briefs/s7-*.md`:

1. custody admission and semantic-preservation gate;
2. generic authored control primitives bound to admitted APIs;
3. prep/plan/critique cutover, execution-plane binding, and GO-1A;
4. gate/revise front-half completion and GO-1B;
5. tiebreaker, finalize, human decisions, and durable reentry;
6. one reusable execute/review/rework delivery cycle;
7. override, recovery, auto-drive, and projection adoption;
8. native-topology conformance plus the Platformization handoff manifest.

The older `briefs/m*.md` files are historical pre-custody decomposition
appendices. They are not launch contracts and cannot narrow the active briefs.

Primary anchors:

- `NORTHSTAR.md`
- `GOLDEN_TRACE_CONTRACT.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/megaplan-native-current-codebase-map.md`
- `docs/arnold/megaplan-native-oracle-synthesis.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`

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
