import React, { Suspense } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { TooltipProvider } from '@/shared/components/ui/tooltip';
import { Toaster as Sonner } from '@/shared/components/ui/runtime/sonner';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { useHandleExternalImageDrop, useAddImageToShot } from '@/shared/hooks/shots';
import { useShotCreation } from '@/shared/hooks/shotCreation/useShotCreation';
import { useShots } from '@/shared/contexts/ShotsContext';
import { AppRoutes } from '@/app/routes';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { AppProviders } from '@/app/providers/AppProviders';
import { useAppDndOverlay } from '@/app/hooks/useAppDndOverlay';
import { useAppExternalDrop } from '@/app/hooks/useAppExternalDrop';
import { useGlobalFileDragDetection } from '@/app/hooks/useGlobalFileDragDetection';
import { isRenderBudgetRuntimeEnabled } from '@/shared/dev/useRenderBudget';
import { useLastAffectedShot } from '@/shared/state/selectionStore';

const LazyRenderTelemetryOverlay = React.lazy(async () => {
  const module = await import('@/shared/dev/RenderTelemetryOverlay');
  return { default: module.RenderTelemetryOverlay };
});

const AppInternalContent: React.FC = () => {
  const { selectedProjectId } = useProjectSelectionContext();
  const { setLastAffectedShotId } = useLastAffectedShot();
  const { shots: shotsFromHook } = useShots();
  const { createShot } = useShotCreation();
  const addImageToShotMutation = useAddImageToShot();
  const handleExternalImageDropMutation = useHandleExternalImageDrop();
  const { handleDragStart, handleDragCancel, finalizeDropAnimation, overlayContent } = useAppDndOverlay();
  useGlobalFileDragDetection();

  const handleDragEnd = useAppExternalDrop({
    selectedProjectId,
    currentShotsCount: shotsFromHook?.length || 0,
    setLastAffectedShotId,
    createShot,
    addImageToShotMutation,
    handleExternalImageDropMutation,
    onDropHandled: finalizeDropAnimation,
  });

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  return (
    <TooltipProvider>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragCancel={handleDragCancel}
        onDragEnd={handleDragEnd}
      >
        <AppRoutes />
        {isRenderBudgetRuntimeEnabled() ? (
          <Suspense fallback={null}>
            <LazyRenderTelemetryOverlay />
          </Suspense>
        ) : null}
        <DragOverlay zIndex={10000} style={{ pointerEvents: 'none' }}>{overlayContent}</DragOverlay>
        <Sonner />
      </DndContext>
    </TooltipProvider>
  );
};

export function App() {
  return (
    <BrowserRouter>
      <AppProviders>
        <AppInternalContent />
      </AppProviders>
    </BrowserRouter>
  );
}
