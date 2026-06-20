/**
 * agent-tool-example — M10 agent tool contribution example.
 *
 * Demonstrates:
 *   1. An `AgentToolContribution` declared in the extension manifest with
 *      an input schema that defines the tool's invocation payload shape.
 *   2. A tool handler function that receives `AgentToolInvocationRequest`
 *      and returns a `ToolResult` — in this example it produces a
 *      `ToolUISummaryResult` with proposal data.
 *   3. `ctx.agentTools.registerTool()` during activation for imperative
 *      handler binding.
 *
 * Agent tools are host-mediated and proposal-backed. This example returns
 * a static UI summary result; real tools would produce mutation proposals,
 * export artifacts, process invocations, or enrichment search results.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports exclusively from @reigh/editor-sdk, the public SDK entrypoint.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  AgentToolContribution,
  AgentToolInputSchema,
  AgentToolInvocationRequest,
  AgentToolHandler,
  AgentToolRegistrationService,
  ToolResult,
  ToolUISummaryResult,
  ToolResultFamily,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Input schema — defines the shape of the tool's invocation payload
// ---------------------------------------------------------------------------

const EXAMPLE_TOOL_INPUT_SCHEMA: AgentToolInputSchema = {
  type: 'object',
  title: 'Example Tool Input',
  description: 'Input payload for the example agent tool.',
  properties: {
    targetClipId: {
      type: 'string',
      title: 'Target Clip ID',
      description: 'The ID of the clip to operate on.',
    },
    action: {
      type: 'string',
      title: 'Action',
      description: 'The action to perform on the target clip.',
      enum: ['analyze', 'label', 'enhance'],
      default: 'analyze',
    },
    confidence: {
      type: 'number',
      title: 'Confidence Threshold',
      description: 'Minimum confidence level (0–1).',
      default: 0.8,
    },
  },
  required: ['targetClipId'],
};

// ---------------------------------------------------------------------------
// Tool handler
// ---------------------------------------------------------------------------

/**
 * An example agent tool handler that produces a ToolUISummaryResult.
 *
 * Real tool handlers would receive a timeline snapshot, perform analysis
 * or generation, and return structured results with proposals, artifacts,
 * or diagnostics.
 */
export const exampleToolHandler: AgentToolHandler = (
  request: AgentToolInvocationRequest,
): ToolResult => {
  const { toolId, extensionId, input } = request;

  const result: ToolUISummaryResult = {
    family: 'ui' as ToolResultFamily,
    summary: `Tool "${toolId}" invoked by "${extensionId}" with action "${String(input?.action ?? 'unknown')}" on clip "${String(input?.targetClipId ?? 'none')}".`,
    proposalData: {
      toolId,
      extensionId,
      input: input ?? {},
      suggestedLabel: `Analyzed by ${toolId}`,
    },
  };

  return result;
};

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export const agentToolExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.agent-tool' as any,
    version: '1.0.0',
    label: 'Agent Tool Example',
    description:
      'Demonstrates agent tool contribution with input schema via M10 SDK surface.',
    apiVersion: 1,
    contributions: [
      {
        id: 'example-agent-tool' as any,
        kind: 'agentTool',
        toolId: 'com.reigh.examples.agentTool.clipAnalyzer',
        label: 'Clip Analyzer',
        description: 'Analyzes a clip and produces a labeled proposal.',
        inputSchema: EXAMPLE_TOOL_INPUT_SCHEMA,
        resultFamilies: ['ui'] as readonly ToolResultFamily[],
        order: 10,
      } as AgentToolContribution,
    ],
    messages: {
      activated: 'Agent tool example activated.',
      disposed: 'Agent tool example disposed.',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    const agentTools = ctx.agentTools as AgentToolRegistrationService;

    const handle = agentTools.registerTool(
      'com.reigh.examples.agentTool.clipAnalyzer',
      exampleToolHandler,
    );

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
        handle.dispose();
      },
    };
  },
});

/** Re-export types for SDK consumers. */
export type {
  AgentToolContribution,
  AgentToolInputSchema,
  AgentToolInvocationRequest,
  AgentToolHandler,
  ToolResult,
  ToolUISummaryResult,
};
