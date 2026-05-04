import type { Json } from "../../../../src/integrations/supabase/types.ts";
import type { TimelineClip, TimelineConfig } from "../../../../src/tools/video-editor/index.ts";
import { getAdminSupabaseClient } from "./client.ts";

type RowMap<Row> = Record<string, Row>;

export interface TimelineSnapshotRow {
  id: string;
  config: TimelineConfig;
  config_version: number;
  asset_registry: Json;
}

export interface TaskSnapshotRow {
  id: string;
  task_type: string;
  params: Json;
  status: string;
  output_location: string | null;
  error_message: string | null;
  created_at: string;
  generation_created: boolean;
}

export interface GenerationSnapshotRow {
  id: string;
  tasks: Json | null;
  params: Json | null;
  location: string | null;
  thumbnail_url: string | null;
  type: string | null;
  primary_variant_id: string | null;
  linked_task_ids: string[];
}

export interface GenerationVariantSnapshotRow {
  id: string;
  generation_id: string;
  location: string;
  thumbnail_url: string | null;
  is_primary: boolean;
  variant_type: string | null;
  name: string | null;
  params: Json | null;
  created_at: string;
  project_id: string | null;
}

export interface ShotGenerationSnapshotRow {
  id: string;
  shot_id: string;
  generation_id: string;
  timeline_frame: number | null;
  metadata: Json | null;
  created_at: string | null;
  updated_at: string;
}

export interface ShotSnapshotRow {
  id: string;
  name: string;
  position: number;
  aspect_ratio: string | null;
  settings: Json | null;
}

export interface SessionSnapshotRow {
  id: string;
  turns: Json;
  status: string;
  model: string;
  summary: string | null;
}

export interface CreditsLedgerSnapshotRow {
  id: string;
  amount: number;
  type: string;
  task_id: string | null;
  metadata: Json | null;
}

export interface UserCreditsSnapshot {
  id: string;
  email: string | null;
  credits: number;
}

export interface HarnessSnapshot {
  captured_at: string;
  timeline_id: string;
  project_id: string;
  user_id: string;
  user: UserCreditsSnapshot | null;
  timelines: RowMap<TimelineSnapshotRow>;
  tasks: RowMap<TaskSnapshotRow>;
  generations: RowMap<GenerationSnapshotRow>;
  generation_variants: RowMap<GenerationVariantSnapshotRow>;
  shot_generations: RowMap<ShotGenerationSnapshotRow>;
  shots: RowMap<ShotSnapshotRow>;
  timeline_agent_sessions: RowMap<SessionSnapshotRow>;
  credits_ledger: RowMap<CreditsLedgerSnapshotRow>;
}

export interface ValueChange {
  path: string;
  before: unknown;
  after: unknown;
}

export interface ModifiedRow<Row> {
  before: Row;
  after: Row;
  changes: ValueChange[];
}

export interface TimelineModifiedRow extends ModifiedRow<TimelineSnapshotRow> {
  clip_changes: TableDiff<TimelineClip>;
}

export interface TableDiff<Row> {
  added: RowMap<Row>;
  removed: RowMap<Row>;
  modified: Record<string, ModifiedRow<Row> | TimelineModifiedRow>;
}

export interface SnapshotDiff {
  user: ModifiedRow<UserCreditsSnapshot> | null;
  timelines: TableDiff<TimelineSnapshotRow>;
  tasks: TableDiff<TaskSnapshotRow>;
  generations: TableDiff<GenerationSnapshotRow>;
  generation_variants: TableDiff<GenerationVariantSnapshotRow>;
  shot_generations: TableDiff<ShotGenerationSnapshotRow>;
  shots: TableDiff<ShotSnapshotRow>;
  timeline_agent_sessions: TableDiff<SessionSnapshotRow>;
  credits_ledger: TableDiff<CreditsLedgerSnapshotRow>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function indexById<Row extends { id: string }>(rows: Row[]): RowMap<Row> {
  return rows.reduce<RowMap<Row>>((accumulator, row) => {
    accumulator[row.id] = row;
    return accumulator;
  }, {});
}

function asTaskIdArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item) => typeof item === "string" && item.trim() ? [item.trim()] : []);
}

function getGenerationLinkedTaskIds(row: { tasks: Json | null; params: Json | null }): string[] {
  const taskIds = new Set(asTaskIdArray(row.tasks));
  if (isRecord(row.params) && typeof row.params.source_task_id === "string" && row.params.source_task_id.trim()) {
    taskIds.add(row.params.source_task_id.trim());
  }

  return Array.from(taskIds).sort((left, right) => left.localeCompare(right));
}

function deepDiff(before: unknown, after: unknown, path = ""): ValueChange[] {
  if (Object.is(before, after)) {
    return [];
  }

  const beforeIsRecord = isRecord(before);
  const afterIsRecord = isRecord(after);
  if (beforeIsRecord && afterIsRecord) {
    const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort((left, right) => left.localeCompare(right));
    return keys.flatMap((key) => deepDiff(before[key], after[key], path ? `${path}.${key}` : key));
  }

  if (Array.isArray(before) && Array.isArray(after)) {
    const length = Math.max(before.length, after.length);
    const changes: ValueChange[] = [];
    for (let index = 0; index < length; index += 1) {
      changes.push(...deepDiff(before[index], after[index], `${path}[${index}]`));
    }
    return changes;
  }

  return [{ path: path || "<root>", before, after }];
}

