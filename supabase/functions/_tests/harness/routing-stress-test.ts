/**
 * Routing stress test — natural language scenarios that test whether the
 * timeline agent correctly interprets realistic user messages and routes
 * them to the right tools / task types.
 *
 * Categories:
 *   - Generation routing (verify task creation, don't wait for GPU)
 *   - Timeline edit routing (verify correct config changes)
 *   - Ambiguous / edge cases (verify graceful handling)
 *
 * Run:
 *   cd reigh-app && npx tsx supabase/functions/_tests/harness/routing-stress-test.ts
 */

import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { SelectedClipPayload } from "../../ai-timeline-agent/types.ts";
import { TestHarness } from "./index.ts";
import type {
  HarnessSnapshot,
  SnapshotDiff,
  TaskSnapshotRow,
  TimelineModifiedRow,
} from "./snapshot.ts";
import type { TimelineClip } from "../../../../src/tools/video-editor/types/index.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TestCategory = "generation" | "timeline-edit" | "ambiguous";
type TestStatus = "PASS" | "FAIL" | "SOFT_PASS" | "ERROR";

interface RoutingTestResult {
  name: string;
  category: TestCategory;
  status: TestStatus;
  checks: CheckResult[];
  agentResponse: string;
  wallTimeMs: number;
  error?: string;
}

