# Unknown-Unknowns: Production / Org Reality

Vantage: assume Arnold succeeds *as designed* — an in-process Python SDK of pieces that
external builders compose into pipelines. Now ask what the wider world does to that artifact
the moment it stops being one dev on one laptop. The frame our process took for granted is
"a developer composes a pipeline and runs it." The world's frame is "an organization runs a
fleet of agents that touch money, code, and customer data, and is liable for what they do."
Those are different products wearing the same API.

---

## Grounding (what the code actually is, not what the pitch says)

- State is a **filesystem tree** (`.megaplan/plans/<name>/state.json`), resolved by *plan name*
  in a shared directory. No identity, owner, or namespace field exists anywhere
  (`grep user_id|tenant|owner|rbac` → nothing in core).
- Concurrency control is `fcntl.flock(LOCK_EX)` on `state.json` — a **same-kernel POSIX
  advisory lock**. It is a no-op across containers, unreliable on NFS/EFS, and invisible to any
  process not on that exact host.
- "Multi-tenancy" in cloud is `chain_session` = a **tmux session name** and `extra_repos` =
  more git clones on one shared volume. That is *time-sharing one box*, not isolation.
- Execution is **in-process**: the pipeline, the LLM driver, the tool calls, and the secrets
  all live in the same Python process with the same ambient filesystem and env (`OPENAI_API_KEY`
  exported into the runner). The trust boundary work we did is *inside* the process; there is no
  boundary *between* whoever asked for the run and what the run can touch.

These are not bugs. They are the correct design for a single-player SDK. The unknown-unknowns
are about what that design *forecloses* — and whether the foreclosure is the real ceiling on the
vision, not the composability work we're pouring effort into.

---

## UU-1 — The unit isn't a pipeline; it's an *accountable agent run*. We built a composability product for a market that buys accountability.

**Insight.** Every comparable system that crossed from "dev SDK" to "thing orgs pay for"
discovered the buyer wasn't paying for the abstraction — they were paying for the *answer to
"who did this, with whose permission, and can you prove it."* LangChain → LangSmith, Temporal →
Temporal Cloud, dbt-core → dbt Cloud, Airflow → Astronomer/MWAA: in every case the OSS framework
stayed free and the **money was in the run record, the access control, and the audit trail** —
not in the composition primitives. Arnold's entire designed value ("composability, the unit is a
pipeline") is precisely the part those markets commoditized to zero. The part they monetized —
*who ran what, against what, and the immutable evidence* — is the part Arnold has no concept of:
no run is attributable to a principal, evidence is local files anyone with shell access can
rewrite, and there is no notion of "this run was authorized to touch this repo/secret."

**Why our process was blind.** Every prior pass optimized the thing inside the frame — making
the SDK more composable, the graph more typed, the policy spine cleaner. "Composability" was the
assumed value axis, so the question "is composability what anyone *pays* for?" was never on the
table. We benchmarked against the framework layer of comparable systems and never looked at where
those same companies' revenue actually came from.

**If true.** The epic is building the free tier of a product whose paid tier doesn't exist yet,
and worse, building it in a shape (in-process, file-state, no principal) that makes the paid tier
expensive to retrofit. The strategic move flips: design the **run-record / attribution / evidence
schema as a first-class typed artifact now** (even single-player), because that artifact is the
future product and the future moat — composability is table stakes you give away.

**Severity: would-reshape.**

---

## UU-2 — `.megaplan/` + `fcntl` + in-process is *single-writer by physics*, and that is a hard architectural ceiling, not a hosting detail to fix later.

**Insight.** The assumption "it runs where megaplan runs today, we'll productize hosting later"
hides a category error. The state model isn't "single-user by default, multi-user with effort" —
it's **single-writer by construction**. Plans are keyed by name in a flat shared tree (two users
who both name a plan `refactor-auth` collide silently), the only mutual exclusion is a host-local
advisory lock that *does not exist* the moment you put state on shared/network storage or run two
containers, and execution shares the process's filesystem + secrets so there is no enforceable
"this run may only see tenant A's data." The standard productization path — "put the state dir on
a shared volume, run N workers" — doesn't degrade gracefully; it produces **silent state
corruption and cross-tenant secret/data bleed**, which is the one failure mode that ends a B2B
company. Temporal, Airflow, Prefect all eventually rewrote their state layer onto a real
transactional store with row-level ownership *exactly* because file/lock-based state can't be made
multi-tenant safe by adding features on top. Arnold would face the same forced rewrite, but only
after customers exist.

**Why our process was blind.** We *did* harden state (typed Ports, realized graph, trust
boundary) — and were explicitly told not to re-audit it. But all that hardening lives *inside one
writer's process*. "Hardened" was measured as internal correctness, never as "safe under
concurrent multi-principal writers," because the single-player frame meant there was only ever one
writer. The lock looks like concurrency control, so it pattern-matches as "we have concurrency
handled" — masking that it solves a different problem (one user, two terminals) than the one
productization requires (two tenants, one fleet).

**If true.** There is an unstated, hard ceiling: the current core can never become multi-tenant
SaaS without replacing its state and execution substrate (store → transactional row-owned DB;
in-process → out-of-process sandbox per run). Better to *name that boundary now* and decide
deliberately: either (a) commit to "Arnold is forever a single-player SDK; the org product is a
separate service that wraps it" — which is honest and fine — or (b) abstract the Store behind a
`Backend` port with ownership/namespace in the *type signature today* so the file backend is one
impl among several. Drifting into productization without that decision is the expensive path.

