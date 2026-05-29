# Committed Unknown-Unknowns — Vantage: THE 10-YEAR ARC

> We ARE building Arnold's full vision. This brief does not question the bet, the demand, or the
> founder's time. It assumes Arnold SUCCEEDS WILDLY and asks the only question the 10-year arc poses:
> **what early (2026-convenience) decision forecloses the best 2030/2035 version?** Where is the
> one-way door we are about to walk through without noticing?

## How this vantage differs from the sibling committed-uu briefs (and what it deliberately does NOT re-cover)

The existing committed-uu corpus is strong and I read it before writing, to avoid duplicating it:

- `durable-foundation.md` → the **Effect Ledger** (replay-class / idempotency / compensation for acts on the world).
- `versioning-identity.md` → the **Behavioral Identity Manifest** (hash the generating function, not the output).
- `the-primitive.md` → the **Activation** (pluggable readiness rule + lifecycle + supervisor as the engine's atom).
- `ai-authored-runtime.md` → the **Contract Ledger** (machine-checkable Port-contract type *system*).
- `distributed-reality.md` → federation: key pool as hidden scheduler, leases-aren't-mutex, no global time order.
- `emergent-dynamics.md` / `the-soul-irreplaceable.md` → Goodhart collapse, model monoculture, recursion governor, open-loop calibration.
- `safe-composition-os.md` → taint **lattice**, model-call-as-declassifier, declassification authority.
- `observability-eval.md` → unattributed/unversioned eval verdict, lineage breaks on AI topologies.
- `adoption-artifact.md` → the shareable/forkable run as a viral artifact.

All of those hunt *inside the machine*. The 10-year arc hunts the **outer envelope**: the relationships
between the self-improving substrate and three slow-moving, externally-owned realities it will collide
with as it succeeds — **the model frontier**, **human/institutional accountability**, and **economic
metering**. These are the one-way doors that don't hurt while there is one tenant and one author, and
that cannot be re-cut once a successful platform has accreted dependents on the wrong side of them.

The endgame I am reasoning toward: Arnold's true 2032 form is **the OS for autonomous work** — the layer
where AI programs are *scheduled, governed, metered, and answered-for*. Not a planner, not a workflow
engine. An OS is defined less by its scheduler (covered) than by its **process model, its accounting,
and its accountability to the world outside the box**. Those three are the gaps below.

---

## UNKNOWN-UNKNOWN 1 — The frontier-model curve will dissolve the P-E-V decomposition itself; we are hard-coding "the work must be broken into plan→execute→verify phases" as a permanent truth when it is a 2026 capability artifact

**Insight.** Plan-Execute-Verify, milestone decomposition, complexity-1–5 tiering, critique→revise loops —
the entire privileged HEART — exists *because today's models cannot one-shot a two-week deliverable
reliably*. Decomposition is a **compensation for a model limitation**, not a law of nature. The 10-year
curve runs straight at that assumption: longer effective context, agentic-native models that plan
internally, models with durable world-models and tool-use baked in, and eventually models for which the
*correct* move is **not to decompose at all** — hand the whole brief to one capable agent and verify the
artifact, or hand it to a model that needs no external verifier because it self-verifies more cheaply
than Arnold's separate review phase can. When that arrives, Arnold's flagship value (the multi-phase
harness) becomes the thing customers *route around*. The phases are not just a feature — they are baked
into the **state machine** (`STATE_PREPPED → STATE_PLANNED → STATE_CRITIQUED → STATE_GATED →
STATE_FINALIZED → STATE_EXECUTED → STATE_REVIEWED`, the canonical plan states), the **profile slot
vocabulary** (`plan`, `critique`, `revise`, `finalize`, `execute`, `review`), the **prompt registry
keys**, the **receipt schema**, and the **billing/observability grain**. P-E-V is not a pipeline Arnold
*runs*; it is a shape Arnold *is built out of* at every layer. The platform's most reused vocabulary is a
bet on a model deficit that the frontier is actively erasing.

**Why it's invisible to us.** Every sibling brief — and the whole codebase — treats P-E-V as the
*invariant* and the model as the *variable* ("cheapest-capable routing" optimizes which model fills a
fixed phase). The self-improvement loop improves *routing within phases*; it has no representation for
"this whole class of work no longer needs phases." We measure success by "the planning pipeline runs
well," which a phase-shaped harness satisfies indefinitely — right up until the day the cheapest-capable
move is *zero phases*, and the harness's structure is now a tax, not a moat. The decision feels settled
because P-E-V *is the product*; that is exactly why its contingency on a model deficit is unexaminable
from inside.

**What it threatens.** The privileged HEART's relevance, and worse, its *foreclosure of the better
2030 version*. If phases are load-bearing in the state machine and slot vocabulary, Arnold cannot
gracefully host the workload that says "no plan phase, no separate verifier" — it can only bolt a
"single-shot" special case onto a phase-shaped spine (the same mush failure `the-primitive.md` names,
one level up: a *workflow-shape* mush instead of an *activation* mush). The platform that should have
become "the OS for autonomous work of *any shape*" stays "the multi-phase planner," and the frontier
walks past it. The deepest cut: the self-improvement loop optimizes the harness toward being a *better
phased planner* — accelerating in the direction the frontier is making obsolete.

**Severity: reshapes-architecture** (escalates to could-sink-the-build if a capable agentic-native model
generation lands inside the build window and P-E-V is still hard-wired into the state machine).

---

## UNKNOWN-UNKNOWN 2 — A successful "OS for autonomous work" is accountable to humans and institutions, but Arnold has no model-independent ANSWERABILITY layer — and the self-improvement loop optimizes away the only artifact a human/regulator can trust

**Insight.** The moment Arnold succeeds as the substrate for autonomous work, its binding constraint
stops being *correctness* and becomes **answerability**: "*Why* did the system do X? Who authorized it?
Who is liable? Can it explain itself to someone who wasn't in the loop — a regulator, an auditor, a
court, a non-technical owner?" Every other durable-execution system that scaled hit this: the journal
that engineers love (replay, debug) is *not* the artifact an institution trusts, because the institution
cannot read an event log and the log records *what* happened, not *why it was legitimate*. Arnold's
specific problem is acute on two fronts the sibling briefs only graze:

1. **The "why" is a model output, which is the least durable and least auditable thing in the system.**
   The journal can prove "model M emitted plan P at hash H for cost C." It cannot prove "this was a
   *reasonable* decision," because the reasoning is a stochastic completion that won't reproduce
   (`observability-eval.md` UU-4 notes determinism stops at the model boundary; the *accountability*
   consequence is unnamed). When a 2030 autonomous Arnold merges code that takes down a customer's
   prod, "the log shows what happened" is not a defense — and the explanation the model would give on
   replay is a *different, post-hoc* rationalization, not the original cause.
2. **Self-improvement is in direct tension with accountability.** A regulated/audited substrate must be
   able to say "for this run, these were the rules in force, frozen and attestable." But the whole HEART
   *continuously rewrites its own rules* (routing, prompts, the engine itself per the dogfood loop). The
   Behavioral Identity Manifest (`versioning-identity.md`) gives *reproducibility* — but reproducibility
   ≠ accountability. An auditor doesn't want "here's the hash that produced it"; they want "here is the
   *attested policy* — the model allowlist, the spend authority, the human approvals, the data-handling
   rules — that this autonomous action was *permitted* under, signed, and not retroactively editable."
   Arnold has `auto_approve` gates and human-decision steps, but no **attested, model-independent policy
   envelope** that travels with a run and can be presented to an outsider as the basis of legitimacy.

**Why it's invisible to us.** Today the human is *in the loop and technical* — Peter reads the trace,
the memory files, the diagnose skill. Accountability is satisfied implicitly because the operator was
present and competent. The vision's success condition *removes that human* (autonomous work, async
recipients, AI authors) — which silently removes the only answerability mechanism the platform has, and
nothing is built to replace it. We conflate **observability** (engineer can introspect) with
**answerability** (an outsider who wasn't there can be given a defensible, attestable account). They are
different organs; we have built the first and named it as if it were the second.

**What it threatens.** The entire "OS for autonomous work" endgame. The substrates that win the
autonomous-work category will be the ones a CISO, a regulator, and an insurer can *certify* — and
certification needs a frozen, signed, model-independent policy-and-authority record per action, plus a
human-readable causal account, neither of which Arnold currently produces. Retrofitting this after
tenants depend on the un-attested journal is the migration that eats years: every run ever recorded
lacks the attestation fields, and the self-improvement loop has been mutating the rules with no signed
record of *which rules applied when*. The platform that should have become the *trusted* OS for
autonomous work becomes un-certifiable, and the certifiable competitor wins the enterprise.

**Severity: could-sink-the-build** (for the enterprise/regulated endgame; the consumer/dev tenant
survives without it, but the highest-value 2030 market is exactly the one that demands it).

---

## UNKNOWN-UNKNOWN 3 — Arnold has no native UNIT OF ACCOUNT for autonomous work, so it cannot become the metering/value-capture layer (the "AWS-of-agents" endgame); cost is recorded in provider dollars, which is the wrong, non-durable, non-composable unit

**Insight.** AWS became AWS not because it had the best compute but because it invented the **billable
unit** — the instance-hour, the GB-month, the request — a stable, composable, meterable abstraction that
*decoupled the price the customer pays from the cost AWS incurs*, and that survived a decade of hardware
churn underneath. The "AWS of agent orchestration" endgame requires the same move: a **durable unit of
autonomous work** that Arnold owns, meters, and can price independently of the underlying model's token
cost. Today Arnold records `cost_usd` in receipts — i.e. it denominates value in *the provider's own
unit, in raw provider dollars, after the fact*. That is fatal for a platform-of-record for three reasons
the cost-attribution briefs (which focus on *correctness* of attribution) don't reach:

1. **The unit is non-durable.** Provider prices change weekly (the soul brief notes the cheapest-capable
   index has a half-life of weeks). A platform whose unit of account *is provider dollars* has a unit
   that re-denominates underneath every stored record — you cannot compare "the cost of this work in
   2026" to "in 2029," cannot offer a customer a stable price, cannot build a margin, cannot bill a
   downstream tenant predictably. Content-hashing the *artifacts* doesn't help: the journal authenticates
   the bytes but the *value* attached to them is in a currency that floats.
2. **The unit is non-composable.** When tenant B composes tenant A's pipeline (the explicit
   shared-pieces vision), there is no abstraction for "A's work cost B *this many Arnold-units*" — only
   raw passthrough of summed provider dollars, which leaks A's model choices and gives B no stable
   contract. Value capture across composed pieces — the entire economic engine of a platform — has no
   denominator.
