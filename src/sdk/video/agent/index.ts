/**
 * Agent family canonical module — placeholder for AgentContribution contracts.
 *
 * The `agent` contribution kind (distinct from `agentTool`) is declared at
 * `declarationMaturity: 'typed'` / `executionMaturity: 'delegated'` in the
 * video family registry.  Agent contributions expose a tool dispatch surface
 * and generation session contract; execution is host-mediated via
 * proposal-backed tool invocation.
 *
 * **Governance note (M2b):**  No dedicated `AgentContribution` interface
 * exists yet in the SDK public surface.  This module is created as the
 * canonical home for the agent family so that `agent.sdkModules` in
 * `familyDefinitions.ts` and `family-maturity.json` points to an existing
 * SDK-owned file rather than a non-existent directory.
 *
 * When `AgentContribution` is implemented, add it here and re-export from
 * `src/sdk/index.ts`.
 *
 * @module video/agent
 * @publicContract
 */

// AgentContribution will be defined here when implemented.
// For now this module exists solely to satisfy the sdkModules reference
// in the video family registry.
