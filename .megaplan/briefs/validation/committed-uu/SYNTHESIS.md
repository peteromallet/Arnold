# Arnold — Committed Unknown-Unknowns Synthesis

**Frame:** We ARE building this. Full vision, category-creating platform. The commitment, the demand,
and the bet are SETTLED and off-limits. This document hunts only what will BITE US while building the
full vision RIGHT — the architectural, conceptual, computational, scaling, and emergent risks we cannot
currently see from inside a single-tenant, human-authored, single-process present.

14 vantages hunted independently. Their findings converge with startling consistency on a small number
of deep structural truths. That convergence is itself the strongest signal: when the OS lens, the PL
lens, the control-theory lens, the biology lens, the durable-systems lens, and the security lens all
point at the same hole from different directions, the hole is real and foundational.

The single most important meta-finding: **almost every risk is invisible for the same reason.** Today
there is exactly one author (us), exactly one tenant (megaplan), exactly one process, one provider-
preference, one model-set, and one human who is simultaneously the operator, the payer, the authority,
and the one who knows why. Every one of those "ones" is a load-bearing simplification that the success
condition of the vision *removes*. The platform doesn't fail when it's wrong; it fails when it
*succeeds* — when the second author, the second tenant, the first AI-emitted graph, the first long-lived
process, or the first untrusted web-fetch arrives. **We are building on assumptions that the win
invalidates.**

---

## Part 1 — Top Unknown-Unknowns, ranked by (invisibility × threat-to-the-build)

Ranked by the product of how blind we currently are to it and how much it threatens the full vision
succeeding. The top tier are could-sink-the-build risks that are *also* maximally invisible today.

### Tier S — could sink the build, and we cannot currently see it

1. **Self-improvement and durable replay are in direct tension at the primitive level — and we won't
   even detect the divergence.** (durable-foundation UU#1, ten-year-arc, emergent-dynamics)
   Durable-execution systems (Temporal/Restate/DBOS) earn "journaled / exactly-once / replay" by making
   orchestration *deterministic and frozen*. Arnold's entire value prop is orchestration that changes
   its mind — *the model is the control flow.* You cannot both journal the planner's output (frozen →
   never re-plans → defeats self-improvement) and let it branch live (re-invokes on replay → diverges
   from journal). Unlike Temporal, Arnold has **no command-history to diff against**, so it won't detect
   the divergence — every crash-resume silently either replays a stale plan as authoritative or
   re-plans into a different universe. **Both produce plausible-but-wrong results, the worst failure
   class, at the level of "which milestones even exist."** Invisible because we are importing the
   durable-execution *vocabulary* without importing the *constraint* that earned it.

