import { invokeSupabaseEdgeFunction } from '@/integrations/supabase/functions/invokeSupabaseEdgeFunction';
import type { SelectedMediaClip } from '@/tools/video-editor/hooks/useSelectedMediaClips';
import {
  buildAnimationIntentPayload,
  buildGenerationClipPayloads,
  createEditableDraft,
  type AllowedSequenceAsset,
  type EditableSequenceDraft,
  type GenerateSequenceResponse,
  type SequenceAnimationIntent,
  type SequenceCreatorMode,
} from '@/tools/video-editor/sequences/generation';
import {
  AVAILABLE_SEQUENCE_CLIP_TYPES,
  AVAILABLE_SEQUENCE_METADATA,
} from '@/tools/video-editor/sequences/registry';
import { validateSequenceDraft } from '@/tools/video-editor/sequences/validation';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

export type RunSequenceGenerationOptions = {
  prompt: string;
  mode?: SequenceCreatorMode;
  editContext?: unknown;
  resolvedConfig: ResolvedTimelineConfig;
  selectedClips: readonly SelectedMediaClip[];
  attachedClips: readonly SelectedMediaClip[];
  allowedAssets: readonly AllowedSequenceAsset[];
  allowedAssetKeys: readonly string[];
  signal: AbortSignal;
};

export type RunSequenceGenerationResult =
  | {
      status: 'aborted';
    }
  | {
      status: 'ok';
      generationPrompt: string;
      animationIntentPayload: SequenceAnimationIntent | undefined;
      validDrafts: EditableSequenceDraft[];
      invalidCount: number;
      generationNote: string | null;
    }
  | {
      status: 'no_valid_drafts';
      generationPrompt: string;
      animationIntentPayload: SequenceAnimationIntent | undefined;
      invalidCount: number;
      generationNote: string;
    };

export const runSequenceGenerationRequest = async ({
  prompt,
  mode,
  editContext,
  resolvedConfig,
  selectedClips,
  attachedClips,
  allowedAssets,
  allowedAssetKeys,
  signal,
}: RunSequenceGenerationOptions): Promise<RunSequenceGenerationResult> => {
  const generationPrompt = prompt.trim();
  const animationIntentPayload = buildAnimationIntentPayload(generationPrompt);
  try {
    const response = await invokeSupabaseEdgeFunction<GenerateSequenceResponse>(
      'ai-generate-sequence',
      {
        body: {
          prompt: generationPrompt,
          mode: mode ?? 'generate',
          edit_context: editContext ?? null,
          ...(animationIntentPayload ? { animation_intent: animationIntentPayload } : {}),
          timeline: {
            output: resolvedConfig.output,
            tracks: resolvedConfig.tracks,
            clips: resolvedConfig.clips.map((clip) => ({
              id: clip.id,
              clipType: clip.clipType,
              asset: clip.asset,
              track: clip.track,
              at: clip.at,
              hold: clip.hold,
              params: clip.params,
            })),
          },
          selected_clips: buildGenerationClipPayloads(selectedClips, allowedAssets),
          attached_clips: buildGenerationClipPayloads(attachedClips, allowedAssets),
          allowed_clip_types: AVAILABLE_SEQUENCE_CLIP_TYPES,
          allowed_assets: allowedAssets.map((asset) => ({
            key: asset.key,
            assetKey: asset.key,
            url: asset.url,
            mediaType: asset.mediaType,
            source: asset.source,
          })),
          theme: resolvedConfig.theme,
          theme_overrides: resolvedConfig.theme_overrides,
        },
        timeoutMs: 150_000,
        signal,
      },
    );
    if (signal.aborted) return { status: 'aborted' };
    if (response.error) {
      throw new Error(response.details || response.error);
    }

    const validDrafts: EditableSequenceDraft[] = [];
    const invalidCountFromClient = (response.drafts ?? []).reduce((count, rawDraft) => {
      const validation = validateSequenceDraft(rawDraft, {
        metadata: AVAILABLE_SEQUENCE_METADATA,
        allowedClipTypes: AVAILABLE_SEQUENCE_CLIP_TYPES,
        allowedAssetKeys,
      });
      if (validation.ok) {
        validDrafts.push(createEditableDraft(validation.draft));
        return count;
      }
      return count + 1;
    }, 0);
    const invalidCount = invalidCountFromClient + (response.invalid_drafts?.length ?? 0);

    if (validDrafts.length === 0) {
      return {
        status: 'no_valid_drafts',
        generationPrompt,
        animationIntentPayload,
        invalidCount,
        generationNote: invalidCount > 0
          ? 'The model returned drafts, but none matched the trusted sequence schema for the current selected or attached assets.'
          : 'No sequence drafts were returned.',
      };
    }

    return {
      status: 'ok',
      generationPrompt,
      animationIntentPayload,
      validDrafts,
      invalidCount,
      generationNote: invalidCount > 0
        ? `${invalidCount} invalid draft${invalidCount === 1 ? '' : 's'} ${invalidCount === 1 ? 'was' : 'were'} rejected.`
        : null,
    };
  } catch (err) {
    if ((err as Error).name === 'AbortError') return { status: 'aborted' };
    throw err;
  }
};
