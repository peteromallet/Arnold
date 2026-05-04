import {
  canonicalizeTimelinePair,
  type AssetRegistry,
  type TimelineClip,
  type TimelineConfig,
} from "../../../src/tools/video-editor/index.ts";
import { isRecord, isSessionStatus, normalizeTimelineRow } from "./llm/messages.ts";
import type {
  AgentProjectImageSettings,
  AgentProjectImageSettingsReference,
  AgentReferenceMode,
  AgentSessionStatus,
  AgentTurn,
  AgentVideoTravelSettings,
  ResolvedReference,
  SupabaseAdmin,
  TimelineState,
} from "./types.ts";

function asTrimmedString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function asOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asOptionalBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function asReferenceMode(value: unknown): AgentReferenceMode | undefined {
  return value === "style" || value === "subject" || value === "style-character" || value === "scene" || value === "custom"
    ? value
    : undefined;
}

type AgentLoraCategory = "qwen" | "z-image";
type AgentPathLora = { path: string; strength: number };
type TravelModelDefaults = { frames: number; steps: number; guidanceScale?: number };
type SearchLoraResult = {
  resourceId: string;
  name: string;
  path: string;
  triggerWord?: string;
  baseModel?: string;
  description?: string;
  highNoiseUrl?: string;
  lowNoiseUrl?: string;
};

const AGENT_LORA_CATEGORIES: AgentLoraCategory[] = ["qwen", "z-image"];
const TRAVEL_MODEL_DEFAULTS: Record<string, TravelModelDefaults> = {
  "wan-2.2": { frames: 61, steps: 6 },
  "ltx-2.3": { frames: 97, steps: 30, guidanceScale: 3 },
  "ltx-2.3-fast": { frames: 97, steps: 8, guidanceScale: 3 },
};

function normalizePathLora(value: unknown): AgentPathLora | null {
  if (!isRecord(value)) {
    return null;
  }

  const path = asTrimmedString(value.path);
  const strength = asOptionalNumber(value.strength);
  if (!path || strength === undefined) {
    return null;
  }

  return { path, strength };
}

function pushUniqueLora(
  target: Partial<Record<AgentLoraCategory, AgentPathLora[]>>,
  seenPaths: Record<AgentLoraCategory, Set<string>>,
  category: AgentLoraCategory,
  lora: AgentPathLora,
): void {
  if (seenPaths[category].has(lora.path)) {
    return;
  }

  seenPaths[category].add(lora.path);
  target[category] = [...(target[category] ?? []), lora];
}

function hasNormalizedLoras(
  value: Partial<Record<AgentLoraCategory, AgentPathLora[]>>,
): boolean {
  return AGENT_LORA_CATEGORIES.some((category) => (value[category]?.length ?? 0) > 0);
}

function normalizeSelectedLorasByCategory(
  value: unknown,
): Partial<Record<AgentLoraCategory, AgentPathLora[]>> | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const normalized: Partial<Record<AgentLoraCategory, AgentPathLora[]>> = {};
  const seenPaths: Record<AgentLoraCategory, Set<string>> = {
    qwen: new Set<string>(),
    "z-image": new Set<string>(),
  };

  for (const category of AGENT_LORA_CATEGORIES) {
    const rawLoras = value[category];
    if (!Array.isArray(rawLoras)) {
      continue;
    }

    for (const rawLora of rawLoras) {
      const lora = normalizePathLora(rawLora);
      if (!lora) {
        continue;
      }
      pushUniqueLora(normalized, seenPaths, category, lora);
    }
  }

  return hasNormalizedLoras(normalized) ? normalized : undefined;
}

function normalizeLegacySelectedLorasByTextModel(
  value: unknown,
): Partial<Record<AgentLoraCategory, AgentPathLora[]>> | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const normalized: Partial<Record<AgentLoraCategory, AgentPathLora[]>> = {};
  const seenPaths: Record<AgentLoraCategory, Set<string>> = {
    qwen: new Set<string>(),
    "z-image": new Set<string>(),
  };

  for (const [modelName, rawLoras] of Object.entries(value)) {
    if (!Array.isArray(rawLoras)) {
      continue;
    }

    const category: AgentLoraCategory = modelName.startsWith("z-") ? "z-image" : "qwen";
    for (const rawLora of rawLoras) {
      const lora = normalizePathLora(rawLora);
      if (!lora) {
        continue;
      }
      pushUniqueLora(normalized, seenPaths, category, lora);
    }
  }

  return hasNormalizedLoras(normalized) ? normalized : undefined;
}

