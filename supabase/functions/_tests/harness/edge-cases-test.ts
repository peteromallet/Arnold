/**
 * Edge-cases stress test for the timeline agent harness.
 *
 * Tests: very long messages, unicode/emoji text clips, rapid-fire concurrency,
 * repeat/batch syntax, find-issues command, and large property values.
 *
 * Run:
 *   cd reigh-app && npx tsx supabase/functions/_tests/harness/edge-cases-test.ts
 */

import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { TestHarness } from "./index.ts";
import type { AgentCallResponse } from "./client.ts";
import type { HarnessSnapshot } from "./snapshot.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EdgeCaseResult {
  name: string;
  status: "pass" | "fail" | "error";
  wall_time_ms: number;
  findings: string[];
  error?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTimeline(snapshot: HarnessSnapshot) {
  const tl = snapshot.timelines[snapshot.timeline_id] ?? Object.values(snapshot.timelines)[0];
  if (!tl) throw new Error("No timeline in snapshot");
  return tl;
}

function getClips(snapshot: HarnessSnapshot) {
  return getTimeline(snapshot).config.clips;
}

function getSessionTurnsText(snapshot: HarnessSnapshot): string {
  return JSON.stringify(
    Object.values(snapshot.timeline_agent_sessions).map((s) => s.turns),
  ).toLowerCase();
}

function elapsed(start: number): number {
  return Date.now() - start;
}

// ---------------------------------------------------------------------------
// Test 1 — Very long message (500+ words)
// ---------------------------------------------------------------------------

async function testVeryLongMessage(): Promise<EdgeCaseResult> {
  const name = "very-long-message";
  const start = Date.now();
  const findings: string[] = [];
  const harness = new TestHarness();

  try {
    await harness.setup();
    const before = await harness.snapshot();

    // Build a 500+ word message with legitimate instructions embedded
    const filler = Array.from({ length: 50 }, (_, i) =>
      `Instruction block ${i + 1}: please note that the timeline should maintain high quality and consistency throughout all clips, ensuring smooth transitions and proper timing alignment.`,
    ).join(" ");
    const longMessage = `Move the first clip to position 5. ${filler} That is all.`;
    const wordCount = longMessage.split(/\s+/).length;
    findings.push(`Message word count: ${wordCount}`);

    let responses: AgentCallResponse[];
    try {
      responses = await harness.sendMessage(longMessage);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      findings.push(`sendMessage threw: ${msg}`);
      return { name, status: "fail", wall_time_ms: elapsed(start), findings, error: msg };
    }

    const after = await harness.snapshot();
    const diff = harness.diff(before, after);

    const statuses = responses.map((r) => r.status);
    findings.push(`Agent statuses: ${statuses.join(", ")}`);
    findings.push(`HTTP statuses: ${responses.map((r) => r.httpStatus).join(", ")}`);

    const terminalStatuses = new Set(["waiting_user", "done", "error", "cancelled"]);
    const lastStatus = statuses[statuses.length - 1];
    if (!terminalStatuses.has(lastStatus)) {
      findings.push(`WARNING: agent did not reach terminal state (last=${lastStatus})`);
    }

    // Check if the agent actually attempted the move
    const clip0Id = getClips(before)[0]?.id;
    const clipMoved = Object.values(diff.timelines.modified).some((row) => {
      if (!("clip_changes" in row)) return false;
      const mod = row.clip_changes.modified[clip0Id];
      return mod && !("clip_changes" in mod);
    });
    findings.push(`First clip move attempted: ${clipMoved}`);
    findings.push(`Diff summary:\n${harness.summarizeDiff(diff)}`);

    return { name, status: "pass", wall_time_ms: elapsed(start), findings };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    findings.push(`Unexpected error: ${msg}`);
    return { name, status: "error", wall_time_ms: elapsed(start), findings, error: msg };
  } finally {
    await harness.teardown();
  }
}

// ---------------------------------------------------------------------------
// Test 2 — Unicode/emoji in text clips
// ---------------------------------------------------------------------------

