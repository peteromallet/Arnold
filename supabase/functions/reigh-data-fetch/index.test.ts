import { beforeEach, describe, expect, it, vi } from "vitest";
import { __getServeHandler, __resetServeHandler } from "../_tests/mocks/denoHttpServer.ts";
import * as ReighDataFetchEntrypoint from "./index.ts";
import { mapProjectGenerationToReighMedia, mapShotGenerationToReighRow } from "./index.ts";

const mocks = vi.hoisted(() => ({
  withEdgeRequest: vi.fn(),
  verifyProjectOwnership: vi.fn(),
  loggerError: vi.fn(),
  loggerInfo: vi.fn(),
}));

vi.mock("../_shared/edgeHandler.ts", () => ({
  NO_SESSION_RUNTIME_OPTIONS: {
    runtimeOptions: {
      clientOptions: {
        auth: {
          autoRefreshToken: false,
          persistSession: false,
        },
      },
    },
  },
  withEdgeRequest: (...args: unknown[]) => mocks.withEdgeRequest(...args),
}));

vi.mock("../_shared/auth.ts", () => ({
  verifyProjectOwnership: (...args: unknown[]) => mocks.verifyProjectOwnership(...args),
}));

vi.mock("../_shared/http.ts", () => ({
  jsonResponse: (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
}));

type QueryResult = { data: unknown; error: unknown };

function createQuery(result: QueryResult, calls: unknown[][]) {
  const query = {
    select: vi.fn((...args: unknown[]) => {
      calls.push(["select", ...args]);
      return query;
    }),
    eq: vi.fn((...args: unknown[]) => {
      calls.push(["eq", ...args]);
      return query;
    }),
    in: vi.fn((...args: unknown[]) => {
      calls.push(["in", ...args]);
      return query;
    }),
    or: vi.fn((...args: unknown[]) => {
      calls.push(["or", ...args]);
      return query;
    }),
    order: vi.fn((...args: unknown[]) => {
      calls.push(["order", ...args]);
      return query;
    }),
    range: vi.fn((...args: unknown[]) => {
      calls.push(["range", ...args]);
      return query;
    }),
    single: vi.fn(() => Promise.resolve(result)),
    then: (resolve: (value: QueryResult) => unknown, reject?: (reason: unknown) => unknown) =>
      Promise.resolve(result).then(resolve, reject),
  };
  return query;
}

function createSupabaseMock(results: Record<string, QueryResult>) {
  const calls: Record<string, unknown[][]> = {};
  return {
    calls,
    client: {
      from: vi.fn((table: string) => {
        calls[table] = [];
        return createQuery(results[table] ?? { data: [], error: null }, calls[table]);
      }),
    },
  };
}

function createContext(
  body: Record<string, unknown>,
  auth: Record<string, unknown>,
  supabaseAdmin: unknown = {},
) {
  return {
    supabaseAdmin,
    logger: {
      error: mocks.loggerError,
      info: mocks.loggerInfo,
    },
    body,
    auth,
  };
}

async function loadHandler() {
  await import("./index.ts");
  return __getServeHandler();
}

describe("reigh-data-fetch edge entrypoint", () => {
  const projectId = "11111111-1111-4111-8111-111111111111";
  const shotId = "22222222-2222-4222-8222-222222222222";
  const taskId = "33333333-3333-4333-8333-333333333333";
  const timelineId = "44444444-4444-4444-8444-444444444444";

  const project = {
    id: projectId,
    name: "Project",
    user_id: "user-1",
    aspect_ratio: "16:9",
    settings: { style: "clean" },
    created_at: "2026-01-01T00:00:00Z",
  };
  const shot = {
    id: shotId,
    project_id: projectId,
    name: "Shot",
    position: 1,
    aspect_ratio: "16:9",
    settings: { camera: "wide" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
  const shotGenerationRows = [
    {
      id: "sg-1",
      shot_id: shotId,
      generation_id: "gen-1",
      timeline_frame: 0,
      metadata: { prompt: "start" },
      generation: {
        id: "gen-1",
        location: "original-1.png",
        thumbnail_url: "thumb-1.png",
        type: "image",
        created_at: "2026-01-01T00:00:01Z",
        starred: true,
        name: "Start",
        based_on: null,
        params: { seed: 1 },
        primary_variant_id: "variant-1",
        primary_variant: {
          location: "variant-1.png",
          thumbnail_url: "variant-thumb-1.png",
        },
      },
    },
    {
      id: "sg-2",
      shot_id: shotId,
      generation_id: "gen-2",
      timeline_frame: null,
      metadata: {},
      generation: {
        id: "gen-2",
        location: "loose.png",
        thumbnail_url: null,
        type: "image",
        created_at: "2026-01-01T00:00:02Z",
        starred: false,
        name: null,
        based_on: null,
        params: null,
        primary_variant_id: null,
        primary_variant: null,
      },
    },
    {
      id: "sg-3",
      shot_id: shotId,
      generation_id: "gen-3",
      timeline_frame: 50,
      metadata: {},
      generation: {
        id: "gen-3",
        location: "video.mp4",
        thumbnail_url: "video.jpg",
        type: "video",
        created_at: "2026-01-01T00:00:03Z",
        starred: false,
        name: "Video",
        based_on: null,
        params: {},
        primary_variant_id: null,
        primary_variant: null,
      },
    },
  ];
  const projectGenerationRows = [
    {
      id: "gallery-gen-1",
      location: "gallery-original.png",
      thumbnail_url: "gallery-thumb.png",
      primary_variant_id: "gallery-variant-1",
      storage_mode: "remote",
      local_handle_id: null,
      local_file_name: null,
      local_file_size: null,
      local_file_mime: null,
      primary_variant: {
        location: "gallery-variant.png",
        thumbnail_url: "gallery-variant-thumb.png",
      },
      type: "image",
      created_at: "2026-01-01T00:00:04Z",
      updated_at: "2026-01-01T00:00:05Z",
      params: { prompt: "gallery prompt", content_type: "image" },
      starred: true,
      tasks: ["task-from-generation"],
      based_on: null,
      shot_data: null,
      name: "Gallery Image",
      is_child: false,
      parent_generation_id: null,
      child_order: null,
    },
  ];
  const taskRow = {
    id: taskId,
    project_id: projectId,
    task_type: "travel-between-images",
    status: "completed",
    params: { prompt: "task prompt", settings: { steps: 20 } },
    output_location: "task-output.mp4",
    result_data: { frames: 120 },
    dependant_on: ["dep-1"],
    error_message: null,
    attempts: 1,
    generation_created: true,
    generation_started_at: "2026-01-01T00:00:01Z",
    generation_processed_at: "2026-01-01T00:00:02Z",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:03Z",
    worker_id: "worker-1",
  };
  const timelineRow = {
    id: timelineId,
    project_id: projectId,
    user_id: "user-1",
    name: "Timeline",
    config: { tracks: [{ id: "track-1" }], nested: { untouched: true } },
    asset_registry: { assets: { asset1: { url: "reigh://asset" } } },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:05Z",
  };

  it("imports entrypoint module directly", () => {
    expect(ReighDataFetchEntrypoint).toBeDefined();
  });

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    __resetServeHandler();

    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        const supabase = createSupabaseMock({
          projects: { data: project, error: null },
          shots: { data: [shot], error: null },
          shot_generations: { data: shotGenerationRows, error: null },
          generations: { data: projectGenerationRows, error: null },
          tasks: { data: [taskRow], error: null },
          timelines: { data: [timelineRow], error: null },
        });
        return handler(createContext({ project_id: projectId }, { isServiceRole: true, userId: null }, supabase.client));
      },
    );
  });

  it("maps shot generation rows with primary variant URLs and position semantics", () => {
    const mapped = mapShotGenerationToReighRow(shotGenerationRows[0]);

    expect(mapped).toMatchObject({
      id: "sg-1",
      generation_id: "gen-1",
      shotImageEntryId: "sg-1",
      shot_generation_id: "sg-1",
      location: "variant-1.png",
      imageUrl: "variant-1.png",
      thumbUrl: "variant-thumb-1.png",
      type: "image",
      timeline_frame: 0,
      position: 0,
      primary_variant_id: "variant-1",
      starred: true,
      params: { seed: 1 },
      metadata: { prompt: "start" },
    });

    expect(mapShotGenerationToReighRow(shotGenerationRows[1])).toMatchObject({
      id: "sg-2",
      location: "loose.png",
      imageUrl: "loose.png",
      thumbUrl: "loose.png",
      timeline_frame: null,
    });
    expect(mapShotGenerationToReighRow(shotGenerationRows[1])).not.toHaveProperty("position");
  });

  it("maps project gallery media with useProjectGenerations transformer semantics", () => {
    const mapped = mapProjectGenerationToReighMedia(projectGenerationRows[0]);

    expect(mapped).toMatchObject({
      id: "gallery-gen-1",
      url: "gallery-variant.png",
      location: "gallery-variant.png",
      thumbUrl: "gallery-variant-thumb.png",
      prompt: "gallery prompt",
      createdAt: "2026-01-01T00:00:04Z",
      updatedAt: "2026-01-01T00:00:05Z",
      isVideo: false,
      type: "image",
      contentType: "image/png",
      starred: true,
      primary_variant_id: "gallery-variant-1",
      storage_mode: "remote",
      is_child: false,
      parent_generation_id: undefined,
    });
    expect(mapped.metadata).toMatchObject({
      prompt: "gallery prompt",
      content_type: "image",
      taskId: "task-from-generation",
      based_on: null,
      variant_id: "gallery-variant-1",
    });
  });

  it("uses strict JSON parsing and shared PAT/service-role auth", async () => {
    const handler = await loadHandler();
    await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));

    expect(mocks.withEdgeRequest).toHaveBeenCalledWith(
      expect.any(Request),
      expect.objectContaining({
        functionName: "reigh-data-fetch",
        logPrefix: "[REIGH-DATA-FETCH]",
        parseBody: "strict",
        auth: { required: true },
        runtimeOptions: {
          clientOptions: {
            auth: {
              autoRefreshToken: false,
              persistSession: false,
            },
          },
        },
      }),
      expect.any(Function),
    );
  });

  it("rejects missing project_id before ownership checks", async () => {
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({}, { isServiceRole: false, userId: "user-1" }));
      },
    );

    const handler = await loadHandler();
    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "project_id is required" });
    expect(mocks.verifyProjectOwnership).not.toHaveBeenCalled();
  });

  it("rejects invalid scoped UUID filters before ownership checks", async () => {
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext(
          { project_id: projectId, shot_id: "not-a-uuid" },
          { isServiceRole: false, userId: "user-1" },
        ));
      },
    );

    const handler = await loadHandler();
    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "shot_id must be a valid UUID" });
    expect(mocks.verifyProjectOwnership).not.toHaveBeenCalled();
  });

  it("verifies project ownership for non-service callers before returning data", async () => {
    mocks.verifyProjectOwnership.mockResolvedValue({
      success: false,
      error: "Forbidden: Project does not belong to user",
      statusCode: 403,
    });
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext({ project_id: projectId }, { isServiceRole: false, userId: "user-1" }));
      },
    );

    const handler = await loadHandler();
    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));

    expect(mocks.verifyProjectOwnership).toHaveBeenCalledWith(
      {},
      projectId,
      "user-1",
      "[REIGH-DATA-FETCH]",
    );
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "Forbidden: Project does not belong to user",
    });
  });

  it("does not perform ownership lookup for service-role callers", async () => {
    const supabase = createSupabaseMock({
      projects: { data: project, error: null },
      shots: { data: [shot], error: null },
      shot_generations: { data: shotGenerationRows, error: null },
      generations: { data: projectGenerationRows, error: null },
      tasks: { data: [taskRow], error: null },
      timelines: { data: [timelineRow], error: null },
    });
    mocks.withEdgeRequest.mockImplementation(
      async (_req: Request, _opts: unknown, handler: (ctx: unknown) => Promise<Response>) => {
        return handler(createContext(
          {
            project_id: projectId,
            shot_id: shotId,
            task_id: taskId,
            timeline_id: timelineId,
          },
          { isServiceRole: true, userId: null },
          supabase.client,
        ));
      },
    );

    const handler = await loadHandler();
    const response = await handler(new Request("https://edge.test/reigh-data-fetch", { method: "POST" }));

    expect(mocks.verifyProjectOwnership).not.toHaveBeenCalled();
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toMatchObject({
      project_id: projectId,
      filters: {
        shot_id: shotId,
        task_id: taskId,
        timeline_id: timelineId,
      },
      project,
      project_settings: { style: "clean" },
      shots: [
        {
          ...shot,
          imageCount: 3,
          positionedImageCount: 2,
          unpositionedImageCount: 1,
          hasUnpositionedImages: true,
        },
      ],
      shot_settings: {
        [shotId]: { camera: "wide" },
      },
      shot_media: {
        by_shot: {
          [shotId]: {
            timeline_images: [
              expect.objectContaining({
                id: "sg-1",
                location: "variant-1.png",
                thumbUrl: "variant-thumb-1.png",
                timeline_frame: 0,
                position: 0,
              }),
            ],
            unpositioned_images: [
              expect.objectContaining({
                id: "sg-2",
                timeline_frame: null,
              }),
            ],
            video_outputs: [
              expect.objectContaining({
                id: "sg-3",
                type: "video",
                timeline_frame: 50,
                position: 1,
              }),
            ],
          },
        },
      },
      project_media: {
        items: [
          expect.objectContaining({
            id: "gallery-gen-1",
            location: "gallery-variant.png",
            thumbUrl: "gallery-variant-thumb.png",
            timeline_frame: null,
            position: null,
          }),
        ],
        images: [
          expect.objectContaining({
            id: "gallery-gen-1",
            isVideo: false,
          }),
        ],
        videos: [],
        total: 1,
        hasMore: false,
        limit: 100,
        offset: 0,
      },
      tasks: [
        expect.objectContaining({
          id: taskId,
          project_id: projectId,
          status: "completed",
          params: { prompt: "task prompt", settings: { steps: 20 } },
          output_location: "task-output.mp4",
          result_data: { frames: 120 },
        }),
      ],
      task_settings: {
        [taskId]: {
          params: { prompt: "task prompt", settings: { steps: 20 } },
          settings: { steps: 20 },
          task_type: "travel-between-images",
          status: "completed",
          output_location: "task-output.mp4",
          result_data: { frames: 120 },
        },
      },
      timelines: [
        {
          ...timelineRow,
        },
      ],
    });
    expect(body.tasks[0]).not.toHaveProperty("settings");
    expect(body.timelines[0].config).toEqual(timelineRow.config);
    expect(body.timelines[0].asset_registry).toEqual(timelineRow.asset_registry);
    expect(supabase.calls.shots).toContainEqual(["eq", "project_id", projectId]);
    expect(supabase.calls.shots).toContainEqual(["eq", "id", shotId]);
    expect(supabase.calls.shots).toContainEqual(["order", "position", { ascending: true }]);
    expect(supabase.calls.shot_generations).toContainEqual(["in", "shot_id", [shotId]]);
    expect(supabase.calls.shot_generations).toContainEqual([
      "order",
      "timeline_frame",
      { ascending: true, nullsFirst: false },
    ]);
    expect(supabase.calls.generations).toContainEqual(["eq", "project_id", projectId]);
    expect(supabase.calls.generations).toContainEqual(["eq", "is_child", false]);
    expect(supabase.calls.generations).toContainEqual(["or", "location.not.is.null,storage_mode.eq.local"]);
    expect(supabase.calls.generations).toContainEqual(["order", "created_at", { ascending: false }]);
    expect(supabase.calls.generations).toContainEqual(["range", 0, 99]);
    expect(supabase.calls.tasks).toContainEqual(["eq", "project_id", projectId]);
    expect(supabase.calls.tasks).toContainEqual(["eq", "id", taskId]);
    expect(supabase.calls.tasks).toContainEqual(["order", "created_at", { ascending: false }]);
    expect(supabase.calls.timelines).toContainEqual(["eq", "project_id", projectId]);
    expect(supabase.calls.timelines).toContainEqual(["eq", "id", timelineId]);
    expect(supabase.calls.timelines).toContainEqual(["order", "updated_at", { ascending: false }]);
  });
});