function normalizeProjectImageReference(value: unknown): AgentProjectImageSettingsReference | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = asTrimmedString(value.id);
  const resourceId = asTrimmedString(value.resourceId);
  if (!id || !resourceId) {
    return null;
  }

  return {
    id,
    resourceId,
    referenceMode: asReferenceMode(value.referenceMode),
    styleReferenceStrength: asOptionalNumber(value.styleReferenceStrength),
    subjectStrength: asOptionalNumber(value.subjectStrength),
    subjectDescription: asTrimmedString(value.subjectDescription) ?? undefined,
    inThisScene: asOptionalBoolean(value.inThisScene),
    inThisSceneStrength: asOptionalNumber(value.inThisSceneStrength),
  };
}

function normalizeProjectImageSettings(value: unknown): AgentProjectImageSettings | null {
  if (!isRecord(value)) {
    return null;
  }

  const selectedReferenceIdByShot = isRecord(value.selectedReferenceIdByShot)
    ? Object.fromEntries(
        Object.entries(value.selectedReferenceIdByShot)
          .filter(([key]) => typeof key === "string" && key.trim().length > 0)
          .map(([key, selection]) => [key, asTrimmedString(selection)]),
      )
    : undefined;
  const references = Array.isArray(value.references)
    ? value.references
      .map((reference) => normalizeProjectImageReference(reference))
      .filter((reference): reference is AgentProjectImageSettingsReference => reference !== null)
    : undefined;
  const selectedLorasByCategory = normalizeSelectedLorasByCategory(value.selectedLorasByCategory)
    ?? (value.selectedLorasByCategory === undefined
      ? normalizeLegacySelectedLorasByTextModel(value.selectedLorasByTextModel)
      : undefined);

  return {
    selectedTextModel: value.selectedTextModel === "qwen-image" || value.selectedTextModel === "qwen-image-2512" || value.selectedTextModel === "z-image"
      ? value.selectedTextModel
      : undefined,
    ...(references ? { references } : {}),
    ...(selectedReferenceIdByShot ? { selectedReferenceIdByShot } : {}),
    ...(selectedLorasByCategory ? { selectedLorasByCategory } : {}),
  };
}

function asTravelGenerationTypeMode(value: unknown): AgentVideoTravelSettings["generationTypeMode"] | undefined {
  return value === "i2v" || value === "vace" ? value : undefined;
}

function asTravelGenerationMode(value: unknown): AgentVideoTravelSettings["generationMode"] | undefined {
  return value === "batch" || value === "by-pair" || value === "timeline" ? value : undefined;
}

function normalizeTravelLora(
  value: unknown,
): AgentVideoTravelSettings["loras"][number] | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = asTrimmedString(value.id);
  const name = asTrimmedString(value.name);
  const path = asTrimmedString(value.path);
  const strength = asOptionalNumber(value.strength);
  if (!id || !name || !path || strength === undefined) {
    return null;
  }

  const lowNoisePath = asTrimmedString(value.lowNoisePath) ?? asTrimmedString(value.low_noise_path) ?? undefined;
  const isMultiStage = asOptionalBoolean(value.isMultiStage) ?? asOptionalBoolean(value.is_multi_stage);

  return {
    id,
    name,
    path,
    strength,
    ...(asTrimmedString(value.triggerWord) ?? asTrimmedString(value.trigger_word)
      ? { triggerWord: asTrimmedString(value.triggerWord) ?? asTrimmedString(value.trigger_word) ?? undefined }
      : {}),
    ...(lowNoisePath ? { lowNoisePath } : {}),
    ...(isMultiStage !== undefined ? { isMultiStage } : (lowNoisePath ? { isMultiStage: true } : {})),
  };
}

