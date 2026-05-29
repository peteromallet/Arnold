# Committed Unknown-Unknowns — Vantage: Identity & Evolution of Living Pipelines

> We ARE building Arnold's full vision. This brief does not question the bet. It
> hunts the identity/versioning/dependency hazards that will bite us while building
> it RIGHT — pipelines, pieces, prompts, and the SDK surface all evolving while runs
> are in-flight and modules depend on each other.

## Where today's code actually stands (grounding, not a critique of scope)

The seeds of the problem are already visible and already half-wrong, which is exactly
why this vantage is dangerous — we *think* we have versioning, and we don't:

- `Pipeline.builder(..., pipeline_version: int = 1)` exists
  (`megaplan/_pipeline/types.py:255`, `megaplan/_pipeline/builder.py:98,108,254`).
  But it is **never persisted to state and never read at resume**. Grep for
  `pipeline_version` outside `_pipeline/` returns nothing. It is a dead integer that
  *looks* like a version contract. This is the most dangerous kind of artifact: a
  named field that lulls everyone into believing identity is handled.
- Resume re-enters a stage **purely by name**: `resume_cursor.phase` is looked up in
  `pipeline.stages` by string and re-entered (`docs/pipeline-resume.md:6-9,49-53`).
  There is **no check that the pipeline graph, the stage's Step, or its prompt are
  the same artifacts the run started under**. A run started Tuesday resumes Thursday
  against whatever the registry now hands back for that name.
- Prompts — the single most behavior-determining artifact in a P-E-V harness — live
  in a **global mutable singleton** `_GLOBAL_REGISTRY` (`megaplan/_pipeline/prompts.py:90-100`)
  with last-writer-wins `register()` (line 48-49) and **no collision detection, no
  content hash, no provenance**. Two packs registering the same key silently shadow
  (FOUNDATION_03 flags "two packs register the same prompt key" as an open question).
- Content-hashing exists, but only in the **storage/migration** layer — file-tree
  snapshots in `store/legacy_migration.py:39-54` and `receipts/schema.py:25`
  (`schema_version: int`). We hash the *bytes a run produced*. We do **not** hash the
  *behavior a run was produced by* (graph topology + Step code + prompt text + model
  routing + invariant set). The durable, content-hashed, journaled foundation hashes
  outputs, not the generating function.

So the foundation has the *mechanism* for identity (sha256, journaling) pointed at the
wrong noun. That mismatch is the spine of every U-U below.

---

## Unknown-Unknown 1 — Behavioral identity ≠ signature identity ≠ content identity. We only have a name.

**Insight.** A pipeline/piece has at least four distinct identities that we are
currently collapsing into one string name:
1. **Name** — `"planning"`, the registry key. What we route on today.
2. **Structural hash** — the graph: stages, edges, Step *classes*, prompt *keys*.
3. **Behavioral hash** — what it actually *does*: the structural hash PLUS the prompt
   *text*, the model routing table, the invariant set, the SDK version it compiled
   against. Two pipelines with identical graphs but different prompt bodies are
   *different functions* and will produce different plans.
4. **Provenance/taint identity** — who/what authored it (human vs a model emitting a
   data-defined topology) and what tainted inputs flowed through it.

Semver of a *signature* (does it still have stage `execute`?) is cheap. Semver of
*behavior* (does `execute` still mean what it meant?) is the thing that bites, and
it's the thing nobody can compute mechanically because prompt edits, model swaps
(cheapest-capable-model routing changes the model *under* a pinned pipeline!), and
invariant changes are all invisible to a structural diff. The killer: **the routing
layer mutates behavior without touching any version.** A pipeline pinned to version
`v3` whose `execute` stage gets re-routed from Opus to a cheaper model when a price
table updates is now a *different behavioral artifact under the same hash* — and we
have no name for that drift.

**Why it's invisible to us.** We named the field `pipeline_version: int` and moved on.
An integer counter implies behavior changes are discrete, intentional, and authored.
But in a self-improving, AI-authored, cheapest-model-routed system, behavior changes
are *continuous, emergent, and authored by the runtime itself*. The version field
assumes a world (humans bumping ints on deliberate edits) that this platform explicitly
is NOT — and the gap is hidden precisely because the field *exists* and looks done.

**What it threatens.** Reproducibility, the self-improvement loop, and trust. The
self-improving harness's whole premise is "this change made plans better." If we
can't pin the *behavioral* identity that produced run A vs run B, every A/B claim is
noise — the model could have silently changed under both. The flagship tenant
(megaplan) becomes un-auditable: "why did this plan come out different from last
week's identical-looking run?" has no answer. And AI agents composing new pipelines
on shared pieces will reference a name whose behavior drifts beneath them.

**Severity: could-sink-the-build.** This is the foundation's load-bearing noun being
wrong. Everything content-hashed, journaled, and self-improving rests on it.

---

## Unknown-Unknown 2 — Resume-into-a-new-version: the in-flight run is a process whose code can change mid-execution.

