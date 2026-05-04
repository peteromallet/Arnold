// deno-lint-ignore-file
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";
import { TimelineConfig as TimelineConfigSchema } from "@banodoco/timeline-schema";
import {
  serializeTimelineConfigSnapshot,
  serializeTimelinePair,
  TimelineDomainError,
  type AssetRegistry,
  type TimelineConfig,
} from "../../../src/tools/video-editor/index.ts";
import { validateTimelinePayload } from "./validate.ts";
import type {
  TimelineImportBody,
  TimelineImportResponseBody,
} from "./types.ts";

interface Logger {
  info(message: string, context?: Record<string, unknown>): void;
  warn(message: string, context?: Record<string, unknown>): void;
  error(message: string, context?: Record<string, unknown>): void;
}

interface OwnershipVerifier {
  (projectId: string, userId: string): Promise<{
    success: boolean;
    error?: string;
    statusCode?: number;
  }>;
}

function canonicalizeImportPayload(
  timeline: Record<string, unknown>,
  assetRegistry: Record<string, unknown> | null,
): { config: TimelineConfig; assetRegistry: AssetRegistry | null } {
  const typedTimeline = timeline as TimelineConfig;

  if (assetRegistry === null) {
    const serialized = serializeTimelineConfigSnapshot(typedTimeline);
    return {
      config: serialized.config,
      assetRegistry: null,
    };
  }

  const serialized = serializeTimelinePair(
    typedTimeline,
    assetRegistry as AssetRegistry,
  );
  return {
    config: serialized.config,
    assetRegistry: serialized.registry,
  };
}

export interface HandleTimelineImportInput {
  body: TimelineImportBody;
  userId: string;
  supabaseAdmin: SupabaseClient;
  logger: Logger;
  verifyOwnership: OwnershipVerifier;
}

export interface HandleTimelineImportResult {
  status: number;
  body: TimelineImportResponseBody;
}

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
  );
}

export async function handleTimelineImport(
  input: HandleTimelineImportInput,
): Promise<HandleTimelineImportResult> {
  const { body, userId, supabaseAdmin, logger, verifyOwnership } = input;

  if (!isUuid(body.project_id)) {
    return { status: 400, body: { ok: false, error: "project_id must be a uuid" } };
  }
  if (!isUuid(body.timeline_id)) {
    return { status: 400, body: { ok: false, error: "timeline_id must be a uuid" } };
  }
  const projectId = body.project_id;
  const timelineId = body.timeline_id;
  const createIfMissing = body.create_if_missing === true;
  const expectedVersionRaw = body.expected_version;
  const expectedVersion =
    typeof expectedVersionRaw === "number" && Number.isFinite(expectedVersionRaw)
      ? Math.trunc(expectedVersionRaw)
      : null;

  // Shape-validate the timeline against the canonical Zod schema before
  // doing anything else. Reigh's runtime treats unknown clipTypes with the
  // loud-placeholder fallback, so we purposely do NOT enforce the strict
  // effect-id registry here — that's the authoring surface's job.
  const parsed = TimelineConfigSchema.safeParse(body.timeline);
  if (!parsed.success) {
    return {
      status: 400,
      body: {
        ok: false,
        error: "timeline payload failed schema validation",
        details: parsed.error.message,
      },
    };
  }
  const validated = validateTimelinePayload(body);
  if (!validated.ok) {
    return {
      status: 400,
      body: { ok: false, error: validated.error },
    };
  }

  let canonicalized: ReturnType<typeof canonicalizeImportPayload>;
  try {
    canonicalized = canonicalizeImportPayload(validated.timeline, validated.assetRegistry);
  } catch (error) {
    if (error instanceof TimelineDomainError) {
      return {
        status: 400,
        body: {
          ok: false,
          error: "timeline payload failed canonical validation",
          details: {
            level: error.level,
            issues: error.issues,
          },
        },
      };
    }
    throw error;
  }

  // Ownership check: the JWT subject must own the project. SD-022: the user
  // JWT authorizes intent; the service-role key is then used for the actual
  // DB write below. authenticateRequest() already verified the JWT and gave
  // us userId; verifyProjectOwnership compares against projects.user_id.
  const ownership = await verifyOwnership(projectId, userId);
  if (!ownership.success) {
    return {
      status: ownership.statusCode ?? 403,
      body: {
        ok: false,
        error: ownership.error ?? "Forbidden",
      },
    };
  }

  // Lookup current row + version. We need this for: (a) 404/create_if_missing
  // branching, (b) timeline.project_id ownership check, (c) --force fetch.
  const { data: existing, error: lookupError } = await supabaseAdmin
    .from("timelines")
    .select("id, project_id, config_version")
    .eq("id", timelineId)
    .maybeSingle();

  if (lookupError) {
    logger.error("timeline lookup failed", { error: lookupError.message });
    return {
      status: 500,
      body: { ok: false, error: "failed to load timeline", details: lookupError.message },
    };
  }

  if (!existing) {
    if (!createIfMissing) {
      return {
        status: 404,
        body: { ok: false, error: "timeline not found" },
      };
    }
    return await insertNewTimeline({
      supabaseAdmin,
      logger,
      projectId,
      timelineId,
      timelineConfig: canonicalized.config,
      assetRegistry: canonicalized.assetRegistry,
    });
  }

  if (existing.project_id !== projectId) {
    return {
      status: 403,
      body: {
        ok: false,
        error: "timeline belongs to a different project",
      },
    };
  }

  // Version handshake. expected_version is omitted on --force; we then
  // adopt the current version as the expected value (last-write-wins).
  const versionToSend = expectedVersion ?? existing.config_version;

  return await callVersionedRpc({
    supabaseAdmin,
    logger,
    timelineId,
    timelineConfig: canonicalized.config,
    assetRegistry: canonicalized.assetRegistry,
    expectedVersion: versionToSend,
    currentVersion: existing.config_version,
  });
}