function resolveTravelModelDefaults(rawSettings: Record<string, unknown>, selectedModel: string): TravelModelDefaults {
  const modelDefaults = TRAVEL_MODEL_DEFAULTS[selectedModel] ?? TRAVEL_MODEL_DEFAULTS["wan-2.2"];
  const modelOverrides = isRecord(rawSettings.modelSettingsByModel)
    && isRecord(rawSettings.modelSettingsByModel[selectedModel])
    ? rawSettings.modelSettingsByModel[selectedModel]
    : null;

  return {
    frames: modelOverrides && asOptionalNumber(modelOverrides.batchVideoFrames) !== undefined
      ? asOptionalNumber(modelOverrides.batchVideoFrames) ?? modelDefaults.frames
      : asOptionalNumber(rawSettings.batchVideoFrames) ?? modelDefaults.frames,
    steps: modelOverrides && asOptionalNumber(modelOverrides.batchVideoSteps) !== undefined
      ? asOptionalNumber(modelOverrides.batchVideoSteps) ?? modelDefaults.steps
      : asOptionalNumber(rawSettings.batchVideoSteps) ?? modelDefaults.steps,
    guidanceScale: modelOverrides && asOptionalNumber(modelOverrides.guidanceScale) !== undefined
      ? asOptionalNumber(modelOverrides.guidanceScale)
      : (asOptionalNumber(rawSettings.guidanceScale) ?? modelDefaults.guidanceScale),
  };
}

function getStringListSearchField(value: unknown): string {
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0).join(" ")
    : "";
}

function getLoraModelFilePath(metadata: Record<string, unknown>): string | null {
  const modelFiles = metadata["Model Files"];
  if (!Array.isArray(modelFiles)) {
    return null;
  }

  const firstFile = modelFiles.find((entry) => isRecord(entry) && asTrimmedString(entry.path));
  return firstFile && isRecord(firstFile) ? asTrimmedString(firstFile.path) : null;
}

function buildResolvedReference(
  pointer: AgentProjectImageSettingsReference,
  metadataValue: unknown,
): ResolvedReference | null {
  if (!isRecord(metadataValue)) {
    return null;
  }

  const url = asTrimmedString(metadataValue.styleReferenceImage)
    ?? asTrimmedString(metadataValue.styleReferenceImageOriginal);
  if (!url) {
    return null;
  }

  return {
    url,
    referenceMode: pointer.referenceMode ?? asReferenceMode(metadataValue.referenceMode) ?? "style",
    styleReferenceStrength: pointer.styleReferenceStrength ?? asOptionalNumber(metadataValue.styleReferenceStrength) ?? 1.1,
    subjectStrength: pointer.subjectStrength ?? asOptionalNumber(metadataValue.subjectStrength) ?? 0,
    subjectDescription: pointer.subjectDescription ?? asTrimmedString(metadataValue.subjectDescription) ?? "",
    inThisScene: pointer.inThisScene ?? asOptionalBoolean(metadataValue.inThisScene) ?? false,
    inThisSceneStrength: pointer.inThisSceneStrength ?? asOptionalNumber(metadataValue.inThisSceneStrength) ?? 1,
  };
}