**Insight.** A long P-E-V run, a chain, an epic, or a standing/interactive process is
a *suspended computation* that resumes against live, mutable definitions. Today resume
is "look up the stage name in the *current* registry and re-enter"
(`docs/pipeline-resume.md:49-53`). There is no version pinning of the in-flight run to
the pipeline/pieces/prompts it began under. The moment Arnold supports standing
processes and emergent graphs that live for days/weeks, the probability that the
underlying pipeline, a piece it composes, or a prompt got edited *during* the run's
lifetime approaches 1.

The subtle, un-named hazards inside this:
- **Partial-version runs.** Stages 1-4 ran under behavioral hash `H1`; an edit lands;
  stages 5-8 run under `H2`. The plan artifact is now a chimera no single version ever
  produced — and the resume contract has no concept of "this run is pinned to `H1`,
  refuse-or-migrate if the live def is `H2`."
- **The graph topology itself changed.** Resume keys on stage *name*. If an edit
  renamed `critique_a`→`critique`, removed it, or rewired its edges, resume either
  KeyErrors (loud-but-late, mid-run) or silently re-enters a stage whose *meaning*
  changed (catastrophic). For AI-emitted topologies this is routine, not exotic.
- **State-shape drift.** `state_patch` is merged blindly via `state.update(dict(...))`.
  A new pipeline version that expects a `state` field the old run never wrote (or
  whose meaning changed) has no migration hook — there's no codemod surface for
  in-flight state, only the offline `store/legacy_migration.py` for *completed* plans.

**Why it's invisible to us.** The resume design was written for a world where you
crash and resume *the same process within minutes* (`docs/pipeline-resume.md:49-53`
emphasizes idempotency for crash-replay). We mentally model resume as "crash recovery,"
which is short-horizon and same-code. The vision's standing/interactive/emergent
processes make resume a *long-horizon, cross-version* operation — and that reframing
hasn't propagated into the design because "resume" still *sounds* like crash recovery.

**What it threatens.** Every long-lived primitive in the vision: standing processes,
loops, emergent graphs, multi-week epics, cloud runs that "outlast a local terminal."
These are headline capabilities. If resume can't survive a definition edit, then the
durability story ("journaled, resumable foundation") is true only for runs shorter
than the edit cadence — which for a self-improving platform is *fast*. Self-improvement
and durability are in direct, undesigned-for tension.

**Severity: reshapes-architecture.** Requires a version-pinning + in-flight-migration
model that the executor, state model, and resume cursor must all be co-designed around.

---

## Unknown-Unknown 3 — Diamond-dependency hell over shared pieces, with no resolution policy and a global mutable namespace.

**Insight.** "Composed from shared pieces" + "modules depend on each other" + a global
prompt registry with last-writer-wins (`prompts.py:48-49,90`) is a classic dependency
diamond waiting to happen, and we have *zero* resolution machinery:

- Pipeline `A` composes piece `P@v2`; pipeline `B` composes `P@v3`; a meta-pipeline or
  emergent graph composes both `A` and `B`. Which `P` is live? Today: whichever
  registered last into the global singleton. Silent. Non-deterministic across import
  order (`FOUNDATION_03` already flags name-collision precedence as unresolved between
  builtin / discovered / `~/.megaplan/pipelines/` user packs).
- **Transitive prompt/Step shadowing.** Because prompts resolve by string key against
  one global dict, an unrelated pack that registers `"critique"` silently changes the
  behavior of *every* pipeline whose Step has `prompt_key="critique"` and no
  pipeline-scoped override. There is no isolation boundary. The Port spine
  (type+version+provenance+taint) is supposed to make composition *safe*, but prompts —
  the highest-leverage behavioral input — flow through a namespace with none of those
  four attributes.
- **No "can these two versions coexist?" predicate.** We have no behavioral-compat
  relation. We can't answer "does `P@v3` satisfy the contract `A` depends on?" because
  the contract is the *behavioral* identity from U-U 1, which we don't compute.

**Why it's invisible to us.** The current scale hides it. With one flagship tenant
(megaplan) and a handful of pipelines, import order is effectively fixed and collisions
don't happen, so the global singleton *looks* adequate. Diamond dependencies only
materialize once "others — and AI agents — build new pipelines on the same pieces" at
volume. We are extrapolating from a single-tenant present where the bug is dormant. The
mutable global is a scaling landmine that is invisible because nothing has stepped on it
*yet*.

**What it threatens.** The core "shared pieces, safe composition" thesis — the spine of
the platform. Multi-tenancy, AI-authored topologies at scale, and the marketplace-of-
pieces ambition all assume composition is deterministic and isolated. A last-writer-wins
global namespace means composition is order-dependent and leaky: tenant B's pack can
silently alter tenant A's plans. That's not a bug, it's a *security and correctness
boundary* failure that becomes a tenant-isolation incident.

**Severity: could-sink-the-build.** Safe composition is named as "the spine." A global
mutable, unprovenanced, last-writer-wins registry is a spine made of soft cartilage.

---

## Unknown-Unknown 4 — Orphaned modules and the SDK-surface compatibility horizon: who can still run a run authored last year?

