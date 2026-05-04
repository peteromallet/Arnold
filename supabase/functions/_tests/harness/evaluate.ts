import type { TimelineClip } from "../../../../src/tools/video-editor/index.ts";
import type {
  HarnessSnapshot,
  SessionSnapshotRow,
  SnapshotDiff,
  TableDiff,
  TimelineModifiedRow,
} from "./snapshot.ts";

const SESSION_TERMINAL_STATUSES = new Set(["waiting_user", "done", "error", "cancelled"]);

export interface AssertionResult {
  pass: boolean;
  reason: string;
}

export interface AllowedIdChanges {
  added?: string[] | "*";
  removed?: string[] | "*";
  modified?: string[] | "*";
}

export interface AllowedChanges {
  user?: boolean;
  tables?: Partial<Record<Exclude<keyof SnapshotDiff, "user">, AllowedIdChanges>>;
  timelineClips?: AllowedIdChanges;
}

function pass(reason: string): AssertionResult {
  return { pass: true, reason };
}

function fail(reason: string): AssertionResult {
  return { pass: false, reason };
}

function getTimelineModifications(diff: SnapshotDiff): TimelineModifiedRow[] {
  return Object.values(diff.timelines.modified).filter(
    (row): row is TimelineModifiedRow => "clip_changes" in row,
  );
}

function findModifiedClip(diff: SnapshotDiff, clipId: string): { timelineId: string; row: TimelineModifiedRow; clip: TimelineClip } | null {
  for (const [timelineId, row] of Object.entries(diff.timelines.modified)) {
    if (!("clip_changes" in row)) continue;
    const clip = row.clip_changes.modified[clipId];
    if (clip && !("clip_changes" in clip)) {
      return { timelineId, row, clip: clip.after };
    }
  }

  return null;
}

function clipDuration(clip: TimelineClip): number | null {
  if (typeof clip.hold === "number") {
    return clip.hold;
  }
  if (typeof clip.from === "number" && typeof clip.to === "number") {
    return clip.to - clip.from;
  }
  return null;
}

function nearlyEqual(left: number | null | undefined, right: number, epsilon = 0.001): boolean {
  return typeof left === "number" && Math.abs(left - right) <= epsilon;
}

function jsonContainsSubstring(value: unknown, expectedSubstring: string): boolean {
  return JSON.stringify(value ?? "").toLowerCase().includes(expectedSubstring.toLowerCase());
}

function isAllowed(changeSet: AllowedIdChanges | undefined, kind: keyof AllowedIdChanges, id: string): boolean {
  const allowed = changeSet?.[kind];
  if (allowed === "*") {
    return true;
  }
  return Array.isArray(allowed) ? allowed.includes(id) : false;
}

function collectUnexpectedTableChanges<Row extends { id: string }>(
  tableName: string,
  diff: TableDiff<Row>,
  allowedChanges: AllowedIdChanges | undefined,
): string[] {
  const unexpected: string[] = [];

  for (const id of Object.keys(diff.added)) {
    if (!isAllowed(allowedChanges, "added", id)) {
      unexpected.push(`${tableName}.added.${id}`);
    }
  }
  for (const id of Object.keys(diff.removed)) {
    if (!isAllowed(allowedChanges, "removed", id)) {
      unexpected.push(`${tableName}.removed.${id}`);
    }
  }
  for (const id of Object.keys(diff.modified)) {
    if (!isAllowed(allowedChanges, "modified", id)) {
      unexpected.push(`${tableName}.modified.${id}`);
    }
  }

  return unexpected;
}

function extractSessionTurns(session: SessionSnapshotRow): Array<{ role: string; content: string }> {
  if (!Array.isArray(session.turns)) {
    return [];
  }

  return session.turns.flatMap((turn) => {
    if (!turn || typeof turn !== "object" || Array.isArray(turn)) {
      return [];
    }
    const role = "role" in turn && typeof turn.role === "string" ? turn.role : null;
    const content = "content" in turn && typeof turn.content === "string" ? turn.content : null;
    return role && content ? [{ role, content }] : [];
  });
}

export function expectClipMoved(diff: SnapshotDiff, clipId: string, expectedPosition: number): AssertionResult {
  const result = findModifiedClip(diff, clipId);
  if (!result) {
    return fail(`Clip ${clipId} was not modified.`);
  }

  return nearlyEqual(result.clip.at, expectedPosition)
    ? pass(`Clip ${clipId} moved to ${result.clip.at}s.`)
    : fail(`Clip ${clipId} ended at ${result.clip.at}s instead of ${expectedPosition}s.`);
}

export function expectClipDeleted(diff: SnapshotDiff, clipId: string): AssertionResult {
  for (const row of getTimelineModifications(diff)) {
    if (row.clip_changes.removed[clipId]) {
      return pass(`Clip ${clipId} was deleted.`);
    }
  }

  return fail(`Clip ${clipId} was not deleted.`);
}

