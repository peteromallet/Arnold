import type { SupabaseClient } from "./supabaseClient.ts";

export const DEFAULT_SELECTOR_NAMESPACE = "production";

export interface RouteContractJSON {
  route_key: string;
  selector_namespace: string;
  selected_backend: string | null;
  selector_version: string | null;
  route_selection_snapshot: Record<string, unknown> | null;
  support_state: string | null;
  selected_profile: string | null;
  selected_template_id: string | null;
  route_run_id: string | null;
  worker_contract_version: string | null;
  derived_at: string;
  derived_by: "edge_function" | "worker" | "live_test";
  derive_route_key_version: number;
}

export function isOrchestratedParentTaskType(taskType: string): boolean {
  return taskType.endsWith("_orchestrator");
}

export async function deriveRouteKey(
  supabase: SupabaseClient,
  taskType: string,
  params: Record<string, unknown>,
): Promise<string | null> {
  const { data, error } = await supabase.rpc("derive_route_key", {
    p_task_type: taskType,
    p_params: params,
  });

  if (error) {
    throw new Error(
      `derive_route_key RPC failed for task_type=${taskType}: ${error.message}`,
    );
  }

  if (data === null || data === undefined) {
    return null;
  }
  if (typeof data !== "string") {
    throw new Error(
      `derive_route_key RPC returned non-string data for task_type=${taskType}: ${typeof data}`,
    );
  }
  const trimmed = data.trim();
  return trimmed.length > 0 ? trimmed : null;
}
