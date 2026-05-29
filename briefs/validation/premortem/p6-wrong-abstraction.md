# P6 — Pre-mortem: pack-ification was the wrong abstraction

**Lens:** first-principles, steelman the alternative. **Date:** 2026-05-28.
**Premise under attack:** "a future Arnold tool = a discovered pipeline pack." The epic
(`briefs/pipeline-unification-EPIC.md`) treats "planning is one pack among many, first among
equals" as the technical substrate for Arnold. This document argues that frame is a **local
maximum** — it optimizes the thing megaplan already is (a planner) into a slightly more general
version of itself, and mistakes that self-generalization for a platform that serves Arnold's
*actual* next tool.

---

## 0. What a "pack" actually IS (from the code, not the brief)

A pack is a `Pipeline` (`megaplan/_pipeline/types.py`): a frozen `Mapping[str, Stage|ParallelStage]`
with an `entry` stage and labelled `Edge`s. Each `Stage` holds one `Step` (a `Protocol` with
`name / kind:{produce,judge,decide,subloop,override} / prompt_key / slot / run(ctx)->StepResult`).
The executor (`executor.py`) is a `while True` loop: run the entry step, read `result.next` /
`verdict.recommendation`, match an outgoing `Edge`, advance the cursor, terminate on `'halt'`.

So the pack model is, precisely: **a finite directed graph of agent-phases, walked one node at a
time, where every node is a render-a-prompt → dispatch-a-model → produce-an-artifact → emit-a-gate
verdict cycle, and control flow is static edges + a 4-value gate recommendation
(proceed/iterate/tiebreaker/escalate).** State is a single `state.json` dict threaded as
`StepResult.state_patch`. That is a beautiful fit for *one shape of work*: a bounded,
batch-oriented, single-tenant, agent-orchestration DAG with critique/gate loops. It is the shape
of planning, and of the demo packs (creative/doc), because those were all designed backwards from
planning.

## 1. What the real second tool looks like — and it is NOT a DAG

The repo already contains the answer, and it contradicts the premise. **Arnold is not
hypothetical.** `megaplan/schemas/arnold.py` + `megaplan/store/base.py` (1,354 LOC, a `Store`
Protocol with `Transaction`, `RevisionConflict`, `LockConflict`, `LeaseConflict`) describe the
actual second tenant. Its primitives:

- **Epics** with editorial `state` (`shaping/sprinting/planned/paused/archived`), `body_edit`s,
  `checklist_change`s, `sprints_change`s — an *event-sourced* entity with `get_epic_at_time(...)`
  time-travel and optimistic-concurrency `revision` conflicts.
- **Resident conversations** over a Discord transport (`ResidentConversationTransport`),
  inbound/outbound `MessageDirection`, **bot turns** with status
  `in_progress/completed/failed/abandoned`.
- **Control messages** (`put_control_message`, `claim_pending_control_messages`,
  `recover_stale_control_messages`, leases) — an inbox/queue with at-least-once delivery and
  stale-claim recovery.
- **Feedback**, **system logs** (`debug/info/warn/error` × category), **external API requests**
  with `pending/sent/confirmed/failed/orphaned` lifecycle, **code artifacts**, **images**.

This is a **long-running, interactive, multi-tenant, transactional, event-sourced service** — a
conversational agent with durable memory, an inbox it drains, a revisioned entity it edits in
place, and an audit log. Map that onto the pack contract and every joint cracks:

| Arnold reality | Pipeline/Stage/Edge assumption | Mismatch |
|---|---|---|
| Runs forever, reacts to inbound messages | DAG terminates at `'halt'` | The executor's whole telos is *finishing*. Arnold never finishes. |
| Control loop driven by external events (a Discord message, a control_message) | Control flow = static `Edge`s + 4 gate values | Edges can't model "wait for the next user turn." There is no `await-event` edge kind, and the gate vocabulary is critique-shaped. |
| State = revisioned rows in a `Store` with transactions + leases + optimistic-concurrency conflicts | State = one `state.json` dict, `state_patch` merged by the executor | `StepResult.state_patch` is a last-writer-wins dict merge. It has no transaction, no revision, no lease, no conflict. A `ParallelStage` is *explicitly forbidden* from touching shared state (the executor rejects an `InProcessHandlerStep` in a `ParallelStage`). |
| Edits one entity over its lifetime (body edits, checklist mutations) | Each Step *produces an artifact file* (`outputs: Mapping[label, Path]`, executor verifies existence) | The pack model is artifact-emitting (write `v{n}.md`), not entity-mutating. `EpicSnapshot.get_epic_at_time` has no analogue in `StepResult`. |
| At-least-once message delivery, stale-claim recovery, lease conflicts | `RuntimePolicy` knows stall/cost/escalate | The policy hooks are batch-job guards (is it stalled? over budget?), not delivery/concurrency semantics. |

