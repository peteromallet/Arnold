import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildDelegatePayload,
  enqueueBanodocoTask,
  executeDelegateToBanodocoAgent,
  findLatestPendingDelegate,
  pollBanodocoTaskStatus,
  summariseTaskStatusForChat,
} from "./delegateToBanodocoAgent.ts";
import type { TimelineState } from "../types.ts";

const FIXED_CORR_ID = "11111111-1111-1111-1111-111111111111";

function makeTimelineState(overrides: Partial<TimelineState> = {}): TimelineState {
  return {
    config: {
      clips: [{ id: "c1", at: 0, from: 0, to: 5, track: "V1", clipType: "media", asset: "a1" }],
      tracks: [{ id: "V1", kind: "visual" }],
      theme: "2rp",
    } as unknown as TimelineState["config"],
    configVersion: 7,
    registry: { assets: { a1: { duration: 5 } } } as unknown as TimelineState["registry"],
    projectId: "44444444-4444-4444-4444-444444444444",
    shotNamesById: {},
    ...overrides,
  };
}

describe("delegateToBanodocoAgent — buildDelegatePayload", () => {
  it("returns an error when intent is missing", () => {
    const result = buildDelegatePayload({
      args: {},
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(result.error).toMatch(/intent/);
    expect(result.payload).toBeUndefined();
  });

  it("returns an error when the user JWT is missing (SD-022)", () => {
    const result = buildDelegatePayload({
      args: { intent: "extend by 15s" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "",
      correlationId: FIXED_CORR_ID,
    });
    expect(result.error).toMatch(/JWT/);
  });

  it("captures expected_version from timelineState.configVersion (SD-013 + SD-034)", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "extend by 15s" },
      timelineState: makeTimelineState({ configVersion: 12 }),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.expected_version).toBe(12);
  });

  it("uses the timeline's current theme when theme_id is omitted", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "anything" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.theme_id).toBe("2rp");
  });

  it("falls back to '2rp' when no theme is set on the timeline", () => {
    const state = makeTimelineState();
    (state.config as unknown as { theme?: string }).theme = undefined;
    const { payload } = buildDelegatePayload({
      args: { intent: "anything" },
      timelineState: state,
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.theme_id).toBe("2rp");
  });

  it("respects an explicit theme_id override", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "anything", theme_id: "arca-gidan" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.theme_id).toBe("arca-gidan");
  });

  it("defaults scope to 'full' when omitted", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "x" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.scope).toBe("full");
  });

  it("rejects unknown scopes by falling back to 'full'", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "x", scope: "wholesale" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.scope).toBe("full");
  });

  it("includes the current timeline snapshot by default", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "x" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.current_timeline).toBeDefined();
    expect((payload?.current_timeline as { clips: unknown[] }).clips).toHaveLength(1);
  });

  it("omits the snapshot when current_timeline_snapshot is false", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "x", current_timeline_snapshot: false },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
      correlationId: FIXED_CORR_ID,
    });
    expect(payload?.current_timeline).toBeUndefined();
  });

  it("uses a generated correlation_id when none is injected", () => {
    const { payload } = buildDelegatePayload({
      args: { intent: "x" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "jwt",
    });
    expect(payload?.correlation_id).toMatch(/^[0-9a-f-]{36}$/i);
  });
});

