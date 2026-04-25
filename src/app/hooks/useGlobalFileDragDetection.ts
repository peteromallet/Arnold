import { useEffect } from 'react';
import { setDragging } from '@/shared/state/dragOverlayStore';

function hasFileTransfer(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes('Files');
}

export function useGlobalFileDragDetection(): void {
  useEffect(() => {
    let dragDepth = 0;

    const handleDragEnter = (event: DragEvent) => {
      if (!hasFileTransfer(event)) {
        return;
      }

      dragDepth += 1;
      if (dragDepth === 1) {
        setDragging(true);
      }
    };

    const handleDragOver = (event: DragEvent) => {
      if (!hasFileTransfer(event)) {
        return;
      }

      event.preventDefault();
      if (dragDepth === 0) {
        dragDepth = 1;
        setDragging(true);
      }
    };

    const handleDragLeave = (event: DragEvent) => {
      if (!hasFileTransfer(event)) {
        return;
      }

      dragDepth = Math.max(0, dragDepth - 1);
      if (dragDepth === 0) {
        setDragging(false);
      }
    };

    const handleDrop = (event: DragEvent) => {
      if (!hasFileTransfer(event)) {
        return;
      }

      event.preventDefault();
      dragDepth = 0;
      setDragging(false);
    };

    window.addEventListener('dragenter', handleDragEnter);
    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('drop', handleDrop);

    return () => {
      window.removeEventListener('dragenter', handleDragEnter);
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('drop', handleDrop);
      dragDepth = 0;
      setDragging(false);
    };
  }, []);
}
