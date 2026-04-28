import type { EdgeRuntime } from "../_shared/edgeRequest.ts";
import { toErrorMessage } from "../_shared/errorMessage.ts";
import {
  GROQ_TRIAGE_MODEL,
  GROQ_TIMEOUT_MS,
  LOOP_LIMIT,
  SOFT_TIMEOUT_MS,
  SUMMARIZE_THRESHOLD,
} from "./config.ts";
import {
  fetchProjectTasks,
  loadActiveReference,
  loadProjectImageSettings,
  loadShotVideoTravelSettings,
  loadSessionStatus,
  loadTimelineState,
  persistSessionState,
} from "./db.ts";
import Groq from "npm:groq-sdk@0.26.0";
import { invokeLlm, triageDifficulty } from "./llm/client.ts";
import {
  buildInitialMessages,
  createToolTurn,
  createTurn,
  extractAssistantText,
  isRecord,
} from "./llm/messages.ts";
import { buildTimelineAgentSystemPrompt } from "./prompts.ts";
import { resolveTimelinePlacement } from "./selectedClips.ts";
import {
  extractToolCalls,
  isToolError,
  type ExtractedToolCall,
} from "./tool-calls.ts";
import { TIMELINE_AGENT_TOOLS } from "./tool-schemas.ts";
import { asStringArray, asTrimmedString } from "./utils.ts";
import {
  createShotWithGenerations,
  resolveSelectedClipShot,
} from "./tools/clips.ts";
import { executeCreateTask } from "./tools/create-task.ts";
import {
  executeDelegateToBanodocoAgent,
  findLatestPendingDelegate,
  pollBanodocoTaskStatus,
  summariseTaskStatusForChat,
} from "./tools/delegateToBanodocoAgent.ts";
import { executeDuplicateGeneration } from "./tools/duplicate-generation.ts";
import { executeSearchLoras, executeSetLora } from "./tools/loras.ts";
import { executeCommand } from "./tools/registry.ts";
import {
  setClipParams as setClipParamsHandler,
  setTheme as setThemeHandler,
  setThemeOverrides as setThemeOverridesHandler,
  viewTimeline,
} from "./tools/timeline.ts";
import { saveTimelineConfigVersioned } from "./db.ts";
import { executeTransformImage } from "./tools/transform-image.ts";
import type {
  AgentSession,
  AgentSessionStatus,
  AgentTurn,
  GenerationContext,
  LlmMessage,
  SelectedClipPayload,
  SupabaseAdmin,
  TimelineState,
  ToolResult,
} from "./types.ts";

type LoopLogger = Pick<EdgeRuntime["logger"], "error" | "info" | "warn">;

const APPEND_SHOT_POSITION = 2_147_483_647;

// ── Session summarization ──────────────────────────────────────────

function summarizeToolCallArgs(toolName: string, args: Record<string, unknown> | undefined): string {
  if (!args) return "";
  if (toolName === "create_task") {
    // Keep the fields that matter for continuity
    const parts: string[] = [];
    if (args.task_type) parts.push(`task_type=${args.task_type}`);
    if (args.prompt) parts.push(`prompt="${String(args.prompt).slice(0, 150)}"`);
    if (args.count) parts.push(`count=${args.count}`);
    if (args.model) parts.push(`model=${args.model}`);
    if (Array.isArray(args.reference_image_urls) && args.reference_image_urls.length > 0) {
      parts.push(`reference_image_urls=${JSON.stringify(args.reference_image_urls)}`);
    }
    return parts.join(", ");
  }
  return JSON.stringify(args).slice(0, 200);
}

function turnsToTranscript(turns: AgentTurn[]): string {
  const lines: string[] = [];
  for (const turn of turns) {
    if (turn.role === "user") {
      lines.push(`USER: ${turn.content}`);
    } else if (turn.role === "assistant") {
      lines.push(`ASSISTANT: ${turn.content}`);
    } else if (turn.role === "tool_call") {
      lines.push(`TOOL CALL ${turn.tool_name}: ${summarizeToolCallArgs(turn.tool_name ?? "", turn.tool_args)}`);
    } else if (turn.role === "tool_result") {
      lines.push(`TOOL RESULT ${turn.tool_name}: ${turn.content}`);
    }
  }
  return lines.join("\n");
}