3. **The unit measures inputs, not work done.** `cost_usd` and tokens measure *what was spent*, not
   *what was accomplished*. The OS-for-autonomous-work endgame needs to meter **completed verified
   work** (a metric Arnold uniquely *can* define, because it has the verify phase) — "a verified
   milestone," "a passed-review unit of change" — decoupled from how many model calls it took. A
   self-improving substrate that gets cheaper over time *destroys its own revenue* if it bills in
   inputs (better routing → fewer tokens → less revenue for the *same delivered work*). Billing in
   inputs makes self-improvement and revenue **directly antagonistic**.

**Why it's invisible to us.** Cost is currently an *engineering/observability* concern (don't overspend
on a run), not a *value-capture* concern (what does the platform sell, in what unit). With one tenant who
*is* the operator, cost-in-provider-dollars is exactly right — Peter pays the provider directly, the unit
is the bill. The need for an owned, durable, composable unit of account only appears when there are
*tenants who pay Arnold rather than the provider* — which is the success condition, not the present. So
the wrong unit is invisible precisely because the platform hasn't yet succeeded into the situation that
exposes it, and `cost_usd` *looks* like "we have cost handled."

**What it threatens.** The "AWS-of-agent-orchestration" endgame and the platform's ability to *capture*
the value it creates. A platform that meters in the supplier's floating currency cannot set its own
price, cannot guarantee a margin, cannot offer composable billing across shared pieces, and structurally
*loses revenue as it improves*. The migration is brutal once dependents exist: every receipt, every
composed-piece contract, every customer agreement is denominated in the wrong, un-re-derivable unit, and
there is no historical "Arnold-unit" measurement to backfill from raw provider dollars that no longer
mean what they did. The platform that should have owned the meter becomes a thin, margin-less pass-through
over the model providers — who then disintermediate it.

