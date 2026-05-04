import type { AssetRegistry, AssetRegistryEntry, TimelineConfig, TimelineClip } from "../../../../src/tools/video-editor/index.ts";
import { getAdminSupabaseClient, signInHarnessUser, type TestUserAuth } from "./client.ts";

const TEST_IMAGE_URLS = [
  "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Fronalpstock_big.jpg/1280px-Fronalpstock_big.jpg",
  "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Red_sunflower.jpg/1280px-Red_sunflower.jpg",
  "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/Otters_in_Shibukawa.jpg/1280px-Otters_in_Shibukawa.jpg",
] as const;

export interface TestTimelineFixture {
  projectId: string;
  timelineId: string;
  config: TimelineConfig;
  assetRegistry: AssetRegistry;
}

export interface TestSessionFixture {
  sessionId: string;
  timelineId: string;
  userId: string;
}

function createRegistryEntry(file: string): AssetRegistryEntry {
  return {
    file,
    type: "image/jpeg",
    duration: 4,
    resolution: "1280x720",
    generationId: crypto.randomUUID(),
    variantId: crypto.randomUUID(),
  };
}

function buildDefaultClips(): TimelineClip[] {
  return TEST_IMAGE_URLS.map((_, index) => ({
    id: `harness-clip-${index + 1}`,
    at: index * 4,
    track: "V1",
    clipType: "media",
    asset: `harness-asset-${index + 1}`,
    hold: 4,
    x: 0,
    y: 0,
    width: 1280,
    height: 720,
    opacity: 1,
  }));
}

function buildAssetRegistryForConfig(config: TimelineConfig): AssetRegistry {
  const assets: Record<string, AssetRegistryEntry> = {};
  let fallbackIndex = 0;

  for (const clip of config.clips) {
    if (!clip.asset || assets[clip.asset]) {
      continue;
    }

    const file = TEST_IMAGE_URLS[fallbackIndex % TEST_IMAGE_URLS.length];
    assets[clip.asset] = createRegistryEntry(file);
    fallbackIndex += 1;
  }

  return { assets };
}

export function buildDefaultTestTimelineConfig(): TimelineConfig {
  return {
    output: {
      resolution: "1280x720",
      fps: 30,
      file: "output.mp4",
      background: null,
      background_scale: null,
    },
    tracks: [
      {
        id: "V1",
        kind: "visual",
        label: "V1",
        scale: 1,
        fit: "contain",
        opacity: 1,
        blendMode: "normal",
      },
    ],
    clips: buildDefaultClips(),
  };
}

export async function getOrCreateTestUser(): Promise<TestUserAuth> {
  return await signInHarnessUser();
}

export async function createTestTimeline(
  userId: string,
  config?: TimelineConfig,
): Promise<TestTimelineFixture> {
  const supabase = getAdminSupabaseClient();
  const timelineConfig = structuredClone(config ?? buildDefaultTestTimelineConfig());
  const assetRegistry = buildAssetRegistryForConfig(timelineConfig);

  const { data: project, error: projectError } = await supabase
    .from("projects")
    .insert({
      user_id: userId,
      name: `Harness Project ${new Date().toISOString()}`,
      aspect_ratio: "16:9",
      settings: {
        created_by: "timeline-agent-harness",
        "project-image-settings": {
          selectedTextModel: "qwen-image",
          generationSource: "just-text",
          selectedLorasByCategory: {
            qwen: [
              {
                id: "harness-lora-1",
                name: "Harness Test LoRA",
                path: "https://huggingface.co/test/harness-lora/resolve/main/test.safetensors",
                strength: 0.8,
              },
            ],
            "z-image": [],
          },
        },
      },
    })
    .select("id")
    .single();

  if (projectError || typeof project?.id !== "string") {
    throw new Error(`Failed to create harness project: ${projectError?.message ?? "missing project id"}`);
  }

  const { data: timeline, error: timelineError } = await supabase
    .from("timelines")
    .insert({
      project_id: project.id,
      user_id: userId,
      name: `Harness Timeline ${new Date().toISOString()}`,
      config: timelineConfig,
      asset_registry: assetRegistry,
    })
    .select("id")
    .single();

  if (timelineError || typeof timeline?.id !== "string") {
    throw new Error(`Failed to create harness timeline: ${timelineError?.message ?? "missing timeline id"}`);
  }

  // Insert placeholder generation rows so that asset registry generationIds are
  // resolvable by the agent (e.g. for shot creation during style-transfer).
  const generationRows = Object.values(assetRegistry.assets)
    .filter((entry) => typeof entry.generationId === "string" && entry.generationId.trim())
    .map((entry) => ({
      id: entry.generationId!,
      project_id: project.id,
      location: entry.file,
    }));

  if (generationRows.length > 0) {
    const { error: generationError } = await supabase.from("generations").insert(generationRows);
    if (generationError) {
      throw new Error(`Failed to create harness generation rows: ${generationError.message}`);
    }

    // Create a shot and link generations via shot_generations so that
    // duplicate_generation can resolve shot_id and timeline_frame.
    const { data: shot, error: shotError } = await supabase
      .from("shots")
      .insert({
        project_id: project.id,
        name: "Harness Shot",
        position: 0,
        aspect_ratio: "16:9",
      })
      .select("id")
      .single();

    if (shotError || typeof shot?.id !== "string") {
      throw new Error(`Failed to create harness shot: ${shotError?.message ?? "missing shot id"}`);
    }

    const shotGenerationRows = generationRows.map((gen, index) => ({
      shot_id: shot.id,
      generation_id: gen.id,
      timeline_frame: index * 50,
    }));

    const { error: sgError } = await supabase.from("shot_generations").insert(shotGenerationRows);
    if (sgError) {
      throw new Error(`Failed to create harness shot_generations: ${sgError.message}`);
    }
  }

  return {
    projectId: project.id,
    timelineId: timeline.id,
    config: timelineConfig,
    assetRegistry,
  };
}

