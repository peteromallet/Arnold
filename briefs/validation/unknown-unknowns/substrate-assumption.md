# Unknown-unknowns — the substrate assumption

**Vantage:** DEEP ASSUMPTION — "Arnold is a Python, in-process library." Attack from outside the frame.
Should Arnold be a PROTOCOL/SPEC, a long-running SERVICE/daemon, or a declarative format with a runtime,
rather than an in-process Python SDK others `import`?

**Status:** adversarial exploration, 2026-05-29. Not a validation of the plan — an attempt to find the
layer the whole milestone program may be solving wrong.

---

## What the process actually assumed (and why it could not see the alternative)

Three structural facts about the prior work make this blindness *guaranteed*, not accidental:

1. **The two seed apps are both Python and both in-process.** Planning (subprocess CLI dispatch loop) and
   resident (asyncio chat loop) are both Python processes that `import megaplan`. The whole "what does a
   *new builder* need?" reframe was derived by triangulating between **two Python apps**. A reframe
   triangulated from two points on the same line cannot discover it is *on a line*. Every "diversity is
   the menu of backends" insight is diversity *within Python in-process composition* (subprocess-vs-async,
   JSON-vs-DB store, graph-vs-loop). None of it is diversity of **who holds the composition** or **what
   language the composer is written in**.

2. **The validation corpus literally never tested it.** `grep -niE "polyglot|non-python|JSON-RPC|gRPC|wire
   protocol|language-agnostic|cross-language"` across all of `briefs/validation/**` returns **zero**
   substantive hits. Every "Protocol" in the corpus is a `typing.Protocol` (an in-process Python ABC);
   every "service"/"server"/"daemon" is the resident Discord bot or the Railway container — i.e. a Python
   process. The "substrate edge" (edges-map.md §7) is explicitly and *only* `in_process` vs
   `subprocess_isolated` — a Python-internal kill/OOM boundary. The word "substrate" was claimed by the
   smallest possible meaning, which inoculated the team against ever asking the big one.

3. **They already ran — and lost — the *declarative* experiment, and over-generalized the loss.** YAML
   pipelines were built and removed in 0.22.0 (`docs/archive/yaml-pipelines-migration.md`). That is a real,
   earned data point: a YAML *serialization of the same Python topology* added a parser, a resolver, and a
   second source of truth without buying expressiveness, because the composer was still a Python developer
   editing files in the same repo. The trap is concluding "declarative lost ⇒ in-process Python won." Those
   are different axes. The YAML experiment tested *representation* (YAML-vs-Python) while holding *substrate*
   (in-process, single-repo, Python composer) fixed. It says nothing about protocol-vs-library or
   service-vs-library. The team is likely to *cite the dead YAML* as if it closed the substrate question. It
   did not.

The unifying blindness: **the unit of analysis was always "the composition," never "the boundary the
composition is expressed across."** Arnold was defined as the verbs (produce/judge/gate/...) and the
nouns (Port/Store/driver). Nobody asked *where the membrane is* — what is inside Arnold's process and what
talks to it from outside.

---

## The smoking gun the frame hid in plain sight

Arnold's single most load-bearing capability — `dispatch` — **already crosses a process and language
boundary today, and it does so over a wire-ish contract.** Planning's `subprocess-cli` backend forks
**Codex** (a Rust/TS binary) and **Shannon/Hermes** and talks to them over stdio + a JSON-ish streaming
protocol, parsing their events for heartbeat/cost/stall. resident's `async-api` backend speaks
**OpenAI-compatible HTTP/JSON** to a model server. The 26 `MEGAPLAN_*` env vars (`s4-external-coupling.md`)
are an *ambient, untyped wire contract* to those out-of-process tools.

So the architecture is **already polyglot and already cross-process** — but only **downward** (Arnold is the
client; tools are servers). The entire epic is investing in making the *upward* boundary
(builder→Arnold) a **typed in-process Python `import`**, at the exact moment the *downward* boundary it
depends on is an untyped multi-language wire protocol. We are hardening the seam that is *already a library*
and leaving un-specified the seam that is *already a protocol*. If a wire protocol is good enough for the
hardest, highest-stakes integration Arnold has (driving Codex/Shannon), the burden of proof is on "why must
the builder boundary be a Python import?" — and that burden was never discharged.

---

## Unknown-unknown #1 — Arnold's real product is a *wire contract*, and the SDK is the wrong artifact

**Insight.** The thing a "fourth builder" most needs to reuse is not the Python verbs — it is the
**dispatch-tool wire contract** (how you drive a Codex/Shannon/Claude agent process with streaming events,
cost, heartbeat, stall-detection, key-pool, cancellation). That contract is the part nobody else can
cheaply rebuild and the part Arnold has spent the most hardening on. The verbs (gate/critique/fan_out) are
a weekend of code for a competent dev; the *operationalized agent-process protocol* is months. By packaging
Arnold as `import megaplan` (Python, in-process), you make the **easy** part reusable and lock the **hard,
valuable** part inside a Python call stack where a Rust/TS/Go builder can never reach it without
re-implementing the whole runtime.

