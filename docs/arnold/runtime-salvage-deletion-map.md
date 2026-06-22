# Runtime Salvage / Deletion Map

This map classifies the old runtime modules that predate the manifest workflow
runtime (`arnold.execution`).  Classifications:

- **Refactored** — logic has been rewritten into the manifest runtime.
- **Quarry-only** — kept for reference/tracing but not used for new runs.
- **Compatibility alias** — thin shim retained until M6 for existing callers.
- **M6 deletion target** — scheduled for removal in milestone 6.

## `arnold.runtime`

| Module | Classification | Notes |
|--------|---------------|-------|
| `arnold.runtime.event_journal` | Refactored | Replaced by `arnold.kernel.journal.NDJsonEventJournal`. |
| `arnold.runtime.envelope` | Refactored | Replaced by `arnold.kernel.events.EventEnvelope`. |
| `arnold.runtime.semantic_replay` | Refactored | Core logic moved to `arnold.kernel.replay` and `arnold.execution.resume`. |
| `arnold.runtime.resume` / `arnold.runtime.resume_validation` | Refactored | Replaced by `arnold.execution.resume.prepare_resume`. |
| `arnold.runtime.state_persistence` | Quarry-only | Old state-authority persistence; do not use for new runs. |
| `arnold/runtime/CONTRACT.md` | Quarry-only | Historical contract document. |
| `arnold.runtime.batch*` | M6 deletion target | Product-specific batch scheduling. |
| `arnold.runtime.driver` | M6 deletion target | Superseded by `arnold.execution.runner.run`. |
| `arnold.runtime.process` | M6 deletion target | Process model no longer used. |
| `arnold.runtime.recovery` | M6 deletion target | Recovery logic is now journal replay. |
| `arnold.runtime.sandbox` | M6 deletion target | Replaced by artifact-root isolation. |
| `arnold.runtime.settings*` | M6 deletion target | Settings resolution moved to product harness. |
| `arnold.runtime.wal_fold` | M6 deletion target | WAL folding replaced by journal fold. |
| `arnold.runtime.oracle` | M6 deletion target | Oracle coordination is out of scope for the neutral runtime. |
| `arnold.runtime.effect` | Refactored | Replaced by `arnold.kernel.effect_ledger` and `ExecutionRegistries.effects`. |
| `arnold.runtime.operations` | M6 deletion target | Operational helpers are product-side. |
| `arnold.runtime.outcome` | Refactored | Replaced by `arnold.execution.backend.NodeState`. |

## `arnold.pipeline`

| Module | Classification | Notes |
|--------|---------------|-------|
| `arnold.pipeline.executor` | Refactored | Core execution logic moved to `arnold.execution.backend.LocalJournalBackend`. |
| `arnold.pipeline.runner` | Refactored | Replaced by `arnold.execution.runner.run`. |
| `arnold.pipeline.resume` | Refactored | Replaced by `arnold.execution.resume`. |
| `arnold.pipeline.routing` | Refactored | Replaced by `arnold.execution.routing.project_routing_state`. |
| `arnold.pipeline.state` | Quarry-only | Old state authority; read for migration only. |
| `arnold.pipeline.contracts` | Compatibility alias | Type aliases retained for existing callers. |
| `arnold.pipeline.validator` | M6 deletion target | Validation now in `arnold.workflow.validation`. |
| `arnold.pipeline.builder` | M6 deletion target | DSL builder replaced by explicit `Pipeline`/`Step`/`Route`. |
| `arnold.pipeline.hooks` | M6 deletion target | Hook dispatch is registry-driven. |
| `arnold.pipeline.registry` | M6 deletion target | Registry logic moved to `arnold.execution.registries`. |
| `arnold.pipeline.subpipeline` | Refactored | Subpipelines are manifest-hash references in `WorkflowNode.subpipeline`. |
| `arnold.pipeline.step_invocation` | M6 deletion target | Native step invocation replaced by backend hooks. |
| `arnold.pipeline.token_cost` / `model_resource_capabilities` / `media_cost` | M6 deletion target | Cost/resource modeling belongs in product harness. |
| `arnold.pipeline.profiles` | M6 deletion target | Profile selection is product-side. |
| `arnold.pipeline.types` | Compatibility alias | Retained until M6. |

## Discovery

| Module | Classification | Notes |
|--------|---------------|-------|
| `arnold.pipeline.discovery` | M6 deletion target | Manifest discovery moved to product harness and `arnold.execution` callers. |
| `arnold.pipelines.megaplan._pipeline.discovery` | M6 deletion target | Product-specific discovery. |

## Oracle

| Module | Classification | Notes |
|--------|---------------|-------|
| `arnold.runtime.oracle` | M6 deletion target | Oracle bisection and tracing are product tools, not runtime primitives. |
| `arnold.pipelines.megaplan.runtime` | M6 deletion target | Product runtime adapter; replaced by registry shims. |

## Replay

| Module | Classification | Notes |
|--------|---------------|-------|
| `arnold.runtime.semantic_replay` | Refactored | See `arnold.kernel.replay` and `arnold.execution.resume`. |
| `arnold.kernel.replay` | Refactored | Current replay primitives. |

## Agent adapter shims

| Module | Classification | Notes |
|--------|---------------|-------|
| `arnold.execution.registries.AgentCapabilityHandler` | Refactored | Bridges `arnold.agent.AgentDispatcher` to the capability registry. |
| `arnold.execution.registries.AgentEffectHandler` | Refactored | Bridges agents to the effect registry. |
| `arnold.execution.registries.AgentReducerHandler` | Refactored | Bridges agents to the reducer registry. |
| `arnold.execution.registries.build_agent_adapter_bridge` | Refactored | Returns `ExecutionRegistries` backed by an agent dispatcher. |
| Older agent runtime shims in `arnold.pipelines.megaplan.agent_runtime` | M6 deletion target | Replaced by the registry bridge above. |

## Migration rule of thumb

- If a module's responsibility is now in `arnold.execution`, `arnold.kernel`,
  `arnold.manifest`, or `arnold.workflow`, it is either **refactored** or an
  **M6 deletion target**.
- If a module is referenced by active product code, mark it a **compatibility
  alias** and schedule removal for M6.
- If a module is only useful for understanding historical behavior, mark it
  **quarry-only**.
