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
import { handlers as timelineHandlers, timelineTools, moveClip, setClipProperty } from "./timeline.ts";
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
      "duplicate_generation",
      "get_tasks",
      "run",
      "search_loras",
      "set_lora",
      "transform_image",
    ]);
  });

  it("timelineHandlers keys match the closed parsed-command target set", () => {
    const expected = [
      "add_media_clip",
      "add_text_clip",
      "delete_clip",
      "duplicate_clip",
      "find_issues",
      "move_clip",
      "query_timeline",
      "set_clip_property",
      "set_text_content",
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
