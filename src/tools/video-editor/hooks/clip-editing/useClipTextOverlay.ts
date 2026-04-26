import { useCallback } from 'react';
import { getVisualTracks } from '@/tools/video-editor/lib/editor-utils';
import { updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils';
import { resolveOverlaps } from '@/tools/video-editor/lib/resolve-overlaps';
import { getNextClipId } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas';
import type { ClipEditingContext } from './types';

export function useClipTextOverlay(ctx: ClipEditingContext) {
  const {
    applyRowsEdit,
    dataRef,
    selectedTrack,
    currentTimeRef,
    selectClip,
    setSelectedTrackId,
  } = ctx;

  const handleAddText = useCallback(() => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const visualTrack = selectedTrack?.kind === 'visual'
      ? selectedTrack
      : getVisualTracks(current.resolvedConfig)[0];
    if (!visualTrack) {
      return;
    }

    const clipId = getNextClipId(current.meta);
    const textDuration = 5;
    const action: TimelineAction = {
      id: clipId,
      start: currentTimeRef.current,
      end: currentTimeRef.current + textDuration,
      effectId: `effect-${clipId}`,
    };
    const rowsWithClip = current.rows.map((row) => (
      row.id === visualTrack.id
        ? { ...row, actions: [...row.actions, action] }
        : row
    ));
    // Resolve overlaps so the text clip doesn't land on top of existing clips
    const { rows: nextRows, metaPatches, adjustments: _adjustments } = resolveOverlaps(
      rowsWithClip, visualTrack.id, clipId, current.meta,
    );
    const nextClipOrder = updateClipOrder(current.clipOrder, visualTrack.id, (ids) => [...ids, clipId]);
    applyRowsEdit(nextRows, {
      ...metaPatches,
      [clipId]: {
        track: visualTrack.id,
        clipType: 'text',
        text: {
          content: 'Double-click to edit',
          fontSize: 64,
          color: '#ffffff',
          align: 'center',
        },
        x: 120,
        y: 120,
        width: 640,
        height: 180,
        opacity: 1,
      },
    }, undefined, nextClipOrder);
    selectClip(clipId);
    setSelectedTrackId(visualTrack.id);
  }, [applyRowsEdit, dataRef, selectedTrack, selectClip, setSelectedTrackId]);

  const handleAddTextAt = useCallback((trackId: string, time: number) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    // Ensure the target track is visual; fall back to first visual track
    const targetTrack = current.tracks.find((t) => t.id === trackId);
    const visualTrack = targetTrack?.kind === 'visual'
      ? targetTrack
      : getVisualTracks(current.resolvedConfig)[0];
    if (!visualTrack) {
      return;
    }

    const clipId = getNextClipId(current.meta);
    const textDuration = 5;
    const action: TimelineAction = {
      id: clipId,
      start: Math.max(0, time),
      end: Math.max(0, time) + textDuration,
      effectId: `effect-${clipId}`,
    };
    const rowsWithClip = current.rows.map((row) => (
      row.id === visualTrack.id
        ? { ...row, actions: [...row.actions, action] }
        : row
    ));
    const { rows: nextRows, metaPatches, adjustments: _adjustments } = resolveOverlaps(
      rowsWithClip, visualTrack.id, clipId, current.meta,
    );
    const nextClipOrder = updateClipOrder(current.clipOrder, visualTrack.id, (ids) => [...ids, clipId]);
    applyRowsEdit(nextRows, {
      ...metaPatches,
      [clipId]: {
        track: visualTrack.id,
        clipType: 'text',
        text: {
          content: 'Double-click to edit',
          fontSize: 64,
          color: '#ffffff',
          align: 'center',
        },
        x: 120,
        y: 120,
        width: 640,
        height: 180,
        opacity: 1,
      },
    }, undefined, nextClipOrder);
    selectClip(clipId);
    setSelectedTrackId(visualTrack.id);
  }, [applyRowsEdit, dataRef, selectClip, setSelectedTrackId]);

  return { handleAddText, handleAddTextAt };
}
