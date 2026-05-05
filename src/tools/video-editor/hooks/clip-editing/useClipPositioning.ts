import { useCallback } from 'react';
import { updateClipInConfig } from '@/tools/video-editor/lib/editor-utils.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';
import type { ClipEditingContext } from './types.ts';

export function useClipPositioning(ctx: ClipEditingContext) {
  const {
    applyConfigEdit,
    applyRowsEdit,
    dataRef,
    resolvedConfig,
    selectedClipId,
    getValidClipIds,
  } = ctx;

  const handleResetClipPosition = useCallback(() => {
    if (!selectedClipId || !resolvedConfig) {
      return;
    }

    const nextConfig = updateClipInConfig(resolvedConfig, selectedClipId, (clip) => ({
      ...clip,
      x: undefined,
      y: undefined,
      width: undefined,
      height: undefined,
      cropTop: undefined,
      cropBottom: undefined,
      cropLeft: undefined,
      cropRight: undefined,
    }));
    applyConfigEdit(nextConfig, { selectedClipId });
  }, [applyConfigEdit, resolvedConfig, selectedClipId]);

  const handleResetClipsPosition = useCallback((clipIds: string[]) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const validClipIds = getValidClipIds(clipIds);
    if (validClipIds.length === 0) {
      return;
    }

    const metaUpdates = Object.fromEntries(
      validClipIds.map((clipId) => [clipId, {
        x: undefined,
        y: undefined,
        width: undefined,
        height: undefined,
        cropTop: undefined,
        cropBottom: undefined,
        cropLeft: undefined,
        cropRight: undefined,
      }]),
    ) as Record<string, Partial<ClipMeta>>;

    applyRowsEdit(current.rows, metaUpdates);
  }, [applyRowsEdit, dataRef, getValidClipIds]);

  return { handleResetClipPosition, handleResetClipsPosition };
}