interface InsertNewTimelineInput {
  supabaseAdmin: SupabaseClient;
  logger: Logger;
  projectId: string;
  timelineId: string;
  timelineConfig: TimelineConfig;
  assetRegistry: AssetRegistry | null;
}

async function insertNewTimeline(
  input: InsertNewTimelineInput,
): Promise<HandleTimelineImportResult> {
  const { supabaseAdmin, logger, projectId, timelineId, timelineConfig, assetRegistry } = input;
  const { data, error } = await supabaseAdmin
    .from("timelines")
    .insert({
      id: timelineId,
      project_id: projectId,
      config: timelineConfig,
      asset_registry: assetRegistry ?? { assets: {} },
      config_version: 1,
    })
    .select("config_version")
    .single();
  if (error) {
    logger.error("timeline insert failed", { error: error.message });
    return {
      status: 500,
      body: { ok: false, error: "timeline insert failed", details: error.message },
    };
  }
  return {
    status: 201,
    body: {
      ok: true,
      config_version: typeof data?.config_version === "number" ? data.config_version : 1,
      created: true,
    },
  };
}

interface CallVersionedRpcInput {
  supabaseAdmin: SupabaseClient;
  logger: Logger;
  timelineId: string;
  timelineConfig: TimelineConfig;
  assetRegistry: AssetRegistry | null;
  expectedVersion: number;
  currentVersion: number;
}

async function callVersionedRpc(
  input: CallVersionedRpcInput,
): Promise<HandleTimelineImportResult> {
  const {
    supabaseAdmin,
    logger,
    timelineId,
    timelineConfig,
    assetRegistry,
    expectedVersion,
    currentVersion,
  } = input;
  const useAssetVariant = assetRegistry !== null;
  const rpcName = useAssetVariant
    ? "update_timeline_versioned"
    : "update_timeline_config_versioned";
  const params = useAssetVariant
    ? {
      p_timeline_id: timelineId,
      p_expected_version: expectedVersion,
      p_config: timelineConfig,
      p_asset_registry: assetRegistry,
    }
    : {
      p_timeline_id: timelineId,
      p_expected_version: expectedVersion,
      p_config: timelineConfig,
    };
  const { data, error } = await supabaseAdmin.rpc(rpcName as never, params as never);
  if (error) {
    logger.error("versioned rpc failed", { error: error.message, rpc: rpcName });
    return {
      status: 500,
      body: { ok: false, error: "rpc failed", details: error.message },
    };
  }
  const rows = (data ?? []) as Array<{ config_version: number }>;
  if (rows.length === 0) {
    return {
      status: 409,
      body: { ok: false, error: "version_mismatch", current_version: currentVersion },
    };
  }
  return {
    status: 200,
    body: { ok: true, config_version: rows[0].config_version, created: false },
  };
}
