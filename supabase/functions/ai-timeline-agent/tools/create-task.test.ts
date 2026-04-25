import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  createGenerationTask: vi.fn(),
  createShotWithGenerations: vi.fn(),
  resolveClipGenerationIds: vi.fn(),
  resolveSelectedClipShot: vi.fn(),
}));

vi.mock("./generation.ts", () => ({
  createGenerationTask: (...args: unknown[]) => mocks.createGenerationTask(...args),
}));

vi.mock("./clips.ts", () => ({
  createShotWithGenerations: (...args: unknown[]) => mocks.createShotWithGenerations(...args),
  resolveClipGenerationIds: (...args: unknown[]) => mocks.resolveClipGenerationIds(...args),
  resolveSelectedClipShot: (...args: unknown[]) => mocks.resolveSelectedClipShot(...args),
}));

import { executeCreateTask } from "./create-task.ts";

describe("executeCreateTask", () => {
  const originalDeno = globalThis.Deno;
  const originalFetch = globalThis.fetch;
  const timelineState = {
    config: { clips: [] },
    configVersion: 1,
    registry: { assets: {} },
    projectId: "project-1",
  } as never;
  const generationContext = {
    image: { defaultModelName: "qwen-image", activeReference: null, selectedLorasByCategory: {} },
    travel: null,
  };
  const timelineStateWithClips = (...clips: Array<Record<string, unknown>>) => ({
    ...timelineState,
    config: { clips },
  }) as never;
  const createSupabaseAdminWithGenerationRows = (
    rows: Array<{ id: string; storage_mode: string }>,
  ) => ({
    from: vi.fn((table: string) => {
      if (table !== "generations") {
        throw new Error(`Unexpected table ${table}`);
      }

      return {
        select: vi.fn(() => ({
          in: vi.fn(async () => ({ data: rows, error: null })),
        })),
      };
    }),
  }) as never;
  const emptySupabaseAdmin = () => createSupabaseAdminWithGenerationRows([]);

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.resolveClipGenerationIds.mockReturnValue([]);
    mocks.resolveSelectedClipShot.mockResolvedValue({ shotId: null, source: null });
    mocks.createGenerationTask.mockResolvedValue({ result: "Queued text-to-image task task-1." });
    vi.stubGlobal("Deno", {
      env: {
        get: vi.fn((key: string) => {
          if (key === "SUPABASE_URL") return "https://example.supabase.co";
          if (key === "SUPABASE_SERVICE_ROLE_KEY") return "service-role-key";
          return undefined;
        }),
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
    if (originalDeno) {
      vi.stubGlobal("Deno", originalDeno);
    }
  });

  it("queues only the unique prompts when ai-prompt returns duplicates, reporting the shortfall", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        prompts: Array.from({ length: 16 }, () => "same prompt"),
      }),
    }) as typeof fetch;

    const result = await executeCreateTask(
      {
        task_type: "text-to-image",
        prompt: "same prompt",
        count: 16,
        model: "qwen-image",
      },
      timelineState,
      undefined,
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(result.result).toContain("Queued 1 task with varied prompts.");
    expect(result.result).toContain("Only 1 of 16 distinct prompt variations were available");
    expect(mocks.createGenerationTask).toHaveBeenCalledTimes(1);
  });

  it("queues all unique prompts when ai-prompt returns a varied set", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        prompts: ["alpha", "beta", "gamma", "delta"],
      }),
    }) as typeof fetch;

    const result = await executeCreateTask(
      {
        task_type: "text-to-image",
        prompt: "base",
        count: 4,
        model: "qwen-image",
      },
      timelineState,
      undefined,
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(result.result).toContain("Queued 4 tasks with varied prompts.");
    expect(mocks.createGenerationTask).toHaveBeenCalledTimes(4);
    const idempotencyKeys = mocks.createGenerationTask.mock.calls.map(([args]) => (args as { idempotency_key?: string }).idempotency_key);
    expect(new Set(idempotencyKeys).size).toBe(4);
  });

  it("forwards variation_intent to the ai-prompt request body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ prompts: ["one", "two"] }),
    }) as unknown as typeof fetch;
    globalThis.fetch = fetchMock;

    await executeCreateTask(
      {
        task_type: "text-to-image",
        prompt: "a fox in a forest",
        count: 2,
        variation_intent: "different lighting conditions",
        model: "qwen-image",
      },
      timelineState,
      undefined,
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    const [, init] = (fetchMock as unknown as { mock: { calls: Array<[string, { body: string }]> } }).mock.calls[0];
    const parsed = JSON.parse(init.body);
    expect(parsed.variationIntent).toBe("different lighting conditions");
  });

  it("reports the real queued count instead of the requested count when some creates fail", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        prompts: ["one", "two", "three"],
      }),
    }) as typeof fetch;

    mocks.createGenerationTask
      .mockResolvedValueOnce({ result: "Queued text-to-image task task-1." })
      .mockResolvedValueOnce({ result: "Failed to create task: boom" })
      .mockResolvedValueOnce({ result: "Queued text-to-image task task-3." });

    const result = await executeCreateTask(
      {
        task_type: "text-to-image",
        prompt: "base",
        count: 3,
        model: "qwen-image",
      },
      timelineState,
      undefined,
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(result.result).toContain("Queued 2 tasks with varied prompts.");
    expect(result.result).toContain("1 failed.");
  });

  it("reuses the resolved shared shot for selected reference clips instead of creating a new one", async () => {
    mocks.resolveClipGenerationIds.mockReturnValue(["gen-1"]);
    mocks.resolveSelectedClipShot.mockResolvedValue({ shotId: "shot-1", source: "explicit" });

    const result = await executeCreateTask(
      {
        task_type: "style-transfer",
        prompt: "apply this look to a portrait",
        reference_image_urls: ["https://example.com/reference.png"],
      },
      timelineState,
      [{
        clip_id: "clip-1",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-1",
        shot_id: "shot-1",
      }],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(result.result).toContain("Reused shot shot-1.");
    expect(mocks.createShotWithGenerations).not.toHaveBeenCalled();
    expect(mocks.createGenerationTask).toHaveBeenCalledWith(expect.objectContaining({
      shot_id: "shot-1",
      reference_image_url: "https://example.com/reference.png",
    }));
  });

  it("rejects local-mode input generations with a structured error before task creation", async () => {
    const supabaseAdmin = createSupabaseAdminWithGenerationRows([
      { id: "gen-local", storage_mode: "local" },
    ]);

    const result = await executeCreateTask(
      {
        task_type: "image-to-image",
        prompt: "warm cinematic grade",
        reference_image_urls: ["https://example.com/reference.png"],
        strength: 0.45,
      },
      timelineState,
      [{
        clip_id: "gallery-gen-local",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-local",
        variant_id: "variant-1",
      }],
      supabaseAdmin,
      generationContext,
      "timeline-1",
    );

    expect(JSON.parse(result.result)).toEqual({
      code: "generation_not_materialized",
      generation_id: "gen-local",
      message: "This generation still lives on the user's device. Open the gallery and let it upload before running a task.",
    });
    expect(mocks.createGenerationTask).not.toHaveBeenCalled();
  });

  it("keeps selected-image edits on the image-to-image path without forcing transfer mode", async () => {
    mocks.resolveClipGenerationIds.mockReturnValue(["gen-1"]);
    mocks.resolveSelectedClipShot.mockResolvedValue({ shotId: "shot-1", source: "explicit" });

    await executeCreateTask(
      {
        task_type: "image-to-image",
        prompt: "orbital view of it without style transfer",
        reference_image_urls: ["https://example.com/reference.png"],
        model: "z-image",
        strength: 0.55,
      },
      timelineState,
      [{
        clip_id: "clip-1",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-1",
        shot_id: "shot-1",
      }],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(mocks.createGenerationTask).toHaveBeenCalledWith(expect.objectContaining({
      task_type: "image-to-image",
      prompt: "orbital view of it without style transfer",
      reference_image_url: "https://example.com/reference.png",
      model_name: "z-image",
      strength: 0.55,
      shot_id: "shot-1",
      based_on: "gen-1",
      params: expect.objectContaining({
        is_primary: true,
      }),
    }));

    const firstCallArgs = mocks.createGenerationTask.mock.calls[0]?.[0] as {
      reference_mode?: string;
    };
    expect(firstCallArgs.reference_mode).toBeUndefined();
  });

  it("passes timeline_placement through when the agent specifies it", async () => {
    const timelinePlacement = {
      timeline_id: "timeline-1",
      source_clip_id: "clip-1",
      target_track: "V1",
      insertion_time: 12.5,
      intent: "after_source" as const,
    };

    await executeCreateTask(
      {
        task_type: "image-to-image",
        prompt: "warm cinematic grade",
        reference_image_urls: ["https://example.com/reference.png"],
        strength: 0.45,
        timeline_placement: timelinePlacement,
      },
      timelineState,
      [{
        clip_id: "clip-1",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-1",
        shot_id: "shot-1",
      }],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(mocks.createGenerationTask).toHaveBeenCalledWith(expect.objectContaining({
      timeline_placement: timelinePlacement,
    }));
  });

  it("omits timeline_placement when the agent does not specify it", async () => {
    await executeCreateTask(
      {
        task_type: "image-to-image",
        prompt: "warm cinematic grade",
        reference_image_urls: ["https://example.com/reference.png"],
        strength: 0.45,
      },
      timelineState,
      [{
        clip_id: "clip-1",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-1",
        shot_id: "shot-1",
      }],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    const firstCallArgs = mocks.createGenerationTask.mock.calls[0]?.[0] as Record<string, unknown>;
    expect("timeline_placement" in firstCallArgs).toBe(false);
  });

  it("persists source_variant_id and placement_intent for exactly one selected timeline clip", async () => {
    await executeCreateTask(
      {
        task_type: "image-to-image",
        prompt: "warm cinematic grade",
        reference_image_urls: ["https://example.com/reference.png"],
        strength: 0.45,
      },
      timelineStateWithClips({
        id: "clip-1",
        at: 5,
        track: "V1",
        hold: 2.5,
      }),
      [{
        clip_id: "clip-1",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-1",
        variant_id: "variant-1",
      }],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(mocks.createGenerationTask).toHaveBeenCalledWith(expect.objectContaining({
      based_on: "gen-1",
      source_variant_id: "variant-1",
      params: expect.objectContaining({
        is_primary: true,
        placement_intent: {
          timeline_id: "timeline-1",
          anchor_clip_id: "clip-1",
          anchor_generation_id: "gen-1",
          anchor_variant_id: "variant-1",
          relation: "after",
          preferred_track_id: "V1",
          fallback_at: 7.5,
          fallback_track_id: "V1",
        },
      }),
    }));
  });

  it("omits placement_intent for gallery-only selections while preserving source_variant_id", async () => {
    await executeCreateTask(
      {
        task_type: "image-to-image",
        prompt: "warm cinematic grade",
        reference_image_urls: ["https://example.com/reference.png"],
        strength: 0.45,
      },
      timelineState,
      [{
        clip_id: "gallery-gen-1",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-1",
        variant_id: "variant-1",
      }],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    const firstCallArgs = mocks.createGenerationTask.mock.calls[0]?.[0] as {
      source_variant_id?: string;
      params?: Record<string, unknown>;
    };

    expect(firstCallArgs.source_variant_id).toBe("variant-1");
    expect(firstCallArgs.params).toEqual(expect.objectContaining({
      is_primary: true,
    }));
    expect("placement_intent" in (firstCallArgs.params ?? {})).toBe(false);
  });

  it("threads source_variant_id and placement_intent for image-upscale requests from a single timeline clip", async () => {
    await executeCreateTask(
      {
        task_type: "image-upscale",
        prompt: "upscale this still",
        reference_image_urls: ["https://example.com/reference.png"],
      },
      timelineStateWithClips({
        id: "clip-1",
        at: 5,
        track: "V1",
        hold: 2.5,
      }),
      [{
        clip_id: "clip-1",
        url: "https://example.com/reference.png",
        media_type: "image",
        generation_id: "gen-1",
        variant_id: "variant-1",
      }],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    expect(mocks.createGenerationTask).toHaveBeenCalledWith(expect.objectContaining({
      generation_id: "gen-1",
      source_variant_id: "variant-1",
      params: expect.objectContaining({
        placement_intent: {
          timeline_id: "timeline-1",
          anchor_clip_id: "clip-1",
          anchor_generation_id: "gen-1",
          anchor_variant_id: "variant-1",
          relation: "after",
          preferred_track_id: "V1",
          fallback_at: 7.5,
          fallback_track_id: "V1",
        },
      }),
    }));
  });

  it("omits placement_intent when multiple selected clips are still on the timeline", async () => {
    await executeCreateTask(
      {
        task_type: "image-to-image",
        prompt: "warm cinematic grade",
        reference_image_urls: ["https://example.com/reference-1.png"],
        strength: 0.45,
      },
      timelineStateWithClips(
        {
          id: "clip-1",
          at: 5,
          track: "V1",
          hold: 2.5,
        },
        {
          id: "clip-2",
          at: 10,
          track: "V2",
          hold: 3,
        },
      ),
      [
        {
          clip_id: "clip-1",
          url: "https://example.com/reference-1.png",
          media_type: "image",
          generation_id: "gen-1",
          variant_id: "variant-1",
        },
        {
          clip_id: "clip-2",
          url: "https://example.com/reference-2.png",
          media_type: "image",
          generation_id: "gen-2",
          variant_id: "variant-2",
        },
      ],
      emptySupabaseAdmin(),
      generationContext,
      "timeline-1",
    );

    const firstCallArgs = mocks.createGenerationTask.mock.calls[0]?.[0] as {
      source_variant_id?: string;
      params?: Record<string, unknown>;
    };

    expect(firstCallArgs.source_variant_id).toBe("variant-1");
    expect(firstCallArgs.params).toEqual(expect.objectContaining({
      is_primary: true,
    }));
    expect("placement_intent" in (firstCallArgs.params ?? {})).toBe(false);
  });
});
