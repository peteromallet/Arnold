import { startExecutor, stopExecutor, getExecutorStatus } from '../executor.js';
import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

/**
 * Start the task executor
 */
export const startExecutorTool: RegisteredTool = {
  name: 'start_executor',
  schema: {
    name: 'start_executor',
    description:
      'Start the task executor. It will automatically pick up queued tasks and run Claude Code to complete them. Use when user wants to start/run/execute/go.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, context: ToolContext): Promise<ToolResult> => {
    const result = await startExecutor(context.notifyCallback || (() => {}));
    return {
      success: result.success,
      action: 'start_executor',
      message: result.message,
    };
  },
};

/**
 * Stop the task executor
 */
export const stopExecutorTool: RegisteredTool = {
  name: 'stop_executor',
  schema: {
    name: 'stop_executor',
    description:
      'Stop the task executor. It will finish any current task but not pick up new ones. Use when user wants to stop/pause/halt.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    try {
      const result = stopExecutor();
      return {
        success: result.success,
        action: 'stop_executor',
        message: result.message,
      };
    } catch (error) {
      return {
        success: false,
        action: 'stop_executor',
        error: error instanceof Error ? error.message : String(error),
      };
    }
  },
};

/**
 * Get the current status of the executor
 */
export const getExecutorStatusTool: RegisteredTool = {
  name: 'get_executor_status',
  schema: {
    name: 'get_executor_status',
    description:
      'Get the current status of the executor - whether it is running and what task it is working on.',
    input_schema: {
      type: 'object' as const,
      properties: {},
    },
  },
  handler: async (_input: Record<string, never>, _context: ToolContext): Promise<ToolResult> => {
    const status = getExecutorStatus();
    return {
      success: true,
      action: 'get_executor_status',
      running: status.running,
      currentTask: status.currentTask,
    };
  },
};

/**
 * All executor-related tools
 */
export const executorTools: RegisteredTool[] = [
  startExecutorTool,
  stopExecutorTool,
  getExecutorStatusTool,
];
