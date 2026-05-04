// deno-lint-ignore-file
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { NO_SESSION_RUNTIME_OPTIONS, withEdgeRequest } from "../_shared/edgeHandler.ts";
import { verifyProjectOwnership } from "../_shared/auth.ts";
import { jsonResponse } from "../_shared/http.ts";
import { ensureUserAuth } from "../_shared/requestGuards.ts";

const LOG_PREFIX = "[REIGH-DATA-FETCH]";
const FUNCTION_VERSION = "2026-05-04.config-version";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PROJECT_SELECT = "id, name, user_id, aspect_ratio, settings, created_at";
const SHOTS_SELECT = "id, project_id, name, position, aspect_ratio, settings, created_at, updated_at";
const SHOT_GENERATIONS_SELECT = `
  id,
  shot_id,
  timeline_frame,
  generation_id,
  metadata,
  generation:generations!shot_generations_generation_id_generations_id_fk (
    id,
    location,
    thumbnail_url,
    type,
    created_at,
    starred,
    name,
    based_on,
    params,
    primary_variant_id,
    primary_variant:generation_variants!generations_primary_variant_id_fkey (
      location,
      thumbnail_url
    )
  )
`;
const PROJECT_GENERATIONS_SELECT = `
  id,
  location,
  thumbnail_url,
  primary_variant_id,
  storage_mode,
  local_handle_id,
  local_file_name,
  local_file_size,
  local_file_mime,
  primary_variant:generation_variants!generations_primary_variant_id_fkey (
    location,
    thumbnail_url
  ),
  type,
  created_at,
  updated_at,
  params,
  starred,
  tasks,
  based_on,
  shot_data,
  name,
  is_child,
  parent_generation_id,
  child_order
`;
const TASKS_SELECT = `
  id,
  project_id,
  task_type,
  status,
  params,
  output_location,
  result_data,
  dependant_on,
  error_message,
  attempts,
  generation_created,
  generation_started_at,
  generation_processed_at,
  created_at,
  updated_at,
  worker_id
`;
const TIMELINES_SELECT = "id, project_id, user_id, name, config, config_version, asset_registry, created_at, updated_at";
const PROJECT_MEDIA_LIMIT = 100;
const LOCAL_GENERATION_MEDIA_SENTINEL_URL = "local://pending-materialization";

interface ReighDataFetchBody extends Record<string, unknown> {
  project_id?: unknown;
  shot_id?: unknown;
  task_id?: unknown;
  timeline_id?: unknown;
}

interface ReighDataFetchRequest {
  projectId: string;
  shotId: string | null;
  taskId: string | null;
  timelineId: string | null;
}

interface JoinedGeneration {
  id: string;
  location: string | null;
  thumbnail_url: string | null;
  type: string | null;
  created_at: string;
  starred: boolean | null;
  name: string | null;
  based_on: string | null;
  params: unknown;
  primary_variant_id?: string | null;
  primary_variant?: {
    location: string | null;
    thumbnail_url: string | null;
  } | null;
}

interface RawProjectGeneration extends JoinedGeneration {
  updated_at?: string | null;
  storage_mode?: string | null;
  local_handle_id?: string | null;
  local_file_name?: string | null;
  local_file_size?: number | null;
  local_file_mime?: string | null;
  tasks?: unknown;
  shot_data?: unknown;
  is_child?: boolean | null;
  parent_generation_id?: string | null;
  child_order?: number | null;
}

interface RawShotGeneration {
  id: string;
  shot_id?: string;
  generation_id?: string;
  timeline_frame: number | null;
  metadata?: unknown;
  generations?: JoinedGeneration | null;
  generation?: JoinedGeneration | null;
}

interface ReighGenerationRow {
  id: string;
  generation_id: string;
  shotImageEntryId: string;
  shot_generation_id: string;
  location: string | null;
  imageUrl: string | null;
  thumbUrl: string | null;
  type: string;
  created_at: string;
  createdAt: string;
  starred: boolean;
  name: string | null;
  based_on: string | null;
  params: Record<string, unknown>;
  timeline_frame: number | null;
  metadata: Record<string, unknown>;
  primary_variant_id: string | null;
  position?: number;
}