function reconcilePinnedShotGroupsForPersistence(
  config: TimelineConfig,
): TimelineConfig["pinnedShotGroups"] {
  if (!config.pinnedShotGroups?.length) {
    return config.pinnedShotGroups;
  }

  const clipById = new Map<string, TimelineClip>();
  for (const clip of config.clips) {
    clipById.set(clip.id, clip);
  }

  let changed = false;
  const nextGroups = config.pinnedShotGroups.flatMap((group) => {
    const seenClipIds = new Set<string>();
    const existingClips = group.clipIds.flatMap((clipId) => {
      if (seenClipIds.has(clipId)) {
        changed = true;
        return [];
      }

      seenClipIds.add(clipId);
      const clip = clipById.get(clipId);
      if (!clip) {
        changed = true;
        return [];
      }

      return [clip];
    });

    if (existingClips.length === 0) {
      changed = true;
      return [];
    }

    const orderedClipIds = [...existingClips]
      .sort((left, right) => {
        if (left.at !== right.at) {
          return left.at - right.at;
        }
        return left.id.localeCompare(right.id);
      })
      .map((clip) => clip.id);
    if (
      orderedClipIds.length !== group.clipIds.length
      || orderedClipIds.some((clipId, index) => clipId !== group.clipIds[index])
    ) {
      changed = true;
    }

    const candidateTrackIds = Array.from(new Set(existingClips.map((clip) => clip.track).filter((trackId) => trackId.trim().length > 0)));
    const nextTrackId = candidateTrackIds.length === 1 ? candidateTrackIds[0] : group.trackId;
    if (nextTrackId !== group.trackId) {
      changed = true;
    }

    return [{
      ...group,
      trackId: nextTrackId,
      clipIds: orderedClipIds,
    }];
  });

  return changed ? nextGroups : config.pinnedShotGroups;
}

export function prepareTimelineConfigForPersistence(
  config: TimelineConfig,
  registry: AssetRegistry,
): TimelineConfig {
  const reconciledPinnedShotGroups = reconcilePinnedShotGroupsForPersistence(config);
  const reconciledConfig = reconciledPinnedShotGroups === config.pinnedShotGroups
    ? config
    : {
        ...config,
        pinnedShotGroups: reconciledPinnedShotGroups,
      };

  return canonicalizeTimelinePair(reconciledConfig, registry).config;
}

export async function loadTimelineState(
  supabaseAdmin: SupabaseAdmin,
  timelineId: string,
): Promise<TimelineState> {
  const { data, error } = await supabaseAdmin
    .from("timelines")
    .select("config, config_version, asset_registry, project_id")
    .eq("id", timelineId)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to load timeline: ${error.message}`);
  }

  if (!data || !isRecord(data)) {
    throw new Error("Timeline not found");
  }

  const normalized = normalizeTimelineRow(data);
  const canonical = canonicalizeTimelinePair(normalized.config, normalized.asset_registry);
  const pinnedShotIds = Array.from(new Set(
    (canonical.config.pinnedShotGroups ?? [])
      .map((group) => asTrimmedString(group.shotId))
      .filter((shotId): shotId is string => shotId !== null),
  ));
  const shotNamesById: Record<string, string> = {};

  if (pinnedShotIds.length > 0) {
    const { data: shotsData, error: shotsError } = await supabaseAdmin
      .from("shots")
      .select("id, name")
      .in("id", pinnedShotIds);

    if (shotsError) {
      throw new Error(`Failed to load shot names: ${shotsError.message}`);
    }

    for (const row of Array.isArray(shotsData) ? shotsData : []) {
      if (!isRecord(row)) {
        continue;
      }

      const shotId = asTrimmedString(row.id);
      const shotName = asTrimmedString(row.name);
      if (shotId && shotName) {
        shotNamesById[shotId] = shotName;
      }
    }
  }

  return {
    config: canonical.config,
    configVersion: normalized.config_version,
    registry: canonical.registry,
    projectId: normalized.project_id,
    shotNamesById,
  };
}

export async function loadProjectImageSettings(
  supabaseAdmin: SupabaseAdmin,
  projectId: string,
): Promise<AgentProjectImageSettings | null> {
  const { data, error } = await supabaseAdmin
    .from("projects")
    .select("settings")
    .eq("id", projectId)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to load project image settings: ${error.message}`);
  }

  if (!data || !isRecord(data) || !isRecord(data.settings)) {
    return null;
  }

  return normalizeProjectImageSettings(data.settings["project-image-settings"]);
}

