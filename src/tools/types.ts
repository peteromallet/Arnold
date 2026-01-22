import type Anthropic from '@anthropic-ai/sdk';
import type { ToolResult, NotifyCallback } from '../types.js';

/**
 * Context passed to tool handlers
 */
export interface ToolContext {
  /** Callback for sending notifications (used by executor tools) */
  notifyCallback: NotifyCallback | null;
  /** Discord user id that initiated this tool call (for authz). Null if unknown. */
  requesterUserId: string | null;
}

/**
 * A tool handler function
 * Uses `any` for input to allow specific tool implementations to define their own input types
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ToolHandler = (input: any, context: ToolContext) => Promise<ToolResult>;

/**
 * A registered tool with its schema and handler
 */
export interface RegisteredTool {
  /** Tool name (must be unique) */
  name: string;
  /** Tool schema for Claude */
  schema: Anthropic.Tool;
  /** Handler function */
  handler: ToolHandler;
}
