/**
 * Task completion generation handlers keyed by routing inputs from createGenerationFromTask.
 */

import type { SupabaseClient } from 'https://esm.sh/@supabase/supabase-js@2.49.4';
import type { CompletionAssetRef } from './generation.ts';
import { VARIANT_TYPE_DEFAULT } from './constants.ts';

import {
  extractShotAndPosition,
  buildGenerationParams,
  resolveBasedOn,
} from './params.ts';

import {
  insertGeneration,
  createVariant,
  derivePredecessorVariantId,
  linkGenerationToShot,
} from './generation-core.ts';

import {
  getOrCreateParentGeneration,
  createVariantOnParent,
  getChildVariantViewedAt,
} from './generation-parent.ts';
import { CompletionError, toCompletionError } from './errors.ts';

const VIDEO_EXTENSIONS = /\.(mp4|webm|mov)(\?|$)/i;

/** Resolve media type from explicit content_type, falling back to URL extension. */
function resolveMediaType(contentType: string | undefined, url?: string): string {
  if (contentType) return contentType;
  if (url && VIDEO_EXTENSIONS.test(url)) return 'video';
  return 'image';
}

// Re-export child generation handlers and shared types for backward compatibility
export {
  type HandlerContext,
  handleChildGeneration,
  createSingleItemVariant,
  findExistingGenerationAtPosition,
  createChildGenerationRecord,
} from './generation-child.ts';

// ===== HANDLER: VARIANT ON SOURCE =====

/**
 * Create variant on source generation (for edit/upscale tasks with based_on)
 * Reads is_primary and variant_type from task data
 */
export async function handleVariantCreation(
  supabase: SupabaseClient,
  taskId: string,
  taskData: unknown,
  basedOnGenerationId: string,
  publicUrl: string,
  thumbnailUrl: string | null
): Promise<CompletionAssetRef> {
  const isPrimary = taskData.params?.is_primary === true;
  const variantType = taskData.variant_type || VARIANT_TYPE_DEFAULT;

  try {
    const { data: sourceGen, error: fetchError } = await supabase
      .from('generations')
      .select('id, params, thumbnail_url, project_id')
      .eq('id', basedOnGenerationId)
      .single();

    if (fetchError || !sourceGen) {
      throw new CompletionError({
        code: 'variant_source_generation_not_found',
        context: 'handleVariantCreation',
        recoverable: false,
        message: `Source generation ${basedOnGenerationId} was not available for task ${taskId}`,
        metadata: {
          task_id: taskId,
          source_generation_id: basedOnGenerationId,
        },
        cause: fetchError,
      });
    }

    const variantParams = {
      ...taskData.params,
      source_task_id: taskId,
      source_variant_id: taskData.params?.source_variant_id || null,
      created_from: taskData.task_type,
      tool_type: taskData.tool_type,
      content_type: taskData.content_type,
    };

    const variant = await createVariant(
      supabase,
      basedOnGenerationId,
      publicUrl,
      thumbnailUrl,
      variantParams,
      isPrimary,
      variantType,
      null
    );

    const { error: markError } = await supabase
      .from('tasks')
      .update({ generation_created: true })
      .eq('id', taskId);
    if (markError) {
      throw new CompletionError({
        code: 'variant_generation_created_update_failed',
        context: 'handleVariantCreation',
        recoverable: true,
        message: `Failed to persist generation_created marker for task ${taskId}`,
        metadata: {
          task_id: taskId,
          source_generation_id: basedOnGenerationId,
        },
        cause: markError,
      });
    }
    return {
      generation_id: basedOnGenerationId,
      variant_id: variant.id,
      location: publicUrl,
      ...(thumbnailUrl ? { thumbnail_url: thumbnailUrl } : {}),
      media_type: resolveMediaType(taskData.content_type, publicUrl),
      created_as: 'variant',
    };
  } catch (variantErr) {
    throw toCompletionError(variantErr, {
      code: 'variant_creation_failed',
      context: 'handleVariantCreation',
      recoverable: true,
      message: `Failed to create variant for task ${taskId}`,
      metadata: {
        task_id: taskId,
        source_generation_id: basedOnGenerationId,
      },
    });
  }
}

// ===== HANDLER: VARIANT ON PARENT =====

/**
 * Creates a variant on the parent generation (for stitch tasks)
 * Used by: travel_stitch, join_final_stitch
 */
