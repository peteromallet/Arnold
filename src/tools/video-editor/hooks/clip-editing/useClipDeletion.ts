import { useCallback } from 'react';
import type { ClipEditingContext, DeleteClipOptions } from './types.ts';

export function useClipDeletion(ctx: ClipEditingContext) {
  const {
    applyRowsEdit,
    dataRef,
    getValidClipIds,
    isPinnedGroupMember,
    notifyPinnedGroupEditBlocked,
  } = ctx;

  const handleDeleteClips = useCallback((clipIds: string[], options?: DeleteClipOptions) => {
    const current = dataRef.current;
    if (!current) {
      return;
    }

    const validClipIds = getValidClipIds(clipIds);
    const clipIdSet = new Set(validClipIds);
    if (clipIdSet.size === 0) {
      return;
    }

    if (!options?.allowPinnedGroupDelete && validClipIds.some((clipId) => isPinnedGroupMember(clipId))) {
      notifyPinnedGroupEditBlocked();
      return;
    }

    const nextRows = current.rows.map((row) => ({
      ...row,
      actions: row.actions.filter((action) => !clipIdSet.has(action.id)),
    }));
    applyRowsEdit(nextRows, undefined, [...clipIdSet], undefined, { semantic: true });
  }, [applyRowsEdit, dataRef, getValidClipIds, isPinnedGroupMember, notifyPinnedGroupEditBlocked]);

  const handleDeleteClip = useCallback((clipId: string, options?: DeleteClipOptions) => {
    handleDeleteClips([clipId], options);
  }, [handleDeleteClips]);

  return { handleDeleteClips, handleDeleteClip };
}
