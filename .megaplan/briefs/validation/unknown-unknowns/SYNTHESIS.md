# Unknown-Unknowns Swarm — Synthesis

**Date:** 2026-05-29
**Inputs:** 14 outside-the-frame vantages (agent-framework-landscape, durable-workflow-engines,
node-graph-ecosystems, plugin-ecosystem-patterns, substrate-assumption, primitive-assumption,
demand-reality, moat-and-value-capture, builder-lifecycle-negative-space, multi-user-org-production,
ai-eats-the-frame, economics, abuse-supply-chain, maintenance-opportunity-cost)
**Job:** Attack the epic's frame from outside. The frame under attack:

> Arnold is a Python, in-process, single-repo SDK of composable pieces that *other developers* compose
> into *pipelines* to build LLM-agent tools. Planning (megaplan) becomes one module among many. Success =
> an external builder ships a new module cheaply. The value is composability. The unit is a pipeline. It
> runs where megaplan runs today.

The point of this document is the thing we did not want to hear. Read it adversarially.

---

## The one-sentence finding

**The epic is organized around the only axis with no remaining margin (composability) and gives away,
relabels as "example #3," or never builds the four things that are actually scarce and defensible:
(1) the hardened, self-improving Plan-Execute-Verify harness, (2) the cheapest-capable-model routing
*calibration* earned on real invoices, (3) the operating-time disciplines — durable execution, attribution,
audit, safe composition — that production teams pay for and get locked into, and (4) any evidence that a
second builder exists at all.** Eleven of fourteen independent vantages converged on a version of this from
mutually-unaware starting points. That convergence is itself the loudest signal.

---

## 1. Top unknown-unknowns, ranked by (invisibility × plan-impact)

Ranking is `how-structurally-blind-were-we × how-much-would-it-change-the-plan`. The top tier are findings
no prior pass *could* have surfaced (the premise that hid them was an axiom in sentence one) AND that, if
true, rewrite the roadmap rather than tweak a milestone.

### Tier 1 — would invalidate or invert the epic (highest invisibility × impact)

1. **The second builder is imaginary; N=0 (demand-reality).**
   `git log megaplan/pipelines/` = 7 commits, 100% Peter. Every pack is Peter-only. The "second seed app"
   `resident` (4,201 LOC, all Peter) doesn't even compose the SDK — it imports megaplan as an ordinary
   library. The entire external-builder half of the program (trust boundary, multi-tenancy, SemVer surface,
   supervisor tier, public docs) serves a user who has never appeared in the repo's record. **Invisibility:
   maximal** — this premise was never given an evidence doc *because it was the frame every other evidence
   doc was commissioned inside*; the person who authored the aspiration is the person whose behavior
   falsifies it and who commissioned the validation. **Impact:** cuts ~40-50% of the epic.

2. **We are giving away the moat as "example #3" (moat-and-value-capture + maintenance).**
   The scarce, dogfooded-on-real-money asset is the *judgment layer*: finalize 1-5 difficulty scoring,
   difficulty→cheapest-capable-model routing, rater≥dispatchee guarantees, tier maps, robustness presets,
   critique-lens selection. M6/M7 deliberately demote this to "planning content" and elevate commodity
   pieces to "the product." M7's acceptance test literally requires a builder to grep-prove **zero** planning
   vocabulary — i.e. it certifies how completely we extracted and gave away the moat. **Invisibility: high**
   — the "would an unrelated builder want this?" discipline test is a moat-destruction machine: it routes
   everything *reusable* into the free SDK and everything *defensible* into "just app content," and cannot
   perceive that the clean-abstraction layer IS the commodity. **Impact:** inverts what is product vs. example.

3. **Megaplan is the product; the node SDK is the commodity (agent-framework-landscape).**
   The plan→critique→execute→review loop is an independent re-derivation of the industry-named
   **Plan-Execute-Verify / harness-engineering** pattern, a benchmarked field with a self-evolving frontier
   (Live-SWE-agent, 77.4% SWE-bench, harness adapts from failure). Megaplan is a battle-hardened PEV harness
   with rare production scar tissue (stall detection, idle backstops, chain resume, gate tiebreakers, cost
   tiering). The frame dissolves our single most market-recognized-as-hard asset and relabels it a generic
   example app. **Invisibility: high** — every pass treated megaplan as the incumbent to generalize *away*
   from, so "make it one module" felt like progress. **Impact:** invert the epic — harness is headline,
   composition is plumbing.

