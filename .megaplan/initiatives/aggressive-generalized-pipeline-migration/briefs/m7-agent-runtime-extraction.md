# m7 — Agent Runtime Extraction (→ `arnold/agent/`)

## Why this milestone exists
The generic Arnold substrate cannot run an agent on its own. `arnold/pipeline/steps/agent.py::AgentStep` is hollow — it takes an *injected* callable and ships no runner. The only real agent runtime in the tree (`run_agent.py::AIAgent`, ~8.5k lines, plus the provider/key/tool/sandbox layers) lives under `arnold/pipelines/megaplan/`. Until it is generic, the m0 inventory's premise ("Megaplan is just the first app") is false, and the downstream "second proof pipeline" milestone cannot honestly satisfy its "zero megaplan imports" rule — it could only hide the megaplan dependency behind DI. This milestone closes that blind spot: extract the agent EXECUTION runtime into a generic `arnold/agent/` package, leaving only profile/robustness *policy* in megaplan.

## In scope — extract to `arnold/agent/` (+ `arnold/runtime/sandbox.py`)
1. **AIAgent core + streaming** — `arnold/pipelines/megaplan/agent/run_agent.py` (the chat-completions loop + the streaming stall-watchdog/producer-consumer/heartbeat infra at `:136-399`). Sole megaplan ref in the streaming path is `runtime.sandbox.get_sandbox_cwd` (:732) — resolve via the sandbox extraction below.
2. **Tool registry + dispatch** — `agent/tools/registry.py`, `agent/model_tools.py`, `agent/toolsets.py`, and the generic `tools/` handlers (terminal, browser, file, web, interrupt) → `arnold/agent/tools/`. Exclude platform-specific tools (honcho/homeassistant/messaging) and the chat `gateway/`.
3. **Provider / key layer** — `runtime/key_pool.py`, `agent/hermes_cli/{env_loader,runtime_provider}.py`, `hermes_constants.py` → `arnold/agent/providers/`. Split `runtime_provider.py`: generic model→provider resolution core vs megaplan-specific blocking guards.
4. **429 → OpenRouter fallback** — `_core/hermes_fanout.py:82-139` (already injection-shaped) → co-locate with the provider layer.
5. **Agent runtime contracts + protocols** — `agent_runtime/contracts.py`, `agent_runtime/adapters.py` → `arnold/agent/contracts.py`; lift `AgentSpec`/`AgentMode` + `parse_agent_spec`/`format_agent_spec` from `megaplan/types.py` (preserve the wire format — supervisor/routing_ledger depend on it).
6. **Tool-call sandbox** — `runtime/sandbox.py` (ContextVar write/exec isolation) → `arnold/runtime/sandbox.py`. Replace `CliError` with the already-defined `SandboxViolation`.

## Couplings to sever (make injected, do not drag planning vocab)
- Budget enforcement: `runtime.governor.current_governor` / `_pipeline.envelope._envelope_ctx` (key_pool.py:80,185) → an injected `BudgetCharger`/`Envelope` **protocol** with a no-op default. Breaking this silently disables cost-capping — cover with a test.
- `types.CliError` → generic Arnold error type at every site.
- `MEGAPLAN_API_KEYS_PATH` / `auto_improve/api_keys.json` layout default → a generic `KeySource` protocol; megaplan supplies its path.

## Out of scope (stays megaplan)
Profile/robustness → agent-config policy (the *decision* of which model/tier/effort); `smart_model_routing.py` heuristic; `observability/*` event storage (plan_dir-coupled); the chat `gateway/`.

## Done criteria
- `arnold/agent/` runs an LLM with tools + sandbox with **zero `arnold.pipelines.megaplan` imports** (enforced by the m0 import-leak gate extended to `arnold/agent/`).
- `AgentStep`'s injected callable has a real default: an `arnold/agent` runner.
- Megaplan re-exports the moved symbols from their old paths (compat shims) — green test suite, no behavior change.
- A throwaway non-megaplan caller (≈ the subagent-launcher shape) drives a tool-using agent importing only `arnold.agent`.
- Budget/cost-cap parity test passes through the new injected `BudgetCharger`.

