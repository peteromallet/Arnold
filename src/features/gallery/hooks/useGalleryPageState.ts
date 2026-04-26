/** Page-level gallery controller for filters, pagination, and gallery actions. */

import { useState, useEffect, useMemo } from 'react';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useProjectGenerations, type GenerationsPaginatedResponse } from '@/shared/hooks/projects/useProjectGenerations';
import { useToggleGenerationStar } from '@/domains/generation/hooks/useGenerationMutations';
import { useDeleteGenerationWithConfirm } from '@/domains/generation/hooks/useDeleteGenerationWithConfirm';
import { useAddImageToShot, usePositionExistingGenerationInShot } from '@/shared/hooks/shots';
import { useShots } from '@/shared/contexts/ShotsContext';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { useGalleryFilterState } from '@/shared/hooks/gallery/useGalleryFilterState';
import { dispatchAppEvent } from '@/shared/lib/typedEvents';
import { useCurrentShot, useLastAffectedShot } from '@/shared/state/selectionStore';

interface UseGenerationsPageLogicOptions {
  itemsPerPage?: number;
  mediaType?: 'all' | 'image' | 'video';
  toolType?: string;
  enableDataLoading?: boolean;
}

/**
 * @internal Use `useGalleryPageState` instead (exported alias below).
 */