export async function createTestSession(
  timelineId: string,
  userId: string,
): Promise<TestSessionFixture> {
  const supabase = getAdminSupabaseClient();
  const { data, error } = await supabase
    .from("timeline_agent_sessions")
    .insert({
      timeline_id: timelineId,
      user_id: userId,
      status: "waiting_user",
      turns: [],
      model: "groq",
    })
    .select("id, timeline_id, user_id")
    .single();

  if (error || typeof data?.id !== "string") {
    throw new Error(`Failed to create harness session: ${error?.message ?? "missing session id"}`);
  }

  return {
    sessionId: data.id,
    timelineId: typeof data.timeline_id === "string" ? data.timeline_id : timelineId,
    userId: typeof data.user_id === "string" ? data.user_id : userId,
  };
}

async function logCleanupFailure(label: string, error: unknown): Promise<void> {
  const message = error instanceof Error ? error.message : String(error);
  console.warn(`[harness.cleanup] ${label}: ${message}`);
}

async function runCleanupStep(
  label: string,
  action: () => PromiseLike<{ error: { message: string } | null }>,
): Promise<void> {
  try {
    const { error } = await action();
    if (error) {
      await logCleanupFailure(label, error.message);
    }
  } catch (error) {
    await logCleanupFailure(label, error);
  }
}

export async function cleanupTestData(projectId: string): Promise<void> {
  const supabase = getAdminSupabaseClient();

  const [{ data: timelines }, { data: tasks }, { data: generations }, { data: shots }] = await Promise.all([
    supabase.from("timelines").select("id").eq("project_id", projectId),
    supabase.from("tasks").select("id").eq("project_id", projectId),
    supabase.from("generations").select("id").eq("project_id", projectId),
    supabase.from("shots").select("id").eq("project_id", projectId),
  ]);

  const timelineIds = (timelines ?? []).flatMap((row) => typeof row?.id === "string" ? [row.id] : []);
  const taskIds = (tasks ?? []).flatMap((row) => typeof row?.id === "string" ? [row.id] : []);
  const generationIds = (generations ?? []).flatMap((row) => typeof row?.id === "string" ? [row.id] : []);
  const shotIds = (shots ?? []).flatMap((row) => typeof row?.id === "string" ? [row.id] : []);

  if (taskIds.length > 0) {
    await runCleanupStep("delete credits_ledger", () => supabase.from("credits_ledger").delete().in("task_id", taskIds));
  }

  if (timelineIds.length > 0) {
    await runCleanupStep("delete timeline_agent_sessions", () => supabase.from("timeline_agent_sessions").delete().in("timeline_id", timelineIds));
  }

  if (shotIds.length > 0) {
    await runCleanupStep("delete shot_generations by shot", () => supabase.from("shot_generations").delete().in("shot_id", shotIds));
  }

  if (generationIds.length > 0) {
    await runCleanupStep("delete shot_generations by generation", () => supabase.from("shot_generations").delete().in("generation_id", generationIds));

    // Disarm the original-variant deletion protection trigger:
    // 1. Clear primary_variant_id FK on generations (breaks circular reference)
    // 2. Re-type "original" variants so the BEFORE DELETE trigger's WHEN clause doesn't match
    await runCleanupStep("clear primary_variant_id", () => supabase.from("generations").update({ primary_variant_id: null }).in("id", generationIds));
    await runCleanupStep("retype original variants for cleanup", () =>
      supabase
        .from("generation_variants")
        .update({ variant_type: "test_cleanup" })
        .in("generation_id", generationIds)
        .eq("variant_type", "original"),
    );

    await runCleanupStep("delete generation_variants", () => supabase.from("generation_variants").delete().in("generation_id", generationIds));
  }

  for (const [label, action] of [
    ["delete generations", () => supabase.from("generations").delete().eq("project_id", projectId)],
    ["delete tasks", () => supabase.from("tasks").delete().eq("project_id", projectId)],
    ["delete shots", () => supabase.from("shots").delete().eq("project_id", projectId)],
    ["delete timelines", () => supabase.from("timelines").delete().eq("project_id", projectId)],
    ["delete project", () => supabase.from("projects").delete().eq("id", projectId)],
  ] as const) {
    await runCleanupStep(label, action);
  }
}
