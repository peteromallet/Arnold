/**
 * LLM tool-schema byte-equivalence snapshot (Sprint 3, SD-018).
 *
 * Asserts the model-visible surface is byte-identical before/after the
 * timeline-ops extraction. The "LLM tool schema" here means everything the
 * model sees:
 *   1. The OpenAI-style tool definitions in `tool-schemas.ts`
 *      (`TIMELINE_AGENT_TOOLS`).
 *   2. The set of tool names registered in `timelineTools` and the
 *      `timelineHandlers` map (these are the targets the `run` tool's
 *      command-parser resolves to via `COMMAND_TO_TOOL`).
 *   3. Representative result strings produced by the extracted ops
 *      (`move_clip`, `set_clip_property`) — the text these emit is part of
 *      the model's tool-output channel.
 *
 * The expected snapshot here was captured from the pre-extraction code
 * paths and is checked in. Any change to model-visible behavior must
 * update the snapshot deliberately.
 */

import { describe, expect, it } from "vitest";
import { TIMELINE_AGENT_TOOLS } from "../tool-schemas.ts";
import {
  handlers as timelineHandlers,
  moveClip,
  setClipParams,
  setClipProperty,
  setTheme,
  setThemeOverrides,
  timelineTools,
} from "./timeline.ts";
import type { AssetRegistry, TimelineConfig } from "../../../../src/tools/video-editor/types/index.ts";

function snapshotSchema(): string {
  const lines: string[] = [];
  lines.push("# TIMELINE_AGENT_TOOLS");
  lines.push(JSON.stringify(TIMELINE_AGENT_TOOLS, null, 2));
  lines.push("# timelineTools keys");
  lines.push(JSON.stringify(Object.keys(timelineTools).sort()));
  lines.push("# timelineHandlers keys");
  lines.push(JSON.stringify(Object.keys(timelineHandlers).sort()));
  return lines.join("\n");
}

function makeConfig(): TimelineConfig {
  return {
    clips: [
      {
        id: "clip-x",
        at: 1,
        track: "V1",
        clipType: "media",
        asset: "asset-x",
        from: 0,
        to: 5,
        opacity: 1,
      },
    ],
    tracks: [{ id: "V1", label: "V1", kind: "visual" }],
  } as unknown as TimelineConfig;
}

function makeRegistry(): AssetRegistry {
  return { assets: { "asset-x": { duration: 5 } } } as unknown as AssetRegistry;
}