**Why the process was blind.** The seed apps are both Python, so "reuse" *always meant* `import`. The
dispatch contract was treated as an *internal interface with backends* (`interface-feasibility.md`), never
as a *publishable external protocol* — because both consumers lived in the same interpreter. The team
optimized the import ergonomics (typed Ports, build-time `consumes` resolution) and never asked whether the
boundary should be importable at all.

**If true.** The milestone program is building the wrong deliverable's polish. M2's typed-Port-binder, M5's
node library "stable signatures," M7's builder-docs are all *Python-import surface*. The high-value
extraction would instead be: specify `dispatch` (and `emit`, `state`-delta, `evidence`) as a **versioned
wire contract** (stdio/JSON-RPC or HTTP), with the Python SDK as *one* client of it. Planning and resident
become two clients; a Rust agent tool becomes a third — none of them `import megaplan`. The acceptance test
"a fourth, non-planning thing ships cheaply" is *far* better served by "a fourth thing in a *different
language*" than by another Python module.

**Severity: would-redirect.** It moves the center of gravity of the whole epic from "Python composition
surface" to "protocol specification," changing what M2/M5/M7 even produce.

---

## Unknown-unknown #2 — composition is a *control-plane* concern, and the right substrate is a long-running service, not a library you re-enter

**Insight.** Everything that makes Arnold *Arnold* — pause/resume, human-gate, set-robustness-mid-run,
recovery policy, budget/cost folding across fan-out shards, chain/epic/bakeoff supervision, the durable
Store — is the behavior of a **long-running stateful orchestrator**, not of a function you call and return
from. resident *already is* this: an always-on async runtime with a durable job poller, coalescer,
scheduler, and confirmation manager (`resident-shape.md`). Planning *fakes* it with a subprocess loop +
`state.json` polling because it lacks a resident. The epic's plan is to extract resident's runtime *as
Python pieces planning imports* — but the honest shape of "a thing that owns durable runs, accepts control
commands mid-flight, and survives the client disconnecting" is a **daemon with an API**, not an SDK. The
"control interface trio" (`read_valid_targets, apply_transition, synthesize_artifacts`) in the EPIC §4 is
*literally a service API surface* dressed as in-process function pointers.

**Why the process was blind.** Megaplan runs today as a CLI invocation and a Railway container, so "where
it runs" was settled before the epic began (`docs/cloud.md`). The team inherited "you invoke it, it runs,
it exits" and only asked how to *compose* within that lifecycle. The premortem lenses
(over-engineering, wrong-abstraction) audited the *pieces*, never the *lifecycle*. Nobody asked: if control
(pause, set-robustness, override, human-gate) is fundamentally about *talking to a run in flight*, is a
library — which by definition has no addressable in-flight identity — even the right shape?

**If true.** The control-plane / supervisor-tier milestones (M5c, M5d) are designing an in-process control
plane for an out-of-process problem. The natural artifact is `arnold serve` (a daemon owning the Store) +
clients (CLI, Discord, a future web UI, other-language SDKs) that issue control commands over a thin API.
This *also* dissolves three live pain points the validation already found: cross-process state via
`state.json` polling, the `MEGAPLAN_*` ambient-env trust model, and "auto bypasses the gate"
(MEMORY: `feedback_auto_gate_bypass`) — a gate is trivially enforceable as "the service won't transition
without a control call," and impossible to enforce reliably as "a Python flag the in-process loop is
supposed to check."

**Severity: would-reshape.** It re-homes the supervisor/control milestones onto a service substrate and
makes the Store a server-owned resource rather than a directory two processes race on, but the verbs and
node library survive largely intact.

---

## Unknown-unknown #3 — "single-repo, in-process" silently forecloses the only market where "others build a fourth thing" is real

