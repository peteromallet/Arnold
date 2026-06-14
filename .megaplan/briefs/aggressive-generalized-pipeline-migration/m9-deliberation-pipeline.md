# m9 — Second-proof pipeline: the Deliberation Pipeline (boundary-ratifying external consumer)

## Why THIS pipeline (and why it replaces a self-built reducer)
A second pipeline only proves the substrate is general if it is a REAL pipeline we want
for its own sake, built by someone not optimizing to fit the API we already shipped. A
multi-judge reducer we author to prove our own point can't fail — it validates nothing.

The Deliberation Pipeline is the right consumer because (a) we genuinely want it — it is
the layered idea-refinement workflow we currently run by hand, and (b) it is emphatically
NOT planning-shaped (no execute/review/git/PR/success-criteria/tiers), yet it demands the
exact substrate features a reducer would dodge: **human-gate suspend/resume, profiles that
aren't `{agent,model,effort}`, plan-version lineage/replay, up-to-10 fan-out, and semantic
replay over LLM nondeterminism.** If this ports onto `arnold/` with ZERO megaplan imports,
the OSS-framework boundary is earned, not asserted.

This milestone runs under the SPI-forge rule (unchanged): build ONLY on public `arnold.*`;
every place you would fork/monkeypatch/copy-an-internal, STOP and promote it to real public
API. The pipeline is the demand; the SPI is what it pulls out of the substrate.

## What it does (the DAG)
Input: an `overall_idea` (free text).

1. **QuestionGen** — one high-abstraction agent (Opus-class) reads the idea and emits the
   *load-bearing questions* whose answers most determine direction, each with a one-line
   rationale and the asker's hypothesized answer. (Structured output.)
2. **HumanGate** — present the questions; the pipeline **SUSPENDS** and persists a resume
   cursor; it resumes when the human submits answers. *(Forces the generic suspend/resume +
   `HumanGateStep` from m8 — a reducer never exercises this.)*
3. **DraftPlan v0** — assemble an initial plan/direction from idea + answers.
4. **Three abstraction layers**, run in order — `high → mid → low`. For each layer L:
   - **Critique panel** — fan out **up to 10** critique agents at abstraction level L over
     the current plan. *(Forces a public, generic fan-out primitive — parallel scatter→gather.)*
   - **Skeptical synthesis** — one synthesizer applies a SKEPTICAL lens to the panel: it
     accepts / rejects / reframes each critique with judgment (NOT consensus), and emits
     plan v(n+1) plus a **changelog** (what changed, what was rejected and why). *(Structured
     output + judgment; non-deterministic.)*
   - **Checkpoint** — persist plan v(n+1) + the layer changelog as artifacts and journal
     events. *(Forces the m8 event journal + state-as-projection: the full v0→vN lineage is
     reconstructable by fold.)*
5. **Report** — at the end (and optionally per-layer), present the human a consolidated
   report: for each of the three layers, what the panel raised, what the skeptic
   accepted/rejected/reframed, and the resulting plan deltas.

"Abstraction level" (high = strategic/"is this the right goal", mid = architectural seams,
low = ground-truth mechanics) is a first-class **profile dimension that is not agent/model/
effort** — it selects panel composition + critique depth. This is the concrete pressure that
forces `arnold` profiles to be opaque/pluggable rather than agent-spec-shaped.

> Provenance: this is exactly the loop used to refine THIS migration plan — idea → load-bearing
> questions → human answers → high-level Opus review → skeptic → mid-level seam audit → skeptic
> → low-level ground-truth validators → skeptic → change report. We are productizing a workflow
> we already trust.

## Substrate features this forces public (the demand-pull targets)
- **Fan-out** — a public `arnold` scatter→gather over up-to-10 agents (today it's megaplan-internal).
- **Suspend/resume + HumanGateStep** — the human-answer pause (m8 must deliver this generically).
- **Opaque profiles + pluggable stage-config validator** — abstraction level ≠ `{agent,model,effort}`.
- **State-as-projection lineage** — plan v0→vN reconstructable by `fold_journal`; the changelog
  is event-sourced, not a side file.
- **Open control vocabulary** — loop over layers, conditional re-runs; no planning `STATE_*`.
- **Semantic replay** — deterministic *structure* with LLM nondeterminism inside; replay compares
  semantically (the m5 oracle work), since two runs won't be byte-identical.
- **`ContractResult`/artifact helpers + standard discovery hook** — registering this pipeline must
  not require copying megaplan boilerplate.

## Done criteria
- The Deliberation Pipeline lives under `arnold/pipelines/deliberation/` (or similar) and imports
  **zero `arnold.pipelines.megaplan`** — proven by the m6 runtime import test (clean venv, megaplan absent) AND the static leak gate.
- It runs end-to-end on real input: idea → questions → (human answers) → 3 layered critique passes
  (fan-out ≤10 each) → change report. A real human-gate suspend/resume cycle is exercised.
- Deterministic replay passes with **semantic** comparison (LLM outputs differ run-to-run; structure,
  ordering, and decision lineage must match).
- Every extension point it needed is now **public `arnold.*` API**, not a fork (list them in the PR).
- A real end-to-end test exists (the evidence_pack canary has none — do not repeat that).

## Locked decisions
- Built by the substrate's PUBLIC surface only; internals reached for become public API or the
  milestone isn't done.
- It must NOT import megaplan, and must NOT be contorted into planning shape (no execute/review/
  finalize/git stages). If the substrate forces a planning shape on it, that is a substrate bug to fix.
- The skeptical-synthesis step is judgment, not consensus: it may reject a majority of a panel.
