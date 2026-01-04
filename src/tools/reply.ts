import type { RegisteredTool, ToolContext } from './types.js';
import type { ToolResult } from '../types.js';

/**
 * Send a message to the user
 */
export const replyTool: RegisteredTool = {
  name: 'reply',
  schema: {
    name: 'reply',
    description:
      'Send a message to the user. Use after completing actions or for rejections/clarifications.',
    input_schema: {
      type: 'object' as const,
      properties: {
        message: {
          type: 'string',
          description: 'The message to send back to the user',
        },
      },
      required: ['message'],
    },
  },
  handler: async (input: { message: string }, _context: ToolContext): Promise<ToolResult> => {
    return {
      success: true,
      action: 'reply',
      message: input.message,
    };
  },
};
