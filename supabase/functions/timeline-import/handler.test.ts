// deno-lint-ignore-file
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { handleTimelineImport } from "./handler.ts";
import type { TimelineImportBody } from "./types.ts";

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";
const TIMELINE_ID = "22222222-2222-2222-2222-222222222222";
const USER_ID = "33333333-3333-3333-3333-333333333333";

interface FakeRow {
  id: string;
  project_id: string;
  config_version: number;
}

function createSupabaseAdminMock(options: {
  existing?: FakeRow | null;
}) {
  const maybeSingle = vi.fn().mockResolvedValue({
    data: options.existing ?? null,
    error: null,
  });
  const eq = vi.fn().mockReturnValue({ maybeSingle });
  const select = vi.fn().mockReturnValue({ eq });
  const from = vi.fn().mockReturnValue({ select });

  return {
    supabaseAdmin: { from } as unknown as Parameters<typeof handleTimelineImport>[0]["supabaseAdmin"],
    mocks: { from, select, eq, maybeSingle },
  };
}

const baseLogger = {
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

const baseTimeline = {
  output: {
    resolution: "1920x1080",
    fps: 30,
    file: "timeline.mp4",
  },
  theme: "banodoco-default",
  clips: [
    { id: "c1", at: 0, track: "v1", clipType: "media" },
  ],
};

function makeBody(overrides: Partial<TimelineImportBody> = {}): TimelineImportBody {
  return {
    project_id: PROJECT_ID,
    timeline_id: TIMELINE_ID,
    timeline: baseTimeline,
    asset_registry: { assets: {} },
    expected_version: 1,
    create_if_missing: false,
    ...overrides,
  };
}

describe("handleTimelineImport", () => {
  const originalDeno = globalThis.Deno;
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.stubGlobal("Deno", {
      env: {
        get: vi.fn((key: string) => {
          if (key === "REIGH_APPEND_SERVICE_URL") return "https://append-service.example";
          if (key === "REIGH_APPEND_SERVICE_INTERNAL_TOKEN") return "internal-token";
          return undefined;
        }),
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      config_version: 6,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
    if (originalDeno) {
      vi.stubGlobal("Deno", originalDeno);
    }
  });

  it("rejects malformed project_id", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const result = await handleTimelineImport({
      body: makeBody({ project_id: "not-a-uuid" }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn(),
    });
    expect(result.status).toBe(400);
    expect(result.body.ok).toBe(false);
  });

  it("rejects payload that fails Zod validation", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const result = await handleTimelineImport({
      body: makeBody({ timeline: { theme: "x" } }), // missing clips
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn(),
    });
    expect(result.status).toBe(400);
    if (result.body.ok === false) {
      expect(result.body.error).toMatch(/schema/i);
    }
  });

  it("accepts no-theme timelines with open generation_defaults", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 5 },
    });
    const timeline = {
      output: baseTimeline.output,
      clips: [],
      generation_defaults: {
        model: "sequence-v1",
        image: { quality: "high", provider: "reigh" },
        provider_settings: { seed: 1234, flags: ["keep", "open"] },
      },
    };
    const result = await handleTimelineImport({
      body: makeBody({ timeline, expected_version: 5 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });

    expect(result.status).toBe(200);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "https://append-service.example/v1/timelines/22222222-2222-2222-2222-222222222222/config-replaced",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer internal-token",
        }),
        body: expect.stringContaining("\"generation_defaults\""),
      }),
    );
  });

  it("canonicalizes malformed non-hold trims against the provided asset registry before persistence", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 5 },
    });
    const timeline = {
      output: baseTimeline.output,
      clips: [{
        id: "clip-video",
        at: 0,
        track: "v1",
        clipType: "media",
        asset: "asset-video",
      }],
    };
    const asset_registry = {
      assets: {
        "asset-video": {
          file: "video.mp4",
          duration: 12,
        },
      },
    };

    const result = await handleTimelineImport({
      body: makeBody({ timeline, asset_registry, expected_version: 5 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });

    expect(result.status).toBe(200);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "https://append-service.example/v1/timelines/22222222-2222-2222-2222-222222222222/config-replaced",
      expect.objectContaining({
        body: expect.stringContaining("\"asset_registry\""),
      }),
    );
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual(expect.objectContaining({
      expected_version: 5,
      source: "supabase_config",
      actor: { type: "agent", id: "timeline-import" },
      asset_registry,
      config: expect.objectContaining({
        clips: [expect.objectContaining({
          id: "clip-video",
          from: 0,
          to: 12,
        })],
      }),
    }));
  });

  it("returns structured domain validation details for stale serialized shapes", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const result = await handleTimelineImport({
      body: makeBody({
        timeline: {
          output: baseTimeline.output,
          clips: [{
            id: "clip-1",
            at: 0,
            track: "v1",
            clipType: "hold",
            hold: 2,
            unexpected_clip_key: true,
          }],
        },
      }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });

    expect(result.status).toBe(400);
    if (result.body.ok === false) {
      expect(result.body.error).toBe("timeline payload failed canonical validation");
      expect(result.body.details).toEqual(expect.objectContaining({
        level: "pair-aware",
        issues: expect.arrayContaining([
          expect.objectContaining({
            code: "unexpected_clip_key",
            path: expect.stringContaining("unexpected_clip_key"),
          }),
        ]),
      }));
    } else {
      throw new Error("expected domain validation failure");
    }
  });

  it("returns 403 when ownership verification fails", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({});
    const verify = vi.fn().mockResolvedValue({ success: false, error: "Forbidden", statusCode: 403 });
    const result = await handleTimelineImport({
      body: makeBody(),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: verify,
    });
    expect(verify).toHaveBeenCalledWith(PROJECT_ID, USER_ID);
    expect(result.status).toBe(403);
  });

  it("returns 404 when timeline missing and create_if_missing=false", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({ existing: null });
    const result = await handleTimelineImport({
      body: makeBody(),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(404);
  });

  it("inserts a new timeline when create_if_missing=true and the row is absent", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      config_version: 1,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: null,
    });
    const result = await handleTimelineImport({
      body: makeBody({ create_if_missing: true }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(201);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "https://append-service.example/v1/timelines/create-with-config",
      expect.objectContaining({
        method: "POST",
      }),
    );
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual(expect.objectContaining({
      project_id: PROJECT_ID,
      timeline_id: TIMELINE_ID,
      user_id: USER_ID,
      source: "supabase_config",
      actor: { type: "agent", id: "timeline-import" },
    }));
    if (result.body.ok === true) {
      expect(result.body.created).toBe(true);
    }
  });

  it("calls the append service with the right args when asset_registry is present", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 5 },
    });
    const result = await handleTimelineImport({
      body: makeBody({ expected_version: 5 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body).toEqual(expect.objectContaining({
      expected_version: 5,
      actor: { type: "agent", id: "timeline-import" },
      source: "supabase_config",
    }));
    expect(result.status).toBe(200);
  });

  it("returns 409 with current_version when the append service reports a version conflict", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: "version_conflict",
      detail: "timeline config_version mismatch: expected 3, found 7",
    }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 7 },
    });
    const result = await handleTimelineImport({
      body: makeBody({ expected_version: 3 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(409);
    if (result.body.ok === false && result.body.error === "version_mismatch") {
      expect(result.body.current_version).toBe(7);
    } else {
      throw new Error("expected version_mismatch");
    }
  });

  it("--force path: omits expected_version, edge function uses current as expected", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 9 },
    });
    const body = makeBody();
    delete body.expected_version;
    const result = await handleTimelineImport({
      body,
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(200);
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const payload = JSON.parse(String(init?.body));
    expect(payload.expected_version).toBe(9);
  });

  it("returns 500 when the append service returns a non-409 error on update", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: "internal_error",
      detail: "something went wrong inside the service",
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 5 },
    });
    const result = await handleTimelineImport({
      body: makeBody({ expected_version: 5 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(500);
    if (result.body.ok === false) {
      expect(result.body.error).toBe("rpc failed");
      expect(result.body.details).toBe("something went wrong inside the service");
    } else {
      throw new Error("expected 500 error response");
    }
  });

  it("returns 500 when the append service fails on create", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: "service_unavailable",
      detail: "cannot create timeline at this time",
    }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
    const { supabaseAdmin } = createSupabaseAdminMock({ existing: null });
    const result = await handleTimelineImport({
      body: makeBody({ create_if_missing: true }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    expect(result.status).toBe(500);
    if (result.body.ok === false) {
      expect(result.body.error).toBe("timeline insert failed");
      expect(result.body.details).toBe("cannot create timeline at this time");
    } else {
      throw new Error("expected 500 error response");
    }
  });

  it("sends no TS-computed event-log fields to the append service on update", async () => {
    const { supabaseAdmin } = createSupabaseAdminMock({
      existing: { id: TIMELINE_ID, project_id: PROJECT_ID, config_version: 5 },
    });
    await handleTimelineImport({
      body: makeBody({ expected_version: 5 }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const payload = JSON.parse(String(init?.body));
    // The Edge handler must not compute event-log fields — that is the Python
    // append service's job.  Verify the payload omits them.
    const forbiddenFields = [
      "event_id",
      "hash",
      "prev_hash",
      "version",
      "projection",
      "schema_version",
    ];
    for (const field of forbiddenFields) {
      expect(payload).not.toHaveProperty(field);
    }
    // It must still include the expected application-level fields.
    expect(payload).toHaveProperty("config");
    expect(payload).toHaveProperty("expected_version");
    expect(payload).toHaveProperty("source");
    expect(payload).toHaveProperty("actor");
  });

  it("sends no TS-computed event-log fields to the append service on create", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      config_version: 1,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;
    const { supabaseAdmin } = createSupabaseAdminMock({ existing: null });
    await handleTimelineImport({
      body: makeBody({ create_if_missing: true }),
      userId: USER_ID,
      supabaseAdmin,
      logger: baseLogger,
      verifyOwnership: vi.fn().mockResolvedValue({ success: true }),
    });
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const payload = JSON.parse(String(init?.body));
    const forbiddenFields = [
      "event_id",
      "hash",
      "prev_hash",
      "version",
      "projection",
      "schema_version",
    ];
    for (const field of forbiddenFields) {
      expect(payload).not.toHaveProperty(field);
    }
    expect(payload).toHaveProperty("config");
    expect(payload).toHaveProperty("project_id");
    expect(payload).toHaveProperty("timeline_id");
  });
});
