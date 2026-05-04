import { toErrorMessage } from "../../_shared/errorMessage.ts";
import { isRecord } from "../utils.ts";
import type {
  AgentSession,
  AgentSessionStatus,
  AgentTurn,
  LlmMessage,
  TimelineRow,
} from "../types.ts";
import type { AssetRegistry, TimelineConfig } from "../../../../src/tools/video-editor/index.ts";
export { isRecord } from "../utils.ts";

export function isSessionStatus(value: unknown): value is AgentSessionStatus {
  return value === "waiting_user"
    || value === "processing"
    || value === "continue"
    || value === "done"
    || value === "cancelled"
    || value === "error";
}

export function normalizeTurns(value: unknown): AgentTurn[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.content !== "string" || typeof item.timestamp !== "string") {
      return [];
    }

    const role = item.role;
    if (role !== "user" && role !== "assistant" && role !== "tool_call" && role !== "tool_result") {
      return [];
    }

    return [{
      role,
      content: item.content,
      attachments: Array.isArray(item.attachments) ? item.attachments : undefined,
      tool_name: typeof item.tool_name === "string" ? item.tool_name : undefined,
      tool_args: isRecord(item.tool_args) ? item.tool_args : undefined,
      timestamp: item.timestamp,
    }];
  });
}

export function createTurn(role: AgentTurn["role"], content: string): AgentTurn {
  return {
    role,
    content,
    timestamp: new Date().toISOString(),
  };
}

export function createToolTurn(
  role: Extract<AgentTurn["role"], "tool_call" | "tool_result">,
  toolName: string,
  content: string,
  toolArgs: Record<string, unknown>,
): AgentTurn {
  return {
    role,
    content,
    tool_name: toolName,
    tool_args: toolArgs,
    timestamp: new Date().toISOString(),
  };
}

export function normalizeSessionRow(row: Record<string, unknown>): AgentSession {
  return {
    id: typeof row.id === "string" ? row.id : "",
    timeline_id: typeof row.timeline_id === "string" ? row.timeline_id : "",
    user_id: typeof row.user_id === "string" ? row.user_id : "",
    status: isSessionStatus(row.status) ? row.status : "error",
    turns: normalizeTurns(row.turns),
    model: typeof row.model === "string" ? row.model : "openrouter",
    summary: typeof row.summary === "string" ? row.summary : null,
    cancelled_at: typeof row.cancelled_at === "string" ? row.cancelled_at : null,
    cancelled_by: typeof row.cancelled_by === "string" ? row.cancelled_by : null,
    cancel_source: typeof row.cancel_source === "string" ? row.cancel_source : null,
    cancel_reason: typeof row.cancel_reason === "string" ? row.cancel_reason : null,
    created_at: typeof row.created_at === "string" ? row.created_at : "",
    updated_at: typeof row.updated_at === "string" ? row.updated_at : "",
  };
}

export function normalizeTimelineRow(row: Record<string, unknown>): TimelineRow {
  return {
    config: (row.config as TimelineConfig | null)
      ?? { output: { resolution: "1920x1080", fps: 30, file: "output.mp4" }, clips: [] },
    config_version: typeof row.config_version === "number" ? row.config_version : 1,
    asset_registry: (row.asset_registry as AssetRegistry | null) ?? { assets: {} },
    project_id: typeof row.project_id === "string" ? row.project_id : "",
  };
}

export function parseToolArgsSafely(rawArguments: unknown): {
  args: Record<string, unknown>;
  error: string | null;
} {
  if (typeof rawArguments !== "string" || !rawArguments.trim()) {
    return { args: {}, error: null };
  }

  try {
    const parsed = JSON.parse(rawArguments);
    // Accept null, empty arrays, etc. as "no args" — only reject non-object primitives like strings/numbers
    if (parsed === null || parsed === undefined) {
      return { args: {}, error: null };
    }
    if (typeof parsed !== "object") {
      console.warn(`[agent] Tool args parsed to non-object: ${typeof parsed} — ${rawArguments.slice(0, 100)}`);
      return { args: {}, error: null };
    }
    return { args: isRecord(parsed) ? parsed : {}, error: null };
  } catch (error: unknown) {
    console.warn(`[agent] Failed to parse tool args: ${rawArguments.slice(0, 200)}`);
    return {
      args: {},
      error: `Invalid tool arguments JSON: ${toErrorMessage(error)}`,
    };
  }
}

export function formatToolArgs(toolArgs: Record<string, unknown>): string {
  return JSON.stringify(toolArgs, null, 2);
}

export function summarizeStoredToolTurn(turn: AgentTurn): string {
  const toolName = turn.tool_name ?? "tool";
  if (turn.role === "tool_call") {
    return `Tool call ${toolName}:\n${formatToolArgs(turn.tool_args ?? {})}`;
  }

  return `Tool result ${toolName}: ${turn.content}`;
}

export function buildInitialMessages(
  systemPrompt: string,
  turns: AgentTurn[],
  sessionSummary?: string | null,
): LlmMessage[] {
  // Fold session summary into the system prompt so the LLM treats it as ground truth
  const fullSystemPrompt = sessionSummary
    ? `${systemPrompt}\n\n## Session history\nThis is an ongoing session. Here is what happened earlier:\n\n${sessionSummary}\n\nThe user's next message continues this session. Always use tools (create_task, etc.) to execute requests — never just describe what you would do.`
    : systemPrompt;

  const messages: LlmMessage[] = [{ role: "system", content: fullSystemPrompt }];

  for (const turn of turns) {
    if (turn.role === "user") {
      messages.push({ role: "user", content: turn.content });
      continue;
    }

    if (turn.role === "assistant") {
      messages.push({ role: "assistant", content: turn.content });
      continue;
    }

    messages.push({
      role: "assistant",
      content: summarizeStoredToolTurn(turn),
    });
  }

  return messages;
}

export function extractAssistantText(message: { content?: unknown }): string {
  if (typeof message.content === "string") {
    return message.content.trim();
  }

  if (!Array.isArray(message.content)) {
    return "";
  }

  return message.content
    .flatMap((item) => {
      if (!isRecord(item)) {
        return [];
      }

      const text = item.text;
      return typeof text === "string" ? [text] : [];
    })
    .join("\n")
    .trim();
}
