# m11 — Unified agent dispatcher (one `dispatch()` over all 3 backends)

`depends_on: m7-agent-runtime-extraction` (runtime + contracts), `m8-state-lifecycle-runtime` (event/state infra). Appended after m10.

## Why this milestone exists
m7 extracts the AIAgent *core* to `arnold/agent/` and lands the `AgentRequest`/
`AgentResult` contracts + the `AgentDispatcher` Protocol — but **no milestone
builds a concrete dispatcher**, and m7–m10 leave the real dispatch site, the
3-way branch in `run_step_with_worker`
(`arnold/pipelines/megaplan/workers/_impl.py:3108-3320`: hermes→`run_hermes_step`,
claude/shannon→`run_shannon_step`, else→`run_codex_step`), **entirely intact and
megaplan-resident**. So `arnold.agent` today has contract *types* but no runner
that an external caller can use to run a turn against any backend without
importing megaplan's `run_step_with_worker`. This milestone closes that: it makes
`arnold.agent` a real, consumable, vendor-agnostic execution API — the public
surface a non-megaplan consumer (e.g. the VibeComfy panel; see the separate
follow-up brief) ratifies before the boundary fully freezes.

## Locked decisions
- **DeepSeek keeps the full Hermes/AIAgent runtime** (the m7 `arnold/agent`
  runner). NO thin client — this is decided. The dispatcher routes the
  DeepSeek/hermes path straight to the AIAgent runner.
- **Additive + flag-gated.** Ship behind `MEGAPLAN_USE_AGENT_DISPATCHER`
  (default OFF); `run_step_with_worker` stays byte-for-byte the default path,
  rollback = one env var. This is the migration's proven strangler pattern.
- **Codex/Shannon stay megaplan-resident, injected — NOT force-moved.** The
  migration deliberately did not relocate `run_codex_step`/`run_shannon_step`;
  do not start that here. They register into the dispatcher as adapter impls.

## In scope
1. **Concrete dispatcher** `arnold/agent/dispatcher.py::ArnoldDispatcher`
   implementing `dispatch(AgentRequest) -> AgentResult` (the Protocol at
   `arnold/agent/contracts.py`). Stateless; `SessionStore`/`KeySource`/event
   sinks injected (consume the m8 runtime infra, imported from `arnold`).
2. **A `BackendAdapter` seam.** `arnold/agent/` ships the **DeepSeek adapter
   native** (wraps the m7 AIAgent runner, Hermes whole). **Codex and Shannon
   adapters are injected** — thin wrappers around the existing megaplan
   `run_codex_step` / `run_shannon_step` happy-path call, registered by megaplan
   (DI, matching "arnold generic, megaplan injects"). No backend code is moved.
3. **Collapse the 3-way branch.** Behind the flag, `run_step_with_worker`
   becomes a thin shim that builds an `AgentRequest` from the resolved
   `AgentMode` + step schema and calls `dispatcher.dispatch(...)`, projecting
   `AgentResult -> WorkerResult` via the existing bridge so callers are
   unchanged.

## Couplings — what stays ABOVE the dispatch call (megaplan policy, not moved)
Schema validation, session bookkeeping, the routing ledger
(`record_step_routing`), per-agent retry loops, and runtime auth/connection
fallback all remain in `run_step_with_worker` wrapping the dispatch call. The
dispatcher does model invocation only.

## Out of scope
- Moving `run_codex_step`/`run_shannon_step` recovery machinery into arnold
  (stays megaplan; injected). - The VibeComfy consumer (separate repo — its own
  follow-up brief). - Flipping the flag on by default (a later, separate cut once
  a real external consumer has ratified the API).

## Done criteria
- A **non-megaplan caller** (≈ the subagent-launcher shape, same ratifying test
  m7/m9 use) drives **all three backends** — deepseek, codex, claude — through
  `arnold.agent.dispatch(AgentRequest)` importing only `arnold.agent`
  (+ injected megaplan adapters for codex/shannon), zero `arnold.pipelines.megaplan`
  leak in the arnold-native path (m0/m6 leak gate extended to the dispatcher).
- **Flag OFF:** `run_step_with_worker` behaviorally identical to today
  (worker tests green). **Flag ON:** parity `WorkerResult` for a fixed prompt
  through each of the 3 branches (golden capture vs dispatcher output).
- Soak the flag-on path on a read-only phase of a throwaway plan before any
  default flip.

## Touchpoints
New `arnold/agent/dispatcher.py` + `arnold/agent/adapters/` (DeepSeek native;
Codex/Shannon injection points); `arnold/pipelines/megaplan/workers/_impl.py`
(`run_step_with_worker` shim + registering the Codex/Shannon adapters);
`arnold/agent/contracts.py` (consume, don't redefine).
