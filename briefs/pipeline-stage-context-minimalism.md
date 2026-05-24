# Brief: Per-stage context minimalism in the planning pipeline

**Status:** ANALYSIS — VERIFIED 2026-05-24 by an 8-wide DeepSeek V4 Pro fan (one agent per stage,
each reading the real prompt-builder + handler). Maps every stage, what its single prompt sees vs.
needs, and a ranked action list (§5). **One earlier survey finding was overturned** — review's
single-worker path is *starved* of the diff, not bloated by it (§3). All file:line below are
confirmed reads.
**Authors:** Claude (orchestration) + DeepSeek V4 Pro panel (per-stage verdicts); decisions by Peter.
**Related:** touches `prompts/*`, `_pipeline/*`, `handlers/*`. Adjacent to
[[project_planning_pipeline_unification]] (planning-as-pack) and the fan-out primitive brief.

---

## 0. The one framing that matters

Each pipeline stage is a **separate, fresh worker invocation** — not turns in one accumulating
conversation. So the thing to minimize is the **per-prompt size of each stage**, *not* repetition
*across* stages. "The plan is forwarded to four stages" is four independent agents that each
genuinely need the plan — that is the architecture working, not waste. Discount any "200–500 KB
moved across the pipeline" framing accordingly; it conflates cross-stage reuse (fine) with
per-prompt bloat (the real target).

---

## 1. The pipeline

Nine stages. Defined in `megaplan/_pipeline/planning.py:24-123`.

```
prep → plan → critique → gate → revise → finalize → execute → review
                  └──────── iterate loop ────────┘         (+ tiebreaker subloop)
```

| # | Stage | Kind | What it does |
|---|-------|------|--------------|
| 1 | **prep** | produce | Inspect codebase + task live, emit engineering brief (`prep.json`) |
| 2 | **plan** | produce | Turn brief into a markdown implementation plan |
| 3 | **critique** | judge | Run structured checks against the plan, flag concerns |
| 4 | **gate** | decide | proceed / iterate / escalate / tiebreaker; settle decisions |
| 5 | **revise** | produce | Rewrite the plan per critique + gate feedback |
| 6 | **finalize** | produce | Decompose approved plan into a task DAG (complexity scores, sense-checks) |
| 7 | **execute** | produce | Run the tasks in batches |
| 8 | **review** | judge | Verify execution against criteria, emit verdict |
| 9 | **tiebreaker** | subloop | Human-driven resolution of constraint tensions |

---

## 2. Shared plumbing

- **`StepContext`** (`_pipeline/types.py:134-148`) — frozen dataclass handed to every stage:
  `plan_dir`, full `state` dict, `profile`, `mode`, `inputs`, `budget`.
- **Shared prompt builders** (`prompts/_shared.py`): `_render_prep_block` (plan/execute),
  `_gate_summary_or_skipped` (gate/revise/execute/review), debt blocks
  (`_planning_debt_block` / `_gate_debt_block` / `_grouped_debt_for_prompt`).
- **Nested-harness guard** prepended to every prompt (`prompts/__init__.py`).
- **Intent block** `intent_brief_reference(state)` re-rendered in ~7 stages (small).

---

## 3. Per-stage findings (verified by 8-wide DeepSeek V4 Pro fan, 2026-05-24)

One DeepSeek subagent per stage read the actual prompt-builder + handler and judged
SEES / NEEDS / GAP. Verdicts below; all file:line are confirmed reads, not the earlier survey.

