# megaplan agentkit migration: phase runners on the shared kernel

Profile intent: `thoughtful//medium @codex +feedback`.

This milestone re-roots megaplan's per-phase runners onto `agentkit.loop.run_step`, and replaces megaplan's internal LLM router, tool registry, progress emitter, usage pricing, and (optionally) workflow state-machine with the agentkit equivalents. `auto.py:drive()` — megaplan's outer state-machine driver — stays. Only what runs *inside* a phase changes.

## Prerequisites

- `agentkit v0.3.0` published and installable.
- `agentkit-bootstrap-chain.yaml` sprints 1, 2, and 3 merged.

## Source plan

- `agentkit`: `docs/agentkit-design.md`, `docs/workflow.md`, `docs/subagent.md`, `docs/providers.md`.
- This repo: `megaplan/auto.py` (esp. `drive` at 774, `_run_phase`), `megaplan/agent/agent/agent_loop.py` (the resident loop at 169–220), `megaplan/agent/agent/auxiliary_client.py` (provider resolution 8–36), `megaplan/agent/agent/anthropic_adapter.py`, `megaplan/agent/workers.py` (subagent spawn 111–182), `megaplan/resident/tool_registry.py`, `megaplan/context_compressor.py`, `megaplan/usage_pricing.py`, `megaplan/progress.py`, `megaplan/profiles/`.

## Goal

Every per-phase LLM call inside megaplan dispatches through `agentkit.loop.run_step` and `agentkit.llm.router`. `ToolRegistry`, `ProgressEmitter`, `usage_pricing`, and `ContextCompressor` are re-exports from agentkit, not separate implementations. The outer `auto.py:drive` state-machine and the workflow/transition matrix stay megaplan-owned in this milestone (an optional follow-up can move them to `agentkit.plan.Workflow` if the round-trip proves clean).

## Required scope

