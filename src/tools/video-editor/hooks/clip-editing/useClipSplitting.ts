import { useCallback } from 'react';
import { splitClipAtPlayhead } from '@/tools/video-editor/lib/editor-utils.ts';
import { splitIntersectingClipsAtPlayhead } from '@/tools/video-editor/lib/clip-editing-utils.ts';
import type { ClipEditingContext } from './types.ts';

export function useClipSplitting(ctx: ClipEditingContext) {
  const {
    applyConfigEdit,
    dataRef,
    resolvedConfig,
    selectedClipId,
    currentTimeRef,
    getValidClipIds,
    isPinnedGroupMember,
    notifyPinnedGroupEditBlocked,
  } = ctx;

  const handleSplitSelectedClip = useCallback(() => {
    if (!selectedClipId || !resolvedConfig) {
      return;
    }

    if (isPinnedGroupMember(selectedClipId)) {
      notifyPinnedGroupEditBlocked();
      return;
    }

    const splitResult = splitClipAtPlayhead(resolvedConfig, selectedClipId, currentTimeRef.current);
    if (!splitResult.nextSelectedClipId) {
      return;
    }

    applyConfigEdit(splitResult.config, { selectedClipId: splitResult.nextSelectedClipId });
  }, [applyConfigEdit, isPinnedGroupMember, notifyPinnedGroupEditBlocked, resolvedConfig, selectedClipId]);

  const handleSplitClipAtTime = useCallback((clipId: string, timeSeconds: number) => {
    if (!resolvedConfig) {
      return;
    }

    if (isPinnedGroupMember(clipId)) {
      notifyPinnedGroupEditBlocked();
      return;
    }

    const splitResult = splitClipAtPlayhead(resolvedConfig, clipId, timeSeconds);
    if (!splitResult.nextSelectedClipId) {
      return;
    }

    applyConfigEdit(splitResult.config, { selectedClipId: splitResult.nextSelectedClipId });
  }, [applyConfigEdit, isPinnedGroupMember, notifyPinnedGroupEditBlocked, resolvedConfig]);

  const handleSplitClipsAtPlayhead = useCallback((clipIds: string[]) => {
    const current = dataRef.current;
    if (!current || !resolvedConfig) {
      return;
    }

    const validClipIds = getValidClipIds(clipIds);
    if (validClipIds.length === 0) {
      return;
    }

    if (validClipIds.some((clipId) => isPinnedGroupMember(clipId))) {
      notifyPinnedGroupEditBlocked();
      return;
    }

    const { config: nextResolvedConfig, didSplit } = splitIntersectingClipsAtPlayhead(
      resolvedConfig,
      current.rows,
      validClipIds,
      currentTimeRef.current,
    );
    if (!didSplit) {
      return;
    }

    applyConfigEdit(nextResolvedConfig);
  }, [applyConfigEdit, dataRef, getValidClipIds, isPinnedGroupMember, notifyPinnedGroupEditBlocked, resolvedConfig]);

  return { handleSplitSelectedClip, handleSplitClipAtTime, handleSplitClipsAtPlayhead };
}
