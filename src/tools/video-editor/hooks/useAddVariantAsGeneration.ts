import { useCallback, useState } from 'react';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError.ts';
import { hasVideoExtension } from '@/shared/lib/typeGuards.ts';
import {
  isVariantPromotionUnsupportedError,
  usePromoteVariantToGeneration,
} from '@/shared/hooks/variants/usePromoteVariantToGeneration.ts';
import { loadPrimaryVariantForGeneration } from '@/tools/video-editor/adapters/reigh/variantPromotionLookup.ts';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants.ts';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  executeGenerationAssetRegistrationPlan,
  planDuplicateGenerationAssetRegistration,
} from '@/tools/video-editor/lib/timeline-asset-plans.ts';
import { useTimelineCommands } from '@/tools/video-editor/hooks/useTimelineCommands.ts';
import {
  useTimelineEditorOps,
  useTimelineMutableAdapters,
} from '@/tools/video-editor/hooks/timelineStore.ts';

export interface UseAddVariantAsGenerationResult {
  addVariantAsGenerationAfterClip: (clipId: string, variant: GenerationVariant) => Promise<void>;
  isPending: (clipId: string, variantId: string) => boolean;
}

/**
 * Promotes a specific variant to a new generation and inserts it on the timeline
 * immediately after the given clip (mirrors handleDuplicateGenerationClip but uses
 * an arbitrary variant rather than the current primary).
 */
export function useAddVariantAsGeneration(): UseAddVariantAsGenerationResult {
  const runtime = useVideoEditorRuntime();
  const selectedProjectId = runtime.project.projectId;
  const commands = useTimelineCommands();
  const { patchRegistry, registerAsset, unpatchRegistry } = useTimelineEditorOps();
  const { dataRef } = useTimelineMutableAdapters();
  const promoteVariant = usePromoteVariantToGeneration();
  const [pending, setPending] = useState<Set<string>>(() => new Set());

  const setPendingKey = useCallback((key: string, on: boolean) => {
    setPending((prev) => {
      const next = new Set(prev);
      if (on) next.add(key); else next.delete(key);
      return next;
    });
  }, []);

  const addVariantAsGenerationAfterClip = useCallback(async (clipId: string, variant: GenerationVariant) => {
    if (!selectedProjectId) {
      runtime.toast.error('Select a project before adding a generation.');
      return;
    }

    const current = dataRef?.current;
    if (!current) return;

    const sourceMeta = current.meta[clipId];
    const sourceAssetKey = sourceMeta?.asset;
    const sourceAssetEntry = sourceAssetKey ? current.registry.assets[sourceAssetKey] : undefined;

    const key = `${clipId}:${variant.id}`;
    setPendingKey(key, true);
    try {
      const promoted = await promoteVariant.mutateAsync({
        variantId: variant.id,
        projectId: selectedProjectId,
      });

      const primaryRow = await loadPrimaryVariantForGeneration(promoted.id);
      if (!primaryRow) {
        throw new Error('Promoted generation is missing a primary variant.');
      }

      const newVariantId = primaryRow.id;
      const newLocation = primaryRow.location ?? promoted.location ?? variant.location;
      const newThumb = primaryRow.thumbnail_url ?? promoted.thumbnail_url ?? variant.thumbnail_url ?? null;

      const isVideo = hasVideoExtension(newLocation);
      const variantType: 'image' | 'video' = isVideo ? 'video' : 'image';
      const registrationPlan = planDuplicateGenerationAssetRegistration({
        generationId: promoted.id,
        variantId: newVariantId,
        variantType,
        imageUrl: newLocation,
        thumbUrl: newThumb ?? newLocation,
        sourceAssetEntry,
      });
      if (!registrationPlan.ok) {
        throw new Error('Failed to plan the new generation asset.');
      }

      const { assetKey, persistPromise } = executeGenerationAssetRegistrationPlan({
        plan: registrationPlan,
        patchRegistry,
        registerAsset,
      });
      const insertResult = commands.addClip({
        assetId: assetKey,
        afterClipId: clipId,
      });
      if (!insertResult.ok) {
        unpatchRegistry(assetKey);
        throw new Error(insertResult.error.message);
      }

      void persistPromise.catch((error) => {
        console.error('[video-editor] Failed to persist promoted variant asset:', error);
        unpatchRegistry(assetKey);
        runtime.toast.error('Failed to save asset');
      });
    } catch (error) {
      if (isVariantPromotionUnsupportedError(error)) {
        runtime.toast.error(error.message);
        return;
      }

      normalizeAndPresentError(error, {
        context: 'video-editor:add-variant-as-generation',
        toastTitle: 'Failed to add variant as generation',
      });
    } finally {
      setPendingKey(key, false);
    }
  }, [commands, dataRef, patchRegistry, promoteVariant, registerAsset, runtime.toast, selectedProjectId, setPendingKey, unpatchRegistry]);

  const isPending = useCallback(
    (clipId: string, variantId: string) => pending.has(`${clipId}:${variantId}`),
    [pending],
  );

  return { addVariantAsGenerationAfterClip, isPending };
}
