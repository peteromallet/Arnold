// deno-lint-ignore-file

import type { AssetRegistry, TimelineConfig } from "../../../src/tools/video-editor/index.ts";

declare const Deno: { env: { get: (key: string) => string | undefined } };

const APPEND_SERVICE_URL_ENV = "REIGH_APPEND_SERVICE_URL";
const APPEND_SERVICE_INTERNAL_TOKEN_ENV = "REIGH_APPEND_SERVICE_INTERNAL_TOKEN";

type TimelineImportSource = "legacy_local" | "supabase_config" | "editor_save" | "other";
type TimelineActor = {
  type: "agent" | "human" | "system";
  id: string;
  display?: string;
};

type AppendServiceSuccess = {
  timeline_id?: string;
  config_version?: number;
  inserted_event_ids?: string[];
  events?: unknown[];
};

type AppendServiceFailure = {
  error?: string;
  detail?: string;
  details?: unknown;
};

export class ReighAppendServiceError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string | null;

  constructor(
    status: number,
    code: string,
    detail: string | null,
  ) {
    super(detail ? `append service failed: ${code}: ${detail}` : `append service failed: ${code}`);
    this.name = "ReighAppendServiceError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

function requireEnv(name: string): string {
  const value = Deno.env.get(name)?.trim();
  if (!value) {
    throw new Error(`Missing ${name}`);
  }
  return value;
}

function getAppendServiceBaseUrl(): string {
  return requireEnv(APPEND_SERVICE_URL_ENV).replace(/\/+$/, "");
}

function getAppendServiceToken(): string {
  return requireEnv(APPEND_SERVICE_INTERNAL_TOKEN_ENV);
}

async function parseJsonIfPresent(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function postAppendService(
  path: string,
  body: Record<string, unknown>,
): Promise<AppendServiceSuccess> {
  const response = await fetch(`${getAppendServiceBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAppendServiceToken()}`,
    },
    body: JSON.stringify(body),
  });

  const payload = await parseJsonIfPresent(response);
  if (!response.ok) {
    const errorPayload = typeof payload === "object" && payload !== null
      ? payload as AppendServiceFailure
      : null;
    throw new ReighAppendServiceError(
      response.status,
      errorPayload?.error ?? (response.statusText.toLowerCase().replace(/\s+/g, "_") || "append_service_error"),
      errorPayload?.detail
        ?? (typeof errorPayload?.details === "string" ? errorPayload.details : null)
        ?? (typeof payload === "string" && payload.trim() ? payload : null),
    );
  }

  if (typeof payload !== "object" || payload === null) {
    throw new Error("append service returned a non-object response");
  }
  return payload as AppendServiceSuccess;
}

function extractConfigVersion(
  response: AppendServiceSuccess,
  operation: string,
): number {
  if (typeof response.config_version !== "number" || !Number.isFinite(response.config_version)) {
    throw new Error(`${operation} returned an invalid config_version`);
  }
  return response.config_version;
}

export async function appendTimelineConfigViaService(input: {
  timelineId: string;
  expectedVersion: number;
  config: TimelineConfig;
  assetRegistry?: AssetRegistry | null;
  actor: TimelineActor;
  source: TimelineImportSource;
}): Promise<number> {
  const response = await postAppendService(
    `/v1/timelines/${encodeURIComponent(input.timelineId)}/config-replaced`,
    {
      config: input.config,
      asset_registry: input.assetRegistry ?? undefined,
      expected_version: input.expectedVersion,
      actor: input.actor,
      source: input.source,
    },
  );
  return extractConfigVersion(response, "append_config_replaced");
}

export async function createTimelineViaService(input: {
  projectId: string;
  timelineId: string;
  userId: string;
  config: TimelineConfig;
  assetRegistry?: AssetRegistry | null;
  actor: TimelineActor;
  source: TimelineImportSource;
  name?: string;
}): Promise<number> {
  const response = await postAppendService(
    "/v1/timelines/create-with-config",
    {
      project_id: input.projectId,
      timeline_id: input.timelineId,
      user_id: input.userId,
      config: input.config,
      asset_registry: input.assetRegistry ?? undefined,
      actor: input.actor,
      source: input.source,
      name: input.name,
    },
  );
  return extractConfigVersion(response, "create_with_config");
}
