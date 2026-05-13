import { describe, expect, it, vi } from "vitest";
import { RouteContractStampError, stampTaskRouteContract } from "./routeContract.ts";
import type { TaskInsertObject } from "./resolvers/types.ts";

function createMockSupabase(
  rpcImpl: (name: string, args: Record<string, unknown>) => Promise<{ data: unknown; error: { message: string } | null }>,
) {
  const rpc = vi.fn(rpcImpl);
  return { client: { rpc } as unknown as Parameters<typeof stampTaskRouteContract>[0], rpc };
}

function baseTask(overrides: Partial<TaskInsertObject> = {}): TaskInsertObject {
  return {
    project_id: "project-1",
    task_type: "image_upscale",
    params: { foo: "bar" },
    status: "Queued",
    ...overrides,
  };
}

describe("stampTaskRouteContract", () => {
  it("calls derive_route_key RPC with task_type and params and stamps route_key + route_contract", async () => {
    const { client, rpc } = createMockSupabase(async () => ({
      data: "image_upscale",
      error: null,
    }));

    const task = baseTask();
    const stamped = await stampTaskRouteContract(client, task);

    expect(rpc).toHaveBeenCalledTimes(1);
    expect(rpc).toHaveBeenCalledWith("derive_route_key", {
      p_task_type: "image_upscale",
      p_params: { foo: "bar" },
    });
    expect(stamped.route_key).toBe("image_upscale");
    expect(stamped.selector_namespace).toBe("production");
    expect(stamped.selected_backend).toBeNull();
    expect(stamped.selector_version).toBeNull();
    expect(stamped.route_selection_snapshot).toBeNull();
    expect(stamped.support_state).toBeNull();
    expect(stamped.selected_profile).toBeNull();
    expect(stamped.selected_template_id).toBeNull();
    expect(stamped.route_run_id).toBeNull();
    expect(stamped.worker_contract_version).toBeNull();
    expect(stamped.params.foo).toBe("bar");
    const contract = stamped.params.route_contract as Record<string, unknown>;
    expect(contract).toBeDefined();
    expect(contract.route_key).toBe("image_upscale");
    expect(contract.selector_namespace).toBe("production");
    expect(typeof contract.derived_at).toBe("string");
    expect(contract.derived_by).toBe("edge_function");
  });

  it("propagates explicit selector_namespace into route_contract and mirrored column", async () => {
    const { client } = createMockSupabase(async () => ({
      data: "image_upscale",
      error: null,
    }));

    const task = baseTask({ selector_namespace: "staging" });
    const stamped = await stampTaskRouteContract(client, task);

    expect(stamped.selector_namespace).toBe("staging");
    const contract = stamped.params.route_contract as Record<string, unknown>;
    expect(contract.selector_namespace).toBe("staging");
  });

  it("orchestrator-parent task types are exempted and do not populate route_contract", async () => {
    const { client, rpc } = createMockSupabase(async () => ({
      data: "travel_orchestrator",
      error: null,
    }));

    const task = baseTask({ task_type: "travel_orchestrator" });
    const stamped = await stampTaskRouteContract(client, task);

    expect(rpc).toHaveBeenCalledTimes(1);
    expect(stamped.route_key).toBe("travel_orchestrator");
    expect(stamped.params.route_contract).toBeUndefined();
    expect(stamped.selector_namespace).toBeUndefined();
  });

  it("orchestrator-parent task type with NULL derive return leaves task unchanged", async () => {
    const { client } = createMockSupabase(async () => ({
      data: null,
      error: null,
    }));

    const task = baseTask({ task_type: "join_clips_orchestrator" });
    const stamped = await stampTaskRouteContract(client, task);

    expect(stamped.route_key).toBeUndefined();
    expect(stamped.params.route_contract).toBeUndefined();
  });

  it("non-orchestrator task with NULL derive return raises RouteContractStampError", async () => {
    const { client } = createMockSupabase(async () => ({
      data: null,
      error: null,
    }));

    const task = baseTask({ task_type: "unknown_task" });
    await expect(stampTaskRouteContract(client, task)).rejects.toBeInstanceOf(
      RouteContractStampError,
    );
    await expect(stampTaskRouteContract(client, task)).rejects.toMatchObject({
      taskType: "unknown_task",
      cause: "derive_returned_null",
    });
  });

  it("RPC error surfaces as a thrown Error", async () => {
    const { client } = createMockSupabase(async () => ({
      data: null,
      error: { message: "function does not exist" },
    }));

    const task = baseTask();
    await expect(stampTaskRouteContract(client, task)).rejects.toThrow(
      /derive_route_key RPC failed/,
    );
  });

  it("preserves params untouched apart from injecting route_contract", async () => {
    const { client } = createMockSupabase(async () => ({
      data: "image_upscale",
      error: null,
    }));

    const task = baseTask({
      params: { foo: "bar", nested: { a: 1 }, model_name: "wan_2_2_i2v" },
    });
    const stamped = await stampTaskRouteContract(client, task);

    expect(stamped.params.foo).toBe("bar");
    expect(stamped.params.nested).toEqual({ a: 1 });
    expect(stamped.params.model_name).toBe("wan_2_2_i2v");
    expect(stamped.params.route_contract).toBeDefined();
  });

  it("RPC return with extra whitespace is trimmed", async () => {
    const { client } = createMockSupabase(async () => ({
      data: "  image_upscale  ",
      error: null,
    }));

    const stamped = await stampTaskRouteContract(client, baseTask());
    expect(stamped.route_key).toBe("image_upscale");
  });

  it("RPC return as empty/whitespace-only string is treated as NULL", async () => {
    const { client } = createMockSupabase(async () => ({
      data: "   ",
      error: null,
    }));

    await expect(stampTaskRouteContract(client, baseTask())).rejects.toBeInstanceOf(
      RouteContractStampError,
    );
  });
});
