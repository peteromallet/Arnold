# Brief: Per-lens critique complexity routing (1–5 → profile, like execute)

**Status:** design v1 — ready for megaplan-prep
**Author:** 3-agent code-grounded investigation, 2026-05-30
**Related:** `.megaplan/briefs/prep-profile-driven-vendor-agnostic.md` (sibling vendor-agnostic-fanout work; supplies the `scatter_over_worker_step` substrate this brief reuses), `.megaplan/briefs/multi-agent-fanout-primitive.md` (the cross-vendor parallel-fanout epic)

## Problem

The critique evaluator **selects a per-lens model and the dispatch deliberately throws it away.** The evaluator emits `CritiqueSelection = {check_id, critic_model, why}` (`audits/critique_evaluator.py:250`), is prompted to route each lens to "the cheapest model that can do it justice, escalate to gpt-5.5 for hard lenses" (`prompts/critique_evaluator.py:382-415`), and the validator even rank/vendor-checks that `critic_model`. Then `handlers/critique.py:216` sets `critic_model_override = None` with the comment *"We deliberately do NOT read any per-lens `critic_model`."* — keeping only `check_id`.

**Observed consequence (empirically confirmed):** every lens runs on the single profile `critique` slot. A `partnered` M2 critique ran all 9 lenses as one hermes/deepseek-v4-pro process ($0.43, `model_actual=null`); the gpt-5.5 the evaluator "chose" for `correctness` appears only in `evaluator_verdict*.json`, never in an execution receipt. The elaborate per-lens routing is **write-only dead data.**

Lens *selection* (which lenses fire, steered by prep metrics) IS wired and works. Only model-per-lens is dead.

## Goal

Mirror execute's complexity routing for critique:

1. **The evaluator rates each selected lens `complexity` 1–5 + justification** (difficulty only — NOT a model name).
2. **The profile owns the score→model map** via `[profiles.X.tier_models.critique]`, exactly like `tier_models.execute`. The profile is the routing ceiling; `--vendor` and single-vendor profiles (`all-claude`/`all-codex`) route critique correctly with zero per-lens vendor strings.
3. **Each lens dispatches to its routed model in a vendor-agnostic parallel fan-out** — a gpt-5.5 `correctness` lens can run beside a deepseek `naming` lens, on claude/codex/hermes alike (today fan-out is hermes-only).

## Why this design (and why NOT just revive `critic_model`)

Reviving the evaluator's existing `critic_model` field is the smaller change but the **weaker design**: it hardcodes vendor names into evaluator output, so it ignores `--vendor` and the profile's ceiling — the same class of silent-misroute bug that motivated the prep work. The 1–5 approach **decouples difficulty (evaluator's job) from model (profile's job)**, which is why execute uses it. DECIDED: 1–5 → `tier_models.critique`. The `critic_model` field is removed, not kept as a fallback.

## What already exists (≈70% there)

- **The profile `tier_models` machinery is already phase-generic.** `_extract_tier_models`/`_validate_tier_models` (`profiles/__init__.py:304-382`) iterate any phase in `VALID_PHASE_KEYS = frozenset(DEFAULT_AGENT_ROUTING.keys())`, which **already includes `critique`** (`types.py:392`). So a `[profiles.X.tier_models.critique]` table **loads and validates today with zero code change.**
- **The fan-out primitives are model-agnostic.** `scatter_gather` (threads) / `scatter_gather_processes` (processes) in `_core/hermes_fanout.py:162,272` carry no model — the model lives in the caller's per-unit closure. They already permit per-unit models; only the *caller* pins one.
- **The score→model resolver is reusable with a one-arg generalization.** `_resolve_tier_spec(args, spec)` (`execute/batch.py:79-98`, dup at `handlers/execute.py:44-61`) hardcodes the literal `"execute"` (`batch.py:94`); it otherwise just calls `resolve_agent_mode(phase, args)`. Take a `phase` param → reusable for critique.
- **The hard-reject validation pattern exists.** Finalize's complexity validation (`handlers/finalize.py:264-275`: int 1–5 or reject, non-empty justification or reject, `bool` excluded) is the template to mirror for per-lens complexity.

## What's actually missing (the real work)