**Insight.** Two slow-burn identity hazards that compound:
- **Orphaned modules.** When a piece is deprecated/deleted but in-flight runs, journaled
  history, or AI-emitted topologies still reference it by name, the reference dangles.
  Today a deleted pipeline name just isn't in the registry → KeyError at lookup, with no
  tombstone, no "this was `P`, superseded by `P'`, migration available" record. Journaled
  history that points at a now-gone behavioral hash is un-replayable — the journal
  promises replay but the *function* it replays is gone.
- **SDK-surface as a versioned artifact.** The `Step` Protocol, `StepResult`/`StepContext`
  shapes, `Edge.kind`/`GateRecommendation` literals (`types.py:74-219`) are *the SDK that
  every piece compiles against*. The module docstring literally says these are "frozen at
  end of Sprint 1" — but the vision is a platform where AI agents author pipelines against
  this surface *indefinitely*. The moment we add a `Step.kind` literal, change `StepResult`,
  or tighten `StepContext.state`, every previously-authored (and stored, and in-flight)
  artifact has a compatibility relationship with the SDK that produced it. We have a
  `schema_version: int` for receipts (`receipts/schema.py:25`) but **no SDK/ABI version on
  the pieces themselves**. A piece authored against SDK `v1` running on engine SDK `v4` is
  the classic "binary built against old headers" problem — and it's invisible until a field
  it relied on shifts meaning.

Note `project_dogfood_engine_shadow_and_openrouter.md` already records a *real instance* of
this class: a worktree's megaplan ran as the engine, so editable-install fixes didn't apply —
the run executed against a *different SDK/engine version than the operator believed*. That's
the SDK-compat horizon biting in miniature, today, and it was confusing enough to warrant a
memory entry.

**Why it's invisible to us.** "Frozen at end of Sprint 1" is a sprint-local promise that
reads as a *permanent* guarantee. We froze the shapes once and stopped thinking about the
fact that a platform's SDK is *never* frozen — it evolves forever, and every artifact ever
authored against it has a lifetime compatibility obligation. We're not seeing it because we
have ~5 internal pieces all authored against the current SDK simultaneously; the version
skew between author-time-SDK and run-time-SDK is currently always zero.

**What it threatens.** Long-term platform durability and the journaled-replay promise. A
content-hashed journal that promises "we can replay any past run" is *false* the day the SDK
the run compiled against is gone and no compat shim exists. For an AI-authored ecosystem, the
graveyard of orphaned pieces and SDK-skewed artifacts grows monotonically; without tombstones,
codemods, and an SDK-compat matrix, the platform accretes un-runnable history — the opposite
of the durable foundation we're promising.

**Severity: worth-designing-for** (escalates to reshapes-architecture once external/AI authors
outnumber internal ones — design the seam now while it's cheap).

---

## THE ABSTRACTION WE HAVEN'T NAMED

### The **Behavioral Identity Manifest** (the "Bom" / pipeline genome)

Today our unit of identity is a **name** (a registry string) and our content-hashing is
pointed at **outputs** (file-tree snapshots, receipts). The vision needs a first-class,
content-addressed, immutable **Behavioral Identity Manifest**: the closure of *everything
that determines what a composed artifact does*, hashed into a single behavioral fingerprint
and pinned to every run.

A Manifest binds, as one content-hashed value:
- the **graph topology** (stages, edges, kinds);
- the **Step code identities** (hash of the implementation, not just the class name);
- the **resolved prompt bodies** (text, not keys — closing the global-registry leak);
- the **model-routing decision** actually taken (so cheapest-capable-model drift is *recorded
  as a version event*, not hidden);
- the **invariant/Port set** in force (type+version+provenance+taint of every Port);
- the **SDK/ABI version** the pieces were authored against;
- the **resolved dependency closure** (the exact `P@hash` of every composed piece — making
  diamonds *detectable and refusable*, not silently last-writer-wins).

With a Manifest:
- **Reproducibility** = "re-run Manifest `H`" — the self-improvement loop gets a denominator.
- **Resume** = "this in-flight run is pinned to Manifest `H`; the live definition is `H'`;
  policy = {pin / refuse / migrate-via-codemod}" — resume becomes a *version-aware* operation,
  not a name lookup.
- **Diamonds** = a Manifest either resolves to a single consistent dependency closure or it is
  *rejected at compose time* with the conflict named.
- **Orphans** = a deleted piece leaves a **tombstone Manifest** so journaled history stays
  introspectable and replay can say "superseded by `H'`, codemod available" instead of KeyError.
- **Behavioral semver** = computed by *diffing two Manifests* — finally a mechanical answer to
  "did behavior change?" that includes prompt and routing drift, not just signature.

The Manifest is the noun the durable/content-hashed/journaled foundation was *built to hash*
but is currently pointing at the wrong object. Name it, make it the unit the scheduler pins
runs to, the unit the registry resolves, and the unit the journal records — and U-U 1-4 all
collapse from "emergent hell" into "a manifest diff + a resolution policy." Leave it unnamed
and we will keep shipping `pipeline_version: int` fields that are dead on arrival because an
integer cannot fingerprint a continuously-self-modifying behavioral closure.
