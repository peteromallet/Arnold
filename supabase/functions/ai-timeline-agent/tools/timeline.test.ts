import { beforeEach, describe, expect, it, vi } from "vitest";
const registryMocks = vi.hoisted(() => ({
  loadTimelineState: vi.fn(),
  saveTimelineConfigVersioned: vi.fn(),
}));
vi.mock("@banodoco/timeline-ops", () => ({
  moveClip: vi.fn(),
  setClipParams: vi.fn(),
  setClipProperty: vi.fn(),
  setThemeOverrides: vi.fn(),
  setTimelineTheme: vi.fn(),
}));
vi.mock("../db.ts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../db.ts")>();
  return {
    ...actual,
    loadTimelineState: (...args: unknown[]) => registryMocks.loadTimelineState(...args),
    saveTimelineConfigVersioned: (...args: unknown[]) => registryMocks.saveTimelineConfigVersioned(...args),
  };
});
import { executeCommand } from "./registry.ts";
import { addMediaClip, setClipParams, setTheme, swapClipAsset, viewTimeline } from "./timeline.ts";
import { provisionTimelineMedia } from "../../../../src/tools/video-editor/commands/index.ts";
import type { AssetRegistry, TimelineConfig } from "../../../../src/tools/video-editor/types/index.ts";

function makeConfig(tracks: { id: string; label: string; kind: string }[] = []): TimelineConfig {
  return { clips: [], tracks } as unknown as TimelineConfig;
}

function makeRegistry(assets: Record<string, { duration?: number }> = {}): AssetRegistry {
  return { assets } as unknown as AssetRegistry;
}

beforeEach(() => {
  registryMocks.loadTimelineState.mockReset();
  registryMocks.saveTimelineConfigVersioned.mockReset();
});

describe("addMediaClip", () => {
  it("adds an image clip with hold duration and opacity", () => {
    const config = makeConfig([{ id: "V1", label: "V1", kind: "visual" }]);
    const registry = makeRegistry();
    const result = addMediaClip(config, registry, {
      track: "V1",
      at: 5.5,
      assetKey: "asset-abc",
      mediaType: "image",
    });

    expect(result.config).toBeDefined();
    expect(result.result).toContain("Added media clip");
    const clip = result.config!.clips[0];
    expect(clip.track).toBe("V1");
    expect(clip.at).toBe(5.5);
    expect(clip.asset).toBe("asset-abc");
    expect((clip as Record<string, unknown>).clipType).toBe("hold");
    expect((clip as Record<string, unknown>).hold).toBe(5);
    expect((clip as Record<string, unknown>).opacity).toBe(1);
  });

  it("adds a video clip with from/to/speed/volume/opacity", () => {
    const config = makeConfig([{ id: "V1", label: "V1", kind: "visual" }]);
    const registry = makeRegistry({ "asset-vid": { duration: 10 } });
    const result = addMediaClip(config, registry, {
      track: "V1",
      at: 0,
      assetKey: "asset-vid",
      mediaType: "video",
    });

    expect(result.config).toBeDefined();
    const clip = result.config!.clips[0] as Record<string, unknown>;
    expect(clip.clipType).toBe("media");
    expect(clip.from).toBe(0);
    expect(clip.to).toBe(10);
    expect(clip.speed).toBe(1);
    expect(clip.volume).toBe(1);
    expect(clip.opacity).toBe(1);
  });

  it("defaults video duration to 5s when asset has no duration", () => {
    const config = makeConfig([{ id: "V1", label: "V1", kind: "visual" }]);
    const registry = makeRegistry();
    const result = addMediaClip(config, registry, {
      track: "V1",
      at: 0,
      assetKey: "asset-unknown",
      mediaType: "video",
    });

    expect(result.config).toBeDefined();
    expect((result.config!.clips[0] as Record<string, unknown>).to).toBe(5);
  });

  it("rejects unknown track", () => {
    const config = makeConfig([{ id: "V1", label: "V1", kind: "visual" }]);
    const registry = makeRegistry();
    const result = addMediaClip(config, registry, {
      track: "V99",
      at: 0,
      assetKey: "asset-abc",
      mediaType: "image",
    });

    expect(result.config).toBeUndefined();
    expect(result.result).toContain("does not exist");
  });

  it("rejects missing required args", () => {
    const config = makeConfig();
    const registry = makeRegistry();
    const result = addMediaClip(config, registry, {});

    expect(result.config).toBeUndefined();
    expect(result.result).toContain("requires");
  });
});