1. **No per-lens complexity producer.** The evaluator emits `critic_model`, not `complexity`. New: rate 1–5 + justification per selected lens.
2. **The critique fan-out caller pins one model AND is hermes-only.** `run_parallel_critique(model: str|None, ...)` (`orchestration/parallel_critique.py:165`) threads one scalar `model` to every lens (`:189-204`), and `_run_check` (`:33-86`) builds a hermes `AIAgent` directly (`:72-86`) — which is why the gate requires `agent_type == "hermes"` (`handlers/critique.py:378`) and claude/codex fall to a single-call else-branch (`:404-413`). Needs: per-lens model + a vendor-dispatching unit runner.

## Design

### Block A — producer + config (ships the routing decision; mostly mechanical)
- **Evaluator schema:** replace `CritiqueSelection.critic_model` with `complexity: int` (1–5) and `complexity_justification: str` (`audits/critique_evaluator.py:250-254`). Update `validate_evaluator_verdict` (`:284-584`): drop the rank/vendor gate on `critic_model`; add the finalize-style hard-reject for complexity (int in 1..5, non-`bool`; non-empty justification) — un-adjudicated lenses rejected/retried, never defaulted (a missing score may fail-safe to 5 = ceiling, matching `compute_batch_complexity`).
- **Evaluator prompt:** rewrite `prompts/critique_evaluator.py:382-415` from "pick the cheapest capable model / escalate to gpt-5.5" to "rate this lens's difficulty 1–5 against this rubric" (port the finalize rubric shape from `prompts/finalize.py:112-141`, incl. a FLOOR rule for high-stakes lenses). The model never names a vendor.
- **Profile tables:** add `[profiles.X.tier_models.critique]` to the profiles you want tiered (start with the ones that already carry `tier_models.execute`: `variable`, `partnered`, `premium`, `apex`, `all-claude`, `all-codex`). Reuse the execute ladders' shape (`all-claude`: haiku→sonnet→opus; `all-codex`: minimal→high effort). **No loader code change** — already validated by the generic path.
- **Resolver:** generalize `_resolve_tier_spec(args, spec)` → `_resolve_tier_spec(args, spec, *, phase="execute")`, threading `phase` into the `phase_model=["{phase}={spec}"]` line (`batch.py:94`) and `resolve_agent_mode(phase, ...)`. Collapse the `handlers/execute.py:44-61` duplicate onto it.

### Block B — extract the shared fan-out primitive + vendor-agnostic per-lens dispatch (the meat)

DECIDED (2026-05-30): this sprint is where the **shared `_core` fan-out primitive** is born — critique is its hardest first consumer (only critique needs per-unit *different* models), so it's the right place to define the general shape. Prep and review migrate onto it as follow-ups (see the fan-out epic). This consumes, not duplicates, dispatch.

- **Extract `megaplan/_core/worker_fanout.py`** — lift the *proven mechanism* from the prep-vendor-agnostic branch's `scatter_over_worker_step` (`orchestration/prep_research.py:240` on that branch: per-unit `AgentMode` → `run_step_with_worker` → claude/codex/hermes, `read_only=True`, caller-owned output path, fanned via `scatter_gather`/`scatter_gather_processes`). Generalize it: the branch helper hardcodes prep's prompt/parse and **pins one model per scatter** — make `resolved` (per-unit `AgentMode`), `prompt`, and `parse` per-unit/caller-supplied, with a pluggable `reduce` and thread|process `isolation`. Target shape:
  ```python
  @dataclass(frozen=True)
  class WorkerUnit:
      step: str; resolved: AgentMode; prompt: str; output_path: Path
      read_only: bool = True; extra: dict = field(default_factory=dict)
  def scatter_over_worker_step(units, *, state, plan_dir, root, parse, reduce,
      isolation="thread", max_concurrent=None, on_unit_error=None): ...
  ```
- **Per-lens routing in the caller:** rewrite `run_parallel_critique` to build one `WorkerUnit` per selected lens, each with `resolved = _resolve_tier_spec(..., phase="critique")` from `tier_map.get(lens.complexity)` — a DIFFERENT model per lens in the same scatter (correctness→gpt-5.5, naming→deepseek). A per-lens analog of the per-batch dispatch loop at `execute/batch.py:1103-1116` (simpler — lenses dispatch individually, no batch-max). Replace `_run_check`'s direct hermes `AIAgent` construction entirely with the new primitive.
- **Remove the hermes-only gate:** with a vendor-agnostic unit runner, `handlers/critique.py:378`'s `agent_type == "hermes"` condition collapses — claude/codex profiles fan out per-lens too, instead of one single-call. Keep the single-call path only as the genuine `len(active_checks) == 1` shortcut and the error fallback.
- **Out of THIS sprint (follow-ups, but design the primitive to serve them):** migrate prep (`run_research_fanout`) and review (`review/parallel.py` `_run_check` + `_run_criteria_verdict`) onto the same primitive; that retires the 4-copy Hermes scaffold and the review/prep collapse gates. The primitive's signature must accommodate prep's one-model-per-scatter and review's per-criterion units without change.