**Severity: reshapes-architecture** (it is foundational to value capture but the technical core can ship
without it; the cost is strategic foreclosure, not a crash — though it quietly *caps the company* at the
provider's margin).

---

## THE SINGLE BIGGEST ABSTRACTION WE HAVEN'T NAMED

### The **Warrant** — a per-action, signed, model-independent, durable record of *the authority and legitimacy under which an autonomous act was taken and what verified work it produced*: the atom of accountability and accounting, distinct from the artifact journal, the Effect Ledger, and the Manifest.

The sibling briefs named the nouns for *making the machine correct*: the Manifest (what produced it),
the Effect Ledger (how acts on the world are made safe), the Activation (the firing atom), the Contract
Ledger (the type system). All are *inward-facing* — they answer the engine's questions. **The 10-year
arc reveals a missing *outward-facing* atom: the unit by which the platform answers to, and charges, the
world outside it.** Call it the **Warrant**.

A Warrant binds, as one signed, append-only, model-independent record attached to every consequential
autonomous action:

- **the authority** — the *attested policy envelope* in force when the act was taken: the model
  allowlist, the spend ceiling and who granted it, the data-handling/taint rules, the human approvals
  obtained, the autonomy level permitted. Frozen and signed at the moment of action, **not** re-derived
  from a self-improving config later. This is the artifact a regulator/CISO/insurer/court is given as the
  *basis of legitimacy* (answers UU-2's accountability gap, which the Manifest's reproducibility cannot).
- **the account** — the work measured in a **durable, owned unit** (verified-work-units), decoupled from
  provider dollars, so value is composable across shared pieces and stable across model-price churn and
  across the self-improvement loop that keeps making the inputs cheaper (answers UU-3's unit-of-account
  gap).
- **the rationale anchor** — a human-readable, *captured-at-decision-time* (not replay-reconstructed)
  account of *why*, pinned to the Manifest hash that produced it — so "why did the system do X" has a
  stored answer that is not a fresh stochastic rationalization (answers UU-2's "the why is a model output"
  trap).
- **the shape-independence** — the Warrant is keyed to *an autonomous action and its verified result*,
  **not** to a P-E-V phase. A single-shot agentic action and a 200-turn emergent graph both produce
  Warrants of the same shape. This is the seam that lets the platform survive UU-1: when the frontier
  dissolves the phases, the unit of accountability and accounting *does not change*, because it was never
  defined in terms of plan/execute/verify in the first place.

Why this is the one to name now: the Manifest, Effect Ledger, and Activation make Arnold a *correct*
engine. The Warrant is what makes it a *platform the world can trust and pay* — the difference between
"a very good agent runtime" and "the OS for autonomous work." It is invisible today because the single
technical operator *is* the authority, *is* the payer, and *is* the one who knows why — so authority,
account, and rationale are all collapsed into one present human and never reified. Every success
condition of the vision (autonomous action without that human, tenants who pay Arnold, composed pieces,
regulated workloads) *splits* that human into three external parties who each need a durable artifact
Arnold does not currently emit. And critically, defining the Warrant in **action+verified-result** terms
rather than **phase** terms is the single decision that keeps the 2030 frontier from foreclosing the
platform: it is the abstraction that is *orthogonal to the model deficit P-E-V was built to compensate
for*, and therefore the one that survives the deficit's disappearance.

Name the Warrant now — as the unit the engine stamps on every consequential act, the unit the meter
counts, and the unit the auditor reads — and UU-1/2/3 become *design problems with a home*. Leave it
unnamed, and Arnold succeeds into being an un-certifiable, margin-less, phase-shaped pass-through over
model providers who own the unit, the trust, and ultimately the customer.

---

## Sources / grounding

- Read in-repo: `docs/pipeline-architecture.md`, `docs/resolution-contract.md`, `docs/canonical-vocabulary.md`
  (canonical plan states + slot/phase vocabulary that hard-wire P-E-V), `the-soul-irreplaceable.md`
  (cost recorded as `cost_usd`, open-loop calibration, weeks-half-life model index),
  `observability-eval.md` (determinism stops at model boundary), `versioning-identity.md` (Manifest =
  reproducibility), `durable-foundation.md` (Effect Ledger), `the-primitive.md` (Activation),
  `ai-authored-runtime.md` (Contract Ledger), `safe-composition-os.md` (declassification authority).
- Analogues reasoned from: AWS's billable-unit (instance-hour/GB-month) as the durable, churn-surviving
  unit of account that decoupled price from cost; the durable-execution field's hard-won split between
  the engineer-facing journal and the institution-facing audit/attestation record; the regulatory arc of
  every infrastructure that became load-bearing (the certifiability constraint arrives *after* adoption,
  not before).
