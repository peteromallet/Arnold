# Brief: Profile-driven, vendor-agnostic prep research

**Status:** design v2 (post adversarial review) — ready for megaplan-prep
**Author:** investigation via 7-agent fan-out (4 design + 3 adversarial/structural), 2026-05-29
**Related:** `briefs/prep-fanout-research-dossier.md` (original prep-fanout design), `briefs/multi-agent-fanout-primitive.md` (the cross-vendor parallel-fanout epic — this brief is its first concrete consumer)

## Problem

Prep-research silently routes to DeepSeek regardless of profile. `all-claude`/`all-codex` pull DeepSeek into prep, violating their single-vendor promise and breaking for users without DeepSeek/Fireworks creds. Root cause is **structural, not a missing default**: prep hand-rolled its own dispatch and its own process-isolation runtime instead of using the harness's shared primitives, and the prep model comes from a hidden constant (`CANONICAL_PREP_MODELS`) instead of the profile.

## Goal

1. **prep_models is a first-class, profile-declared slot** (`triage`, `fanout`, `distill`). Whatever a profile declares, runs — on claude, codex, hermes, or any model.
2. **Fanout runs on any vendor with TRUE per-area parallelism** (not a degraded single call).
3. **New default policy:** every profile defaults prep to **DeepSeek-v4-pro**, EXCEPT `all-claude` → **`claude:claude-sonnet-4-6`** and `all-codex` → **`codex:gpt-5.4`** (each vendor's second-most-powerful — cost discipline for read-only research).

## Why NOT the "single-call like critique" shortcut (rejected)

The tempting design — mirror critique's `if count>1 and agent=="hermes": parallel else: one call does all areas` — was adversarially disproven for prep specifically:
- **Vacuous gate.** Prep has three stage models; fanout is hard-pinned hermes by construction (`_reject_write_capable_prep_provider:226`); there is no single `agent` at the dispatch site (`run_prep_orchestration`, `handlers/plan.py:150`). Critique's gate doesn't transfer.
- **Silent signal loss.** Per-area `elapsed_time_ms`/`timed_out_count`/`partial_count` are required `prep_metrics.json` fields (`runtime.py:258,282`) that the critique-evaluator reads to steer critics (`prompts/critique_evaluator.py:199-213`). A single call has one elapsed time and self-reported status → evaluator silently degrades.
- **~10× output truncation.** Hermes gives 32,768 output tokens *per area* (`prep_research.py:684`); `PREP_AREA_CAPS["extreme"]=10`. One call cannot hold 10 parallel budgets.
- **Validation leans on a latent bug.** `validate_payload("prep-research")` only checks the top-level `findings` key (`_impl.py:1609`); it does NOT validate finding items. Single-call would pass shallow validation that the per-area path (`_PREP_RESEARCH_FINDING_SCHEMA`) would reject.

Conclusion: prep needs real per-area isolation. The right move is to make the *fan-out primitive* vendor-agnostic, which the codebase is already ~70% set up for.

## Design — unify the fan-out, make the unit callable vendor-agnostic

### The core structural fix
- **Use the dead primitive.** `scatter_gather_processes` (`_core/hermes_fanout.py:272`) is a process-isolated scatter/gather with ZERO production callers. `run_research_fanout` hand-rolls `mp.get_context("spawn")` instead. Route prep fanout through `scatter_gather_processes`.
- **One shared per-unit runner.** Extract a `scatter_over_worker_step(make_prompt, schema, toolset, parse, *, isolation="thread"|"process", model)` helper that absorbs the **triplicated** Hermes scaffold (`_make_agent`/`_reasoning_off`/`_run_attempt`/`with_429_openrouter_fallback`) currently copy-pasted across `prep_research.py:695-752`, `parallel_critique.py:72-152`, `review/parallel.py:87-251` (canonical lives in `workers/hermes.py:854-880`).
- **Vendor-agnostic unit callable.** The per-area unit dispatches to the resolved stage model's vendor via a read-only worker (hermes toolset-gated / codex read-only sandbox / claude tool-restricted) inside an isolated process, and returns the existing `{finding, metrics}` two-part payload. This is what unlocks "fanout on any vendor" while preserving per-area timing, output budget, and independent-investigator semantics (real overlap/contradiction detection).

### Read-only enforcement per vendor (the "read-only runner" the guard waits for)
- **Hermes** — `enabled_toolsets=["file-readonly","web"]` (exists).
- **Codex** — unify on Agent-1's **Option A**: add `read_only: bool` to `run_codex_step` (drop `--add-dir`/writable_roots, emit `sandbox_mode='read-only'`, skip `--full-auto`, force `--ephemeral`, cwd=project_dir), thread it through `run_step_with_worker`, and **delete `run_codex_prep_step`** (~80% duplication of `run_codex_step`, single callsite).
- **Claude/Shannon** — NEW read-only launch mode in `run_shannon_step`: emit `--allowedTools Read Grep Glob WebFetch WebSearch` / `--disallowedTools Edit Write …`, drop the `--dangerously-skip-permissions` bypass. Must survive the root-cloud `rootSafeClaudeArgs` rewrite; update `tests/test_workers_shannon.py`. (Weaker isolation than codex/hermes — permission-policy only — but strictly safer than today's bypass-everything, and safer than critique's write-capable Claude.)

### Model / profile layer (works today for what can already run)
- **Flip** `CANONICAL_PREP_MODELS["fanout"]` `deepseek-v4-flash` → `DIRECT_DEEPSEEK_V4_PRO_SPEC`.
- **Declare** explicit `[profiles.X.prep_models]` ONLY in the two exception profiles (`all-claude`→sonnet, `all-codex`→gpt-5.4, all three stages). The other 14 inherit the flipped canonical default. Machinery already exists end-to-end (`_resolve_prep_models_with_inheritance` → `resolve_prep_models` → `state.config.prep_models` → `resolve_prep_stage_model`).
- **Guard flip + dedup.** `_reject_write_capable_prep_provider` (`prep_research.py:209`) and `_validate_prep_models` (`profiles/__init__.py:222`) encode the SAME vendor rules in two places. Extract one `validate_prep_stage_provider(agent, stage)` and call from both; flip it from a vendor blocklist to a **read-only-launch assertion** (accept claude/codex/hermes when launched read-only).
- **`--vendor` rewrites prep_models across the board** (DECIDED — overrides the earlier "keep prep out" recommendation). Route `prep_models` through the existing `_swap_premium_spec` / `_CLAUDE_MODEL_TO_CODEX_SPEC` mapping in `apply_vendor_rewrite`, same as every other slot: `claude:claude-sonnet-4-6 ↔ codex:gpt-5.4` swaps with the flag. DeepSeek/hermes prep specs are non-premium and pass through unchanged, so cost-tiered profiles keep cheap read-only research and never pull a premium model into the fanout. Net effect: the flag picks "the appropriate model from the other side" for prep wherever a premium side was chosen, with zero new mapping logic. Requires the swapped-to vendor's read-only runner to exist (Shannon read-only for claude; the vendor-agnostic fanout for the parallel stage).

## Structural debt found (tiered)

**IN-SCOPE (the refactor *is* the fix):**
- Route prep fanout through `scatter_gather_processes`; retire the hand-rolled `mp.spawn`.
- Extract the shared `scatter_over_worker_step` helper; migrate prep onto it (critique/review migration = cheap follow-up, do if low-risk).
- Extract the single `validate_prep_stage_provider`; flip to read-only assertion.
- Unify codex read-only into `run_codex_step` (delete `run_codex_prep_step`).
- Make the unit callable vendor-agnostic; add Shannon read-only mode.

**FOLLOW-UP (out of this sprint):**
- Delete the vestigial `flat_agent == "codex"` special-case in `resolve_prep_models:993` once profiles confirmed not relying on it.
- Fix `DEFAULT_AGENT_ROUTING["prep"]="claude"` (`types.py:394`) — a latent trap: prep legitimately cannot run claude write-capable; reachable only via the MOCK path. Change to `codex`/hermes.
- Unify the two read-only toolset sources of truth (`PREP_RESEARCH_TOOLSETS` vs `_toolsets_for_phase` `prep_readonly_phases`).
- Consolidate critique/review onto `scatter_over_worker_step`.

## Invariant output contract (MUST preserve byte-compatibly)

Artifacts: `prep_triage.json`, `prep.json` (also re-written by `handlers/plan.py:152`), `research.json`, `prep_metrics.json`, `prep_dossier.md`, plus skip-path artifacts.
Finding schema `_PREP_RESEARCH_FINDING_SCHEMA`: `{area, brief, status, findings[], files[], code_refs[], confidence, error}`.
Per-unit `{finding, metrics}` two-part shape feeding `prep_metrics.per_unit` (including real per-area `elapsed_time_ms`).
6 consumers: critique-evaluator prep section, plan `_render_prep_block`, planning `_prep_context_sections`, receipts extractors, feedback digest, `handlers/plan.py`.
Per-area timeout/kill ladder → `timed_out` status (the evaluator depends on it). Preserve under the new runner.

## Sprint shape (decided: ONE megaplan, not an epic)

Run as a **single megaplan** at **`partnered` / full / `:high` depth, with `--with-prep`** (tier picked to the highest-difficulty deliverable, the fan-out refactor). The two work-blocks below are the internal ordering for the plan, not separate sprints:

- **Block A — config + codex unification (do first; ships value alone).** prep_models profile-declared; flip `CANONICAL_PREP_MODELS["fanout"]` → deepseek-v4-pro; the two profile tables (`all-claude`→sonnet, `all-codex`→gpt-5.4); extract `validate_prep_stage_provider` (dedup the guard); unify codex read-only into `run_codex_step` + delete `run_codex_prep_step`; route triage/distill through `run_step_with_worker`; preflight validation; profile-validation test; fix `DEFAULT_AGENT_ROUTING["prep"]`.
- **Block B — vendor-agnostic parallel fan-out (the meat).** Extract `scatter_over_worker_step`; route prep fanout through `scatter_gather_processes` (retire the hand-rolled `mp.spawn`); vendor-agnostic unit callable preserving the `{finding, metrics}` + per-area-timing + `timed_out` contract; Shannon read-only launch mode; flip the guard to a read-only-launch assertion.

`thorough` is the step-up if hardening the read-only-isolation boundary (research workers must not mutate the repo) warrants it.

### Launch prerequisite (decided)

**Land the in-flight `shannon.py` roulette WIP first** (469 lines + 353 test lines, currently uncommitted on `main`). Block B edits `shannon.py` for the read-only mode; building on top of the committed roulette work avoids a merge collision and keeps the megaplan's diff reviewable. Then fork the run from that landed base (clean worktree) so no unrelated WIP carries in.

## Verdict

The single-call shortcut was a hedge that would have quietly degraded prep. The real fix — vendor-agnostic *parallel* fan-out built on the primitive that already exists — pays down triplicated scaffold + a dead primitive + duplicated guard logic in the same stroke. One `partnered//high +prep` sprint; Block A closes the original silent-DeepSeek bug and gets `all-codex` prep onto gpt-5.4 even before Block B lands.