interface ProjectMediaRow {
  id: string;
  isVideo: boolean;
  [key: string]: unknown;
}

interface ShotMediaGroups {
  all: ReighGenerationRow[];
  timeline_images: ReighGenerationRow[];
  unpositioned_images: ReighGenerationRow[];
  video_outputs: ReighGenerationRow[];
}

type ParseResult =
  | { ok: true; value: ReighDataFetchRequest }
  | { ok: false; error: string };

interface QueryResult<T = unknown> {
  data: T | null;
  error: { message?: string } | null;
  count?: number | null;
}

interface ReighDataQueryBuilder<T = unknown> extends PromiseLike<QueryResult<T>> {
  select: (...args: unknown[]) => ReighDataQueryBuilder<T>;
  eq: (...args: unknown[]) => ReighDataQueryBuilder<T>;
  in: (...args: unknown[]) => ReighDataQueryBuilder<T>;
  or: (...args: unknown[]) => ReighDataQueryBuilder<T>;
  order: (...args: unknown[]) => ReighDataQueryBuilder<T>;
  range: (...args: unknown[]) => ReighDataQueryBuilder<T>;
  single: () => Promise<QueryResult<T>>;
}

interface ReighDataSupabaseClient {
  from: <T = unknown>(table: string) => ReighDataQueryBuilder<T>;
}

function toRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return null;
}

function stripQueryParameters(value: string | null): string | null {
  if (!value) return null;
  const queryIndex = value.indexOf("?");
  return queryIndex === -1 ? value : value.slice(0, queryIndex);
}

function parseGenerationTaskId(tasks: unknown): { taskId: string | null; status: string } {
  if (typeof tasks === "string" && tasks.length > 0) {
    return { taskId: tasks, status: "string" };
  }

  if (Array.isArray(tasks)) {
    const taskId = tasks.find((task) => typeof task === "string");
    return { taskId: typeof taskId === "string" ? taskId : null, status: "array" };
  }

  const taskRecord = toRecord(tasks);
  const taskId = firstString(taskRecord.id, taskRecord.task_id, taskRecord.taskId);
  return { taskId, status: Object.keys(taskRecord).length > 0 ? "object" : "empty" };
}

function extractPrompt(params: Record<string, unknown>): string {
  const originalParams = toRecord(params.originalParams);
  const orchestratorDetails = toRecord(originalParams.orchestrator_details);
  const metadataBlock = toRecord(params.metadata);

  return firstString(
    orchestratorDetails.prompt,
    params.prompt,
    metadataBlock.prompt,
  ) ?? "No prompt";
}

function extractThumbnailUrl(item: RawProjectGeneration, mainUrl: string | null): string | null {
  const thumbnailUrl = item.primary_variant?.thumbnail_url || item.thumbnail_url;
  if (thumbnailUrl) return thumbnailUrl;

  const params = toRecord(item.params);
  const originalParams = toRecord(params.originalParams);
  const orchestratorDetails = toRecord(originalParams.orchestrator_details);
  const fullPayload = toRecord(params.full_orchestrator_payload);
  const originalFullPayload = toRecord(originalParams.full_orchestrator_payload);

  return firstString(
    params.thumbnailUrl,
    orchestratorDetails.thumbnail_url,
    fullPayload.thumbnail_url,
    originalFullPayload.thumbnail_url,
  ) ?? mainUrl;
}