async function testUnicodeEmojiTextClip(): Promise<EdgeCaseResult> {
  const name = "unicode-emoji-text-clip";
  const start = Date.now();
  const findings: string[] = [];
  const harness = new TestHarness();

  try {
    await harness.setup();
    const before = await harness.snapshot();

    const unicodeContent = "\u{1F3AC} Premi\u00E8re Sc\u00E8ne \u2014 d\u00E9but";
    const message = `Add a text clip saying '${unicodeContent}' at 0s for 3 seconds`;
    findings.push(`Message: ${message}`);

    let responses: AgentCallResponse[];
    try {
      responses = await harness.sendMessage(message);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      findings.push(`sendMessage threw: ${msg}`);
      return { name, status: "fail", wall_time_ms: elapsed(start), findings, error: msg };
    }

    const after = await harness.snapshot();
    const diff = harness.diff(before, after);

    const statuses = responses.map((r) => r.status);
    findings.push(`Agent statuses: ${statuses.join(", ")}`);

    // Check for added text clips
    let textClipFound = false;
    let contentMatch = false;
    for (const row of Object.values(diff.timelines.modified)) {
      if (!("clip_changes" in row)) continue;
      for (const clip of Object.values(row.clip_changes.added)) {
        if (clip.clipType === "text") {
          textClipFound = true;
          const content = clip.text?.content ?? "";
          findings.push(`Text clip content: "${content}"`);
          // Check if the unicode content survived the round-trip
          if (content.includes("\u{1F3AC}") || content.includes("Premi\u00E8re") || content.includes("d\u00E9but")) {
            contentMatch = true;
            findings.push("Unicode content preserved correctly");
          } else {
            findings.push("WARNING: Unicode content may have been mangled");
          }
        }
      }
    }

    if (!textClipFound) {
      findings.push("FAIL: No text clip was added");
      return { name, status: "fail", wall_time_ms: elapsed(start), findings };
    }

    findings.push(`Diff summary:\n${harness.summarizeDiff(diff)}`);

    return {
      name,
      status: contentMatch ? "pass" : "fail",
      wall_time_ms: elapsed(start),
      findings,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    findings.push(`Unexpected error: ${msg}`);
    return { name, status: "error", wall_time_ms: elapsed(start), findings, error: msg };
  } finally {
    await harness.teardown();
  }
}

// ---------------------------------------------------------------------------
// Test 3 — Rapid-fire concurrent requests
// ---------------------------------------------------------------------------

async function testRapidFireConcurrent(): Promise<EdgeCaseResult> {
  const name = "rapid-fire-concurrent";
  const start = Date.now();
  const findings: string[] = [];
  const harness = new TestHarness();

  try {
    await harness.setup();
    const before = await harness.snapshot();

    const messages = [
      "Move the first clip to position 2",
      "Add a text clip saying 'concurrent-test-A' at 0s for 1 second",
      "Set the second clip's opacity to 0.5",
    ];

    findings.push(`Firing ${messages.length} concurrent callAgentOnce requests...`);

    // Fire all 3 at the same time using callAgentOnce (no waiting between)
    const results = await Promise.allSettled(
      messages.map((msg) =>
        harness.callAgentOnce(msg),
      ),
    );

    const fulfilled: AgentCallResponse[] = [];
    const rejected: string[] = [];

    for (let i = 0; i < results.length; i++) {
      const result = results[i];
      if (result.status === "fulfilled") {
        fulfilled.push(result.value);
        findings.push(`Request ${i + 1} ("${messages[i].slice(0, 40)}..."): HTTP ${result.value.httpStatus}, status=${result.value.status}`);
      } else {
        const reason = result.reason instanceof Error ? result.reason.message : String(result.reason);
        rejected.push(reason);
        findings.push(`Request ${i + 1} ("${messages[i].slice(0, 40)}..."): REJECTED — ${reason}`);
      }
    }

    // Check for 409 conflicts
    const conflicts = fulfilled.filter((r) => r.httpStatus === 409);
    findings.push(`409 conflicts: ${conflicts.length}`);
    findings.push(`Fulfilled: ${fulfilled.length}, Rejected: ${rejected.length}`);

    // Check if the session is still usable after concurrent access
    const after = await harness.snapshot();
    const sessions = Object.values(after.timeline_agent_sessions);
    const sessionStatuses = sessions.map((s) => s.status);
    findings.push(`Session statuses after concurrent requests: ${sessionStatuses.join(", ")}`);

    // Check for corruption: is the session in a bad state?
    const corrupted = sessionStatuses.some((s) => s === "processing" || s === "continue");
    if (corrupted) {
      findings.push("WARNING: Session may be stuck in non-terminal state after concurrent requests");
    }

    const diff = harness.diff(before, after);
    findings.push(`Diff summary:\n${harness.summarizeDiff(diff)}`);

    // This test passes if we didn't hard-crash — the findings are the value
    return {
      name,
      status: rejected.length === results.length ? "fail" : "pass",
      wall_time_ms: elapsed(start),
      findings,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    findings.push(`Unexpected error: ${msg}`);
    return { name, status: "error", wall_time_ms: elapsed(start), findings, error: msg };
  } finally {
    await harness.teardown();
  }
}

// ---------------------------------------------------------------------------
// Test 4 — Repeat/batch command
// ---------------------------------------------------------------------------

async function testRepeatCommand(): Promise<EdgeCaseResult> {
  const name = "repeat-batch-command";
  const start = Date.now();
  const findings: string[] = [];
  const harness = new TestHarness();

  try {
    await harness.setup();
    const before = await harness.snapshot();
    const clipsBefore = getClips(before).length;
    findings.push(`Clips before: ${clipsBefore}`);

    const message = "repeat 5 add-text V1 {i} 0.5 'count-{i}' --start 0 --gap 0.5";
    findings.push(`Message: ${message}`);

    let responses: AgentCallResponse[];
    try {
      responses = await harness.sendMessage(message);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      findings.push(`sendMessage threw: ${msg}`);
      return { name, status: "fail", wall_time_ms: elapsed(start), findings, error: msg };
    }

    const after = await harness.snapshot();
    const diff = harness.diff(before, after);

    const statuses = responses.map((r) => r.status);
    findings.push(`Agent statuses: ${statuses.join(", ")}`);
    findings.push(`Reinvocations: ${responses.length - 1}`);

    // Count new text clips
    let addedTextClips = 0;
    for (const row of Object.values(diff.timelines.modified)) {
      if (!("clip_changes" in row)) continue;
      for (const clip of Object.values(row.clip_changes.added)) {
        if (clip.clipType === "text") {
          addedTextClips++;
          findings.push(`  Added text clip: "${clip.text?.content}" at=${clip.at}`);
        }
      }
    }

    const clipsAfter = getClips(after).length;
    findings.push(`Clips after: ${clipsAfter}`);
    findings.push(`Text clips added: ${addedTextClips}`);

    if (addedTextClips === 5) {
      findings.push("All 5 text clips created as expected");
    } else if (addedTextClips > 0) {
      findings.push(`WARNING: Expected 5 text clips but got ${addedTextClips}`);
    } else {
      findings.push("FAIL: No text clips were added — agent may not support repeat syntax");
    }

    // Check session turns for how the agent interpreted the command
    const turnsText = getSessionTurnsText(after);
    if (turnsText.includes("repeat")) {
      findings.push("Agent acknowledged 'repeat' in conversation");
    }

    findings.push(`Diff summary:\n${harness.summarizeDiff(diff)}`);

    return {
      name,
      status: addedTextClips >= 5 ? "pass" : "fail",
      wall_time_ms: elapsed(start),
      findings,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    findings.push(`Unexpected error: ${msg}`);
    return { name, status: "error", wall_time_ms: elapsed(start), findings, error: msg };
  } finally {
    await harness.teardown();
  }
}

// ---------------------------------------------------------------------------
// Test 5 — Find-issues after creating a gap
// ---------------------------------------------------------------------------

async function testFindIssuesWithGap(): Promise<EdgeCaseResult> {
  const name = "find-issues-with-gap";
  const start = Date.now();
  const findings: string[] = [];
  const harness = new TestHarness();

  try {
    await harness.setup();

    // Step 1: Move clip 1 to position 10 to create a gap
    const snapBefore = await harness.snapshot();
    const clip1 = getClips(snapBefore)[1];
    if (!clip1) {
      findings.push("SKIP: Timeline has fewer than 2 clips");
      return { name, status: "error", wall_time_ms: elapsed(start), findings };
    }

    findings.push(`Moving clip ${clip1.id} from ${clip1.at}s to 10s to create a gap...`);

    let moveResponses: AgentCallResponse[];
    try {
      moveResponses = await harness.sendMessage(`move ${clip1.id} 10`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      findings.push(`Move sendMessage threw: ${msg}`);
      return { name, status: "fail", wall_time_ms: elapsed(start), findings, error: msg };
    }

    findings.push(`Move statuses: ${moveResponses.map((r) => r.status).join(", ")}`);

    const afterMove = await harness.snapshot();
    const clipsAfterMove = getClips(afterMove);
    findings.push(`Clips after move: ${clipsAfterMove.map((c) => `${c.id}@${c.at}s`).join(", ")}`);

    // Step 2: Send find-issues
    findings.push("Sending 'find-issues' command...");

    let issueResponses: AgentCallResponse[];
    try {
      issueResponses = await harness.sendMessage("find-issues");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      findings.push(`find-issues sendMessage threw: ${msg}`);
      return { name, status: "fail", wall_time_ms: elapsed(start), findings, error: msg };
    }

    findings.push(`find-issues statuses: ${issueResponses.map((r) => r.status).join(", ")}`);

    const afterIssues = await harness.snapshot();
    const turnsText = getSessionTurnsText(afterIssues);

    // Check if the agent mentioned the gap
    const mentionsGap = turnsText.includes("gap")
      || turnsText.includes("empty")
      || turnsText.includes("space")
      || turnsText.includes("discontin");

    findings.push(`Agent mentions gap/empty/space: ${mentionsGap}`);

    // Extract the agent's response about issues
    const sessions = Object.values(afterIssues.timeline_agent_sessions);
    for (const session of sessions) {
      if (Array.isArray(session.turns)) {
        const assistantTurns = (session.turns as Array<{ role?: string; content?: string }>)
          .filter((t) => t.role === "assistant" && t.content);
        const lastAssistant = assistantTurns[assistantTurns.length - 1];
        if (lastAssistant?.content) {
          findings.push(`Last assistant response (truncated): ${lastAssistant.content.slice(0, 300)}`);
        }
      }
    }

    return {
      name,
      status: mentionsGap ? "pass" : "fail",
      wall_time_ms: elapsed(start),
      findings,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    findings.push(`Unexpected error: ${msg}`);
    return { name, status: "error", wall_time_ms: elapsed(start), findings, error: msg };
  } finally {
    await harness.teardown();
  }
}

// ---------------------------------------------------------------------------
// Test 6 — Large property value
// ---------------------------------------------------------------------------

async function testLargePropertyValue(): Promise<EdgeCaseResult> {
  const name = "large-property-value";
  const start = Date.now();
  const findings: string[] = [];
  const harness = new TestHarness();

  try {
    await harness.setup();
    const before = await harness.snapshot();

    const clip0 = getClips(before)[0];
    if (!clip0) {
      findings.push("SKIP: No clips in timeline");
      return { name, status: "error", wall_time_ms: elapsed(start), findings };
    }

    findings.push(`Clip ${clip0.id} current x=${clip0.x}`);

    const message = `Set ${clip0.id} x 99999`;
    findings.push(`Message: ${message}`);

    let responses: AgentCallResponse[];
    try {
      responses = await harness.sendMessage(message);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      findings.push(`sendMessage threw: ${msg}`);
      return { name, status: "fail", wall_time_ms: elapsed(start), findings, error: msg };
    }

    const after = await harness.snapshot();
    const diff = harness.diff(before, after);

    const statuses = responses.map((r) => r.status);
    findings.push(`Agent statuses: ${statuses.join(", ")}`);

    // Check what happened to the clip's x value
    const afterClip0 = getClips(after).find((c) => c.id === clip0.id);
    if (afterClip0) {
      findings.push(`Clip ${clip0.id} x after: ${afterClip0.x}`);
      if (afterClip0.x === 99999) {
        findings.push("Agent set x to 99999 without validation");
      } else if (afterClip0.x === clip0.x) {
        findings.push("Agent did NOT change x — may have rejected the value");
      } else {
        findings.push(`Agent set x to ${afterClip0.x} — possibly clamped or adjusted`);
      }
    } else {
      findings.push("WARNING: Clip disappeared after command");
    }

    // Check if the agent mentioned anything about the value being too large
    const turnsText = getSessionTurnsText(after);
    const mentionsLimit = turnsText.includes("out of range")
      || turnsText.includes("too large")
      || turnsText.includes("invalid")
      || turnsText.includes("clamp")
      || turnsText.includes("maximum")
      || turnsText.includes("bounds");
    findings.push(`Agent mentioned limits/validation: ${mentionsLimit}`);

    findings.push(`Diff summary:\n${harness.summarizeDiff(diff)}`);

    // Pass either way — we're interested in the behavior, not enforcing a specific outcome
    return { name, status: "pass", wall_time_ms: elapsed(start), findings };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    findings.push(`Unexpected error: ${msg}`);
    return { name, status: "error", wall_time_ms: elapsed(start), findings, error: msg };
  } finally {
    await harness.teardown();
  }
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  console.log("=== Edge-Cases Stress Test ===\n");

  const tests = [
    testVeryLongMessage,
    testUnicodeEmojiTextClip,
    testRapidFireConcurrent,
    testRepeatCommand,
    testFindIssuesWithGap,
    testLargePropertyValue,
  ];

  const results: EdgeCaseResult[] = [];

  for (const testFn of tests) {
    console.log(`--- Running: ${testFn.name} ---`);
    const result = await testFn();
    results.push(result);
    console.log(`  Status: ${result.status} (${result.wall_time_ms}ms)`);
    for (const finding of result.findings) {
      for (const line of finding.split("\n")) {
        console.log(`  ${line}`);
      }
    }
    if (result.error) {
      console.log(`  Error: ${result.error}`);
    }
    console.log();
  }

  // Summary table
  console.log("=== Summary ===");
  console.table(
    results.map((r) => ({
      test: r.name,
      status: r.status,
      wall_ms: r.wall_time_ms,
      findings: r.findings.length,
    })),
  );

  // Write JSON report
  const reportDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "reports");
  mkdirSync(reportDir, { recursive: true });
  const timestamp = new Date().toISOString().replaceAll(":", "-");
  const reportPath = path.join(reportDir, `edge-cases-report-${timestamp}.json`);
  writeFileSync(reportPath, JSON.stringify({ generated_at: new Date().toISOString(), results }, null, 2) + "\n", "utf8");
  console.log(`\nWrote report to ${reportPath}`);

  // Exit with failure if any test errored
  const hasErrors = results.some((r) => r.status === "error");
  const hasFails = results.some((r) => r.status === "fail");
  if (hasErrors) {
    console.log("\nSome tests errored — see findings above.");
    process.exitCode = 1;
  } else if (hasFails) {
    console.log("\nSome tests failed — these are the interesting findings.");
  } else {
    console.log("\nAll tests passed.");
  }
}

const entryPath = process.argv[1] ? path.resolve(process.argv[1]) : null;
if (entryPath && fileURLToPath(import.meta.url) === entryPath) {
  main().catch((err) => {
    console.error(err instanceof Error ? err.stack ?? err.message : String(err));
    process.exitCode = 1;
  });
}
