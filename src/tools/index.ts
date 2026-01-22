import { logger } from '../logger.js';
import { config } from '../config.js';
import { redactToolResult } from '../secrets.js';
import { taskTools } from './tasks.js';
import { executorTools } from './executor.js';
import { statsTools } from './stats.js';
import { replyTool } from './reply.js';
import { runpodTools } from './runpod.js';
import { codeTools } from './code.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

/**
 * All registered tools
 */
const allTools: RegisteredTool[] = [
  ...taskTools,
  ...executorTools,
  ...statsTools,
  ...runpodTools,
  ...codeTools,
  replyTool,
];

/**
 * Tool registry - maps tool names to their handlers
 */
const toolRegistry = new Map<string, RegisteredTool>(
  allTools.map((tool) => [tool.name, tool])
);

/**
 * Get all tool schemas for Claude
 */
export function getToolSchemas() {
  return allTools.map((tool) => tool.schema);
}

/**
 * Get list of tool names (for system prompt)
 */
export function getToolNames() {
  return allTools.map((tool) => tool.name);
}

/**
 * Execute a tool by name
 */
export async function executeTool(
  toolName: string,
  input: unknown,
  context: ToolContext
): Promise<ToolResult> {
  // Enforce that ALL tools are only usable by the configured Discord user
  if (!context.requesterUserId || context.requesterUserId !== config.discord.allowedUserId) {
    logger.warn('Unauthorized tool call blocked', {
      toolName,
      requesterUserId: context.requesterUserId,
    });
    return {
      success: false,
      action: toolName,
      error: 'Unauthorized: this bot can only be used by its owner.',
    };
  }

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
    const result = await tool.handler(input, context);
    const safe = redactToolResult(result);
    logger.debug('Tool result', { tool: toolName, success: safe.success });
    return safe;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logger.error('Tool execution failed', error instanceof Error ? error : undefined, {
      tool: toolName,
    });
    return {
      success: false,
      action: toolName,
      error: redactToolResult({ success: false, action: toolName, error: message }).error,
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