function diffRows<Row>(
  beforeRows: RowMap<Row>,
  afterRows: RowMap<Row>,
  createModifiedRow: (before: Row, after: Row) => ModifiedRow<Row> | TimelineModifiedRow = (before, after) => ({
    before,
    after,
    changes: deepDiff(before, after),
  }),
): TableDiff<Row> {
  const added: RowMap<Row> = {};
  const removed: RowMap<Row> = {};
  const modified: Record<string, ModifiedRow<Row> | TimelineModifiedRow> = {};
  const ids = Array.from(new Set([...Object.keys(beforeRows), ...Object.keys(afterRows)])).sort((left, right) => left.localeCompare(right));

  for (const id of ids) {
    const before = beforeRows[id];
    const after = afterRows[id];
    if (!before && after) {
      added[id] = after;
      continue;
    }
    if (before && !after) {
      removed[id] = before;
      continue;
    }
    if (before && after) {
      const rowDiff = createModifiedRow(before, after);
      if (rowDiff.changes.length > 0 || ("clip_changes" in rowDiff && Object.keys(rowDiff.clip_changes.added).length + Object.keys(rowDiff.clip_changes.removed).length + Object.keys(rowDiff.clip_changes.modified).length > 0)) {
        modified[id] = rowDiff;
      }
    }
  }

  return { added, removed, modified };
}

function createTimelineModifiedRow(before: TimelineSnapshotRow, after: TimelineSnapshotRow): TimelineModifiedRow {
  const beforeWithoutClips = {
    ...before,
    config: {
      ...before.config,
      clips: [],
    },
  };
  const afterWithoutClips = {
    ...after,
    config: {
      ...after.config,
      clips: [],
    },
  };

  return {
    before,
    after,
    changes: deepDiff(beforeWithoutClips, afterWithoutClips),
    clip_changes: diffRows(
      indexById(before.config.clips),
      indexById(after.config.clips),
      (previousClip, nextClip) => ({
        before: previousClip,
        after: nextClip,
        changes: deepDiff(previousClip, nextClip),
      }),
    ),
  };
}

async function selectRows<Row>(query: PromiseLike<{ data: Row[] | null; error: { message: string } | null }>, label: string): Promise<Row[]> {
  const { data, error } = await query;
  if (error) {
    throw new Error(`Failed to load ${label}: ${error.message}`);
  }

  return data ?? [];
}

async function selectSingle<Row>(query: PromiseLike<{ data: Row | null; error: { message: string } | null }>, label: string): Promise<Row | null> {
  const { data, error } = await query;
  if (error) {
    throw new Error(`Failed to load ${label}: ${error.message}`);
  }

  return data;
}

export async function snapshotState(
  timelineId: string,
  projectId: string,
  userId: string,
): Promise<HarnessSnapshot> {
  const supabase = getAdminSupabaseClient();
  const [timeline, tasks, generations, shots, sessions, credits, user] = await Promise.all([
    selectSingle<{
      id: string;
      config: TimelineConfig;
      config_version?: number;
      asset_registry?: Json;
    }>(
      supabase.from("timelines").select("id, config, config_version, asset_registry").eq("id", timelineId).maybeSingle(),
      "timeline",
    ),
    selectRows<TaskSnapshotRow>(
      supabase.from("tasks").select("id, task_type, params, status, output_location, error_message, created_at, generation_created").eq("project_id", projectId).order("created_at", { ascending: true }),
      "tasks",
    ),
    selectRows<Omit<GenerationSnapshotRow, "linked_task_ids">>(
      supabase.from("generations").select("id, tasks, params, location, thumbnail_url, type, primary_variant_id").eq("project_id", projectId).order("created_at", { ascending: true }),
      "generations",
    ),
    selectRows<ShotSnapshotRow>(
      supabase.from("shots").select("id, name, position, aspect_ratio, settings").eq("project_id", projectId).order("position", { ascending: true }),
      "shots",
    ),
    selectRows<SessionSnapshotRow>(
      supabase.from("timeline_agent_sessions").select("id, turns, status, model, summary").eq("timeline_id", timelineId).order("created_at", { ascending: true }),
      "timeline_agent_sessions",
    ),
    selectRows<CreditsLedgerSnapshotRow>(
      supabase.from("credits_ledger").select("id, amount, type, task_id, metadata").eq("user_id", userId).order("created_at", { ascending: true }),
      "credits_ledger",
    ),
    selectSingle<UserCreditsSnapshot>(
      supabase.from("users").select("id, email, credits").eq("id", userId).maybeSingle(),
      "user credits",
    ),
  ]);

  const generationIds = generations.flatMap((row) => typeof row?.id === "string" ? [row.id] : []);
  const shotIds = shots.flatMap((row) => typeof row?.id === "string" ? [row.id] : []);
  const [generationVariants, shotGenerations] = await Promise.all([
    generationIds.length > 0
      ? selectRows<GenerationVariantSnapshotRow>(
        supabase.from("generation_variants").select("id, generation_id, location, thumbnail_url, is_primary, variant_type, name, params, created_at, project_id").in("generation_id", generationIds).order("created_at", { ascending: true }),
        "generation_variants",
      )
      : Promise.resolve([] as GenerationVariantSnapshotRow[]),
    shotIds.length > 0
      ? selectRows<ShotGenerationSnapshotRow>(
        supabase.from("shot_generations").select("id, shot_id, generation_id, timeline_frame, metadata, created_at, updated_at").in("shot_id", shotIds).order("updated_at", { ascending: true }),
        "shot_generations",
      )
      : Promise.resolve([] as ShotGenerationSnapshotRow[]),
  ]);

  return {
    captured_at: new Date().toISOString(),
    timeline_id: timelineId,
    project_id: projectId,
    user_id: userId,
    user: user ?? null,
    timelines: timeline && typeof timeline.id === "string"
      ? indexById([{
        id: timeline.id,
        config: timeline.config,
        config_version: typeof timeline.config_version === "number"
          ? timeline.config_version
          : 1,
        asset_registry: timeline.asset_registry ?? { assets: {} },
      }])
      : {},
    tasks: indexById(tasks),
    generations: indexById(generations.map((row) => ({
      ...row,
      linked_task_ids: getGenerationLinkedTaskIds(row),
    }))),
    generation_variants: indexById(generationVariants),
    shot_generations: indexById(shotGenerations),
    shots: indexById(shots),
    timeline_agent_sessions: indexById(sessions),
    credits_ledger: indexById(credits),
  };
}