**Insight.** The success criterion is *external adoption* ("a third builder ships a fourth thing"). But the
chosen substrate — a Python library you `import` into your own process, sharing your interpreter, your
dependency tree, your key-pool, your trust level (`a5-sandbox-trust.md`: trust is process-global env) —
maximizes *coupling* at exactly the moment you want *adoption*. Every successful "others build on it"
substrate of the last decade won by being **the opposite of an in-process library**: LSP (a protocol; any
editor, any language server), MCP (a protocol; any host, any tool, any language), the OpenAI API (a wire
spec; thousands of SDKs), Temporal/Airflow (a *service* you submit workflows to). The pattern is brutal and
consistent: **orchestration substrates that won were services-with-protocols; orchestration *libraries*
stayed single-team tools** (Prefect-the-library vs Prefect-the-cloud; Dagster-the-lib vs Dagster+; even
LangChain's gravity moved to LangGraph *Platform/Server*). An in-process Python SDK is the substrate of a
*framework*, and frameworks are adopted by people *already in your language and your repo*. That is not "a
third builder." That is "me, again, next quarter."

**Why the process was blind.** "Builders are developers" and "it runs where megaplan runs today" were
stated as fixed premises in the EPIC's opening, not as choices. The whole investigation accepted the
deployment story and asked only about the API ergonomics. No comparable-systems / market analysis was in
scope — the validation was all *code archaeology* of the existing two apps. So the dominant industry
evidence about *what substrate actually gets third-party adoption* never entered the room.

**If true.** The acceptance tests are measuring the wrong adoption. "jokes upgraded to a real pipeline" and
"a select-based tournament toy" are *in-repo, in-Python, by-us* — they prove composability, not adoption.
The honest adoption oracle is "someone who is **not in this repo and not necessarily in Python** ran their
own thing through Arnold." Only a protocol or a hosted service can pass that. If the real goal is adoption,
the in-process library is a *category error* about what gets adopted, and the epic should at minimum carve a
stable wire contract *now* (cheap to do early, ruinously expensive to retrofit after M2–M7 harden a Python
import surface as the public API).

**Severity: would-redirect.** It challenges whether the stated success metric is even reachable on the
chosen substrate, which is upstream of every milestone.

---

## Unknown-unknown #4 — the dead YAML experiment is being mis-cited; the substrate question it actually settles is the *opposite* of what it looks like

**Insight.** The team will reflexively answer "we tried declarative, it lost, so in-process Python is right."
But read what actually died: a YAML *serialization of a graph topology* whose author was still a Python dev
in the same repo with the same runtime. What that experiment *proves* is that **representation alone buys
nothing when the substrate is unchanged** — moving the same composition from `.py` to `.yaml` just adds a
parser. It is *evidence for the substrate thesis, not against it*: it shows that the value was never in the
representation, so squeezing the Python import surface (M2/M5/M7) will hit the *same wall* — better
ergonomics on the same substrate, no new builders. The thing the YAML experiment never tried is the only
thing that would change the equation: a **different composer** (another language, another process, a hosted
client) talking to Arnold over a contract. A DSL/spec only earns its keep when its *consumers are
heterogeneous* (cf. SQL, HCL, GraphQL — adopted because many different runtimes and languages speak them).
Arnold's YAML had exactly one consumer shape, so of course it lost.

**Why the process was blind.** The experiment was filed as "YAML pipelines, removed" — a closed verdict.
Closed verdicts stop inquiry. Nobody re-examined *which variable* the experiment actually moved, so the
loss got over-generalized from "this representation, this substrate" to "declarative/external substrates,
in general."

**If true.** The epic should explicitly *separate the two axes it conflated*: representation (Python vs
YAML — settled, Python wins) and substrate (library vs protocol vs service — **untested**). The dead YAML
must not be allowed to stand in for the untested substrate question in any milestone-justifying argument. A
cheap experiment — define the `dispatch` contract as a wire spec and drive one real run from a *non-Python*
client — would test the actual variable in days, before M2 hardens the Python surface as the contract.

**Severity: worth-knowing.** It doesn't redirect by itself, but it removes the single biggest piece of
"evidence" the team would use to dismiss #1–#3, so it's load-bearing for whether those get a fair hearing.

---

## The single biggest REFRAME

**Stop asking "what pieces does a Python builder compose in-process?" and start asking "what is the smallest
contract someone *outside our process and possibly outside Python* must speak to run a robust agent
pipeline through Arnold?"**

Arnold's durable value is not the verbs (cheap to clone) — it is the **operationalized agent-orchestration
contract**: drive an agent process with streaming events, cost, heartbeat, stall-detection, key-pool,
budget-folding, pause/resume, human-gate, recovery policy, durable state. That contract is *already*
spoken across a process+language boundary on its hardest edge (Codex/Shannon dispatch). The epic is
investing to make the *easy, cloneable* part (Python composition) a polished `import`, while leaving the
*hard, valuable* part as an untyped ambient-env wire mess — and is using a mis-read dead YAML experiment to
avoid examining the substrate at all.

The reframe: **Arnold is a protocol + a reference runtime, not a library.** Concretely — define `dispatch`,
`emit`, `state`-delta, `evidence`, and `control` (pause/resume/gate/set-robustness) as a **versioned wire
contract** (stdio JSON-RPC and/or HTTP). Ship the Python SDK and an `arnold serve` daemon as the *reference
implementations / first clients*, not as the product. Planning and resident become two clients of the same
contract; the load-bearing acceptance test becomes **a fourth thing in a different language (or a different
process) that never imports megaplan**. If that test is unreachable, the "others build a fourth thing" goal
was never reachable on an in-process library — and it's far cheaper to learn that by speccing the contract
*before* M2, than after M2–M7 have ossified a Python import as the public API.

The conservative, non-regret move even if you keep the SDK: **carve and freeze the wire contract for
`dispatch` now**, as a deliverable parallel to M2, so the substrate decision stays open and the most
valuable asset becomes the thing a polyglot world can adopt — instead of being permanently trapped behind a
Python call stack.
