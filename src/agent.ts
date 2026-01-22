import Anthropic from '@anthropic-ai/sdk';
import { config } from './config.js';
import { logger } from './logger.js';
import { ExternalServiceError } from './errors.js';
import { getToolSchemas, getToolNames, executeTool } from './tools/index.js';
import type { ToolAction, ParseTaskResult, NotifyCallback, ConversationMessage } from './types.js';
import type { ToolContext } from './tools/types.js';

const client = new Anthropic();

/**
 * Build the system prompt with current tool names
 */
function buildSystemPrompt(): string {
  const toolNames = getToolNames().join(', ');

  return `You are a concise task bot. Keep replies SHORT - 1-2 sentences max.

EXCEPTION: For RunPod GPU results, ALWAYS include the FULL message with Storage, RAM, and Jupyter URL exactly as returned.

Tools: ${toolNames}

ALWAYS end with reply tool to tell the user what happened. Include task ID when relevant.

The executor runs automatically on startup. Tasks with status "todo" will be picked up and executed.

Guidelines:
- New work → create_task (defaults to backlog unless user says "now"/"immediately"/"urgent"), then reply with confirmation + task ID
- Find tasks → search_tasks, then reply with results
- Modify task → update_task, then reply with what changed + task ID
- Stop/pause execution → stop_executor, then reply
- Resume execution → start_executor, then reply
- Status → get_executor_status, then reply with status
- RunPod GPU → create_runpod_instance, list_runpod_instances, terminate_runpod_instances
- RunPod GPU scheduling (e.g. "kill all machines in 30 minutes") → schedule_terminate_runpod_instances
- Cancel scheduled shutdown → cancel_scheduled_termination
- Check scheduled shutdown → get_scheduled_termination_status
- For RunPod GPU tools, INCLUDE the FULL message returned by the tool in reply.
- Chitchat → just reply

Status: queued/todo=do now, upcoming/backlog=later (DEFAULT), in_progress, stuck, done, cancelled
Area: ui, api, backend, frontend, database, tools, docs, infra`;
}

/**
 * Process user message with multi-turn tool use
 *
 * This is the core agent loop:
 * 1. Send message to Claude with available tools
 * 2. If Claude calls tools, execute them and feed results back
 * 3. Repeat until Claude responds with text or calls 'reply'
 *
 * @param userMessage - The current message
 * @param conversationHistory - Previous messages for context
 * @param notifyCallback - Callback for executor notifications
 * @returns Final result with actions taken and reply
 */
export async function parseTask(
  userMessage: string,
  conversationHistory: ConversationMessage[] = [],
  notifyCallback: NotifyCallback | null = null,
  requesterUserId: string | null = null,
): Promise<ParseTaskResult> {
  // Build context for tool execution
  const toolContext: ToolContext = {
    notifyCallback,
    requesterUserId,
  };

  // Build the user message with optional conversation history
  let fullMessage = userMessage;

  if (conversationHistory.length > 0) {
    const historyText = conversationHistory
      .map((m) => `${m.role === 'assistant' ? 'Bot' : 'User'}: ${m.content}`)
      .join('\n');

    fullMessage = `${userMessage}

---
PREVIOUS CONVERSATION (last ${conversationHistory.length} messages - look for task IDs):
${historyText}`;
  }

  const messages: Anthropic.MessageParam[] = [{ role: 'user', content: fullMessage }];
  const actions: ToolAction[] = [];
  let finalReply: string | null = null;
  let iterations = 0;
  const maxIterations = 10;

  const systemPrompt = buildSystemPrompt();
  const tools = getToolSchemas();

  logger.debug('Starting agent loop', {
    messageLength: userMessage.length,
    historyLength: conversationHistory.length,
    toolCount: tools.length,
  });

  while (iterations < maxIterations) {
    iterations++;
    logger.debug('Agent iteration', { iteration: iterations });

    // Call Claude
    let response: Anthropic.Message;
    try {
      response = await client.messages.create({
        model: config.anthropic.model,
        max_tokens: 1024,
        system: systemPrompt,
        tools,
        messages,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error('Anthropic API error', error instanceof Error ? error : undefined);
      throw new ExternalServiceError('anthropic', message);
    }

    logger.debug('Claude response', { contentTypes: response.content.map((c) => c.type) });

    // Check if Claude is done (no more tool calls)
    const toolUses = response.content.filter(
      (c): c is Anthropic.ToolUseBlock => c.type === 'tool_use',
    );

    if (toolUses.length === 0) {
      // Claude responded with text only - extract it as the reply
      const textContent = response.content.find(
        (c): c is Anthropic.TextBlock => c.type === 'text',
      );
      if (textContent) {
        finalReply = textContent.text;
      }
      break;
    }

    // Process each tool call
    const toolResults: Anthropic.ToolResultBlockParam[] = [];
    for (const toolUse of toolUses) {
      logger.info('Executing tool', { tool: toolUse.name });

      const result = await executeTool(
        toolUse.name,
        toolUse.input as Record<string, unknown>,
        toolContext,
      );

      // Track the action
      actions.push({
        tool: toolUse.name,
        input: toolUse.input as Record<string, unknown>,
        result,
      });

      // If this was a reply tool, capture it
      if (toolUse.name === 'reply' && result.success && result.message) {
        finalReply = result.message;
      }

      toolResults.push({
        type: 'tool_result',
        tool_use_id: toolUse.id,
        content: JSON.stringify(result),
        is_error: !result.success,
      });
    }

    // Add assistant message and tool results to conversation
    messages.push({ role: 'assistant', content: response.content });
    messages.push({ role: 'user', content: toolResults });

    // If the last tool was 'reply', we're done
    if (toolUses.some((t) => t.name === 'reply')) {
      break;
    }
  }

  logger.info('Agent loop completed', {
    iterations,
    actionsCount: actions.length,
    hasReply: !!finalReply,
  });

  return {
    actions,
    reply: finalReply,
  };
}