**Severity: would-redirect.**

---

## UU-3 — "Builders are developers" silently assumed the developer is also the principal, the approver, and on-call. In an org those are three different people, and the whole human-in-the-loop / gate machinery is wired to the wrong one.

**Insight.** Arnold (via megaplan) has rich human-in-the-loop machinery: approval gates,
critique, the auto_approve flag, override handlers. All of it implicitly addresses *one human* —
the developer at the keyboard who is also the person allowed to approve, the person whose creds
are used, and the person who gets paged when it stalls. In a real org these roles fission:
- the **builder** writes the module,
- the **operator** runs it (different person, often a different team),
- the **approver** of a gate (e.g. "this agent is about to push to prod / spend $400 / open a
  PR against payments") is frequently *neither* — it's a lead or a compliance owner,
- the **on-call** who inherits a wedged 1800s-timeout chain at 3am is someone who has never seen
  the pipeline.

The gate question "should this proceed?" is meaningless without "*who is allowed to answer it*,"
and Arnold has no concept of an approver distinct from the runner. Worse, our own MEMORY notes
that `megaplan auto` *bypasses* the auto_approve gate — in a single-player world that's a
convenience bug; in an org world that's an **unauthorized-action incident** (the agent took a
gated action no one with authority approved). The same machinery that is "helpful autonomy" for
one dev is "broken segregation of duties" for an org — and SOC2 / regulated buyers will refuse it
on exactly that basis.

**Why our process was blind.** "Builders are developers" collapsed four org roles into one
persona. Once you assume the builder == runner == approver == owner, the gate naturally addresses
"the user," and there's no slot in the design where a *second* identity could even be expressed.
The blindness is in the persona model, upstream of any code decision.

**If true.** Gates, overrides, and especially `auto`'s gate-bypass need a notion of *authorized
approver* and an *attributed approval event* before Arnold can run anything consequential in an
org. This reshapes the gate/override design (the very nodes the epic treats as composable pieces)
from "ask the user" to "route a decision to a principal with authority and record their answer."
It also means the on-call / runbook / observability story is a *product surface*, not docs.

**Severity: would-reshape.**

---

## UU-4 — Agents that touch repos, money, and customer data make Arrnold a *security and liability* surface, and the in-process model means the blast radius of one bad pipeline is "everything the host can reach."

**Insight.** The moment "other people compose pipelines" is real, you are running
**other-people's-code + other-people's-prompts** in-process, with the host's secrets and
filesystem ambiently available, against live repos and (per cloud.md) `extra_repos` on a shared
volume. A composed pipeline is arbitrary code plus a non-deterministic LLM that can be
prompt-injected via the data it reads (a malicious file in a repo it's reviewing, a poisoned
issue it's triaging). In the single-player frame that's "you ran your own thing, your problem."
In the org frame it's: a module authored by team A, run by team B's service account, prompt-injected
by content from customer C, exfiltrating team D's secret because everything shares one process and
one env. There is no sandbox boundary, no per-run credential scoping, no egress control, no
data-residency partition. This is not a hardening backlog item; it is the **liability model of the
whole product**, and it's the first question any security review (and any enterprise procurement)
will ask. "Composable agent pieces" without an isolation boundary is, from a CISO's chair, "a
remote code execution framework we let arbitrary teams and arbitrary inputs drive."

**Why our process was blind.** The trust-boundary work we did was *inside* the process (typed
Ports, policy spine) — defending the pipeline's own integrity. The threat model never included
*the run itself* as adversarial (malicious/injected pipeline vs. the host/other tenants), because
single-player means you don't attack yourself. Composability was framed as a *developer-experience*
win ("ship a module cheaply") and never as an *attack-surface* expansion ("anyone can ship code
that runs with your secrets").

**If true.** Productization requires an isolation substrate (per-run container/microVM,
scoped/short-lived credentials, egress allowlists, data-residency-aware storage) that in-process
execution structurally cannot provide. Either the org product runs each pipeline out-of-process in
a sandbox — a different execution engine than the one the epic is hardening — or Arnold is
positioned as "trusted-author, single-team internal tooling only," which caps the addressable
market. Naming that fork now prevents pouring more effort into an engine that can't cross the
security bar.

**Severity: would-reshape.**

---

## The single biggest REFRAME

**We are building the composition layer of an agent framework. The market past one developer
buys the *governance* layer — attribution, isolation, approval-by-authority, and immutable
audit — and treats composition as a free commodity. Arnold's current substrate (name-keyed
filesystem state, host-local advisory locks, in-process execution sharing one set of secrets) is
*single-writer and single-principal by physics*, so the governance layer can't be bolted on; it
forces a substrate rewrite later, at the worst possible time (after customers).**

So the strategic question the epic never asked is not "how do we make pieces more composable"
but: **"Is Arnold a single-player developer SDK forever (and the org product is a separate
governing service that wraps it), or is it meant to become the org product — in which case the
unit must be an *accountable, isolated, attributable run*, not a pipeline, and that has to be
true in the type system before there are users, not after?"** Answering that one branch retires
most of these unknown-unknowns; leaving it implicit means every composability investment is a bet
on the branch no one chose.
