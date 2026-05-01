// Sprint 7 (SD-020 + SD-022 + SD-034 + SD-035): delegateToBanodocoAgent tool.
//
// Single new tool that delegates BULK generative authoring to a `banodoco`
// pinned-Railway worker via the orchestrator. Surgical edits stay
// synchronous on this side; this tool is for "regenerate the section",
// "extend the hype reel by 15s", "produce a fresh 2rp version" sized
// requests.
//
// Behavior (do NOT relitigate):
//
//   1. Read the current timeline state's `expected_version` (SD-013 +
//      SD-034 idempotency).
//   2. Generate a fresh `correlation_id` (UUIDv4). The agent owns this id;
//      the worker writes it into the timeline-version metadata so a retry
//      that races a predecessor's write recognises its own work.
//   3. POST the task payload to the orchestrator's task-enqueue endpoint
//      with `Authorization: Bearer <user_jwt>`. The orchestrator routes
//      the task to the `banodoco` worker pool.
//   4. Return immediately to the LLM with a "queued" message. NO
//      synchronous wait; NO config-application here. The editor's
//      existing realtime subscription on the `timelines` table picks up
//      the worker's write.
//
// Status surfacing — the agent loop polls task status on subsequent turns
// (see `pollBanodocoTaskStatus`).

import type {
  TimelineState,
  ToolResult,
} from "../types.ts";
import { asTrimmedString, isRecord } from "../utils.ts";

declare const Deno: { env: { get: (key: string) => string | undefined } };

export type DelegateScope = "full" | "insert" | "replace_range";

export interface DelegateToBanodocoAgentArgs {
  intent: string;
  brief_inputs?: Record<string, unknown>;
  theme_id?: string;
  scope?: DelegateScope;
  current_timeline_snapshot?: boolean;
}

export interface BanodocoTaskPayload {
  intent: string;
  brief_inputs: Record<string, unknown>;
  theme_id: string;
  expected_version: number;
  scope: DelegateScope;
  user_jwt: string;
  project_id: string;
  timeline_id: string;
  correlation_id: string;
  current_timeline?: unknown;
}

export interface BuildPayloadInput {
  args: Record<string, unknown>;
  timelineState: TimelineState;
  timelineId: string;
  userJwt: string;
  // Caller may inject a UUID for deterministic tests.
  correlationId?: string;
}

export interface BuildPayloadResult {
  payload?: BanodocoTaskPayload;
  error?: string;
}

const VALID_SCOPES: ReadonlySet<DelegateScope> = new Set(["full", "insert", "replace_range"]);

function defaultThemeId(state: TimelineState): string {
  const theme = (state.config as unknown as { theme?: unknown }).theme;
  return typeof theme === "string" && theme.trim() ? theme : "2rp";
}

export function buildDelegatePayload(input: BuildPayloadInput): BuildPayloadResult {
  const intent = asTrimmedString((input.args as { intent?: unknown }).intent);
  if (!intent) {
    return { error: "delegateToBanodocoAgent requires intent." };
  }
  if (!input.userJwt) {
    return { error: "delegateToBanodocoAgent requires the caller's JWT (SD-022)." };
  }

  const rawScope = (input.args as { scope?: unknown }).scope;
  const scope = (typeof rawScope === "string" && VALID_SCOPES.has(rawScope as DelegateScope))
    ? (rawScope as DelegateScope)
    : "full";

  const briefInputsRaw = (input.args as { brief_inputs?: unknown }).brief_inputs;
  const briefInputs = isRecord(briefInputsRaw) ? briefInputsRaw : {};

  const themeId = asTrimmedString((input.args as { theme_id?: unknown }).theme_id)
    || defaultThemeId(input.timelineState);

  const includeSnapshot = (input.args as { current_timeline_snapshot?: unknown }).current_timeline_snapshot !== false;

  const correlationId = input.correlationId ?? crypto.randomUUID();

  const payload: BanodocoTaskPayload = {
    intent,
    brief_inputs: briefInputs,
    theme_id: themeId,
    expected_version: input.timelineState.configVersion,
    scope,
    user_jwt: input.userJwt,
    project_id: input.timelineState.projectId,
    timeline_id: input.timelineId,
    correlation_id: correlationId,
  };
  if (includeSnapshot) {
    payload.current_timeline = input.timelineState.config;
  }
  return { payload };
}

