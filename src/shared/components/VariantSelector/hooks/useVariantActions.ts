/**
 * useVariantActions - Manages variant action state and handlers
 *
 * Extracted from VariantSelector to isolate:
 * - Promote/delete/copy/load transient UI state
 * - Action handlers (promote, delete, copy ID, load settings, load images, star)
 * - Lineage depth checking on hover
 */

import { useState, useCallback, useRef } from 'react';
import { useAsyncOperationMap } from '@/shared/hooks/async/useAsyncOperation';
import { usePrefetchTaskData, usePrefetchTaskById } from '@/shared/hooks/tasks/useTaskPrefetch';
import { getLineageDepth } from '@/shared/hooks/variants/useLineageChain';
import { getSourceTaskIdLegacyCompatible } from '@/shared/lib/taskIdHelpers';
import { useToggleVariantStar } from '@/shared/hooks/variants/useToggleVariantStar';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';

interface UseVariantActionsProps {
  variants: GenerationVariant[];
  activeVariantId: string | null;
  isMobile: boolean;
  onPromoteToGeneration?: (variantId: string) => Promise<void>;
  onDeleteVariant?: (variantId: string) => Promise<void>;
  onLoadVariantSettings?: (variantParams: Record<string, unknown>) => void;
  onLoadVariantImages?: (variant: GenerationVariant) => void;
}

export function useVariantActions(props: UseVariantActionsProps) {
  const {
    variants,
    activeVariantId,
    isMobile,
    onPromoteToGeneration,
    onDeleteVariant,
    onLoadVariantSettings,
    onLoadVariantImages,
  } = props;

  // Transient UI state
  const [localIsPromoting, setLocalIsPromoting] = useState(false);
  const [promoteSuccess, setPromoteSuccess] = useState(false);
  const [copiedVariantId, setCopiedVariantId] = useState<string | null>(null);
  const [loadedSettingsVariantId, setLoadedSettingsVariantId] = useState<string | null>(null);
  const [loadedImagesVariantId, setLoadedImagesVariantId] = useState<string | null>(null);
  const [lineageGifVariantId, setLineageGifVariantId] = useState<string | null>(null);
  const [mobileInfoVariantId, setMobileInfoVariantId] = useState<string | null>(null);
  const [variantLineageDepth, setVariantLineageDepth] = useState<Record<string, number>>({});

  const deleteOperation = useAsyncOperationMap();
  const { toggleStar } = useToggleVariantStar();
  const { selectedProjectId } = useProjectSelectionContext();

  // Lineage depth checking on hover
  const checkedLineageIdsRef = useRef<Set<string>>(new Set());
  const prefetchTaskData = usePrefetchTaskData();
  const prefetchTaskById = usePrefetchTaskById();

  const checkLineageDepthOnHover = useCallback(async (variantId: string) => {
    if (checkedLineageIdsRef.current.has(variantId)) return;
    if (!selectedProjectId) return;
    checkedLineageIdsRef.current.add(variantId);
    try {
      const depth = await getLineageDepth(variantId, selectedProjectId);
      setVariantLineageDepth(prev => ({ ...prev, [variantId]: depth }));
    } catch {
      setVariantLineageDepth(prev => ({ ...prev, [variantId]: 0 }));
    }
  }, [selectedProjectId]);

  const handleVariantMouseEnter = useCallback((variant: GenerationVariant) => {
    if (isMobile) return;
    checkLineageDepthOnHover(variant.id);

    const variantParams = variant.params;
    const validSourceTaskId = getSourceTaskIdLegacyCompatible(variantParams);

    if (validSourceTaskId) {
      prefetchTaskById(validSourceTaskId);
    } else {
      prefetchTaskData(variant.generation_id);
    }
  }, [isMobile, prefetchTaskData, prefetchTaskById, checkLineageDepthOnHover]);

  // Action handlers
  const handlePromoteToGeneration = useCallback(async () => {
    if (!activeVariantId || !onPromoteToGeneration) return;
    setLocalIsPromoting(true);
    setPromoteSuccess(false);
    try {
      await onPromoteToGeneration(activeVariantId);
      setPromoteSuccess(true);
      setTimeout(() => setPromoteSuccess(false), 2000);
    } finally {
      setLocalIsPromoting(false);
    }
  }, [activeVariantId, onPromoteToGeneration]);

  const handleCopyId = useCallback((variantId: string) => {
    navigator.clipboard.writeText(variantId).catch(() => {});
    setCopiedVariantId(variantId);
    setTimeout(() => setCopiedVariantId(null), 2000);
  }, []);

  const handleLoadSettings = useCallback((variant: GenerationVariant) => {
    if (!onLoadVariantSettings) return;
    onLoadVariantSettings(variant.params as Record<string, unknown>);
    setLoadedSettingsVariantId(variant.id);
    setTimeout(() => setLoadedSettingsVariantId(null), 2000);
  }, [onLoadVariantSettings]);

  const handleLoadImages = useCallback((variant: GenerationVariant) => {
    if (!onLoadVariantImages) return;
    onLoadVariantImages(variant);
    setLoadedImagesVariantId(variant.id);
    setTimeout(() => setLoadedImagesVariantId(null), 2000);
  }, [onLoadVariantImages]);

  const handleToggleStar = useCallback((variantId: string, starred: boolean) => {
    const variant = variants.find(v => v.id === variantId);
    if (!variant) return;
    toggleStar({ variantId, generationId: variant.generation_id, starred });
  }, [variants, toggleStar]);

  const handleDeleteVariant = useCallback((variantId: string) => {
    if (!onDeleteVariant) return;
    deleteOperation.execute(
      variantId,
      () => onDeleteVariant(variantId),
      { context: 'VariantSelector' }
    );
  }, [onDeleteVariant, deleteOperation]);

  return {
    // Transient state
    localIsPromoting,
    promoteSuccess,
    copiedVariantId,
    loadedSettingsVariantId,
    loadedImagesVariantId,
    lineageGifVariantId,
    setLineageGifVariantId,
    mobileInfoVariantId,
    setMobileInfoVariantId,
    variantLineageDepth,

    // Handlers
    handleVariantMouseEnter,
    handlePromoteToGeneration,
    handleCopyId,
    handleLoadSettings,
    handleLoadImages,
    handleToggleStar,
    handleDeleteVariant,
    isDeleteLoading: (id: string) => deleteOperation.isLoading(id),
  };
}
