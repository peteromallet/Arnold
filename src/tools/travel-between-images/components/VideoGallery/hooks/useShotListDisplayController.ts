import React from 'react';
import {
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { arrayMove, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { useReorderShots } from '@/shared/hooks/shots';
import { useShots } from '@/shared/contexts/ShotsContext';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { shotQueryKeys } from '@/shared/lib/queryKeys/shots';
import { usePendingNewShotDrop } from './usePendingNewShotDrop';
import type { Shot } from '@/domains/generation/types';
import type { NewShotDropHandlers } from './newShotDrop.types';

interface UseShotListDisplayControllerParams extends NewShotDropHandlers {
  projectId: string;
  shots?: Shot[];
  sortMode: 'ordered' | 'newest' | 'oldest';
}

export function useShotListDisplayController({
  projectId,
  shots: propShots,
  sortMode,
  onGenerationDropForNewShot,
  onFilesDropForNewShot,
  onSkeletonSetupReady,
}: UseShotListDisplayControllerParams) {
  const { isLoading: shotsLoading, error: shotsError } = useShots();
  const { selectedProjectId: currentProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const effectiveProjectId = projectId || currentProjectId;
  const currentProject = React.useMemo(
    () => projects.find((project) => project.id === currentProjectId) || null,
    [projects, currentProjectId]
  );

  const reorderShotsMutation = useReorderShots();
  const queryClient = useQueryClient();
  const [optimisticShots, setOptimisticShots] = React.useState<Shot[] | null>(null);
  const [isInputFocused, setIsInputFocused] = React.useState(false);

  const shots = React.useMemo(() => {
    const baseList = optimisticShots || propShots;
    if (!baseList) return baseList;

    if (reorderShotsMutation.isPending) {
      return baseList;
    }

    if (sortMode === 'newest') {
      return [...baseList].sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime();
        const dateB = new Date(b.created_at || 0).getTime();
        return dateB - dateA;
      });
    }

    if (sortMode === 'oldest') {
      return [...baseList].sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime();
        const dateB = new Date(b.created_at || 0).getTime();
        return dateA - dateB;
      });
    }

    return [...baseList].sort((a, b) => (a.position || 0) - (b.position || 0));
  }, [propShots, optimisticShots, reorderShotsMutation.isPending, sortMode]);

  React.useEffect(() => {
    if (!reorderShotsMutation.isPending && optimisticShots) {
      setOptimisticShots(null);
    }
  }, [reorderShotsMutation.isPending, optimisticShots]);

  React.useEffect(() => {
    const handleFocusIn = (e: FocusEvent) => {
      const target = e.target as HTMLElement;
      const isFormElement = target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.contentEditable === 'true';
      setIsInputFocused(isFormElement);
    };

    const handleFocusOut = (e: FocusEvent) => {
      const target = e.target as HTMLElement;
      const isFormElement = target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.contentEditable === 'true';
      if (isFormElement) {
        setIsInputFocused(false);
      }
    };

    document.addEventListener('focusin', handleFocusIn);
    document.addEventListener('focusout', handleFocusOut);

    return () => {
      document.removeEventListener('focusin', handleFocusIn);
      document.removeEventListener('focusout', handleFocusOut);
    };
  }, []);

  const keyboardSensor = useSensor(KeyboardSensor, {
    coordinateGetter: sortableKeyboardCoordinates,
  });

  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 250,
        tolerance: 5,
      },
    }),
    keyboardSensor
  );

  const handleDragStart = () => {
    if (isInputFocused) {
      return false;
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || !shots || !effectiveProjectId) {
      return;
    }

    if (active.id !== over.id) {
      const oldIndex = shots.findIndex((shot) => shot.id === active.id);
      const newIndex = shots.findIndex((shot) => shot.id === over.id);
      if (oldIndex === -1 || newIndex === -1) {
        return;
      }

      const reorderedShots = arrayMove(shots, oldIndex, newIndex);
      const shotsWithNewPositions = reorderedShots.map((shot, index) => ({
        ...shot,
        position: index + 1,
      }));

      setOptimisticShots(shotsWithNewPositions);
      queryClient.setQueryData(shotQueryKeys.list(effectiveProjectId, 0), shotsWithNewPositions);

      const shotOrders = reorderedShots.map((shot, index) => ({
        shotId: shot.id,
        position: index + 1,
      }));

      reorderShotsMutation.mutate(
        { projectId: effectiveProjectId, shotOrders },
        {
          onError: (error) => {
            queryClient.setQueriesData(
              { queryKey: [...shotQueryKeys.all, effectiveProjectId] },
              shots
            );
            toast.error(`Failed to reorder shots: ${error.message}`);
          },
        }
      );
    }
  };

  const sortableItems = React.useMemo(() => {
    if (!shots) return [];
    return shots.map((shot) => shot.id);
  }, [shots]);

  const currentShotIds = React.useMemo(() => shots?.map((s) => s.id) ?? [], [shots]);
  const pendingNewShot = usePendingNewShotDrop({
    currentShotIds,
    shots,
    onGenerationDropForNewShot,
    onFilesDropForNewShot,
    onSkeletonSetupReady,
  });

  const isDragDisabled = true;

  return {
    shotsLoading,
    shotsError,
    shots,
    currentProject,
    effectiveProjectId,
    sensors,
    handleDragStart,
    handleDragEnd,
    sortableItems,
    pendingNewShot,
    isDragDisabled,
  };
}
