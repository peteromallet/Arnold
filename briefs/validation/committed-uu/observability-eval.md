# Committed-Vision Unknown-Unknowns — Observability & Eval as First-Class

Vantage: For a self-improving platform running long, AI-authored, composed
workflows, what does "see what happened / know if it's good / prove it improved"
demand as a *core abstraction*, not a bolt-on? We are 100% building Arnold. This
brief only asks how to build the observability/eval spine *right* and what will
bite if we don't.

## What exists today (grounding)

- **Per-plan `events.ndjson`** (`megaplan/observability/{events,trace,introspect,cost}.py`):
  an append-only journal of ~25 event kinds (lifecycle, subprocess, LLM heartbeat,
  artifact, cost, drift). The design doc (`docs/observability-and-introspection-design.md`)
  is explicit and correct: "build everything else as thin readers over it." But its
  framing is *liveness* — "what is it doing, why, since when, how to intervene." It
  is a present-tense operator console, not an evaluation substrate.
- **Receipts** (`megaplan/receipts/schema.py`): per-phase provenance with real
  content-addressing — `prompt_hash_canonical`, `upstream_artifact_hashes: list[str]`,
  `model_actual`, `cost_usd`, `verdict`, `canonicalization_version`. This is the
  closest thing to lineage. But `upstream_artifact_hashes()` is a **hard-coded
  if-ladder per phase name** (plan→[], critique→plan_vN, gate→critique_vN…). The
  lineage is hand-authored per built-in pipeline shape, not *derived from the actual
  Port-to-Port data flow* the pipeline primitive defines.
- **Epic events** (`megaplan/store/_db/events.py`): a DB journal with
  `pre_state_sha256` / `post_state_sha256` and canonical-JSON snapshots — genuine
  journaled, content-hashed foundation. But it is a *second, disjoint* journal at a
  different grain than `events.ndjson`, and neither cost.py nor introspect.py reads it.
- **Scores** are bare `PipelineVerdict.score: float` (`_pipeline/types.py`,
  `demo_judges.py`). No recorded identity of *which* scorer, *which* rubric version,
  *which* judge model produced the number. The score is a leaf value, not a
  reproducible, versioned, comparable object.

So today: liveness is first-class; lineage is partial and hand-wired; eval-as-data
is essentially absent. That gap is where the unknown-unknowns live.

---

## UU-1 — The eval verdict is unattributed and unversioned: "better" is uncomputable

**Insight.** A self-improving platform's central loop is "new version of a piece
beats old version." But a `score` is a float with no provenance. To compare two
runs you need: same rubric, same judge model, same judge prompt, same input
distribution — and you need to *know* they were the same. Today none of that is
recorded alongside the number. The scorer is invisible. When megaplan changes its
critique evaluator (and MEMORY shows this churns: "Static critique removed,"
"adaptive critique evaluator silently fell back to static," "KeyError critique_evaluator"),
every historical score silently changes meaning. You cannot tell a *real* quality
regression from a *measurement* regression. The platform improves itself against a
ruler that is itself drifting and unlabeled.

**Why invisible to us.** The live-observability work is so well-executed that it
*feels* like the eval story is covered — events, cost, traces, heartbeats are all
there. But every one of those answers "what happened," none answers "was the new
version actually better, and can I trust the comparison." The team's mental model
treats the score as ground truth rather than as the *output of a versioned program
that must itself be observed*. Judge-as-data is a category the current schema has
no slot for.

**What it threatens.** The privileged self-improving heart. If you can't attribute
quality to (piece-version × rubric-version × judge-version × input-set), then every
"we made routing/critique/planning better" claim is unfalsifiable, and the
self-improvement loop optimizes against a moving target — possibly Goodhart's-lawing
into the judge's blind spots. This is the deepest threat: a self-improving system
whose improvement metric is unversioned will confidently improve in the wrong
direction and have no way to notice.

**Severity:** could-sink-the-build.

---

## UU-2 — Lineage is hand-wired per pipeline shape; AI-authored topologies break it silently

**Insight.** `upstream_artifact_hashes()` enumerates lineage by phase *name*
(`if phase == "critique": return hashes of plan_vN`). This works because the
built-in planning pipeline's shape is known and stable. But the vision is
**AI-authored, data-defined topologies** — models *emit* pipelines with arbitrary
graphs, loops, and emergent edges. For any pipeline the model invents, the
phase-name if-ladder produces *empty or wrong* upstream hashes. Lineage will be
silently incomplete for exactly the pipelines the platform exists to host. The
Port abstraction (type+version+provenance+taint) is the natural carrier of true
data-flow lineage — provenance is literally in the Port — yet lineage is currently
recomputed from filenames instead of being *read off the Ports that actually
carried the data*. Provenance and observed-lineage are two implementations of one
truth that have been allowed to diverge.

**Why invisible to us.** The built-in `planning` pipeline is the flagship tenant
and the only one exercised hard, so the hand-wired ladder always looks complete in
practice. The failure only manifests on *foreign, model-emitted* graphs — which
don't exist yet at volume. We are validating lineage against the one topology where
the shortcut happens to be correct.

**What it threatens.** Replay-as-debugger and cost/quality attribution across
*composed* runs. When an emitted pipeline produces a bad output, "why did this
composed run produce this?" requires walking the real data-flow DAG. If lineage was
reconstructed from a planning-shaped assumption, the replay reconstructs a fiction.
Cross-piece attribution ("which composed-in piece caused the cost/quality change")
becomes impossible precisely when topologies get interesting. This reshapes the
foundation: lineage must be *emitted by the runtime as Ports are crossed*, derived
from the activation/scheduler model, not reconstructed by a reader.