- Pin `agentkit>=0.3.0,<0.4.0` in `pyproject.toml`. Vendor copies of `usage_pricing.py`, `context_compressor.py`, `progress.py` are deleted (re-exported from agentkit).
- **Tool registry**: `megaplan/resident/tool_registry.py` becomes a thin re-export: `from agentkit.tools import Toolkit, ToolRegistration, ToolResult`. Existing megaplan-resident tools remain registered the same way.
- **LLM router**: `megaplan/agent/agent/auxiliary_client.py` becomes `from agentkit.llm.router import ProviderRouter`. The resolution chain (OpenRouter / Nous / Codex / Anthropic / direct DeepSeek / Kimi / MiniMax / Fireworks) is preserved by registering each adapter against the router.
- **Anthropic adapter**: `megaplan/agent/agent/anthropic_adapter.py` thinking-budget logic is preserved — port verbatim into `agentkit.llm.anthropic`'s `thinking_budget_for(model)` hook (introduced in `agentkit v0.3.0`).
- **Per-phase runner**: `_run_phase` (in `auto.py`) currently calls `OpenAICompatibleAgentRunner` or similar inside `resident/agent_loop.py`. Replace this inner call with `await agentkit.loop.run_step(...)` passing the appropriate `Toolkit`, phase-specific `StepPlan`, model from the profile, and a `Budget` derived from the phase's cost/iteration caps.
- **StepPlan per phase**: each megaplan phase maps to a `StepPlan`. `prep`, `plan`, `revise`, `execute`, `review` are single-step plans with their phase's allowed tools. `critique` and `gate` are single-step with critic-tool subsets. The phase enum and transition matrix stay in `megaplan/workflow.py` for now.
- **Context compaction**: `ContextCompressor` becomes a re-export. Existing tail/head protection settings and iterative-summary parameters preserved.
- **Progress emitter**: `progress.py` becomes a re-export of `agentkit.obs.events`. File / DB / multi backends preserved. Existing megaplan event types kept as a megaplan-local enum that extends agentkit's base.
- **Subagent spawning**: `megaplan/agent/workers.py:111-182` is reduced to a thin wrapper around `agentkit.subagent.spawn`. Worktree resolution behaviour preserved. Codex OAuth, Hermes worker, and Claude Code worker entrypoints stay megaplan-owned (they're shell scripts that invoke specific binaries) — only the *spawning* mechanism is shared.
- **Profiles**: `megaplan/profiles/` becomes a thin wrapper around `agentkit.profiles`. Built-in `standard.toml`, `thoughtful.toml`, `premium.toml`, `super-premium.toml`, and the `all-*` and named profiles (`detectives`, `holmes`, etc.) all load through `agentkit.profiles.load_profile(name)`.
- **Cost ledger**: usage_pricing emit goes to `agentkit.obs.cost.ledger`. Existing per-phase cost reporting in `DriverOutcome` keeps the same shape — internally backed by agentkit.

## Cutover protocol

Megaplan is a tool, not a service in prod, so this is a less ceremonious cutover than Veas / bndc.

1. Per-PR review: each module re-pointed (tool registry, router, anthropic adapter, etc.) is its own commit on the milestone branch. Tests must pass per-commit.
2. Run megaplan against a small recorded plan (`tests/fixtures/sample_plans/`) at `--depth minimal` end-to-end. Compare output artifacts and event stream to a baseline recorded before this milestone.
3. Run megaplan against a real plan at `--depth low` and compare cost / token / latency vs baseline. Tolerate ±10% delta on cost.
4. Soak: 3–5 real plans (from the operator's normal workload) at `--depth medium` over 3 days. Watch for divergent behaviour in critique/gate phases, since those are where provider-quirk differences will surface.
5. Tag `megaplan` `vNEXT` once green.

## Explicit non-goals

- Do not change `auto.py:drive()` outer state-machine semantics. Transition matrix, robustness pruning, tiebreaker logic, stall detection, blocked-task retries — all stay megaplan-owned. (An optional Sprint 4 may move them to `agentkit.plan.Workflow` if the round-trip from bndc's chain validates cleanly.)
- Do not change the per-phase agent-spec format (`hermes:openrouter:gemini-3-flash`).
- Do not change the megaplan CLI surface (`megaplan plan`, `megaplan auto`, `megaplan chain`, `megaplan cloud chain`).
- Do not change `cloud.yaml` format or `megaplan cloud` behaviour.
- Do not migrate the bakeoff harness. (Bakeoffs spawn many subagents; eventual port should reuse `agentkit.subagent.spawn` but is its own follow-up.)
- Do not change Codex OAuth flow or Codex Responses-API quirks. Behaviour is preserved via the ported anthropic_adapter logic.

## Acceptance criteria

- `pytest` against megaplan's existing test suite passes with the agentkit-rooted internals.
- Recorded-LLM regression test: `--depth minimal` end-to-end run produces identical artifacts to a baseline recorded pre-migration (modulo timestamps, run IDs).
- Real `--depth low` plan: cost within ±10% of baseline, no new error categories in `DriverOutcome.events`.
- Soak (3 real plans at `--depth medium`) completes without manual intervention. No regression in critique/gate divergence rate.
- `usage_pricing.py`, `progress.py`, `context_compressor.py`, the inner runner in `resident/agent_loop.py`, and `auxiliary_client.py` are deleted or reduced to ≤20-line re-export shims.
- megaplan's published wheel still works as a CLI tool — `pip install megaplan && megaplan --help` succeeds.

## Testing notes

- Provider-specific quirks are the main risk: Codex reasoning toggles, Anthropic thinking budgets, DeepSeek tool-use shape, model-metadata-fetch fallbacks (`models.dev` → provider API → hardcoded). Port verbatim; the time to clean these up is Sprint 4, not now.
- The Codex OAuth + Responses-API adapter must keep its exact retry / reasoning-disable behaviour per model family — bring all existing megaplan tests with you and run them against the agentkit-rooted adapter.
- Cost-pricing snapshots: megaplan's `usage_pricing.py` carries multi-provider price tables and fallback fetch logic. Agentkit must reproduce these — diff outputs on a fixed input dataset.

## Risks and mitigations

- **Provider-quirk regressions.** Many small per-provider behaviours. The cure is high-fidelity adapter porting + recorded tests, not refactoring.
- **Auxiliary client cost-attribution drift.** Megaplan's auxiliary calls (critique side tasks, summarisation) must charge cost to the correct phase. Verify by inspecting `DriverOutcome.history[*].cost` on a recorded plan.
- **Worktree path-resolution edge cases.** `workers.py:111-182` had a long tail of bugs over time. Port the resolution function verbatim with its existing test suite; refactor later.