## Invariant output contract (MUST preserve byte-compatibly)
- Per-lens check artifacts and `evaluator_verdict*.json` keep their shape, MINUS the removed `critic_model` (PLUS `complexity`/`complexity_justification`). Audit any consumer of `selections[].critic_model` before removing it (grep; the investigation found only the validator reads it).
- Lens *selection* behavior (which lenses fire, prep-metric steering via `_render_prep_section`, `prompts/critique_evaluator.py:177-227`) is UNCHANGED. This brief touches only which model runs a selected lens.
- Critique receipts must now record real per-lens `model_actual` (today null/uniform) — that's the success signal, not a regression.
- The operator pin `execution.critic_model` (`pinned_critic_model`, applied uniformly `critique.py:312-342`) still forces one model for all lenses when set — it overrides tier routing, mirroring how `--phase-model execute=` disables execute routing.

## Anti-scope
- Do NOT touch execute's routing, finalize's scoring, or `compute_batch_complexity`.
- Do NOT change WHICH lenses fire or the prep-metric selection logic.
- Do NOT re-derive a fan-out primitive — reuse `scatter_over_worker_step`.

## Launch prerequisite (decided)
**Strongly prefer landing the `prep-vendor-agnostic` branch (commit `6e536827`) to `main` first** — it carries the proven `run_step_with_worker`-based vendor-agnostic dispatch that Block B lifts into `_core`, plus the codex `read_only`/Shannon read-only modes the per-lens runner needs. Landing it first gives Block B working code to generalize (per-unit model + prompt + parse) instead of writing dispatch from scratch, and avoids a `prep_research.py` / fan-out collision. It is **no longer a hard blocker** (this sprint owns the `_core` extraction either way), but skipping it enlarges Block B by the dispatch plumbing.

## Sprint shape
ONE megaplan, **`partnered` / full / `:high`, `--with-prep`**. Block B is now meatier — it extracts the shared `_core` fan-out primitive (the first slice of `.megaplan/briefs/multi-agent-fanout-primitive.md`) in addition to wiring per-lens routing — so the tier tracks that primitive-design difficulty. **`thorough` is a reasonable step-up** given the primitive is a cross-cutting foundation that prep+review will later depend on; pick it if the per-unit isolation boundary or the run_oneshot-vs-run_step_with_worker separation needs hardening. Block A still ships value alone (gets `all-codex`/`all-claude` critique onto their own ladders even before B lands the cross-vendor dispatch). Prep and review migration onto the new primitive are explicit **follow-up sprints**, not in this one.

## Done criteria
- A `partnered` critique run shows distinct `model_actual` per lens in the receipts (e.g. correctness on the ceiling model, naming on deepseek), matching the profile's `tier_models.critique`.
- `--vendor codex` on that run routes the premium lenses to gpt-5.x, not claude.
- `all-claude`/`all-codex` critique fan out per-lens within their own family (no DeepSeek pulled in).
- Single-lens and operator-pin paths unchanged; critique artifacts byte-compatible minus `critic_model` / plus `complexity`.
- Full test pass incl. new evaluator-complexity validation tests and a per-lens-routing test.

## Touchpoints
`megaplan/audits/critique_evaluator.py` (schema+validation) · `megaplan/prompts/critique_evaluator.py` (rubric prompt) · `megaplan/handlers/critique.py` (discard point :208-216, gate :378, dispatch) · `megaplan/orchestration/parallel_critique.py` (per-lens routing + vendor-agnostic unit) · `megaplan/execute/batch.py` + `megaplan/handlers/execute.py` (`_resolve_tier_spec` generalization) · `megaplan/profiles/*.toml` (add `tier_models.critique`) · `megaplan/_core/hermes_fanout.py` (reuse `scatter_over_worker_step`) · tests: `tests/test_critique*.py`, `tests/test_profiles.py`.
