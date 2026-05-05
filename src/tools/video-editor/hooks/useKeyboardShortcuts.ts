import { useEffect } from 'react';
import { isEditableTarget } from '@/tools/video-editor/lib/coordinate-utils.ts';

interface UseKeyboardShortcutsOptions {
  hasSelectedClip: boolean;
  canMoveSelectedClipToTrack: boolean;
  precisionEnabled: boolean;
  selectedClipIds: ReadonlySet<string>;
  timelineFps: number;
  moveSelectedClipsToTrack: (direction: 'up' | 'down', selectedClipIds: ReadonlySet<string>) => void;
  undo: () => void;
  redo: () => void;
  selectAllClips: () => void;
  togglePlayPause: () => void;
  seekRelative: (deltaSeconds: number) => void;
  toggleMute: () => void;
  splitSelectedClip: () => void;
  deleteSelectedClip: () => void;
  clearSelection: () => void;
}

export function useKeyboardShortcuts({
  hasSelectedClip,
  canMoveSelectedClipToTrack,
  precisionEnabled,
  selectedClipIds,
  timelineFps,
  moveSelectedClipsToTrack,
  undo,
  redo,
  selectAllClips,
  togglePlayPause,
  seekRelative,
  toggleMute,
  splitSelectedClip,
  deleteSelectedClip,
  clearSelection,
}: UseKeyboardShortcutsOptions) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) {
        return;
      }

      const isModifierPressed = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();

      if (isModifierPressed && key === 'z' && !event.shiftKey) {
        event.preventDefault();
        undo();
        return;
      }

      if ((isModifierPressed && key === 'z' && event.shiftKey) || (event.ctrlKey && key === 'y')) {
        event.preventDefault();
        redo();
        return;
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        seekRelative(event.altKey && precisionEnabled ? -(1 / timelineFps) : -1);
        return;
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault();
        seekRelative(event.altKey && precisionEnabled ? (1 / timelineFps) : 1);
        return;
      }

      if (event.key === 'ArrowUp' && hasSelectedClip) {
        event.preventDefault();
        if (canMoveSelectedClipToTrack) {
          moveSelectedClipsToTrack('up', selectedClipIds);
        }
        return;
      }

      if (event.key === 'ArrowDown' && hasSelectedClip) {
        event.preventDefault();
        if (canMoveSelectedClipToTrack) {
          moveSelectedClipsToTrack('down', selectedClipIds);
        }
        return;
      }

      if (isModifierPressed && key === 'a') {
        event.preventDefault();
        selectAllClips();
        return;
      }

      if (event.code === 'Space') {
        event.preventDefault();
        togglePlayPause();
        return;
      }

      if (key === 'm' && hasSelectedClip) {
        event.preventDefault();
        toggleMute();
        return;
      }

      if (key === 's' && hasSelectedClip) {
        event.preventDefault();
        splitSelectedClip();
        return;
      }

      if ((event.key === 'Backspace' || event.key === 'Delete') && hasSelectedClip) {
        event.preventDefault();
        deleteSelectedClip();
        return;
      }

      if (event.key === 'Escape') {
        event.preventDefault();
        clearSelection();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [canMoveSelectedClipToTrack, clearSelection, deleteSelectedClip, hasSelectedClip, moveSelectedClipsToTrack, precisionEnabled, redo, seekRelative, selectAllClips, selectedClipIds, splitSelectedClip, timelineFps, toggleMute, togglePlayPause, undo]);
}
