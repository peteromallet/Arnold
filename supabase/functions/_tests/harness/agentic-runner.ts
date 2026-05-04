import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { TimelineConfig } from "../../../../src/tools/video-editor/index.ts";
import { getAdminSupabaseClient } from "./client.ts";
import { getReighAppRoot } from "./env.ts";
import { TestHarness } from "./index.ts";
import type { HarnessSnapshot } from "./snapshot.ts";
import { snapshotState } from "./snapshot.ts";
import { extractNewTaskIds } from "./waiter.ts";

type GeneratedCaseCategory = "timeline-edit" | "generation" | "error-handling";

interface AgenticRunnerOptions {
  timelineId?: string;
  rounds: number;
  dryRun: boolean;
  maxTasks: number;
}

interface GeneratedCase {
  name: string;
  category: GeneratedCaseCategory;
  message: string;
  selected_clip_indexes?: number[];
  requires_generation?: boolean;
  estimated_generation_tasks?: number;
  expected_outcome?: string;
}

interface ExecutedCaseResult {
  name: string;
  category: GeneratedCaseCategory;
  status: "executed" | "dry-run" | "skipped-budget" | "error";
  message: string;
  selected_clip_indexes: number[];
  requires_generation: boolean;
  estimated_generation_tasks: number;
  tasks_created: number;
  task_ids: string[];
  reinvocations: number;
  agent_statuses: string[];
  diff_summary?: string;
  error?: string;
}

interface RoundAnalysis {
  case_evaluations: Array<{ name: string; score: number; pass: boolean; reason: string }>;
  failure_patterns: string[];
  suggested_next_steps: string[];
}

interface RoundReport {
  round: number;
  generated_cases: GeneratedCase[];
  executed_cases: ExecutedCaseResult[];
  analysis: RoundAnalysis;
}

interface AgenticRunReport {
  generated_at: string;
  timeline_source: string;
  dry_run: boolean;
  max_tasks: number;
  tasks_used: number;
  rounds: RoundReport[];
  report_path: string;
}