describe("swapClipAsset", () => {
  it("swaps a clip using a provisioned external-media asset", () => {
    const config = {
      clips: [{
        id: "clip-1",
        at: 0,
        track: "V1",
        asset: "asset-old",
        clipType: "hold",
        hold: 5,
      }],
      tracks: [{ id: "V1", label: "V1", kind: "visual" }],
    } as unknown as TimelineConfig;
    const registry = makeRegistry({
      "asset-old": { type: "image/png" },
    });

    const result = swapClipAsset(config, registry, {
      clipId: "clip-1",
      asset: {
        assetKey: "asset-new",
        mediaType: "video",
        durationSeconds: 8,
        entry: {
          file: "https://example.com/video.mp4",
          type: "video/mp4",
          duration: 8,
        },
        source: "external-media",
      },
    });

    expect(result.config).toBeDefined();
    expect(result.result).toContain("Swapped clip clip-1 to video asset asset-new.");
    expect(result.config!.clips[0]).toMatchObject({
      id: "clip-1",
      asset: "asset-new",
      clipType: "media",
      from: 0,
      to: 8,
      speed: 1,
      volume: 1,
    });
  });
});

describe("provisionTimelineMedia", () => {
  it("normalizes external media through the injected registration host", async () => {
    const asset = await provisionTimelineMedia({
      kind: "external-media",
      url: "https://example.com/video.mp4",
      mediaType: "video",
      generationId: "gen-123",
      durationSeconds: 9,
      thumbnailUrl: "https://example.com/video-thumb.jpg",
    }, {
      getAssetEntry: () => null,
      registerExternalAsset: async (_source, entry) => {
        expect(entry).toMatchObject({
          file: "https://example.com/video.mp4",
          type: "video/mp4",
          duration: 9,
          generationId: "gen-123",
          thumbnailUrl: "https://example.com/video-thumb.jpg",
        });
        return { assetKey: "asset-external" };
      },
    });

    expect(asset).toMatchObject({
      assetKey: "asset-external",
      mediaType: "video",
      durationSeconds: 9,
      source: "external-media",
    });
  });
});

describe("viewTimeline", () => {
  it("includes clip-level shot context and a shot-groups section with resolved names or shot-id fallback", () => {
    const config = {
      output: { file: "out.mp4", fps: 30, resolution: "1920x1080" },
      tracks: [{ id: "V1", label: "V1", kind: "visual" }],
      clips: [
        {
          id: "clip-1",
          asset: "asset-1",
          at: 0,
          track: "V1",
          clipType: "hold",
          hold: 2,
        },
        {
          id: "clip-2",
          asset: "asset-2",
          at: 2,
          track: "V1",
          clipType: "hold",
          hold: 3,
        },
      ],
      pinnedShotGroups: [
        { shotId: "shot-1", trackId: "V1", clipIds: ["clip-1"], mode: "images" },
        { shotId: "shot-2", trackId: "V1", clipIds: ["clip-2"], mode: "video" },
      ],
    } as unknown as TimelineConfig;

    const result = viewTimeline(config, makeRegistry({
      "asset-1": { duration: 2 },
      "asset-2": { duration: 3 },
    }), {
      "shot-1": "Hero Shot",
    });

    expect(result.result).toContain("Clips:");
    expect(result.result).toContain("- id=clip-1 | track=V1 | at=0s | duration=2s | type=hold | asset=asset-1 | shot=Hero Shot | shotId=shot-1");
    expect(result.result).toContain("- id=clip-2 | track=V1 | at=2s | duration=3s | type=hold | asset=asset-2 | shot=shot-2 | shotId=shot-2");
    expect(result.result).toContain("Shot groups:");
    expect(result.result).toContain("- shot=Hero Shot | shotId=shot-1 | trackId=V1 | clipIds=clip-1 | mode=images");
    expect(result.result).toContain("- shot=shot-2 | shotId=shot-2 | trackId=V1 | clipIds=clip-2 | mode=video");
  });
});