export async function handleVariantOnParent(ctx: HandlerContext): Promise<unknown | null> {
  const { supabase, taskId, taskData, publicUrl, thumbnailUrl, logger } = ctx;
  const orchestrationContract = (
    taskData.params?.orchestration_contract && typeof taskData.params.orchestration_contract === 'object'
      ? taskData.params.orchestration_contract
      : {}
  ) as Record<string, unknown>;

  const orchTaskId = orchestrationContract.orchestrator_task_id ||
                     taskData.params?.orchestrator_task_id_ref ||
                     taskData.params?.orchestrator_task_id ||
                     taskData.params?.full_orchestrator_payload?.orchestrator_task_id;

  const directParentGenerationId = typeof taskData.params?.parent_generation_id === 'string'
    ? taskData.params.parent_generation_id
    : null;

  const parentGen = orchTaskId
    ? await getOrCreateParentGeneration(supabase, orchTaskId, taskData.project_id, taskData.params)
    : directParentGenerationId
      ? { id: directParentGenerationId }
      : null;

  if (!parentGen?.id) {
    throw new CompletionError({
      code: 'parent_generation_resolution_failed',
      context: 'handleVariantOnParent',
      recoverable: false,
      message: `No parent generation could be resolved for task ${taskId}`,
      metadata: {
        task_id: taskId,
        ...(orchTaskId ? { orchestrator_task_id: String(orchTaskId) } : {}),
        ...(directParentGenerationId ? { parent_generation_id: directParentGenerationId } : {}),
      },
    });
  }

  logger?.info(`${taskData.task_type}: creating variant on parent`, {
    task_id: taskId,
    parent_generation_id: parentGen.id,
    orchestrator_task_id: orchTaskId ?? null,
    action: "create_variant_on_parent"
  });

  const variantType = taskData.variant_type || VARIANT_TYPE_DEFAULT;

  const result = await createVariantOnParent(
    supabase,
    parentGen.id,
    publicUrl,
    thumbnailUrl,
    taskData,
    taskId,
    variantType,
    {
      tool_type: taskData.tool_type,
      created_from: `${taskData.task_type}_completion`,
    }
  );

  // For loop tasks with based_on (e.g., "Add to Join" loop), also create variant on source generation
  const orchDetails = taskData.params?.orchestrator_details || taskData.params?.full_orchestrator_payload || {};
  const isLoop = orchDetails.loop_first_clip === true;
  const basedOnId = orchDetails.based_on || orchestrationContract.based_on || taskData.params?.based_on;

  if (isLoop && basedOnId) {
    logger?.info(`${taskData.task_type}: creating loop variant on source`, {
      task_id: taskId,
      based_on: basedOnId,
      action: "create_loop_variant_on_source"
    });

    // Verify the source generation exists before creating variant
    const { data: sourceGen, error: sourceError } = await supabase
      .from('generations')
      .select('id')
      .eq('id', basedOnId)
      .maybeSingle();

    if (sourceGen && !sourceError) {
      await createVariant(
        supabase,
        basedOnId,
        publicUrl,
        thumbnailUrl,
        {
          ...taskData.params,
          source_task_id: taskId,
          tool_type: taskData.tool_type,
          created_from: 'loop_variant',
        },
        true, // is_primary - make this the new primary variant
        'clip_join', // variant_type
        null
      );
    } else if (sourceError) {
      throw new CompletionError({
        code: 'loop_variant_source_lookup_failed',
        context: 'handleVariantOnParent',
        recoverable: true,
        message: `Failed to resolve loop source generation ${String(basedOnId)} for task ${taskId}`,
        metadata: {
          task_id: taskId,
          source_generation_id: String(basedOnId),
        },
        cause: sourceError,
      });
    }
  }

  return result;
}

// ===== HANDLER: VARIANT ON CHILD =====

/**
 * Creates a variant on an existing child generation (for individual segment regeneration)
 * Used by: individual_travel_segment (when child_generation_id is present)
 */
