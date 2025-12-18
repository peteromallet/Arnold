import type Anthropic from '@anthropic-ai/sdk';
import { logger } from '../logger.js';
import { taskTools } from './tasks.js';
import { executorTools } from './executor.js';
import { statsTools } from './stats.js';
import { replyTool } from './reply.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

// Re-export types
export type { RegisteredTool, ToolContext, ToolHandler } from './types.js';

/**
 * All registered tools
 */
const allTools: RegisteredTool[] = [
  ...taskTools,
  ...executorTools,
  ...statsTools,
  replyTool,
];

/**
 * Tool registry - maps tool names to their handlers
 */
const toolRegistry = new Map<string, RegisteredTool>(
  allTools.map((tool) => [tool.name, tool]),
);

/**
 * Get all tool schemas for Claude
 */
export function getToolSchemas(): Anthropic.Tool[] {
  return allTools.map((tool) => tool.schema);
}

/**
 * Get list of tool names (for system prompt)
 */
export function getToolNames(): string[] {
  return allTools.map((tool) => tool.name);
}

/**
 * Execute a tool by name
 */
export async function executeTool(
  toolName: string,
  input: Record<string, unknown>,
  context: ToolContext,
): Promise<ToolResult> {
  const tool = toolRegistry.get(toolName);

  if (!tool) {
    logger.warn('Unknown tool called', { toolName });
    return {
      success: false,
      action: 'unknown',
      error: `Unknown tool: ${toolName}`,
    };
  }

  logger.debug('Executing tool', { tool: toolName, input });

  try {
    const result = await tool.handler(input as any, context);
    logger.debug('Tool result', { tool: toolName, success: result.success });
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logger.error('Tool execution failed', error instanceof Error ? error : undefined, {
      tool: toolName,
    });
    return {
      success: false,
      action: toolName,
      error: message,
    };
  }
}

/**
 * Check if a tool exists
 */
export function hasTool(toolName: string): boolean {
  return toolRegistry.has(toolName);
}

/**
 * Register a new tool at runtime (for extensions)
 */
export function registerTool(tool: RegisteredTool): void {
  if (toolRegistry.has(tool.name)) {
    logger.warn('Overwriting existing tool', { toolName: tool.name });
  }
  toolRegistry.set(tool.name, tool);
  allTools.push(tool);
  logger.info('Tool registered', { toolName: tool.name });
}