export async function loadShotVideoTravelSettings(
  supabaseAdmin: SupabaseAdmin,
  shotId?: string | null,
): Promise<AgentVideoTravelSettings | null> {
  if (!shotId) {
    return null;
  }

  const { data, error } = await supabaseAdmin
    .from("shots")
    .select("settings")
    .eq("id", shotId)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to load shot video travel settings: ${error.message}`);
  }

  if (!data || !isRecord(data) || !isRecord(data.settings)) {
    return null;
  }

  const rawSettings = data.settings["travel-between-images"];
  if (!isRecord(rawSettings)) {
    return null;
  }

  const selectedModel = asTrimmedString(rawSettings.selectedModel) ?? "wan-2.2";
  const modelDefaults = resolveTravelModelDefaults(rawSettings, selectedModel);
  const loras = Array.isArray(rawSettings.loras)
    ? rawSettings.loras
      .map((entry) => normalizeTravelLora(entry))
      .filter((entry): entry is AgentVideoTravelSettings["loras"][number] => entry !== null)
    : [];

  return {
    selectedModel,
    frames: modelDefaults.frames,
    steps: modelDefaults.steps,
    amountOfMotion: asOptionalNumber(rawSettings.amountOfMotion) ?? 50,
    guidanceScale: modelDefaults.guidanceScale,
    turboMode: asOptionalBoolean(rawSettings.turboMode) ?? false,
    enhancePrompt: asOptionalBoolean(rawSettings.enhancePrompt) ?? false,
    negativePrompt: asTrimmedString(rawSettings.negativePrompt) ?? undefined,
    textBeforePrompts: asTrimmedString(rawSettings.textBeforePrompts) ?? undefined,
    textAfterPrompts: asTrimmedString(rawSettings.textAfterPrompts) ?? undefined,
    generationTypeMode: asTravelGenerationTypeMode(rawSettings.generationTypeMode) ?? "i2v",
    generationMode: asTravelGenerationMode(rawSettings.generationMode) ?? "timeline",
    loras,
    phaseConfig: isRecord(rawSettings.phaseConfig) ? rawSettings.phaseConfig : undefined,
    smoothContinuations: asOptionalBoolean(rawSettings.smoothContinuations) ?? false,
  };
}

export async function searchLoras(
  supabaseAdmin: SupabaseAdmin,
  query: string,
  userId?: string,
): Promise<SearchLoraResult[]> {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return [];
  }

  const baseQuery = supabaseAdmin
    .from("resources")
    .select("id, metadata")
    .eq("type", "lora");
  const { data, error } = userId
    ? await baseQuery.or(`is_public.eq.true,user_id.eq.${userId}`).limit(200)
    : await baseQuery.eq("is_public", "true").limit(200);

  if (error) {
    throw new Error(`Failed to search loras: ${error.message}`);
  }

  if (!Array.isArray(data)) {
    return [];
  }

  return data.flatMap((entry) => {
    if (!isRecord(entry) || !isRecord(entry.metadata)) {
      return [];
    }

    const resourceId = asTrimmedString(entry.id);
    const metadata = entry.metadata;
    const name = asTrimmedString(metadata.Name);
    const path = getLoraModelFilePath(metadata);
    if (!resourceId || !name || !path) {
      return [];
    }

    const triggerWord = asTrimmedString(metadata.trigger_word) ?? undefined;
    const baseModel = asTrimmedString(metadata.base_model) ?? undefined;
    const description = asTrimmedString(metadata.Description) ?? undefined;
    const highNoiseUrl = asTrimmedString(metadata.high_noise_url) ?? undefined;
    const lowNoiseUrl = asTrimmedString(metadata.low_noise_url) ?? undefined;
    const haystack = [
      name,
      getStringListSearchField(metadata.Tags),
      description ?? "",
      triggerWord ?? "",
      baseModel ?? "",
    ].join(" ").toLowerCase();

    if (!haystack.includes(normalizedQuery)) {
      return [];
    }

    return [{
      resourceId,
      name,
      path,
      ...(triggerWord ? { triggerWord } : {}),
      ...(baseModel ? { baseModel } : {}),
      ...(description ? { description } : {}),
      ...(highNoiseUrl ? { highNoiseUrl } : {}),
      ...(lowNoiseUrl ? { lowNoiseUrl } : {}),
    }];
  }).slice(0, 10);
}

export async function updateShotLoras(
  supabaseAdmin: SupabaseAdmin,
  shotId: string,
  loras: AgentVideoTravelSettings["loras"],
): Promise<void> {
  const { data, error } = await supabaseAdmin
    .from("shots")
    .select("settings")
    .eq("id", shotId)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to load shot settings for LoRA update: ${error.message}`);
  }

  const currentSettings = data && isRecord(data) && isRecord(data.settings) ? data.settings : {};
  const currentTravelSettings = isRecord(currentSettings["travel-between-images"])
    ? currentSettings["travel-between-images"]
    : {};
  const nextSettings = {
    ...currentSettings,
    "travel-between-images": {
      ...currentTravelSettings,
      loras,
    },
  };

  const updateResult = await supabaseAdmin
    .from("shots")
    .update({ settings: nextSettings })
    .eq("id", shotId);

  if (updateResult.error) {
    throw new Error(`Failed to update shot loras: ${updateResult.error.message}`);
  }
}