| Stage | Verdict | Highest-value finding | Conf. |
|-------|---------|------------------------|-------|
| prep | right-sized | 12-step investigation list (`planning.py:348-360`) → ~6 steps + a scope-bound line; harness guard is dead weight (no execute tools) | high |
| plan | **over-fed** | `PLAN_TEMPLATE` is 63 lines w/ two fully-worked example plans (`planning.py:90-153`) — invariants already stated in prose at :147-151; cut to ~10-line schema. Also 20-ticket block → top-5 | high |
| critique | over-fed | Full plan metadata JSON dumped *alongside* its already-extracted structure_warnings (`critique.py:138,215-218`); full debt registry where a 2-line "don't re-flag" directive suffices (`_shared.py:138-152`) | high |
| gate | over-fed | Full plan text into a *decision* stage (`gate.py:83`) — outline would do (medium conf); **triple** unresolved-flags representation, same `flag_registry` 3× (`gate.py:93`, `evaluation.py:724,798`); debt duplicated from signals | 85% |
| revise | over-fed | Full plan metadata (`critique.py:81-82`) ≈80% dead — needs only `success_criteria`; full `gate.json` where `{recommendation, rationale, flag_resolutions}` is the only signal | 85% |
| finalize | right-sized, leans over-fed | Plan-metadata dump (`finalize.py:76`) redundant w/ plan prose. Note: `_finalize_debt_block` (`_shared.py:171-178`) is **defined but never called** — finalize sees no debt for watch_items | med |
| execute | **over-fed (non-batched path only)** | `_execute_prompt` dumps entire `finalize.json` + full plan meta + full `review.json` (`execute.py:418,424,429`); the **batched** path `_execute_batch_prompt` is already well-scoped. Non-batched is a legacy "dump everything" that predates batching | high |
| review | over-fed (NOT starved — agent's "starved" verdict corrected) | see "Review" note below | high |

### Review: the two paths differ, but neither is starved (corrected 2026-05-24)
The DeepSeek agent flagged single-worker review as "starved of the diff." **That was wrong** — it
read the prompt-builder but not the worker's toolset. The single-worker review is *agentic*:
- `workers/hermes.py:312` — *"Gate and review get file only (judgment, not investigation)"* → review
  **has the `file` toolset** (`read_file`/`search_files`).
- `collect_git_diff_summary` (`review.py:525`, `_core/io.py:981`) returns `git status --short` (or a
  `--stat` branch summary) — i.e. **the list of changed files** + per-task evidence/commands in
  `finalize.json`/`execution.json`.
- The prompt instructs pull-on-demand (`review.py:614`): *"Trust executor evidence by default. Dig
  deeper only where the git diff … make the claim ambiguous."*

So single-worker review is a deliberate **pointer + evidence + tools** design (worker opens changed
files itself), not a prompt that withholds the diff. That is *good* minimalism.

What survives is only an **inconsistency between the two paths**: single-worker *pulls* the diff
(summary + `file` tool), while the parallel per-check path *inlines* the full
`collect_git_diff_patch` to every check-worker + criteria-worker (`review.py:141`,
`parallel.py:125-149`) — ~5× duplication. If anything the parallel push is the weaker choice; the
single-worker pull is the model to converge toward, not away from.

**Lesson for this brief:** a "what's in the prompt" audit is incomplete without checking the worker's
toolset — an agentic worker with `file`/`terminal` tools is *meant* to pull detail on demand, so a
slim prompt is a feature, not starvation.

---

## 4. Cross-cutting patterns

The eight verdicts collapse into a few repeated shapes, not eight unrelated nits:

1. **"Dump the whole JSON when a slice would do."** The single most common pattern — appears in
   critique, revise, finalize, and review: the full `plan.meta.json` and/or full `gate.json` are
   `json_dump`-ed when the worker uses only `success_criteria` (or `{recommendation, rationale,
   flag_resolutions}`). Each is a small, local edit.
2. **The plan prose already narrates its own metadata.** success_criteria / assumptions / questions
   live in the plan markdown the worker is already reading — dumping the meta JSON on top is
   redundant in finalize, revise, critique.
3. **Static instruction blocks sized for the worst case.** `PLAN_TEMPLATE` (63 ln),
   `_EXECUTE_OUTPUT_SHAPE_EXAMPLE` (~45 ln), prep's 12-step list, the harness guard on
   JSON-only/non-executing workers — all compressible with no signal loss.
4. **Non-batched execute path is legacy.** The batched path already does the right thing; the
   non-batched one inherits "dump everything."

What held up from §0: the fresh-worker framing was right — *no* agent flagged cross-stage reuse as
waste. Every real finding is about a *single* prompt carrying more (or, for review, less) than its
own job needs.

---

## 5. Ranked action list

**Caveat that re-scopes everything below:** review/gate/execute workers are *agentic* (they have the
`file` tool, sometimes `terminal`). So "bloat" here means **data pushed into the prompt that the
worker neither uses nor needs pushed** (it could pull it) — pushing unused JSON is still waste. But
do NOT read a slim prompt as starvation: an agentic worker is meant to pull detail on demand.

**Tier 1 — clear cost wins, low risk (no correctness bug found)**
- The "slice not whole-JSON" edits: `success_criteria`-only in revise (`critique.py:82`) & finalize
  (`finalize.py:76`); `{recommendation,rationale,flag_resolutions}`-only gate.json in revise/finalize;
  same for review's pushed `latest_meta`/`gate`/`execution` dumps (`review.py:596,599,604`).
- Execute non-batched: route single-batch runs through the batch-scoped builder, or trim the full
  `finalize.json`/`meta`/`review.json` dumps (`execute.py:418,424,429`) to the actionable slices.
- Review parallel path: trim the inlined `finalize.json` in `_parallel_review_context`
  (`review.py:146`) to `{tasks:[{id,status}], sense_checks:[{id}], success_criteria,
  baseline_test_failures}`; consider whether the full inlined patch should become pull-on-demand to
  match the single-worker path.

**Tier 2 — modest / cosmetic**
- `PLAN_TEMPLATE` 63 → ~10-line schema (`planning.py:90-153`); ticket block 20 → top-5.
- Gate: dedup the triple unresolved-flags representation; consider plan-outline vs full text (med conf).
- Critique: drop the redundant metadata dump; debt block → 2-line directive.
- prep: 12-step list → ~6 + scope bound.
- Decide on `_finalize_debt_block` — wire it in (so finalize watch_items see debt) or delete the dead code.
- Harness guard: skip or shorten for JSON-only workers.

**Open call for Peter:** no correctness bug survived scrutiny — this is all token-cost minimalism.
Tier 1 is a clean ~half-day of localized "slice not whole-JSON" edits. Worth a megaplan sprint, or
not worth the churn given these are agentic workers that can pull what they need anyway?
