# Unknown-Unknowns from the Durable-Execution / Workflow-Engine Vantage

Vantage: 15+ years of hard-won lessons in Temporal, Dagster, Prefect, Airflow,
Argo Workflows, AWS Step Functions, Nextflow — plus the 2025/26 wave of these
engines being retrofitted under LLM-agent frameworks (OpenAI Agents SDK,
Pydantic AI, LangGraph). Temporal raised $300M at $5B in Feb 2026 explicitly on
the back of AI-native durable execution (1.86T of its 9.1T lifetime actions from
AI-native companies). This is not a niche we are adjacent to — it is the
category we are quietly re-implementing.

The frame we are attacking from outside: Arnold as an in-process Python SDK of
composable "pieces" + node library, where the unit is a *pipeline (DAG/loop)*
that *developers compose*, success = an external builder ships a module cheaply,
value = composability, runs on a `.megaplan/` state dir + Store. Every prior
pass took "we build a better composition kit" for granted. The workflow-engine
world says the composition kit was never the hard part.

---

## What these systems actually solved (the canon)

1. **Strict separation: workflow DEFINITION (a versioned, immutable, diffable
   artifact) vs workflow EXECUTION (a journal of recorded events).** Temporal,
   WWF, Step Functions all enforce this. Step Functions: every `UpdateStateMachine`
   mints an immutable read-only *revision*; executions are pinned to a version or
   alias, never "latest." The article *"Agent Workflows Are Rediscovering Durable
   Execution"* (May 2026) names this as the #1 thing agent frameworks get wrong:
   "The workflow as a whole, the actual business logic, is often not a portable,
   inspectable, versioned artifact that can be reviewed, diffed, approved, tested,
   and audited." And: "A workflow definition is not the same thing as a workflow
   execution."

2. **Determinism contract: replay is achieved by re-executing the
   definition deterministically and substituting RECORDED results for every
   non-deterministic step.** The workflow function must be pure; all
   non-determinism (clocks, randomness, network, *LLM calls*) lives in
   "activities" whose first-execution results are journaled and *never re-run*.
   "You cannot replay an LLM call and pretend it is the same event." Temporal
   *fails the workflow* on a history/code mismatch rather than silently
   continuing.

3. **Versioning of IN-FLIGHT workflows is the central, unavoidable problem** —
   not retry, not state, not observability (those are downstream of it). The
   moment you ship a code change, every paused/running execution either (a)
   completes on its *original pinned version* (Worker Versioning / Step Functions
   aliases) or (b) is explicitly *patched* with branch guards (Temporal
   `GetVersion`/patching). If you do neither, "a paused workflow can resume into a
   different universe" and dies on non-determinism. This is the single hardest,
   most-relearned lesson in the whole category.

4. **Side effects must be idempotent OR have a recorded result to replay.**
   "Retries are only safe when the target operation is idempotent or the
   workflow has a recorded result it can reuse." Engines give you idempotency
   keys / activity IDs to dedupe. Airflow's entire backfill discipline is built
   on this (upsert/MERGE/partition-overwrite; `--reset-dagruns` or you silently
   skip/duplicate; streaming-vs-backfill partition collisions silently lose 12h
   of data).

5. **Sagas (forward compensation), not ACID rollback**, for distributed
   multi-step work. You cannot un-send an email or un-merge a branch; you record
   a compensating action.

6. **The agent-specific gap that NOBODY has closed yet:** the deterministic-replay-
   for-agents literature (Sakura Sky "missing primitives," Zylos) captures *tool
   outputs* but has *no mechanism for irreversible side effects* — file writes,
   code edits, `git merge`, branch creation. The replay model assumes the world
   is read-back-able. Agents that *mutate a repo* break the core durable-execution
   assumption. This is precisely megaplan's execute/review domain.

7. **Dagster's reframe: the unit is the ASSET (the durable thing produced), not
   the TASK (the step that produces it).** Task-centric orchestrators "provide
   insight into pipeline status but not the state of the underlying assets that
   actually matter." Assets are "nameable, traceable, versionable," carry lineage,
   and let you ask "what is stale / what must be recomputed" declaratively.

---

## UNKNOWN-UNKNOWNS

