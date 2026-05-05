import { useState, useCallback } from "react";
import { normalizeAndPresentError } from "@/shared/lib/errorHandling/runtimeError";
import { pixelToFrame } from "../../utils/timeline-utils";
import { TIMELINE_PADDING_OFFSET } from "../../constants";
import {
  getDragType as sharedGetDragType,
  getGenerationDropData,
  wasDropHandledByVariant,
  type DragType,
  type GenerationDropData
} from "@/shared/lib/dnd/dragDrop";
import { filterValidTimelineImageFiles } from "./imageDropValidation";

// Re-export for backward compatibility
export type { DragType, GenerationDropData };

type FileDropHandleItem = DataTransferItem & {
  getAsFileSystemHandle?: () => Promise<FileSystemHandle | null>;
};

type FileSystemHandleLike = FileSystemHandle & {
  getFile?: () => Promise<File>;
};

function supportsLocalFileHandles(): boolean {
  return typeof DataTransferItem !== 'undefined'
    && typeof (DataTransferItem.prototype as FileDropHandleItem).getAsFileSystemHandle === 'function';
}

function isReadableFileHandle(handle: FileSystemHandleLike | null | undefined): handle is FileSystemFileHandle {
  return !!handle && handle.kind === 'file' && typeof handle.getFile === 'function';
}

interface UseUnifiedDropProps {
  onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
  onGenerationDrop?: (generationId: string, imageUrl: string, thumbUrl: string | undefined, targetFrame?: number) => Promise<void>;
  fullMin: number;
  fullRange: number;
}

/**
 * Unified drop hook that handles both file drops (from file system) and generation drops (from GenerationsPane)
 * Reuses the same coordinate system and visual feedback for consistency
 */
