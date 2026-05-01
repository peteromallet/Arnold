import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { bootstrapEdgeHandler, NO_SESSION_RUNTIME_OPTIONS } from "../_shared/edgeHandler.ts";
import { edgeErrorResponse } from "../_shared/edgeRequest.ts";
import { jsonResponse } from "../_shared/http.ts";
import {
  enforceRateLimit,
  RATE_LIMITS,
} from "../_shared/rateLimit.ts";
import type { SupabaseClient } from "../_shared/supabaseClient.ts";
import { getErrorMessage } from "./request.ts";
import { JWT_AUTH_REQUIRED } from "../_shared/requestGuards.ts";
import { getTaskFamilyResolver } from "./resolvers/registry.ts";
import { createWorkerPassthroughResolver } from "./resolvers/workerPassthrough.ts";
import { TaskValidationError } from "./resolvers/shared/validation.ts";
import type { ResolveRequest } from "./resolvers/types.ts";

function createErrorResponse(
  message: string,
  status: number,
  errorCode: string,
  recoverable = status >= 500 || status === 429,
) {
  return edgeErrorResponse({ errorCode, message, recoverable }, status);
}

function isAuthorizedIdempotentRecoveryProject(
  existingProjectId: unknown,
  requestedProjectId: string,
): boolean {
  return typeof existingProjectId === "string" && existingProjectId === requestedProjectId;
}

interface InsertTaskSuccess {
  ok: true;
  taskId: string;
  deduplicated: boolean;
}

interface InsertTaskFailure {
  ok: false;
  response: Response;
}

type InsertTaskResult = InsertTaskSuccess | InsertTaskFailure;

interface ParseResolverRequestSuccess {
  ok: true;
  value: ResolveRequest;
}

interface ParseResolverRequestFailure {
  ok: false;
  error: string;
}

type ParseResolverRequestResult = ParseResolverRequestSuccess | ParseResolverRequestFailure;