describe("enqueueBanodocoTask", () => {
  const originalDeno = globalThis.Deno;

  beforeEach(() => {
    vi.stubGlobal("Deno", {
      env: {
        get: vi.fn((key: string) => {
          if (key === "ORCHESTRATOR_TASK_ENQUEUE_URL") return "https://orchestrator.test/functions/v1/enqueue-task";
          return undefined;
        }),
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (originalDeno) {
      vi.stubGlobal("Deno", originalDeno);
    }
  });

  it("posts the SD-034 envelope and returns 'queued'", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ task_id: "task-abc" }), { status: 200 }),
    );

    const { payload } = buildDelegatePayload({
      args: { intent: "extend by 15s" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "user-jwt",
      correlationId: FIXED_CORR_ID,
    });

    const result = await enqueueBanodocoTask(payload!, { fetchImpl: fetchImpl as unknown as typeof fetch });

    expect(result.status).toBe("queued");
    expect(result.task_id).toBe("task-abc");
    expect(result.correlation_id).toBe(FIXED_CORR_ID);

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("https://orchestrator.test/functions/v1/enqueue-task");
    expect(init.method).toBe("POST");
    expect(init.headers["Authorization"]).toBe("Bearer user-jwt");
    const body = JSON.parse(init.body);
    expect(body.task_type).toBe("banodoco_timeline_generate");
    expect(body.worker_pool).toBe("banodoco");
    expect(body.params.expected_version).toBe(7);
    expect(body.params.correlation_id).toBe(FIXED_CORR_ID);
  });

  it("surfaces orchestrator HTTP errors as enqueue errors", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response("queue full", { status: 503 }),
    );
    const { payload } = buildDelegatePayload({
      args: { intent: "extend" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "user-jwt",
      correlationId: FIXED_CORR_ID,
    });
    const result = await enqueueBanodocoTask(payload!, { fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(result.status).toBe("error");
    expect(result.message).toMatch(/HTTP 503/);
  });

  it("surfaces fetch failure as an error", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("ENETUNREACH"));
    const { payload } = buildDelegatePayload({
      args: { intent: "extend" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "user-jwt",
      correlationId: FIXED_CORR_ID,
    });
    const result = await enqueueBanodocoTask(payload!, { fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(result.status).toBe("error");
    expect(result.message).toMatch(/ENETUNREACH/);
  });

  it("returns an error when ORCHESTRATOR_TASK_ENQUEUE_URL is unset", async () => {
    vi.stubGlobal("Deno", { env: { get: () => undefined } });
    const { payload } = buildDelegatePayload({
      args: { intent: "extend" },
      timelineState: makeTimelineState(),
      timelineId: "tl-1",
      userJwt: "user-jwt",
      correlationId: FIXED_CORR_ID,
    });
    const result = await enqueueBanodocoTask(payload!);
    expect(result.status).toBe("error");
    expect(result.message).toMatch(/ORCHESTRATOR/);
  });
});

describe("executeDelegateToBanodocoAgent (top-level)", () => {
  beforeEach(() => {
    vi.stubGlobal("Deno", {
      env: {
        get: vi.fn((key: string) => {
          if (key === "ORCHESTRATOR_TASK_ENQUEUE_URL") return "https://orchestrator.test/functions/v1/enqueue-task";
          return undefined;
        }),
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the LLM-visible queued message including task_id and correlation_id", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ task_id: "task-xyz" }), { status: 200 }),
    );
    const result = await executeDelegateToBanodocoAgent(
      { intent: "extend by 15s" },
      makeTimelineState(),
      "tl-1",
      "user-jwt",
      { fetchImpl: fetchImpl as unknown as typeof fetch, correlationId: FIXED_CORR_ID },
    );
    expect(result.result).toContain("Queued");
    expect(result.result).toContain("task_id=task-xyz");
    expect(result.result).toContain(`correlation_id=${FIXED_CORR_ID}`);
  });

  it("returns the build-time error when intent is missing", async () => {
    const result = await executeDelegateToBanodocoAgent(
      {},
      makeTimelineState(),
      "tl-1",
      "user-jwt",
    );
    expect(result.result).toMatch(/intent/);
  });
});

describe("pollBanodocoTaskStatus", () => {
  beforeEach(() => {
    vi.stubGlobal("Deno", {
      env: {
        get: (key: string) => key === "ORCHESTRATOR_BASE_URL" ? "https://orchestrator.test" : undefined,
      },
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("normalises Complete with a config_version", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        status: "Complete",
        result: { config_version: 9 },
        correlation_id: FIXED_CORR_ID,
      }), { status: 200 }),
    );
    const snap = await pollBanodocoTaskStatus("task-abc", "user-jwt", { fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(snap.status).toBe("Complete");
    expect(snap.config_version).toBe(9);
    expect(snap.correlation_id).toBe(FIXED_CORR_ID);
  });

  it("maps failure_code=worker_unavailable to its dedicated status variant", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        status: "Failed",
        failure_code: "worker_unavailable",
      }), { status: 200 }),
    );
    const snap = await pollBanodocoTaskStatus("task-abc", "user-jwt", { fetchImpl: fetchImpl as unknown as typeof fetch });
    // Note: status is preserved as "Failed" (which happened) but failure_code is also surfaced.
    expect(snap.status).toBe("Failed");
    expect(snap.failure_code).toBe("worker_unavailable");
  });

  it("returns 'unknown' when ORCHESTRATOR_BASE_URL is unset", async () => {
    vi.stubGlobal("Deno", { env: { get: () => undefined } });
    const snap = await pollBanodocoTaskStatus("task-abc", "user-jwt");
    expect(snap.status).toBe("unknown");
  });

  it("returns 'unknown' on non-200", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("oops", { status: 500 }));
    const snap = await pollBanodocoTaskStatus("task-abc", "user-jwt", { fetchImpl: fetchImpl as unknown as typeof fetch });
    expect(snap.status).toBe("unknown");
  });
});

