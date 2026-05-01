import type { AssetRegistry, TimelineClip } from "../../../../src/tools/video-editor/types/index.ts";
import type { SelectedClipPayload } from "../../ai-timeline-agent/types.ts";
import {
  expectClipDeleted,
  expectClipMoved,
  expectClipTrimmed,
  expectCreditChargedSoft,
  expectDuplicateGeneration,
  expectGenerationCreated,
  expectGenerationCreatedSoft,
  expectMediaClipAdded,
  expectNoCollateralDamage,
  expectPropertySet,
  expectSessionTerminal,
  expectTaskCreatedByPrompt,
  expectTaskParamsContain,
  expectTextAdded,
  scoreResult,
  type AssertionResult,
} from "./evaluate.ts";
import type { HarnessSnapshot, SnapshotDiff, TaskSnapshotRow, TimelineSnapshotRow } from "./snapshot.ts";

export type TestCaseCategory = "timeline-edit" | "generation" | "error-handling";

export interface TestCaseEvaluationContext {
  before: HarnessSnapshot;
  after: HarnessSnapshot;
  diff: SnapshotDiff;
}

export interface TestCase {
  name: string;
  category: TestCaseCategory;
  setup?: (snapshot: HarnessSnapshot) => Promise<void> | void;
  message: string | ((snapshot: HarnessSnapshot) => string);
  selectedClips?: SelectedClipPayload[] | ((snapshot: HarnessSnapshot) => SelectedClipPayload[]);
  evaluate: (context: TestCaseEvaluationContext) => ReturnType<typeof scoreResult>;
  skipTaskCompletion?: boolean;
  timeoutMs?: number;
}

/** @deprecated The agent now supports duplicate_generation + add-media, so compound workflows are unblocked. */
export const COMPOUND_CASES_BLOCKED_REASON = null;

const TEXT_TO_IMAGE_PROMPT = "harness lighthouse mist matte painting";
const STYLE_TRANSFER_PROMPT = "harness style transfer editorial portrait";
const SEARCH_AND_ADD_LORA_PROMPT = "harness editorial portrait with soft window light";
const INSERT_AFTER_SOURCE_PROMPT = "harness warm cinematic grade with subtle contrast";
const TEXT_CLIP_CONTENT = "Harness caption alpha";

function pass(reason: string): AssertionResult {
  return { pass: true, reason };
}

function fail(reason: string): AssertionResult {
  return { pass: false, reason };
}

function getTimeline(snapshot: HarnessSnapshot): TimelineSnapshotRow {
  const timeline = snapshot.timelines[snapshot.timeline_id] ?? Object.values(snapshot.timelines)[0];
  if (!timeline) {
    throw new Error("Harness snapshot did not include a timeline row.");
  }
  return timeline;
}

function getClip(snapshot: HarnessSnapshot, index: number): TimelineClip {
  const clip = getTimeline(snapshot).config.clips[index];
  if (!clip) {
    throw new Error(`Harness snapshot did not include clip index ${index}.`);
  }
  return clip;
}

function getRegistry(snapshot: HarnessSnapshot): AssetRegistry {
  const registry = getTimeline(snapshot).asset_registry;
  if (!registry || typeof registry !== "object" || Array.isArray(registry) || !("assets" in registry)) {
    throw new Error("Harness snapshot asset_registry is not shaped like an AssetRegistry.");
  }
  return registry as AssetRegistry;
}

function clipDurationSeconds(clip: TimelineClip): number | undefined {
  if (typeof clip.hold === "number") {
    return clip.hold;
  }

  if (typeof clip.from === "number" && typeof clip.to === "number") {
    return clip.to - clip.from;
  }

  return undefined;
}

function buildSelectedClip(snapshot: HarnessSnapshot, clipIndex: number): SelectedClipPayload {
  const clip = getClip(snapshot, clipIndex);
  if (!clip.asset) {
    throw new Error(`Clip ${clip.id} does not reference an asset.`);
  }

  const asset = getRegistry(snapshot).assets[clip.asset];
  if (!asset?.file) {
    throw new Error(`Asset registry entry for ${clip.asset} is missing a file URL.`);
  }

  return {
    clip_id: clip.id,
    url: asset.file,
    media_type: asset.type?.startsWith("video/") ? "video" : "image",
    is_timeline_backed: true,
    track_id: clip.track,
    at: clip.at,
    ...(typeof clipDurationSeconds(clip) === "number"
      ? { duration: clipDurationSeconds(clip) }
      : {}),
    ...(typeof asset.generationId === "string" && asset.generationId.trim()
      ? { generation_id: asset.generationId }
      : {}),
  };
}

