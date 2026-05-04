// deno-lint-ignore-file
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";
import type { TaskStatusResponseBody, TaskStatusResultEnvelope } from "./types.ts";

interface Logger {
  info(message: string, context?: Record<string, unknown>): void;
  warn(message: string, context?: Record<string, unknown>): void;
  error(message: string, context?: Record<string, unknown>): void;
}

export interface HandleTaskStatusInput {
  taskId: string;
  supabaseAdmin: SupabaseClient;
  logger: Logger;
}

export interface HandleTaskStatusResult {
  status: number;
  body: TaskStatusResponseBody | { error: string };
}

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Reads a task's status row and projects the response envelope expected by
 * the banodoco poller. The `result_data` JSON column holds the worker-supplied
 * envelope (see Bug 2 in the cross-repo contract notes); this handler hoists
 * the well-known fields (correlation_id, message, failure_code) into the
 * top-level response and passes the remaining fields through under `result`.
 *
 * Authentication and ownership are handled by the caller (see ./index.ts):
 * we mirror `timeline-import` and assume `verifyOwnership` has already passed.
 */
export async function handleTaskStatus(
  input: HandleTaskStatusInput,
): Promise<HandleTaskStatusResult> {
  const { taskId, supabaseAdmin, logger } = input;

  if (!isUuid(taskId)) {
    return { status: 400, body: { error: "task_id must be a uuid" } };
  }

  const { data: task, error } = await supabaseAdmin
    .from("tasks")
    .select("id, status, result_data")
    .eq("id", taskId)
    .maybeSingle();

  if (error) {
    logger.error("task lookup failed", { error: error.message });
    return { status: 500, body: { error: "failed to load task" } };
  }
  if (!task) {
    return { status: 404, body: { error: "Task not found" } };
  }

  const resultData = isRecord(task.result_data) ? task.result_data : {};

  const correlation_id =
    typeof resultData.correlation_id === "string" ? resultData.correlation_id : undefined;
  const message = typeof resultData.message === "string" ? resultData.message : undefined;
  const failure_code =
    typeof resultData.failure_code === "string" ? resultData.failure_code : undefined;

  // Everything in result_data that is *not* a top-level surfaced field
  // becomes the `result` envelope. We keep keys workers care about
  // (config_version, timeline_id) and forward unknown keys verbatim so
  // the worker contract stays open-ended.
  const RESERVED_TOP_LEVEL = new Set(["correlation_id", "message", "failure_code"]);
  const result: TaskStatusResultEnvelope = {};
  for (const [key, value] of Object.entries(resultData)) {
    if (RESERVED_TOP_LEVEL.has(key)) continue;
    result[key] = value;
  }

  const body: TaskStatusResponseBody = {
    status: typeof task.status === "string" ? task.status : "unknown",
  };
  if (correlation_id !== undefined) body.correlation_id = correlation_id;
  if (message !== undefined) body.message = message;
  if (failure_code !== undefined) body.failure_code = failure_code;
  if (Object.keys(result).length > 0) body.result = result;

  logger.info("Returning task status", {
    task_id: taskId,
    status: body.status,
    has_result: body.result !== undefined,
  });

  return { status: 200, body };
}