4. **The substrate the field already rejected (durable-workflow-engines + multi-user-org-production).**
   In-process / single-repo / `.megaplan` state dir is single-WRITER by physics and the exact architecture
   Temporal, Airflow, Prefect, LangGraph all *abandoned* (they rewrote onto transactional row-owned stores)
   because file+lock state cannot be made multi-tenant-safe, crash-survivable, or versioned by adding
   features on top. The named failure — "an agent halfway through a loop loses all intermediate work on
   failure" — is our architecture and our exact multi-day epic workload. "Runs where megaplan runs today"
   was carried in as a *constraint to preserve*, never a *decision to defend*. **Impact:** durable execution
   must be core (own it or rent Temporal/Inngest), or name the single-player ceiling explicitly.

5. **The typed-Port artifact bus is a prompt-injection bus with a schema (abuse-supply-chain, UU-1).**
   The M2 keystone — typed Port + StateDelta + shared Store — is the existential finding because it **fires
   with zero malicious modules**. Any benign ingest piece that faithfully fetches a poisoned web page / GitHub
   issue writes a well-formed `Port[PlanDraft]` whose *content* is adversarial instruction; a downstream
   gate/produce node reads it as *trusted, validated* structured context and acts on it. The typing makes it
   worse — it signals "trust this," which is exactly the disarming the injection wants. **Invisibility:
   maximal** — security was framed as untrusted-CODE-loading (M6) while the Port type system was designed by
   the composability frame (M2); the two mental models never met. Interrogation even flagged the type-erasure
   into state_patch as a *correctness* bug, never a security one. **Impact:** the Port needs a 4th axis
   (provenance + taint); structural change to the keystone, not a bolt-on.

### Tier 2 — would reshape major milestones (high invisibility, large local impact)