describe("themed command availability", () => {
  it("rejects set_params for clips outside the installed sequence families", () => {
    const config = {
      clips: [{
        id: "clip-1",
        at: 0,
        track: "V1",
        clipType: "media",
        asset: "asset-1",
      }],
      tracks: [{ id: "V1", label: "V1", kind: "visual" }],
    } as unknown as TimelineConfig;

    const result = setClipParams(config, makeRegistry(), {
      clipId: "clip-1",
      params: { title: "Hello" },
    });

    expect(result.result).toBe(
      "Clip clip-1 does not support set_params. Installed sequence clip types: image-jump, section-hook, art-card, resource-card, cta-card.",
    );
    expect(result.config).toBeUndefined();
  });

  it("rejects set_theme for themes not installed in this build", () => {
    const result = setTheme(makeConfig(), makeRegistry(), { themeId: "arca-gidan" });
    expect(result.result).toBe("Theme arca-gidan is not installed. Available themes: 2rp.");
    expect(result.config).toBeUndefined();
  });
});

describe("executeCommand", () => {
  it("validates a typed transaction without saving or mutating the timeline", async () => {
    const state = {
      config: {
        clips: [],
        tracks: [{ id: "V1", label: "V1", kind: "visual" }],
      },
      configVersion: 2,
      registry: makeRegistry(),
      projectId: "project-1",
      shotNamesById: {},
    } as unknown as import("../types.ts").TimelineState;
    const supabaseAdmin = {
      rpc: () => ({
        maybeSingle: async () => ({ data: null, error: null }),
      }),
    } as unknown as import("../types.ts").SupabaseAdmin;

    const result = await executeCommand({
      transaction: {
        transactionId: "tx-validate",
        commands: [{
          type: "add-text",
          payload: {
            track: "V1",
            at: 3,
            duration: 2,
            text: "hello",
          },
        }],
      },
      mode: "validate",
    }, state, "timeline-1", supabaseAdmin);

    expect(result.result).toContain("Validated 1/1 command(s).");
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(state.config.clips).toHaveLength(0);
  });

  it("dry-runs a typed add-media transaction without saving", async () => {
    const state = {
      config: makeConfig([{ id: "V1", label: "V1", kind: "visual" }]),
      configVersion: 3,
      registry: makeRegistry(),
      projectId: "project-1",
      shotNamesById: {},
    } as unknown as import("../types.ts").TimelineState;
    const supabaseAdmin = {
      rpc: () => ({
        maybeSingle: async () => ({ data: null, error: null }),
      }),
    } as unknown as import("../types.ts").SupabaseAdmin;

    const result = await executeCommand({
      transaction: {
        transactionId: "tx-dry-run",
        commands: [{
          type: "add-media",
          payload: {
            trackId: "V1",
            at: 1,
            generationId: "gen-1",
            url: "https://example.com/add.png",
            mediaType: "image",
          },
        }],
      },
      mode: "dry_run",
    }, state, "timeline-1", supabaseAdmin);

    expect(result.result).toContain("Dry ran 1/1 command(s).");
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(state.config.clips).toHaveLength(0);
  });

  it("applies a typed transaction batch and saves once", async () => {
    const state = {
      config: makeConfig([{ id: "V1", label: "V1", kind: "visual" }]),
      configVersion: 4,
      registry: makeRegistry(),
      projectId: "project-1",
      shotNamesById: {},
    } as unknown as import("../types.ts").TimelineState;
    const supabaseAdmin = {
      rpc: () => ({
        maybeSingle: async () => ({ data: null, error: null }),
      }),
    } as unknown as import("../types.ts").SupabaseAdmin;
    registryMocks.saveTimelineConfigVersioned.mockResolvedValue(5);

    const result = await executeCommand({
      transaction: {
        transactionId: "tx-apply",
        commands: [
          {
            type: "add-media",
            payload: {
              trackId: "V1",
              at: 0,
              generationId: "gen-1",
              url: "https://example.com/a.png",
              mediaType: "image",
            },
          },
          {
            type: "add-media",
            payload: {
              trackId: "V1",
              at: 6,
              generationId: "gen-2",
              url: "https://example.com/b.png",
              mediaType: "image",
            },
          },
        ],
      },
    }, state, "timeline-1", supabaseAdmin);

    expect(result.result).toContain("Applied 2/2 command(s).");
    expect(registryMocks.saveTimelineConfigVersioned).toHaveBeenCalledTimes(1);
    expect(state.config.clips).toHaveLength(2);
    expect(state.configVersion).toBe(5);
  });

  it("rejects invalid typed batches atomically without saving", async () => {
    const state = {
      config: {
        clips: [],
        tracks: [{ id: "V1", label: "V1", kind: "visual" }],
      },
      configVersion: 6,
      registry: makeRegistry(),
      projectId: "project-1",
      shotNamesById: {},
    } as unknown as import("../types.ts").TimelineState;
    const supabaseAdmin = {
      rpc: () => ({
        maybeSingle: async () => ({ data: null, error: null }),
      }),
    } as unknown as import("../types.ts").SupabaseAdmin;

    const result = await executeCommand({
      transaction: {
        transactionId: "tx-invalid-batch",
        commands: [
          {
            type: "add-text",
            payload: {
              track: "V1",
              at: 2,
              duration: 1.5,
              text: "hello",
            },
          },
          {
            type: "delete",
            payload: {
              clipId: "missing-clip",
            },
          },
        ],
      },
    }, state, "timeline-1", supabaseAdmin);

    expect(result.result).toContain("Clip missing-clip was not found.");
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
    expect(state.config.clips).toHaveLength(0);
    expect(state.configVersion).toBe(6);
  });

  it("keeps repeat as a compatibility adapter and rejects nested add-media", async () => {
    const state = {
      config: makeConfig([{ id: "V1", label: "V1", kind: "visual" }]),
      configVersion: 1,
      registry: makeRegistry(),
      projectId: "project-1",
      shotNamesById: {},
    } as unknown as import("../types.ts").TimelineState;
    const supabaseAdmin = {
      rpc: () => ({
        maybeSingle: async () => ({ data: null, error: null }),
      }),
    } as unknown as import("../types.ts").SupabaseAdmin;

    const result = await executeCommand(
      'repeat 2 add-media V1 0 gen-1 https://example.com/add.png --start 0 --gap 1',
      state,
      "timeline-1",
      supabaseAdmin,
    );

    expect(result.result).toContain("add-media is not supported inside repeat.");
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });

  it("keeps repeat as a compatibility adapter and rejects nested swap", async () => {
    const state = {
      config: {
        clips: [{
          id: "clip-1",
          at: 0,
          track: "V1",
          clipType: "hold",
          hold: 2,
          asset: "asset-1",
        }],
        tracks: [{ id: "V1", label: "V1", kind: "visual" }],
      },
      configVersion: 1,
      registry: makeRegistry({ "asset-1": { duration: 2 } }),
      projectId: "project-1",
      shotNamesById: {},
    } as unknown as import("../types.ts").TimelineState;
    const supabaseAdmin = {
      rpc: () => ({
        maybeSingle: async () => ({ data: null, error: null }),
      }),
    } as unknown as import("../types.ts").SupabaseAdmin;

    const result = await executeCommand(
      "repeat 2 swap clip-1 gen-1 https://example.com/swap.png --start 0 --gap 1",
      state,
      "timeline-1",
      supabaseAdmin,
    );

    expect(result.result).toContain("swap is not supported inside repeat.");
    expect(registryMocks.saveTimelineConfigVersioned).not.toHaveBeenCalled();
  });
});
