// deno-lint-ignore-file
import { describe, expect, it, vi } from "vitest";
import { handleTaskStatus } from "./handler.ts";

const TASK_ID = "44444444-4444-4444-4444-444444444444";

interface FakeTaskRow {
  id: string;
  status: string;
  result_data: Record<string, unknown> | null;
}

function createSupabaseAdminMock(options: {
  task?: FakeTaskRow | null;
  error?: { message: string } | null;
}) {
  const maybeSingle = vi.fn().mockResolvedValue({
    data: options.task ?? null,
    error: options.error ?? null,
  });
  const eq = vi.fn().mockReturnValue({ maybeSingle });
  const select = vi.fn().mockReturnValue({ eq });
  const from = vi.fn().mockReturnValue({ select });
  return {
    supabaseAdmin: { from } as unknown as Parameters<typeof handleTaskStatus>[0]["supabaseAdmin"],
    mocks: { from, select, eq, maybeSingle },
  };
}

const baseLogger = {
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

describe("handleTaskStatus", () => {
  it("rejects malformed task_id", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const result = await handleTaskStatus({
      taskId: "not-a-uuid",
      supabaseAdmin,
      logger: baseLogger,
    });
    expect(result.status).toBe(400);
    expect((result.body as { error: string }).error).toMatch(/uuid/);
  });

  it("returns 404 when task is not found", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({ task: null });
    const result = await handleTaskStatus({
      taskId: TASK_ID,
      supabaseAdmin,
      logger: baseLogger,
    });
    expect(result.status).toBe(404);
  });

  it("returns 500 on lookup error", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({ error: { message: "boom" } });
    const result = await handleTaskStatus({
      taskId: TASK_ID,
      supabaseAdmin,
      logger: baseLogger,
    });
    expect(result.status).toBe(500);
  });

  it("returns plain status when result_data is empty", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      task: { id: TASK_ID, status: "Queued", result_data: null },
    });
    const result = await handleTaskStatus({
      taskId: TASK_ID,
      supabaseAdmin,
      logger: baseLogger,
    });
    expect(result.status).toBe(200);
    const body = result.body as Record<string, unknown>;
    expect(body.status).toBe("Queued");
    expect(body.result).toBeUndefined();
    expect(body.correlation_id).toBeUndefined();
  });

  it("hoists top-level fields and exposes config_version under result", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      task: {
        id: TASK_ID,
        status: "Complete",
        result_data: {
          correlation_id: "corr-123",
          message: "done",
          config_version: 7,
          timeline_id: "55555555-5555-5555-5555-555555555555",
          extra_field: "passthrough",
        },
      },
    });
    const result = await handleTaskStatus({
      taskId: TASK_ID,
      supabaseAdmin,
      logger: baseLogger,
    });
    expect(result.status).toBe(200);
    const body = result.body as Record<string, unknown>;
    expect(body.status).toBe("Complete");
    expect(body.correlation_id).toBe("corr-123");
    expect(body.message).toBe("done");
    expect(body.failure_code).toBeUndefined();
    const envelope = body.result as Record<string, unknown>;
    expect(envelope.config_version).toBe(7);
    expect(envelope.timeline_id).toBe("55555555-5555-5555-5555-555555555555");
    expect(envelope.extra_field).toBe("passthrough");
    expect(envelope.correlation_id).toBeUndefined();
  });

  it("surfaces failure_code on Failed tasks", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      task: {
        id: TASK_ID,
        status: "Failed",
        result_data: {
          failure_code: "version_conflict",
          message: "version mismatch",
          correlation_id: "corr-fail",
        },
      },
    });
    const result = await handleTaskStatus({
      taskId: TASK_ID,
      supabaseAdmin,
      logger: baseLogger,
    });
    expect(result.status).toBe(200);
    const body = result.body as Record<string, unknown>;
    expect(body.status).toBe("Failed");
    expect(body.failure_code).toBe("version_conflict");
    expect(body.message).toBe("version mismatch");
    expect(body.correlation_id).toBe("corr-fail");
    // No leftover passthrough fields → no `result` key.
    expect(body.result).toBeUndefined();
  });
});
