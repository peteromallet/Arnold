import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadTimelineState, saveTimelineConfigVersioned } from "./db.ts";
import { appendTimelineConfigViaService } from "../_shared/reighAppendService.ts";
import type { SupabaseAdmin, TimelineState } from "./types.ts";

describe("saveTimelineConfigVersioned", () => {
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
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
    if (originalDeno) {
      vi.stubGlobal("Deno", originalDeno);
    }
  });

  it("posts config saves to the append service", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      config_version: 8,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;

    const nextVersion = await saveTimelineConfigVersioned(
      {} as SupabaseAdmin,
      "timeline-1",
      7,
      { tracks: [], clips: [] },
    );

    expect(nextVersion).toBe(8);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "https://append-service.example/v1/timelines/timeline-1/config-replaced",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer internal-token",
        }),
      }),
    );
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual(expect.objectContaining({
      expected_version: 7,
      source: "editor_save",
      actor: { type: "agent", id: "ai-timeline-agent" },
      config: { tracks: [], clips: [] },
    }));
  });

  it("maps append-service version conflicts to null", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: "version_conflict",
      detail: "timeline config_version mismatch: expected 4, found 6",
    }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;

    const nextVersion = await saveTimelineConfigVersioned(
      {} as SupabaseAdmin,
      "timeline-1",
      4,
      { tracks: [], clips: [] },
    );

    expect(nextVersion).toBeNull();
  });

  it("retries connection resets before succeeding", async () => {
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new TypeError("connection reset by peer"))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        config_version: 3,
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    const sleepSpy = vi.spyOn(globalThis, "setTimeout").mockImplementation(((fn: TimerHandler) => {
      if (typeof fn === "function") {
        fn();
      }
      return 0 as unknown as number;
    }) as typeof setTimeout);

    const nextVersion = await saveTimelineConfigVersioned(
      {} as SupabaseAdmin,
      "timeline-1",
      2,
      { tracks: [], clips: [] },
      1,
    );

    expect(nextVersion).toBe(3);
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    expect(sleepSpy).toHaveBeenCalledTimes(1);
  });

  it("throws on non-409 append service errors after retries are exhausted", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: "internal_error",
      detail: "catastrophic failure",
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;

    await expect(
      saveTimelineConfigVersioned(
        {} as SupabaseAdmin,
        "timeline-1",
        7,
        { tracks: [], clips: [] },
        1,
      ),
    ).rejects.toThrow("Failed to save timeline config");
  });

  it("sends no TS-computed event-log fields in the append payload", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      config_version: 8,
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;

    await saveTimelineConfigVersioned(
      {} as SupabaseAdmin,
      "timeline-1",
      7,
      { tracks: [], clips: [] },
    );

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const payload = JSON.parse(String(init?.body));
    // The agent's save path must not compute event-log fields — that is the
    // Python append service's exclusive job.  Verify the payload omits them.
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
  });
});

describe("appendTimelineConfigViaService", () => {
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
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    globalThis.fetch = originalFetch;
    if (originalDeno) {
      vi.stubGlobal("Deno", originalDeno);
    }
  });

  it("posts config+registry saves to the append service", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      config_version: 5,
      inserted_event_ids: ["evt-1", "evt-2"],
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;

    const assetRegistry = {
      assets: {
        "asset-video": { file: "video.mp4", duration: 12 },
      },
    };

    const configVersion = await appendTimelineConfigViaService({
      timelineId: "timeline-1",
      expectedVersion: 4,
      config: { tracks: [], clips: [] },
      assetRegistry,
      actor: { type: "agent", id: "ai-timeline-agent" },
      source: "editor_save",
    });

    expect(configVersion).toBe(5);
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    const payload = JSON.parse(String(init?.body));
    expect(payload).toEqual(expect.objectContaining({
      expected_version: 4,
      config: { tracks: [], clips: [] },
      asset_registry: assetRegistry,
      actor: { type: "agent", id: "ai-timeline-agent" },
      source: "editor_save",
    }));
    // Config+registry payload must still omit event-log fields.
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
  });

  it("maps append-service version conflicts to a thrown ReighAppendServiceError", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: "version_conflict",
      detail: "timeline config_version mismatch: expected 4, found 6",
    }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    })) as typeof fetch;

    await expect(
      appendTimelineConfigViaService({
        timelineId: "timeline-1",
        expectedVersion: 4,
        config: { tracks: [], clips: [] },
        actor: { type: "agent", id: "ai-timeline-agent" },
        source: "editor_save",
      }),
    ).rejects.toThrow("append service failed");
  });
});