export const useUnifiedDrop = ({
  onFileDrop,
  onGenerationDrop,
  fullMin,
  fullRange
}: UseUnifiedDropProps) => {
  const [isFileOver, setIsFileOver] = useState(false);
  const [isGenerationOver, setIsGenerationOver] = useState(false);
  const [dropTargetFrame, setDropTargetFrame] = useState<number | null>(null);

  /**
   * Detect the type of item being dragged (wrapper around shared utility for logging)
   */
  const getDragType = useCallback((e: React.DragEvent<HTMLDivElement>): DragType => {
    const dragType = sharedGetDragType(e);
    
    return dragType;
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    const dragType = getDragType(e);
    
    if (dragType === 'file' && onFileDrop) {
      setIsFileOver(true);
    } else if (dragType === 'generation' && onGenerationDrop) {
      setIsGenerationOver(true);
    }
  }, [getDragType, onFileDrop, onGenerationDrop]);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>, containerRef: React.RefObject<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    const dragType = getDragType(e);
    
    if (dragType !== 'none' && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      // Account for timeline padding offset - same calculation as useTimelineDrag
      const relativeX = e.clientX - rect.left - TIMELINE_PADDING_OFFSET;
      const effectiveWidth = rect.width - (TIMELINE_PADDING_OFFSET * 2);
      const targetFrame = Math.max(0, pixelToFrame(relativeX, effectiveWidth, fullMin, fullRange));
      setDropTargetFrame(targetFrame);
      
      if (dragType === 'file' && onFileDrop) {
        setIsFileOver(true);
        e.dataTransfer.dropEffect = 'copy';
      } else if (dragType === 'generation' && onGenerationDrop) {
        setIsGenerationOver(true);
        e.dataTransfer.dropEffect = 'copy';
      } else {
        e.dataTransfer.dropEffect = 'none';
      }
    } else {
      e.dataTransfer.dropEffect = 'none';
      setDropTargetFrame(null);
    }
  }, [getDragType, onFileDrop, onGenerationDrop, fullMin, fullRange]);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Only clear state if we're actually leaving the container
    if (e.currentTarget.contains(e.relatedTarget as Node)) {
      return;
    }
    
    setIsFileOver(false);
    setIsGenerationOver(false);
    setDropTargetFrame(null);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent<HTMLDivElement>, containerRef?: React.RefObject<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    const dragType = getDragType(e);
    
    // Calculate target frame directly from drop coordinates (not stale state)
    // This fixes the "jumping to wrong location" bug caused by stale dropTargetFrame state
    let targetFrame: number | null = dropTargetFrame;
    if (containerRef?.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const relativeX = e.clientX - rect.left - TIMELINE_PADDING_OFFSET;
      const effectiveWidth = rect.width - (TIMELINE_PADDING_OFFSET * 2);
      targetFrame = Math.max(0, pixelToFrame(relativeX, effectiveWidth, fullMin, fullRange));
    }
    
    // Reset visual state — always, even if a child variant handler already
    // processed the drop. This is the whole point: the event bubbles up so we
    // can clean up, but we skip re-processing the action.
    setIsFileOver(false);
    setIsGenerationOver(false);
    setDropTargetFrame(null);

    // A child variant drop target already handled this drop — don't also
    // create a standalone image.
    if (wasDropHandledByVariant(e)) {
      return;
    }

    // Handle file drops (from file system)
    if (dragType === 'file' && onFileDrop) {
      const files = Array.from(e.dataTransfer.files);

      if (files.length === 0) {
        return;
      }

      const canUseLocalHandles = supportsLocalFileHandles();
      const fileItems = canUseLocalHandles
        ? (Array.from(e.dataTransfer.items).filter((it): it is FileDropHandleItem => it.kind === 'file'))
        : null;
      const allHandlePromises: Array<Promise<FileSystemHandle | null> | null> | null = fileItems
        ? files.map((_, idx) => fileItems[idx]?.getAsFileSystemHandle?.() ?? null)
        : null;

      const validFiles = filterValidTimelineImageFiles(files);

      if (validFiles.length === 0) {
        return;
      }

      let alignedHandlePromises: Array<Promise<FileSystemHandle | null> | null> | null = null;
      if (allHandlePromises) {
        alignedHandlePromises = [];
        let cursor = 0;
        for (let i = 0; i < files.length && cursor < validFiles.length; i++) {
          if (files[i] === validFiles[cursor]) {
            alignedHandlePromises.push(allHandlePromises[i]);
            cursor++;
          }
        }
      }

      let handles: Array<FileSystemFileHandle | null> | undefined;
      if (alignedHandlePromises) {
        const resolved = await Promise.all(
          alignedHandlePromises.map((p) => (p ? p.catch(() => null) : Promise.resolve(null))),
        );
        handles = resolved.map((h) => (isReadableFileHandle(h as FileSystemHandleLike | null) ? (h as FileSystemFileHandle) : null));
      }

      try {
        await onFileDrop(validFiles, targetFrame ?? undefined, handles);
      } catch (error) {
        normalizeAndPresentError(error, { context: 'UnifiedDrop', toastTitle: 'Failed to add images' });
      }
    }
    
    // Handle generation drops (from GenerationsPane)
    else if (dragType === 'generation' && onGenerationDrop) {
      
      const data = getGenerationDropData(e);
      
      if (!data) {
        normalizeAndPresentError(new Error('No valid data found'), { context: 'UnifiedDrop', showToast: false });
        return;
      }
      
      try {
        
        await onGenerationDrop(data.generationId, data.imageUrl, data.thumbUrl, targetFrame ?? undefined);
      } catch (error) {
        normalizeAndPresentError(error, { context: 'UnifiedDrop', toastTitle: 'Failed to add generation' });
      }
    }
  }, [getDragType, onFileDrop, onGenerationDrop, dropTargetFrame, fullMin, fullRange]);

  // Determine current drag type for consumers
  const currentDragType: DragType = isFileOver ? 'file' : isGenerationOver ? 'generation' : 'none';

  return {
    isFileOver: isFileOver || isGenerationOver, // Combined state for backward compatibility
    dropTargetFrame,
    dragType: currentDragType,
    handleDragEnter,
    handleDragOver,
    handleDragLeave,
    handleDrop,
  };
};