### U1 (would-reshape → would-redirect). The unit isn't the pipeline; it's the versioned (definition, journal) pair — and "developers compose pipelines" is the wrong success metric.

Every prior pass optimized *authoring* (compose nodes into a DAG cheaply). The
entire durable-execution canon says authoring was never where systems die. They
die at the seam between a **definition that keeps changing** and **executions
that are still running on yesterday's definition.** Arnold's headline feature —
"the realized graph is re-invocable mid-run" — is, from this vantage, the exact
mechanism that makes in-flight versioning *unsolvable* unless the definition is
an immutable, content-hashed, pinned artifact separate from the journal. If a
builder edits a node mid-epic (and epics run for weeks — see the project memory),
every paused milestone resumes "into a different universe."

**Why we were blind:** we framed value as *composability* and the user as a
*developer at authoring time*. We never modeled the *operator at recovery time*
six days into a paused run after the SDK was upgraded. "Composable pieces" is an
authoring-time virtue; durable execution is an operating-time discipline, and
the two are in tension (more composability = more surface that can drift).

**If true:** the epic's success metric flips from "external builder ships a
module cheaply" to "a run started on version N completes correctly on version N
even after N+1 ships, and an operator can diff/audit exactly which definition+
inputs produced this journal." Pipelines must be content-hash-pinned and the
state dir must store the *definition snapshot*, not a path to it. (Memory note
`project_init_brief_snapshot_gap` — "init stores brief as PATH not content" — is
the *first symptom* of this whole missing discipline, not an isolated bug.)

---

### U2 (would-reshape). Replay/resume is a lie for agents that mutate a repo — and we are building exactly that.

The whole "resume mid-run / re-invoke the realized graph / policy spine" design
implicitly assumes the durable-execution replay model works. It does *not* work
when the non-deterministic step has irreversible side effects on the world. The
agent-replay literature openly has "no mechanism for handling irreversible side
effects." Megaplan's execute node *edits files, commits, merges, creates
worktrees and branches*. You cannot journal-and-replay a `git merge` the way you
journal an LLM completion. The honest models for this are (a) **idempotency keys
on side-effecting nodes** (this file-edit was already applied; skip), and (b)
**Sagas / compensating actions** (this branch was created; the compensation is
delete-branch), not "re-invoke the graph."

**Why we were blind:** "resume" was treated as a state-machine property
("realized graph re-invocable"), reasoning about *control flow*, never about the
*irreversible external state* (git history, the filesystem) that control flow
touches. The frame's mental model is data flowing through nodes; the reality is
nodes mutating a shared mutable repo.

**If true:** every side-effecting node needs an explicit idempotency key + a
declared compensating action, and resume must be defined as "re-derive which
side effects already landed (via git/worktree introspection), skip those, and
compensate partial ones" — *not* "replay the journal." Several memory items
(`worktree_carry_review_falsepositive`, `worktree_carry_breaks_pr_isolation`,
`chain_blocked_retry_and_resume`) are all the same wound: resume semantics
defined over control flow while ignoring the mutable git substrate.

---

### U3 (would-redirect). You are competing with Temporal/LangGraph/OpenAI-Agents-SDK on durable execution — and you've chosen the part they already commoditized, while skipping the part that's their moat.

As of late 2025/early 2026, durable execution is *no longer optional infra* for
agent frameworks — OpenAI Agents SDK, Pydantic AI, and LangGraph all ship it as
a baseline, backed by mature engines. "Composability of agent pieces" is being
given away free *on top of* a hardened durability substrate that took Temporal a
decade and $300M to build. Arnold is reinventing the substrate (state, retry,
resume, observability — the "policy spine," the realized graph) *in-process,
single-repo, on a `.megaplan/` dir*, which is exactly the architecture these
engines abandoned because in-process state can't survive process death,
versioning, or multi-tenant operation.

**Why we were blind:** the frame says "it runs where megaplan runs today (local
/ Railway container, a `.megaplan/` dir + Store)" — we inherited megaplan's
deployment as a *constraint* and never asked whether the durability layer should
be *ours to build at all*. We assumed the value was the node library on top; we
never priced the substrate underneath against a category that gives it away.