/*
 * OPERATIONAL NOTE — Production Realtime smoke
 *
 * Realtime (Supabase's Postgres → WebSocket broadcast) is configured to
 * stream changes on `public.timelines`.  When the append service updates a
 * materialized `timelines` row (config + config_version + asset_registry)
 * the Realtime channel delivers the new row state to connected browser
 * clients.
 *
 * Realtime correctness is verified via a manual smoke procedure, not a
 * blocking automated test, because it requires a live Supabase project,
 * an active WebSocket connection, and a non-trivial timing window for
 * delivery confirmation.  The procedure:
 *   1. Open the Reigh video editor (browser).
 *   2. Save a timeline change.
 *   3. Confirm the timeline list re-renders with the updated config_version.
 *   4. Open a second browser tab — confirm it receives the update via
 *      the Realtime subscription without a manual refresh.
 *
 * This note exists to document the expected behavior and the manual-
 * verification-only posture; it does not represent missing coverage.
 */
describe("loadTimelineState", () => {
  const timelineId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
  const projectId = "pppppppp-qqqq-rrrr-ssss-tttttttttttt";

  function makeSupabaseAdmin(overrides: {
    timelineData?: Record<string, unknown> | null;
    timelineError?: { message: string } | null;
    shotsData?: Array<Record<string, unknown>> | null;
    shotsError?: { message: string } | null;
  } = {}) {
    const maybeSingle = vi.fn().mockResolvedValue({
      data: overrides.timelineData,
      error: overrides.timelineError ?? null,
    });
    const timelineEq = vi.fn().mockReturnValue({ maybeSingle });
    const timelineSelect = vi.fn().mockReturnValue({ eq: timelineEq });

    const shotsIn = vi.fn().mockResolvedValue({
      data: overrides.shotsData,
      error: overrides.shotsError ?? null,
    });
    const shotsSelect = vi.fn().mockReturnValue({ in: shotsIn });

    const from = vi.fn((table: string) => {
      if (table === "timelines") {
        return { select: timelineSelect };
      }
      if (table === "shots") {
        return { select: shotsSelect };
      }
      return { select: vi.fn() };
    });

    return {
      supabaseAdmin: { from } as unknown as SupabaseAdmin,
      mocks: { from, timelineSelect, timelineEq, maybeSingle, shotsSelect, shotsIn },
    };
  }

  function buildTimelineConfig() {
    return {
      output: { resolution: "1920x1080", fps: 30, file: "timeline.mp4" },
      tracks: [{ id: "V1", kind: "visual" as const, label: "V1" }],
      clips: [],
    };
  }

  it("reads materialized timelines.config and returns a deserialized TimelineState", async () => {
    const config = buildTimelineConfig();
    const assetRegistry = { assets: { "asset-1": { file: "clips/demo.mp4" } } };
    const row = {
      config,
      config_version: 7,
      asset_registry: assetRegistry,
      project_id: projectId,
    };
    const { supabaseAdmin, mocks } = makeSupabaseAdmin({ timelineData: row });

    const state: TimelineState = await loadTimelineState(supabaseAdmin, timelineId);

    // Verify the timeline select was called correctly
    expect(mocks.from).toHaveBeenCalledWith("timelines");
    expect(mocks.timelineSelect).toHaveBeenCalledWith("config, config_version, asset_registry, project_id");
    expect(mocks.timelineEq).toHaveBeenCalledWith("id", timelineId);

    // Verify the returned state deserializes materialized config
    expect(state.config).toEqual(config);
    expect(state.configVersion).toBe(7);
    expect(state.registry).toEqual(assetRegistry);
    expect(state.projectId).toBe(projectId);
  });

  it("preserves config_version from the materialized row", async () => {
    const config = buildTimelineConfig();
    const row = {
      config,
      config_version: 42,
      asset_registry: { assets: {} },
      project_id: projectId,
    };
    const { supabaseAdmin } = makeSupabaseAdmin({ timelineData: row });

    const state = await loadTimelineState(supabaseAdmin, timelineId);

    expect(state.configVersion).toBe(42);
    expect(state.config).toEqual(config);
  });

  it("returns empty shotNamesById when there are no pinned shot groups", async () => {
    const config = buildTimelineConfig();
    const row = {
      config,
      config_version: 1,
      asset_registry: { assets: {} },
      project_id: projectId,
    };
    const { supabaseAdmin } = makeSupabaseAdmin({ timelineData: row });

    const state = await loadTimelineState(supabaseAdmin, timelineId);

    expect(state.shotNamesById).toEqual({});
  });

  it("loads shot names when config has pinnedShotGroups with clipIds", async () => {
    // pinnedShotGroups entries need trackId + clipIds for canonicalizeTimelinePair.
    // We pair them with actual clips so repairShotGroupContiguity doesn't crash.
    const clips = [
      { id: "clip-1", at: 0, track: "V1", clipType: "hold" as const, hold: 2 },
      { id: "clip-2", at: 50, track: "V1", clipType: "hold" as const, hold: 2 },
    ];
    const config = {
      ...buildTimelineConfig(),
      clips,
      pinnedShotGroups: [
        { shotId: "shot-aaa", trackId: "V1", clipIds: ["clip-1"] },
        { shotId: "shot-bbb", trackId: "V1", clipIds: ["clip-2"] },
      ],
    };
    const row = {
      config,
      config_version: 3,
      asset_registry: { assets: {} },
      project_id: projectId,
    };
    const shotsData = [
      { id: "shot-aaa", name: "Alpha Shot" },
      { id: "shot-bbb", name: "Bravo Shot" },
    ];
    const { supabaseAdmin, mocks } = makeSupabaseAdmin({ timelineData: row, shotsData });

    const state = await loadTimelineState(supabaseAdmin, timelineId);

    // Verify shots query was called
    expect(mocks.from).toHaveBeenCalledWith("shots");
    expect(mocks.shotsSelect).toHaveBeenCalledWith("id, name");
    expect(mocks.shotsIn).toHaveBeenCalledWith("id", ["shot-aaa", "shot-bbb"]);

    expect(state.shotNamesById).toEqual({
      "shot-aaa": "Alpha Shot",
      "shot-bbb": "Bravo Shot",
    });
  });

  it("throws when timeline is not found", async () => {
    const { supabaseAdmin } = makeSupabaseAdmin({ timelineData: null });

    await expect(
      loadTimelineState(supabaseAdmin, timelineId),
    ).rejects.toThrow("Timeline not found");
  });

  it("throws when the Supabase query fails", async () => {
    const { supabaseAdmin } = makeSupabaseAdmin({
      timelineData: null,
      timelineError: { message: "connection refused" },
    });

    await expect(
      loadTimelineState(supabaseAdmin, timelineId),
    ).rejects.toThrow("Failed to load timeline");
  });

  it("canonicalizes the config+registry pair", async () => {
    // canonicalizeTimelinePair normalizes config against registry.
    // Provide a config with a media clip referencing an asset and
    // an asset_registry that supplies duration — the canonicalized
    // config should inherit the asset's duration if needed.
    const config = {
      ...buildTimelineConfig(),
      clips: [
        { id: "clip-1", at: 0, track: "V1", clipType: "media" as const, asset: "asset-video" },
      ],
    };
    const assetRegistry = {
      assets: {
        "asset-video": { file: "video.mp4", duration: 12 },
      },
    };
    const row = {
      config,
      config_version: 5,
      asset_registry: assetRegistry,
      project_id: projectId,
    };
    const { supabaseAdmin } = makeSupabaseAdmin({ timelineData: row });

    const state = await loadTimelineState(supabaseAdmin, timelineId);

    // The canonicalized config should still be a valid TimelineConfig
    expect(state.config).toBeDefined();
    expect(state.config.clips).toHaveLength(1);
    expect(state.registry).toEqual(assetRegistry);
  });
});