export interface EnqueueResult {
  status: "queued" | "error";
  task_id?: string;
  correlation_id?: string;
  message: string;
}

interface OrchestratorEnqueueResponse {
  task_id?: string;
}

export async function enqueueBanodocoTask(
  payload: BanodocoTaskPayload,
  options: { fetchImpl?: typeof fetch } = {},
): Promise<EnqueueResult> {
  const orchestratorUrl = Deno.env.get("ORCHESTRATOR_TASK_ENQUEUE_URL")
    ?? Deno.env.get("ORCHESTRATOR_BASE_URL");
  if (!orchestratorUrl) {
    return {
      status: "error",
      message: "ORCHESTRATOR_TASK_ENQUEUE_URL is not configured for delegateToBanodocoAgent.",
    };
  }

  const enqueueUrl = orchestratorUrl.endsWith("/")
    ? `${orchestratorUrl.slice(0, -1)}/functions/v1/enqueue-task`
    : orchestratorUrl.includes("/functions/v1/")
      ? orchestratorUrl
      : `${orchestratorUrl}/functions/v1/enqueue-task`;

  const fetchImpl = options.fetchImpl ?? fetch;

  // The orchestrator validates the SD-034 envelope on its side; the agent
  // sends a `task_type` + `params` body matching the existing enqueue
  // contract (see api_orchestrator/handlers/banodoco.py).
  const body = {
    task_type: "banodoco_timeline_generate",
    params: payload,
    project_id: payload.project_id,
    run_type: "banodoco-worker",
    worker_pool: "banodoco",
  };

  let resp: Response;
  try {
    resp = await fetchImpl(enqueueUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // SD-022 round-trip: the user's JWT travels with the enqueue so
        // the orchestrator (and downstream worker) can re-verify identity.
        "Authorization": `Bearer ${payload.user_jwt}`,
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    return {
      status: "error",
      message: `Failed to reach orchestrator: ${err instanceof Error ? err.message : String(err)}`,
    };
  }

  if (resp.status >= 400) {
    let errBody = "";
    try {
      errBody = (await resp.text()).slice(0, 500);
    } catch {
      // ignore
    }
    return {
      status: "error",
      message: `Orchestrator rejected enqueue (HTTP ${resp.status}): ${errBody}`,
    };
  }

  let parsed: OrchestratorEnqueueResponse | null = null;
  try {
    parsed = await resp.json();
  } catch {
    // Some endpoints reply with a 2xx and no body — that's fine.
  }

  return {
    status: "queued",
    task_id: parsed?.task_id,
    correlation_id: payload.correlation_id,
    message:
      "Queued — generative work will appear in ~30s. Stay on this timeline; the editor will refresh when it's ready.",
  };
}

export async function executeDelegateToBanodocoAgent(
  args: Record<string, unknown>,
  timelineState: TimelineState,
  timelineId: string,
  userJwt: string | undefined,
  options: { fetchImpl?: typeof fetch; correlationId?: string } = {},
): Promise<ToolResult> {
  const { payload, error } = buildDelegatePayload({
    args,
    timelineState,
    timelineId,
    userJwt: userJwt ?? "",
    correlationId: options.correlationId,
  });
  if (error || !payload) {
    return { result: error ?? "delegateToBanodocoAgent failed to build a payload." };
  }

  const enqueue = await enqueueBanodocoTask(payload, { fetchImpl: options.fetchImpl });
  if (enqueue.status === "error") {
    return { result: enqueue.message };
  }

  // Surface the correlation_id + task_id so the LLM can include them in a
  // follow-up status check, and so the agent loop's status-poll helper
  // can find them in the most recent tool_result content.
  const decoration = enqueue.task_id
    ? ` task_id=${enqueue.task_id} correlation_id=${enqueue.correlation_id}`
    : ` correlation_id=${enqueue.correlation_id}`;

  return {
    result: `${enqueue.message}${decoration}`,
  };
}

// ---------------------------------------------------------------------------
// Status polling helper (called from the agent loop on each turn while a
// banodoco task is in flight). Pure data shape; the loop wraps it.
// ---------------------------------------------------------------------------

export interface BanodocoTaskStatusSnapshot {
  task_id: string;
  status: "Queued" | "In Progress" | "Complete" | "Failed" | "worker_unavailable" | "unknown";
  failure_code?: string;
  message?: string;
  config_version?: number;
  correlation_id?: string;
}

export async function pollBanodocoTaskStatus(
  taskId: string,
  userJwt: string,
  options: { fetchImpl?: typeof fetch } = {},
): Promise<BanodocoTaskStatusSnapshot> {
  const orchestratorUrl = Deno.env.get("ORCHESTRATOR_TASK_STATUS_URL")
    ?? Deno.env.get("ORCHESTRATOR_BASE_URL");
  if (!orchestratorUrl) {
    return { task_id: taskId, status: "unknown", message: "ORCHESTRATOR_BASE_URL not set" };
  }

  const statusUrl = orchestratorUrl.includes("/tasks/")
    ? orchestratorUrl
    : `${orchestratorUrl.replace(/\/$/, "")}/functions/v1/task-status?task_id=${encodeURIComponent(taskId)}`;

  const fetchImpl = options.fetchImpl ?? fetch;
  let resp: Response;
  try {
    resp = await fetchImpl(statusUrl, {
      headers: { "Authorization": `Bearer ${userJwt}` },
    });
  } catch (err) {
    return {
      task_id: taskId,
      status: "unknown",
      message: `status fetch failed: ${err instanceof Error ? err.message : String(err)}`,
    };
  }

  if (resp.status >= 400) {
    return { task_id: taskId, status: "unknown", message: `HTTP ${resp.status}` };
  }

  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    return { task_id: taskId, status: "unknown", message: "non-JSON response" };
  }

  if (!isRecord(body)) {
    return { task_id: taskId, status: "unknown" };
  }

  const status = typeof body.status === "string" ? body.status : "unknown";
  const failure_code = typeof body.failure_code === "string" ? body.failure_code : undefined;
  const message = typeof body.message === "string" ? body.message : undefined;
  const correlation_id = typeof body.correlation_id === "string" ? body.correlation_id : undefined;
  const config_version = typeof (body as { result?: unknown }).result === "object"
    && isRecord((body as { result?: unknown }).result)
    && typeof (body as { result: { config_version?: unknown } }).result.config_version === "number"
    ? (body as { result: { config_version: number } }).result.config_version
    : undefined;

  // Normalise the status enum to the BanodocoTaskStatusSnapshot variant set.
  const normalisedStatus: BanodocoTaskStatusSnapshot["status"] =
    status === "Queued" || status === "In Progress" || status === "Complete"
      || status === "Failed"
      ? status
      : (failure_code === "worker_unavailable" ? "worker_unavailable" : "unknown");

  return {
    task_id: taskId,
    status: normalisedStatus,
    failure_code,
    message,
    correlation_id,
    config_version,
  };
}