export async function handleVariantOnChild(ctx: HandlerContext): Promise<unknown | null> {
  const { supabase, taskId, taskData, publicUrl, thumbnailUrl, logger, childGenerationId } = ctx;

  if (!childGenerationId) {
    return null; // Fall back to child_generation behavior
  }

  const childGenId = childGenerationId;

  logger?.info("individual_travel_segment with child_generation_id", {
    task_id: taskId,
    child_generation_id: childGenId,
    action: "create_variant_on_existing_child"
  });

  const { data: childGen, error: fetchError } = await supabase
    .from('generations')
    .select('*')
    .eq('id', childGenId)
    .single();

  if (fetchError || !childGen) {
    throw new CompletionError({
      code: 'child_generation_lookup_failed',
      context: 'handleVariantOnChild',
      recoverable: false,
      message: `Child generation ${childGenId} was not available for task ${taskId}`,
      metadata: {
        task_id: taskId,
        child_generation_id: childGenId,
      },
      cause: fetchError,
    });
  }

  // Extract pair_shot_generation_id from nested locations if not at top level
  const pairShotGenerationId = taskData.params?.pair_shot_generation_id ||
                                taskData.params?.individual_segment_params?.pair_shot_generation_id;

  const variantParams = {
    ...taskData.params,
    tool_type: taskData.tool_type,
    source_task_id: taskId,
    created_from: 'individual_segment_regeneration',
    ...(pairShotGenerationId && { pair_shot_generation_id: pairShotGenerationId }),
  };
  const predecessorVariantId = await derivePredecessorVariantId(
    supabase,
    variantParams,
    childGen.parent_generation_id,
    typeof childGen.child_order === 'number' ? childGen.child_order : null,
  );
  if (predecessorVariantId) {
    variantParams.continuation_predecessor_variant_id = predecessorVariantId;
  }

  // Respect make_primary_variant flag from UI (defaults to true for backward compatibility)
  const makePrimary = taskData.params?.make_primary_variant ?? true;

  // Always check for single-segment case (independent of makePrimary flag)
  // This determines if we should propagate to the parent generation
  const singleSegmentViewedAt = await getChildVariantViewedAt(supabase, {
    taskParams: taskData.params,
    childGeneration: childGen,
  });
  // For the child variant, only auto-view if makePrimary is true
  const childViewedAt = makePrimary ? singleSegmentViewedAt : null;

  const variantType = taskData.variant_type || VARIANT_TYPE_DEFAULT;

  await createVariant(
    supabase,
    childGen.id,
    publicUrl,
    thumbnailUrl,
    variantParams,
    makePrimary,
    variantType,
    null,
    childViewedAt
  );

  await supabase.from('tasks').update({ generation_created: true }).eq('id', taskId);
  return childGen;
}

// ===== HANDLER: STANDALONE GENERATION =====

/**
 * Creates an independent generation (for regular tasks)
 * Used by: single_image, wan_2_2_i2v, image_inpaint, etc.
 */
export async function handleStandaloneGeneration(ctx: HandlerContext): Promise<unknown> {
  const { supabase, taskId, taskData, publicUrl, thumbnailUrl, logger } = ctx;

  const { shotId, addInPosition } = extractShotAndPosition(taskData.params);

  // Validate shot exists
  if (shotId) {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (uuidRegex.test(shotId)) {
      await supabase.from('shots').select('id').eq('id', shotId).single();
    }
  }

  const generationType = resolveMediaType(taskData.content_type, publicUrl);
  const generationParams = buildGenerationParams(
    taskData.params, taskData.tool_type, generationType, shotId, thumbnailUrl || undefined, taskId
  );
  const newGenerationId = crypto.randomUUID();

  const generationName = taskData.params?.generation_name ||
    taskData.params?.orchestrator_details?.generation_name ||
    taskData.params?.full_orchestrator_payload?.generation_name;

  // Find based_on
  const basedOnGenerationId = await resolveBasedOn(supabase, taskData.params);

  logger?.info("Creating standalone generation", {
    task_id: taskId,
    generation_id: newGenerationId,
    based_on: basedOnGenerationId,
    shot_id: shotId,
    generation_type: generationType,
  });

  const generationRecord: Record<string, unknown> = {
    id: newGenerationId,
    tasks: [taskId],
    params: generationParams,
    type: generationType,
    project_id: taskData.project_id,
    name: generationName,
    based_on: basedOnGenerationId,
    parent_generation_id: null,
    is_child: false,
    child_order: null,
    created_at: new Date().toISOString()
  };

  const newGeneration = await insertGeneration(supabase, generationRecord);

  // Create "original" variant
  const originalVariant = await createVariant(
    supabase, newGeneration.id, publicUrl, thumbnailUrl,
    { ...generationParams, source_task_id: taskId, created_from: 'generation_original' },
    true, 'original', null, null
  );

  // Link to shot if applicable
  if (shotId) {
    await linkGenerationToShot(supabase, shotId, newGeneration.id, addInPosition);
  }

  await supabase.from('tasks').update({ generation_created: true }).eq('id', taskId);

  return {
    ...newGeneration,
    completionAsset: {
      generation_id: newGeneration.id,
      variant_id: originalVariant.id,
      location: publicUrl,
      ...(thumbnailUrl ? { thumbnail_url: thumbnailUrl } : {}),
      media_type: generationType,
      created_as: 'generation' as const,
    },
  };
}