interface InsertTaskWithRecoveryOptions {
  supabaseAdmin: SupabaseClient;
  insertObject: TaskInsertObject;
  idempotencyKey?: string;
  finalProjectId: string;
  isServiceRole: boolean;
  logger: {
    info: (message: string, context?: Record<string, unknown>) => void;
    error: (message: string, context?: Record<string, unknown>) => void;
    flush: () => Promise<void>;
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asNonEmptyString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function parseRequestIdempotencyKey(body: unknown): string | undefined {
  if (!isRecord(body)) {
    return undefined;
  }

  return asNonEmptyString(body.idempotency_key) ?? undefined;
}

function parseResolverRequest(body: unknown): ParseResolverRequestResult | null {
  if (!isRecord(body) || !("family" in body)) {
    return null;
  }

  const family = asNonEmptyString(body.family);
  if (!family) {
    return { ok: false, error: "family must be a non-empty string when provided" };
  }

  const projectId = asNonEmptyString(body.project_id);
  if (!projectId) {
    return { ok: false, error: "project_id required" };
  }

  if (!isRecord(body.input)) {
    return { ok: false, error: "input must be an object when family is provided" };
  }

  return {
    ok: true,
    value: {
      family,
      project_id: projectId,
      input: body.input,
    },
  };
}

async function sha256Hex(value: string): Promise<string> {
  const buffer = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function deriveBatchIdempotencyKey(baseKey: string, taskIndex: number): Promise<string> {
  return await sha256Hex(`${baseKey}:${taskIndex}`);
}

async function resolveInsertIdempotencyKey(
  insertObject: TaskInsertObject,
  requestIdempotencyKey: string | undefined,
  taskIndex: number,
  taskCount: number,
): Promise<string | undefined> {
  if (taskCount > 1 && requestIdempotencyKey) {
    return await deriveBatchIdempotencyKey(requestIdempotencyKey, taskIndex);
  }

  return insertObject.idempotency_key ?? requestIdempotencyKey;
}

function buildTaskInsertPayload(
  insertObject: TaskInsertObject,
  idempotencyKey: string | undefined,
): TaskInsertObject {
  if (!idempotencyKey) {
    const { idempotency_key: _idempotencyKey, ...payloadWithoutIdempotencyKey } = insertObject;
    return payloadWithoutIdempotencyKey;
  }

  return {
    ...insertObject,
    idempotency_key: idempotencyKey,
  };
}

function buildCreateTaskResponse(
  taskIds: string[],
  options?: {
    deduplicated?: boolean;
    meta?: Record<string, unknown>;
  },
): Response {
  if (taskIds.length === 1) {
    return jsonResponse({
      task_id: taskIds[0],
      status: "Task queued",
      ...(options?.meta ? { meta: options.meta } : {}),
      ...(options?.deduplicated ? { deduplicated: true } : {}),
    });
  }

  return jsonResponse({
    task_ids: taskIds,
    status: "Task queued",
    ...(options?.meta ? { meta: options.meta } : {}),
  });
}

async function insertTaskWithRecovery({
  supabaseAdmin,
  insertObject,
  idempotencyKey,
  finalProjectId,
  isServiceRole,
  logger,
}: InsertTaskWithRecoveryOptions): Promise<InsertTaskResult> {
  const payload = buildTaskInsertPayload(insertObject, idempotencyKey);

  const { data: insertedTask, error } = await supabaseAdmin
    .from("tasks")
    .insert(payload)
    .select("id")
    .single();

  if (error) {
    if (
      error.code === "23505" &&
      idempotencyKey &&
      error.message?.includes("idempotency_key")
    ) {
      logger.info("Idempotent duplicate detected, returning existing task", {
        idempotency_key: idempotencyKey,
      });

      const { data: existingTask, error: fetchError } = await supabaseAdmin
        .from("tasks")
        .select("id, status, project_id")
        .eq("idempotency_key", idempotencyKey)
        .single();

      if (fetchError || typeof existingTask?.id !== "string") {
        logger.error("Failed to fetch existing task for idempotency key", {
          idempotency_key: idempotencyKey,
          error: fetchError?.message,
        });
        await logger.flush();
        return {
          ok: false,
          response: createErrorResponse(
            "Duplicate task detected but could not retrieve it",
            500,
            "duplicate_task_lookup_failed",
          ),
        };
      }

      if (
        !isServiceRole &&
        !isAuthorizedIdempotentRecoveryProject(existingTask.project_id, finalProjectId)
      ) {
        logger.error("Idempotent duplicate belongs to a different project", {
          idempotency_key: idempotencyKey,
          requested_project_id: finalProjectId,
          existing_project_id: existingTask.project_id,
        });
        await logger.flush();
        return {
          ok: false,
          response: createErrorResponse(
            "Forbidden: duplicate task belongs to a different project",
            403,
            "project_forbidden",
            false,
          ),
        };
      }

      return {
        ok: true,
        taskId: existingTask.id,
        deduplicated: true,
      };
    }

    logger.error("Task creation failed", { error: error.message, code: error.code });
    await logger.flush();
    return {
      ok: false,
      response: createErrorResponse(error.message, 500, "task_insert_failed"),
    };
  }

  if (!insertedTask || typeof insertedTask.id !== "string") {
    logger.error("Task creation returned invalid payload", { insertedTask });
    await logger.flush();
    return {
      ok: false,
      response: createErrorResponse("Task creation failed", 500, "invalid_task_insert_payload"),
    };
  }

  return {
    ok: true,
    taskId: insertedTask.id,
    deduplicated: false,
  };
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return jsonResponse({ ok: true });
  }

  const bootstrap = await bootstrapEdgeHandler(req, {
    functionName: "create-task",
    logPrefix: "[CREATE-TASK]",
    method: "POST",
    parseBody: "strict",
    corsPreflight: false,
    auth: JWT_AUTH_REQUIRED,
    ...NO_SESSION_RUNTIME_OPTIONS,
  });
  if (!bootstrap.ok) {
    return bootstrap.response;
  }

  const { supabaseAdmin, logger, auth, body: rawBody } = bootstrap.value;
  const requestIdempotencyKey = parseRequestIdempotencyKey(rawBody);

  const parsedResolverRequest = parseResolverRequest(rawBody);
  if (!parsedResolverRequest) {
    logger.error("Missing family field in request body");
    await logger.flush();
    return createErrorResponse("family field is required", 400, "invalid_request_body", false);
  }

  if (!parsedResolverRequest.ok) {
    logger.error("Invalid resolver request body", { error: parsedResolverRequest.error });
    await logger.flush();
    return createErrorResponse(parsedResolverRequest.error, 400, "invalid_request_body", false);
  }

  const resolverRequest = parsedResolverRequest.value;

  logger.info("Creating task", {
    task_family: resolverRequest.family,
    project_id: resolverRequest.project_id,
  });

  const isServiceRole = auth?.isServiceRole === true;
  const callerId = auth?.userId ?? null;

  if (isServiceRole) {
    logger.debug("Authenticated via service-role key");
  } else if (auth?.isJwtAuth) {
    logger.debug("Authenticated via JWT", { user_id: callerId });
  } else {
    logger.debug("Authenticated via PAT", { user_id: callerId });
  }

  if (!isServiceRole && callerId) {
    const rateLimitDenied = await enforceRateLimit({
      supabaseAdmin,
      functionName: 'create-task',
      userId: callerId,
      config: RATE_LIMITS.taskCreation,
      logger,
      logPrefix: '[CREATE-TASK]',
      responses: {
        serviceUnavailable: () => createErrorResponse(
          "Rate limit service unavailable",
          503,
          "rate_limit_service_unavailable",
        ),
      },
    });
    if (rateLimitDenied) return rateLimitDenied;
  }

  let finalProjectId: string;
  let projectAspectRatio: string | null = null;
  const requestedProjectId = resolverRequest.project_id;

  if (isServiceRole) {
    finalProjectId = requestedProjectId;
  } else {
    if (!callerId) {
      logger.error("Could not determine user ID");
      await logger.flush();
      return createErrorResponse("Could not determine user ID", 401, "authentication_failed", false);
    }

    const { data: projectData, error: projectError } = await supabaseAdmin
      .from("projects")
      .select("user_id, aspect_ratio")
      .eq("id", requestedProjectId)
      .single();

    if (projectError) {
      logger.error("Project lookup error", { project_id: requestedProjectId, error: projectError.message });
      await logger.flush();
      return createErrorResponse("Project not found", 404, "project_not_found", false);
    }

    const ownerId = projectData?.user_id;
    if (typeof ownerId !== "string") {
      logger.error("Project missing owner", { project_id: requestedProjectId });
      await logger.flush();
      return createErrorResponse("Project not found", 404, "project_not_found", false);
    }

    if (ownerId !== callerId) {
      logger.error("User doesn't own project", {
        user_id: callerId,
        project_id: requestedProjectId,
        owner_id: ownerId,
      });
      await logger.flush();
      return createErrorResponse("Forbidden: You don't own this project", 403, "project_forbidden", false);
    }

    finalProjectId = requestedProjectId;
    projectAspectRatio = typeof projectData?.aspect_ratio === "string"
      ? projectData.aspect_ratio
      : null;
  }

  if (projectAspectRatio === null) {
    const { data: projectData, error: projectError } = await supabaseAdmin
      .from("projects")
      .select("aspect_ratio")
      .eq("id", finalProjectId)
      .single();

    if (projectError) {
      logger.error("Project aspect ratio lookup error", {
        project_id: finalProjectId,
        error: projectError.message,
      });
      await logger.flush();
      return createErrorResponse("Project not found", 404, "project_not_found", false);
    }

    projectAspectRatio = typeof projectData?.aspect_ratio === "string"
      ? projectData.aspect_ratio
      : null;
  }

  try {
    let resolver = getTaskFamilyResolver(resolverRequest.family);
    if (!resolver) {
      // No explicit resolver — check if this task type exists in the DB.
      // Worker-created child tasks (category: "processing") don't need
      // validation, just a passthrough insert.
      const { data: taskType } = await supabaseAdmin
        .from("task_types")
        .select("name")
        .eq("name", resolverRequest.family)
        .eq("is_active", true)
        .maybeSingle();

      if (!taskType) {
        logger.error("Unknown task family", { family: resolverRequest.family });
        await logger.flush();
        return createErrorResponse("Unknown task family", 400, "unknown_task_family", false);
      }

      resolver = createWorkerPassthroughResolver(resolverRequest.family);
    }

    const resolverResult = await resolver(resolverRequest, {
      supabaseAdmin,
      projectId: finalProjectId,
      aspectRatio: projectAspectRatio,
      logger,
    });

    if (!Array.isArray(resolverResult.tasks) || resolverResult.tasks.length === 0) {
      logger.error("Resolver returned no tasks", { family: resolverRequest.family });
      await logger.flush();
      return createErrorResponse("Resolver did not return any tasks", 500, "invalid_resolver_result");
    }

    const insertObjects = resolverResult.tasks;
    const responseMeta = resolverResult.meta;

    const createdTaskIds: string[] = [];
    let deduplicatedCount = 0;

    for (let taskIndex = 0; taskIndex < insertObjects.length; taskIndex++) {
      const insertObject = insertObjects[taskIndex];
      const idempotencyKey = await resolveInsertIdempotencyKey(
        insertObject,
        requestIdempotencyKey,
        taskIndex,
        insertObjects.length,
      );

      const insertResult = await insertTaskWithRecovery({
        supabaseAdmin,
        insertObject,
        idempotencyKey,
        finalProjectId,
        isServiceRole,
        logger,
      });

      if (!insertResult.ok) {
        return insertResult.response;
      }

      createdTaskIds.push(insertResult.taskId);
      if (insertResult.deduplicated) {
        deduplicatedCount += 1;
      }
    }

    if (createdTaskIds.length === 1) {
      logger.setDefaultTaskId(createdTaskIds[0]);
    }

    logger.info("Task created successfully", {
      task_id: createdTaskIds[0],
      task_ids: insertObjects.length > 1 ? createdTaskIds : undefined,
      task_count: createdTaskIds.length,
      task_family: resolverRequest.family,
      project_id: finalProjectId,
      created_by: isServiceRole ? "service-role" : callerId,
      has_idempotency_key: !!requestIdempotencyKey,
      deduplicated_count: deduplicatedCount,
    });

    await logger.flush();
    return buildCreateTaskResponse(createdTaskIds, {
      meta: responseMeta,
      deduplicated: createdTaskIds.length === 1 && deduplicatedCount === 1,
    });
  } catch (error: unknown) {
    if (error instanceof TaskValidationError) {
      logger.error("Validation error", { error: error.message, field: error.field });
      await logger.flush();
      return createErrorResponse(error.message, 400, "validation_error", false);
    }

    const message = getErrorMessage(error);
    logger.critical("Unexpected error", { error: message });
    await logger.flush();
    return createErrorResponse("Internal server error", 500, "internal_server_error");
  }
});
