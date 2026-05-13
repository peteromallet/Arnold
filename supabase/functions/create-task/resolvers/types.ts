import type { SupabaseClient } from "../../_shared/supabaseClient.ts";
import type { SystemLogger } from "../../_shared/systemLogger.ts";

export type TaskStatus = "Queued" | "In Progress" | "Complete" | "Failed" | "Cancelled";

export type MaterializedInputKind = "file" | "remote";

export interface MaterializedInputRecord {
  generation_id: string;
  kind: MaterializedInputKind;
  target: string;
}

export interface TaskInsertObject {
  attempts?: number;
  copied_from_share?: string | null;
  created_at?: string;
  dependant_on?: string[] | null;
  error_message?: string | null;
  generation_created?: boolean;
  generation_processed_at?: string | null;
  generation_started_at?: string | null;
  id?: string;
  idempotency_key?: string | null;
  materialized_inputs?: MaterializedInputRecord[] | null;
  output_location?: string | null;
  params: Record<string, unknown>;
  project_id: string;
  result_data?: Record<string, unknown> | null;
  status?: TaskStatus;
  task_type: string;
  updated_at?: string | null;
  worker_id?: string | null;
  route_key?: string | null;
  selector_namespace?: string | null;
  selected_backend?: string | null;
  selector_version?: string | null;
  route_selection_snapshot?: Record<string, unknown> | null;
  support_state?: string | null;
  selected_profile?: string | null;
  selected_template_id?: string | null;
  route_run_id?: string | null;
  worker_contract_version?: string | null;
}

export interface ResolveRequest {
  family: string;
  project_id: string;
  input: Record<string, unknown>;
}

export interface ResolverContext {
  supabaseAdmin: SupabaseClient;
  projectId: string;
  aspectRatio: string | null;
  logger: SystemLogger;
}

export interface ResolverResult {
  tasks: TaskInsertObject[];
  meta?: Record<string, unknown>;
}

export type TaskFamilyResolver = (
  request: ResolveRequest,
  context: ResolverContext,
) => Promise<ResolverResult> | ResolverResult;