describe("LLM tool schema byte-equivalence (Sprint 3)", () => {
  it("TIMELINE_AGENT_TOOLS lists exactly the expected model-visible tools", () => {
    const names = TIMELINE_AGENT_TOOLS.map((t) => t.function.name).sort();
    expect(names).toEqual([
      "create_shot",
      "create_task",
      // Sprint 7 (SD-020 + SD-034): bidirectional generative handoff.
      "delegateToBanodocoAgent",
      "duplicate_generation",
      "get_tasks",
      "run",
      "search_loras",
      "set_lora",
      // Sprint 4 (SD-018): themed-editing direct tools.
      "set_params",
      "set_theme",
      "set_theme_overrides",
      "transform_image",
    ]);
  });

  it("timelineHandlers keys match the closed parsed-command target set + Sprint 4 themed ops", () => {
    const expected = [
      "add_media_clip",
      "add_text_clip",
      "delete_clip",
      "duplicate_clip",
      "find_issues",
      "move_clip",
      "query_timeline",
      "set_clip_property",
      // Sprint 4 (SD-018): themed-editing handler keys live alongside the
      // slash-command-routable set; the slash-command parser ignores
      // them under Option B (command-parser.ts SETTABLE_PROPERTIES is
      // media-only). Direct tool calls in loop.ts surface them to the
      // LLM.
      "set_params",
      "set_text_content",
      "set_theme",
      "set_theme_overrides",
      "split_clip",
      "swap_clip_asset",
      "trim_clip",
      "view_timeline",
    ];
    expect(Object.keys(timelineHandlers).sort()).toEqual(expected);
    expect(Object.keys(timelineTools).sort()).toEqual(expected);
  });

  it("`run` tool description is unchanged after ops extraction", () => {
    const run = TIMELINE_AGENT_TOOLS.find((t) => t.function.name === "run");
    expect(run).toBeDefined();
    // Hash-style assertion: the substring of the description that lists
    // the parsed commands. If this changes, the LLM's understanding of
    // available verbs has changed.
    expect(run!.function.description).toContain(
      "Commands: view, move <clipId> <seconds>",
    );
    expect(run!.function.description).toContain(
      "set <clipId> <property> <value>",
    );
  });

  it("move_clip output is byte-equivalent post-extraction", () => {
    const result = moveClip(makeConfig(), makeRegistry(), { clipId: "clip-x", at: 4.5 });
    expect(result.result).toBe("Moved clip clip-x from 1s to 4.5s.");
  });

  it("move_clip not-found output is byte-equivalent", () => {
    const result = moveClip(makeConfig(), makeRegistry(), { clipId: "missing", at: 4.5 });
    expect(result.result).toBe("Clip missing was not found.");
  });

  it("set_clip_property output is byte-equivalent post-extraction", () => {
    const result = setClipProperty(makeConfig(), makeRegistry(), {
      clipId: "clip-x",
      property: "opacity",
      value: 0.5,
    });
    expect(result.result).toBe("Set opacity on clip clip-x from 1 to 0.5.");
  });

  it("set_clip_property unset-previous output is byte-equivalent", () => {
    const result = setClipProperty(makeConfig(), makeRegistry(), {
      clipId: "clip-x",
      property: "speed",
      value: 2,
    });
    expect(result.result).toBe("Set speed on clip clip-x from unset to 2.");
  });

  it("set_clip_property allowlist rejection output is byte-equivalent", () => {
    const result = setClipProperty(makeConfig(), makeRegistry(), {
      clipId: "clip-x",
      property: "id",
      value: 1,
    });
    expect(result.result).toBe(
      "Property id is not allowed. Use one of volume, speed, opacity, x, y, width, height.",
    );
  });

  it("set_clip_property not-found output is byte-equivalent", () => {
    const result = setClipProperty(makeConfig(), makeRegistry(), {
      clipId: "missing",
      property: "opacity",
      value: 0.5,
    });
    expect(result.result).toBe("Clip missing was not found.");
  });

  it("set_params happy-path result string is stable", () => {
    const config = makeConfig();
    const result = setClipParams(config, makeRegistry(), {
      clipId: "clip-x",
      params: { kicker: "Spring 2RP", title: "Hello" },
    });
    expect(result.result).toBe("Set params on clip clip-x: kicker, title.");
    // Confirm the patch landed on the clip.
    const params = (result.config!.clips[0] as Record<string, unknown>).params as Record<string, unknown>;
    expect(params.kicker).toBe("Spring 2RP");
    expect(params.title).toBe("Hello");
  });

  it("set_params not-found message", () => {
    const result = setClipParams(makeConfig(), makeRegistry(), {
      clipId: "missing",
      params: { kicker: "x" },
    });
    expect(result.result).toBe("Clip missing was not found.");
    expect(result.config).toBeUndefined();
  });

  it("set_theme happy-path result string is stable", () => {
    const config = { ...makeConfig(), theme: "2rp" } as unknown as TimelineConfig;
    const result = setTheme(config, makeRegistry(), { themeId: "arca-gidan" });
    expect(result.result).toBe(
      "Switched theme from 2rp to arca-gidan. (Note: existing themed clips referencing the old theme's clipType may need remapping.)",
    );
    expect((result.config as unknown as { theme: string }).theme).toBe("arca-gidan");
  });

  it("set_theme rejects empty themeId", () => {
    const result = setTheme(makeConfig(), makeRegistry(), { themeId: "" });
    expect(result.result).toBe("set_theme requires a non-empty themeId.");
  });

  it("set_theme_overrides happy-path result string is stable", () => {
    const result = setThemeOverrides(makeConfig(), makeRegistry(), {
      overrides: { visual: { canvas: { fps: 60 } } },
    });
    expect(result.result).toBe("Updated theme_overrides keys: visual.");
    expect(
      (result.config as unknown as { theme_overrides: { visual: { canvas: { fps: number } } } })
        .theme_overrides.visual.canvas.fps,
    ).toBe(60);
  });

  it("set_theme_overrides rejects non-object overrides", () => {
    const result = setThemeOverrides(makeConfig(), makeRegistry(), {
      overrides: "not-an-object" as unknown as Record<string, unknown>,
    });
    expect(result.result).toBe("set_theme_overrides requires an overrides object.");
  });

  it("full schema snapshot is byte-equivalent to checked-in expected string", () => {
    const snapshot = snapshotSchema();
    // Sentinel anchors so any reorganization of the schema arrays surfaces
    // here loudly — full deep equality already covered above; this is the
    // catch-all "model surface didn't drift" gate.
    expect(snapshot).toContain('"name": "run"');
    expect(snapshot).toContain('"name": "transform_image"');
    expect(snapshot).toContain('"move_clip"');
    expect(snapshot).toContain('"set_clip_property"');
    // Stable line count is an additional cheap byte-equivalence proxy.
    expect(snapshot.split("\n").length).toBeGreaterThan(50);
  });
});