export function diffSnapshots(before: HarnessSnapshot, after: HarnessSnapshot): SnapshotDiff {
  return {
    user: before.user && after.user
      ? (() => {
        const changes = deepDiff(before.user, after.user);
        return changes.length > 0 ? { before: before.user, after: after.user, changes } : null;
      })()
      : null,
    timelines: diffRows(before.timelines, after.timelines, createTimelineModifiedRow),
    tasks: diffRows(before.tasks, after.tasks),
    generations: diffRows(before.generations, after.generations),
    generation_variants: diffRows(before.generation_variants, after.generation_variants),
    shot_generations: diffRows(before.shot_generations, after.shot_generations),
    shots: diffRows(before.shots, after.shots),
    timeline_agent_sessions: diffRows(before.timeline_agent_sessions, after.timeline_agent_sessions),
    credits_ledger: diffRows(before.credits_ledger, after.credits_ledger),
  };
}

function summarizeTable<Row extends { id: string }>(
  label: string,
  table: TableDiff<Row>,
  renderAdded?: (row: Row) => string,
  renderModified?: (id: string, row: ModifiedRow<Row> | TimelineModifiedRow) => string,
): string[] {
  const lines = [
    `${label}: +${Object.keys(table.added).length} -${Object.keys(table.removed).length} ~${Object.keys(table.modified).length}`,
  ];

  for (const row of Object.values(table.added)) {
    lines.push(`  + ${renderAdded ? renderAdded(row) : row.id}`);
  }
  for (const row of Object.values(table.removed)) {
    lines.push(`  - ${row.id}`);
  }
  for (const [id, row] of Object.entries(table.modified)) {
    lines.push(`  ~ ${renderModified ? renderModified(id, row) : `${id} (${row.changes.map((change) => change.path).join(", ")})`}`);
  }

  return lines;
}

export function summarizeDiff(diff: SnapshotDiff): string {
  const lines: string[] = [];

  if (diff.user) {
    lines.push(`user credits: ${diff.user.before.credits} -> ${diff.user.after.credits}`);
  }

  lines.push(
    ...summarizeTable("timelines", diff.timelines, (row) => row.id, (id, row) => {
      const clipChangeCount = "clip_changes" in row
        ? Object.keys(row.clip_changes.added).length + Object.keys(row.clip_changes.removed).length + Object.keys(row.clip_changes.modified).length
        : 0;
      const parts = row.changes.map((change) => change.path);
      if (clipChangeCount > 0) parts.push(`clips(${clipChangeCount})`);
      return `${id} (${parts.join(", ") || "changed"})`;
    }),
    ...summarizeTable("tasks", diff.tasks, (row) => `${row.id} [${row.task_type}] ${row.status}`),
    ...summarizeTable("generations", diff.generations, (row) => `${row.id} linked_tasks=${row.linked_task_ids.join(",") || "none"}`),
    ...summarizeTable("generation_variants", diff.generation_variants),
    ...summarizeTable("shot_generations", diff.shot_generations),
    ...summarizeTable("shots", diff.shots, (row) => `${row.id} ${row.name}`),
    ...summarizeTable("timeline_agent_sessions", diff.timeline_agent_sessions, (row) => `${row.id} ${row.status}`),
    ...summarizeTable("credits_ledger", diff.credits_ledger, (row) => `${row.id} ${row.type} ${row.amount}`),
  );

  return lines.join("\n");
}
