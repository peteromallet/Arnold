import { describe, expect, it } from "vitest";
import { parseCommand } from "./command-parser.ts";

describe("parseCommand", () => {
  it("parses every supported canonical command family", () => {
    const cases = [
      ["view", "view"],
      ["find-issues", "find-issues"],
      ["move clip-1 12", "move"],
      ["trim clip-1 --from 1 --duration 2", "trim"],
      ["delete clip-1", "delete"],
      ["set clip-1 opacity 0.5", "set"],
      ['add-text V1 2 3 "hello world"', "add-text"],
      ["add-media V1 2.5 gen-123 https://example.com/img.png", "add-media"],
      ['set-text clip-1 "updated text"', "set-text"],
      ["duplicate clip-1 2", "duplicate"],
      ["repeat 3 add-text V1 0.2 hi --start 1 --gap 0.5", "repeat"],
      ['generate "wide shot" --count 2', "generate"],
    ] as const;

    for (const [input, expectedType] of cases) {
      expect(parseCommand(input).type).toBe(expectedType);
    }
  });

  it("normalizes aliases through the dispatch map", () => {
    expect(parseCommand("rm clip-1")).toEqual({ type: "delete", clipId: "clip-1" });
    expect(parseCommand("issues")).toEqual({ type: "find-issues" });
    expect(parseCommand('gen "sunrise" --count 2')).toEqual({
      type: "generate",
      prompt: "sunrise",
      count: 2,
    });
    expect(parseCommand('settext clip-1 "new text"')).toEqual({
      type: "set-text",
      clipId: "clip-1",
      text: "new text",
    });
  });

  it("parses add-media with default image type", () => {
    expect(parseCommand("add-media V1 2.5 gen-123 https://example.com/img.png")).toEqual({
      type: "add-media",
      track: "V1",
      at: 2.5,
      generationId: "gen-123",
      url: "https://example.com/img.png",
      mediaType: "image",
    });
  });

  it("parses add-media with explicit video type", () => {
    expect(parseCommand("add-media V2 0 gen-456 https://example.com/vid.mp4 --type video")).toEqual({
      type: "add-media",
      track: "V2",
      at: 0,
      generationId: "gen-456",
      url: "https://example.com/vid.mp4",
      mediaType: "video",
    });
  });

  it("parses add-media via addmedia alias", () => {
    expect(parseCommand("addmedia V1 1 gen-789 https://example.com/x.png").type).toBe("add-media");
  });

  it("rejects add-media with missing args", () => {
    expect(parseCommand("add-media V1 2.5").type).toBe("error");
  });

  it("rejects add-media with invalid --type", () => {
    expect(parseCommand("add-media V1 0 gen-1 https://x.png --type audio").type).toBe("error");
  });

  it("keeps the unknown-command error path", () => {
    expect(parseCommand("unknown command")).toEqual({
      type: "error",
      message: 'Unknown command "unknown". Available: view, move, split, trim, delete, set, set-text, add-text, add-media, swap, duplicate, query, undo, repeat, find-issues. For generation requests, use create_task (legacy generate still works).',
    });
  });
});