6. **The missing primitive is a scheduler, not select+reduce (primitive-assumption).**
   Three of the epic's own five stress cases (constraint solver, bounty market, genetic tournament) are not
   topologies — they are **control regimes** (fixpoint-until-quiescent, market-clearing, selection). What
   bent the SDK was that each needs a *scheduler* (what fires next when there's no authored next) that a
   DAG-or-loop cannot express. "Add select + structured reduce" fixes the wrong layer; the real gap is a
   pluggable activation policy one level down. The realized-graph (ordered rewrite fold) *assumes* a
   determinable order exists to project — fixpoint/clearing/selection have none.

7. **The unit is the shareable RUNNABLE artifact, not the composable piece (node-graph + plugin + lifecycle).**
   ComfyUI's growth = workflow-in-a-PNG + one-click 3,000-node install; n8n's = 6,000 remixable templates +
   click-into-any-past-execution inspector. Max/MSP stayed niche with *identical* node expressiveness for
   lacking exactly the share/remix/registry/inspect layer. We treat the megaplan run (state + events + diff)
   — a near-perfect shareable artifact — as private internal state. The KPI should be *time-to-first-re-run
   of a stranger's shared pipeline+result*; none of registry, export format, provenance embedding, or
   builder-facing replay/inspect is scoped. (Builder-lifecycle: replay was BUILT then withheld as a CI-only
   oracle — promote it to a builder-facing debugger.)

8. **No upgrade / dependency / debug lifecycle (builder-lifecycle-negative-space).**
   The epic models `author` + a static checkpoint. The real lifecycle is author→test→debug→version→depend→
   distribute→upgrade→support. There is no inter-module dependency edge (module B cannot depend on module A),
   no `arnold test`/fixture format (validation checks STRUCTURE never BEHAVIOR), no codemod/compat window
   (version mismatch just refuses, and discovery *silently swallows* import errors so breaks fail invisibly),
   no debug/inspect loop for a live composition. M5c's STATE_* eviction is exactly the breaking change that
   orphans every external module post-launch with no carry-across.

9. **Economics is the control plane, not a max_cost scalar (economics — 4 faces).**
   (a) Dogfood economics rest on a billing arbitrage external builders can't inherit — Shannon drives Claude
   on a flat-rate OAuth seat (~$0/turn); a builder's fan_out of N Claude judges either serializes through one
   rate-limited seat or flips to metered API billing. (b) fan_out/compete are O(N) spend, ~O(log N) value
   (same-base-model panels are heavily correlated); nothing prices this. (c) No billing principal — "whose
   key/seat/budget" is undefined once tenants are real. (d) The idiomatic style (many stateless one-shots) is
   **cache-hostile** — it defeats prompt-cache hit rate, the single biggest cost lever. We costed the system
   we run, not the system we ship.

10. **AI authors the pipelines; the human-builder population is shrinking (ai-eats-the-frame).**
    The flagship verb (critique_revise_gate_loop) externalizes a verify-retry loop that test-time-compute
    models now run *better internally* — the most-hardened chunk of the epic is depreciating. M7 (docs for a
    *human* author) is insurance on a shrinking population; an *agent* author needs a machine-checkable schema
    + fast validator, not authoring prose. M6's package-registry trust becomes per-run ephemeral-sandbox of
    machine-emitted graphs. The durable value is the *invariants the runtime enforces* on whatever gets
    emitted, not a library of verbs.

### Tier 3 — worth knowing (lower impact or already partly visible)

11. **Composition is a control-plane concern; the honest substrate is a daemon (substrate-assumption).**
    Pause/resume, human-gate, mid-run robustness change, supervision are always-on-orchestrator behaviors;
    a library has no in-flight identity to receive a pause. Natural artifact: an `arnold-serve` daemon, not
    in-process function pointers.

12. **The reusable asset is the dispatch *wire contract*, not the verbs (substrate-assumption).**
    Verbs are cheap to clone; the dispatch protocol (streaming, cost, heartbeat, stall-detection, key-pool,
    cancellation) is months of work — and a Python import traps the hard part behind a call stack a Rust/TS/Go
    builder can't reach. The honest fourth-thing test is a fourth thing in *another language*.

13. **Replay is a lie for agents that mutate a repo (durable-workflow-engines).**
    You cannot journal-and-replay a git merge. Resume must mean "re-derive which side effects already landed,
    skip them, compensate partials" (idempotency keys + Sagas), not "re-invoke the realized graph."

14. **The contract-checker is a quality GATE that suppresses ecosystem size (plugin-ecosystem-patterns).**
    HACS thrived on integrations that *couldn't* meet core's bar; the dead ecosystems (Roam) were the
    closed single-blessed-path ones. A mandatory blessing gate caps the network at core-team review bandwidth.

15. **Open-sourcing the robustness layer arms your disintermediators (moat-and-value-capture).**
    The parties who most want "make routing-to-cheap SAFE," turnkey, are cheap-model providers
    (DeepSeek/Kimi) and aggregators (OpenRouter) — who win every redirected token and have a billion users of
    distribution. Naive-MIT for the whole stack is the highest-disintermediation-risk choice available.

---

## 2. Premise-threats — findings that, if true, INVALIDATE or REDIRECT the epic

These are the brave ones. Each names a load-bearing premise and the finding that breaks it.

| # | Premise (epic axiom) | Threat (if true) | Verdict |
|---|---|---|---|
| PT-1 | *"Other people compose pipelines" — a second builder exists.* | **N=0. The only builder is Peter, who consolidates his own code — which every codebase already permits.** Half the epic serves a user the repo's own record says is imaginary. | **Invalidates** the external half. |
| PT-2 | *"The value is composability."* | **Composability is the one commoditized axis (8+ incumbents; the frontier is *retreating* from DAGs toward plain-code 12-factor + MCP protocol + DSPy compilation). The moat is observability/eval/durable-execution + the routing calibration — all out-of-frame.** | **Redirects** the center of gravity. |
| PT-3 | *"Megaplan becomes one module among many."* | **Megaplan IS the product (a hardened PEV harness with rare scar tissue); the SDK is the commodity. Demoting it to a sample app destroys the only real-money credibility asset and invites "wire it yourself."** | **Inverts** product vs. example. |
| PT-4 | *"It runs where megaplan runs today (in-process, .megaplan dir)."* | **That substrate is single-writer by physics and the exact architecture every durable-execution engine abandoned. The first multi-week epic spanning an SDK upgrade resumes into a different universe / corrupts a repo with a half-applied non-idempotent side effect / can't be audited.** | **Redirects** the substrate decision. |
| PT-5 | *"The unit is a pipeline (DAG or loop)."* | **(a) The highest-value agent tools are standing/interactive processes with no terminal state — Arnold's run-outcome vocab enumerates only ways to STOP. (b) The era's leverage is NOT pre-committing to a graph (ReAct/blackboard: the graph IS the emergent output). (c) The real gap is a scheduler, not node types.** | **Reshapes** the primitive. |
| PT-6 | *"Builders are developers (compose pieces in code)."* | **Every breakout this cycle moved topology OFF code into LLM-/GUI-editable DATA (n8n, Dify, Flowise, Langflow). The typed-Port keystone *deepens* code-centricity at the exact moment leverage moved to "the workflow is data the model authors." The just-deleted yaml-pipelines layer may have been the right surface.** | **Reshapes** authoring modality. |
| PT-7 | *"Composability is the value (and trust = M6 add-on)."* | **The typed artifact bus + shared keys + agent composers = a distributed multi-tenant system running third-party CODE and third-party INSTRUCTIONS on shared credentials. Safe composability is the only version that survives an ecosystem; it's a spine through M2/M4/M5/M6, decided in M2.** | **Redirects** the security architecture. |
| PT-8 | *"This is an engineering epic."* | **It's a founder-portfolio bet under bus-factor-1: it spends a non-renewable solo quarter converting a validated vertical product into a commodity horizontal framework + an unbounded unfunded support liability, while the actual moat stays trapped in one undocumented head and the actual market (35x-cheaper coding) goes unsold.** | **Redirects** the whole bet. |

**The bravest summary:** PT-1, PT-2, PT-3, and PT-8 collectively say *you may be building the wrong thing for
the wrong person at the wrong time.* The honest builder question the current frame cannot answer — *"why not
just use LangGraph, or write 200 lines per 12-factor and point LangSmith at it?"* — has no answer because the
one differentiated thing (the routing-and-robustness calibration + the hardened harness) is precisely what
M6/M7 are designed to strip out and give away.

---

## 3. Cheap probes — fastest test for each premise-threat BEFORE committing months

Ordered by asymmetry (cost-to-run vs. months-it-could-save). The first three are days-or-less and gate the
point of no return (M2, where types get de-planned for hypothetical external diversity).

| Threat | Cheap probe | Cost | What kills the epic |
|---|---|---|---|
| **PT-1 (no second builder)** | **Recruit ONE real non-Peter person** to build ONE real thing on the *pre-epic* codebase (it already has build_pipeline, discovery, patterns.py, 5 packs). Hand them the repo + a one-paragraph brief, watch where they bounce. Separately: ship M1's contract-checker + `pipelines new` scaffold + SKILL.md alone, instrument discovery — does any non-Peter pack ever land in `~/.megaplan/pipelines/` in 30 days? | **One afternoon** to recruit; 30 days passive. | No one to ask, or they bounce, or they reach for LangGraph → demand is weak → collapse to Peter-serving core. |
| **PT-2 (composability commoditized)** | **Prior-art spike (1 day):** read 12-factor-agents, LangGraph+LangSmith pricing, CrewAI/DSPy positioning. Answer in writing: "what does a builder PAY for and get locked into?" If the answer is observability/eval/durability/routing (not composition), the thesis is on the wrong axis. | **1 day.** | Answer is anything other than "composing nodes." |
| **PT-3 (harness is the product)** | **Reframe test (½ day):** write the README two ways — "Arnold, an SDK; megaplan is example #3" vs. "a self-improving PEV harness with composition as plumbing." Show both to 3 outside devs cold; which gets "I'd try that"? | **½ day.** | The harness framing wins → invert the epic. |
| **PT-4 (substrate rejected)** | **Crash/upgrade drill (1-2 days):** start a multi-milestone chain, kill the process mid-execute, bump the SDK version, resume. Does it complete on the pinned definition, or resume into a different universe / leave a half-applied git side effect? Use the *existing* engine — no new code. | **1-2 days.** | It corrupts or silently mis-resumes → durable execution must be core. |
| **PT-5 (wrong unit)** | **Build a standing agent (2-3 days):** a long-lived PR-watcher or in-editor copilot ON Arnold. If it needs an event loop bolted *around* Arnold rather than expressed *in* it, the run/terminate frame is wrong. | **2-3 days.** | Needs the loop outside → the most valuable category is structurally excluded. |
| **PT-6 (code vs data topology)** | **Serialization spike (1 day):** can the realized graph round-trip to JSON/YAML and back, and can an LLM emit a valid one? The deleted yaml-pipelines doc already tested representation — re-read its verdict, but note it held SUBSTRATE fixed (its real lesson is "representation alone buys nothing," not "declarative lost"). | **1 day.** | Round-trip is impossible without the Python build() → topology is locked to code authors. |
| **PT-7 (injection bus)** | **Red-team probe (½ day):** plant a poisoned instruction in a file/issue a benign ingest node fetches; run a pipeline whose downstream node reads that Port. Does the instruction execute? (It will.) | **½ day.** | It executes with zero malicious modules → keystone needs provenance/taint. |
| **PT-8 (founder portfolio)** | **Attention-week estimate (½ day):** re-estimate the epic in founder-attention-weeks with a self-reference + solo-non-delegability multiplier (recursion: you're refactoring the engine running the refactor). If honest number ≈ a full quarter of the only person who can also sell, that flips the bet on its own. | **½ day.** | The number is "a quarter you can't get back." |

**The meta-probe (the cheapest, most decisive):** the team spent enormous validation effort on whether the
abstraction is *correct* and ~zero on whether anyone *wants* it. A corpus grep across c1-c7, s1-s4, 8
premortems, 11 confidence docs, 10 interrogation lenses for any demand-existence question ("do people want",
"who would use", "finished tool vs SDK") returns **literally zero hits**. The fact that, in a months-long
program explicitly FOR second builders, no one ever tried to recruit a second builder, is itself the loudest
evidence that demand is weak. **Insert a demand gate before M2.**

---

## 4. Blind-spots in our PROCESS that let these hide

The findings cluster into five structural blindnesses. Each is a property of *how we validated*, not of any
individual missed fact — which is why every prior pass was structurally unable to see them.

1. **Axioms-as-given, never-as-tested.** The frame stated "value = composability," "builders are developers,"
   "the unit is a pipeline," "runs where megaplan runs today" in the opening sentences. Every downstream pass
   *optimized within* those axioms (better Ports, cleaner graph). The axioms were never represented as
   *milestones competing for the slot*, so the alternative (be a product, not an SDK; be a daemon, not a
   library; be data, not code) could never compete. **A design process scores plans; it cannot score the
   non-existence of a plan.**

2. **The artifact had validation machinery; demand had none.** Premortems, confidence ledgers, interrogation
   lenses — all operate on the ARTIFACT (will it break? is it correct? is the abstraction clean?). There is
   zero customer-discovery machinery because the culture is "harden the plan." A demand test isn't a pytest,
   so it never made the board. We are excellent at robustness-against-our-own-bugs and have no instrument for
   robustness-against-the-world-being-different.

3. **The prototype user was the author.** Peter is the entire addressable sliver (expert, Python-native,
   building agent tools). Using him as prototype user silently installed an *imaginary* external builder as
   design authority while displacing the only real user. "What does a NEW builder need?" *felt* like rigor —
   it was the moment an N=0 user became the design authority. You cannot see your own indispensability from
   inside it (bus-factor is invisible to the indispensable person).

4. **Mental models owned by different milestones never met.** Security = untrusted-code (M6). Dataflow =
   shape contracts (M2). They were owned by different milestones and different mental models, so the
   typed-artifact-injection bus (which lives in the seam between them) was nobody's section. Same for:
   trust-as-in-process-concept (policy spine) vs. trust-as-social/distribution-concept (nobody owned it
   because the frame had no strangers in it); money-as-performance-metric vs. money-as-liability/security
   boundary. **The blind spots live in the seams between owned milestones.**

5. **Hardening held the model and the world constant.** Every oracle measured "will this break?" against
   TODAY's model and TODAY's market. None asked "will this still MATTER?" The 5-domain stress test couldn't
   return "this verb is a crutch that dissolves" because every sketch assumed a model that needs the crutch.
   The more we hardened (build-time resolution as keystone), the more concrete we poured around a 2026 shape
   — converting agility into commitment at exactly the moment the frontier is moving. **"Wait to run" / "too
   big to even begin" is itself a warning: a deliverable whose world may change before it ships.**

6. **The discipline test was a moat-destruction machine.** "Would an unrelated builder want this? → SDK;
   planning-only → stays put" routes everything *reusable* into the free giveaway and everything *defensible
   and earned* into "just app content." It was built to find clean abstractions and is constitutionally
   unable to perceive that the clean-abstraction layer IS the commodity and the messy app content IS the moat.

---

## 5. Reframes worth taking seriously

Five reframes, from most-radical to most-surgical. They are not mutually exclusive; the recommended path
braids the GTM reframe (R1) with the architectural ones (R3/R4) as conditional bets gated on probes.

**R1 — Founder portfolio, not engineering epic (from maintenance + demand).**
Stop asking "how do we build a good SDK?" and ask "what is the highest-leverage use of the only person's
next quarter?" Honest re-sequence: (1) write down + automate the routing-calibration playbook to de-risk
bus-factor-1 — *the moat is trapped in one undocumented head;* (2) do the minimal PRIVATE internal-boundary
cleanup that speeds Peter's own velocity (~1-2 weeks, not 10 milestones); (3) sell the routing product
(35x-cheaper coding, real invoice, hot 2026 buyer pain) and find the real second builder; (4) let THEIR
demand define the public SDK surface — by which point you have revenue or headcount to carry the support
liability the epic currently hands, unfunded, to one person. **The SDK should be PULLED by a paying builder,
not PUSHED by an internal aesthetic of composability.**

**R2 — Invert product and example (from agent-framework + moat).**
Headline = a best-in-class, *self-improving* PEV harness; composition = plumbing. Differentiation lives in
hardening, evals, and self-evolution (capture: did the cheap model's work survive review? did finalize's 1-5
predict actual escalation? — feed it back; ideally publish a citeable cheapest-capable-model index that
churns weekly with prices). Keep megaplan the privileged flagship in every docs/benchmark surface even if
it's *technically* a discovered module. **Decouple "no code privilege" from "no special status" — the epic
conflates them and M7's zero-planning-vocabulary test actively pushes builders away from the flagship.**

**R3 — Governance/operating-time, not authoring-time (from durable-engines + multi-user + economics).**
The defensible unit is not the pipeline but the *(immutable content-hashed definition, append-only journal)*
pair plus the operating-time disciplines: version-pin in-flight runs, recorded-result replay, idempotency
keys + Saga compensation for irreversible git/fs side effects, asset-lineage observability, per-principal
attribution + budget ledger + tamper-evident audit. **The builder's win flips from "I shipped a module" to
"my weeks-long run survived a version upgrade, a crash, and an audit, and I can prove which definition+inputs
produced this exact result."** Build the moat, *rent* the durable substrate (target Temporal/LangGraph/Step
Functions OR the local Store via a Backend port) rather than re-implementing in-process what Temporal spent a
decade and $300M building.

**R4 — Safe composition as a first-class spine (from abuse-supply-chain).**
The correct mental model is not "plugin SDK" (npm/VS Code) but "operating system / browser." The unit of
trust is the FLOW of an artifact through a capability-attenuated boundary with provenance, not the module.
Concretely: Port = (type, version, CAS, **provenance, taint**); StateDelta carries who-wrote-it + was-any-
input-external; produce/judge/gate/revise fence untrusted-origin content before it can instruct a model;
capabilities attenuate DOWN the DAG (intersection of declared-need and composition-grant, never amplify);
prompts/rubrics/SKILL.md are content-addressed + hash-pinned (the payload in an agent system is the English,
and there is no SBOM-for-prompts industry tooling). Decided in M2, not bolted on in M6.

**R5 — The adoption surface is the shareable runnable artifact + registry + inspector (node-graph + plugin).**
If any external-builder path survives, the flywheel is: a killer first-party runnable tool → low-friction way
its users get MORE community tools → permissionless publish (HACS-style, points at any repo) → OPTIONAL
trust/quality signals (not a mandatory blessing gate). Promote the run record (state + events + diff) from
internal telemetry to a shareable, versioned, diffable, *replayable/inspectable* artifact — and add a
declarative (YAML/JSON) authoring+sharing surface with the Python SDK demoted to the peek-inside escape
hatch (reconsider the yaml-pipelines deletion). Plus dependency/process isolation, because foreign pieces
silently breaking each other in one shared interpreter is the ceiling-setting failure of the most-adopted
node ecosystems.

---

## Recommended immediate action (the cheapest thing that changes the most)

**Insert a demand gate before M2.** Run the day-or-less probes (PT-1 recruit-one-builder, PT-2 prior-art
spike, PT-8 attention-week estimate, PT-7 injection red-team) in parallel this week. M2 is the point of no
return — it de-plans the types for hypothetical external diversity and ossifies the Python import as the
public API. The asymmetry is brutal: a few days of probes vs. a solo quarter spent making a validated product
subtractable and unsold for a builder who, by the repo's own record, does not exist.

If the demand probe comes back empty (no one to ask, or they reach for LangGraph), the honest move is the
~40-50% smaller Peter-serving epic: M1 (hygiene + contract-checker), M2 (de-planning the types), the node
decouplings — all of which pay off the next time Peter ships a tool — and **defer/delete** the trust boundary,
manifest-first discovery, SemVer surface, multi-tenant quota, and public supervisor tier until a paying second
builder pulls them into existence.