async function summarizeTurns(
  turnsToSummarize: AgentTurn[],
  existingSummary: string | null,
  logger: LoopLogger,
): Promise<string | null> {
  const apiKey = Deno.env.get("GROQ_API_KEY");
  if (!apiKey) return existingSummary;

  const transcript = turnsToTranscript(turnsToSummarize);
  if (!transcript.trim()) return existingSummary;

  const systemMsg = `You summarize AI agent conversation history for an image/video generation tool. Write a concise summary that captures:

1. What the user originally asked for and their creative direction
2. What tasks were created (task types, counts, key prompts used)
3. What reference images were used (include URLs so they can be reused)
4. The user's latest feedback or direction — what they liked, what they want changed
5. Any unresolved requests or issues

Keep it factual and compact. Use bullet points. Include specific URLs and prompt text — these are needed for follow-up requests.`;

  const userMsg = existingSummary
    ? `Here is the existing summary of earlier conversation:\n${existingSummary}\n\nHere is the new conversation to incorporate:\n${transcript}\n\nProduce an updated combined summary.`
    : `Summarize this conversation:\n${transcript}`;

  try {
    const groq = new Groq({ apiKey, timeout: GROQ_TIMEOUT_MS });
    const resp = await groq.chat.completions.create({
      model: GROQ_TRIAGE_MODEL,
      messages: [
        { role: "system", content: systemMsg },
        { role: "user", content: userMsg },
      ],
      temperature: 0.1,
      max_tokens: 1024,
    });
    const summary = resp.choices[0]?.message?.content?.trim();
    if (summary) {
      logger.info("Session summarized", { oldTurns: turnsToSummarize.length, summaryLength: summary.length });
      return summary;
    }
  } catch (err: unknown) {
    logger.error("Failed to summarize session", { error: toErrorMessage(err) });
  }
  return existingSummary;
}

const MAX_TURNS_TO_SUMMARIZE = 30; // Cap per summarization call to avoid token limits

async function maybeCompressSession(
  turns: AgentTurn[],
  existingSummary: string | null,
  logger: LoopLogger,
): Promise<{ turns: AgentTurn[]; summary: string | null }> {
  if (turns.length <= SUMMARIZE_THRESHOLD) {
    return { turns, summary: existingSummary };
  }

  // Keep the most recent turns, summarize a bounded chunk of older ones
  const keepCount = Math.floor(SUMMARIZE_THRESHOLD / 2);
  const olderTurns = turns.slice(0, turns.length - keepCount);
  const recentTurns = turns.slice(turns.length - keepCount);

  // Only summarize the most recent chunk of older turns (closest to current context)
  // If there's a huge backlog, we drop the oldest turns — the existing summary
  // (if any) already covers earlier history
  const turnsToSummarize = olderTurns.length > MAX_TURNS_TO_SUMMARIZE
    ? olderTurns.slice(-MAX_TURNS_TO_SUMMARIZE)
    : olderTurns;

  const summary = await summarizeTurns(turnsToSummarize, existingSummary, logger);
  return { turns: recentTurns, summary };
}

export interface RunAgentLoopOptions {
  session: AgentSession;
  userMessage?: string;
  selectedClips?: SelectedClipPayload[];
  supabaseAdmin: SupabaseAdmin;
  // Sprint 7 (SD-022): the raw user JWT, threaded through to
  // delegateToBanodocoAgent so the orchestrator + worker can re-verify
  // identity. Empty string when the caller authenticated via PAT or
  // service-role; in that case the delegate tool will refuse.
  userJwt?: string;
  logger: LoopLogger;
}

export interface RunAgentLoopResult {
  status: AgentSessionStatus;
  turns: AgentTurn[];
  summary: string | null;
}

