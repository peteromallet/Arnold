// Regression tests for shouldScrubEnvKeyBeforeLaunch (megaplan patch P17).
//
// claude >=2.1.170 treats CLAUDECODE / CLAUDE_CODE_* in its environment as a
// nested-session marker and STOPS persisting the interactive conversation
// transcript to the top-level <sessionId>.jsonl (only an {"type":"ai-title"}
// row is written). Shannon polls that file for the submitted prompt + reply,
// never finds them, and the turn dies instantly with "Timed out waiting for
// Claude transcript" / no llm_call_start. When megaplan is launched from
// inside a Claude Code session (the common autonomous case), the tmux server
// inherits those markers, so the spawned interactive claude must have them
// stripped via `env -u`.
//
// Run: bun test megaplan/vendor/shannon/env_scrub.test.ts
import { expect, test } from "bun:test";
import { shouldScrubEnvKeyBeforeLaunch } from "./index.ts";

test("scrubs the nested-Claude-session markers (P17)", () => {
  expect(shouldScrubEnvKeyBeforeLaunch("CLAUDECODE")).toBe(true);
  expect(shouldScrubEnvKeyBeforeLaunch("CLAUDE_CODE_ENTRYPOINT")).toBe(true);
  expect(shouldScrubEnvKeyBeforeLaunch("CLAUDE_CODE_SESSION_ID")).toBe(true);
  expect(shouldScrubEnvKeyBeforeLaunch("CLAUDE_CODE_CHILD_SESSION")).toBe(true);
  expect(shouldScrubEnvKeyBeforeLaunch("CLAUDE_CODE_EXECPATH")).toBe(true);
});

test("still scrubs the existing megaplan/shannon control vars", () => {
  expect(shouldScrubEnvKeyBeforeLaunch("MEGAPLAN_SHANNON_MAX_CONCURRENT")).toBe(true);
  expect(shouldScrubEnvKeyBeforeLaunch("SHANNON_EMIT_METADATA")).toBe(true);
});

test("keeps deliberate config knobs and isolation vars", () => {
  // shannon.py sets this as a real output-budget knob, not a nesting marker.
  expect(shouldScrubEnvKeyBeforeLaunch("CLAUDE_CODE_MAX_OUTPUT_TOKENS")).toBe(false);
  // CLAUDE_CONFIG_DIR is re-injected explicitly; never blanket-scrubbed here.
  expect(shouldScrubEnvKeyBeforeLaunch("CLAUDE_CONFIG_DIR")).toBe(false);
  expect(shouldScrubEnvKeyBeforeLaunch("PATH")).toBe(false);
  expect(shouldScrubEnvKeyBeforeLaunch("HOME")).toBe(false);
});
