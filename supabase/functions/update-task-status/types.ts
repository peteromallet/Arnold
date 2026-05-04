export const VALID_TASK_STATUSES = ['Queued', 'In Progress', 'Complete', 'Failed', 'Cancelled'] as const;

export type TaskStatus = typeof VALID_TASK_STATUSES[number];

export interface UpdateTaskStatusRequest {
  task_id: string;
  status: TaskStatus;
  output_location?: string;
  attempts?: number;
  error_details?: string;
  clear_worker?: boolean;
  reset_generation_started_at?: boolean;
  /**
   * Optional worker-supplied envelope persisted to `tasks.result_data`. The
   * banodoco worker uses this to surface `correlation_id`, `config_version`,
   * `failure_code`, etc.; the new `task-status` GET reader projects these
   * values into the poller-facing response (see Bug 2 in the cross-repo
   * contract notes). When omitted, `result_data` is left untouched.
   */
  result_data?: Record<string, unknown>;
}

export interface TaskStatusRow {
  id: string;
  status: TaskStatus;
  params?: unknown;
  generation_started_at?: string | null;
  generation_processed_at?: string | null;
}