interface CheckResult {
  label: string;
  pass: boolean;
  detail: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function chk(label: string, pass: boolean, detail: string): CheckResult {
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

function getAddedTasks(diff: SnapshotDiff): TaskSnapshotRow[] {
  return Object.values(diff.tasks.added);
}

function getLastAgentResponse(snapshot: HarnessSnapshot): string {
  const sessions = Object.values(snapshot.timeline_agent_sessions);
  for (const session of sessions) {
    if (Array.isArray(session.turns)) {
      const assistantTurns = (session.turns as Array<{ role?: string; content?: string }>)
        .filter((t) => t.role === "assistant" && t.content);
      const last = assistantTurns[assistantTurns.length - 1];
      if (last?.content) return last.content;
    }
  }
  return "(no agent response found)";
}

function buildSelectedClip(snapshot: HarnessSnapshot, clipIndex: number): SelectedClipPayload {
  const timeline = getTimeline(snapshot);
  if (!timeline) throw new Error("No timeline in snapshot");

  const clip = timeline.config.clips[clipIndex];
  if (!clip) throw new Error(`No clip at index ${clipIndex}`);
  if (!clip.asset) throw new Error(`Clip ${clip.id} has no asset`);

  const registry = timeline.asset_registry as {
    assets: Record<string, { file: string; type?: string; generationId?: string }>;
  };
  const asset = registry.assets[clip.asset];
  if (!asset?.file) throw new Error(`Asset ${clip.asset} missing file`);

  return {
    clip_id: clip.id,
    url: asset.file,
    media_type: asset.type?.startsWith("video/") ? "video" : "image",
    ...(asset.generationId ? { generation_id: asset.generationId } : {}),
  };
}

function elapsed(start: number): number {
  return Date.now() - start;
}

function taskParamsContain(task: TaskSnapshotRow, substring: string): boolean {
  return JSON.stringify(task.params ?? {}).toLowerCase().includes(substring.toLowerCase());
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

interface RoutingTestDef {
  name: string;
  category: TestCategory;
  message: string | ((snapshot: HarnessSnapshot) => string);
  selectedClips?: (snapshot: HarnessSnapshot) => SelectedClipPayload[];
  evaluate: (ctx: {
    before: HarnessSnapshot;
    after: HarnessSnapshot;
    diff: SnapshotDiff;
    agentResponse: string;
  }) => { checks: CheckResult[]; softPass?: boolean };
}

async function runSingleTest(testDef: RoutingTestDef): Promise<RoutingTestResult> {
  const start = Date.now();
  const harness = new TestHarness();
  const result: RoutingTestResult = {
    name: testDef.name,
    category: testDef.category,
    status: "ERROR",
    checks: [],
    agentResponse: "",
    wallTimeMs: 0,
  };

  try {
    await harness.setup();
    const before = await harness.snapshot();

    const message = typeof testDef.message === "function"
      ? testDef.message(before)
      : testDef.message;

    const selectedClips = testDef.selectedClips?.(before);

    console.log(`\n--- [${testDef.name}] "${message.slice(0, 80)}${message.length > 80 ? "..." : ""}"`);
    if (selectedClips?.length) {
      console.log(`    selectedClips: [${selectedClips.map((c) => c.clip_id).join(", ")}]`);
    }

    await harness.sendMessage(message, selectedClips);

    const after = await harness.snapshot();
    const diff = harness.diff(before, after);
    const agentResponse = getLastAgentResponse(after);
    result.agentResponse = agentResponse.slice(0, 300);

    console.log(`    Agent: "${agentResponse.slice(0, 120)}${agentResponse.length > 120 ? "..." : ""}"`);

    const evalResult = testDef.evaluate({ before, after, diff, agentResponse });
    result.checks = evalResult.checks;

    const allPassed = evalResult.checks.every((c) => c.pass);
    if (allPassed) {
      result.status = evalResult.softPass ? "SOFT_PASS" : "PASS";
    } else {
      result.status = "FAIL";
    }

    for (const c of result.checks) {
      console.log(`    ${c.pass ? "  ok" : "FAIL"} ${c.label}: ${c.detail}`);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    result.error = msg;
    result.status = "ERROR";
    console.log(`    ERROR: ${msg}`);
  } finally {
    result.wallTimeMs = elapsed(start);
    await harness.teardown();
  }

  return result;
}

// ---------------------------------------------------------------------------
// Test definitions
// ---------------------------------------------------------------------------

const tests: RoutingTestDef[] = [
  // =========================================================================
  // GENERATION ROUTING (1-5)
  // =========================================================================
  {
    name: "1. Watercolor mountain painting",
    category: "generation",
    message: "Make me a beautiful watercolor painting of a mountain landscape",
    evaluate: ({ diff }) => {
      const tasks = getAddedTasks(diff);
      const checks: CheckResult[] = [];

      checks.push(chk(
        "Task created",
        tasks.length >= 1,
        tasks.length >= 1
          ? `${tasks.length} task(s) created: ${tasks.map((t) => t.task_type).join(", ")}`
          : "No tasks were created",
      ));

      if (tasks.length >= 1) {
        const hasPromptContent = tasks.some(
          (t) => taskParamsContain(t, "watercolor") || taskParamsContain(t, "mountain") || taskParamsContain(t, "landscape"),
        );
        checks.push(chk(
          "Prompt content preserved",
          hasPromptContent,
          hasPromptContent
            ? "Task params contain watercolor/mountain/landscape"
            : `Task params: ${JSON.stringify(tasks[0].params).slice(0, 200)}`,
        ));
      }

      return { checks };
    },
  },

  {
    name: "2. Image-to-video from selected clip",
    category: "generation",
    message: "Turn this image into a video",
    selectedClips: (snapshot) => [buildSelectedClip(snapshot, 0)],
    evaluate: ({ diff }) => {
      const tasks = getAddedTasks(diff);
      const checks: CheckResult[] = [];

      checks.push(chk(
        "Task created",
        tasks.length >= 1,
        tasks.length >= 1
          ? `${tasks.length} task(s): ${tasks.map((t) => t.task_type).join(", ")}`
          : "No tasks created",
      ));

      if (tasks.length >= 1) {
        // The task should be video-related (i2v, travel, video, etc.)
        const videoRelated = tasks.some(
          (t) =>
            t.task_type.includes("video") ||
            t.task_type.includes("i2v") ||
            t.task_type.includes("travel") ||
            t.task_type.includes("animate") ||
            taskParamsContain(t, "video") ||
            taskParamsContain(t, "image_url"),
        );
        checks.push(chk(
          "Video-related task type",
          videoRelated,
          videoRelated
            ? `Task type(s): ${tasks.map((t) => t.task_type).join(", ")}`
            : `Unexpected task type(s): ${tasks.map((t) => t.task_type).join(", ")}`,
        ));
      }

      return { checks };
    },
  },

  {
    name: "3. Style transfer (Van Gogh)",
    category: "generation",
    message: "I want this photo but in the style of Van Gogh",
    selectedClips: (snapshot) => [buildSelectedClip(snapshot, 0)],
    evaluate: ({ diff }) => {
      const tasks = getAddedTasks(diff);
      const checks: CheckResult[] = [];

      checks.push(chk(
        "Task created",
        tasks.length >= 1,
        tasks.length >= 1
          ? `${tasks.length} task(s): ${tasks.map((t) => t.task_type).join(", ")}`
          : "No tasks created",
      ));

      if (tasks.length >= 1) {
        // Should be style-transfer related
        const styleRelated = tasks.some(
          (t) =>
            t.task_type.includes("style") ||
            taskParamsContain(t, "style") ||
            taskParamsContain(t, "van gogh") ||
            taskParamsContain(t, "reference"),
        );
        checks.push(chk(
          "Style-transfer routing",
          styleRelated,
          styleRelated
            ? `Task type: ${tasks[0].task_type}, params mention style/reference`
            : `No style indicators found. Types: ${tasks.map((t) => t.task_type).join(", ")}`,
        ));

        // Should reference the selected clip's image
        const hasReference = tasks.some(
          (t) =>
            taskParamsContain(t, "style_reference") ||
            taskParamsContain(t, "reference_image") ||
            taskParamsContain(t, "reference_mode"),
        );
        checks.push(chk(
          "References selected clip",
          hasReference,
          hasReference
            ? "Task params contain reference image data"
            : "No reference image found in task params",
        ));
      }

      return { checks };
    },
  },

  {
    name: "4. Subject/scene transfer (Eiffel Tower)",
    category: "generation",
    message: "Put this person in front of the Eiffel Tower",
    selectedClips: (snapshot) => [buildSelectedClip(snapshot, 0)],
    evaluate: ({ diff }) => {
      const tasks = getAddedTasks(diff);
      const checks: CheckResult[] = [];

      checks.push(chk(
        "Task created",
        tasks.length >= 1,
        tasks.length >= 1
          ? `${tasks.length} task(s): ${tasks.map((t) => t.task_type).join(", ")}`
          : "No tasks created",
      ));

      if (tasks.length >= 1) {
        // Should be subject-transfer or scene-transfer
        const transferRelated = tasks.some(
          (t) =>
            t.task_type.includes("style") ||
            t.task_type.includes("subject") ||
            t.task_type.includes("scene") ||
            taskParamsContain(t, "subject") ||
            taskParamsContain(t, "reference_mode") ||
            taskParamsContain(t, "eiffel"),
        );
        checks.push(chk(
          "Subject/scene transfer routing",
          transferRelated,
          transferRelated
            ? `Task type: ${tasks[0].task_type}`
            : `No transfer indicators. Types: ${tasks.map((t) => t.task_type).join(", ")}`,
        ));

        // Should have prompt about Eiffel Tower
        const hasEiffel = tasks.some((t) => taskParamsContain(t, "eiffel"));
        checks.push(chk(
          "Prompt mentions Eiffel Tower",
          hasEiffel,
          hasEiffel
            ? "Eiffel Tower found in task params"
            : "Eiffel Tower not found in task params",
        ));
      }

      return { checks };
    },
  },

  {
    name: "5. Multiple image generations (3 variations)",
    category: "generation",
    message: "Generate 3 variations of a sunset over the ocean",
    evaluate: ({ diff }) => {
      const tasks = getAddedTasks(diff);
      const checks: CheckResult[] = [];

      // Should create at least 1 task (might be 1 task with count=3, or 3 tasks)
      checks.push(chk(
        "Task(s) created",
        tasks.length >= 1,
        tasks.length >= 1
          ? `${tasks.length} task(s): ${tasks.map((t) => t.task_type).join(", ")}`
          : "No tasks created",
      ));

      if (tasks.length >= 1) {
        // Check if the agent created 3 tasks OR a single task with count/imagesPerPrompt >= 3
        const multipleTasksOrBatch =
          tasks.length >= 3 ||
          tasks.some(
            (t) =>
              taskParamsContain(t, '"imagesPerPrompt":3') ||
              taskParamsContain(t, '"imagesPerPrompt": 3') ||
              taskParamsContain(t, '"count":3') ||
              taskParamsContain(t, '"count": 3') ||
              taskParamsContain(t, '"num_images":3') ||
              taskParamsContain(t, '"num_images": 3') ||
              taskParamsContain(t, '"variations":3') ||
              taskParamsContain(t, '"n":3'),
          );
        checks.push(chk(
          "3 variations requested",
          multipleTasksOrBatch,
          multipleTasksOrBatch
            ? tasks.length >= 3
              ? `${tasks.length} separate tasks created`
              : "Single task with batch count >= 3"
            : `Only ${tasks.length} task(s), no batch count found. Params: ${JSON.stringify(tasks[0]?.params).slice(0, 200)}`,
        ));

        // Should mention sunset/ocean
        const hasPrompt = tasks.some(
          (t) => taskParamsContain(t, "sunset") || taskParamsContain(t, "ocean"),
        );
        checks.push(chk(
          "Prompt content preserved",
          hasPrompt,
          hasPrompt ? "sunset/ocean found in params" : "sunset/ocean not found",
        ));
      }

      return { checks };
    },
  },

  // =========================================================================
  // TIMELINE EDIT ROUTING (6-10)
  // =========================================================================
  {
    name: "6. Make first clip shorter (2 seconds)",
    category: "timeline-edit",
    message: "Can you make the first clip shorter? Like 2 seconds",
    evaluate: ({ before, diff }) => {
      const checks: CheckResult[] = [];
      const cc = getClipChanges(diff);
      const clip0Id = getClips(before)[0]?.id;

      if (!clip0Id) {
        checks.push(chk("Clip 0 exists", false, "No clips in timeline"));
        return { checks };
      }

      // Check clip 0 was modified
      const clip0Modified = cc?.modified[clip0Id];
      checks.push(chk(
        "First clip modified",
        !!clip0Modified,
        clip0Modified ? `Clip ${clip0Id} was modified` : `Clip ${clip0Id} was not modified`,
      ));

      if (clip0Modified && !("clip_changes" in clip0Modified)) {
        // Check trim fields changed
        const trimChanged = clip0Modified.changes.some(
          (c) => c.path === "from" || c.path === "to" || c.path === "hold",
        );
        checks.push(chk(
          "Trim fields changed",
          trimChanged,
          trimChanged
            ? `Changed fields: ${clip0Modified.changes.map((c) => c.path).join(", ")}`
            : `Changed fields: ${clip0Modified.changes.map((c) => c.path).join(", ")} (no trim fields)`,
        ));

        // Check approximate duration ~2s
        const afterClip = clip0Modified.after;
        let duration: number | null = null;
        if (typeof afterClip.hold === "number") {
          duration = afterClip.hold;
        } else if (typeof afterClip.from === "number" && typeof afterClip.to === "number") {
          duration = afterClip.to - afterClip.from;
        }
        const durationOk = duration !== null && Math.abs(duration - 2) < 0.5;
        checks.push(chk(
          "Duration ~2 seconds",
          durationOk,
          `duration=${duration ?? "unknown"}`,
        ));
      }

      // No generation tasks should be created for a trim
      const tasks = getAddedTasks(diff);
      checks.push(chk(
        "No generation tasks",
        tasks.length === 0,
        tasks.length === 0 ? "Correct: no tasks created" : `Unexpected: ${tasks.length} task(s) created`,
      ));

      return { checks };
    },
  },

  {
    name: "7. Add 'Chapter 1' text at beginning",
    category: "timeline-edit",
    message: "Put some text that says 'Chapter 1' at the beginning",
    evaluate: ({ diff }) => {
      const checks: CheckResult[] = [];
      const cc = getClipChanges(diff);

      const addedClips = cc ? Object.values(cc.added) : [];
      const textClips = addedClips.filter((c) => c.clipType === "text");

      checks.push(chk(
        "Text clip added",
        textClips.length >= 1,
        textClips.length >= 1
          ? `${textClips.length} text clip(s) added`
          : `No text clips added (${addedClips.length} total clips added)`,
      ));

      if (textClips.length >= 1) {
        const hasChapter1 = textClips.some(
          (c) => c.text?.content?.toLowerCase().includes("chapter 1"),
        );
        checks.push(chk(
          "Text says 'Chapter 1'",
          hasChapter1,
          hasChapter1
            ? `Content: "${textClips[0].text?.content}"`
            : `Content: "${textClips.map((c) => c.text?.content).join(", ")}"`,
        ));

        // Should be near 0s
        const nearBeginning = textClips.some(
          (c) => typeof c.at === "number" && c.at <= 1,
        );
        checks.push(chk(
          "Placed near beginning (at <= 1s)",
          nearBeginning,
          `at=${textClips.map((c) => c.at).join(", ")}`,
        ));
      }

      // No generation tasks
      const tasks = getAddedTasks(diff);
      checks.push(chk(
        "No generation tasks",
        tasks.length === 0,
        tasks.length === 0 ? "Correct" : `Unexpected: ${tasks.length} task(s)`,
      ));

      return { checks };
    },
  },

  {
    name: "8. Increase volume on second clip",
    category: "timeline-edit",
    message: "The second clip is too quiet, bump up the volume",
    evaluate: ({ before, diff }) => {
      const checks: CheckResult[] = [];
      const cc = getClipChanges(diff);
      const clips = getClips(before);
      const clip1Id = clips[1]?.id;

      if (!clip1Id) {
        checks.push(chk("Clip 1 exists", false, "Fewer than 2 clips in timeline"));
        return { checks };
      }

      const clip1Modified = cc?.modified[clip1Id];
      checks.push(chk(
        "Second clip modified",
        !!clip1Modified,
        clip1Modified ? `Clip ${clip1Id} was modified` : `Clip ${clip1Id} was not modified`,
      ));

      if (clip1Modified && !("clip_changes" in clip1Modified)) {
        const volumeChanged = clip1Modified.changes.some((c) => c.path === "volume");
        checks.push(chk(
          "Volume property changed",
          volumeChanged,
          volumeChanged
            ? `Changed: ${clip1Modified.changes.filter((c) => c.path === "volume").map((c) => `${c.before} -> ${c.after}`).join(", ")}`
            : `Changed fields: ${clip1Modified.changes.map((c) => c.path).join(", ")}`,
        ));

        if (volumeChanged) {
          const volumeChange = clip1Modified.changes.find((c) => c.path === "volume");
          const beforeVol = typeof volumeChange?.before === "number" ? volumeChange.before : 1;
          const afterVol = typeof volumeChange?.after === "number" ? volumeChange.after : 0;
          checks.push(chk(
            "Volume increased",
            afterVol > beforeVol,
            `${beforeVol} -> ${afterVol}`,
          ));
        }
      }

      return { checks };
    },
  },

  {
    name: "9. Rearrange clips (last plays first)",
    category: "timeline-edit",
    message: "Rearrange the clips so the last one plays first",
    evaluate: ({ before, after, diff }) => {
      const checks: CheckResult[] = [];
      const clipsBefore = getClips(before);
      const clipsAfter = getClips(after);

      if (clipsBefore.length < 2) {
        checks.push(chk("Enough clips", false, "Fewer than 2 clips"));
        return { checks };
      }

      const lastClipId = clipsBefore[clipsBefore.length - 1]?.id;

      // The last clip should now be at position 0 or at the earliest time
      const lastClipAfter = clipsAfter.find((c) => c.id === lastClipId);
      if (lastClipAfter) {
        // Check it's at position 0 or at time 0
        const isFirst =
          clipsAfter.indexOf(lastClipAfter) === 0 ||
          (typeof lastClipAfter.at === "number" && lastClipAfter.at <= 0.1);
        checks.push(chk(
          "Last clip moved to first position",
          isFirst,
          `Clip ${lastClipId} is at index ${clipsAfter.indexOf(lastClipAfter)}, at=${lastClipAfter.at}`,
        ));
      } else {
        checks.push(chk("Last clip still exists", false, `Clip ${lastClipId} not found after`));
      }

      // All clips should still exist (rearrange, not delete)
      const allSurvived = clipsBefore.every((cb) => clipsAfter.some((ca) => ca.id === cb.id));
      checks.push(chk(
        "All clips preserved",
        allSurvived,
        allSurvived
          ? `All ${clipsBefore.length} clips still present`
          : `Some clips missing after rearrange`,
      ));

      // Timeline should have been modified
      const cc = getClipChanges(diff);
      const anyModified = cc ? Object.keys(cc.modified).length > 0 : false;
      checks.push(chk(
        "Clips were modified",
        anyModified,
        anyModified
          ? `${Object.keys(cc!.modified).length} clip(s) modified`
          : "No clips were modified",
      ));

      return { checks };
    },
  },

  {
    name: "10. Delete middle clip",
    category: "timeline-edit",
    message: "I don't need the middle clip anymore",
    evaluate: ({ before, diff }) => {
      const checks: CheckResult[] = [];
      const clipsBefore = getClips(before);
      const cc = getClipChanges(diff);

      if (clipsBefore.length < 3) {
        checks.push(chk("Enough clips", false, `Only ${clipsBefore.length} clips, need 3+`));
        return { checks };
      }

      const middleIndex = Math.floor(clipsBefore.length / 2);
      const middleClipId = clipsBefore[middleIndex]?.id;
      // Also accept clip at index 1 as "middle" for 3-clip timelines
      const clip1Id = clipsBefore[1]?.id;

      const removed = cc ? Object.keys(cc.removed) : [];
      const middleRemoved = removed.includes(middleClipId) || removed.includes(clip1Id);
      checks.push(chk(
        "Middle clip deleted",
        middleRemoved,
        middleRemoved
          ? `Removed: ${removed.join(", ")}`
          : `No middle clip removed. Removed: ${removed.join(", ") || "none"}`,
      ));

      // Should have removed exactly 1 clip
      checks.push(chk(
        "Exactly 1 clip removed",
        removed.length === 1,
        `${removed.length} clip(s) removed`,
      ));

      // No generation tasks
      const tasks = getAddedTasks(diff);
      checks.push(chk(
        "No generation tasks",
        tasks.length === 0,
        tasks.length === 0 ? "Correct" : `Unexpected: ${tasks.length} task(s)`,
      ));

      return { checks };
    },
  },

  // =========================================================================
  // AMBIGUOUS / EDGE CASES (11-13)
  // =========================================================================
  {
    name: "11. Vague: 'Make it look better'",
    category: "ambiguous",
    message: "Make it look better",
    evaluate: ({ agentResponse }) => {
      const checks: CheckResult[] = [];

      // The agent should either:
      //  a) Ask for clarification (mentions "what" or asks a question)
      //  b) Make a judgment call and do something reasonable
      const turnsLower = agentResponse.toLowerCase();
      const asksQuestion = turnsLower.includes("?");
      const asksClarification =
        turnsLower.includes("what would you like") ||
        turnsLower.includes("could you") ||
        turnsLower.includes("can you clarify") ||
        turnsLower.includes("what do you mean") ||
        turnsLower.includes("more specific") ||
        turnsLower.includes("which");

      // Or the agent took some action (modified clips or created tasks)
      const cc = getClipChanges(diff);
      const tookAction =
        getAddedTasks(diff).length > 0 ||
        (cc && (Object.keys(cc.modified).length > 0 || Object.keys(cc.added).length > 0));

      const handledReasonably = asksClarification || asksQuestion || tookAction;
      checks.push(chk(
        "Handled vague request",
        handledReasonably,
        asksClarification
          ? "Agent asked for clarification"
          : asksQuestion
            ? "Agent asked a question"
            : tookAction
              ? "Agent took action (judgment call)"
              : "Agent neither clarified nor acted",
      ));

      // This test is soft — either behavior is acceptable
      return { checks, softPass: handledReasonably };
    },
  },

  {
    name: "12. Unsupported: 'Add some music'",
    category: "ambiguous",
    message: "Add some music",
    evaluate: ({ agentResponse }) => {
      const checks: CheckResult[] = [];
      const turnsLower = agentResponse.toLowerCase();

      // Agent should explain it can't generate audio, or explain limitations
      const explainsLimitation =
        turnsLower.includes("can't") ||
        turnsLower.includes("cannot") ||
        turnsLower.includes("don't have") ||
        turnsLower.includes("not able") ||
        turnsLower.includes("not supported") ||
        turnsLower.includes("unable") ||
        turnsLower.includes("audio") ||
        turnsLower.includes("music") ||
        turnsLower.includes("sound");

      checks.push(chk(
        "Acknowledges music/audio request",
        explainsLimitation,
        explainsLimitation
          ? "Agent addressed the music/audio request"
          : `Agent response: "${agentResponse.slice(0, 200)}"`,
      ));

      // Should NOT create an image generation task when asked for music
      const tasks = getAddedTasks(diff);
      const noImageTask = !tasks.some(
        (t) =>
          t.task_type.includes("image") ||
          t.task_type.includes("t2i") ||
          t.task_type.includes("style"),
      );
      checks.push(chk(
        "No spurious image generation",
        noImageTask,
        noImageTask
          ? "Correct: no image generation tasks"
          : `Unexpected: created ${tasks.map((t) => t.task_type).join(", ")}`,
      ));

      return { checks, softPass: true };
    },
  },

  {
    name: "13. Unsupported: 'Enhance the resolution'",
    category: "ambiguous",
    message: "Can you enhance the resolution?",
    evaluate: ({ agentResponse }) => {
      const checks: CheckResult[] = [];
      const turnsLower = agentResponse.toLowerCase();

      // Agent should explain limitation or attempt something reasonable
      const addressesRequest =
        turnsLower.includes("resolution") ||
        turnsLower.includes("upscale") ||
        turnsLower.includes("enhance") ||
        turnsLower.includes("quality") ||
        turnsLower.includes("can't") ||
        turnsLower.includes("cannot") ||
        turnsLower.includes("not supported") ||
        turnsLower.includes("unable") ||
        turnsLower.includes("don't");

      checks.push(chk(
        "Addresses resolution request",
        addressesRequest,
        addressesRequest
          ? "Agent addressed the resolution/enhance topic"
          : `Agent response: "${agentResponse.slice(0, 200)}"`,
      ));

      return { checks, softPass: true };
    },
  },
];

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  console.log("=== Routing Stress Test ===");
  console.log(`Testing ${tests.length} natural-language routing scenarios\n`);

  const results: RoutingTestResult[] = [];

  for (const testDef of tests) {
    const result = await runSingleTest(testDef);
    results.push(result);
  }

  // -------------------------------------------------------------------------
  // Summary table
  // -------------------------------------------------------------------------
  console.log("\n\n========================================");
  console.log("          ROUTING STRESS TEST RESULTS");
  console.log("========================================\n");

  const col = { name: 42, cat: 14, status: 10, checks: 8, time: 8 };
  const hdr = [
    "Test".padEnd(col.name),
    "Category".padEnd(col.cat),
    "Status".padEnd(col.status),
    "Checks".padEnd(col.checks),
    "Time".padEnd(col.time),
  ].join(" | ");
  console.log(hdr);
  console.log("-".repeat(hdr.length));

  for (const r of results) {
    const checksStr = `${r.checks.filter((c) => c.pass).length}/${r.checks.length}`;
    const row = [
      r.name.padEnd(col.name),
      r.category.padEnd(col.cat),
      r.status.padEnd(col.status),
      checksStr.padEnd(col.checks),
      `${(r.wallTimeMs / 1000).toFixed(1)}s`.padEnd(col.time),
    ].join(" | ");
    console.log(row);
  }

  console.log("-".repeat(hdr.length));

  const passed = results.filter((r) => r.status === "PASS").length;
  const softPassed = results.filter((r) => r.status === "SOFT_PASS").length;
  const failed = results.filter((r) => r.status === "FAIL").length;
  const errored = results.filter((r) => r.status === "ERROR").length;

  console.log(`\nPASS: ${passed}  SOFT_PASS: ${softPassed}  FAIL: ${failed}  ERROR: ${errored}  Total: ${results.length}`);
  console.log(`(SOFT_PASS = acceptable behavior for ambiguous/edge cases)\n`);

  // -------------------------------------------------------------------------
  // Per-category breakdown
  // -------------------------------------------------------------------------
  const categories: TestCategory[] = ["generation", "timeline-edit", "ambiguous"];
  for (const cat of categories) {
    const catResults = results.filter((r) => r.category === cat);
    const catPassed = catResults.filter((r) => r.status === "PASS" || r.status === "SOFT_PASS").length;
    console.log(`  ${cat}: ${catPassed}/${catResults.length} passed`);
  }

  // -------------------------------------------------------------------------
  // Detailed failure / error report
  // -------------------------------------------------------------------------
  const problems = results.filter((r) => r.status === "FAIL" || r.status === "ERROR");
  if (problems.length > 0) {
    console.log("\n--- FAILURES & ERRORS ---\n");
    for (const r of problems) {
      console.log(`[${r.status}] ${r.name}`);
      if (r.error) console.log(`  Error: ${r.error}`);
      for (const c of r.checks.filter((c) => !c.pass)) {
        console.log(`  FAIL ${c.label}: ${c.detail}`);
      }
      console.log(`  Agent said: "${r.agentResponse.slice(0, 200)}"`);
      console.log();
    }
  }

  // -------------------------------------------------------------------------
  // Key insight summary
  // -------------------------------------------------------------------------
  console.log("--- KEY INSIGHT ---");
  const genResults = results.filter((r) => r.category === "generation");
  const editResults = results.filter((r) => r.category === "timeline-edit");
  const ambigResults = results.filter((r) => r.category === "ambiguous");

  const genScore = genResults.filter((r) => r.status === "PASS").length;
  const editScore = editResults.filter((r) => r.status === "PASS").length;
  const ambigScore = ambigResults.filter((r) => r.status === "PASS" || r.status === "SOFT_PASS").length;

  console.log(`  Generation routing:  ${genScore}/${genResults.length} correct`);
  console.log(`  Timeline edit routing: ${editScore}/${editResults.length} correct`);
  console.log(`  Ambiguous handling:  ${ambigScore}/${ambigResults.length} reasonable`);

  const totalScore = genScore + editScore + ambigScore;
  const totalPossible = results.length;
  console.log(`\n  Overall: ${totalScore}/${totalPossible} (${Math.round((totalScore / totalPossible) * 100)}%)`);
  console.log(`  Does the agent understand what users actually mean? ${totalScore >= totalPossible * 0.7 ? "YES (>= 70%)" : "NEEDS WORK (< 70%)"}`);

  // -------------------------------------------------------------------------
  // JSON report
  // -------------------------------------------------------------------------
  const reportDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "reports");
  mkdirSync(reportDir, { recursive: true });
  const timestamp = new Date().toISOString().replaceAll(":", "-");
  const reportPath = path.join(reportDir, `routing-stress-report-${timestamp}.json`);
  writeFileSync(
    reportPath,
    JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        summary: { passed, softPassed, failed, errored, total: results.length },
        results: results.map((r) => ({
          name: r.name,
          category: r.category,
          status: r.status,
          checks: r.checks,
          agentResponse: r.agentResponse,
          wallTimeMs: r.wallTimeMs,
          error: r.error,
        })),
      },
      null,
      2,
    ) + "\n",
    "utf8",
  );
  console.log(`\nWrote JSON report to ${reportPath}`);

  if (failed + errored > 0) {
    process.exitCode = 1;
  }
}

const entryPath = process.argv[1] ? path.resolve(process.argv[1]) : null;
if (entryPath && fileURLToPath(import.meta.url) === entryPath) {
  main().catch((err) => {
    console.error(err instanceof Error ? err.stack ?? err.message : String(err));
    process.exitCode = 1;
  });
}
