import type { UpdateTaskStatusRequest } from './types.ts';

export function buildTaskUpdatePayload(request: UpdateTaskStatusRequest): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    status: request.status,
    updated_at: new Date().toISOString(),
  };

  if (request.status === 'In Progress') {
    payload.generation_started_at = new Date().toISOString();
  }

  if (request.reset_generation_started_at === true) {
    payload.generation_started_at = new Date().toISOString();
  }

  if (request.status === 'Complete') {
    payload.generation_processed_at = new Date().toISOString();
  }

  if (request.output_location !== undefined) {
    payload.output_location = request.output_location;
  }

  if (request.attempts !== undefined) {
    payload.attempts = request.attempts;
  }

  if (request.error_details !== undefined) {
    payload.error_message = request.error_details;
  }

  if (request.clear_worker === true) {
    payload.worker_id = null;
    payload.generation_started_at = null;
  }

  // Worker-supplied result envelope. We only write the column when the
  // request includes it explicitly, so the existing "leave it alone"
  // behaviour for callers that don't know about result_data is preserved.
  // Bug 2 (cross-repo contract): the new `task-status` GET reader projects
  // the well-known fields out of this column.
  if (request.result_data !== undefined) {
    payload.result_data = request.result_data;
  }

  return payload;
}
