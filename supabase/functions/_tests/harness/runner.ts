import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  resolveCaseMessage,
  resolveCaseSelectedClips,
  testCases,
  type TestCase,
  type TestCaseCategory,
} from "./cases.ts";
import { TestHarness } from "./index.ts";
import type { AssertionResult } from "./evaluate.ts";
import { extractNewTaskIds } from "./waiter.ts";

export interface RunTestSuiteOptions {
  category?: TestCaseCategory;
  caseName?: string;
  skipGenerations?: boolean;
  reportDir?: string;
}

export interface TestCaseRunResult {
  name: string;
  category: TestCaseCategory;
  status: "passed" | "failed" | "error";
  score: number;
  passed: number;
  failed: number;
  wall_time_ms: number;
  reinvocations: number;
  tasks_created: number;
  task_ids: string[];
  assertion_details: AssertionResult[];
  agent_statuses: string[];
  diff_summary?: string;
  error?: string;
}

export interface TestSuiteReport {
  generated_at: string;
  filters: {
    category?: TestCaseCategory;
    caseName?: string;
    skipGenerations: boolean;
  };
  totals: {
    total: number;
    passed: number;
    failed: number;
    errored: number;
  };
  results: TestCaseRunResult[];
  report_path: string;
}

function parseArgs(argv: string[]): RunTestSuiteOptions | { help: true } {
  const options: RunTestSuiteOptions = {};

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      return { help: true };
    }
    if (arg === "--skip-generations") {
      options.skipGenerations = true;
      continue;
    }
    if (arg === "--category") {
      const value = argv[index + 1];
      if (!value || (value !== "timeline-edit" && value !== "generation" && value !== "error-handling")) {
        throw new Error("--category must be one of: timeline-edit, generation, error-handling");
      }
      options.category = value;
      index += 1;
      continue;
    }
    if (arg === "--case") {
      const value = argv[index + 1];
      if (!value) {
        throw new Error("--case requires a value");
      }
      options.caseName = value;
      index += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function printHelp(): void {
  console.log(
    [
      "Usage: npx tsx reigh-app/supabase/functions/_tests/harness/runner.ts [options]",
      "",
      "Options:",
      "  --category <timeline-edit|generation|error-handling>",
      "  --case <name-fragment>",
      "  --skip-generations",
      "  --help",
    ].join("\n"),
  );
}

function filterCases(cases: TestCase[], options: RunTestSuiteOptions): TestCase[] {
  return cases.filter((testCase) => {
    if (options.category && testCase.category !== options.category) {
      return false;
    }
    if (options.caseName) {
      return testCase.name.toLowerCase().includes(options.caseName.toLowerCase());
    }
    return true;
  });
}

function createReportPath(reportDir?: string): string {
  const directory = reportDir
    ?? path.join(path.dirname(fileURLToPath(import.meta.url)), "reports");
  mkdirSync(directory, { recursive: true });
  const timestamp = new Date().toISOString().replaceAll(":", "-");
  return path.join(directory, `runner-report-${timestamp}.json`);
}

function summarizeResults(results: TestCaseRunResult[]) {
  const passed = results.filter((result) => result.status === "passed").length;
  const failed = results.filter((result) => result.status === "failed").length;
  const errored = results.filter((result) => result.status === "error").length;
  return {
    total: results.length,
    passed,
    failed,
    errored,
  };
}

async function runSingleCase(
  testCase: TestCase,
  options: RunTestSuiteOptions,
): Promise<TestCaseRunResult> {
  const harness = new TestHarness();
  const startedAt = Date.now();

  try {
    await harness.setup();
    const before = await harness.snapshot();
    await testCase.setup?.(before);

    const message = resolveCaseMessage(testCase, before);
    const selectedClips = resolveCaseSelectedClips(testCase, before);
    const responses = await harness.sendMessage(message, selectedClips);

    if (!options.skipGenerations && !testCase.skipTaskCompletion) {
      await harness.waitForSideEffects({
        taskTimeoutMs: testCase.timeoutMs,
        generationTimeoutMs: testCase.timeoutMs,
        creditsTimeoutMs: testCase.timeoutMs ? Math.min(testCase.timeoutMs, 30_000) : undefined,
      });
    }

    const after = await harness.snapshot();
    const diff = harness.diff(before, after);
    const evaluation = testCase.evaluate({ before, after, diff });
    const taskIds = extractNewTaskIds(before, after);
    const status = evaluation.failed === 0 ? "passed" : "failed";

    return {
      name: testCase.name,
      category: testCase.category,
      status,
      score: evaluation.score,
      passed: evaluation.passed,
      failed: evaluation.failed,
      wall_time_ms: Date.now() - startedAt,
      reinvocations: Math.max(0, responses.length - 1),
      tasks_created: taskIds.length,
      task_ids: taskIds,
      assertion_details: evaluation.details,
      agent_statuses: responses.map((response) => response.status),
      diff_summary: harness.summarizeDiff(diff),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      name: testCase.name,
      category: testCase.category,
      status: "error",
      score: 0,
      passed: 0,
      failed: 1,
      wall_time_ms: Date.now() - startedAt,
      reinvocations: 0,
      tasks_created: 0,
      task_ids: [],
      assertion_details: [{ pass: false, reason: message }],
      agent_statuses: [],
      error: message,
    };
  } finally {
    await harness.teardown();
  }
}

export async function runTestSuite(
  cases: TestCase[],
  options: RunTestSuiteOptions = {},
): Promise<TestSuiteReport> {
  const selectedCases = filterCases(cases, options);
  const results: TestCaseRunResult[] = [];

  for (const testCase of selectedCases) {
    results.push(await runSingleCase(testCase, options));
  }

  const reportPath = createReportPath(options.reportDir);
  const report: TestSuiteReport = {
    generated_at: new Date().toISOString(),
    filters: {
      ...(options.category ? { category: options.category } : {}),
      ...(options.caseName ? { caseName: options.caseName } : {}),
      skipGenerations: Boolean(options.skipGenerations),
    },
    totals: summarizeResults(results),
    results,
    report_path: reportPath,
  };

  writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");

  console.table(results.map((result) => ({
    case: result.name,
    category: result.category,
    status: result.status,
    score: result.score,
    passed: result.passed,
    failed: result.failed,
    wall_ms: result.wall_time_ms,
    reinvocations: result.reinvocations,
    tasks_created: result.tasks_created,
  })));
  console.log(`Wrote runner report to ${reportPath}`);

  return report;
}

async function main(): Promise<void> {
  const parsed = parseArgs(process.argv.slice(2));
  if ("help" in parsed) {
    printHelp();
    return;
  }

  await runTestSuite(testCases, parsed);
}

const entryPath = process.argv[1] ? path.resolve(process.argv[1]) : null;
if (entryPath && fileURLToPath(import.meta.url) === entryPath) {
  main().catch((error) => {
    const message = error instanceof Error ? error.stack ?? error.message : String(error);
    console.error(message);
    process.exitCode = 1;
  });
}
