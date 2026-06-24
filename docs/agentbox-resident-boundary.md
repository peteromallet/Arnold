# AgentBox Resident Boundary

This note records the package ownership boundary for the Discord thin path.
The goal is to keep the resident chat flow usable by Discord and future
Operator surfaces without moving product-specific behavior into Arnold's neutral
runtime contracts.

## Arnold-Facing Neutral Seams

Arnold-facing neutral seams are protocol and contract surfaces that can be used
without knowing about Discord, AgentBox, or Megaplan product behavior.

- `arnold_pipelines.megaplan.resident.runtime` owns the reusable resident loop:
  inbound event persistence, authorization calls, burst coalescing, agent
  dispatch, outbound delivery, and system/progress emission through protocols.
- `InboundEvent`, `OutboundMessage`, `OutboundSink`, and `EmitProtocol` are the
  neutral handoff shapes. They carry durable identity and IO boundaries, not
  Operator command policy or model-supplied actor authority.
- `arnold_pipelines.megaplan.resident.config.ResidentConfig` is the environment
  and timeout/configuration seam for resident runtimes. Transport-specific
  startup can read it, but command semantics stay outside this layer.

## Megaplan-Owned Resident Runtime Details

Megaplan owns the resident implementation details that require Megaplan store,
schema, plan, cloud, and control semantics.

- `ResidentRuntime` persists resident conversations, messages, turns, tool calls,
  and progress/system events through the Megaplan `Store`.
- `MegaplanResidentProfile` owns the Megaplan system prompt, hot-context loading,
  resident tool registry, confirmations, cloud control, export, editorial, and
  search behavior.
- Discord-specific delivery and inbound mapping live under
  `arnold_pipelines.megaplan.resident.discord`; they adapt Discord events to the
  neutral runtime seam instead of defining AgentBox or Arnold contracts.

## AgentBox-Owned Operator/Profile/Helper Integration

AgentBox owns the Operator-facing integration layer: commands, profiles, helpers,
and host/run-dir operation views that turn resident intent into AgentBox actions.

- Operator commands should call AgentBox-owned helpers for operation launch,
  status, logs, profile selection, and bounded context loading.
- AgentBox profiles decide which Operator shell and helper affordances are
  available. Megaplan resident profiles may expose thin tool wrappers, but should
  not duplicate AgentBox command policy.
- Shared status/log formatting for AgentBox operations belongs in AgentBox or an
  AgentBox-owned adapter helper. Discord tools should delegate to that view so
  CLI and Discord report the same operation state.

In short: Arnold sees neutral resident protocols, Megaplan owns the resident
runtime and Megaplan-specific tools, and AgentBox owns Operator/profile/helper
integration around operations.
