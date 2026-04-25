import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { isNotFoundError } from '@/shared/constants/supabaseErrors';
import { ensureUniqueFrame } from '@/shared/lib/timelinePositionCalculator';
import { isQuotaOrServerError } from './shotMutationHelpers';

export interface AddImageToShotVariables {
  shot_id: string;
  generation_id: string;
  project_id: string;
  imageUrl?: string;
  thumbUrl?: string;
  timelineFrame?: number | null;
  abortSignal?: AbortSignal;
  onMaterializeProgress?: (progress: number) => void;
}

export const withVariableMetadata = (data: Record<string, unknown>, variables: AddImageToShotVariables) => ({
  ...data,
  project_id: variables.project_id,
  imageUrl: variables.imageUrl,
  thumbUrl: variables.thumbUrl,
});

async function insertUnpositionedShotGeneration(
  shotId: string,
  generationId: string,
): Promise<Record<string, unknown>> {
  const { data, error } = await supabase().from('shot_generations')
    .insert({
      shot_id: shotId,
      generation_id: generationId,
      timeline_frame: null,
    })
    .select()
    .single();

  if (error) {
    throw error;
  }

  return data as Record<string, unknown>;
}

export async function insertAutoPositionedShotGeneration(
  shotId: string,
  generationId: string,
): Promise<Record<string, unknown>> {
  const { data: rpcResult, error: rpcError } = await supabase().rpc('add_generation_to_shot', {
    p_shot_id: shotId,
    p_generation_id: generationId,
    p_with_position: true,
  });

  if (rpcError) {
    throw rpcError;
  }

  const result = Array.isArray(rpcResult) ? rpcResult[0] : rpcResult;
  return (result || {}) as Record<string, unknown>;
}

async function fetchResolvedTimelineFrame(shotId: string, requestedFrame: number): Promise<number> {
  const { data: existingGens, error: fetchError } = await supabase().from('shot_generations')
    .select('timeline_frame')
    .eq('shot_id', shotId)
    .not('timeline_frame', 'is', null);

  if (fetchError && !isNotFoundError(fetchError)) {
    // Non-critical fetch failure: fall through with empty frame list.
  }

  const existingFrames = (existingGens || [])
    .map((generation) => generation.timeline_frame)
    .filter((frame): frame is number => frame != null && frame !== -1);

  return ensureUniqueFrame(requestedFrame, existingFrames);
}

async function insertExplicitlyPositionedShotGeneration(
  shotId: string,
  generationId: string,
  timelineFrame: number,
): Promise<Record<string, unknown>> {
  const resolvedFrame = await fetchResolvedTimelineFrame(shotId, timelineFrame);
  const { data, error } = await supabase().from('shot_generations')
    .insert({
      shot_id: shotId,
      generation_id: generationId,
      timeline_frame: resolvedFrame,
    })
    .select()
    .single();

  if (error) {
    throw error;
  }

  return data as Record<string, unknown>;
}

export function runAddImageMutation(variables: AddImageToShotVariables): Promise<Record<string, unknown>> {
  const { shot_id, generation_id, timelineFrame } = variables;

  if (timelineFrame === null) {
    return insertUnpositionedShotGeneration(shot_id, generation_id);
  }
  if (timelineFrame === undefined) {
    return insertAutoPositionedShotGeneration(shot_id, generation_id);
  }
  return insertExplicitlyPositionedShotGeneration(shot_id, generation_id, timelineFrame);
}

export function toAddImageErrorMessage(error: Error): string {
  if (error.message.includes('Load failed') || error.message.includes('TypeError')) {
    return 'Network connection issue. Please check your internet connection and try again.';
  }
  if (error.message.includes('fetch')) {
    return 'Unable to connect to server. Please try again in a moment.';
  }
  if (isQuotaOrServerError(error)) {
    return 'Server is temporarily busy. Please wait a moment before trying again.';
  }
  return error.message;
}
