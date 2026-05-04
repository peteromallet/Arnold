// deno-lint-ignore-file
import { jsonResponse } from "../_shared/http.ts";
import {
  enforceRateLimit,
  RATE_LIMITS,
} from "../_shared/rateLimit.ts";
import { bootstrapEdgeHandler, NO_SESSION_RUNTIME_OPTIONS } from "../_shared/edgeHandler.ts";
import { toErrorMessage } from "../_shared/errorMessage.ts";
import { resolveTaskStorageActor } from "../_shared/taskActorPolicy.ts";
import { ensureTaskActor } from "../_shared/requestGuards.ts";
import type { AssetRegistryEntry } from "../../../src/tools/video-editor/index.ts";
import {
  loadTimelineState,
  prepareTimelineConfigForPersistence,
  saveTimelineConfigVersioned,
} from "../ai-timeline-agent/db.ts";
import { addMediaClip } from "../ai-timeline-agent/tools/timeline.ts";
import type { SupabaseAdmin as TimelineSupabaseAdmin } from "../ai-timeline-agent/types.ts";

// Import from refactored modules
import { parseCompleteTaskRequest, validateStoragePathSecurity } from './request.ts';
import { handleStorageOperations, getStoragePublicUrl, cleanupFile } from './storage.ts';
import * as completeTaskParams from './params.ts';
import { createGenerationFromTask, type CompletionAssetRef } from './generation.ts';
import { executePlacement, extractPlacementIntent } from './placement.ts';
import { checkOrchestratorCompletion } from './orchestrator.ts';
import { validateAndCleanupShotId } from './shotValidation.ts';
import { triggerCostCalculationIfNotSubTask } from './billing.ts';
import { CompletionError } from './errors.ts';
import {
  completeTaskErrorResponse,
  fetchTaskContext,
  markTaskFailed,
  persistCompletionFollowUpIssues,
  type CompletionFollowUpIssue,
} from './completionHelpers.ts';

// Provide a loose Deno type for local tooling
declare const Deno: { env: { get: (key: string) => string | undefined } };

async function applyCompletedGenerationTimelinePlacement(
  supabaseAdmin: TimelineSupabaseAdmin,
  options: {
    taskId: string;
    params: Record<string, unknown>;
    contentType: "image" | "video";
    generationId: string;
    publicUrl: string;
    thumbnailUrl: string | null;
    filename: string;
    logger: {
      info: (message: string, metadata?: Record<string, unknown>) => void;
    };
  },
): Promise<void> {
  const placement = completeTaskParams.extractTimelinePlacement?.(options.params) ?? null;
  if (!placement) {
    return;
  }

  const timelineState = await loadTimelineState(supabaseAdmin, placement.timeline_id);
  const assetKey = `asset-${crypto.randomUUID().slice(0, 6)}`;
  const assetEntry: AssetRegistryEntry = {
    file: options.publicUrl,
    type: completeTaskParams.getContentType(options.filename),
    generationId: options.generationId,
    ...(options.thumbnailUrl && options.thumbnailUrl !== options.publicUrl
      ? { thumbnailUrl: options.thumbnailUrl }
      : {}),
  };

  const { error: assetRegistryError } = await supabaseAdmin
    .rpc("upsert_asset_registry_entry", {
      p_timeline_id: placement.timeline_id,
      p_asset_id: assetKey,
      p_entry: assetEntry,
    })
    .maybeSingle();

  if (assetRegistryError) {
    throw new Error(`Failed to register timeline asset: ${assetRegistryError.message}`);
  }

  const nextRegistry = {
    ...timelineState.registry,
    assets: {
      ...timelineState.registry.assets,
      [assetKey]: assetEntry,
    },
  };
  const insertionResult = addMediaClip(timelineState.config, nextRegistry, {
    track: placement.target_track,
    at: placement.insertion_time,
    assetKey,
    mediaType: options.contentType,
  });

  if (!insertionResult.config) {
    throw new Error(insertionResult.result);
  }

  const configToSave = prepareTimelineConfigForPersistence(insertionResult.config, nextRegistry);

  const nextVersion = await saveTimelineConfigVersioned(
    supabaseAdmin,
    placement.timeline_id,
    timelineState.configVersion,
    configToSave,
  );
  if (nextVersion === null) {
    throw new Error(`Failed to save timeline ${placement.timeline_id}: version conflict.`);
  }

  options.logger.info("Applied completion-time timeline placement", {
    task_id: options.taskId,
    generation_id: options.generationId,
    timeline_id: placement.timeline_id,
    source_clip_id: placement.source_clip_id,
    target_track: placement.target_track,
    insertion_time: placement.insertion_time,
    intent: placement.intent,
    asset_key: assetKey,
    config_version: nextVersion,
  });
}