function parseEnvFile(contents: string): Record<string, string> {
  const parsed: Record<string, string> = {};
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const normalized = line.startsWith("export ") ? line.slice(7) : line;
    const separatorIndex = normalized.indexOf("=");
    if (separatorIndex <= 0) continue;
    const key = normalized.slice(0, separatorIndex).trim();
    const value = normalized.slice(separatorIndex + 1).trim().replace(/^["']|["']$/g, "");
    if (key) parsed[key] = value;
  }
  return parsed;
}

function readOptionalEnvValue(key: string): string | undefined {
  const direct = process.env[key]?.trim();
  if (direct) return direct;
  const envFile = process.env.HARNESS_ENV_FILE?.trim()
    ? path.resolve(process.cwd(), process.env.HARNESS_ENV_FILE)
    : path.join(getReighAppRoot(), ".env.local");
  if (!existsSync(envFile)) return undefined;
  return parseEnvFile(readFileSync(envFile, "utf8"))[key]?.trim();
}

function parseArgs(argv: string[]): AgenticRunnerOptions | { help: true } {
  const options: AgenticRunnerOptions = { rounds: 3, dryRun: false, maxTasks: 5 };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") return { help: true };
    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (arg === "--timeline-id") {
      const value = argv[index + 1];
      if (!value) throw new Error("--timeline-id requires a value");
      options.timelineId = value;
      index += 1;
      continue;
    }
    if (arg === "--rounds") {
      const value = Number(argv[index + 1]);
      if (!Number.isInteger(value) || value < 1) throw new Error("--rounds must be a positive integer");
      options.rounds = value;
      index += 1;
      continue;
    }
    if (arg === "--max-tasks") {
      const value = Number(argv[index + 1]);
      if (!Number.isInteger(value) || value < 0) throw new Error("--max-tasks must be a non-negative integer");
      options.maxTasks = value;
      index += 1;
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }
  return options;
}

function printHelp(): void {
  console.log([
    "Usage: npx tsx reigh-app/supabase/functions/_tests/harness/agentic-runner.ts [options]",
    "",
    "Options:",
    "  --timeline-id <uuid>",
    "  --rounds <number>",
    "  --dry-run",
    "  --max-tasks <number>",
    "  --help",
    "",
    "Note: --dry-run requires --timeline-id so the runner can avoid creating temporary fixtures.",
  ].join("\n"));
}

function getTimeline(snapshot: HarnessSnapshot) {
  const timeline = snapshot.timelines[snapshot.timeline_id] ?? Object.values(snapshot.timelines)[0];
  if (!timeline) throw new Error("No timeline row found in harness snapshot.");
  return timeline;
}

function summarizeSnapshot(snapshot: HarnessSnapshot): string {
  const timeline = getTimeline(snapshot);
  const tracks = timeline.config.tracks?.map((track) => `${track.id}:${track.kind}`).join(", ") ?? "none";
  const clips = timeline.config.clips
    .slice(0, 8)
    .map((clip, index) => `- [${index}] id=${clip.id} track=${clip.track} at=${clip.at} type=${clip.clipType ?? "media"} asset=${clip.asset ?? "none"}`)
    .join("\n");
  return [
    `Timeline id: ${snapshot.timeline_id}`,
    `Tracks: ${tracks}`,
    `Clip count: ${timeline.config.clips.length}`,
    "Clips:",
    clips || "- none",
    `Existing tasks: ${Object.keys(snapshot.tasks).length}`,
    `Existing generations: ${Object.keys(snapshot.generations).length}`,
    `Existing shots: ${Object.keys(snapshot.shots).length}`,
  ].join("\n");
}

function reportPathFor(name: string): string {
  const directory = path.join(path.dirname(fileURLToPath(import.meta.url)), "reports");
  mkdirSync(directory, { recursive: true });
  const timestamp = new Date().toISOString().replaceAll(":", "-");
  return path.join(directory, `${name}-${timestamp}.json`);
}

function parseJsonResponse<T>(text: string): T {
  const cleaned = text.replace(/^```json\s*/i, "").replace(/^```\s*/i, "").replace(/\s*```$/i, "").trim();
  return JSON.parse(cleaned) as T;
}

async function callAnthropicJson<T>(system: string, prompt: string): Promise<T> {
  const apiKey = readOptionalEnvValue("ANTHROPIC_API_KEY");
  if (!apiKey) {
    throw new Error("Missing ANTHROPIC_API_KEY in the environment or harness env file.");
  }

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: readOptionalEnvValue("ANTHROPIC_MODEL") ?? "claude-3-7-sonnet-latest",
      max_tokens: 2_000,
      system,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(`Anthropic request failed: ${response.status} ${JSON.stringify(payload)}`);
  }

  const content = Array.isArray((payload as { content?: unknown }).content)
    ? ((payload as { content: Array<{ type: string; text?: string }> }).content
      .filter((block) => block.type === "text")
      .map((block) => block.text ?? "")
      .join("\n"))
    : "";
  return parseJsonResponse<T>(content);
}

async function loadBaselineContext(options: AgenticRunnerOptions): Promise<{
  snapshot: HarnessSnapshot;
  timelineConfig: TimelineConfig;
  source: string;
}> {
  if (options.timelineId) {
    const supabase = getAdminSupabaseClient();
    const { data, error } = await supabase
      .from("timelines")
      .select("id, project_id, user_id, config")
      .eq("id", options.timelineId)
      .single();
    if (error || !data?.project_id || !data?.user_id || !data?.config) {
      throw new Error(`Failed to load timeline ${options.timelineId}: ${error?.message ?? "missing timeline data"}`);
    }
    const snapshot = await snapshotState(options.timelineId, data.project_id, data.user_id);
    return { snapshot, timelineConfig: structuredClone(data.config), source: `timeline:${options.timelineId}` };
  }

  if (options.dryRun) {
    throw new Error("--dry-run requires --timeline-id so the runner does not create temporary fixtures.");
  }

  const harness = new TestHarness();
  try {
    await harness.setup();
    const snapshot = await harness.snapshot();
    return {
      snapshot,
      timelineConfig: structuredClone(getTimeline(snapshot).config),
      source: "temporary-harness-fixture",
    };
  } finally {
    await harness.teardown();
  }
}

function buildSelectedClips(snapshot: HarnessSnapshot, indexes: number[]): Array<{ clip_id: string; url: string; media_type: "image" | "video"; generation_id?: string }> {
  const timeline = getTimeline(snapshot);
  const registry = timeline.asset_registry as { assets?: Record<string, { file?: string; type?: string; generationId?: string }> };
  return indexes.flatMap((index) => {
    const clip = timeline.config.clips[index];
    const asset = clip?.asset ? registry.assets?.[clip.asset] : undefined;
    if (!clip || !asset?.file) return [];
    return [{
      clip_id: clip.id,
      url: asset.file,
      media_type: asset.type?.startsWith("video/") ? "video" : "image",
      ...(asset.generationId ? { generation_id: asset.generationId } : {}),
    }];
  });
}

async function executeGeneratedCase(
  generatedCase: GeneratedCase,
  timelineConfig: TimelineConfig,
  options: AgenticRunnerOptions,
  usedTasks: number,
): Promise<{ result: ExecutedCaseResult; taskDelta: number }> {
  const estimatedTasks = Math.max(0, generatedCase.estimated_generation_tasks ?? (generatedCase.requires_generation ? 1 : 0));
  if (generatedCase.requires_generation && usedTasks + estimatedTasks > options.maxTasks) {
    return {
      result: {
        name: generatedCase.name,
        category: generatedCase.category,
        status: "skipped-budget",
        message: generatedCase.message,
        selected_clip_indexes: generatedCase.selected_clip_indexes ?? [],
        requires_generation: Boolean(generatedCase.requires_generation),
        estimated_generation_tasks: estimatedTasks,
        tasks_created: 0,
        task_ids: [],
        reinvocations: 0,
        agent_statuses: [],
      },
      taskDelta: 0,
    };
  }

  if (options.dryRun) {
    return {
      result: {
        name: generatedCase.name,
        category: generatedCase.category,
        status: "dry-run",
        message: generatedCase.message,
        selected_clip_indexes: generatedCase.selected_clip_indexes ?? [],
        requires_generation: Boolean(generatedCase.requires_generation),
        estimated_generation_tasks: estimatedTasks,
        tasks_created: 0,
        task_ids: [],
        reinvocations: 0,
        agent_statuses: [],
      },
      taskDelta: 0,
    };
  }

  const harness = new TestHarness({ timelineConfig: structuredClone(timelineConfig) });
  try {
    await harness.setup();
    const before = await harness.snapshot();
    const responses = await harness.sendMessage(
      generatedCase.message,
      buildSelectedClips(before, generatedCase.selected_clip_indexes ?? []),
    );
    await harness.waitForSideEffects({
      taskTimeoutMs: generatedCase.requires_generation ? 180_000 : undefined,
      generationTimeoutMs: generatedCase.requires_generation ? 180_000 : undefined,
      creditsTimeoutMs: generatedCase.requires_generation ? 30_000 : undefined,
    });
    const after = await harness.snapshot();
    const diff = harness.diff(before, after);
    const taskIds = extractNewTaskIds(before, after);
    return {
      result: {
        name: generatedCase.name,
        category: generatedCase.category,
        status: "executed",
        message: generatedCase.message,
        selected_clip_indexes: generatedCase.selected_clip_indexes ?? [],
        requires_generation: Boolean(generatedCase.requires_generation),
        estimated_generation_tasks: estimatedTasks,
        tasks_created: taskIds.length,
        task_ids: taskIds,
        reinvocations: Math.max(0, responses.length - 1),
        agent_statuses: responses.map((response) => response.status),
        diff_summary: harness.summarizeDiff(diff),
      },
      taskDelta: generatedCase.requires_generation ? Math.max(estimatedTasks, taskIds.length || 1) : 0,
    };
  } catch (error) {
    return {
      result: {
        name: generatedCase.name,
        category: generatedCase.category,
        status: "error",
        message: generatedCase.message,
        selected_clip_indexes: generatedCase.selected_clip_indexes ?? [],
        requires_generation: Boolean(generatedCase.requires_generation),
        estimated_generation_tasks: estimatedTasks,
        tasks_created: 0,
        task_ids: [],
        reinvocations: 0,
        agent_statuses: [],
        error: error instanceof Error ? error.message : String(error),
      },
      taskDelta: 0,
    };
  } finally {
    await harness.teardown();
  }
}

export async function runAgenticSuite(options: AgenticRunnerOptions): Promise<AgenticRunReport> {
  const baseline = await loadBaselineContext(options);
  const rounds: RoundReport[] = [];
  let tasksUsed = 0;

  for (let round = 1; round <= options.rounds; round += 1) {
    const generated = await callAnthropicJson<{ cases: GeneratedCase[] }>(
      "You are designing timeline-agent QA cases. Return JSON only.",
      [
        `Round ${round}.`,
        `Dry run: ${options.dryRun}.`,
        `Remaining generation budget: ${Math.max(0, options.maxTasks - tasksUsed)}.`,
        "Do not propose compound generate-and-place cases.",
        "Use clip indexes from the summary when you need selected clips.",
        'Return {"cases":[...]} with up to 4 cases. Each case needs name, category, message, selected_clip_indexes, requires_generation, estimated_generation_tasks, expected_outcome.',
        summarizeSnapshot(baseline.snapshot),
      ].join("\n\n"),
    );

    const executedCases: ExecutedCaseResult[] = [];
    for (const generatedCase of generated.cases ?? []) {
      const { result, taskDelta } = await executeGeneratedCase(generatedCase, baseline.timelineConfig, options, tasksUsed);
      tasksUsed += taskDelta;
      executedCases.push(result);
    }

    const analysis = await callAnthropicJson<RoundAnalysis>(
      "You are reviewing timeline-agent QA results. Return JSON only.",
      JSON.stringify({
        dry_run: options.dryRun,
        remaining_generation_budget: Math.max(0, options.maxTasks - tasksUsed),
        generated_cases: generated.cases ?? [],
        executed_cases: executedCases,
      }, null, 2),
    );

    rounds.push({
      round,
      generated_cases: generated.cases ?? [],
      executed_cases: executedCases,
      analysis,
    });
  }

  const reportPath = reportPathFor("agentic-runner-report");
  const report: AgenticRunReport = {
    generated_at: new Date().toISOString(),
    timeline_source: baseline.source,
    dry_run: options.dryRun,
    max_tasks: options.maxTasks,
    tasks_used: tasksUsed,
    rounds,
    report_path: reportPath,
  };
  writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.table(rounds.map((round) => ({
    round: round.round,
    generated_cases: round.generated_cases.length,
    executed_cases: round.executed_cases.length,
    failure_patterns: round.analysis.failure_patterns.length,
    suggested_next_steps: round.analysis.suggested_next_steps.length,
  })));
  console.log(`Wrote agentic report to ${reportPath}`);
  return report;
}

async function main(): Promise<void> {
  const parsed = parseArgs(process.argv.slice(2));
  if ("help" in parsed) {
    printHelp();
    return;
  }
  await runAgenticSuite(parsed);
}

const entryPath = process.argv[1] ? path.resolve(process.argv[1]) : null;
if (entryPath && fileURLToPath(import.meta.url) === entryPath) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.stack ?? error.message : String(error));
    process.exitCode = 1;
  });
}