2. **The eval ruler is an unattributed, unversioned float — a self-improving system that cannot version
   its own ruler does not improve; it drifts with confidence.** (observability-eval UU#1, emergent-
   dynamics UU#1, the-soul UU#1)
   A score has no recorded judge-model, rubric-version, judge-prompt, or input-set identity. "Did the
   new version beat the old?" is uncomputable as a trustworthy join — you cannot separate a real quality
   regression from a *measurement* regression. The optimizer and the evaluator share machinery, so the
   loop Goodharts: it converges on "plans the evaluator scores higher," not better plans. The divergence
   between internal score and external reality only appears over a *population* of runs that no test
   measures, because the suite *is* the evaluator. Invisible because the live-observability layer is so
   good it *feels* like the eval story is covered — but every observability surface answers "what
   happened," none answers "was it better, and can I trust the comparison." We are inside the loop we'd
   need to stand outside of.

3. **Side effects on the outside world obey laws content-hashing cannot touch — and we will conflate
   "the artifact is content-addressed" with "performing the act is idempotent."** (durable-foundation
   UU#2, integration-seams UU#2)
   Content-addressing makes *reads/derivations* idempotent (same inputs → same hash → cache hit). It
   does *nothing* for git merge/push, model spend, PR/CI emission. A pushed merge others branched from
   is a Saga *pivot* — a point of no return, not a free undo. A crash between model-API-return and
   journal-write means you **pay again** on replay with no provider-honored dedup key. The marquee
   selling point (resume-after-crash for the long-running/cloud tenant) is precisely where this bites.
   Invisible because content-hashing *lulls* us — "everything is content-addressed and journaled" feels
   like it confers idempotency on acts when it confers it only on artifacts. MEMORY's existing
   worktree-carry and execute-stall bugs are the foreshocks of this un-modeled effect layer.

4. **Taint must be propagating, executor-enforced, and inside the content-hash — but it is treated as
   after-the-fact audit metadata, so untrusted outputs launder into trusted positions.** (ai-authored
   UU#3, safe-composition UU#1/#3, adjacent-field UU#2)
   The whole economic thesis is *mixing* high-trust (frontier) and low-trust (cheap) outputs in one
   graph. Without taint as a propagating Port property the executor enforces at every edge, nothing
   stops a DeepSeek artifact from flowing into a slot whose correctness the router assumed a frontier
   model guaranteed. The LLM call is an **unauthorized declassifier** (tainted input → "clean" output)
   and the fan-out *reduce* node is a confused deputy (high authority, ingests low-trust externally-
   influenced content). Worse: if the label sits *beside* the value, two identical-byte values with
   different taint **collide to one hash** and dedup silently launders the tainted copy into the trusted
   one's provenance. Taint not propagated *at production time* is unrecoverable from hashes later,
   because the model call already merged and declassified. Invisible because today every stage is our
   own trusted Python — taint has never had to *gate* anything, so audit-provenance ("explains what
   happened") and enforcement-provenance ("prevents it") feel like one organ.

5. **The runtime validates only control-flow validity (edges resolve); model-emitted graphs are
   syntactically fine and semantically feral — and the runtime cannot reject what it has no type system
   to name.** (ai-authored UU#1, the-primitive UU#3, observability-eval UU#2)
   Humans don't emit semantically-incoherent graphs, so "valid = edges resolve" has never been wrong in
   practice. When the author becomes a model, the error distribution *inverts*: stage B consumes an
   output A never produced in B's shape; a loop has no decreasing measure so it can't terminate; two
   parallel stages write the same state key. There is no Port type system to reject any of this at
   admission, so it surfaces only by running — a crash, a non-terminating loop, or a silently-wrong
   artifact. "The runtime enforces invariants on untrusted generated graphs" is hollow if the runtime
   can only catch dangling edges. Invisible because we test the one graph we wrote, and the validator's
   shape becomes load-bearing everywhere before the author ever changes.

6. **Mutable single-document state is the architectural OPPOSITE of the journaled foundation — and the
   engine hides the contradiction by BANNING concurrency.** (the-primitive UU#2, adjacent-field UU#1,
   distributed-reality, integration-seams UU#3)
   Truth today is one destructively-overwritten `state.json` reconciled last-writer-wins;
   `events.ndjson` is a read-only narration *beside* it, not its source of truth. A journaled foundation
   means **state IS the fold of an append-only log** — the inverse of what exists. The executor
   *rejects* any parallel stage that touches shared state. The platform's answer to "concurrent
   activation is hard" is "don't do it where state is involved" — but markets, fan-out, emergent graphs,
   and standing processes ALL require concurrent shared-world mutation. It's a self-concealing pair: the
   data model's unsoundness is invisible exactly as long as concurrency is banned, and concurrency is
   banned exactly because the data model is unsound. We will believe the "foundation pillar" is in
   progress when the actual event-sourced substrate has never been built. Retrofitting it *after*
   tenants depend on `state.json` semantics is a quarter-eating migration that silently corrupts
   in-flight runs.

### Tier A — reshapes architecture, largely invisible from the single-tenant present

7. **Cheapest-capable routing is an optimizer with an attractor: it converges the whole fleet onto a
   model MONOCULTURE that fails in correlation, and content-hashing the prompt (not the weights) makes
   replay a lie.** (emergent-dynamics UU#2, the-soul UU#3, distributed-reality UU#1)
   Already empirically ~79–90% DeepSeek. One provider deprecates/reprices/silently re-tunes and *every*
   pipeline regresses at once. The hash keys on the prompt, not the remote weights — a model that
   changed behind a stable name produces a journal that says "same input, same route" while output
   silently shifted. The cheap model's systematic blind spot is inherited fleet-wide and **baked in by
   the self-improvement loop** because it was never penalized. Model-identity is not a hash-pinned
   provenance fact anywhere. Invisible because routing is reviewed as a per-run cost/correctness
   accounting question; correlated failure only exists across the fleet and across provider-time.

8. **No tree-scoped governor: every limiter is per-NODE, so an AI-emitted recursive graph is a fork bomb
   against shared keys, compute, and the bank account.** (emergent-dynamics UU#3, distributed-reality
   UU#4, cost-latency UU#3, adjacent-field UU#4, the-primitive UU#4)
   `CostTracker`, `StallDetector`, `ThreadPoolExecutor(max_workers)` are all local to one node. A child
   subloop runs under its own state so the parent cap can't see child spend — N levels each pass their
   local cap while the aggregate is unbounded. No global concurrency limit, no recursion-depth ceiling,
   no fan-out budget, no `--max-cost` that bounds the tree. Every governor was correct for the
   *bounded, human-authored* megaplan DAG and was never re-derived for emergent/recursive authorship.
   The biology lens sharpens it: there is **no conserved currency** (ATP) charged per-subgraph against a
   fixed pool, so a self-constructing graph has no thermodynamic stop — it expands until it hits an
   external wall (rate limit, wallet, crash). One bad emitted graph DoSes the shared substrate.

9. **Resume was designed for crash-recovery (short-horizon, same code) but the vision's standing/
   emergent/multi-week processes make it a long-horizon CROSS-VERSION operation against live, mutable
   definitions.** (versioning-identity UU#2, durable-foundation UU#3)
   Once processes live for days, the probability the underlying pipeline/piece/prompt was edited mid-run
   approaches 1. This produces **chimera runs** (stages 1–4 ran under behavioral hash H1, an edit lands,
   stages 5–8 run under H2), name-keyed resume re-entering a renamed-but-different-meaning stage, and
   state-shape drift merged blindly. The self-improving engine multiplies this on two axes: the engine
   improves, AND the AI-emitted definitions keep changing — and content-hashing pins the *graph
   definition* but **not the interpreter** (scheduler semantics, Port coercion, taint logic are
   self-improving code). Resume silently runs NEW interpreter semantics over an OLD graph. Invisible
   because "resume" still *sounds* like crash recovery.

10. **The calibration flywheel is a censored, biased, co-degrading loop that reads BETTER as quality
    rots.** (the-soul UU#1, emergent-dynamics UU#1, adjacent-field UU#3)
    Receipts record every (complexity, model, verdict, cost) tuple and are never read back. The naive
    close — lower the tier where the cheap model survived review — is positive feedback on a censored
    signal (no counterfactual for tasks we didn't route cheap) where the reviewer is often itself a
    cheap model ("survived review" can mean "two cheap models agreed"). A closed loop ratchets down:
    routing and the co-degrading reviewer both drift cheaper while pass-rate stays green and ground-
    truth rots. **Failure is indistinguishable from success on the dashboard we'd naturally build.**
    Compounded by churn: the model market reshuffles every few weeks, so the flywheel we count on to
    compound is the thing that decays fastest, and there is no capability-class transfer or staleness
    decay — calibration data has a half-life and we treat it as a monotonically growing asset.

11. **The cross-tenant verify-step corpus is the only irreplaceable asset — and multi-tenancy + taint +
    privacy fragment it into N sub-threshold puddles.** (the-soul UU#4)
    The copyable part is the algorithm; the irreplaceable part is the cross-domain corpus of "this
    shaped task, routed to this model, at this cost, survived/failed this verifier," which only WE sit
    downstream of because verify is the chokepoint every pipeline flows through. The heart's
    irreplaceability and the Port taint spine are in **direct tension**: tainted/private tenant data
    can't enter the shared corpus, so privacy-respecting tenants get worse routing and shrink the
    corpus. Invisible because we frame "keep the heart central" as an API/dependency-graph problem when
    the centrality that matters is **data gravity** — where verify receipts physically land and whether
    taint rules let them aggregate.

12. **Prompt caching (vendor-local, prefix-stable) and cheapest-capable routing (cross-provider) are
    physically antagonistic — optimizing one destroys the other.** (cost-latency UU#1/#2)
    The instant routing moves a logical piece across providers, all accumulated cache state is worthless
    and you re-pay full input cost. Worse, the pipeline path already injects per-run entropy
    (`<PLAN_DIR>/<PLAN_ID>`) into prompt prefixes, defeating even same-provider caching at the PEV heart.
    Nobody measures per-phase prefix-cache-hit-rate as a first-class metric, so its near-zero rate is
    invisible. At scale this is the difference between ~10× and ~100× input-token cost — not a percentage
    tax but the viability of the core economic claim.

### Tier B — worth designing for now; cheap to seed, expensive to retrofit

13. **No declassification/endorsement authority → pure taint propagation makes everything maximally
    tainted within a few hops and operators disable the checks.** (safe-composition UU#4) Every IFC
    system that shipped learned this. Arnold's natural declassifier is the VERIFY half of PEV — but PEV
    raises a *quality* score, not a *security* label. Shipping taint-without-declassification ends with
    it disabled: paying the cost of labels with none of the guarantee.

14. **Two disjoint journals already exist** (`events.ndjson` filesystem/presentation vs `epic_events`
    DB/content-hashed) with no shared schema, ID space, or join key — and surfaces re-derive truth
    heuristically at read time (`cost.py` classifies vendor by substring). "Thin readers over one
    journal" is already violated; if observability is the spine, two spines is no spine. (observability-
    eval UU#3, integration-seams UU#1)

15. **No portable adoption unit.** The megaplan run (state + journal + diff) is already the strongest
    viral artifact — ComfyUI-PNG + n8n-replay + HF-card fused — but it lives in a per-user scratch dir,
    privatized, with no stable id, no contract for rehydration, and no lineage edge for AI-scale
    remixing. We built the substance and skipped the naming. (adoption-artifact, all four UUs)

16. **No native unit of account.** We denominate value in the *provider's* floating dollars, after the
    fact — non-durable (can't compare 2026 to 2029), non-composable (can't bill A's pipeline to B), and
    measuring *inputs not work*, so a self-improving substrate that gets cheaper **destroys its own
    revenue.** (ten-year-arc UU#3)

17. **No model-independent answerability layer.** Observability lets an engineer introspect; it does not
    give a regulator/CISO/insurer a frozen, signed policy envelope under which an autonomous act was
    *permitted*, plus a captured-at-decision-time "why" (the journal's "why" is a stochastic completion
    that re-rationalizes on replay). The certifiable competitor wins the enterprise endgame. (ten-year-
    arc UU#2)

---

## Part 2 — Abstractions we have not yet named (the deep nouns)

Every vantage independently reached for a missing first-class object. Strikingly, these are not 14
different nouns — they are **facets of a small number of deep abstractions**, each of which is currently
implemented zero-to-N times as ad-hoc side-channels. Naming them now is the single highest-leverage move
available, because each unnamed noun is otherwise built three-to-five times inconsistently, bolted onto
an executor designed when the author was always human and always trusted.

### The two spine-peers the vision already half-knows

- **Port** — named in the vision (type+version+provenance+taint), governs safe composition of DATA in
  SPACE: "is this connection safe right now?" Mostly aspirational in code.
- **The Activation** *(the-primitive)* — the missing PEER of the graph: a first-class, persisted,
  supervised record of *a node firing*, carrying a **pluggable readiness rule** and a **lifecycle**.
  Today "a step running" is an implicit, transient program-counter-plus-thread with no identity, no
  persisted lifecycle, no readiness rule beyond "the previous edge matched," and no supervisor. The
  readiness *predicate* is the real primitive; the graph is just the common case where readiness =
  "upstream done." DAG / fixpoint / standing-process / market / emergent all become *one* field, not a
  mush of incompatible Step kinds. Subsumes the content-hashed foundation (identity = hash over node +
  input Ports + profile), supervision (BEAM/OTP lifecycle), and journal-native state (transitions ARE
  the events; `state.json` becomes a derived cache).

### The carriers — what flows and what governs

- **The Conveyance / Work-Envelope / The Reduction** *(safe-composition + integration-seams +
  adjacent-field converge on ONE noun).* The single most-converged-upon missing abstraction. Port is the
  *spatial* half (the envelope on a value crossing a data boundary). The unnamed *temporal* half is the
  **conserved run-context that rides every edge through dispatch, retry, cancellation, cost accrual, and
  the journal**, carrying identity + lineage + taint(as a *lattice*, joined at every merge, with per-Step
  transfer functions) + cost-ledger + deadline + cancellation-token + error-class + retry-budget. They
  are two faces of one law: **nothing crosses a seam — spatial or temporal — naked.** Type, provenance,
  taint, cost, and cancellation are CONSERVED QUANTITIES the runtime must make impossible to drop. Today
  the platform runs two parallel languages — the typed edge/verdict language and an untyped
  string/state-dict language everything cross-cutting actually speaks — with only a lossy translation
  between them.

- **The Governor / Homeostat** *(emergent-dynamics + distributed-reality).* The PEER of Port for safety
  in DYNAMICS rather than space: "is this LOOP STABLE?" / "is this RECURSION TREE bounded?" /
  "is this fair across tenants?" A tree-scoped resource/recursion budget AI-emitted topologies are
  admitted against; an exogenous (non-self) fitness oracle the self-improvement loop must close against;
  read-side taint+decay on journal memory; model-identity provenance so routing diversity and replay
  determinism are even *expressible*. Its distributed face is the **Capacity Lease** — one linearizable
  cross-tenant arbiter of every contended resource (provider rate-limit, fan-out width, dollars,
  worktrees), with fencing tokens (not wall clocks) so a stolen/expired lease fails its NEXT WRITE.
  Port is the spine; Governor is the nervous system that keeps the spine from convulsing.

### The ledgers — what we must record to be a platform, not a process

- **The Effect Ledger** *(durable-foundation).* The dual of the Port, governing safe composition of
  ACTS on the outside world. Every world-facing act is a typed Effect carrying: a **replay-class**
  (pure | idempotent-keyed | at-most-once journal-before-execute | pivot/irreversible); an explicit
  **external-system-honored idempotency key** distinct from the content hash (hash dedups the *artifact*,
  key dedups the *act*); a declared **compensation** (refund/void/release/revert) or an explicit
  noncompensable marker forcing the planner to route *around* needing undo; and provenance+taint on the
  same spine.

- **The Contract Ledger** *(ai-authored).* The TYPE SYSTEM, not the type — a machine-checkable,
  versioned, content-hashed registry of Port contracts and the *legal moves between them*, that is
  simultaneously (a) the admission validator a model reads to emit valid-by-construction graphs, (b) the
  repair-negotiation surface (structured machine-readable rejection — "B expects plan@v2, A emits
  plan@v1, legal moves are X,Y" — turning a halt into a gradient an optimizer can climb), (c) the
  taint/provenance propagation rule the executor enforces and that is *part of the cache key*, and (d)
  the harness-independent pinned Port meaning the self-improvement optimizer cannot quietly redefine.

- **The Calibration Ledger** *(the-soul).* A first-class, content-hashed, append-only record of
  **CapabilityClaims and their adjudicated outcomes** — {typed domain-tagged task-signature,
  predicted-tier, routed-model, verifier-identity-and-tier, verdict, cost, counterfactual-tag,
  timestamp} — with three primitive operations: DECAY & CHURN (observations age; new models seed from a
  capability-class prior, not cold-start), EXPLORATION BUDGET (a fraction of routing is deliberately
  off-policy so the loop can't ratchet, with the cost-pressured reviewer never trusted as ground truth),
  and TAINT-AWARE AGGREGATION (Port taint governs which claims enter the SHARED ledger vs stay tenant-
  local, making the privacy↔flywheel trade explicit). The 1–5 difficulty score, the cross-vendor
  equivalence table, and `tier_models` become *projections* of the Ledger; routing becomes a query, not
  a TOML read.

- **The Evaluand + the (single) Ledger** *(observability-eval).* A versioned, attributable judgment
  record — "this judgment, by this judge-version, against this rubric-version, over this input-set,
  produced this score, recorded here, joinable to that one" — recorded into ONE content-addressed
  observation log at run/piece/port grain that every surface READS and nothing recomputes. Turns "is the
  new version better?" from a vibe over floats into a join over hashed identities. A judge becomes a
  Port-typed, content-hashed, versioned *piece* (eval-as-pipeline-kind); a rubric change is a visible
  version bump, not a silent meaning-shift. For a self-improving heart, **this is not a feature of the
  spine; it IS the spine.**

### The identity and the outward-facing atoms

- **The Behavioral Identity Manifest (the pipeline "genome").** Content-hashing today points at OUTPUTS
  and the unit of identity is a NAME. The Manifest hashes the **closure of everything that determines
  what a composed artifact DOES**: graph topology + Step *code* hashes (not class names) + resolved
  prompt *bodies* (text, not keys — closing the global-registry leak) + the model-routing decision
  *actually taken* (so cheapest-model drift is a recorded version event, not hidden) + the invariant/Port
  set + the SDK/ABI version authored-against + the resolved dependency closure (exact P@hash of every
  composed piece, making diamonds detectable instead of last-writer-wins). With it, reproducibility =
  re-run Manifest H; resume = "pinned to H, live def is H′, policy = pin/refuse/migrate-via-codemod";
  behavioral semver = a mechanical Manifest-diff. **The Manifest is the noun the content-hashed
  foundation was built to hash but is currently pointing at the wrong object.**

- **The Replayable Capsule** *(adoption-artifact).* The first-class, portable unit of EXCHANGE and
  identity — Definition (Port-graph + intent + routing) + Contract (the declared world it needs:
  repo@commit, model/tool versions, required-secrets-by-shape, Port input types — the Port spine
  *exported* as a recipient-verifiable manifest checked BEFORE running, refusing-or-adapting *loudly*) +
  Lineage (immutable parent edges so AI-scale remix accretes a genealogy instead of a flat soup) +
  Evidence (journaled events + diff + verify trail + cost, renderable as a *story* for a cold recipient).
  We already emit ~80% of the bytes; we skipped naming the capsule. Registry, inspector, and fork-with-
  back-edge fall out as operations on it.

- **The Warrant** *(ten-year-arc).* The OUTWARD-facing atom — a per-action, signed, model-independent,
  durable record of the AUTHORITY under which an autonomous act was taken AND the verified work it
  produced. Binds: AUTHORITY (the frozen-and-signed policy envelope at action-time — model allowlist,
  spend ceiling + who granted it, data/taint rules, approvals, autonomy level — the artifact a regulator
  is handed); ACCOUNT (work in a durable OWNED unit, verified-work-units, decoupled from provider dollars
  and stable across the self-improvement loop); RATIONALE ANCHOR (a captured-*at-decision-time*, not
  replay-reconstructed, "why," pinned to the Manifest hash); and **SHAPE-INDEPENDENCE** (keyed to an
  autonomous ACTION + VERIFIED RESULT, NOT to a P-E-V phase — so a single-shot agentic action and a
  200-turn emergent graph produce Warrants of identical shape, the one property that keeps the 2030
  frontier from foreclosing the platform).

**The relationship between the nouns:** Activation (the firing atom) carries a Conveyance/Envelope (the
conserved context) across Ports (the data sockets), governed by the Governor (the dynamics regulator),
recording typed Effects into the Effect Ledger, validated against the Contract Ledger, judged into the
Evaluand/Ledger and Calibration Ledger, fingerprinted by the Manifest, packaged as a Capsule, and
attested by a Warrant. They are not 11 features; they are the organs of one body the vision implies and
the code has only in embryo.

---

## Part 3 — Architecture-reshapers (findings that change foundation / primitive / spine)

These are the findings where the *right answer changes the shape of the foundation itself* — building
them last means re-touching every edge, every cache entry, every receipt, and silently corrupting
in-flight runs during migration.

1. **State must become a deterministic fold over an append-only, effect-typed, taint-carrying event log
   — the dependency arrow currently points the wrong way.** `state.json` is the racy authority;
   `events.ndjson` is optional telemetry. The OS lens is unambiguous: the WAL is authoritative, live
   structures are a rebuildable cache. Then resume = replay, the mid-write-corruption class disappears,
   and concurrent writers stop racing the authoritative file. This is the foundation everything else
   stands on. **Reshaper #1; everything below assumes it.**

2. **The Activation (pluggable readiness rule + lifecycle/supervisor), not the graph shape, is the
   scheduler primitive.** A sequential DAG walker cannot host loop/standing/market/emergent as peers;
   it becomes a switch-statement mush over incompatible firing semantics (the reserved-inert `subloop`
   and `override` Step kinds are the first two pegs already hammered in; the hardcoded
   `max_blocked_retries=1` bug IS the missing fixpoint semantics surfacing). Name the Activation now,
   while the only readiness rule is "upstream done"; retrofit it after the second tenant and it is a
   foundation-replacement under load.

3. **Port = type+version+provenance+taint must be RUNTIME-ENFORCED, with taint as a propagating lattice
   inside the content-hash and a typed declassification edge.** The runtime's only output invariant
   today is `Path.exists()`. Without Ports as an enforced type, "the runtime enforces invariants on
   AI-authored topologies" is unbacked and the routing thesis has no safety story. Taint not propagated
   at production time is unrecoverable. **Must be in the Port from day one or it is unachievable.**

4. **A tree-scoped Governor + linearizable Capacity-Lease arbiter must sit under the scheduler and over
   the key pool, before topologies stop being hand-written.** The `KeyPool` is a scheduler for a
   contended global resource mis-scoped as a process-local singleton (fan-out workers all pick the same
   LRU key and stampede it in lockstep; cooldowns in process A are invisible to B). FileStore execution
   leases are a non-atomic read-then-write that double-grants over a shared volume under clock skew —
   directly breaking single-writer-per-plan. The fix requires a resource-accounting + admission-control
   layer the primitive surface has no place for.

5. **One Ledger, recorded-into and never recomputed-from, at run/piece/port grain, spanning plans/epics/
   standing/emergent processes.** Two disjoint journals + read-time substring vendor classification = no
   spine. Lineage must be EMITTED by the runtime as Ports are crossed (read off the Port's provenance
   field), not reconstructed by a phase-name if-ladder that is silently wrong for every AI-emitted graph.
   The Ledger must record hashed, re-injectable model I/O keyed by (prompt_hash, model_version, params)
   so the past stays re-evaluable when models drift behind stable names.

6. **The Manifest must be the object the content-hash points at — the behavioral closure, not the
   output file.** Pin it to every run and reproducibility/resume/diamond-resolution/behavioral-semver
   all collapse from emergent hell into "a manifest diff plus a resolution policy." The dead
   `pipeline_version: int` field is the tell that we think identity is handled when an integer cannot
   fingerprint a continuously self-modifying behavioral closure.

7. **Model-identity must be a hash-pinned provenance fact, not an assumed constant.** Content-hashing
   the prompt while the weights drift behind a stable name makes "deterministic auditable replay" a lie
   and bakes the cheap model's blind spot fleet-wide. This is a single-point-of-failure dressed as a
   distributed system, and it touches the cache key, the journal, and the routing telemetry.

8. **The Run/Composition transaction boundary must wrap multiple stores.** `durable+journaled+content-
   hashed` is true per-store and false across the composition; a crash between stages leaves state
   advanced, receipt written, DB possibly not, with no enclosing unit of work to roll all three back.
   Open/close `Store.transaction()` ON the Envelope so durability is a property of the RUN, not of each
   store in isolation.

---

## Part 4 — What we'll wish we'd known

- **That the win, not the bug, is what breaks us.** Every assumption that makes today simple — one
  author, one tenant, one process, one model-preference, one human-who-is-everything — is removed by the
  success condition. We will wish we'd built for the second of everything from the first.

- **That "content-addressed and journaled" was a half-truth we let ourselves believe was the whole
  foundation.** It confers idempotency on artifacts/reads, never on acts/effects; it dedups storage,
  never bounds replay-chain length; it pins the prompt, never the weights; it pins the graph definition,
  never the interpreter that walks it; it gives integrity, never genealogy. Four separate vantages
  independently caught us conflating the half with the whole.

- **That self-improvement and durability/accountability/reproducibility are in structural tension, not
  harmony.** The faster Arnold improves, the more divergent the universe a paused run wakes into; the
  more it rewrites its own rules, the less it can attest "these were the rules in force"; the better its
  routing gets, the less revenue it earns per unit of delivered work. These tensions are designable but
  only if named up front; un-named they surface as "mysterious" production failures years apart.

- **That P-E-V is a COMPENSATION for a 2026 model deficit, not a law — and we hard-wired it into the
  state machine, slot vocabulary, prompt keys, receipt schema, and billing grain.** The frontier runs
  straight at that deficit. The self-improvement loop optimizes the harness toward being a *better
  phased planner* — accelerating in the direction the frontier makes obsolete. Anchoring accountability
  and accounting to ACTIONS + VERIFIED RESULTS (shape-independent) rather than phases is the one decision
  that keeps the great 2030 version reachable.

- **That the irreplaceable asset is DATA GRAVITY at the verify chokepoint, and the safe-composition spine
  is in direct tension with it.** We will wish we'd designed the privacy↔flywheel trade as an explicit,
  tunable knob (taint-aware aggregation) instead of letting multi-tenancy emergently shatter the corpus.

- **That "frozen at end of Sprint 1" was a sprint-local promise read as a permanent guarantee.** A
  platform's SDK/ABI evolves forever and every artifact ever authored carries a lifetime compatibility
  obligation. Author-time-SDK vs run-time-SDK skew is zero today and grows monotonically forever; the
  dogfood-engine-shadow MEMORY entry is the first instance already recorded.

- **That the most viral object in the whole vision was sitting in a scratch directory the whole time.**
  We built the Capsule's substance (state + journal + diff) as engine machinery and never made it the
  unit of exchange, identity, and trust.

---

## Part 5 — Design principles to adopt NOW (so early decisions don't foreclose the great version)

These are not "build everything now." Most of the deep nouns can be *seeded* cheaply today — a typed
field, a recorded fact, a no-op enforcement hook — while there is one author and one tenant, and that
seed is worth orders of magnitude more than the full build is later, because retrofitting touches every
edge under load.

1. **State is a fold over an append-only log; the log is the truth, the document is a cache.** Make this
   the foundation now, before tenants depend on `state.json` semantics. This single decision dissolves
   the mid-write-corruption class, makes resume = replay, and unbans concurrency.

2. **Nothing crosses a seam naked.** Every value crossing a Port and every unit crossing a dispatch/
   retry/cancel/cost boundary carries a typed, conserved context (the Conveyance/Envelope). Type,
   provenance, taint, cost, deadline, cancellation, retry-budget are CONSERVED QUANTITIES the runtime
   makes impossible to drop. Concretely: `StepContext`/`StepResult` carry a typed `RunEnvelope` instead
   of leaking cost/error/lineage/cancel through `state.json` and `repr(exc)`.

3. **Distinguish artifact-identity from act-identity from behavioral-identity from model-identity — four
   hashes, not one string.** The content hash dedups artifacts; the idempotency key dedups acts; the
   Manifest fingerprints behavior; model-version pins the weights. Collapsing them is the root of the
   replay-is-a-lie and double-charge failure classes.

4. **Taint propagates, is enforced at every edge by the executor, lives INSIDE the content-hash, and is
   lowered only by a principalled declassifier (the PEV verifier).** Seed the lattice and the no-op
   propagation hook now; the cache-collision-launders-taint failure cannot be retrofitted after untrusted
   content shares the store.

5. **Make rejection negotiable, not terminal.** A model author needs structured, machine-readable
   rejection it can repair against in a bounded loop ("B expects plan@v2, A emits plan@v1, legal moves
   are X,Y") plus a runtime that offers the legal moves. Reject-only gives the optimizer no gradient and
   puts a human back in the loop on every malformed graph.

6. **Every self-improving loop closes against an EXOGENOUS reference signal the loop is forbidden to
   touch, with verifier identity recorded and an exploration budget that keeps the signal un-censored.**
   No metric the loop optimizes may also be the metric the loop is judged by. The optimizer and the
   evaluator must not share machinery. This is the anti-Goodhart spine of "self-improving."

7. **The judge is a versioned, attributable, content-hashed piece; the score is a join over (piece-
   version × rubric-version × judge-version × input-set), never a bare float.** A system that cannot
   version its own ruler cannot prove it improved.

8. **Every limit is tree-scoped against a conserved budget held by a named principal.** No per-node
   governor is admitted as sufficient. AI-emitted topologies are admitted against a recursion-depth,
   fan-out, dollar, and concurrency budget charged per-subgraph against a fixed pool. There is a global,
   linearizable arbiter (Capacity Lease, fencing tokens) for every contended resource, and the human
   operator is no longer the implicit governor.

9. **Resume is version-aware, not a name lookup.** Pin every run to its Manifest hash; resume policy is
   pin / refuse / migrate-via-codemod against the live definition. Records carry the SDK/ABI version
   authored-against; orphaned pieces leave tombstones so the journal stays replayable.

10. **Record world-facing acts as typed Effects with replay-class, external idempotency key, and declared
    compensation — before the first real money/merge/PR is journaled.** Pure derivations are free;
    everything else must declare how it survives replay and how it is undone (or that it cannot be).

11. **Anchor accountability and accounting to ACTIONS + VERIFIED RESULTS, not to P-E-V phases.** Keep the
    phase machinery as one *implementation* of an action, not as the spine. This is the cheap decision
    today that keeps the platform from being a phase-shaped pass-through when the frontier erases the
    deficit P-E-V compensates for. Seed a Warrant skeleton (authority envelope + verified-work-unit +
    decision-time rationale anchor) now, while the human is still authority+payer+rationale, so the
    fields exist when those three split into external parties.

12. **The unit of exchange is a first-class Capsule with an exported, recipient-verifiable contract that
    refuses-or-adapts LOUDLY — silence on rehydration is forbidden.** The harness's existing instinct to
    degrade silently (silent OpenRouter routing, TIEBREAKER→ITERATE auto-downgrade) is the single most
    dangerous habit for trust-on-first-contact and must be inverted into fail-loud everywhere a contract
    is unmet.

13. **Treat the journal as a feedback channel with memory, not a write-only audit log.** Read-side taint,
    decay/freshness, and quarantine on journaled memory; "durable" must NOT mean "unconditionally
    authoritative." Immutability is a feature for integrity and a bug for correction — design the
    governance that reconciles them.

14. **Measure the things that are invisible at single-tenant scale, now, as first-class metrics:**
    per-phase prefix-cache-hit-rate; model-diversity/monoculture index; tree-aggregate spend;
    routing-counterfactual coverage; judge-vs-ground-truth divergence over a population. You cannot
    govern variety you cannot sense (Ashby); the sensors must exist before the regime that needs them.

---

## Closing

The vision is coherent and the substance is real — Arnold already emits ~80% of the bytes of a Capsule,
has a journal in embryo, a Port in prose, a cost meter, and a routing engine. The danger is not that the
pieces are missing; it is that **they are each implemented once, locally-correct, for the one regime that
the success condition removes** — and that the durable-execution and content-addressing vocabulary we've
adopted *feels* like it confers guarantees it does not. The deepest single move is to recognize that
state must be a fold over a typed, conserved, journaled event log, and that everything crossing a seam —
spatial (Port) or temporal (Envelope) — carries conserved quantities the runtime makes impossible to
drop. Name the deep nouns now, seed them while there is one author, and the dozen "mysterious production
outages years apart" collapse into a handful of design problems with a home. Leave them unnamed and we
will re-derive each — as Step kinds, retry counters, orphan janitors, idle timers, merge reconcilers,
and substring classifiers — the exact trajectory the MEMORY log already shows in miniature.