**Severity:** reshapes-architecture.

---

## UU-3 — Two disjoint journals at two grains, and the surfaces read the wrong one

**Insight.** There are already *two* event logs — per-plan `events.ndjson`
(filesystem, ~25 kinds, presentation-oriented) and `epic_events` (DB, content-hashed
pre/post state, transaction/turn IDs, replay-ordered). They overlap conceptually but
share no schema, no ID space, no join key. `cost.py` aggregates by re-scanning
`events.ndjson` and *re-classifying vendor by substring* (`_classify_vendor`) rather
than reading a journaled, hashed cost record. The "build everything as thin readers
over the journal" principle is right — but it's already been violated by having two
journals and by surfaces that derive truth (cost-by-vendor) heuristically at read
time instead of recording it at write time. As pieces multiply and run *across*
plans/epics/standing-processes, a per-plan-file journal cannot express a run that
spans tenants, repos, or a long-lived interactive process. The grain is wrong for
the vision's scheduler model (DAGs *and* loops *and* standing/emergent graphs).

**Why invisible to us.** Each journal was built for its own immediate need (plan
liveness vs. epic durability) and each is locally excellent. Nobody owns "the one
journal," so the duplication is no single author's bug — it's an architectural seam
that only hurts when you try to ask a question that *crosses* the two, which day-to-day
megaplan use rarely does.

**What it threatens.** Every cross-cutting eval/lineage question the vision
promises: A/B across pipeline *versions* (which version, in which run, in which
journal?), attribution across pieces shared between tenants, replay of a standing or
emergent-graph process that has no single "plan dir." If observability is the spine,
two spines is no spine. Convergence late is a migration through every reader.

**Severity:** reshapes-architecture.

---

## UU-4 — Replay is journaled at the orchestration grain, but determinism stops at the model boundary

**Insight.** `list_epic_events_for_replay` and content-hashed pre/post state imply
replay-as-debugger. But the load-bearing work is non-deterministic LLM calls. The
journal records `prompt_hash`, tokens, cost, `request_id`, finish_reason — the
*envelope* — but not the **exact model output bytes** as a first-class, hashed,
re-injectable artifact keyed by `(prompt_hash, model_version, sampling_params, seed)`.
So you can replay the *control flow* (which phase ran, which edge fired) but you
cannot reproduce *why a given output happened* without re-calling a model that has
since changed (silently — providers version models behind stable names) and is
non-deterministic anyway. "Replay" therefore means two different things — orchestration
replay (have it) vs. observation replay / record-and-mock (don't) — and the gap is
invisible until you try to debug a one-year-old composed run whose model no longer
exists.

**Why invisible to us.** Replay reads as "done" because the epic journal is genuinely
replayable at its grain, and live runs reproduce "well enough" because the models are
still current. The decay is *temporal*: the gap only bites when the model behind a
stable name has drifted or retired — exactly the regime a long-lived self-improving
platform lives in, and exactly when you most need to re-examine an old run to prove
improvement.

**What it threatens.** "Prove it improved" over time, debugging historical regressions,
and any A/B that re-scores old outputs with a new judge. Without recorded, hashed,
re-injectable model I/O, the platform can never re-evaluate the past — it can only
ever compare the present to the present, which is amnesia disguised as observability.

**Severity:** worth-designing-for (becomes could-sink-the-build at multi-year horizon).

---

## The single biggest UNNAMED ABSTRACTION

**The Evaluand (a versioned, attributable judgment record) — and its dual, the
Ledger (one content-addressed observation log that every score, cost, and lineage
edge is *recorded into*, never recomputed from).**

Today the platform has a `score` (a float) and two `journals` (disjoint). It is
missing the thing in between: a first-class object that says *this judgment, by this
judge-version, against this rubric-version, over this input-set, produced this score
with this provenance, recorded here, comparable to that one.* The Evaluand makes
"is the new version better?" a **join over hashed identities** instead of a vibe over
floats. Its preconditions force the rest into place:

- A **judge/eval is itself a Port-typed piece** (type+version+provenance), so the
  scorer is content-hashed and versioned exactly like the things it scores —
  eval-as-a-pipeline-kind falls out for free, and a rubric change is a *visible
  version bump*, not a silent meaning-shift (kills UU-1).
- **Lineage is emitted by the runtime as Ports are crossed** and *is* the provenance
  field of the Port — one truth, derived from data flow, correct for any AI-authored
  topology (kills UU-2).
- **One Ledger** at the right grain (run/piece/port, spanning plans, epics, standing
  and emergent processes) that every surface reads and nothing recomputes — cost,
  quality, and lineage become recorded facts with provenance, not substring guesses
  (kills UU-3).
- The Ledger records **hashed, re-injectable model I/O** keyed by
  (prompt_hash, model_version, params), making the past re-evaluable — replay-as-debugger
  and re-score-the-past become real (kills UU-4).

Naming it changes the build: observability stops being "show me what's happening"
(an operator feature) and becomes "every fact this platform acts on — what ran, what
it cost, how good it was, and where the data came from — is a content-addressed,
versioned, journaled record that improvement is *proven against by join, not asserted
by vibe*." For a platform whose privileged heart is self-improvement, the Evaluand +
Ledger is not a feature of the spine — it *is* the spine. A self-improving system that
cannot version its own ruler does not improve; it drifts with confidence.