function attachSelectedClips(
  turn: AgentTurn,
  selectedClips?: SelectedClipPayload[],
) {
  if (!selectedClips?.length) {
    return;
  }

  turn.attachments = selectedClips.map((clip) => ({
    clipId: clip.clip_id,
    url: clip.url,
    mediaType: clip.media_type,
    ...(typeof clip.is_timeline_backed === "boolean"
      ? { isTimelineBacked: clip.is_timeline_backed }
      : {}),
    ...(clip.generation_id ? { generationId: clip.generation_id } : {}),
    ...(clip.prompt ? { prompt: clip.prompt } : {}),
    ...(clip.shot_id ? { shotId: clip.shot_id } : {}),
    ...(clip.shot_name ? { shotName: clip.shot_name } : {}),
    ...(typeof clip.shot_selection_clip_count === "number"
      ? { shotSelectionClipCount: clip.shot_selection_clip_count }
      : {}),
    ...(clip.track_id ? { trackId: clip.track_id } : {}),
    ...(typeof clip.at === "number" ? { at: clip.at } : {}),
    ...(typeof clip.duration === "number" ? { duration: clip.duration } : {}),
    ...(clip.timeline_placement ? { timelinePlacement: clip.timeline_placement } : {}),
  }));
}

function enrichSelectedClipsWithTimelinePlacement(
  selectedClips: SelectedClipPayload[] | undefined,
  timelineState: TimelineState,
  timelineId: string,
): SelectedClipPayload[] | undefined {
  if (!selectedClips?.length) {
    return selectedClips;
  }

  const timelineBackedClips = selectedClips.filter((clip) => clip.is_timeline_backed);
  if (timelineBackedClips.length !== 1) {
    return selectedClips;
  }

  const sourceClip = timelineBackedClips[0];
  const timelinePlacement = resolveTimelinePlacement(sourceClip, timelineState, timelineId);
  if (!timelinePlacement) {
    return selectedClips;
  }

  return selectedClips.map((clip) => (
    clip.clip_id === sourceClip.clip_id
      ? { ...clip, timeline_placement: timelinePlacement }
      : clip
  ));
}

