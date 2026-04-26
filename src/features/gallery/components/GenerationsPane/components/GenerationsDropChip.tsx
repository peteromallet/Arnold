import React from 'react';
import { Upload } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { usePositionStrategy } from '@/shared/hooks/panePositioning/usePositionStrategy';
import { UI_Z_LAYERS } from '@/shared/lib/uiLayers';
import { usePanesStore } from '@/shared/state/panesStore';
import { setDragging, useIsDraggingFiles } from '@/shared/state/dragOverlayStore';
import { useGenerationsPaneController } from '../hooks/useGenerationsPaneController';
import { useDropToGeneration } from '@/features/gallery/hooks/useDropToGeneration';

type GenerationsPaneController = ReturnType<typeof useGenerationsPaneController>;

const CHIP_VERTICAL_OFFSET_PX = 56;

export function GenerationsDropChip({
  controller,
}: {
  controller: GenerationsPaneController;
}): React.ReactElement | null {
  const { pane } = controller;
  const isDraggingFiles = useIsDraggingFiles();
  const dropToGeneration = useDropToGeneration();
  const effectiveGenerationsPaneHeight = usePanesStore((state) => state.effectiveGenerationsPaneHeight);
  const isVisible = pane.isLocked || (pane.paneIsOpen && !pane.isLocked);

  const dynamicStyle = usePositionStrategy({
    side: 'bottom',
    dimension: effectiveGenerationsPaneHeight,
    offsets: {
      horizontal:
        (pane.isShotsPaneLocked ? pane.shotsPaneWidth : 0) -
        (pane.isTasksPaneLocked ? pane.tasksPaneWidth : 0),
    },
    isVisible,
  });

  if (!isDraggingFiles || pane.isOnImageGenerationPage) {
    return null;
  }

  const transform = typeof dynamicStyle.transform === 'string'
    ? `${dynamicStyle.transform} translateY(-${CHIP_VERTICAL_OFFSET_PX}px)`
    : `translateX(-50%) translateY(-${CHIP_VERTICAL_OFFSET_PX}px)`;

  return (
    <div
      data-testid="generations-drop-chip"
      aria-hidden="true"
      onDragOver={(event) => {
        event.preventDefault();
      }}
      onDrop={(event) => {
        event.preventDefault();
        const files = Array.from(event.dataTransfer?.files ?? []);
        const items = Array.from(event.dataTransfer?.items ?? []);
        setDragging(false);
        if (files.length === 0) {
          return;
        }
        void dropToGeneration(files, { items });
      }}
      style={{
        ...dynamicStyle,
        transform,
        zIndex: UI_Z_LAYERS.GENERATIONS_DROP_CHIP,
      }}
      className={cn(
        'fixed flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900/95 px-3 py-2 text-sm font-medium text-zinc-100 shadow-xl backdrop-blur-sm',
        'pointer-events-auto touch-none',
      )}
    >
      <Upload className="h-4 w-4 text-zinc-300" />
      <span>Drop to add as generation</span>
    </div>
  );
}
