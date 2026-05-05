/**
 * useEmptyStateDrop - drag-and-drop handling for the empty timeline state.
 *
 * Supports both file drops and internal generation drops.
 * Returns drag state and handlers for the empty-state overlay.
 */

import { useState, useCallback } from 'react';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { filterValidTimelineImageFiles } from './imageDropValidation';

interface UseEmptyStateDropProps {
  onFileDrop?: (files: File[], targetFrame?: number, handles?: Array<FileSystemFileHandle | null>) => Promise<void>;
  onGenerationDrop?: (generationId: string, imageUrl: string, thumbUrl: string | undefined, targetFrame?: number) => Promise<void>;
  onImageUpload?: (files: File[]) => Promise<void>;
}

interface UseEmptyStateDropReturn {
  isDragOver: boolean;
  dragType: 'file' | 'generation' | null;
  handleEmptyStateDragEnter: (e: React.DragEvent) => void;
  handleEmptyStateDragOver: (e: React.DragEvent) => void;
  handleEmptyStateDragLeave: (e: React.DragEvent) => void;
  handleEmptyStateDrop: (e: React.DragEvent) => Promise<void>;
}

export function useEmptyStateDrop({
  onFileDrop,
  onGenerationDrop,
  onImageUpload,
}: UseEmptyStateDropProps): UseEmptyStateDropReturn {
  const [isDragOver, setIsDragOver] = useState(false);
  const [dragType, setDragType] = useState<'file' | 'generation' | null>(null);

  const handleEmptyStateDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.dataTransfer.types.includes('application/x-generation') && onGenerationDrop) {
      setIsDragOver(true);
      setDragType('generation');
    } else if (e.dataTransfer.types.includes('Files') && onFileDrop) {
      setIsDragOver(true);
      setDragType('file');
    }
  }, [onFileDrop, onGenerationDrop]);

  const handleEmptyStateDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.dataTransfer.types.includes('application/x-generation') && onGenerationDrop) {
      setIsDragOver(true);
      setDragType('generation');
      e.dataTransfer.dropEffect = 'copy';
    } else if (e.dataTransfer.types.includes('Files') && onFileDrop) {
      setIsDragOver(true);
      setDragType('file');
      e.dataTransfer.dropEffect = 'copy';
    } else {
      e.dataTransfer.dropEffect = 'none';
    }
  }, [onFileDrop, onGenerationDrop]);

  const handleEmptyStateDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x < rect.left || x >= rect.right || y < rect.top || y >= rect.bottom) {
      setIsDragOver(false);
      setDragType(null);
    }
  }, []);

  const handleEmptyStateDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    setDragType(null);

    // Handle internal generation drop first
    if (e.dataTransfer.types.includes('application/x-generation') && onGenerationDrop) {
      try {
        const dataString = e.dataTransfer.getData('application/x-generation');
        if (dataString) {
          const data = JSON.parse(dataString);
          if (data.generationId && data.imageUrl) {
            await onGenerationDrop(data.generationId, data.imageUrl, data.thumbUrl, 0);
            return;
          }
        }
      } catch (error) {
        normalizeAndPresentError(error, { context: 'Timeline', toastTitle: 'Failed to add image' });
      }
      return;
    }

    // Handle file drop
    if (!onImageUpload) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    const validFiles = filterValidTimelineImageFiles(files);

    if (validFiles.length === 0) return;

    try {
      await onImageUpload(validFiles);
    } catch (error) {
      normalizeAndPresentError(error, { context: 'Timeline', toastTitle: 'Failed to add images' });
    }
  }, [onImageUpload, onGenerationDrop]);

  return {
    isDragOver,
    dragType,
    handleEmptyStateDragEnter,
    handleEmptyStateDragOver,
    handleEmptyStateDragLeave,
    handleEmptyStateDrop,
  };
}
