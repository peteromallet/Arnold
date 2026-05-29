# Unknown-Unknowns: The Agent-Framework Landscape (Prior-Art Vantage)

Vantage: study what LangGraph, CrewAI, AutoGen, OpenAI Agents SDK/Swarm, DSPy,
Pydantic-AI, Mastra, Inngest agent-kit, Temporal, and the "12-factor agents" /
"harness engineering" movements have already solved/standardized — to surface what
the Arnold epic's frame ("composable Python pipeline SDK of pieces that builders
compose into DAGs/loops") is structurally blind to.

We assume: Arnold = in-process Python SDK of composable nodes
(produce/judge/gate/revise/fan_out/reduce/select/escalate/clarify/verify) that
external **developers** compose into **pipelines (DAG/loop)**; value = composability;
megaplan becomes one module; success = an external builder ships a module cheaply.

This brief attacks the frame from outside. Internal/code findings (typed Ports,
realized graph, policy spine, trust boundary) are deliberately out of scope.

---

## What the landscape actually settled (grounding)

- **The frame is crowded and converged, not novel.** Multi-agent / composable-pipeline
  is a 3+ year-old, near-commoditized category. LangGraph (~34.5M monthly downloads,
  enterprise default), CrewAI (role-based, ~60% of Fortune 500 touched, "working pipeline
  before lunch"), Microsoft Agent Framework (AutoGen+Semantic Kernel merged, v1.0 GA Apr
  2026), OpenAI Agents SDK (Swarm productionized Mar 2025), LlamaIndex Workflows,
  Pydantic-AI, Mastra, Inngest. A new entrant in 2026 with "composable nodes you wire into
  a DAG" has **no axis of differentiation that any of these doesn't already own**.
- **The graph/DAG abstraction is the thing the market is actively souring on.**
  "Many engineers regret graph-based architectures... graphs, sub-graphs, state objects
  all hiding the actual agent logic." CrewAI's adoption thesis is explicitly *"we have a
  crew of agents" beats "we have a DAG with conditional edges."* The "12-factor agents"
  movement (Dex Horthy/HumanLayer) — the most-cited 2025 production doctrine — says **own
  your control flow in plain code; most strong teams roll the stack themselves; there
  aren't a lot of frameworks in production customer-facing agents.** Our central bet (the
  DAG/loop is the unit of value) is the abstraction the leading edge is walking away from.
- **The composition layer is being commoditized by protocols, not SDKs.** MCP (97M+
  monthly SDK downloads, Linux Foundation governance, OpenAI/Google/MS/AWS adoption) +
  A2A + AGENTS.md standardized tool-attach, agent-to-agent handoff, and agent config as
  *language-neutral protocols*. The integration pain Arnold's "drivers/pieces" solve in
  Python is being solved one layer down, for every language, by the ecosystem.
- **The real moat of the one framework that "won" is NOT the framework.** LangGraph's
  durable revenue and lock-in is **LangSmith** (observability/eval/tracing, "set one env
  var and it just works"). Teams pay for *"how do I run this in production without it
  falling over at 2am"* — traces, evals, regression detection — not for the node library.
- **Durability, not composability, is the named production gap.** "Checkpoints are not
  durable execution" (Diagrid); LangGraph/CrewAI/ADK explicitly called short. Temporal
  and Inngest win agent infra by guaranteeing run-to-completion across infra failure
  *inside* a step, idempotent retries, resume. Megaplan already lives this pain (our own
  memory: stream stalls, idle backstops, chain-blocked retries, resume-via-project-dir).
- **DSPy reframed the entire value proposition: prompts as compiled artifacts.** You
  declare signatures + metrics and an *optimizer* produces the prompts; switching models =
  recompile, not re-engineer. The frontier is **optimization/learning over a program**,
  not hand-wired graphs of hand-written prompts.
- **"Harness engineering" / Plan-Execute-Verify is now a named field with its own
  doctrine.** Coding-agent harnesses (Claude Code, Codex, Devin) converge on PEV; "65% of
  enterprise AI failures trace to harness defects (context drift, schema misalignment,
  state degradation)"; Live-SWE-agent hits 77.4% on SWE-bench with a *self-evolving*
  harness that adapts from failure signals. Megaplan's plan→critique→execute→review **is a
  PEV harness** — re-derived in a vacuum and re-labeled as "one module."

---

## Unknown-Unknowns

### U1 — We re-derived an already-named category ("harness engineering" / PEV) and demoted our one real asset to "a module"
Our node set (produce/judge/gate/revise/verify/escalate) is a re-derivation of the
**Plan-Execute-Verify harness** pattern that the coding-agent industry has independently
named, benchmarked (SWE-bench), and is now *evolving automatically* (Live-SWE-agent,
77.4%). Megaplan is not "one module among many" — it is a battle-hardened PEV harness with
real production scar tissue (stall detection, idle backstops, chain resume, gate
tiebreakers, cost tiering). The epic's frame **dissolves the only thing we have that the
market recognizes as hard and valuable** and reframes it as a generic example app.
- **Why our process was blind:** every prior pass treated megaplan as the *incumbent to be
  generalized away from*, so "make it one module" felt like progress (de-coupling). No
  pass asked "is megaplan-the-harness actually the differentiated product, and Arnold the
  commodity wrapper?" We optimized for composability because that's the axis we chose, not
  the axis the market rewards.
- **If true:** invert the epic. The deliverable is a **best-in-class, self-improving PEV
  coding/agent harness** (with the composition layer as plumbing), not a generic node SDK.
  Differentiation = the hardening, evals, and self-evolution of the harness — not the DAG.
- **Severity: would-redirect**

### U2 — Composability is the commoditized axis; the moat is observability/eval/durability, which our frame treats as out-of-scope infra
The framework that actually won (LangGraph) monetizes and locks in via **LangSmith**
(traces/evals/regression), and the framework infra that wins production (Temporal/Inngest)
wins via **durable execution**. "Composable pieces" is table stakes that 8 incumbents
already ship. Arnold's stated value ("the value is composability") is **a bet on the one
axis with no remaining margin.** Meanwhile megaplan *already* has proto-versions of the
winning axes (cost/observability tooling, diagnose/observe skills, chain resume) that the
epic frame relegates to "where it runs today."
- **Why our process was blind:** the frame fixed "value = composability" as an axiom in
  sentence one; every downstream pass optimized *within* that axiom (better Ports, cleaner
  graph). The question "what do builders actually pay for / get locked into?" was never
  on the table because the answer was pre-supplied.
- **If true:** success metric must change. Not "external builder ships a module cheaply"
  (commodity, low willingness-to-pay) but "Arnold gives every pipeline production-grade
  trace/eval/replay/durability for free." Promote observability + durable execution from
  background infra to **the headline feature**; treat node composability as undifferentiated
  baseline.
- **Severity: would-redirect**

### U3 — "External developers compose Python pipelines" is the wrong user/unit; the market moved to declarative config (roles/YAML), protocols (MCP/A2A), and optimizers (DSPy) — i.e. *less* hand-wiring, not more
Three independent escapes from "developer hand-codes a graph": CrewAI (declarative
roles/YAML, intuitive mental model → adoption), MCP/A2A/AGENTS.md (composition as
language-neutral protocol, not an SDK call), DSPy (the program is *compiled/optimized*, not
wired). Arnold doubles down on the most laborious, least-adopted modality — a Python
developer manually assembling typed nodes into a DAG — at the exact moment the field is
abstracting *above* code or *optimizing* the code away. "Why not just use LangGraph (or
write 200 lines of plain Python per 12-factor)?" has no answer in the current frame.
- **Why our process was blind:** "builders are developers" and "the unit is a pipeline"
  were stated as givens. We never modeled the *non*-developer builder, the
  config/protocol-driven builder, or the optimizer-driven builder — so the entire trend of
  raising or compiling-away the abstraction was invisible.