export function mapProjectGenerationToReighMedia(item: RawProjectGeneration): ProjectMediaRow {
  const params = toRecord(item.params);
  const isLocalGeneration = item.storage_mode === "local";
  const resolvedMediaUrl = item.primary_variant?.location || item.location;
  const mainUrl = isLocalGeneration ? null : resolvedMediaUrl;
  const thumbnailUrl = extractThumbnailUrl(item, mainUrl);
  const taskIdParse = parseGenerationTaskId(item.tasks);
  const storedContentType = asString(params.content_type);
  const isVideo = Boolean(item.type?.includes("video") || storedContentType === "video");
  const contentType = storedContentType === "video"
    ? "video/mp4"
    : storedContentType === "image"
      ? "image/png"
      : undefined;

  return {
    id: item.id,
    url: isLocalGeneration ? LOCAL_GENERATION_MEDIA_SENTINEL_URL : mainUrl,
    location: mainUrl,
    thumbUrl: thumbnailUrl,
    urlIdentity: stripQueryParameters(mainUrl) || undefined,
    thumbUrlIdentity: stripQueryParameters(thumbnailUrl) || undefined,
    prompt: extractPrompt(params),
    metadata: {
      ...params,
      taskId: taskIdParse.taskId,
      taskIdStatus: taskIdParse.status,
      based_on: item.based_on,
      variant_id: item.primary_variant_id ?? undefined,
    },
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    isVideo,
    type: item.type ?? (isVideo ? "video" : "image"),
    ...(contentType ? { contentType } : {}),
    starred: item.starred || false,
    based_on: item.based_on,
    position: null,
    timeline_frame: null,
    name: item.name ?? asString(params.name) ?? undefined,
    derivedCount: 0,
    hasUnviewedVariants: false,
    unviewedVariantCount: 0,
    primary_variant_id: item.primary_variant_id ?? null,
    storage_mode: item.storage_mode ?? "remote",
    local_handle_id: item.local_handle_id ?? null,
    local_file_name: item.local_file_name ?? null,
    local_file_size: item.local_file_size ?? null,
    local_file_mime: item.local_file_mime ?? null,
    is_child: item.is_child ?? undefined,
    parent_generation_id: item.parent_generation_id ?? undefined,
    child_order: item.child_order ?? undefined,
  };
}

function hasValidImageLocation(generation: ReighGenerationRow): boolean {
  return Boolean(generation.location && generation.location !== "/placeholder.svg");
}

function isVideoOutputGeneration(generation: ReighGenerationRow): boolean {
  return Boolean(generation.type?.includes("video"));
}

function selectTimelineImages(generations: ReighGenerationRow[]): ReighGenerationRow[] {
  return generations
    .filter((generation) =>
      generation.timeline_frame != null &&
      generation.timeline_frame >= 0 &&
      !isVideoOutputGeneration(generation) &&
      hasValidImageLocation(generation)
    )
    .sort((a, b) => (a.timeline_frame ?? 0) - (b.timeline_frame ?? 0));
}

function selectUnpositionedImages(generations: ReighGenerationRow[]): ReighGenerationRow[] {
  return generations.filter((generation) =>
    generation.timeline_frame == null &&
    !isVideoOutputGeneration(generation) &&
    hasValidImageLocation(generation)
  );
}

function selectVideoOutputs(generations: ReighGenerationRow[]): ReighGenerationRow[] {
  return generations.filter(isVideoOutputGeneration);
}

export function mapShotGenerationToReighRow(sg: RawShotGeneration): ReighGenerationRow | null {
  const gen = sg.generations || sg.generation;
  if (!gen) return null;

  const primaryVariant = gen.primary_variant;
  const effectiveLocation = primaryVariant?.location || gen.location;
  const effectiveThumbnail = primaryVariant?.thumbnail_url || gen.thumbnail_url || effectiveLocation;

  return {
    id: sg.id,
    generation_id: gen.id,
    shotImageEntryId: sg.id,
    shot_generation_id: sg.id,
    location: effectiveLocation,
    imageUrl: effectiveLocation,
    thumbUrl: effectiveThumbnail,
    type: gen.type || "image",
    created_at: gen.created_at,
    createdAt: gen.created_at,
    starred: gen.starred || false,
    name: gen.name,
    based_on: gen.based_on,
    params: toRecord(gen.params),
    timeline_frame: sg.timeline_frame,
    metadata: toRecord(sg.metadata),
    primary_variant_id: gen.primary_variant_id || null,
    ...(sg.timeline_frame != null ? { position: Math.floor(sg.timeline_frame / 50) } : {}),
  };
}

function groupShotMedia(rows: ReighGenerationRow[]): ShotMediaGroups {
  return {
    all: rows,
    timeline_images: selectTimelineImages(rows),
    unpositioned_images: selectUnpositionedImages(rows),
    video_outputs: selectVideoOutputs(rows),
  };
}

