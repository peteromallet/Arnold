import { useState, useEffect, useMemo, useRef } from 'react';
import type { UseMutationResult } from '@tanstack/react-query';
import { useToggleGenerationStar } from '@/domains/generation/hooks/useGenerationMutations';
import { GenerationRow } from '@/domains/generation/types';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';

interface UseStarToggleProps {
  media: GenerationRow;
  starred?: boolean;
  shotId?: string;
}

interface UseStarToggleReturn {
  localStarred: boolean;
  setLocalStarred: React.Dispatch<React.SetStateAction<boolean>>;
  toggleStarMutation: UseMutationResult<void, Error, { id: string; starred: boolean; projectId: string; shotId?: string }>;
  handleToggleStar: () => void;
}

/**
 * Hook for managing star toggle state
 * Maintains local state for immediate UI updates while syncing with server
 */
export const useStarToggle = ({ media, starred, shotId }: UseStarToggleProps): UseStarToggleReturn => {
  const { selectedProjectId } = useProjectSelectionContext();
  const toggleStarMutation = useToggleGenerationStar();
  
  // Track when we last mutated to prevent stale prop syncing
  const lastMutationTimeRef = useRef<number>(0);
  const prevMediaIdRef = useRef<string>(media.id);

  // Local starred state to ensure UI reflects updates immediately even if parent data is stale
  const initialStarred = useMemo(() => {
    // Prefer explicit prop, fall back to media.starred if available
    
    if (typeof starred === 'boolean') {
      return starred;
    }
    if (typeof media.starred === 'boolean') {
      return media.starred;
    }
    return false;
  }, [starred, media.starred]);

  const [localStarred, setLocalStarred] = useState<boolean>(initialStarred);

  // Keep local state in sync when parent updates (e.g., after query refetch or navigating to different image)
  // BUT: Don't sync if we recently performed a mutation (prevents stale prop from resetting UI)
  useEffect(() => {
    const mediaChanged = prevMediaIdRef.current !== media.id;
    const timeSinceMutation = Date.now() - lastMutationTimeRef.current;
    const recentlyMutated = timeSinceMutation < 2000; // 2 second grace period
    const willSync = mediaChanged || !recentlyMutated;
    
    // Only sync if:
    // 1. Media changed (navigated to different image), OR
    // 2. Haven't recently mutated (prevents stale prop from overriding optimistic update)
    if (willSync) {
      setLocalStarred(initialStarred);
    }
    
    prevMediaIdRef.current = media.id;
  }, [initialStarred, media.id]);

  // Handler that records mutation time to prevent stale prop syncing
  const handleToggleStar = () => {
    const newStarred = !localStarred;
    
    // Record mutation time BEFORE updating state
    lastMutationTimeRef.current = Date.now();
    
    // Optimistically update UI
    setLocalStarred(newStarred);
    
    // IMPORTANT: Use generation_id (actual generations.id) when available, falling back to id
    // For ShotImageManager/Timeline images, id is shot_generations.id but generation_id is the actual generation ID
    // For variants, generation_id is in metadata.generation_id (the parent generation)
    const actualGenerationId = getGenerationId(media);
    
    // Trigger mutation
    if (!selectedProjectId) {
      setLocalStarred((prev) => !prev);
      return;
    }
    toggleStarMutation.mutate({
      id: actualGenerationId ?? media.id,
      starred: newStarred,
      projectId: selectedProjectId,
      shotId,
    });
  };

  return {
    localStarred,
    setLocalStarred,
    toggleStarMutation,
    handleToggleStar,
  };
};