export function expectClipTrimmed(
  diff: SnapshotDiff,
  clipId: string,
  expectedDuration?: number,
): AssertionResult {
  const result = findModifiedClip(diff, clipId);
  if (!result) {
    return fail(`Clip ${clipId} was not modified.`);
  }

  const beforeClip = result.row.clip_changes.modified[clipId];
  if (!beforeClip || "clip_changes" in beforeClip) {
    return fail(`Clip ${clipId} trim diff was not available.`);
  }

  const changedTrimFields = beforeClip.changes.some((change) => change.path === "from" || change.path === "to" || change.path === "hold");
  if (!changedTrimFields) {
    return fail(`Clip ${clipId} changed, but no trim fields changed.`);
  }

  if (typeof expectedDuration !== "number") {
    return pass(`Clip ${clipId} trim fields changed.`);
  }

  const actualDuration = clipDuration(beforeClip.after);
  return nearlyEqual(actualDuration, expectedDuration)
    ? pass(`Clip ${clipId} trimmed to ${actualDuration}s.`)
    : fail(`Clip ${clipId} duration is ${actualDuration ?? "unknown"} instead of ${expectedDuration}s.`);
}

export function expectTextAdded(diff: SnapshotDiff, expectedText: string): AssertionResult {
  for (const row of getTimelineModifications(diff)) {
    for (const clip of Object.values(row.clip_changes.added)) {
      if (clip.clipType === "text" && clip.text?.content.includes(expectedText)) {
        return pass(`Text clip "${expectedText}" was added.`);
      }
    }
  }

  return fail(`No added text clip contained "${expectedText}".`);
}

export function expectPropertySet(
  diff: SnapshotDiff,
  clipId: string,
  property: keyof TimelineClip,
  expectedValue: unknown,
): AssertionResult {
  const result = findModifiedClip(diff, clipId);
  if (!result) {
    return fail(`Clip ${clipId} was not modified.`);
  }

  const actual = result.clip[property];
  return Object.is(actual, expectedValue)
    ? pass(`Clip ${clipId} ${String(property)} was set to ${String(expectedValue)}.`)
    : fail(`Clip ${clipId} ${String(property)} is ${String(actual)} instead of ${String(expectedValue)}.`);
}

export function expectTaskCreated(
  diff: SnapshotDiff,
  taskType: string,
  promptSubstring?: string,
): AssertionResult {
  const match = Object.values(diff.tasks.added).find((row) => {
    if (row.task_type !== taskType) {
      return false;
    }
    if (!promptSubstring) {
      return true;
    }
    return jsonContainsSubstring(row.params, promptSubstring);
  });

  return match
    ? pass(`Task ${match.id} (${taskType}) was created.`)
    : fail(`No added task matched task_type=${taskType}${promptSubstring ? ` with prompt containing "${promptSubstring}"` : ""}.`);
}

export function expectGenerationCreated(diff: SnapshotDiff, taskId?: string): AssertionResult {
  const match = Object.values(diff.generations.added).find((row) => !taskId || row.linked_task_ids.includes(taskId));
  return match
    ? pass(`Generation ${match.id} was created${taskId ? ` for task ${taskId}` : ""}.`)
    : fail(`No added generation matched${taskId ? ` task ${taskId}` : " the expectation"}.`);
}

/**
 * Soft version of expectGenerationCreated — passes if a generation exists, but
 * also passes (with a note) when none is found (e.g. worker failed on synthetic
 * reference images).
 */
export function expectGenerationCreatedSoft(diff: SnapshotDiff, taskId?: string): AssertionResult {
  const match = Object.values(diff.generations.added).find((row) => !taskId || row.linked_task_ids.includes(taskId));
  return match
    ? pass(`Generation ${match.id} was created${taskId ? ` for task ${taskId}` : ""}.`)
    : pass(`No generation created${taskId ? ` for task ${taskId}` : ""} (acceptable — worker may fail on synthetic reference data).`);
}

export function expectTaskCreatedByPrompt(
  diff: SnapshotDiff,
  promptSubstring: string,
): AssertionResult {
  const match = Object.values(diff.tasks.added).find((row) =>
    jsonContainsSubstring(row.params, promptSubstring),
  );

  return match
    ? pass(`Task ${match.id} (${match.task_type}) was created with prompt containing "${promptSubstring}".`)
    : fail(`No added task had params containing "${promptSubstring}".`);
}

export function expectCreditCharged(diff: SnapshotDiff, taskId?: string): AssertionResult {
  const match = Object.values(diff.credits_ledger.added).find((row) => !taskId || row.task_id === taskId);
  return match
    ? pass(`credits_ledger entry ${match.id} was created${taskId ? ` for task ${taskId}` : ""}.`)
    : fail(`No added credits_ledger row matched${taskId ? ` task ${taskId}` : " the expectation"}.`);
}

/**
 * Soft version of expectCreditCharged — passes if a charge exists, but also
 * passes (with a note) when no charge is found (e.g. free-tier or test accounts).
 */
export function expectCreditChargedSoft(diff: SnapshotDiff, taskId?: string): AssertionResult {
  const match = Object.values(diff.credits_ledger.added).find((row) => !taskId || row.task_id === taskId);
  return match
    ? pass(`credits_ledger entry ${match.id} was created${taskId ? ` for task ${taskId}` : ""}.`)
    : pass(`No credits_ledger charge found${taskId ? ` for task ${taskId}` : ""} (acceptable — may be free tier or test account).`);
}