- **If true:** the composition surface should be **declarative + protocol-native + optimizable**,
  not "Python developer wires typed nodes." At minimum, Arnold needs a no-/low-code
  composition layer, first-class MCP/A2A interop, and a DSPy-style "optimize this pipeline
  against a metric" path — or it ships into a modality the market is leaving.
- **Severity: would-reshape**

### U4 — In-process, single-repo, local/Railway is an architecture the field already rejected for anything beyond a demo
The production consensus (Temporal, Inngest, "checkpoints are not durable execution",
DynamoDB-backed LangGraph) is that serious agent execution is **distributed, durable,
event-sourced, and host-failure-survivable** — explicitly *not* an in-process loop with a
local state dir. "An agent halfway through a loop inside a single node loses all
intermediate work on failure" is the named failure mode of exactly our architecture.
Arnold's runtime assumption (Python in-process + `.megaplan/` dir + a Store, runs where
megaplan runs) is the architecture the field calls a prototype.
- **Why our process was blind:** "it runs where megaplan runs today" was carried in as a
  constraint to preserve, not a decision to defend. Continuity with the existing harness
  smuggled in a runtime model that the rest of the industry has already outgrown for
  long-horizon work — and long-horizon is precisely megaplan's epic/chain use case.
- **If true:** the runtime needs a durable-execution backbone (own it, or sit on
  Temporal/Inngest/event-sourced state) as a *core* concern, not "cloud is where it runs."
  Otherwise Arnold inherits megaplan's stall/resume scars as permanent architecture, and
  can't credibly serve the multi-day epic workloads it's aimed at.
- **Severity: would-reshape**

---

## The single biggest REFRAME

**We are building a commodity (a composable node SDK / DAG runner) and giving away the
moat (a hardened, self-evolving Plan-Execute-Verify harness plus the observability,
evaluation, and durable-execution layer that production teams actually pay for and get
locked into).**

The market has already commoditized "composable agent pipelines" and is actively
*retreating* from the graph abstraction toward (a) plain-code/12-factor control flow,
(b) declarative roles + language-neutral protocols (MCP/A2A/AGENTS.md), and (c) compiled/
optimized programs (DSPy). What is *not* commoditized — and where the one winner's real
revenue lives — is **observability + eval + durable execution**, plus a genuinely hard,
benchmarkable **PEV coding/agent harness**.

So the epic's center of gravity is inverted. Instead of "dissolve megaplan into a generic
pipeline SDK and let builders compose nodes," the defensible move is: **keep the hardened
PEV harness as the headline product, make it self-evolving (Live-SWE-agent), wrap it in
first-class traces/evals/replay/durability, expose composition the way the market actually
consumes it (declarative + MCP/A2A + optimizable) — and let "composability" be the
undifferentiated baseline, not the thesis.**

If we ship the current frame, the honest builder question — *"why not just use LangGraph,
or write 200 lines per 12-factor, and point LangSmith at it?"* — has no answer.