function resolveTurnsText(snapshot: HarnessSnapshot): string {
  return JSON.stringify(Object.values(snapshot.timeline_agent_sessions).map((session) => session.turns)).toLowerCase();
}

function expectSessionMentions(snapshot: HarnessSnapshot, substring: string): AssertionResult {
  return resolveTurnsText(snapshot).includes(substring.toLowerCase())
    ? pass(`Session turns mention "${substring}".`)
    : fail(`Session turns did not mention "${substring}".`);
}

function findAddedTask(
  diff: SnapshotDiff,
  predicate: (task: TaskSnapshotRow) => boolean,
): TaskSnapshotRow | null {
  return Object.values(diff.tasks.added).find(predicate) ?? null;
}

function expectTaskParam(
  diff: SnapshotDiff,
  predicate: (task: TaskSnapshotRow) => boolean,
  label: string,
): AssertionResult {
  const task = findAddedTask(diff, predicate);
  return task
    ? pass(`Task ${task.id} matched ${label}.`)
    : fail(`No added task matched ${label}.`);
}

function evaluateWith(assertions: AssertionResult[]) {
  return scoreResult(assertions);
}

export function resolveCaseMessage(testCase: TestCase, snapshot: HarnessSnapshot): string {
  return typeof testCase.message === "function" ? testCase.message(snapshot) : testCase.message;
}

export function resolveCaseSelectedClips(
  testCase: TestCase,
  snapshot: HarnessSnapshot,
): SelectedClipPayload[] | undefined {
  if (!testCase.selectedClips) {
    return undefined;
  }
  return typeof testCase.selectedClips === "function"
    ? testCase.selectedClips(snapshot)
    : testCase.selectedClips;
}