function uniqueGenerationCount(rows: ReighGenerationRow[]): number {
  return new Set(rows.map((row) => row.generation_id).filter(Boolean)).size;
}

function uniqueUnpositionedGenerationCount(rows: ReighGenerationRow[]): number {
  return new Set(
    rows
      .filter((row) => row.timeline_frame == null)
      .map((row) => row.generation_id)
      .filter(Boolean),
  ).size;
}

function projectMediaGroups(items: ProjectMediaRow[]) {
  return {
    images: items.filter((item) => !item.isVideo),
    videos: items.filter((item) => item.isVideo),
  };
}

function taskSettingsById(tasks: Array<Record<string, unknown>>) {
  const settings: Record<string, unknown> = {};
  for (const task of tasks) {
    const id = asString(task.id);
    if (!id) continue;
    const params = toRecord(task.params);
    settings[id] = {
      params,
      settings: toRecord(params.settings),
      task_type: task.task_type ?? null,
      status: task.status ?? null,
      output_location: task.output_location ?? null,
      result_data: task.result_data ?? null,
    };
  }
  return settings;
}

function parseRequiredUuid(body: ReighDataFetchBody, field: "project_id"): ParseResult | string {
  const value = body[field];
  if (typeof value !== "string") {
    return { ok: false, error: `${field} is required` };
  }

  const trimmed = value.trim();
  if (!UUID_PATTERN.test(trimmed)) {
    return { ok: false, error: `${field} must be a valid UUID` };
  }

  return trimmed;
}

function parseOptionalUuid(
  body: ReighDataFetchBody,
  field: "shot_id" | "task_id" | "timeline_id",
): ParseResult | string | null {
  const value = body[field];
  if (value === undefined || value === null || value === "") {
    return null;
  }

  if (typeof value !== "string") {
    return { ok: false, error: `${field} must be a valid UUID` };
  }

  const trimmed = value.trim();
  if (!UUID_PATTERN.test(trimmed)) {
    return { ok: false, error: `${field} must be a valid UUID` };
  }

  return trimmed;
}

export function parseReighDataFetchRequest(body: ReighDataFetchBody): ParseResult {
  const projectId = parseRequiredUuid(body, "project_id");
  if (typeof projectId !== "string") return projectId;

  const shotId = parseOptionalUuid(body, "shot_id");
  if (shotId && typeof shotId !== "string") return shotId;

  const taskId = parseOptionalUuid(body, "task_id");
  if (taskId && typeof taskId !== "string") return taskId;

  const timelineId = parseOptionalUuid(body, "timeline_id");
  if (timelineId && typeof timelineId !== "string") return timelineId;

  return {
    ok: true,
    value: {
      projectId,
      shotId,
      taskId,
      timelineId,
    },
  };
}

async function fetchProject(supabaseAdmin: ReighDataSupabaseClient, projectId: string) {
  return await supabaseAdmin
    .from("projects")
    .select(PROJECT_SELECT)
    .eq("id", projectId)
    .single();
}

async function fetchProjectShots(
  supabaseAdmin: ReighDataSupabaseClient,
  projectId: string,
  shotId: string | null,
) {
  let query = supabaseAdmin
    .from("shots")
    .select(SHOTS_SELECT)
    .eq("project_id", projectId);

  if (shotId) {
    query = query.eq("id", shotId);
  }

  return await query.order("position", { ascending: true });
}

async function fetchShotGenerations(supabaseAdmin: ReighDataSupabaseClient, shotIds: string[]) {
  if (shotIds.length === 0) {
    return { data: [], error: null };
  }

  return await supabaseAdmin
    .from("shot_generations")
    .select(SHOT_GENERATIONS_SELECT)
    .in("shot_id", shotIds)
    .order("timeline_frame", { ascending: true, nullsFirst: false });
}