export async function updateProjectImageLoras(
  supabaseAdmin: SupabaseAdmin,
  projectId: string,
  category: AgentLoraCategory,
  loras: AgentPathLora[],
): Promise<void> {
  const { data, error } = await supabaseAdmin
    .from("projects")
    .select("settings")
    .eq("id", projectId)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to load project image settings for LoRA update: ${error.message}`);
  }

  const currentSettings = data && isRecord(data) && isRecord(data.settings) ? data.settings : {};
  const currentProjectImageSettings = isRecord(currentSettings["project-image-settings"])
    ? currentSettings["project-image-settings"]
    : {};
  const currentSelectedLorasByCategory = isRecord(currentProjectImageSettings.selectedLorasByCategory)
    ? currentProjectImageSettings.selectedLorasByCategory
    : {};
  const nextSettings = {
    ...currentSettings,
    "project-image-settings": {
      ...currentProjectImageSettings,
      selectedLorasByCategory: {
        ...currentSelectedLorasByCategory,
        [category]: loras,
      },
    },
  };

  const updateResult = await supabaseAdmin
    .from("projects")
    .update({ settings: nextSettings })
    .eq("id", projectId);

  if (updateResult.error) {
    throw new Error(`Failed to update project image loras: ${updateResult.error.message}`);
  }
}

export async function loadActiveReference(
  supabaseAdmin: SupabaseAdmin,
  settings: AgentProjectImageSettings | null,
  shotId?: string,
): Promise<ResolvedReference | null> {
  if (!settings) {
    return null;
  }

  const selectedReferenceId = settings.selectedReferenceIdByShot?.[shotId ?? "none"] ?? null;
  if (!selectedReferenceId) {
    return null;
  }

  const pointer = settings.references?.find((reference) => reference.id === selectedReferenceId);
  if (!pointer) {
    return null;
  }

  const { data, error } = await supabaseAdmin
    .from("resources")
    .select("type, metadata")
    .eq("id", pointer.resourceId)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to load active reference: ${error.message}`);
  }

  if (!data || !isRecord(data) || data.type !== "style-reference") {
    return null;
  }

  return buildResolvedReference(pointer, data.metadata);
}

export async function saveTimelineConfigVersioned(
  supabaseAdmin: SupabaseAdmin,
  timelineId: string,
  expectedVersion: number,
  config: TimelineConfig,
  retries = 2,
): Promise<number | null> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const { data, error } = await supabaseAdmin
        .rpc("update_timeline_config_versioned", {
          p_timeline_id: timelineId,
          p_expected_version: expectedVersion,
          p_config: config,
        })
        .maybeSingle();

      if (error) {
        // Connection errors are retryable
        if (attempt < retries && (error.message.includes("connection") || error.message.includes("reset") || error.message.includes("SendRequest"))) {
          console.warn(`[agent] DB save failed (attempt ${attempt + 1}), retrying: ${error.message}`);
          await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
          continue;
        }
        throw new Error(`Failed to save timeline config: ${error.message}`);
      }

      const nextVersion = (data as { config_version?: unknown } | null)?.config_version;
      return typeof nextVersion === "number" ? nextVersion : null;
    } catch (err: unknown) {
      if (attempt < retries && err instanceof Error && (err.message.includes("connection") || err.message.includes("reset") || err.message.includes("SendRequest"))) {
        console.warn(`[agent] DB save threw (attempt ${attempt + 1}), retrying: ${err.message}`);
        await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
        continue;
      }
      throw err;
    }
  }
  throw new Error("Failed to save timeline config after retries");
}

