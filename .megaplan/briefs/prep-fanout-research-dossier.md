# Prep-as-orchestrator: triage → fan-out → distill → plan

**Status:** design / not yet implemented
**Author:** design session 2026-05-24/25 (v3 — Peter's canonical 3-step PREP, after
two adversarial review rounds. Premise confirmed: research IS a significant
plan-quality bottleneck — see memory `project_research_bottleneck`.)
**Scope:** PREP becomes a 3-step internal pipeline; PLAN phase contract unchanged.

## One-line

PREP becomes a **three-step pipeline**: (1) a **triage** agent reads the task,
walks the code with tools, and outputs *only* the set of areas that merit deeper
investigation; (2) those areas **fan out** to up to ~10 DeepSeek subagents, each
with a brief on what to investigate; (3) a **distill** step reduces all their
findings into the prep output. The triage's own output **plus** the distilled
findings feed PLAN, which makes the decisions. PREP gathers evidence; PLAN judges.

## Motivation

Today research is **serial and duplicated across two single-agent phases**:

- **PREP** (`megaplan/prompts/planning.py:287` `_prep_prompt`) — one agent searches
  the repo (Glob/Grep/Read), traces call chains, writes `prep.json`. Can decide
  `"skip": true` for trivial tasks (`planning.py:335`).