async function fetchProjectGenerations(supabaseAdmin: ReighDataSupabaseClient, projectId: string) {
  return await supabaseAdmin
    .from("generations")
    .select(PROJECT_GENERATIONS_SELECT, { count: "exact" })
    .eq("project_id", projectId)
    .eq("is_child", false)
    .or("location.not.is.null,storage_mode.eq.local")
    .order("created_at", { ascending: false })
    .range(0, PROJECT_MEDIA_LIMIT - 1);
}

async function fetchTasks(
  supabaseAdmin: ReighDataSupabaseClient,
  projectId: string,
  taskId: string | null,
) {
  let query = supabaseAdmin
    .from("tasks")
    .select(TASKS_SELECT)
    .eq("project_id", projectId);

  if (taskId) {
    query = query.eq("id", taskId);
  }

  return await query.order("created_at", { ascending: false });
}

async function fetchTimelines(
  supabaseAdmin: ReighDataSupabaseClient,
  projectId: string,
  timelineId: string | null,
) {
  let query = supabaseAdmin
    .from("timelines")
    .select(TIMELINES_SELECT)
    .eq("project_id", projectId);

  if (timelineId) {
    query = query.eq("id", timelineId);
  }

  return await query.order("updated_at", { ascending: false });
}

serve((req) => {
  return withEdgeRequest<ReighDataFetchBody>(req, {
    functionName: "reigh-data-fetch",
    logPrefix: LOG_PREFIX,
    parseBody: "strict",
    auth: {
      required: true,
    },
    ...NO_SESSION_RUNTIME_OPTIONS,
  }, async ({ supabaseAdmin, logger, body, auth }) => {
    const parsed = parseReighDataFetchRequest(body);
    if (!parsed.ok) {
      logger.error("Invalid request", { error: parsed.error });
      return jsonResponse({ error: parsed.error }, 400);
    }

    const { projectId, shotId, taskId, timelineId } = parsed.value;
    const isServiceRole = auth?.isServiceRole ?? false;
    const userGuard = isServiceRole ? null : ensureUserAuth(auth, logger);
    if (userGuard && !userGuard.ok) {
      return userGuard.response;
    }

    if (!isServiceRole) {
      const ownership = await verifyProjectOwnership(
        supabaseAdmin,
        projectId,
        userGuard!.userId,
        LOG_PREFIX,
      );
      if (!ownership.success) {
        logger.error("Project ownership verification failed", {
          project_id: projectId,
          user_id: userGuard!.userId,
          error: ownership.error,
        });
        return jsonResponse(
          { error: ownership.error || "Forbidden: Project does not belong to user" },
          ownership.statusCode || 403,
        );
      }
    }

    const { data: project, error: projectError } = await fetchProject(supabaseAdmin, projectId);
    if (projectError || !project) {
      logger.error("Project lookup failed", {
        project_id: projectId,
        error: projectError?.message,
      });
      return jsonResponse({ error: "Project not found" }, 404);
    }

    const { data: shotsData, error: shotsError } = await fetchProjectShots(
      supabaseAdmin,
      projectId,
      shotId,
    );
    if (shotsError) {
      logger.error("Shots query failed", {
        project_id: projectId,
        shot_id: shotId,
        error: shotsError.message,
      });
      return jsonResponse({ error: "Failed to fetch shots" }, 500);
    }

    const baseShots = shotsData ?? [];
    const shotIds = baseShots.map((shot: { id: string }) => shot.id);
    const { data: shotGenerationsData, error: shotGenerationsError } = await fetchShotGenerations(
      supabaseAdmin,
      shotIds,
    );
    if (shotGenerationsError) {
      logger.error("Shot media query failed", {
        project_id: projectId,
        shot_id: shotId,
        error: shotGenerationsError.message,
      });
      return jsonResponse({ error: "Failed to fetch shot media" }, 500);
    }

    const mediaRowsByShot: Record<string, ReighGenerationRow[]> = {};
    for (const sg of shotGenerationsData ?? []) {
      const mapped = mapShotGenerationToReighRow(sg as RawShotGeneration);
      if (!mapped) continue;
      const mediaShotId = typeof sg.shot_id === "string" ? sg.shot_id : "";
      if (!mediaRowsByShot[mediaShotId]) {
        mediaRowsByShot[mediaShotId] = [];
      }
      mediaRowsByShot[mediaShotId].push(mapped);
    }

    const shotMediaByShot: Record<string, ShotMediaGroups> = {};
    for (const id of shotIds) {
      shotMediaByShot[id] = groupShotMedia(mediaRowsByShot[id] ?? []);
    }

    const shots = baseShots.map((shot: Record<string, unknown>) => {
      const images = mediaRowsByShot[shot.id as string] ?? [];
      const imageCount = uniqueGenerationCount(images);
      const unpositionedImageCount = uniqueUnpositionedGenerationCount(images);

      return {
        ...shot,
        images,
        imageCount,
        positionedImageCount: imageCount - unpositionedImageCount,
        unpositionedImageCount,
        hasUnpositionedImages: unpositionedImageCount > 0,
      };
    });

    const { data: projectGenerationsData, error: projectGenerationsError, count: projectGenerationsCount } = await fetchProjectGenerations(
      supabaseAdmin,
      projectId,
    );
    if (projectGenerationsError) {
      logger.error("Project media query failed", {
        project_id: projectId,
        error: projectGenerationsError.message,
      });
      return jsonResponse({ error: "Failed to fetch project media" }, 500);
    }

    const projectMediaItems = (projectGenerationsData ?? []).map((item: RawProjectGeneration) =>
      mapProjectGenerationToReighMedia(item)
    );
    const projectMedia = {
      items: projectMediaItems,
      ...projectMediaGroups(projectMediaItems),
      total: projectGenerationsCount ?? projectMediaItems.length,
      hasMore: projectGenerationsCount != null
        ? PROJECT_MEDIA_LIMIT < projectGenerationsCount
        : projectMediaItems.length === PROJECT_MEDIA_LIMIT,
      limit: PROJECT_MEDIA_LIMIT,
      offset: 0,
    };

    const { data: tasksData, error: tasksError } = await fetchTasks(
      supabaseAdmin,
      projectId,
      taskId,
    );
    if (tasksError) {
      logger.error("Tasks query failed", {
        project_id: projectId,
        task_id: taskId,
        error: tasksError.message,
      });
      return jsonResponse({ error: "Failed to fetch tasks" }, 500);
    }
    const taskSettings = taskSettingsById(tasksData ?? []);

    const { data: timelinesData, error: timelinesError } = await fetchTimelines(
      supabaseAdmin,
      projectId,
      timelineId,
    );
    if (timelinesError) {
      logger.error("Timelines query failed", {
        project_id: projectId,
        timeline_id: timelineId,
        error: timelinesError.message,
      });
      return jsonResponse({ error: "Failed to fetch timelines" }, 500);
    }

    logger.info("Request authorized", {
      function_version: FUNCTION_VERSION,
      project_id: projectId,
      shot_id: shotId,
      task_id: taskId,
      timeline_id: timelineId,
      service_role: isServiceRole,
      shot_count: shots.length,
      shot_media_count: (shotGenerationsData ?? []).length,
      project_media_count: projectMediaItems.length,
      task_count: (tasksData ?? []).length,
      timeline_count: (timelinesData ?? []).length,
    });

    return jsonResponse({
      project_id: projectId,
      filters: {
        shot_id: shotId,
        task_id: taskId,
        timeline_id: timelineId,
      },
      project,
      project_settings: project.settings ?? null,
      shots,
      shot_settings: Object.fromEntries(
        shots.map((shot: Record<string, unknown>) => [shot.id, shot.settings ?? null]),
      ),
      shot_media: {
        by_shot: shotMediaByShot,
      },
      project_media: projectMedia,
      tasks: tasksData ?? [],
      task_settings: taskSettings,
      timelines: timelinesData ?? [],
      data: {
        project,
        project_settings: project.settings ?? null,
        shots,
        shot_settings: Object.fromEntries(
          shots.map((shot: Record<string, unknown>) => [shot.id, shot.settings ?? null]),
        ),
        shot_media: {
          by_shot: shotMediaByShot,
        },
        project_media: projectMedia,
        tasks: tasksData ?? [],
        task_settings: taskSettings,
        timelines: timelinesData ?? [],
      },
    }, 200);
  });
});
