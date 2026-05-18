import type { SupabaseClient } from "../_shared/supabaseClient.ts";
import {
  DEFAULT_SELECTOR_NAMESPACE,
  deriveRouteKey,
  isOrchestratedParentTaskType,
  type RouteContractJSON,
} from "../_shared/selectedRoute.ts";
import type { TaskInsertObject } from "./resolvers/types.ts";

const DERIVE_ROUTE_KEY_VERSION = 1;

export class RouteContractStampError extends Error {
  readonly taskType: string;
  readonly cause: "derive_returned_null" | "rpc_failure";

  constructor(message: string, taskType: string, cause: "derive_returned_null" | "rpc_failure") {
    super(message);
    this.name = "RouteContractStampError";
    this.taskType = taskType;
    this.cause = cause;
  }
}

function asParamsRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function firstString(...candidates: unknown[]): string | null {
  for (const c of candidates) {
    if (typeof c === "string" && c.length > 0) return c;
  }
  return null;
}

function firstRecord(...candidates: unknown[]): Record<string, unknown> | null {
  for (const c of candidates) {
    if (c && typeof c === "object" && !Array.isArray(c)) return c as Record<string, unknown>;
  }
  return null;
}

function buildRouteContractJSON(
  routeKey: string,
  selectorNamespace: string,
  existing: Record<string, unknown> | undefined,
  topLevel: TaskInsertObject,
  params: Record<string, unknown>,
): RouteContractJSON {
  // Workers pass route fields as `route_snapshot_fields` flattened into the
  // create-task input. The workerPassthrough resolver dumps the entire input
  // into params (so they end up at task.params.selected_backend), while
  // frontend resolvers tend to lift them to top-level TaskInsertObject
  // columns. Look in all three places, preferring top-level, then
  // params.*, then params.route_contract.* (legacy), then null.
  return {
    route_key: routeKey,
    selector_namespace: selectorNamespace,
    selected_backend: firstString(
      topLevel.selected_backend,
      params.selected_backend,
      existing?.selected_backend,
    ),
    selector_version: firstString(
      topLevel.selector_version,
      params.selector_version,
      existing?.selector_version,
    ),
    route_selection_snapshot: firstRecord(
      topLevel.route_selection_snapshot,
      params.route_selection_snapshot,
      existing?.route_selection_snapshot,
    ),
    support_state: firstString(
      topLevel.support_state,
      params.support_state,
      existing?.support_state,
    ),
    selected_profile: firstString(
      topLevel.selected_profile,
      params.selected_profile,
      existing?.selected_profile,
    ),
    selected_template_id: firstString(
      topLevel.selected_template_id,
      params.selected_template_id,
      existing?.selected_template_id,
    ),
    route_run_id: firstString(
      topLevel.route_run_id,
      params.route_run_id,
      existing?.route_run_id,
    ),
    worker_contract_version: firstString(
      topLevel.worker_contract_version,
      params.worker_contract_version,
      existing?.worker_contract_version,
    ),
    derived_at: new Date().toISOString(),
    derived_by: "edge_function",
    derive_route_key_version: DERIVE_ROUTE_KEY_VERSION,
  };
}

export async function stampTaskRouteContract(
  supabase: SupabaseClient,
  task: TaskInsertObject,
): Promise<TaskInsertObject> {
  const params = asParamsRecord(task.params);

  // Orchestrator-parent tasks are exempt from the Layer 1 trigger
  // (BEFORE INSERT WHEN status='Queued' AND task_type NOT LIKE '%_orchestrator').
  // We still stamp route_key when derive returns one, but do not require
  // route_contract presence or claim eligibility.
  if (isOrchestratedParentTaskType(task.task_type)) {
    const orchestratorRouteKey = await deriveRouteKey(supabase, task.task_type, params);
    if (orchestratorRouteKey === null) {
      return task;
    }
    return { ...task, route_key: orchestratorRouteKey };
  }

  const routeKey = await deriveRouteKey(supabase, task.task_type, params);
  if (routeKey === null) {
    throw new RouteContractStampError(
      `derive_route_key returned NULL for task_type=${task.task_type} — task would fail the tasks_assert_claimable trigger`,
      task.task_type,
      "derive_returned_null",
    );
  }

  const selectorNamespace =
    typeof task.selector_namespace === "string" && task.selector_namespace.length > 0
      ? task.selector_namespace
      : DEFAULT_SELECTOR_NAMESPACE;

  const existingContract = params.route_contract && typeof params.route_contract === "object"
    ? (params.route_contract as Record<string, unknown>)
    : undefined;

  const contract = buildRouteContractJSON(routeKey, selectorNamespace, existingContract, task, params);

  return {
    ...task,
    route_key: routeKey,
    selector_namespace: selectorNamespace,
    selected_backend: contract.selected_backend,
    selector_version: contract.selector_version,
    route_selection_snapshot: contract.route_selection_snapshot,
    support_state: contract.support_state,
    selected_profile: contract.selected_profile,
    selected_template_id: contract.selected_template_id,
    route_run_id: contract.route_run_id,
    worker_contract_version: contract.worker_contract_version,
    params: {
      ...params,
      route_contract: contract,
    },
  };
}