export function summariseTaskStatusForChat(snap: BanodocoTaskStatusSnapshot): string {
  switch (snap.status) {
    case "Queued":
      return "Banodoco task is still queued — no worker has claimed it yet.";
    case "In Progress":
      return "Banodoco worker is generating now.";
    case "Complete":
      return snap.config_version
        ? `Banodoco wrote v${snap.config_version} — the editor's realtime subscription will refresh shortly.`
        : "Banodoco wrote the new timeline — the editor will refresh shortly.";
    case "Failed":
      if (snap.failure_code === "version_conflict") {
        return "Your edits superseded the AI's mid-generation. Retry the request to regenerate against the new state.";
      }
      if (snap.failure_code === "auth_failed") {
        return "Banodoco rejected the request: authentication failed. Sign in again and retry.";
      }
      return `Banodoco task failed${snap.message ? `: ${snap.message}` : "."}`;
    case "worker_unavailable":
      return "No Banodoco worker is available right now — try again in a minute.";
    default:
      return snap.message ?? "Banodoco task status unknown.";
  }
}

// Convenience for the loop: derives the most recent (task_id, correlation_id)
// pair the LLM emitted via this tool, by scanning the trailing tool_result
// turns.
export function findLatestPendingDelegate(
  turns: ReadonlyArray<{ role: string; tool_name?: string; content: string }>,
): { task_id: string; correlation_id: string } | null {
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    const turn = turns[i];
    if (turn.role !== "tool_result" || turn.tool_name !== "delegateToBanodocoAgent") {
      continue;
    }
    const taskMatch = turn.content.match(/task_id=([\w-]{4,})/i);
    const corrMatch = turn.content.match(/correlation_id=([\w-]{4,})/i);
    if (taskMatch && corrMatch) {
      return { task_id: taskMatch[1], correlation_id: corrMatch[1] };
    }
  }
  return null;
}