describe("summariseTaskStatusForChat", () => {
  it("summarises Queued / In Progress / Complete plainly", () => {
    expect(summariseTaskStatusForChat({ task_id: "t", status: "Queued" })).toMatch(/queued/);
    expect(summariseTaskStatusForChat({ task_id: "t", status: "In Progress" })).toMatch(/generating/);
    expect(summariseTaskStatusForChat({ task_id: "t", status: "Complete", config_version: 9 })).toMatch(/v9/);
  });

  it("emits the SD-034 retry copy on version_conflict", () => {
    const summary = summariseTaskStatusForChat({
      task_id: "t",
      status: "Failed",
      failure_code: "version_conflict",
    });
    expect(summary).toMatch(/edits superseded/);
    expect(summary).toMatch(/retry/i);
  });

  it("emits a worker_unavailable hint when no worker is around", () => {
    const summary = summariseTaskStatusForChat({
      task_id: "t",
      status: "worker_unavailable",
    });
    expect(summary).toMatch(/no banodoco worker/i);
  });

  it("emits an auth_failed hint when JWT was rejected", () => {
    const summary = summariseTaskStatusForChat({
      task_id: "t",
      status: "Failed",
      failure_code: "auth_failed",
    });
    expect(summary).toMatch(/auth/i);
  });
});

describe("findLatestPendingDelegate", () => {
  it("recovers task_id and correlation_id from a recent tool_result turn", () => {
    const turns = [
      { role: "user", content: "extend by 15s" },
      {
        role: "tool_result",
        tool_name: "delegateToBanodocoAgent",
        content: `Queued — generative work will appear in ~30s. task_id=task-abc correlation_id=${FIXED_CORR_ID}`,
      },
    ];
    const found = findLatestPendingDelegate(turns);
    expect(found?.task_id).toBe("task-abc");
    expect(found?.correlation_id).toBe(FIXED_CORR_ID);
  });

  it("returns null when no delegate tool_result exists", () => {
    const turns = [
      { role: "user", content: "hi" },
      { role: "assistant", content: "hi back" },
    ];
    expect(findLatestPendingDelegate(turns)).toBeNull();
  });

  it("returns null when the tool_result has only a partial id pattern", () => {
    const turns = [
      {
        role: "tool_result",
        tool_name: "delegateToBanodocoAgent",
        content: "Queued — generative work will appear in ~30s.",
      },
    ];
    expect(findLatestPendingDelegate(turns)).toBeNull();
  });
});
