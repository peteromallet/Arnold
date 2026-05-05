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
      classifier?: { path: 'json' | 'code'; reason: string };
    }
  | {
      status: 'no_valid_drafts';
      generationPrompt: string;
      animationIntentPayload: SequenceAnimationIntent | undefined;
      invalidCount: number;
      generationNote: string;
      classifier?: { path: 'json' | 'code'; reason: string };
    }
  | {
      // Classifier routed the request to the code path (a custom sequence
      // component). Caller should dispatch a follow-up call via
      // runSequenceComponentGenerationRequest.
      status: 'classifier_code';
      generationPrompt: string;
      animationIntentPayload: SequenceAnimationIntent | undefined;
      classifier: { path: 'code'; reason: string };
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

    // Unified-UX classifier: if the model decided this prompt requires a
    // custom sequence component (path=code), surface that to the caller so
    // the panel can confirm/fork-to-DB and dispatch the code-path follow-up
    // via runSequenceComponentGenerationRequest. We do NOT call the
    // ai-generate-sequence-component endpoint here because the panel may
    // need to gate the code path behind a "Customize this sequence for
    // yourself" confirmation (T13).
    if (response.classifier?.path === 'code') {
      return {
        status: 'classifier_code',
        generationPrompt,
        animationIntentPayload,
        classifier: { path: 'code', reason: response.classifier.reason ?? '' },
      };
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

    const classifierVerdict = response.classifier
      ? { path: response.classifier.path, reason: response.classifier.reason ?? '' }
      : undefined;

    if (validDrafts.length === 0) {
      return {
        status: 'no_valid_drafts',
        generationPrompt,
        animationIntentPayload,
        invalidCount,
        generationNote: invalidCount > 0
          ? 'The model returned drafts, but none matched the trusted sequence schema for the current selected or attached assets.'
          : 'No sequence drafts were returned.',
        classifier: classifierVerdict,
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
      classifier: classifierVerdict,
    };
  } catch (err) {
    if ((err as Error).name === 'AbortError') return { status: 'aborted' };
    throw err;
  }
};

// ─── Sequence component code-path generation ─────────────────────────
// Companion to runSequenceGenerationRequest above. The JSON helper handles
// param-tweakable edits (workerRender stays true); this code-path helper
// dispatches to ai-generate-sequence-component when the unified-UX
// classifier (see T12) decides the request needs a generated React
// component instead. Body shape mirrors the JSON path so the same asset
// context flows through.

export interface ExistingSequenceComponentInput {
  code: string;
  schema: object;
  defaults: object;
}

export type RunSequenceComponentGenerationOptions = {
  prompt: string;
  name?: string;
  themeId?: string;
  existingComponent?: ExistingSequenceComponentInput;
  resolvedConfig: ResolvedTimelineConfig;
  selectedClips: readonly SelectedMediaClip[];
  attachedClips: readonly SelectedMediaClip[];
  allowedAssets: readonly AllowedSequenceAsset[];
  allowedAssetKeys: readonly string[];
  signal: AbortSignal;
};

export interface SequenceComponentGenerationResponse {
  code?: string;
  name?: string;
  description?: string;
  schemaJson?: object;
  defaultsJson?: object;
  message?: string;
  model?: string;
  error?: string;
  details?: string;
  rawOutput?: string;
}

export type RunSequenceComponentGenerationResult =
  | { status: 'aborted' }
  | {
      status: 'ok';
      code: string;
      name: string;
      description: string;
      schemaJson: object;
      defaultsJson: object;
      message: string | null;
      model: string | null;
    }
  | {
      status: 'error';
      error: string;
      rawOutput?: string;
    };

export const runSequenceComponentGenerationRequest = async ({
  prompt,
  name,
  themeId,
  existingComponent,
  resolvedConfig,
  selectedClips,
  attachedClips,
  allowedAssets,
  allowedAssetKeys,
  signal,
}: RunSequenceComponentGenerationOptions): Promise<RunSequenceComponentGenerationResult> => {
  const generationPrompt = prompt.trim();
  try {
    const response = await invokeSupabaseEdgeFunction<SequenceComponentGenerationResponse>(
      'ai-generate-sequence-component',
      {
        body: {
          prompt: generationPrompt,
          ...(name ? { name } : {}),
          ...(themeId ? { themeId } : {}),
          ...(existingComponent ? { existingComponent } : {}),
          selected_clips: buildGenerationClipPayloads(selectedClips, allowedAssets),
          attached_clips: buildGenerationClipPayloads(attachedClips, allowedAssets),
          allowed_assets: allowedAssets.map((asset) => ({
            key: asset.key,
            assetKey: asset.key,
            url: asset.url,
            mediaType: asset.mediaType,
            source: asset.source,
          })),
          allowed_asset_keys: allowedAssetKeys,
          theme: resolvedConfig.theme,
          theme_overrides: resolvedConfig.theme_overrides,
        },
        timeoutMs: 150_000,
        signal,
      },
    );
    if (signal.aborted) return { status: 'aborted' };
    if (response.error || !response.code || !response.schemaJson || !response.defaultsJson) {
      return {
        status: 'error',
        error: response.details || response.error || 'Sequence component generation returned an incomplete response',
        rawOutput: response.rawOutput,
      };
    }
    return {
      status: 'ok',
      code: response.code,
      name: response.name ?? '',
      description: response.description ?? '',
      schemaJson: response.schemaJson,
      defaultsJson: response.defaultsJson,
      message: response.message ?? null,
      model: response.model ?? null,
    };
  } catch (err) {
    if ((err as Error).name === 'AbortError') return { status: 'aborted' };
    throw err;
  }
};