function useGenerationsPageLogic({
  itemsPerPage = 45,
  mediaType = 'image',
  toolType,
  enableDataLoading = true
}: UseGenerationsPageLogicOptions = {}) {
  const { selectedProjectId } = useProjectSelectionContext();
  const { shots: shotsData } = useShots();

  const shouldLoadData = enableDataLoading && !!selectedProjectId;
  const [page, setPage] = useState(1);

  const { currentShotId } = useCurrentShot();

  const { lastAffectedShotId, setLastAffectedShotId } = useLastAffectedShot();

  const filterState = useGalleryFilterState({
    shouldLoadData,
    onShotFilterApplied: setLastAffectedShotId,
  }, mediaType, toolType);

  const {
    selectedShotFilter,
    excludePositioned,
    searchTerm,
    starredOnly,
    filters,
    expectedItemCount,
    applyQueryFallback,
  } = filterState;

  useEffect(() => {
    setPage(1);
  }, [selectedShotFilter, excludePositioned]);

  useEffect(() => {
    setPage(1);
  }, [mediaType, starredOnly]);

  const generationsQuery = useProjectGenerations(
    shouldLoadData ? selectedProjectId : null,
    page,
    itemsPerPage,
    shouldLoadData,
    filters
  );
  const generationsResponse = generationsQuery.data as GenerationsPaginatedResponse | undefined;
  const isFetching = generationsQuery.isFetching;
  const isError = generationsQuery.isError;
  const error = generationsQuery.error;

  const isPlaceholderData = generationsQuery.isPlaceholderData;

  const isLoading = generationsQuery.isLoading || (isFetching && isPlaceholderData);

  useEffect(() => {
    applyQueryFallback({
      isLoading,
      isFetching,
      total: generationsResponse?.total,
      hasResponse: generationsResponse !== undefined,
    }, page);
  }, [selectedShotFilter, isLoading, isFetching, generationsResponse?.total, page, applyQueryFallback, generationsResponse]);


  const addImageToShotMutation = useAddImageToShot();
  const positionExistingGenerationMutation = usePositionExistingGenerationInShot();
  const { requestDelete, confirmDialogProps, deletingId } = useDeleteGenerationWithConfirm({ projectId: selectedProjectId });
  const toggleStarMutation = useToggleGenerationStar();


  const paginatedData = useMemo(() => {
    const items = generationsResponse?.items ?? [];
    const total = generationsResponse?.total ?? 0;
    const totalPages = Math.ceil(total / itemsPerPage);

    return {
      items,
      totalPages,
      currentPage: page
    };
  }, [generationsResponse, page, itemsPerPage]);


  useEffect(() => {

    if (!lastAffectedShotId && shotsData && shotsData.length > 0) {
      setLastAffectedShotId(shotsData[0].id);
    }
  }, [lastAffectedShotId, shotsData, setLastAffectedShotId, currentShotId, selectedShotFilter]);


  const handleServerPageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleDeleteGeneration = (id: string) => {
    requestDelete(id);
  };

  const handleToggleStar = (id: string, starred: boolean) => {
    if (!selectedProjectId) {
      return;
    }
    toggleStarMutation.mutate({ id, starred, projectId: selectedProjectId });
  };

  const handleAddToShot = async (targetShotId: string, generationId: string, imageUrl?: string, thumbUrl?: string): Promise<boolean> => {
    const resolvedTargetShotId = targetShotId || lastAffectedShotId || currentShotId;

    if (!resolvedTargetShotId || !selectedProjectId) {
      toast.error("No shot selected", {
        description: "Please select a shot in the gallery or create one first.",
      });
      return false;
    }

    const shouldPositionExisting = selectedShotFilter === resolvedTargetShotId && excludePositioned;

    const operationId = `${resolvedTargetShotId}:${generationId}:${Date.now()}`;
    dispatchAppEvent('shot-pending-upload', { shotId: resolvedTargetShotId, expectedCount: 1, operationId });

    try {
      if (shouldPositionExisting) {
        await positionExistingGenerationMutation.mutateAsync({
          shot_id: resolvedTargetShotId,
          generation_id: generationId,
          project_id: selectedProjectId,
        });
      } else {
        await addImageToShotMutation.mutateAsync({
          shot_id: resolvedTargetShotId,
          generation_id: generationId,
          imageUrl: imageUrl,
          thumbUrl: thumbUrl,
          project_id: selectedProjectId,
        });
      }

      setLastAffectedShotId(resolvedTargetShotId);
      dispatchAppEvent('shot-pending-upload-succeeded', { shotId: resolvedTargetShotId, operationId });
      return true;
    } catch (error) {
      normalizeAndPresentError(error, { context: 'useGenerationsPageLogic', toastTitle: 'Failed to add image to shot' });
      dispatchAppEvent('shot-pending-upload-failed', { shotId: resolvedTargetShotId, operationId });
      return false;
    }
  };

  const handleAddToShotWithoutPosition = async (targetShotId: string, generationId: string, imageUrl?: string, thumbUrl?: string): Promise<boolean> => {
    const resolvedTargetShotId = targetShotId || lastAffectedShotId || currentShotId;

    if (!resolvedTargetShotId || !selectedProjectId) {
      toast.error("No shot selected", {
        description: "Please select a shot in the gallery or create one first.",
      });
      return false;
    }

    try {
      await addImageToShotMutation.mutateAsyncWithoutPosition({
        shot_id: resolvedTargetShotId,
        generation_id: generationId,
        imageUrl: imageUrl,
        thumbUrl: thumbUrl,
        project_id: selectedProjectId,
      });
      setLastAffectedShotId(resolvedTargetShotId);
      return true;
    } catch (error) {
      normalizeAndPresentError(error, { context: 'useGenerationsPageLogic', toastTitle: 'Failed to add image to shot' });
      return false;
    }
  };

  return {
    selectedProjectId,
    shotsData,
    generationsResponse,
    paginatedData,
    lastAffectedShotId,
    totalCount: generationsResponse?.total ?? 0,

    page,
    selectedShotFilter,
    excludePositioned,
    searchTerm,
    starredOnly,

    setPage,
    setSelectedShotFilter: filterState.setSelectedShotFilter,
    setExcludePositioned: filterState.setExcludePositioned,
    setSearchTerm: filterState.setSearchTerm,
    setStarredOnly: filterState.setStarredOnly,

    isLoading,
    isFetching,
    isError,
    error,
    isDeleting: deletingId,

    confirmDialogProps,
    expectedItemCount,

    handleServerPageChange,
    handleDeleteGeneration,
    handleAddToShot,
    handleAddToShotWithoutPosition,
    handleToggleStar,
  };
}

export const useGalleryPageState = useGenerationsPageLogic;