**If true:** the epic redirects from "build composable pieces + our own
state/retry/resume" to "define Arnold's nodes as a thin, *portable, versioned
definition artifact* that can target a real durable-execution backend (Temporal/
LangGraph/Step Functions) OR our local Store — and own the *agent-specific*
layer (judge/gate/critique/escalate semantics, compensations for code edits)
that none of them have." Build the moat (agentic side-effect compensation +
plan-quality nodes), rent the substrate (durable replay).

---

### U4 (worth-knowing → would-reshape). "Status of the pipeline" is the wrong observability target; "state of the produced artifact" is. Adopt the asset/lineage reframe.

Dagster's hard-won lesson: task-centric orchestration tells you *whether a step
ran*, not *whether the thing you cared about is correct, fresh, or stale.* For
megaplan the "assets" are the plan, the critique, the diff, the PR, the review
verdict. An asset-centric model gives free lineage ("this PR derives from this
plan v3 which derives from this brief-hash"), staleness detection ("the brief
changed; the plan is stale; recompute"), and partial recompute — all things the
node-DAG frame gets only by bolting on tracing after the fact (the
"observability-and-introspection-design" doc is the bolt-on).

**Why we were blind:** the chosen unit is the *pipeline (DAG/loop)* — a
fundamentally task/control-flow ontology. Assets are an orthogonal ontology the
frame never considered, so all observability discussion is trapped inside
"trace the nodes" instead of "track the artifacts."

**If true:** model nodes as *producers of named, versioned, hashed assets* with
declared upstream dependencies. Resume, staleness, caching, and the entire
introspection story fall out for free from asset lineage instead of being
re-derived per-node. (Note: `shannon_stream_stall`, `execute_stall_codex_silence`
are heartbeat/idle problems — symptoms of task-status observability with no
notion of "is the artifact making progress.")

---

## THE SINGLE BIGGEST REFRAME

**Arnold's center of gravity is wrong. The frame treats Arnold as a
*composition kit* (authoring-time, value = composability, unit = pipeline). The
durable-execution canon says the kit is the easy, commoditized part; the
durable, defensible part is the *(immutable definition, append-only journal)*
pair and the operating-time disciplines around it — version-pinning in-flight
runs, recorded-result replay, idempotency keys + Saga compensation for
irreversible side effects, and asset-lineage observability.**

Reframe the epic from *"a Python SDK of composable pieces that developers
compose into pipelines"* to *"a portable, content-hashed, versioned
agent-workflow DEFINITION format + the agent-specific durability layer (recorded
non-determinism, idempotent/compensating side-effects on a mutable repo,
asset-lineage), designed to run ON a real durable-execution backend rather than
re-implementing one in-process."* Composability becomes a property of the
definition format, not the product. The builder's win is no longer "I shipped a
module"; it's "my weeks-long run survived a version upgrade, a crash, and an
audit — and I can prove which definition+inputs produced this exact result."

If we keep the current frame, the most likely failure is not that builders find
it hard to compose — it's that the first real multi-week epic that spans an SDK
upgrade silently resumes "into a different universe," corrupts a repo with a
half-applied non-idempotent side effect, and cannot be audited or reproduced —
and we relearn, expensively, the four lessons above that Temporal learned a
decade ago.

---

### Sources
- Agent Workflows Are Rediscovering Durable Execution (Koshy, May 2026) — nittikkin.medium.com
- Temporal: determinism, Worker Versioning, patching — docs.temporal.io, temporal.io/blog, learn.temporal.io
- Temporal $300M / $5B, AI-native action volume — learn.temporal.io / press Feb 2026
- AWS Step Functions versions & aliases (immutable revisions, execution pinning) — docs.aws.amazon.com
- Dagster software-defined assets vs task DAGs — dagster.io/blog/software-defined-assets, docs.dagster.io
- Nextflow cache & resume; non-deterministic input cache invalidation — nextflow.io/docs
- Airflow backfill idempotency, --reset-dagruns, streaming/backfill partition collision — risingwave.com, oneuptime.com, ml4devs.com
- Deterministic replay for AI agents / missing primitives — sakurasky.com, zylos.ai
- OpenAI Agents SDK / Pydantic AI / LangGraph durable execution as baseline — render.com, docs.langchain.com
