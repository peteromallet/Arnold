// Regression tests for paneLooksReadyForUserMessage (megaplan patch P16).
//
// Claude Code >=2.1.x renders the composer box and then pads the rest of the
// pane height with blank lines, so the visible `❯` prompt can sit ABOVE many
// trailing blank rows. A fixed `lines.slice(-12)` then only sees blank tail
// rows and never matches, so Shannon's readiness probe times out forever
// ("Timed out waiting for Claude prompt"). The fix trims trailing blank lines
// before inspecting the meaningful tail.
//
// Run: bun test megaplan/vendor/shannon/pane_ready.test.ts
import { expect, test } from "bun:test";
import { paneLooksReadyForUserMessage } from "./index.ts";

const BORDER = "─".repeat(80);

test("ready prompt buried above trailing blank lines is detected (P16)", () => {
  const pane = [
    " ▐▛███▜▌   Claude Code v2.1.161",
    "▝▜█████▛▘  Opus 4.7 with high effort · Claude Max",
    "  ▘▘ ▝▝    ~/Documents/.megaplan-worktrees/agent-edit-native",
    "",
    "",
    BORDER,
    // Note: Claude renders a non-breaking space (U+00A0) after the marker.
    "❯ Try \"create a util logging.py that...\"",
    BORDER,
    "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents",
    ...Array(14).fill(""),
  ].join("\n");
  expect(paneLooksReadyForUserMessage(pane)).toBe(true);
});

test("non-breaking space after marker still counts as ready", () => {
  const pane = ["❯ Try \"edit workflow.py to...\"", "", "", ""].join("\n");
  expect(paneLooksReadyForUserMessage(pane)).toBe(true);
});

test("tight pane with no trailing blanks stays ready", () => {
  const pane = [BORDER, "❯ Try \"how does session.py work?\"", BORDER, "  ⏵⏵ bypass permissions on"].join("\n");
  expect(paneLooksReadyForUserMessage(pane)).toBe(true);
});

test("legacy bare prompt marker at end of line stays ready", () => {
  expect(paneLooksReadyForUserMessage("some output\n│ ❯ \n")).toBe(true);
  expect(paneLooksReadyForUserMessage("some output\n❯\n\n")).toBe(true);
});

test("booting pane without a composer prompt is not ready", () => {
  const pane = [" ▐▛███▜▌   Claude Code v2.1.161", "loading...", "", ""].join("\n");
  expect(paneLooksReadyForUserMessage(pane)).toBe(false);
});

test("empty pane is not ready", () => {
  expect(paneLooksReadyForUserMessage("\n\n\n\n")).toBe(false);
});