- **PLAN** (`megaplan/prompts/planning.py:156` `_plan_prompt`) — consumes the brief
  but is *also* told to research itself (`planning.py:255-260`: "inspect the
  repository yourself… stop exploring once you have enough evidence").

So one agent does breadth-first investigation one tool-call at a time, then a
second re-investigates to fill gaps, *then* writes the plan — breadth bounded by a
single serial context window.

## The three PREP steps (+ PLAN)

**Step 1 — TRIAGE (route only).** One serial agent with read tools
(Glob/Grep/Read). It reads the task and walks the code, but its **only deliverable
is the list of areas that merit deeper investigation** — it does NOT produce the
findings itself. Output: a triage map of up to ~10 investigation areas, each with
a one-line "what to investigate / what to discuss" brief, plus a short framing of
the task as it now understands it (this framing is part of what feeds PLAN). The
triage owns routing, so it is the highest-leverage step — use a reasoning model,
and give it enough budget to walk the code, not a shallow skim (see Risks).

**Step 2 — FAN-OUT (investigate).** Each triage area becomes a brief dispatched to
its own DeepSeek subagent — **up to ~10 in parallel, one wave**. Each subagent
gets its brief (what to investigate, what to discuss) and read-only tools, runs a
full agentic investigation, and returns a finding
(`{area, brief, findings, files, code_refs, confidence}`). Briefs should ask for
relationships (caller/callee/interface), not just "list X."

**Step 3 — DISTILL / ADJUDICATE (reduce).** One step consumes all subagent
findings and distills them into the prep output — resolving overlaps, surfacing
cross-area connections, and flagging contradictions/gaps. This is the
"adjudicate" step: it weighs findings against each other, it doesn't just
concatenate them. **It also records the negative space:** areas that were explored
but yielded nothing meaningful (dead ends, ruled-out hypotheses, low-signal
lookups). This makes the dossier a complete record of the whole research process,
so PLAN knows what has *already been checked and dismissed* and doesn't waste its
budget re-investigating it. Negative results are signal, not noise.

**PREP output → PLAN.** The prep output = **triage framing + distilled findings**.
PLAN reads that and **makes the decisions** — it is NOT a summarizer. It chooses
the approach, writes must/should/info criteria with `requires`, assigns
complexity 1–5, sequences steps in PLAN_TEMPLATE, and decides ambiguity
(`question`) vs. default (`assumption`). PREP carrying the verbose gathering is
what lets PLAN spend its budget on judgment instead of investigation. PLAN keeps
a demoted escape hatch (`planning.py:257-260`) for genuine gaps only.

```
STEP 1 TRIAGE (serial, read tools)            PLAN (judge)
  read task + walk code                          read prep output ─► structured plan
  → up to ~10 areas, each w/ a brief             │   (triage framing + distilled findings)
  → + task framing                               └─ genuine gap? → targeted lookup (rare)
        │
        ▼
STEP 2 FAN-OUT (≤10 DeepSeek, parallel, one wave)
  each area-brief → subagent → finding
        │
        ▼
STEP 3 DISTILL/ADJUDICATE (1 reduce)
  weigh findings, connect across areas, flag gaps
  → prep output ───────────────────────────────►  (framing + distilled findings)
```

## De-risking: the must-fixes (load-bearing)

These came out of adversarial review and are NOT optional for v1:

- **Per-subagent wall-clock timeout.** `hermes_fanout.py:143` calls
  `future.result()` with no timeout. A network/tool stall hangs the whole wave.
  (`AIAgent` does cap `max_iterations=90` at `run_agent.py:769`, so it can't loop
  *forever* — but stalls still hang.) Add a wall-clock timeout; lower per-agent
  `max_iterations` for research.
- **No all-or-nothing failure.** `scatter_gather_checks` raises `CliError` if any
  slot is `None` (`hermes_fanout.py:160`). For research that contradicts
  "coverage over completeness." Return partial-result **sentinels**
  (`{status: timed_out}`), build the dossier from whatever completed, annotate
  the misses.
- **Actually read-only.** The `file` toolset includes `write_file`/`patch`
  (`hermes.py:376`) — subagents can write today. Add a real read-only toolset, or
  explicitly disable `write_file`/`patch` for research units.
- **Instrument everything.** Log cost, tokens, files touched, per-unit failures.
  For proving value, prefer **downstream** signals (critique flags for
  wrong-target/root-cause, revise cycles, execution failures from missing touch
  points, human-override rate) over "PLAN re-investigation rate" — round-2 review
  showed the latter measures *trust in the prep output*, not plan quality.

## How subagents are spawned and awaited

Plain Python threads — **no subprocess spawning, no async/await**. A "subagent" is
an in-process `AIAgent`, not a separate OS process. All three layers are proven in
the critique path:

1. **Spin up** — one `AIAgent` per unit (`parallel_critique.py:72-86`), isolated
   via `session_id=str(uuid.uuid4())`, own `session_db=SessionDB(db_path=…)`,
   `enabled_toolsets` (read-only for research), DeepSeek model from
   `_resolve_model(model)`.
2. **Dispatch** — `submit_check_fn(executor)` returns `executor.submit(worker, …)`
   Futures (`parallel_critique.py:188-203`); pool bounded
   `min(max_concurrency, num_units)` (`hermes_fanout.py:121-128`).
3. **Await** — `as_completed(futures)` collects in finish-order, accumulating
   cost/tokens (`hermes_fanout.py:143-155`). Inside each thread,
   `agent.run_conversation(...)` runs the *entire* agentic tool-loop, so we await
   a whole investigation, not one completion. `with_429_openrouter_fallback`
   (`parallel_critique.py:138`) handles rate limits.

**Reuse vs. new:** `scatter_gather_checks` is critique-shaped (hard-codes the
8-tuple + flag-union dedup, `hermes_fanout.py:150,168-170`). For research, extract
a thin generic `scatter_gather(units, worker_fn, *, timeout) -> list[finding] +
cost` with partial-failure tolerance, OR pass empties and ignore the flag output.
New per-unit worker `_run_research_thread` (research prompt → finding).

## What to build (v1)

1. **Triage prompt + step** — read task, walk code (read tools), output up to ~10
   investigation areas each with a one-line brief + a short task framing. Reasoning
   model with real budget to walk the code (not a shallow skim).
2. **Investigation-brief prompt** — "investigate <area>, discuss <brief>, report a
   relation-oriented finding."
3. **Generic `scatter_gather`** — bounded concurrency (≤10), per-subagent
   interrupt-based timeout, partial-failure sentinels, read-only toolset.
4. **Distill/adjudicate reduce** — weigh findings, connect across areas, flag
   gaps/contradictions → prep output.
5. **Prep output shape** — triage framing + distilled findings **+ an
   "explored, nothing meaningful" section** (areas checked and dismissed, with a
   one-line why). The dossier is a saved artifact summarizing the entire research
   process — positive findings AND negative space — not just what was found. Keep
   `prep.json` compatible (distilled index) so downstream is unchanged; richer
   detail incl. the negative-space section lives in the companion `prep_dossier.md`.
6. **Wire into the prep handler** — replace single `_run_worker("prep", …)` with
   triage → fan-out → distill → write artifacts. Triage-returns-0 = skip path;
   robustness level caps N.
7. **`prep_models` config** — optional `[profiles.X.prep_models]` sub-table
   (triage/fanout/distill); fall back to flat `prep` when absent. Resolve per-step
   model the same way `tier_models.execute` is resolved.
8. **Reframe PLAN prompt** (`planning.py:257-260`) → scoped gap-filler.
9. **Instrumentation** per the must-fixes (downstream metrics).

## Anti-scope (do NOT touch)

- **Do not change the PLAN phase contract or its outputs** (`plan_v{N}.md`,
  `plan_v{N}.meta.json`) beyond the one demoted escape-hatch reframe at
  `planning.py:257-260`.
- **Do not change critique/review behavior.** The shared `scatter_gather` is an
  *extraction* — the critique/review path must keep its existing 8-tuple +
  flag-union semantics and all existing critique tests must still pass. Refactor
  for reuse only; no behavior change there.
- **No multi-wave / adaptive research.** The only serial step beyond the single
  fan-out wave is the light cross-reference inside distill (Risks). Do not build
  a wave loop, convergence signal, or follow-up dispatch.
- **No decision-bound reframe.** This sprint builds breadth-first
  triage→fan-out→distill, not PLAN-drafts-hypotheses (recorded alternative only).
- Don't widen scope to the generic `fan_out(invoke,isolate,reduce)` primitive —
  build the research-specific `scatter_gather` only.

## Done criteria

- **Serial-equivalent preserved:** when triage returns 0 areas, prep behaves like
  today's `skip: true` (no fan-out; same downstream effect). Verified by test.
- **Existing critique/review tests pass unchanged** after the `scatter_gather`
  extraction.
- **3-step prep runs end-to-end** on a real task at `partnered`: triage emits
  areas → ≤10 subagents fan out → distill writes `prep.json` (+ companion dossier)
  → PLAN consumes it and produces a plan. Demonstrated on one real run.
- **`prep_models` resolution works:** absent the sub-table, all three steps use
  the flat `prep` model; present, each step uses its own; `--vendor codex` routes
  triage to `codex:high`. Verified by test.
- **Timeout is real, not cosmetic:** a stalled subagent is interrupted via
  `agent.interrupt()` (not just `future.result(timeout=)`); the wave completes
  from partial results with the miss annotated. Verified by test.
- **`file-readonly` toolset exists** and research subagents cannot `write_file`/
  `patch`. Verified by test (the aspirational `test_structured_output.py:126`
  assertion now passes).
- **Dossier records negative space:** the saved `prep_dossier.md` includes an
  "explored, nothing meaningful" section listing dismissed areas + why, so the
  artifact summarizes the whole research process, not only positive findings.

## Risks carried from review (mitigate, don't ignore)

- **Triage is the single point of failure** (DeepSeek A). It routes everything; a
  mis-framed triage faithfully fans out a bad map. Mitigation: give triage real
  read-budget (it's the one step that must not be cheap-skimped), and let the
  distill step flag "findings contradict the triage framing" so PLAN sees it.
- **Cross-area seams** (DeepSeek C). With ≤10 parallel subagents, the connections
  *between* areas belong to no single subagent and can't be manufactured by distill
  from findings that never surfaced them. Mitigations: (a) triage explicitly lists
  cross-cutting/integration areas as their own briefs; (b) give the distill step
  read tools so it can do a few targeted cross-reference lookups — i.e. distill is
  a light *serial* pass, not a pure text reduce. This is the narrow, bounded form
  of C's "serial second pass," without reopening full multi-wave.
- **Anchoring** (round-2 both metas): a rich prep output can make PLAN coast. PLAN
  prompt should present findings as *evidence to judge*, not settled conclusions.
- **Timeout is cosmetic without `agent.interrupt()`** (DeepSeek D) — see must-fixes.

## Rollout: this REPLACES the prep phase

The 3-step pipeline becomes *the* prep phase — not a gated alternative alongside
serial prep. There is one prep implementation that degrades gracefully:

- **Cheap/skip path is inside it.** Triage decides how many areas merit
  investigation; **0 areas = today's `skip: true`** (no fan-out, behaves like a
  trivial-task skip). So we don't maintain two prep implementations.
- **Robustness caps N.** The robustness level sets the max areas triage may fan
  out: low → cap ~2–3, high → cap 10. Same dial, one code path.
- Every robustness level still emits `prep.json` (honors "all robustness levels
  write the same artifacts"); only research depth changes.

Prove value on **downstream** quality signals (critique flags for
wrong-target/root-cause, revise cycles, override rate), not re-investigation rate.

## Model configuration: three slots, default one-for-all

Mirrors the existing `[tier_models.execute]` sub-table pattern. The flat `prep`
entry stays the fallback; an optional `[profiles.X.prep_models]` sub-table gives
each step its own model. If the sub-table is absent, **all three steps use the
flat `prep` model** (one-for-all, matching how `--phase-model execute=…` falls
back to the flat entry).

```toml
prep = "hermes:...deepseek-v4-pro"           # fallback / one-for-all

[profiles.X.prep_models]
triage  = "claude:high"                       # HIGH reasoning — load-bearing router
fanout  = "hermes:...deepseek-v4-flash"       # cheap, parallel, high-volume
distill = "hermes:...deepseek-v4-pro"         # mid reasoning — connects across areas
```

**This triage/fanout/distill split is the recommended default** surfaced by the
`megaplan-decision` skill: triage is the highest-leverage step so it runs at
**high** reasoning depth; fanout is the cost lever (flash × up to 10); distill
must weigh/connect across areas (mid reasoning). **Vendor follows the run:** under
`--vendor codex`, triage switches to `codex:high` (the premium-reasoning slot
tracks the chosen vendor, same as plan/critique do today). Fanout stays on the
cheap hermes/DeepSeek workers regardless of vendor.

## Deferred / rejected (recorded)

- **Multi-wave iterative research** — not in v1. The bounded exception is the
  light serial cross-reference in the distill step (Risks above); full adaptive
  waves stay deferred until data justifies them.
- **Decision-bound research** (Codex round-2 reframe: PLAN drafts hypotheses →
  fan out at uncertainty → adjudicate) — recorded as the main alternative shape.
  Peter chose breadth-first triage→fan-out→distill; revisit if breadth proves
  wasteful or anchoring shows up in practice.
- **Extract the generic `fan_out(units,invoke,isolate,reduce)` primitive up front**
  — deferred. Build the research-specific `scatter_gather` now; generalize when a
  second real consumer exists (`.megaplan/briefs/multi-agent-fanout-primitive.md`).

## Open questions

- N selection — triage picks up to ~10, but on what signal (task complexity, repo
  size, area count)? Hard cap at 10.
- Triage vs distill model tiers — triage is reasoning (load-bearing); does distill
  need reasoning to connect across areas, or is cheap fine?
- Prep output format — `prep.json` index + companion `prep_dossier.md`? How
  structured per area?
- Does distill need its own read tools (for the cross-reference pass), or is a
  pure text reduce enough?

## Review history

- **DeepSeek 5-lens panel** (cost, synthesis, reliability, YAGNI, decomposition)
  surfaced: blind-decompose flaw, synthesis bottleneck, no timeout, all-or-nothing
  failure, non-read-only toolset, multi-wave YAGNI, N× cost / no dedup.
- **Codex (GPT-5.5) adjudication**: SHIP-DE-RISKED. Verified the code claims;
  corrected the panel (the `max_iterations=90` cap exists; synthesis loss is
  mitigable, not "metaphysical"). Prescribed: scout pass first, single wave, N=2–4
  + seam unit, real read-only, timeout + sentinels, curated dossier, instrument
  PLAN re-investigation rate. This v2 incorporates that ruling.

### Round 2 (4 DeepSeek + 1 Codex on v2) — UNRESOLVED, design may need v3

- **Codex meta-lens (most penetrating):** the `PREP=evidence / PLAN=decisions`
  split is a FALSE DICHOTOMY and a local maximum. Planning is hypothesis-driven
  search — the decision determines what evidence matters. (a) The premise "more
  research → better plans" is UNPROVEN; the system already has 3 research
  checkpoints (prep, plan, critique-vs-repo). (b) "PLAN re-investigation rate"
  measures trust, not quality. Reframe to **decision-bound adversarial research**:
  PLAN drafts 2–3 candidate approaches → fan out only at the uncertainty behind
  each → synthesis returns "which hypothesis survives," not a dossier.
- **DeepSeek A+B (converge):** a scout good enough to ROUTE has already done half
  the investigation; fan-out subagents start cold (30–50% re-read tax), can't see
  across boundaries. Either make scout = PLAN agent at full budget, or DELETE
  fan-out (scout→plan) unless units are provably disjoint (no shared files/chains).
- **DeepSeek C:** relational loss UNSOLVED — a seam unit in the SAME wave as the
  part-finders is a category error. Needs a SERIAL second pass after findings
  return (contradicts v2 "single wave only"; narrow multi-wave is the structural
  minimum for cross-cutting analysis).
- **DeepSeek D (code-verified must-fix reality):** timeout is COSMETIC unless
  `agent.interrupt()` (`run_agent.py:6322`) is called + agent ref threaded through
  the submit path (~15 lines, 2 files) — else zombie threads burn tokens to
  `max_iterations`. `file-readonly` toolset doesn't exist (~5 lines to add; an
  aspirational test already exists). Partial-sentinel extraction is 50–70 lines
  (fork risk), not "thin." `max_iterations` already plumbed (0 code). PLAN
  re-investigation-rate telemetry doesn't exist — a new subsystem, not a checkbox.

**Resolution → v3.** Peter confirmed from domain knowledge that research IS a
significant plan-quality bottleneck (memory `project_research_bottleneck`),
closing the "validate the premise / delete PREP" path. He chose the breadth-first
shape over Codex's decision-bound reframe, specified as the 3-step PREP at the top
of this doc (triage → fan-out ≤10 → distill/adjudicate → PLAN). The surviving
review findings are folded in as must-fixes (D) and the Risks section (A triage
SPOF, C cross-area seams via a light serial distill, anchoring). Decision-bound
research is recorded as the main alternative if breadth proves wasteful.