The pack abstraction isn't *under-built* for Arnold. It is built for the **opposite shape of
problem**: terminating vs. resident, artifact-producing vs. entity-mutating, statically-routed
vs. event-driven, single-state-dict vs. transactional-store.

## 2. The three kinds of tool, and where the pack model lands

**Serves well:** bounded agent-orchestration DAGs with a critique/gate loop — planning, the doc
pack, the creative pack, a "writing panel," `epic-blitz`. Anything whose natural description is
"render prompt → call model → judge → branch → repeat until done." For these the Pipeline/Stage/
Edge shape is genuinely good and the unification is real value.

**Serves badly:** anything resident or interactive (Arnold's conversational core), anything whose
control flow is data- or event-driven rather than statically-edged, anything whose state needs
transactions/revisions/leases (the whole `Store`), anything that's a *service* rather than a
*job*. You can technically cram these in — a single-stage pipeline whose `Step.run` is a 2,500-line
event loop — but at that point the Pipeline wrapper is **decorative**: the `entry`/`edges`/`halt`
machinery does nothing, and all the real logic lives inside one opaque step. That is the
"contorted or bypassed" failure the pre-mortem names.

**Doesn't serve at all:** non-orchestration tools (a pure data export, a viewer, a daemon). These
wouldn't even pretend to be packs.

The tell from the *current* tree: the two existing non-planning packs (creative, doc) are, per
C6/c4 validation, **stubs that never dispatch a model** — `CreativeStep.run` just renders a prompt
to markdown and writes a file; `grep` for `resolve_agent_mode`/`run_step_with_worker`/`dispatch`
across both pack dirs returns *zero matches*. The only two "proofs" that the pack model is general
are packs that exercise none of the orchestration machinery. The genericity is **asserted, not
demonstrated** — and the one tenant we have real schemas for (Arnold) doesn't fit the shape at all.

## 3. Why pack-ifying planning optimizes for generality the real tool won't use

The epic spends its hardest, riskiest milestone (**m3**, "extreme/max", port the ~2,500-LOC
untested `auto.py` in-process) and a full milestone (**m5**, `HandlerContext`) and another (**m6**,
EvidenceRealizer) building *generality of the planning execution model*. But:

- The generality being built is **DAG generality** — pack-agnostic profiles (m2), one execution
  path for walking stages (m3), a typed context for *handler* dispatch (m5), pluggable *evidence*
  for *artifact-producing* steps (m6). **Every one of these is a generalization along the axis
  planning already varies on.** None of them adds an `await-event` edge, a transactional state
  backend, a resident control loop, or a lease primitive — the axes Arnold actually needs.
- u2 already established that two of those pillars (HandlerContext, Realizer) are
  contradicted-or-YAGNI by the validated code, and that the subprocess-reconstitution model makes a
  *second tenant make the collision worse, not better*. The pre-mortem extends this: the second
  tenant doesn't just stress the chosen abstraction, it **lives outside its domain**.
- This is textbook **local-maximum optimization**: we are climbing the "make the planner more
  general" hill because that's the hill we're standing on, and calling the summit "a platform."
  But Arnold's tool is in a different valley (resident services), and the pack hill doesn't connect
  to it. Worse: every milestone that hardens Pipeline/Stage/Edge as *the* extension seam raises the
  switching cost of admitting later that the real seam is lower (shared services) — we will have
  invested apex/extreme effort into making the wrong contract load-bearing.

## 4. The better abstraction: a thin shared-services layer that tools compose freely

Invert the dependency. Today: `Pipeline` is the top-level contract and everything must *be* a
pipeline to reuse anything. Instead, make the **reusable capabilities free-standing services**,
and let a pipeline be *one optional consumer* of them rather than the mandatory frame:

- **Worker dispatch** — `resolve_agent_mode` + `run_step_with_worker` + profile resolution, as a
  callable `dispatch(slot, prompt, profile) -> result`. (This is exactly the C6 fix: make
  dispatch pack-agnostic and fail-typed. It is valuable *on its own*, independent of packs.)
- **State/store** — the `Store` Protocol (already exists!) as the durable-state service, with the
  pipeline's `state.json` being just the *file* backend of that Protocol. Arnold uses the DB
  backend; planning uses the file backend; neither has to be a pipeline to get transactions.
- **Emission / receipts / event sink** — one hook (the c3/u1 consolidation), consumed by anything.
- **Evidence strategy** — the C5 "build the seam, skip the Protocol" object: an injected
  git-vs-prose evidence function, callable without a Pipeline around it.

Then a *tool* is just code that composes these. Planning composes them into a DAG walk (keep the
Pipeline runtime — it's good for DAGs!). Arnold composes them into a resident event loop over the
`Store`. **Neither is privileged; the shared layer is the platform, not the pipeline shape.** The
`_pipeline` registry becomes "the catalog of *DAG-shaped* tools," not "the catalog of all tools" —
an honest, narrower claim. This is the difference between "everything is a pipeline" (forces the
shape) and "everything can call the services" (shares the substance).

The crucial reframing: the genuinely load-bearing, reusable thing megaplan has built is **the
worker-dispatch + profile + emission + store machinery**, not the Stage/Edge/`halt` graph. The
epic bundles those together and calls the bundle "pack." Unbundle them, and the services survive
contact with Arnold while the graph shape does not.

## 5. The cheapest thing to do NOW to de-risk the bet

**Do not build the platform on a hypothesis. Make Arnold pull on the abstraction before m3.**

Concrete, cheap, this-week:

1. **Write a one-page "Arnold-as-a-pack" thought-spike** that tries to express Arnold's resident
   loop in the current Pipeline/Stage/Edge/`StepResult` vocabulary, using the *real* schemas in
   `megaplan/schemas/arnold.py` + `store/base.py`. List every primitive that has no home (await-
   event edge, transaction, lease, revision-conflict, resident loop, in-place entity edit). If the
   list is long (it will be), the pack frame is falsified *on paper, for free*, before any apex
   milestone is funded.

2. **Pull the one load-bearing pillar OUT of the pack frame and ship it standalone: pack-agnostic
   dispatch (m2 / C6, ~2–3.5 days).** This is valuable whether or not the pack abstraction is
   right — it's "make `resolve_agent_mode` not KeyError on an unknown slot + decouple
   `VALID_PHASE_KEYS`." Ship it as a *service Arnold could call directly*, not as a pipeline
   feature. If Arnold can dispatch a worker without being a pipeline, the thin-services thesis is
   proven and m3/m5/m6 can be re-scoped or deferred.

3. **Reframe `Store` as the durable-state service now (it already is a Protocol).** Make the
   pipeline's `state.json` an explicit *backend* of `Store` rather than a parallel state model.
   This is mostly naming/wiring, and it directly tests whether planning and Arnold can share state
   substrate without sharing the graph shape.

4. **Defer the irreversible commitments** — m3 (auto.py in-process port), m5 (HandlerContext), m6
   (Realizer Protocol) — until the spike (#1) or a real Arnold prototype (#2) demonstrates the pack
   frame survives contact with a resident tool. Per u2 these are already the low-value-per-risk
   milestones; the pre-mortem adds: they also bet apex effort on the abstraction *most likely to be
   wrong* for tenant #2.

Net: the de-risking is a **half-day paper spike + a 2–3-day standalone dispatch service**, against
which we can falsify "future tool = pipeline pack" *before* committing the extreme/max milestone.
The pack runtime stays — for DAG-shaped tools it's genuinely good. What we refuse to do is declare
it the universal tenant contract on the strength of two stub packs and zero resident tenants.
