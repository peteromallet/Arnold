/**
 * Complex multi-step scenario tests for the timeline agent.
 *
 * These test natural-language requests that combine multiple operations,
 * multi-turn conversations, and compound instructions.
 *
 * Run:
 *   cd reigh-app && npx tsx supabase/functions/_tests/harness/complex-scenarios-test.ts
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { TestHarness } from "./index.ts";
import type { HarnessSnapshot, SnapshotDiff, TimelineModifiedRow } from "./snapshot.ts";
import type { TimelineClip } from "../../../../src/tools/video-editor/types/index.ts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface ScenarioResult {
  name: string;
  status: "PASS" | "FAIL" | "ERROR";
  checks: CheckResult[];
  diffSummary: string;
  wallTimeMs: number;
  error?: string;
}

interface CheckResult {
  label: string;
  pass: boolean;
  detail: string;
}

function check(label: string, pass: boolean, detail: string): CheckResult {
  return { label, pass, detail };
}

function getTimeline(snapshot: HarnessSnapshot) {
  return snapshot.timelines[snapshot.timeline_id] ?? Object.values(snapshot.timelines)[0];
}

function getClips(snapshot: HarnessSnapshot): TimelineClip[] {
  return getTimeline(snapshot)?.config.clips ?? [];
}

function getClipChanges(diff: SnapshotDiff): TimelineModifiedRow["clip_changes"] | null {
  for (const row of Object.values(diff.timelines.modified)) {
    if ("clip_changes" in row) {
      return (row as TimelineModifiedRow).clip_changes;
    }
  }
  return null;
}

function printResult(result: ScenarioResult): void {
  const icon = result.status === "PASS" ? "[PASS]" : result.status === "FAIL" ? "[FAIL]" : "[ERR ]";
  console.log(`\n${icon} Scenario: ${result.name}  (${result.wallTimeMs}ms)`);
  for (const c of result.checks) {
    console.log(`  ${c.pass ? "  ok" : "FAIL"} ${c.label}: ${c.detail}`);
  }
  if (result.diffSummary) {
    console.log(`  Diff summary:\n${result.diffSummary.split("\n").map((l) => `    ${l}`).join("\n")}`);
  }
  if (result.error) {
    console.log(`  Error: ${result.error}`);
  }
}

// ---------------------------------------------------------------------------
// Scenario runner wrapper
// ---------------------------------------------------------------------------

type ScenarioFn = () => Promise<ScenarioResult>;

async function runScenario(name: string, fn: () => Promise<Omit<ScenarioResult, "name" | "wallTimeMs" | "status">>): Promise<ScenarioResult> {
  const start = Date.now();
  try {
    const partial = await fn();
    const allPassed = partial.checks.every((c) => c.pass);
    return {
      name,
      status: allPassed ? "PASS" : "FAIL",
      wallTimeMs: Date.now() - start,
      ...partial,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      name,
      status: "ERROR",
      checks: [],
      diffSummary: "",
      wallTimeMs: Date.now() - start,
      error: message,
    };
  }
}

// ---------------------------------------------------------------------------
// Scenario 1: Multi-edit in one message
// ---------------------------------------------------------------------------

async function scenario1_multiEdit(): Promise<ScenarioResult> {
  return runScenario("Multi-edit in one message", async () => {
    const harness = new TestHarness();
    try {
      await harness.setup();
      const before = await harness.snapshot();
      const clips = getClips(before);
      const clip1Id = clips[0]?.id;
      const clip2Id = clips[1]?.id;
      const clip3Id = clips[2]?.id;

      await harness.sendMessage(
        `Move the first clip to 10 seconds, delete the second clip, and set the third clip's opacity to 0.5`,
      );

      const after = await harness.snapshot();
      const diff = harness.diff(before, after);
      const cc = getClipChanges(diff);
      const afterClips = getClips(after);

      const checks: CheckResult[] = [];

      // Check clip 1 moved
      const clip1After = afterClips.find((c) => c.id === clip1Id);
      if (cc?.modified[clip1Id]) {
        const movedTo = clip1After?.at;
        checks.push(check(
          "Clip 1 moved to 10s",
          typeof movedTo === "number" && Math.abs(movedTo - 10) < 0.5,
          `at=${movedTo}`,
        ));
      } else {
        checks.push(check("Clip 1 moved", false, "Clip 1 was not modified"));
      }

      // Check clip 2 deleted
      const clip2Deleted = cc?.removed[clip2Id] != null || !afterClips.some((c) => c.id === clip2Id);
      checks.push(check("Clip 2 deleted", clip2Deleted, clip2Deleted ? "removed" : "still present"));

      // Check clip 3 opacity
      const clip3After = afterClips.find((c) => c.id === clip3Id);
      const opacityOk = clip3After != null && typeof clip3After.opacity === "number" && Math.abs(clip3After.opacity - 0.5) < 0.01;
      checks.push(check("Clip 3 opacity=0.5", opacityOk, `opacity=${clip3After?.opacity}`));

      return { checks, diffSummary: harness.summarizeDiff(diff) };
    } finally {
      await harness.teardown();
    }
  });
}

// ---------------------------------------------------------------------------
// Scenario 2: Bulk text overlay
// ---------------------------------------------------------------------------

async function scenario2_bulkTextOverlay(): Promise<ScenarioResult> {
  return runScenario("Bulk text overlay", async () => {
    const harness = new TestHarness();
    try {
      await harness.setup();
      const before = await harness.snapshot();

      await harness.sendMessage(
        `Add text overlays saying 'Scene 1', 'Scene 2', 'Scene 3' at 0s, 4s, and 8s on track V1`,
      );

      const after = await harness.snapshot();
      const diff = harness.diff(before, after);
      const cc = getClipChanges(diff);

      const checks: CheckResult[] = [];

      const addedClips = cc ? Object.values(cc.added) : [];
      const textClips = addedClips.filter((c) => c.clipType === "text");

      checks.push(check(
        "3 text clips created",
        textClips.length >= 3,
        `${textClips.length} text clips added (${addedClips.length} total clips added)`,
      ));

      // Check for Scene 1, Scene 2, Scene 3 content
      for (const label of ["Scene 1", "Scene 2", "Scene 3"]) {
        const found = textClips.some((c) => c.text?.content?.includes(label));
        checks.push(check(
          `Text "${label}" present`,
          found,
          found ? "found" : `not found in ${textClips.map((c) => c.text?.content).join(", ")}`,
        ));
      }

      return { checks, diffSummary: harness.summarizeDiff(diff) };
    } finally {
      await harness.teardown();
    }
  });
}

// ---------------------------------------------------------------------------
// Scenario 3: Describe then edit (multi-turn)
// ---------------------------------------------------------------------------

async function scenario3_describeThenEdit(): Promise<ScenarioResult> {
  return runScenario("Describe then edit (multi-turn)", async () => {
    const harness = new TestHarness();
    try {
      await harness.setup();
      const before = await harness.snapshot();
      const clipsBefore = getClips(before);
      const firstClipId = clipsBefore[0]?.id;

      // Turn 1: ask what's on the timeline
      await harness.sendMessage("What's on the timeline?");

      // Turn 2: delete everything except the first clip
      await harness.sendMessage("Now delete everything except the first clip");

      const after = await harness.snapshot();
      const diff = harness.diff(before, after);
      const afterClips = getClips(after);

      const checks: CheckResult[] = [];

      // First clip should still exist
      const firstClipSurvived = afterClips.some((c) => c.id === firstClipId);
      checks.push(check(
        "First clip survives",
        firstClipSurvived,
        firstClipSurvived ? `${firstClipId} still present` : `${firstClipId} was removed`,
      ));

      // Other clips should be gone
      const otherClipIds = clipsBefore.slice(1).map((c) => c.id);
      const otherClipsRemoved = otherClipIds.every((id) => !afterClips.some((c) => c.id === id));
      checks.push(check(
        "Other clips removed",
        otherClipsRemoved,
        otherClipsRemoved
          ? `All ${otherClipIds.length} other clips removed`
          : `Some still present: ${otherClipIds.filter((id) => afterClips.some((c) => c.id === id)).join(", ")}`,
      ));

      // After the second message, should have only 1 clip (or at least fewer)
      checks.push(check(
        "Only 1 clip remains",
        afterClips.length === 1,
        `${afterClips.length} clips remain (started with ${clipsBefore.length})`,
      ));

      return { checks, diffSummary: harness.summarizeDiff(diff) };
    } finally {
      await harness.teardown();
    }
  });
}

// ---------------------------------------------------------------------------
// Scenario 4: Speed change + trim
// ---------------------------------------------------------------------------

async function scenario4_speedAndTrim(): Promise<ScenarioResult> {
  return runScenario("Speed change + trim", async () => {
    const harness = new TestHarness();
    try {
      await harness.setup();
      const before = await harness.snapshot();
      const clips = getClips(before);
      const clip1Id = clips[0]?.id;

      await harness.sendMessage(
        "Speed up the first clip to 2x and trim it to 2 seconds",
      );

      const after = await harness.snapshot();
      const diff = harness.diff(before, after);
      const afterClips = getClips(after);
      const clip1After = afterClips.find((c) => c.id === clip1Id);

      const checks: CheckResult[] = [];

      // Check speed set to 2
      const speedOk = clip1After != null && typeof clip1After.speed === "number" && Math.abs(clip1After.speed - 2) < 0.01;
      checks.push(check(
        "Speed set to 2x",
        speedOk,
        `speed=${clip1After?.speed}`,
      ));

      // Check duration trimmed to 2s (hold or to-from)
      let durationOk = false;
      let actualDuration: number | string = "unknown";
      if (clip1After) {
        if (typeof clip1After.hold === "number") {
          actualDuration = clip1After.hold;
          durationOk = Math.abs(clip1After.hold - 2) < 0.5;
        } else if (typeof clip1After.from === "number" && typeof clip1After.to === "number") {
          actualDuration = clip1After.to - clip1After.from;
          durationOk = Math.abs((clip1After.to - clip1After.from) - 2) < 0.5;
        }
      }
      checks.push(check(
        "Duration trimmed to ~2s",
        durationOk,
        `duration=${actualDuration}`,
      ));

      return { checks, diffSummary: harness.summarizeDiff(diff) };
    } finally {
      await harness.teardown();
    }
  });
}

// ---------------------------------------------------------------------------
// Scenario 5: Duplicate + arrange
// ---------------------------------------------------------------------------

async function scenario5_duplicate(): Promise<ScenarioResult> {
  return runScenario("Duplicate first clip 3 times", async () => {
    const harness = new TestHarness();
    try {
      await harness.setup();
      const before = await harness.snapshot();
      const clipsBefore = getClips(before);
      const clip0 = clipsBefore[0];

      await harness.sendMessage("Duplicate the first clip 3 times");

      const after = await harness.snapshot();
      const diff = harness.diff(before, after);
      const cc = getClipChanges(diff);

      const checks: CheckResult[] = [];

      const addedClips = cc ? Object.values(cc.added) : [];
      checks.push(check(
        "3 new clips created",
        addedClips.length >= 3,
        `${addedClips.length} clips added`,
      ));

      // Check that new clips reference the same asset as clip 0
      const sameAsset = addedClips.filter((c) => c.asset === clip0?.asset);
      checks.push(check(
        "New clips copy clip 0 asset",
        sameAsset.length >= 3,
        `${sameAsset.length}/${addedClips.length} share asset ${clip0?.asset}`,
      ));

      return { checks, diffSummary: harness.summarizeDiff(diff) };
    } finally {
      await harness.teardown();
    }
  });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  console.log("=== Complex Scenario Tests ===\n");

  const scenarios: ScenarioFn[] = [
    scenario1_multiEdit,
    scenario2_bulkTextOverlay,
    scenario3_describeThenEdit,
    scenario4_speedAndTrim,
    scenario5_duplicate,
  ];

  const results: ScenarioResult[] = [];
  for (const scenario of scenarios) {
    const result = await scenario();
    printResult(result);
    results.push(result);
  }

  // Summary
  const passed = results.filter((r) => r.status === "PASS").length;
  const failed = results.filter((r) => r.status === "FAIL").length;
  const errored = results.filter((r) => r.status === "ERROR").length;

  console.log("\n=== Summary ===");
  console.log(`Total: ${results.length}  Passed: ${passed}  Failed: ${failed}  Errored: ${errored}`);

  console.table(
    results.map((r) => ({
      scenario: r.name,
      status: r.status,
      checks_passed: r.checks.filter((c) => c.pass).length,
      checks_total: r.checks.length,
      wall_ms: r.wallTimeMs,
    })),
  );

  if (failed + errored > 0) {
    process.exitCode = 1;
  }
}

const entryPath = process.argv[1] ? path.resolve(process.argv[1]) : null;
if (entryPath && fileURLToPath(import.meta.url) === entryPath) {
  main().catch((error) => {
    const message = error instanceof Error ? error.stack ?? error.message : String(error);
    console.error(message);
    process.exitCode = 1;
  });
}
