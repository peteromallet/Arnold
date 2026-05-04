import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  loadTimelineState: vi.fn(),
  saveTimelineConfigVersioned: vi.fn(),
  addMediaClip: vi.fn(),
}));

vi.mock("../ai-timeline-agent/db.ts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../ai-timeline-agent/db.ts")>();
  return {
    ...actual,
    loadTimelineState: (...args: unknown[]) => mocks.loadTimelineState(...args),
    saveTimelineConfigVersioned: (...args: unknown[]) => mocks.saveTimelineConfigVersioned(...args),
  };
});

vi.mock("../ai-timeline-agent/tools/timeline.ts", () => ({
  addMediaClip: (...args: unknown[]) => mocks.addMediaClip(...args),
}));

import { executePlacement } from "./placement.ts";

function createSupabaseAdmin() {
  const maybeSingle = vi.fn().mockResolvedValue({ error: null });
  const rpc = vi.fn().mockReturnValue({ maybeSingle });
  return { rpc, maybeSingle };
}

describe("complete_task/placement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.saveTimelineConfigVersioned.mockResolvedValue(2);
    mocks.addMediaClip.mockReturnValue({
      config: {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [{ id: "clip-added", track: "V1", at: 10.5, asset: "asset-added", clipType: "hold", hold: 5 }],
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual 1' }],
      },
      result: "Added media clip clip-added on track V1 at 10.5s.",
    });
  });

  it("inserts after the anchor clip end on the preferred track and registers the exact variant", async () => {
    const supabaseAdmin = createSupabaseAdmin();
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        clips: [{ id: "clip-source-1", at: 8, track: "V1", clipType: "hold", hold: 2.5 }],
        tracks: [{ id: "V1", kind: "visual", label: "Visual 1" }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: "project-1",
      shotNamesById: {},
    });

    const result = await executePlacement(
      supabaseAdmin as never,
      {
        timeline_id: "timeline-1",
        anchor_clip_id: "clip-source-1",
        anchor_generation_id: "gen-source-1",
        anchor_variant_id: "variant-source-1",
        relation: "after",
        preferred_track_id: "V1",
        fallback_at: 22.25,
        fallback_track_id: "V1",
      },
      {
        generation_id: "gen-placed-1",
        variant_id: "variant-placed-1",
        location: "https://cdn.example.com/tasks/task-1/out.png",
        thumbnail_url: "https://cdn.example.com/tasks/task-1/thumb.png",
        media_type: "image",
        created_as: "variant",
      },
    );

    expect(result).toEqual(expect.objectContaining({
      status: "placed",
      timelineId: "timeline-1",
      usedFallback: false,
      configVersion: 2,
    }));
    expect(supabaseAdmin.rpc).toHaveBeenCalledWith("upsert_asset_registry_entry", expect.objectContaining({
      p_timeline_id: "timeline-1",
      p_entry: expect.objectContaining({
        file: "https://cdn.example.com/tasks/task-1/out.png",
        generationId: "gen-placed-1",
        variantId: "variant-placed-1",
        thumbnailUrl: "https://cdn.example.com/tasks/task-1/thumb.png",
      }),
    }));

    const rpcArgs = supabaseAdmin.rpc.mock.calls[0]?.[1] as { p_asset_id: string };
    expect(mocks.addMediaClip).toHaveBeenCalledWith(
      {
        clips: [{ id: "clip-source-1", at: 8, track: "V1", clipType: "hold", hold: 2.5 }],
        tracks: [{ id: "V1", kind: "visual", label: "Visual 1" }],
      },
      expect.objectContaining({
        assets: expect.objectContaining({
          [rpcArgs.p_asset_id]: expect.objectContaining({
            generationId: "gen-placed-1",
            variantId: "variant-placed-1",
          }),
        }),
      }),
      {
        track: "V1",
        at: 10.5,
        assetKey: rpcArgs.p_asset_id,
        mediaType: "image",
      },
    );
    expect(mocks.saveTimelineConfigVersioned).toHaveBeenCalledWith(
      supabaseAdmin,
      "timeline-1",
      1,
      expect.objectContaining({
        clips: expect.any(Array),
      }),
    );
  });

  it("falls back to the stored coordinates when the anchor clip is gone but the fallback track remains", async () => {
    const supabaseAdmin = createSupabaseAdmin();
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        clips: [],
        tracks: [{ id: "V1", kind: "visual", label: "Visual 1" }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: "project-1",
      shotNamesById: {},
    });

    const result = await executePlacement(
      supabaseAdmin as never,
      {
        timeline_id: "timeline-1",
        anchor_clip_id: "clip-source-1",
        relation: "after",
        preferred_track_id: "V1",
        fallback_at: 22.25,
        fallback_track_id: "V1",
      },
      {
        generation_id: "gen-placed-1",
        variant_id: "variant-placed-1",
        location: "https://cdn.example.com/tasks/task-1/out.png",
        media_type: "image",
        created_as: "variant",
      },
    );

    expect(result).toEqual(expect.objectContaining({
      status: "placed",
      usedFallback: true,
    }));

    const rpcArgs = supabaseAdmin.rpc.mock.calls[0]?.[1] as { p_asset_id: string };
    expect(mocks.addMediaClip).toHaveBeenCalledWith(
      {
        clips: [],
        tracks: [{ id: "V1", kind: "visual", label: "Visual 1" }],
      },
      expect.anything(),
      {
        track: "V1",
        at: 22.25,
        assetKey: rpcArgs.p_asset_id,
        mediaType: "image",
      },
    );
  });

  it("returns a degraded follow-up issue without mutating the timeline when the anchor and fallback are both gone", async () => {
    const supabaseAdmin = createSupabaseAdmin();
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        clips: [],
        tracks: [{ id: "V2", kind: "visual", label: "Visual 2" }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: "project-1",
      shotNamesById: {},
    });

    await expect(executePlacement(
      supabaseAdmin as never,
      {
        timeline_id: "timeline-1",
        anchor_clip_id: "clip-source-1",
        relation: "after",
        preferred_track_id: "V1",
        fallback_at: 22.25,
        fallback_track_id: "V1",
      },
      {
        generation_id: "gen-placed-1",
        variant_id: "variant-placed-1",
        location: "https://cdn.example.com/tasks/task-1/out.png",
        media_type: "image",
        created_as: "variant",
      },
    )).resolves.toEqual({
      status: "skipped",
      issue: {
        step: "timeline_placement",
        code: "placement_anchor_and_fallback_missing",
        message: "Skipped placement because anchor clip clip-source-1 was missing and fallback track V1 no longer exists on timeline timeline-1.",
      },
    });

    expect(supabaseAdmin.rpc).not.toHaveBeenCalled();
    expect(mocks.addMediaClip).not.toHaveBeenCalled();
    expect(mocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it("reconciles stale pinned shot group metadata before persisting the split config write", async () => {
    const supabaseAdmin = createSupabaseAdmin();
    mocks.loadTimelineState.mockResolvedValue({
      config: {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [{ id: "clip-source-1", at: 8, track: "V1", clipType: "hold", hold: 2.5 }],
        tracks: [{ id: "V1", kind: "visual", label: "Visual 1" }],
        pinnedShotGroups: [{
          shotId: 'shot-1',
          trackId: 'stale-track',
          clipIds: ['missing-clip', 'clip-source-1'],
          mode: 'images',
        }],
      },
      configVersion: 1,
      registry: { assets: {} },
      projectId: "project-1",
      shotNamesById: {},
    });
    mocks.addMediaClip.mockReturnValue({
      config: {
        output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
        clips: [
          { id: "clip-source-1", at: 8, track: "V1", clipType: "hold", hold: 2.5 },
          { id: "clip-added", at: 10.5, track: "V1", clipType: "media", asset: "asset-added" },
        ],
        tracks: [{ id: "V1", kind: "visual", label: "Visual 1" }],
        pinnedShotGroups: [{
          shotId: 'shot-1',
          trackId: 'stale-track',
          clipIds: ['missing-clip', 'clip-source-1'],
          mode: 'images',
        }],
      },
      result: "Added media clip clip-added on track V1 at 10.5s.",
    });

    await executePlacement(
      supabaseAdmin as never,
      {
        timeline_id: "timeline-1",
        anchor_clip_id: "clip-source-1",
        relation: "after",
        preferred_track_id: "V1",
        fallback_at: 22.25,
        fallback_track_id: "V1",
      },
      {
        generation_id: "gen-placed-1",
        variant_id: "variant-placed-1",
        location: "https://cdn.example.com/tasks/task-1/out.png",
        media_type: "image",
        created_as: "variant",
      },
    );

    expect(mocks.saveTimelineConfigVersioned).toHaveBeenCalledWith(
      supabaseAdmin,
      'timeline-1',
      1,
      expect.objectContaining({
        pinnedShotGroups: [{
          shotId: 'shot-1',
          trackId: 'V1',
          clipIds: ['clip-source-1'],
          mode: 'images',
        }],
      }),
    );
  });
});