export async function completeTaskHandler(req: Request): Promise<Response> {
  const bootstrap = await bootstrapEdgeHandler(req, {
    functionName: "complete-task",
    logPrefix: "[COMPLETE-TASK]",
    parseBody: "none",
    auth: {
      required: true,
      options: { allowJwtUserAuth: true },
    },
    ...NO_SESSION_RUNTIME_OPTIONS,
  });
  if (!bootstrap.ok) {
    return bootstrap.response;
  }

  const { supabaseAdmin, logger, auth } = bootstrap.value;
  const authResult = ensureTaskActor(auth, logger);
  if (!authResult.ok) {
    await logger.flush();
    return completeTaskErrorResponse("Authentication failed", 401);
  }

  // 1) Parse and validate request
  const parseResult = await parseCompleteTaskRequest(req);
  if (!parseResult.success) {
    return parseResult.response;
  }
  const parsedRequest = parseResult.data;
  const taskIdString = parsedRequest.taskId;

  logger.setDefaultTaskId?.(taskIdString);
  logger.info("Processing task", {
    task_id: taskIdString,
    mode: parsedRequest.mode,
    filename: parsedRequest.filename,
  });

  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";

  // 3) Security check: Validate storage path for orchestrator references
  if (parsedRequest.requiresOrchestratorCheck && parsedRequest.storagePath) {
    const securityResult = await validateStoragePathSecurity(
      supabaseAdmin,
      taskIdString,
      parsedRequest.storagePath,
      parsedRequest.storagePathTaskId
    );
    if (!securityResult.allowed) {
      logger.error("Storage path security check failed", { error: securityResult.error });
      await logger.flush();
      return completeTaskErrorResponse(
        securityResult.error || "Access denied",
        403,
        'storage_path_access_denied',
      );
    }
  }

  // 4) Authentication is handled by bootstrapEdgeHandler.
  const isServiceRole = auth!.isServiceRole;
  const callerId = auth!.userId;

  // 4b) Rate limit non-service-role callers (workers use service-role and are not rate limited)
  if (!isServiceRole && callerId) {
    const rateLimitDenied = await enforceRateLimit({
      supabaseAdmin,
      functionName: 'complete-task',
      userId: callerId,
      config: RATE_LIMITS.userAction,
      logger,
      logPrefix: '[COMPLETE-TASK]',
      responses: {
        serviceUnavailable: () => completeTaskErrorResponse("Rate limit service unavailable", 503, 'rate_limit_service_unavailable'),
      },
    });
    if (rateLimitDenied) return rateLimitDenied;
  }

  try {
    const completionFollowUpIssues: CompletionFollowUpIssue[] = [];

    // 5) Resolve actor policy once (ownership + task user resolution).
    const taskActor = await resolveTaskStorageActor({
      supabaseAdmin,
      taskId: taskIdString,
      auth: auth!,
      logPrefix: "[COMPLETE-TASK]",
    });
    if (!taskActor.ok) {
      logger.error("Task actor resolution failed", {
        task_id: taskIdString,
        error: taskActor.error,
        status_code: taskActor.statusCode,
      });
      await logger.flush();
      return completeTaskErrorResponse(
        taskActor.error,
        taskActor.statusCode,
        'task_actor_resolution_failed',
      );
    }

    const completionAuthContext = {
      isServiceRole: taskActor.value.isServiceRole,
      taskOwnerVerified: taskActor.value.taskOwnerVerified,
      actorId: taskActor.value.callerId,
    };

    // 6) MODE 4: Verify referenced file exists
    if (parsedRequest.storagePath) {
      const pathParts = parsedRequest.storagePath.split('/');
      const isMode3Format = pathParts.length >= 4 && pathParts[1] === 'tasks';

      if (!isMode3Format) {
        const fileCheck = await getStoragePublicUrl(supabaseAdmin, parsedRequest.storagePath);
        if (!fileCheck.exists) {
          return completeTaskErrorResponse(
            "Referenced file does not exist or is not accessible in storage",
            404,
            'storage_reference_not_found',
          );
        }
      }
    }

    // 7) Determine user ID for storage path from shared actor policy.
    const userId = taskActor.value.taskUserId;

    // 8) Fetch task context once (used by validation, generation creation, orchestrator check)
    const taskContext = await fetchTaskContext(supabaseAdmin, taskIdString, logger);
    if (!taskContext) {
      logger.error("Failed to fetch task context", { task_id: taskIdString });
      await logger.flush();
      return completeTaskErrorResponse("Task not found", 404, 'task_not_found');
    }

    // 9) Handle storage operations
    const storageResult = await handleStorageOperations(supabaseAdmin, parsedRequest, userId, isServiceRole);
    const { publicUrl, objectPath, thumbnailUrl } = storageResult;

    // 10) Validate shot references and update params if needed
    try {
      let updatedParams = { ...taskContext.params };
      let needsParamsUpdate = false;

      // Validate and cleanup invalid shot_id references
      const shotValidation = await validateAndCleanupShotId(supabaseAdmin, updatedParams, taskContext.tool_type);
      if (shotValidation.needsUpdate) {
        needsParamsUpdate = true;
        updatedParams = shotValidation.updatedParams;
      }

      // Add thumbnail URL if available
      if (thumbnailUrl) {
        needsParamsUpdate = true;
        updatedParams = completeTaskParams.setThumbnailInParams(updatedParams, taskContext.task_type, thumbnailUrl);
      }

      if (needsParamsUpdate) {
        await supabaseAdmin.from("tasks").update({ params: updatedParams }).eq("id", taskIdString);
        
        // Keep in-memory context in sync so downstream steps (generation creation) use updated params
        taskContext.params = updatedParams;
      }
    } catch (validationError) {
      logger.warn("Validation follow-up failed; continuing completion flow", {
        task_id: taskIdString,
        error: toErrorMessage(validationError),
      });
      completionFollowUpIssues.push({
        step: 'validation',
        code: 'validation_follow_up_failed',
        message: toErrorMessage(validationError),
      });
      // Continue anyway - don't fail task completion due to validation errors
    }

    // 11) Create generation (if applicable)
    const CREATE_GENERATION_IN_EDGE = Deno.env.get("CREATE_GENERATION_IN_EDGE") !== "false";
    let createdGenerationId: string | null = null;
    let completionAssetRef: CompletionAssetRef | null = null;
    if (CREATE_GENERATION_IN_EDGE) {
      try {
        const generationOutcome = await createGenerationFromTask(
          supabaseAdmin,
          taskContext.id,
          {
            id: taskContext.id,
            task_type: taskContext.task_type,
            project_id: taskContext.project_id,
            params: taskContext.params,
            tool_type: taskContext.tool_type,
            content_type: taskContext.content_type,
            variant_type: taskContext.variant_type,
            category: taskContext.category,
          },
          publicUrl,
          thumbnailUrl,
          logger,
          completionAuthContext,
        );

        if (generationOutcome.status === 'skipped') {
          logger.info('Generation creation skipped', {
            task_id: taskContext.id,
            reason: generationOutcome.reason,
          });
        } else {
          completionAssetRef = generationOutcome.completionAsset;
          const generationId = typeof generationOutcome.generation?.id === 'string'
            && generationOutcome.generation.id.length > 0
            ? generationOutcome.generation.id
            : null;
          createdGenerationId = generationId;
          const placementIntent = extractPlacementIntent(taskContext.params);

          if (placementIntent) {
            if (!completionAssetRef) {
              logger.warn('Placement intent was present but no completion asset ref was available', {
                task_id: taskContext.id,
                generation_id: generationId,
                placement_intent: placementIntent,
              });
              completionFollowUpIssues.push({
                step: 'timeline_placement',
                code: 'placement_completion_asset_missing',
                message: 'Placement intent could not be applied because the completed asset reference was unavailable.',
              });
            } else {
              try {
                const placementResult = await executePlacement(
                  supabaseAdmin as unknown as TimelineSupabaseAdmin,
                  placementIntent,
                  completionAssetRef,
                );

                if (placementResult.status === 'placed') {
                  logger.info('Applied completion-time placement intent', {
                    task_id: taskContext.id,
                    generation_id: generationId,
                    timeline_id: placementResult.timelineId,
                    asset_key: placementResult.assetKey,
                    clip_id: placementResult.clipId,
                    used_fallback: placementResult.usedFallback,
                    config_version: placementResult.configVersion,
                  });
                } else {
                  logger.warn('Timeline placement intent degraded', {
                    task_id: taskContext.id,
                    generation_id: generationId,
                    placement_intent: placementIntent,
                    issue: placementResult.issue,
                  });
                  completionFollowUpIssues.push(placementResult.issue);
                }
              } catch (timelinePlacementError) {
                const message = toErrorMessage(timelinePlacementError);
                logger.error("Timeline placement follow-up failed", {
                  task_id: taskContext.id,
                  generation_id: generationId,
                  error: message,
                  placement_intent: placementIntent,
                });
                completionFollowUpIssues.push({
                  step: 'timeline_placement',
                  code: 'timeline_placement_failed',
                  message,
                });
              }
            }
          } else if (!generationId) {
            logger.warn('Generation creation returned no generation id; skipping timeline placement', {
              task_id: taskContext.id,
            });
          } else {
            try {
              await applyCompletedGenerationTimelinePlacement(
                supabaseAdmin as unknown as TimelineSupabaseAdmin,
                {
                  taskId: taskContext.id,
                  params: taskContext.params,
                  contentType: taskContext.content_type,
                  generationId,
                  publicUrl,
                  thumbnailUrl: thumbnailUrl ?? null,
                  filename: parsedRequest.filename,
                  logger,
                },
              );
            } catch (timelinePlacementError) {
              const message = toErrorMessage(timelinePlacementError);
              logger.error("Timeline placement follow-up failed", {
                task_id: taskContext.id,
                generation_id: generationId,
                error: message,
                timeline_placement: completeTaskParams.extractTimelinePlacement?.(taskContext.params) ?? null,
              });
              completionFollowUpIssues.push({
                step: 'timeline_placement',
                code: 'timeline_placement_failed',
                message,
              });
            }
          }
        }
        void completionAssetRef;
      } catch (genErr: unknown) {
        const normalizedError = genErr instanceof CompletionError ? genErr : null;
        const msg = toErrorMessage(genErr);
        logger.error("Generation creation failed", {
          error: msg,
          error_code: normalizedError?.code ?? 'generation_completion_failed',
          recoverable: normalizedError?.recoverable ?? true,
          error_context: normalizedError?.context,
          error_metadata: normalizedError?.metadata,
        });
        await markTaskFailed(
          supabaseAdmin,
          taskIdString,
          normalizedError
            ? `Generation creation failed [${normalizedError.code}]: ${normalizedError.message}`
            : `Generation creation failed: ${msg}`,
        );
        await logger.flush();
        return completeTaskErrorResponse(
          normalizedError?.message ?? "Internal server error",
          500,
          normalizedError?.code ?? 'internal_server_error',
          normalizedError ? { recoverable: normalizedError.recoverable } : undefined,
        );
      }
    }

    // 12) Update task to Complete
    // Use output_location override if provided (e.g., JSON metadata from transition_only mode),
    // otherwise fall back to the storage public URL
    const finalOutputLocation = parsedRequest.outputLocationOverride || publicUrl;
    const { error: dbError } = await supabaseAdmin.from("tasks").update({
      status: "Complete",
      output_location: finalOutputLocation,
      generation_processed_at: new Date().toISOString()
    }).eq("id", taskIdString).eq("status", "In Progress");

    if (dbError) {
      const dbMsg = toErrorMessage(dbError);
      logger.error("Database update failed", {
        task_id: taskIdString,
        error: dbMsg,
      });
      await markTaskFailed(supabaseAdmin, taskIdString, `Task completion DB update failed: ${dbMsg}`);
      await logger.flush();
      await cleanupFile(supabaseAdmin, objectPath);
      return completeTaskErrorResponse("Internal server error", 500);
    }

    // 13) Check orchestrator completion (for segment tasks) - uses task context
    try {
      await checkOrchestratorCompletion(
        {
          supabase: supabaseAdmin,
          taskIdString,
          completedTask: taskContext, // Pass context instead of fetching again
          publicUrl,
          supabaseUrl,
          serviceKey,
          authContext: completionAuthContext,
          logger,
        },
      );
    } catch (orchErr) {
      logger.warn("Orchestrator completion follow-up failed", {
        task_id: taskIdString,
        error: toErrorMessage(orchErr),
      });
      completionFollowUpIssues.push({
        step: 'orchestrator_completion',
        code: 'orchestrator_follow_up_failed',
        message: toErrorMessage(orchErr),
      });
    }

    // 14) Calculate cost (service role only)
    if (isServiceRole) {
      const billingResult = await triggerCostCalculationIfNotSubTask(
        supabaseAdmin,
        supabaseUrl,
        serviceKey,
        taskIdString,
      );
      if (!billingResult.ok) {
        logger.warn("Cost calculation follow-up failed", {
          task_id: taskIdString,
          billing_result: billingResult,
        });
        completionFollowUpIssues.push({
          step: 'cost_calculation',
          code: billingResult.errorCode || 'cost_calculation_follow_up_failed',
          message: billingResult.message || 'Cost calculation follow-up failed',
        });
      }
    }

    if (completionFollowUpIssues.length > 0) {
      const persistenceResult = await persistCompletionFollowUpIssues(
        supabaseAdmin,
        taskIdString,
        taskContext.result_data,
        completionFollowUpIssues,
      );
      if (!persistenceResult.ok) {
        logger.error("Failed to persist completion follow-up issues", {
          task_id: taskIdString,
          error: persistenceResult.error instanceof Error
            ? persistenceResult.error.message
            : String(persistenceResult.error),
        });
        completionFollowUpIssues.push({
          step: 'follow_up_persistence',
          code: 'completion_follow_up_persistence_failed',
          message: persistenceResult.error instanceof Error
            ? persistenceResult.error.message
            : String(persistenceResult.error),
        });
      }
    }

    // 15) Return success
    const responseData = {
      success: true,
      public_url: publicUrl,
      thumbnail_url: thumbnailUrl,
      follow_up: completionFollowUpIssues.length === 0
        ? { status: 'ok' as const, issues: [] as CompletionFollowUpIssue[] }
        : { status: 'degraded' as const, issues: completionFollowUpIssues },
      message: completionFollowUpIssues.length === 0
        ? "Task completed and file uploaded successfully"
        : "Task completed with follow-up warnings",
    };

    logger.info("Task completed successfully", { 
      task_id: taskIdString,
      output_location: publicUrl,
      generation_id: createdGenerationId,
      has_thumbnail: !!thumbnailUrl,
      follow_up_issue_count: completionFollowUpIssues.length,
    });
    await logger.flush();

    return jsonResponse(responseData, 200);

  } catch (error: unknown) {
    const errMsg = toErrorMessage(error);
    logger.critical("Unexpected error", {
      task_id: taskIdString,
      error: errMsg,
      stack: error instanceof Error ? error.stack?.substring(0, 500) : undefined
    });
    await markTaskFailed(supabaseAdmin, taskIdString, `Task completion failed: ${errMsg}`);
    await logger.flush();
    return completeTaskErrorResponse("Internal server error", 500);
  }
}
