/**
 * M10: Agent tool invocation service — bridges registry invocation with
 * host-owned ProposalRuntime.create() for timeline-editing results.
 *
 * This service is the canonical frontend invocation path. It ensures that
 * valid timeline-editing ToolResult outputs are routed through
 * ProposalRuntime.create() rather than being returned as raw patches.
 * Accept/reject/preview remain host-owned through existing ProposalPanel
 * and TimelineOps flows.
 *
 * @module agentToolInvocationService
 * @milestone M10
 */

import type {
  AgentToolInvocationRequest,
  AgentToolHandler,
  DisposeHandle,
  ToolResult,
  ToolMutationProposalResult,
  ToolUISummaryResult,
  ToolResultDiagnostic,
  ProcessSpawnConfig,
  ToolProcessResult,
  ProposalRuntime,
} from '@reigh/editor-sdk';
import type { AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry';
import {
  isTimelineEditableResult,
  toolResultToTimelineProposalInputs,
  validateToolResult,
} from '@/tools/video-editor/runtime/agentToolContracts';

// ---------------------------------------------------------------------------
// AgentToolInvocationService
// ---------------------------------------------------------------------------

/**
 * Frontend invocation service that routes timeline-editing tool results
 * through the host-owned ProposalRuntime.
 *
 * Composes the AgentToolRegistry (handler execution + validation) with
 * ProposalRuntime (proposal lifecycle: preview/accept/reject) so that
 * agent tools produce host-mediated proposals rather than raw patches.
 */
export interface AgentToolInvocationService {
  /**
   * Invoke a registered agent tool.
   *
   * - Delegates handler execution and result validation to the registry.
   * - Routes valid timeline-editing (mutation/proposal) results through
   *   ProposalRuntime.create() so the host owns the proposal lifecycle.
   * - Returns a UI-summary result describing the created proposal(s),
   *   or the original result for non-timeline-editing families.
   *
   * @returns The ToolResult, or null if the tool/handler is unavailable.
   */
  invokeTool(request: AgentToolInvocationRequest): Promise<ToolResult | null>;

  /**
   * The underlying registry (exposed for adapters that need direct access).
   */
  readonly registry: AgentToolRegistry;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export interface CreateAgentToolInvocationServiceOptions {
  /** The provider-scoped agent tool registry. */
  registry: AgentToolRegistry;

  /** The provider-scoped proposal runtime (stable for provider lifetime). */
  proposalRuntime: ProposalRuntime;
}

/**
 * Create the frontend invocation service.
 *
 * The returned service is the intended entry point for all browser-side
 * agent tool invocation. It guarantees that timeline-editing results are
 * routed through ProposalRuntime.create() so that:
 *
 * - Every mutation proposal has a tracked lifecycle (pending → accepted/rejected/stale).
 * - Preview is computed immediately after creation via proposalRuntime.create().
 * - Accept/reject remain host-owned through ProposalPanel → ProposalRuntime.accept/reject.
 * - Accept always applies through TimelineOps (preserving commitData/history).
 * - Stale-base handling is enforced during acceptance.
 */
export function createAgentToolInvocationService(
  options: CreateAgentToolInvocationServiceOptions,
): AgentToolInvocationService {
  const { registry, proposalRuntime } = options;

  async function invokeTool(
    request: AgentToolInvocationRequest,
  ): Promise<ToolResult | null> {
    // 1. Invoke through the registry (handler execution + result validation)
    const result = await registry.invokeTool(request);

    // 2. If the result is null (handler unavailable, tool missing, error), pass through
    if (result === null) {
      return null;
    }

    // 3. If the result is a timeline-editing result, route through ProposalRuntime
    if (isTimelineEditableResult(result)) {
      return routeTimelineEditableResult(result, request);
    }

    // 4. Non-timeline-editing results pass through unchanged
    return result;
  }

  /**
   * Route a timeline-editing (mutation/proposal) result through ProposalRuntime.
   *
   * Converts each patch to a TimelineProposalInput, creates proposals via
   * proposalRuntime.create(), and returns a ToolUISummaryResult describing
   * the created proposals.
   */
  function routeTimelineEditableResult(
    result: ToolMutationProposalResult,
    request: AgentToolInvocationRequest,
  ): ToolUISummaryResult {
    // Use the proposalRuntime's currentVersion as the base version.
    // This ensures proposals are computed against the version at invocation time.
    const baseVersion = proposalRuntime.currentVersion;

    // Build a source identifier that includes the tool and extension
    const source = `${request.toolId}`;

    // Convert patches to TimelineProposalInput records
    const proposalInputs = toolResultToTimelineProposalInputs(
      result,
      baseVersion,
      source,
    );

    // Create proposals through the host-owned ProposalRuntime
    const createdProposals = proposalInputs.map((input) =>
      proposalRuntime.create(input),
    );

    // Build a UI summary describing what was created
    const proposalIds = createdProposals.map((p) => p.id);
    const patchCount = proposalInputs.length;
    const previewable = createdProposals.every((p) => p.previewable);

    const summaryLines: string[] = [];
    summaryLines.push(
      patchCount === 1
        ? `Created 1 proposal from tool "${request.toolId}".`
        : `Created ${patchCount} proposals from tool "${request.toolId}".`,
    );

    if (result.rationale) {
      summaryLines.push(`Rationale: ${result.rationale}`);
    }

    if (result.affectedObjectIds && result.affectedObjectIds.length > 0) {
      const objectList = result.affectedObjectIds.slice(0, 5).join(', ');
      const suffix =
        result.affectedObjectIds.length > 5
          ? ` (and ${result.affectedObjectIds.length - 5} more)`
          : '';
      summaryLines.push(`Affected objects: ${objectList}${suffix}`);
    }

    if (!previewable) {
      summaryLines.push(
        'Note: Some proposals could not be fully previewed. Review before accepting.',
      );
    }

    // Collect any diagnostics from the original result
    const diagnostics: ToolResultDiagnostic[] = [...(result.diagnostics ?? [])];

    // Add a summary diagnostic
    diagnostics.push({
      severity: 'info',
      code: 'agent-tool/proposals-created',
      message: summaryLines.join(' '),
      detail: {
        proposalIds,
        baseVersion,
        source,
        patchCount,
        previewable,
      },
    });

    const uiResult: ToolUISummaryResult = {
      family: 'ui/summary',
      summary: summaryLines.join('\n'),
      diagnostics,
      detail: {
        proposalIds,
        baseVersion,
        source,
        patchCount,
        previewable,
        affectedObjectIds: result.affectedObjectIds,
        sourceRefs: result.sourceRefs,
      },
    };

    return uiResult;
  }

  return {
    invokeTool,
    registry,
  };
}
