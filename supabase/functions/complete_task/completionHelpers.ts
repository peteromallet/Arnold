import { toErrorMessage } from "../_shared/errorMessage.ts";
import type { SupabaseClient } from 'https://esm.sh/@supabase/supabase-js@2.49.4';
import { edgeErrorResponse } from "../_shared/edgeRequest.ts";
import type { CompletionLogger } from './types.ts';

export type MaterializedInputKind = 'file' | 'remote';

export interface MaterializedInputRecord {
  generation_id: string;
  kind: MaterializedInputKind;
  target: string;
}

export interface TaskContext {
  id: string;
  task_type: string;
  project_id: string;
  params: Record<string, unknown>;
  result_data: unknown;
  tool_type: string;
  category: string;
  content_type: 'image' | 'video';
  variant_type: string | null;
  materialized_inputs?: MaterializedInputRecord[] | null;
}

export type CompletionFollowUpStep =
  | 'validation'
  | 'timeline_placement'
  | 'orchestrator_completion'
  | 'cost_calculation'
  | 'follow_up_persistence'
  | 'materialized_input_cleanup';

export interface CompletionFollowUpIssue {
  step: CompletionFollowUpStep;
  code: string;
  message: string;
}

function defaultErrorCode(status: number): string {
  if (status === 401) return 'authentication_failed';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 405) return 'method_not_allowed';
  if (status === 429) return 'rate_limited';
  if (status === 503) return 'service_unavailable';
  if (status >= 500) return 'internal_server_error';
  return 'request_failed';
}

export function completeTaskErrorResponse(
  message: string,
  status: number,
  errorCode = defaultErrorCode(status),
  options?: { recoverable?: boolean },
): Response {
  return edgeErrorResponse(
    {
      errorCode,
      message,
      recoverable: options?.recoverable ?? (status >= 500 || status === 429),
    },
    status,
  );
}

function asObjectRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

/**
 * Best-effort mark a task as Failed so the UI can update immediately.
 * Swallows errors — callers still return their own HTTP error response.
 */
export async function markTaskFailed(
  supabase: SupabaseClient,
  taskId: string,
  errorMessage: string,
): Promise<void> {
  try {
    await supabase.from("tasks").update({
      status: "Failed",
      error_message: errorMessage,
      updated_at: new Date().toISOString(),
    }).eq("id", taskId).in("status", ["Queued", "In Progress"]);
  } catch {
    // Best-effort — don't mask the original error
  }
}

export async function persistCompletionFollowUpIssues(
  supabase: SupabaseClient,
  taskId: string,
  existingResultData: unknown,
  issues: CompletionFollowUpIssue[],
): Promise<{ ok: true } | { ok: false; error: unknown }> {
  if (issues.length === 0) {
    return { ok: true };
  }

  const baseResultData = asObjectRecord(existingResultData);
  const completionFollowUp = {
    status: 'degraded',
    recorded_at: new Date().toISOString(),
    issues,
  };

  const { error } = await supabase
    .from('tasks')
    .update({
      result_data: {
        ...baseResultData,
        completion_follow_up: completionFollowUp,
      },
    })
    .eq('id', taskId);

  if (error) {
    return { ok: false, error };
  }

  return { ok: true };
}

/**
 * Fetch task context with all required fields for the completion flow.
 * Uses a single query with FK join (tasks.task_type -> task_types.name).
 * Returns null if task not found or on error.
 */
export async function fetchTaskContext(
  supabase: SupabaseClient,
  taskId: string,
  logger?: CompletionLogger,
): Promise<TaskContext | null> {
  const { data: task, error } = await supabase
    .from("tasks")
    .select(`id, task_type, project_id, params, result_data, materialized_inputs, task_types!tasks_task_type_fkey(tool_type, category, content_type, variant_type)`)
    .eq("id", taskId)
    .single();

  if (error || !task) {
    logger?.error('Failed to fetch task context', {
      task_id: taskId,
      fetch_error: toErrorMessage(error),
    });
    return null;
  }

  const taskTypeInfo = task.task_types || {};

  return {
    id: task.id,
    task_type: task.task_type,
    project_id: task.project_id,
    params: task.params || {},
    result_data: task.result_data,
    tool_type: taskTypeInfo.tool_type || 'unknown',
    category: taskTypeInfo.category || 'unknown',
    content_type: taskTypeInfo.content_type || 'image',
    variant_type: taskTypeInfo.variant_type || null,
    materialized_inputs: Array.isArray(task.materialized_inputs)
      ? (task.materialized_inputs as MaterializedInputRecord[])
      : null,
  };
}