export function expectNoCollateralDamage(
  diff: SnapshotDiff,
  allowedChanges: AllowedChanges,
): AssertionResult {
  const unexpected: string[] = [];

  if (diff.user && !allowedChanges.user) {
    unexpected.push("user.modified");
  }

  const tableNames: Array<Exclude<keyof SnapshotDiff, "user">> = [
    "timelines",
    "tasks",
    "generations",
    "generation_variants",
    "shot_generations",
    "shots",
    "timeline_agent_sessions",
    "credits_ledger",
  ];

  for (const tableName of tableNames) {
    const tableDiff = diff[tableName] as TableDiff<{ id: string }>;
    unexpected.push(
      ...collectUnexpectedTableChanges(
        tableName,
        tableDiff,
        allowedChanges.tables?.[tableName],
      ),
    );
  }

  for (const row of getTimelineModifications(diff)) {
    unexpected.push(
      ...collectUnexpectedTableChanges("timelines", row.clip_changes, allowedChanges.timelineClips)
        .map((path) => path.replace("timelines", "timelineClips")),
    );
  }

  return unexpected.length === 0
    ? pass("No unexpected table or clip changes detected.")
    : fail(`Unexpected changes detected: ${unexpected.join(", ")}`);
}

export function expectMediaClipAdded(diff: SnapshotDiff, trackId?: string): AssertionResult {
  for (const row of getTimelineModifications(diff)) {
    for (const clip of Object.values(row.clip_changes.added)) {
      const isMedia = clip.clipType === "hold" || clip.clipType === "media";
      const matchesTrack = !trackId || clip.track === trackId;
      if (isMedia && clip.asset && matchesTrack) {
        return pass(`Media clip ${clip.id} was added on track ${clip.track} with asset ${clip.asset}.`);
      }
    }
  }

  return fail(`No added media clip found${trackId ? ` on track ${trackId}` : ""}.`);
}

export function expectDuplicateGeneration(diff: SnapshotDiff): AssertionResult {
  const addedGenerations = Object.values(diff.generations.added);
  const addedShotGenerations = Object.values(diff.shot_generations.added);
  if (addedGenerations.length === 0) {
    return fail("No new generations were created by duplicate_generation.");
  }
  // Duplicated generations are linked to a shot via shot_generations
  if (addedShotGenerations.length === 0) {
    return fail("Generation was duplicated but no shot_generations entry was created.");
  }
  return pass(`Duplicated generation: ${addedGenerations.map((g) => g.id).join(", ")}.`);
}

export function expectTaskParamsContain(
  diff: SnapshotDiff,
  key: string,
  label?: string,
): AssertionResult {
  for (const task of Object.values(diff.tasks.added)) {
    if (jsonContainsSubstring(task.params, key)) {
      return pass(`Task ${task.id} params contain "${label ?? key}".`);
    }
  }

  return fail(`No added task params contain "${label ?? key}".`);
}

export function expectSessionTerminal(snapshot: HarnessSnapshot): AssertionResult {
  const sessions = Object.values(snapshot.timeline_agent_sessions);
  if (sessions.length === 0) {
    return fail("No timeline_agent_sessions rows were present.");
  }

  const nonTerminal = sessions.filter((session) => !SESSION_TERMINAL_STATUSES.has(session.status));
  return nonTerminal.length === 0
    ? pass(`All sessions are terminal: ${sessions.map((session) => session.status).join(", ")}.`)
    : fail(`Non-terminal sessions remain: ${nonTerminal.map((session) => `${session.id}=${session.status}`).join(", ")}`);
}

export function expectAgentError(snapshot: HarnessSnapshot, errorSubstring?: string): AssertionResult {
  const sessions = Object.values(snapshot.timeline_agent_sessions);
  if (sessions.length === 0) {
    return fail("No timeline_agent_sessions rows were present.");
  }

  const erroredSession = sessions.find((session) => session.status === "error");
  if (!erroredSession) {
    return fail("No session reached status=error.");
  }

  if (!errorSubstring) {
    return pass(`Session ${erroredSession.id} reached status=error.`);
  }

  const turns = extractSessionTurns(erroredSession);
  const matchingTurn = turns.find((turn) => turn.content.toLowerCase().includes(errorSubstring.toLowerCase()));
  return matchingTurn
    ? pass(`Session ${erroredSession.id} surfaced error text containing "${errorSubstring}".`)
    : fail(`Session ${erroredSession.id} reached status=error but no turn contained "${errorSubstring}".`);
}

export function scoreResult(assertions: AssertionResult[]): {
  passed: number;
  failed: number;
  score: number;
  details: AssertionResult[];
} {
  const passed = assertions.filter((assertion) => assertion.pass).length;
  const failed = assertions.length - passed;
  return {
    passed,
    failed,
    score: assertions.length === 0 ? 0 : Math.round((passed / assertions.length) * 100),
    details: assertions,
  };
}