export async function loadSessionStatus(
  supabaseAdmin: SupabaseAdmin,
  sessionId: string,
): Promise<AgentSessionStatus | null> {
  const { data, error } = await supabaseAdmin
    .from("timeline_agent_sessions")
    .select("status")
    .eq("id", sessionId)
    .maybeSingle();

  if (error || !data || !isRecord(data)) {
    return null;
  }

  return isSessionStatus(data.status) ? data.status : null;
}

export async function persistSessionState(
  supabaseAdmin: SupabaseAdmin,
  options: {
    sessionId: string;
    status: AgentSessionStatus;
    turns: AgentTurn[];
    summary: string | null;
  },
): Promise<void> {
  const { error } = await supabaseAdmin
    .from("timeline_agent_sessions")
    .update({
      status: options.status,
      turns: options.turns,
      summary: options.summary,
      updated_at: new Date().toISOString(),
    })
    .eq("id", options.sessionId);

  if (error) {
    throw new Error(`Failed to persist session state: ${error.message}`);
  }
}

// ── Task queries ──────────────────────────────────────────────────────

export interface AgentTaskSummary {
  id: string;
  task_type: string;
  status: string;
  created_at: string;
  generation_started_at: string | null;
  generation_processed_at: string | null;
  error_message: string | null;
  attempts: number;
  params_summary: string;
}

const TASK_SELECT_COLUMNS =
  "id, task_type, status, created_at, generation_started_at, generation_processed_at, error_message, attempts, params";

function summarizeTaskParams(params: unknown): string {
  if (!isRecord(params)) return "";
  const parts: string[] = [];
  if (typeof params.model_name === "string") parts.push(`model=${params.model_name}`);
  if (typeof params.prompt === "string") parts.push(`prompt="${params.prompt.slice(0, 80)}${params.prompt.length > 80 ? "…" : ""}"`);
  if (typeof params.task_type === "string" && !parts.length) parts.push(`type=${params.task_type}`);
  return parts.join(", ");
}

function rowToTaskSummary(row: Record<string, unknown>): AgentTaskSummary {
  return {
    id: String(row.id ?? ""),
    task_type: String(row.task_type ?? ""),
    status: String(row.status ?? ""),
    created_at: String(row.created_at ?? ""),
    generation_started_at: row.generation_started_at ? String(row.generation_started_at) : null,
    generation_processed_at: row.generation_processed_at ? String(row.generation_processed_at) : null,
    error_message: row.error_message ? String(row.error_message) : null,
    attempts: typeof row.attempts === "number" ? row.attempts : 0,
    params_summary: summarizeTaskParams(row.params),
  };
}

export async function fetchProjectTasks(
  supabaseAdmin: SupabaseAdmin,
  projectId: string,
  options?: { status?: string; taskId?: string; limit?: number },
): Promise<AgentTaskSummary[]> {
  if (options?.taskId) {
    const { data, error } = await supabaseAdmin
      .from("tasks")
      .select(TASK_SELECT_COLUMNS)
      .eq("id", options.taskId)
      .maybeSingle();
    if (error) throw new Error(`Failed to fetch task: ${error.message}`);
    if (!data || !isRecord(data)) return [];
    return [rowToTaskSummary(data)];
  }

  let query = supabaseAdmin
    .from("tasks")
    .select(TASK_SELECT_COLUMNS)
    .eq("project_id", projectId)
    .order("created_at", { ascending: false })
    .limit(Math.min(options?.limit ?? 10, 50));

  if (options?.status) {
    query = query.eq("status", options.status);
  }

  const { data, error } = await query;
  if (error) throw new Error(`Failed to fetch tasks: ${error.message}`);
  if (!Array.isArray(data)) return [];
  return data.filter(isRecord).map(rowToTaskSummary);
}