## Locked decisions
- This is a MOVE + dependency-inversion, not a rewrite. Preserve the streaming watchdog semantics and the `parse/format_agent_spec` wire format exactly.
- Profile-driven behavior stays megaplan-owned and is injected into the generic runtime, never imported by it.

---

## Revision — post perspective-audit (2026-06-09)

A 10-lens adversarial audit found that a naive MOVE of the agent runtime would
**mechanically re-couple** to megaplan on day one. Two refinements:

### 0. Build on the m6 runtime foundation (depends_on m6-runtime-foundation)
The cross-cutting carriers this extraction reads — the run **envelope**
(`RunEnvelope`+`join()`), the **error base** (`ArnoldError`), and the per-step
`RunContext` — are made generic in **m6-runtime-foundation** and now live in
`arnold/runtime/`. This milestone CONSUMES them: import the envelope/error from
`arnold.runtime`, never from megaplan; charge cost through the injected `RunContext`,
not by importing the governor. If the foundation left a gap, fix it in foundation,
not with a local shim here.

### 1. Extract a THIN `ProviderPool`, do NOT shred the budget triad (heed the contrarian)
`key_pool` + `governor` + `budget_authority` are a cohesive megaplan budget
subsystem. Extracting them as three separately-injected protocols would create a
generic API with exactly one implementation — premature-protocol fiction. Instead
extract only a thin `ProviderPool` protocol to `arnold/agent/` = key acquisition
(`acquire(provider, model) -> key`) with NO envelope/governor/budget awareness.
The governor + budget_authority STAY megaplan-owned and wrap the generic pool.

### Scope note (also from the audit)
Broaden the hollow generic `AgentStep`'s `WorkerFn = Callable[..., str]` to
`Callable[..., Any]` so non-text pipelines (image-gen, ETL) aren't forced into
string-shaped outputs, and reconcile its `prompt_key`/`slot` fields with megaplan's
registry-callback prompt resolution (wrap the registry as a `Callable` `PromptSource`)
so megaplan's builder can actually adopt the generic step at m9.

---

## Ground-truth validation (2026-06-09) — judgment-filtered

A neutral validator grepped all 59 agent files and the key_pool. Two corrections:

- **The real coupling is `runtime.process`, not envelope/CliError.** Agent-layer megaplan
  coupling is exactly two modules / 10 sites: `runtime.process` (`kill_group`/`spawn`/
  `spawn_async`, **8 unconditional sites**: code_execution_tool, browser_tool,
  process_registry, environments/local, environments/persistent_shell, rl_training_tool,
  copilot_acp_client, whatsapp) and `runtime.sandbox.get_sandbox_cwd` (2 lazy sites).
  The envelope ContextVar and `CliError` do **not** appear in agent code at all (envelope
  is foundation-level, m6). So the real seam this milestone needs is a **`ProcessManager`
  protocol** (process spawn/kill abstraction) plus the sandbox-cwd resolver — not envelope
  plumbing. Coupling is confirmed shallow + all generic-infra (zero planning vocab) → it is
  a MOVE, as briefed.

- **Thin `ProviderPool` requires lifting the charge OUT of `acquire()`.** Ground truth:
  `key_pool.acquire()` is NOT envelope-free today — it reads `_envelope_ctx` and calls
  `gov.charge(envelope)` inline (key_pool.py:180-189), deliberately OUTSIDE the pool lock
  so a `BudgetExceeded` doesn't strand the lock. So extracting a thin pool = move that
  `gov.charge(envelope)` call from inside `acquire()` into megaplan's caller (preserving
  the outside-the-lock ordering); the generic `acquire()` does key-selection + cooldown
  only. `report_429()` is already envelope-free. Mechanical refactor across `acquire_key`
  + `resolve_model` call-sites — name it, it's not free.

- **Done-criteria add:** `import arnold.agent` in a megaplan-absent venv must succeed
  (the runtime boundary check from m6) — proves zero residual coupling incl. dynamic/ContextVar.
