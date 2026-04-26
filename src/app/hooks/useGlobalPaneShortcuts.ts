import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { usePanesStore } from '@/shared/state/panesStore';
import { resolveVideoEditorPath } from '@/tools/video-editor/lib/video-editor-path';

/**
 * Global keyboard shortcuts for pane management.
 *
 * Opt+W — toggle editor pane (top) lock
 * Opt+S — toggle generations pane (bottom) lock
 * Opt+A — toggle shots pane (left) lock
 * Opt+D — toggle tasks pane (right) lock
 * Opt+Shift+W — navigate to video editor
 * Opt+Shift+S — navigate to image generation
 * Opt+Shift+A — toggle shots pane lock (same as Opt+A)
 * Opt+Shift+D — toggle tasks pane lock (same as Opt+D)
 */
export function useGlobalPaneShortcuts() {
  const queryClient = useQueryClient();
  const { selectedProjectId } = useProjectSelectionContext();
  const isEditorPaneLocked = usePanesStore((state) => state.isEditorPaneLocked);
  const setIsEditorPaneLocked = usePanesStore((state) => state.setIsEditorPaneLocked);
  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  const setIsGenerationsPaneLocked = usePanesStore((state) => state.setIsGenerationsPaneLocked);
  const isShotsPaneLocked = usePanesStore((state) => state.isShotsPaneLocked);
  const setIsShotsPaneLocked = usePanesStore((state) => state.setIsShotsPaneLocked);
  const isTasksPaneLocked = usePanesStore((state) => state.isTasksPaneLocked);
  const setIsTasksPaneLocked = usePanesStore((state) => state.setIsTasksPaneLocked);
  const navigate = useNavigate();

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!event.altKey) return;

      // Skip if focus is in an editable element
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      ) {
        return;
      }

      switch (event.code) {
        case 'KeyW':
          event.preventDefault();
          if (event.shiftKey) {
            navigate(resolveVideoEditorPath(queryClient, selectedProjectId));
          } else {
            setIsEditorPaneLocked(!isEditorPaneLocked);
          }
          break;

        case 'KeyS':
          event.preventDefault();
          if (event.shiftKey) {
            navigate('/tools/image-generation');
          } else {
            setIsGenerationsPaneLocked(!isGenerationsPaneLocked);
          }
          break;

        case 'KeyA':
          event.preventDefault();
          setIsShotsPaneLocked(!isShotsPaneLocked);
          break;

        case 'KeyD':
          event.preventDefault();
          setIsTasksPaneLocked(!isTasksPaneLocked);
          break;
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    isEditorPaneLocked,
    isGenerationsPaneLocked,
    isShotsPaneLocked,
    isTasksPaneLocked,
    navigate,
    queryClient,
    selectedProjectId,
    setIsEditorPaneLocked,
    setIsGenerationsPaneLocked,
    setIsShotsPaneLocked,
    setIsTasksPaneLocked,
  ]);
}