export function recoverSelectedClipsFromTurns(turns: AgentTurn[]): SelectedClipPayload[] {
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const turn = turns[index];
    if (turn?.role !== "user" || !Array.isArray(turn.attachments) || turn.attachments.length === 0) {
      continue;
    }

    return turn.attachments.flatMap((attachment) => {
      if (!isRecord(attachment)) {
        return [];
      }

      const clipId = typeof attachment.clipId === "string" ? attachment.clipId.trim() : "";
      const url = typeof attachment.url === "string" ? attachment.url.trim() : "";
      const mediaType = attachment.mediaType;
      const generationId = typeof attachment.generationId === "string" && attachment.generationId.trim()
        ? attachment.generationId.trim()
        : undefined;
      const prompt = typeof attachment.prompt === "string" && attachment.prompt.trim()
        ? attachment.prompt.trim()
        : undefined;
      const isTimelineBacked = typeof attachment.isTimelineBacked === "boolean"
        ? attachment.isTimelineBacked
        : undefined;
      const shotId = typeof attachment.shotId === "string" && attachment.shotId.trim()
        ? attachment.shotId.trim()
        : undefined;
      const shotName = typeof attachment.shotName === "string" && attachment.shotName.trim()
        ? attachment.shotName.trim()
        : undefined;
      const trackId = typeof attachment.trackId === "string" && attachment.trackId.trim()
        ? attachment.trackId.trim()
        : undefined;
      const at = typeof attachment.at === "number" && Number.isFinite(attachment.at)
        ? attachment.at
        : undefined;
      const duration = typeof attachment.duration === "number"
        && Number.isFinite(attachment.duration)
        && attachment.duration >= 0
        ? attachment.duration
        : undefined;
      const timelinePlacement = isRecord(attachment.timelinePlacement)
        && typeof attachment.timelinePlacement.timeline_id === "string"
        && attachment.timelinePlacement.timeline_id.trim()
        && typeof attachment.timelinePlacement.source_clip_id === "string"
        && attachment.timelinePlacement.source_clip_id.trim()
        && typeof attachment.timelinePlacement.target_track === "string"
        && attachment.timelinePlacement.target_track.trim()
        && typeof attachment.timelinePlacement.insertion_time === "number"
        && Number.isFinite(attachment.timelinePlacement.insertion_time)
        && (attachment.timelinePlacement.intent === "after_source" || attachment.timelinePlacement.intent === "replace")
        ? {
          timeline_id: attachment.timelinePlacement.timeline_id.trim(),
          source_clip_id: attachment.timelinePlacement.source_clip_id.trim(),
          target_track: attachment.timelinePlacement.target_track.trim(),
          insertion_time: attachment.timelinePlacement.insertion_time,
          intent: attachment.timelinePlacement.intent,
        }
        : undefined;
      const shotSelectionClipCount = typeof attachment.shotSelectionClipCount === "number"
        && Number.isFinite(attachment.shotSelectionClipCount)
        && attachment.shotSelectionClipCount > 0
        ? attachment.shotSelectionClipCount
        : undefined;

      if (!clipId || !url || (mediaType !== "image" && mediaType !== "video")) {
        return [];
      }

      return [{
        clip_id: clipId,
        url,
        media_type: mediaType,
        ...(generationId ? { generation_id: generationId } : {}),
        ...(prompt ? { prompt } : {}),
        ...(shotId ? { shot_id: shotId } : {}),
        ...(shotName ? { shot_name: shotName } : {}),
        ...(trackId ? { track_id: trackId } : {}),
        ...(typeof at === "number" ? { at } : {}),
        ...(typeof duration === "number" ? { duration } : {}),
        ...(typeof isTimelineBacked === "boolean" ? { is_timeline_backed: isTimelineBacked } : {}),
        ...(timelinePlacement ? { timeline_placement: timelinePlacement } : {}),
        ...(shotSelectionClipCount ? { shot_selection_clip_count: shotSelectionClipCount } : {}),
      }];
    });
  }

  return [];
}

function resolveSharedShotName(
  selectedClips: SelectedClipPayload[] | undefined,
  shotId: string | null,
  timelineState: TimelineState,
): string | null {
  if (!shotId) {
    return null;
  }

  const explicitShotName = selectedClips?.find((clip) => clip.shot_id === shotId)?.shot_name;
  if (typeof explicitShotName === "string" && explicitShotName.trim()) {
    return explicitShotName.trim();
  }

  return timelineState.shotNamesById[shotId] ?? null;
}

export function cleanAssistantText(text: string): string {
  return text
    .replace(/\[TOOL_CALL\][\s\S]*?\[\/TOOL_CALL\]/g, "")
    .replace(/<invoke[\s\S]*?<\/invoke>/g, "")
    .replace(/Tool call \w+:[\s\S]*?(?=\n\n|$)/g, "")
    .replace(/(?:run|create_task)\s*\([^)]*\)/g, "")
    .replace(/^\s*\d+[.):-]\s*(set-text|move|trim|delete|duplicate|add-text|set|view|find-issues|generate)\b.*$/gm, "")
    .trim();
}

async function executeCreateShot(
  args: Record<string, unknown>,
  timelineState: TimelineState,
  supabaseAdmin: SupabaseAdmin,
): Promise<Pick<ToolResult, "result">> {
  const shotName = asTrimmedString(args.shot_name);
  const generationIds = asStringArray(args.generation_ids);

  if (!shotName) {
    return { result: "create_shot requires shot_name." };
  }

  if (generationIds.length === 0) {
    return { result: "create_shot requires at least one generation_id." };
  }

  const shotId = await createShotWithGenerations(supabaseAdmin, {
    projectId: timelineState.projectId,
    shotName,
    generationIds,
    position: APPEND_SHOT_POSITION,
  });

  return {
    result: `Created shot ${shotName} (${shotId}) with ${generationIds.length} generation(s).`,
  };
}