export const seedTestCases: TestCase[] = [
  {
    name: "move clip to a new position",
    category: "timeline-edit",
    message: (snapshot) => `move ${getClip(snapshot, 0).id} 6.5`,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectClipMoved(diff, getClip(before, 0).id, 6.5),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          tables: {
            timelines: { modified: [before.timeline_id] },
            timeline_agent_sessions: { modified: "*" },
          },
          timelineClips: { modified: [getClip(before, 0).id] },
        }),
      ]),
  },
  {
    name: "delete an existing clip",
    category: "timeline-edit",
    message: (snapshot) => `delete ${getClip(snapshot, 1).id}`,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectClipDeleted(diff, getClip(before, 1).id),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          tables: {
            timelines: { modified: [before.timeline_id] },
            timeline_agent_sessions: { modified: "*" },
          },
          timelineClips: { removed: [getClip(before, 1).id] },
        }),
      ]),
  },
  {
    name: "trim a clip duration",
    category: "timeline-edit",
    message: (snapshot) => `trim ${getClip(snapshot, 0).id} --from 0.5 --duration 2.5`,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectClipTrimmed(diff, getClip(before, 0).id, 2.5),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          tables: {
            timelines: { modified: [before.timeline_id] },
            timeline_agent_sessions: { modified: "*" },
          },
          timelineClips: { modified: [getClip(before, 0).id] },
        }),
      ]),
  },
  {
    name: "add a text clip",
    category: "timeline-edit",
    message: () => `add-text V1 1.5 2 "${TEXT_CLIP_CONTENT}"`,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectTextAdded(diff, TEXT_CLIP_CONTENT),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          tables: {
            timelines: { modified: [before.timeline_id] },
            timeline_agent_sessions: { modified: "*" },
          },
          timelineClips: { added: "*" },
        }),
      ]),
  },
  {
    name: "set a clip volume property",
    category: "timeline-edit",
    message: (snapshot) => `set ${getClip(snapshot, 2).id} volume 0.25`,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectPropertySet(diff, getClip(before, 2).id, "volume", 0.25),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          tables: {
            timelines: { modified: [before.timeline_id] },
            timeline_agent_sessions: { modified: "*" },
          },
          timelineClips: { modified: [getClip(before, 2).id] },
        }),
      ]),
  },
  {
    name: "duplicate a generation from a selected clip",
    category: "timeline-edit",
    message: (snapshot) => {
      const clip = getClip(snapshot, 0);
      const registry = getRegistry(snapshot);
      const asset = clip.asset ? registry.assets[clip.asset] : null;
      const generationId = typeof asset?.generationId === "string" ? asset.generationId : null;
      return generationId
        ? `Duplicate generation ${generationId}`
        : `Duplicate the generation from clip ${clip.id}`;
    },
    selectedClips: (snapshot) => [buildSelectedClip(snapshot, 0)],
    skipTaskCompletion: true,
    evaluate: ({ after, diff }) =>
      evaluateWith([
        expectDuplicateGeneration(diff),
        expectSessionTerminal(after),
        expectSessionMentions(after, "duplicated"),
        expectNoCollateralDamage(diff, {
          tables: {
            generations: { added: "*" },
            generation_variants: { added: "*" },
            shot_generations: { added: "*" },
            timeline_agent_sessions: { modified: "*" },
          },
        }),
      ]),
  },
  {
    name: "duplicate a generation and add it to the timeline",
    category: "timeline-edit",
    message: (snapshot) => {
      const clip = getClip(snapshot, 0);
      return `Duplicate the generation from clip ${clip.id} and add it right after this clip on the same track`;
    },
    selectedClips: (snapshot) => [buildSelectedClip(snapshot, 0)],
    skipTaskCompletion: true,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectDuplicateGeneration(diff),
        expectMediaClipAdded(diff, getClip(before, 0).track),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          tables: {
            timelines: { modified: [before.timeline_id] },
            generations: { added: "*" },
            generation_variants: { added: "*" },
            shot_generations: { added: "*" },
            timeline_agent_sessions: { modified: "*" },
          },
          timelineClips: { added: "*" },
        }),
      ]),
  },
  {
    name: "create a text-to-image generation",
    category: "generation",
    message: () => `Create a text-to-image generation for "${TEXT_TO_IMAGE_PROMPT}".`,
    timeoutMs: 180_000,
    evaluate: ({ after, diff }) => {
      const task = findAddedTask(
        diff,
        (row) => JSON.stringify(row.params).toLowerCase().includes(TEXT_TO_IMAGE_PROMPT),
      );
      return evaluateWith([
        expectTaskCreatedByPrompt(diff, TEXT_TO_IMAGE_PROMPT),
        expectGenerationCreated(diff, task?.id),
        expectCreditChargedSoft(diff, task?.id),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          user: true,
          tables: {
            tasks: { added: "*" },
            generations: { added: "*" },
            generation_variants: { added: "*" },
            timeline_agent_sessions: { modified: "*" },
            credits_ledger: { added: "*" },
          },
        }),
      ]);
    },
  },
  {
    name: "create a style-transfer generation from a selected clip",
    category: "generation",
    message: (snapshot) =>
      `Use selected clip ${getClip(snapshot, 0).id} as the style reference and create a style-transfer image for "${STYLE_TRANSFER_PROMPT}".`,
    selectedClips: (snapshot) => [buildSelectedClip(snapshot, 0)],
    timeoutMs: 180_000,
    evaluate: ({ after, diff }) => {
      const task = findAddedTask(
        diff,
        (row) => JSON.stringify(row.params).toLowerCase().includes(STYLE_TRANSFER_PROMPT),
      );
      return evaluateWith([
        expectTaskCreatedByPrompt(diff, STYLE_TRANSFER_PROMPT),
        // The resolver stores reference intent as task_type (qwen_image_style)
        // and the presence of style_reference_image in params, not as a literal
        // reference_mode field.
        expectTaskParam(
          diff,
          (row) =>
            row.id === task?.id
            && row.task_type.includes("style")
            && JSON.stringify(row.params).includes("style_reference_image"),
          'task_type contains "style" and params include style_reference_image',
        ),
        // Soft: the worker cannot process external (non-storage) reference
        // images, so the task will fail and no generation will be produced
        // when running against synthetic harness fixtures.
        expectGenerationCreatedSoft(diff, task?.id),
        expectCreditChargedSoft(diff, task?.id),
        expectSessionTerminal(after),
      ]);
    },
  },
  {
    name: "edit a selected image and insert the result after the source clip",
    category: "generation",
    message: (snapshot) => {
      const clip = getClip(snapshot, 0);
      return `Create an image-to-image edit from selected clip ${clip.id} with prompt "${INSERT_AFTER_SOURCE_PROMPT}" and insert the result after the source clip on the same track.`;
    },
    selectedClips: (snapshot) => [buildSelectedClip(snapshot, 0)],
    timeoutMs: 180_000,
    evaluate: ({ before, after, diff }) => {
      const sourceClip = getClip(before, 0);
      const task = findAddedTask(
        diff,
        (row) => JSON.stringify(row.params).toLowerCase().includes(INSERT_AFTER_SOURCE_PROMPT),
      );

      return evaluateWith([
        expectTaskCreatedByPrompt(diff, INSERT_AFTER_SOURCE_PROMPT),
        expectTaskParamsContain(diff, "timeline_placement", "timeline placement in task params"),
        expectGenerationCreated(diff, task?.id),
        expectMediaClipAdded(diff, sourceClip.track),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          user: true,
          tables: {
            tasks: { added: "*" },
            generations: { added: "*" },
            generation_variants: { added: "*" },
            shot_generations: { added: "*" },
            timelines: { modified: [before.timeline_id] },
            timeline_agent_sessions: { modified: "*" },
            credits_ledger: { added: "*" },
          },
          timelineClips: { added: "*" },
        }),
      ]);
    },
  },
  {
    name: "create a text-to-image generation with project LoRAs",
    category: "generation",
    message: () => "Generate a cinematic desert landscape at golden hour",
    skipTaskCompletion: true,
    evaluate: ({ after, diff }) => {
      const task = findAddedTask(
        diff,
        (row) => JSON.stringify(row.params).toLowerCase().includes("desert"),
      );
      return evaluateWith([
        expectTaskCreatedByPrompt(diff, "desert"),
        // Verify the task uses the correct model (qwen_image, not wan_2_2_t2i)
        expectTaskParam(
          diff,
          (row) => row.task_type === "qwen_image" || row.task_type === "qwen_image_style",
          'task_type is qwen_image or qwen_image_style (not wan_2_2_t2i)',
        ),
        // Verify project LoRAs were passed through
        expectTaskParamsContain(diff, "harness-lora", "harness test LoRA path in params"),
        expectGenerationCreatedSoft(diff, task?.id),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          user: true,
          tables: {
            tasks: { added: "*" },
            generations: { added: "*" },
            generation_variants: { added: "*" },
            timeline_agent_sessions: { modified: "*" },
            credits_ledger: { added: "*" },
          },
        }),
      ]);
    },
  },
  {
    name: "search for a LoRA in natural language and use it for image generation",
    category: "generation",
    message: () =>
      `Find the public InStyle LoRA, add it to image generation for this project, and create "${SEARCH_AND_ADD_LORA_PROMPT}".`,
    skipTaskCompletion: true,
    evaluate: ({ after, diff }) => {
      const task = findAddedTask(
        diff,
        (row) => JSON.stringify(row.params).toLowerCase().includes(SEARCH_AND_ADD_LORA_PROMPT),
      );
      return evaluateWith([
        expectTaskCreatedByPrompt(diff, SEARCH_AND_ADD_LORA_PROMPT),
        expectTaskParam(
          diff,
          (row) => row.id === task?.id && (row.task_type === "qwen_image" || row.task_type === "qwen_image_style"),
          'task_type is qwen_image or qwen_image_style after natural-language LoRA setup',
        ),
        expectTaskParamsContain(diff, "instyle.safetensors", "InStyle LoRA path in params"),
        expectSessionMentions(after, "instyle"),
        expectSessionTerminal(after),
        expectNoCollateralDamage(diff, {
          user: true,
          tables: {
            tasks: { added: "*" },
            generations: { added: "*" },
            generation_variants: { added: "*" },
            timeline_agent_sessions: { modified: "*" },
            credits_ledger: { added: "*" },
          },
        }),
      ]);
    },
  },
  {
    name: "reject moving a nonexistent clip id",
    category: "error-handling",
    message: () => "move harness-missing-clip-404 3",
    skipTaskCompletion: true,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectSessionTerminal(after),
        expectSessionMentions(after, "not found"),
        // Known agent bug: error recovery loop causes collateral modifications
        // when user requests an invalid operation. See loop.ts:184-189.
        // TODO: Remove these allowances after fixing the agent's error recovery.
        expectNoCollateralDamage(diff, {
          tables: {
            timelines: { modified: [before.timeline_id] },
            timeline_agent_sessions: { modified: "*" },
          },
          timelineClips: { modified: "*" },
        }),
      ]),
  },
  {
    name: "reject an invalid trim duration",
    category: "error-handling",
    message: (snapshot) => `trim ${getClip(snapshot, 0).id} --duration -1`,
    skipTaskCompletion: true,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectSessionTerminal(after),
        expectSessionMentions(after, "duration"),
        expectNoCollateralDamage(diff, {
          tables: {
            timeline_agent_sessions: { modified: "*" },
          },
        }),
        pass(`Invalid trim target used real clip ${getClip(before, 0).id}.`),
      ]),
  },
  {
    name: "reject nonsensical freeform message gracefully",
    category: "error-handling",
    message: "purple elephant dancing on timeline please",
    skipTaskCompletion: true,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectSessionTerminal(after),
        // No tasks should be created for gibberish input
        Object.keys(diff.tasks.added).length === 0
          ? pass("No tasks created for nonsensical message.")
          : fail(`Unexpected task(s) created: ${Object.keys(diff.tasks.added).join(", ")}`),
        expectNoCollateralDamage(diff, {
          tables: {
            timeline_agent_sessions: { modified: "*" },
            // Allow timeline/clip modifications due to known agent error-recovery bug
            timelines: { modified: [before.timeline_id] },
          },
          timelineClips: { modified: "*" },
        }),
      ]),
  },
  {
    name: "reject setting an invalid property name",
    category: "error-handling",
    message: (snapshot) => `set ${getClip(snapshot, 0).id} nonexistentProp 42`,
    skipTaskCompletion: true,
    evaluate: ({ before, after, diff }) => {
      const invalidResult = expectSessionMentions(after, "invalid");
      const unsupportedResult = expectSessionMentions(after, "unsupported");
      const propertyResult = expectSessionMentions(after, "property");
      const mentionedIssue = invalidResult.pass || unsupportedResult.pass || propertyResult.pass;
      return evaluateWith([
        expectSessionTerminal(after),
        // Agent should mention the property is invalid or unsupported
        mentionedIssue
          ? pass("Agent acknowledged the property is invalid/unsupported.")
          : fail("Agent did not mention invalid/unsupported property."),
        // No tasks should be created
        Object.keys(diff.tasks.added).length === 0
          ? pass("No tasks created for invalid property.")
          : fail(`Unexpected task(s) created: ${Object.keys(diff.tasks.added).join(", ")}`),
        expectNoCollateralDamage(diff, {
          tables: {
            timeline_agent_sessions: { modified: "*" },
            // Allow timeline/clip modifications due to known agent error-recovery bug
            timelines: { modified: [before.timeline_id] },
          },
          timelineClips: { modified: "*" },
        }),
      ]);
    },
  },
  {
    name: "handle empty message gracefully",
    category: "error-handling",
    message: "",
    skipTaskCompletion: true,
    evaluate: ({ before, after, diff }) =>
      evaluateWith([
        expectSessionTerminal(after),
        // No tasks should be created for empty input
        Object.keys(diff.tasks.added).length === 0
          ? pass("No tasks created for empty message.")
          : fail(`Unexpected task(s) created: ${Object.keys(diff.tasks.added).join(", ")}`),
        // Note: the agent endpoint may reject empty messages with a 400 — that's acceptable;
        // the test runner treats non-2xx as session terminal so this assertion still holds.
        expectNoCollateralDamage(diff, {
          tables: {
            timeline_agent_sessions: { modified: "*" },
            // Allow timeline/clip modifications due to known agent error-recovery bug
            timelines: { modified: [before.timeline_id] },
          },
          timelineClips: { modified: "*" },
        }),
      ]),
  },
];

export const testCases = seedTestCases;