async function executeGetTasks(
  args: Record<string, unknown>,
  timelineState: TimelineState,
  supabaseAdmin: SupabaseAdmin,
): Promise<ToolResult> {
  const tasks = await fetchProjectTasks(supabaseAdmin, timelineState.projectId, {
    status: typeof args.status === "string" ? args.status : undefined,
    taskId: typeof args.task_id === "string" ? args.task_id : undefined,
    limit: typeof args.limit === "number" ? args.limit : undefined,
  });

  if (tasks.length === 0) {
    return { result: "No tasks found." };
  }

  const lines = tasks.map((t) => {
    const age = timeSince(t.created_at);
    let line = `• ${t.id.slice(0, 8)} | ${t.task_type} | ${t.status} | ${age}`;
    if (t.params_summary) line += ` | ${t.params_summary}`;
    if (t.error_message) line += `\n  Error: ${t.error_message.slice(0, 200)}`;
    if (t.status === "In Progress" && t.generation_started_at) {
      line += ` | running ${timeSince(t.generation_started_at)}`;
    }
    if (t.status === "Complete" && t.attempts > 1) {
      line += ` | ${t.attempts} attempts`;
    }
    return line;
  });

  return { result: `${tasks.length} task(s):\n${lines.join("\n")}` };
}

function timeSince(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return `${Math.round(ms / 1000)}s ago`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m ago`;
  return `${Math.round(ms / 3_600_000)}h ago`;
}

export async function executeToolCall(
  toolCall: ExtractedToolCall,
  timelineState: TimelineState,
  supabaseAdmin: SupabaseAdmin,
  timelineId: string,
  selectedClips?: SelectedClipPayload[],
  generationContext?: GenerationContext,
  userId?: string,
  logger?: LoopLogger,
  userJwt?: string,
): Promise<ToolResult> {
  const toolArgs = toolCall.args;

  if (toolCall.parseError) {
    return { result: toolCall.parseError };
  }

  // Sprint 7 (SD-020 + SD-034 + SD-035): bidirectional generative handoff.
  if (toolCall.name === "delegateToBanodocoAgent") {
    return await executeDelegateToBanodocoAgent(
      toolArgs,
      timelineState,
      timelineId,
      userJwt,
    );
  }

  if (toolCall.name === "run") {
    return typeof toolArgs.command === "string" && toolArgs.command.trim()
      ? await executeCommand(
        toolArgs.command,
        timelineState,
        timelineId,
        supabaseAdmin,
      )
      : { result: "run requires command." };
  }

  if (toolCall.name === "create_task") {
    return await executeCreateTask(toolArgs, timelineState, selectedClips, supabaseAdmin, generationContext, timelineId, logger);
  }

  if (toolCall.name === "transform_image") {
    return await executeTransformImage(toolArgs, selectedClips, userId);
  }

  if (toolCall.name === "search_loras") {
    return await executeSearchLoras(toolArgs, supabaseAdmin, userId);
  }

  if (toolCall.name === "set_lora") {
    return await executeSetLora(toolArgs, timelineState, selectedClips, supabaseAdmin, generationContext);
  }

  if (toolCall.name === "duplicate_generation") {
    return await executeDuplicateGeneration(toolArgs, timelineState, selectedClips, supabaseAdmin);
  }

  if (toolCall.name === "create_shot") {
    return await executeCreateShot(toolArgs, timelineState, supabaseAdmin);
  }

  if (toolCall.name === "get_tasks") {
    return await executeGetTasks(toolArgs, timelineState, supabaseAdmin);
  }

  // Sprint 4 (SD-018): direct themed-editing tools — set_params,
  // set_theme, set_theme_overrides. These mutate timeline.config and need
  // versioned save, mirroring the `run` tool's persistence path. They do
  // NOT route through the slash-command parser because the parser is
  // media-only (Option B); themed-field edits are intentionally
  // chat-only.
  if (
    toolCall.name === "set_params"
    || toolCall.name === "set_theme"
    || toolCall.name === "set_theme_overrides"
  ) {
    timelineState.previousConfig = structuredClone(timelineState.config);
    const handler = toolCall.name === "set_params"
      ? setClipParamsHandler
      : toolCall.name === "set_theme"
        ? setThemeHandler
        : setThemeOverridesHandler;
    const result = handler(timelineState.config, timelineState.registry, toolArgs as never);
    if (!result.config) {
      return result;
    }
    const nextVersion = await saveTimelineConfigVersioned(
      supabaseAdmin,
      timelineId,
      timelineState.configVersion,
      result.config,
    );
    if (nextVersion === null) {
      return { result: "Version conflict. Please retry." };
    }
    timelineState.config = result.config;
    timelineState.configVersion = nextVersion;
    return result;
  }

  return { result: `Unknown tool: ${toolCall.name}.` };
}

export function buildToolErrorTurn(toolCallId: string, error: unknown): AgentTurn {
  return createTurn("assistant", `[TOOL ERROR ${toolCallId}] ${toErrorMessage(error)}`);
}

async function processToolCalls({
  toolCalls,
  assistantText,
  turns,
  messages,
  timelineState,
  selectedClips,
  generationContext,
  supabaseAdmin,
  timelineId,
  userId,
  userJwt,
  setActiveToolCallId,
  logger,
}: {
  toolCalls: ExtractedToolCall[];
  assistantText: string;
  turns: AgentTurn[];
  messages: LlmMessage[];
  timelineState: TimelineState;
  selectedClips?: SelectedClipPayload[];
  generationContext?: GenerationContext;
  supabaseAdmin: SupabaseAdmin;
  timelineId: string;
  userId?: string;
  // Sprint 7 (SD-022): forwarded to delegateToBanodocoAgent.
  userJwt?: string;
  setActiveToolCallId: (toolCallId: string | null) => void;
  logger?: LoopLogger;
}): Promise<{ hasError: boolean }> {
  let hasError = false;

  for (const toolCall of toolCalls) {
    const toolArgs = toolCall.args;
    const toolContent = toolCall.name === "run"
      ? (typeof toolArgs.command === "string" ? toolArgs.command : JSON.stringify(toolArgs))
      : JSON.stringify(toolArgs);

    setActiveToolCallId(toolCall.id);
    turns.push(createToolTurn("tool_call", toolCall.name, toolContent, toolArgs));
    messages.push({
      role: "assistant",
      content: null,
      tool_calls: [{
        id: toolCall.id,
        type: "function" as const,
        function: { name: toolCall.name, arguments: JSON.stringify(toolArgs) },
      }],
    });

    const result = await executeToolCall(
      toolCall,
      timelineState,
      supabaseAdmin,
      timelineId,
      selectedClips,
      generationContext,
      userId,
      logger,
      userJwt,
    );
    setActiveToolCallId(null);

    turns.push(createToolTurn("tool_result", toolCall.name, result.result, toolArgs));
    messages.push({
      role: "tool",
      tool_call_id: toolCall.id,
      content: result.result,
    });

    if (isToolError(result.result)) {
      hasError = true;
      break;
    }
  }

  setActiveToolCallId(null);

  if (assistantText) {
    const cleaned = cleanAssistantText(assistantText);
    if (cleaned && cleaned.length > 2) {
      turns.push(createTurn("assistant", cleaned));
    }
  }

  if (hasError) {
    const lastResult = turns[turns.length - 1];
    messages.push({
      role: "user",
      content: `Tool failed: "${lastResult?.content ?? "unknown error"}". You can: (1) run(command="...") with a corrected timeline command, (2) create_task({...}) with corrected task arguments, (3) run(command="view") to inspect the timeline, or (4) reply in plain text to tell the user what went wrong.`,
    });
  }

  return { hasError };
}

// Sprint 7 (SD-034 status path): if a delegateToBanodocoAgent tool call is
// in flight (i.e. the most recent tool_result for that tool reports
// "queued"), poll the orchestrator's task-status endpoint at the start of
// each loop turn and surface the state transition as a chat message
// before the LLM is asked for its next action. The LLM sees the status
// update via the appended assistant turn and can react.
async function maybeSurfaceBanodocoStatus(
  turns: AgentTurn[],
  userJwt: string | undefined,
  logger: LoopLogger,
): Promise<void> {
  if (!userJwt) {
    return;
  }
  const pending = findLatestPendingDelegate(turns);
  if (!pending) {
    return;
  }
  // Skip if the very last turn is already a status update for this task.
  const last = turns[turns.length - 1];
  if (
    last?.role === "assistant"
    && typeof last.content === "string"
    && last.content.includes(pending.task_id)
  ) {
    return;
  }
  try {
    const snap = await pollBanodocoTaskStatus(pending.task_id, userJwt);
    const summary = summariseTaskStatusForChat(snap);
    turns.push(createTurn("assistant", `[banodoco-status ${pending.task_id}] ${summary}`));
  } catch (err) {
    logger.warn?.("Failed to poll banodoco task status", {
      task_id: pending.task_id,
      error: toErrorMessage(err),
    });
  }
}

export async function runAgentLoop(
  options: RunAgentLoopOptions,
): Promise<RunAgentLoopResult> {
  const { session, userMessage, selectedClips, supabaseAdmin, userJwt, logger } = options;
  const effectiveSelectedClips = selectedClips?.length
    ? selectedClips
    : recoverSelectedClipsFromTurns(session.turns);

  const lastTurn = session.turns[session.turns.length - 1];
  const isDuplicate = userMessage && lastTurn?.role === "user" && lastTurn.content === userMessage;
  const turns = [...session.turns];
  if (userMessage && !isDuplicate) {
    const userTurn = createTurn("user", userMessage);
    attachSelectedClips(userTurn, effectiveSelectedClips);
    turns.push(userTurn);
  }
  let status: AgentSessionStatus = "processing";
  let activeToolCallId: string | null = null;

  let summary = session.summary;

  try {
    await persistSessionState(supabaseAdmin, {
      sessionId: session.id,
      status,
      turns,
      summary,
    });

    const timelineState = await loadTimelineState(supabaseAdmin, session.timeline_id);
    const resolvedSelectedClips = enrichSelectedClipsWithTimelinePlacement(
      effectiveSelectedClips,
      timelineState,
      session.timeline_id,
    );
    if (userMessage && !isDuplicate) {
      const currentUserTurn = turns[turns.length - 1];
      if (currentUserTurn?.role === "user") {
        attachSelectedClips(currentUserTurn, resolvedSelectedClips);
      }
    }
    const imageSettings = await loadProjectImageSettings(supabaseAdmin, timelineState.projectId);
    const clipShotResolution = await resolveSelectedClipShot(
      supabaseAdmin,
      timelineState,
      resolvedSelectedClips,
    );
    const clipShotId = clipShotResolution.shotId;
    const clipShotName = resolveSharedShotName(resolvedSelectedClips, clipShotId, timelineState);
    const travelSettings = clipShotId
      ? await loadShotVideoTravelSettings(supabaseAdmin, clipShotId)
      : null;
    const activeReference = imageSettings
      ? await loadActiveReference(supabaseAdmin, imageSettings, clipShotId ?? undefined)
      : null;
    const generationContext: GenerationContext = {
      image: imageSettings
        ? {
          defaultModelName: imageSettings.selectedTextModel ?? "qwen-image",
          activeReference,
          selectedLorasByCategory: imageSettings.selectedLorasByCategory,
        }
        : null,
      travel: travelSettings,
    };
    const timelineSummary = viewTimeline(
      timelineState.config,
      timelineState.registry,
      timelineState.shotNamesById,
    ).result;
    const systemPrompt = buildTimelineAgentSystemPrompt({
      projectId: timelineState.projectId,
      timelineSummary,
      selectedClips: resolvedSelectedClips,
      defaultModel: generationContext.image?.defaultModelName,
      activeReference: generationContext.image?.activeReference ?? null,
      travelSettings,
      imageLorasByCategory: generationContext.image?.selectedLorasByCategory ?? null,
      sharedShotId: clipShotId,
      sharedShotName: clipShotName,
    });
    // Compress long sessions: summarize old turns, keep recent ones
    const compressed = await maybeCompressSession(turns, summary, logger);
    summary = compressed.summary;
    if (compressed.turns.length < turns.length) {
      // Replace turns with compressed version
      turns.length = 0;
      turns.push(...compressed.turns);
    }

    const messages = buildInitialMessages(systemPrompt, turns, summary);
    const startedAt = Date.now();

    // Triage the user message to pick provider: easy/okay → Kimi K2.5, hard → Claude
    const difficulty = userMessage
      ? await triageDifficulty(userMessage, logger)
      : "okay";

    for (let iteration = 0; iteration < LOOP_LIMIT; iteration += 1) {
      if (Date.now() - startedAt >= SOFT_TIMEOUT_MS) {
        status = "continue";
        break;
      }

      // Sprint 7 (SD-034 status path): on each turn, check whether a
      // banodoco task is pending and surface its status before invoking
      // the LLM.
      await maybeSurfaceBanodocoStatus(turns, userJwt, logger);

      const currentStatus = await loadSessionStatus(supabaseAdmin, session.id);
      if (currentStatus === "cancelled") {
        logger.info("Detected cancelled session during agent loop", {
          session_id: session.id,
          status: currentStatus,
        });
        status = "cancelled";
        break;
      }

      let completion;
      try {
        completion = await invokeLlm(
          {
            messages: messages as unknown[],
            tools: TIMELINE_AGENT_TOOLS as unknown[],
            tool_choice: "auto",
            temperature: 0.2,
            max_tokens: 4096,
            top_p: 1,
          },
          difficulty,
          logger,
        );
      } catch (llmError: unknown) {
        const text = `AI service error: ${toErrorMessage(llmError)}`;
        turns.push(createTurn("assistant", text));
        messages.push({ role: "assistant", content: text });
        status = "waiting_user";
        break;
      }

      const responseMessage = completion.choices[0]?.message;
      if (!responseMessage) {
        turns.push(createTurn("assistant", "No response from AI."));
        status = "waiting_user";
        break;
      }

      const extractedToolCalls = extractToolCalls(responseMessage);
      const assistantText = extractAssistantText(responseMessage);

      if (extractedToolCalls.length === 0) {
        const text = assistantText || "What would you like me to do?";
        turns.push(createTurn("assistant", text));
        messages.push({ role: "assistant", content: text });
        status = "waiting_user";
        break;
      }

      const { hasError } = await processToolCalls({
        toolCalls: extractedToolCalls,
        assistantText,
        turns,
        messages,
        timelineState,
        selectedClips: resolvedSelectedClips,
        generationContext,
        supabaseAdmin,
        timelineId: session.timeline_id,
        userId: session.user_id,
        userJwt,
        setActiveToolCallId: (toolCallId) => { activeToolCallId = toolCallId; },
        logger,
      });

      if (hasError) {
        continue;
      }
    }

    if (status === "processing") {
      status = "continue";
    }

    await persistSessionState(supabaseAdmin, {
      sessionId: session.id,
      status,
      turns,
      summary,
    });

    logger.info("Agent loop completed", {
      session_id: session.id,
      status,
      turns_added: turns.length - session.turns.length,
    });

    return { status, turns, summary };
  } catch (error: unknown) {
    const errorDetail = toErrorMessage(error);
    console.error(`[agent] FATAL: ${errorDetail}`);
    logger.error("Agent loop failed", {
      session_id: session.id,
      error: errorDetail,
    });

    turns.push(
      activeToolCallId
        ? buildToolErrorTurn(activeToolCallId, error)
        : createTurn("assistant", `[INTERNAL ERROR] ${errorDetail}`),
    );

    try {
      await persistSessionState(supabaseAdmin, {
        sessionId: session.id,
        status: "error",
        turns,
        summary,
      });
    } catch (persistError: unknown) {
      logger.error("Failed to persist error state", {
        session_id: session.id,
        error: toErrorMessage(persistError),
      });
    }

    return { status: "error", turns, summary };
  }
}
