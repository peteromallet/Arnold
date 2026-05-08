import React, { useCallback, useMemo, useState } from 'react';
import { ArrowDownWideNarrow, ArrowUpWideNarrow, Check, Copy, Eye, EyeOff, Loader2, Pencil, Play, Plus, Search, Trash2, Video, X } from 'lucide-react';
import { useShotCreation } from '@/shared/hooks/shotCreation/useShotCreation';
import { cn } from '@/shared/components/ui/contracts/cn';
import { useShots } from '@/shared/contexts/ShotsContext';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useShotFinalVideos, type ShotFinalVideo } from '@/tools/travel-between-images/hooks/video/useShotFinalVideos';
import {
  setShotDragData,
  createDragPreview,
  getGenerationDropData,
  getMultiGenerationDropData,
  isValidDropTarget,
} from '@/shared/lib/dnd/dragDrop';
import { VideoGenerationModal } from '@/tools/travel-between-images/components/VideoGenerationModal';
import { useHiddenShots } from '@/tools/travel-between-images/hooks/useHiddenShots';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import { isVideoGeneration, isPositioned } from '@/shared/lib/typeGuards';
import { getDisplayUrl } from '@/shared/lib/media/mediaUrl';
import { useAddImageToShot } from '@/shared/hooks/shots/useShotGenerationMutations';
import { useDuplicateShot, useDeleteShot } from '@/shared/hooks/shots/useShotsCrud';
import { useDuplicateShotWithVideos } from '@/shared/hooks/shots/useDuplicateShotWithVideos';
import { useUpdateShotName } from '@/shared/hooks/shots/useShotUpdates';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import type { Shot } from '@/domains/generation/types';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';

interface ShotsPanelContentProps {
  projectId: string;
}

type SortMode = 'ordered' | 'newest' | 'oldest';

function ShotCard({
  shot,
  finalVideo,
  isHidden,
  onDoubleClick,
  onDuplicate,
  onDuplicateWithVideos,
  duplicateWithVideosIsPending,
  onDelete,
  onRename,
  onToggleHidden,
  onGenerationDrop,
}: {
  shot: Shot;
  finalVideo?: ShotFinalVideo;
  isHidden: boolean;
  onDoubleClick: () => void;
  onDuplicate: () => void;
  onDuplicateWithVideos: () => void;
  duplicateWithVideosIsPending: boolean;
  onDelete: () => void;
  onRename: (name: string) => void;
  onToggleHidden: () => void;
  onGenerationDrop: (shotId: string, generationId: string, imageUrl: string, thumbUrl?: string) => Promise<void>;
}) {
  const [isDropTarget, setIsDropTarget] = useState(false);
  const [dropState, setDropState] = useState<'idle' | 'loading' | 'success'>('idle');
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(shot.name);

  const thumbnailUrl = finalVideo?.thumbnailUrl
    ?? getDisplayUrl(shot.images?.[0]?.thumbUrl ?? shot.images?.[0]?.imageUrl ?? shot.images?.[0]?.location);
  const imageCount = shot.images?.filter((img) => !isVideoGeneration(img) && isPositioned(img)).length ?? 0;

  const handleDragStart = (event: React.DragEvent<HTMLDivElement>) => {
    const imageGenerationIds = (shot.images ?? [])
      .filter((image) => !isVideoGeneration(image))
      .map((image) => getGenerationId(image))
      .filter((id): id is string => typeof id === 'string' && id.length > 0);

    setShotDragData(event, { shotId: shot.id, shotName: shot.name, imageGenerationIds });
    const cleanup = createDragPreview(event, imageGenerationIds.length > 1 ? { badgeText: String(imageGenerationIds.length) } : undefined);
    if (cleanup) setTimeout(cleanup, 0);
  };

  const handleDragOver = (event: React.DragEvent) => {
    if (isValidDropTarget(event)) {
      event.preventDefault();
      event.stopPropagation();
      setIsDropTarget(true);
    }
  };

  const handleDragLeave = () => setIsDropTarget(false);

  const handleDrop = async (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDropTarget(false);
    setDropState('loading');

    try {
      const multiData = getMultiGenerationDropData(event);
      if (multiData) {
        for (const gen of multiData) {
          await onGenerationDrop(shot.id, gen.generationId, gen.imageUrl, gen.thumbUrl);
        }
        setDropState('success');
        setTimeout(() => setDropState('idle'), 1500);
        return;
      }

      const generationData = getGenerationDropData(event);
      if (generationData) {
        await onGenerationDrop(shot.id, generationData.generationId, generationData.imageUrl, generationData.thumbUrl);
        setDropState('success');
        setTimeout(() => setDropState('idle'), 1500);
        return;
      }

      setDropState('idle');
    } catch {
      setDropState('idle');
    }
  };

  const handleSaveName = () => {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== shot.name) {
      onRename(trimmed);
    }
    setIsEditing(false);
  };

  return (
    <div
      draggable={!isEditing}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onDoubleClick={onDoubleClick}
      className={cn(
        'group relative flex cursor-grab flex-col overflow-hidden rounded-md border border-border bg-card/80 transition-all hover:border-accent active:cursor-grabbing',
        isHidden && 'opacity-60',
        isDropTarget && 'ring-2 ring-primary scale-[1.02]',
        dropState === 'loading' && 'ring-2 ring-primary/50',
        dropState === 'success' && 'ring-2 ring-green-500',
      )}
    >
      {/* Actions overlay */}
      <div className="absolute right-0.5 top-0.5 z-10 flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setIsEditing(true); setEditName(shot.name); }}
          className="rounded bg-background/70 p-0.5 text-muted-foreground backdrop-blur-sm hover:text-foreground"
          title="Rename"
        >
          <Pencil className="h-2.5 w-2.5" />
        </button>
        <div className="group/duplicate relative flex">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDuplicate(); }}
            className="rounded bg-background/70 p-0.5 text-muted-foreground backdrop-blur-sm hover:text-foreground"
            title="Duplicate"
            aria-label="Duplicate shot"
          >
            <Copy className="h-2.5 w-2.5" />
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDuplicateWithVideos(); }}
            className="absolute -right-1 -top-1 z-20 rounded bg-background/90 p-0.5 text-muted-foreground opacity-0 shadow-sm backdrop-blur-sm transition-opacity hover:text-foreground focus:opacity-100 group-hover/duplicate:opacity-100"
            title="Duplicate with videos"
            aria-label="Duplicate with videos"
            disabled={duplicateWithVideosIsPending}
          >
            {duplicateWithVideosIsPending ? (
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
            ) : (
              <Video className="h-2.5 w-2.5" />
            )}
          </button>
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggleHidden(); }}
          className="rounded bg-background/70 p-0.5 text-muted-foreground backdrop-blur-sm hover:text-foreground"
          title={isHidden ? 'Unhide' : 'Hide'}
        >
          {isHidden ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
        </button>
        {isHidden && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="rounded bg-background/70 p-0.5 text-muted-foreground backdrop-blur-sm hover:text-destructive"
            title="Delete"
          >
            <Trash2 className="h-2.5 w-2.5" />
          </button>
        )}
      </div>

      <div className="relative aspect-video w-full overflow-hidden bg-muted">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={shot.name} className="h-full w-full object-cover" draggable={false} />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-muted-foreground">No images</div>
        )}
        {(isDropTarget || dropState !== 'idle') && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60 backdrop-blur-sm">
            {dropState === 'loading' ? (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            ) : dropState === 'success' ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <span className="text-[9px] font-medium text-primary">Drop here</span>
            )}
          </div>
        )}
        {finalVideo && dropState === 'idle' && !isDropTarget && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-background/70 text-foreground backdrop-blur-sm">
              <Play className="h-2.5 w-2.5 fill-current" />
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 px-1.5 py-1">
        {isEditing ? (
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter') handleSaveName(); if (e.key === 'Escape') setIsEditing(false); }}
            onBlur={handleSaveName}
            className="min-w-0 flex-1 rounded bg-background px-1 text-[10px] text-foreground outline-none ring-1 ring-border"
            autoFocus
          />
        ) : (
          <span className="min-w-0 flex-1 truncate text-[10px] text-foreground">{shot.name}</span>
        )}
        <span className="shrink-0 text-[9px] text-muted-foreground">{imageCount}</span>
      </div>
    </div>
  );
}

export function ShotsPanelContent({ projectId }: ShotsPanelContentProps) {
  useRenderBudget('ShotsPanelContent', 5);
  const { shots, isLoading, refetchShots } = useShots();
  const { finalVideoMap } = useShotFinalVideos(projectId);
  const { selectedProjectId } = useProjectSelectionContext();
  const addImageToShot = useAddImageToShot();
  const duplicateShot = useDuplicateShot();
  const duplicateShotWithVideos = useDuplicateShotWithVideos();
  const deleteShot = useDeleteShot();
  const updateShotName = useUpdateShotName();
  const { createShot } = useShotCreation();

  const [searchQuery, setSearchQuery] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('ordered');
  const [modalShot, setModalShot] = useState<Shot | null>(null);
  const [newShotDropState, setNewShotDropState] = useState<'idle' | 'loading' | 'success'>('idle');
  const [showHidden, setShowHidden] = useState(false);

  const { hiddenIds, toggle: toggleHidden } = useHiddenShots(selectedProjectId);

  const filteredShots = useMemo(() => {
    if (!shots) return [];
    let result = shots;
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter((shot) => shot.name.toLowerCase().includes(query));
    }
    if (sortMode === 'newest') {
      result = [...result].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
    } else if (sortMode === 'oldest') {
      result = [...result].sort((a, b) => (a.created_at ?? '').localeCompare(b.created_at ?? ''));
    }
    return result;
  }, [shots, searchQuery, sortMode]);

  const visibleShots = useMemo(() => {
    if (showHidden) return filteredShots;
    return filteredShots.filter((shot) => !hiddenIds.has(shot.id));
  }, [filteredShots, hiddenIds, showHidden]);

  const hiddenCount = useMemo(
    () => filteredShots.filter((shot) => hiddenIds.has(shot.id)).length,
    [filteredShots, hiddenIds],
  );

  const handleGenerationDrop = useCallback(async (shotId: string, generationId: string, imageUrl: string, thumbUrl?: string) => {
    if (!selectedProjectId) return;
    try {
      await addImageToShot.mutateAsync({
        shot_id: shotId,
        generation_id: generationId,
        project_id: selectedProjectId,
        imageUrl,
        thumbUrl,
      });
      refetchShots();
    } catch (error) {
      normalizeAndPresentError(error, { context: 'ShotsPanelContent', toastTitle: 'Failed to add image to shot' });
    }
  }, [addImageToShot, refetchShots, selectedProjectId]);

  const handleNewShotDrop = useCallback(async (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setNewShotDropState('loading');
    try {
      const multiData = getMultiGenerationDropData(event);
      const singleData = getGenerationDropData(event);
      const generationIds = multiData
        ? multiData.map((g) => g.generationId)
        : singleData ? [singleData.generationId] : [];
      if (generationIds.length === 0) { setNewShotDropState('idle'); return; }
      const result = await createShot({ generationIds });
      if (result?.shot) {
        refetchShots();
        setNewShotDropState('success');
        setTimeout(() => setNewShotDropState('idle'), 1500);
      } else {
        setNewShotDropState('idle');
      }
    } catch {
      setNewShotDropState('idle');
    }
  }, [createShot, refetchShots]);

  const handleDuplicate = useCallback(async (shotId: string) => {
    if (!selectedProjectId) return;
    try {
      await duplicateShot.mutateAsync({ shotId, projectId: selectedProjectId });
    } catch (error) {
      normalizeAndPresentError(error, { context: 'ShotsPanelContent', toastTitle: 'Failed to duplicate shot' });
    }
  }, [duplicateShot, selectedProjectId]);

  const handleDuplicateWithVideos = useCallback(async (shotId: string) => {
    if (!selectedProjectId) return;
    try {
      await duplicateShotWithVideos.mutateAsync({ shotId, projectId: selectedProjectId });
    } catch (error) {
      normalizeAndPresentError(error, { context: 'ShotsPanelContent', toastTitle: 'Failed to duplicate shot with videos' });
    }
  }, [duplicateShotWithVideos, selectedProjectId]);

  const handleDelete = useCallback(async (shotId: string) => {
    if (!selectedProjectId) return;
    try {
      await deleteShot.mutateAsync({ shotId, projectId: selectedProjectId });
    } catch (error) {
      normalizeAndPresentError(error, { context: 'ShotsPanelContent', toastTitle: 'Failed to delete shot' });
    }
  }, [deleteShot, selectedProjectId]);

  const handleRename = useCallback(async (shotId: string, name: string) => {
    if (!selectedProjectId) return;
    try {
      await updateShotName.mutateAsync({ shotId, name, projectId: selectedProjectId });
    } catch (error) {
      normalizeAndPresentError(error, { context: 'ShotsPanelContent', toastTitle: 'Failed to rename shot' });
    }
  }, [updateShotName, selectedProjectId]);

  if (isLoading) {
    return <div className="flex h-full items-center justify-center text-xs text-muted-foreground">Loading shots…</div>;
  }

  if (!shots || shots.length === 0) {
    return <div className="flex h-full items-center justify-center text-xs text-muted-foreground">No shots yet</div>;
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
        <Search className="h-3 w-3 shrink-0 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.stopPropagation()}
          placeholder="Search shots…"
          className="min-w-0 flex-1 bg-transparent text-xs text-foreground outline-none placeholder:text-muted-foreground"
        />
        {searchQuery && (
          <button type="button" onClick={() => setSearchQuery('')} className="text-muted-foreground hover:text-foreground">
            <X className="h-3 w-3" />
          </button>
        )}
        <div className="ml-auto flex items-center gap-0.5 border-l border-border pl-2">
          <button
            type="button"
            onClick={() => setSortMode(sortMode === 'newest' ? 'ordered' : 'newest')}
            className={cn('rounded p-1 text-muted-foreground transition-colors hover:text-foreground', sortMode === 'newest' && 'bg-accent text-foreground')}
            title="Newest first"
          >
            <ArrowDownWideNarrow className="h-3 w-3" />
          </button>
          <button
            type="button"
            onClick={() => setSortMode(sortMode === 'oldest' ? 'ordered' : 'oldest')}
            className={cn('rounded p-1 text-muted-foreground transition-colors hover:text-foreground', sortMode === 'oldest' && 'bg-accent text-foreground')}
            title="Oldest first"
          >
            <ArrowUpWideNarrow className="h-3 w-3" />
          </button>
          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={() => setShowHidden((prev) => !prev)}
              className={cn(
                'flex items-center gap-1 rounded px-1.5 py-1 text-[10px] text-muted-foreground transition-colors hover:text-foreground',
                showHidden && 'bg-accent text-foreground',
              )}
              title={showHidden ? 'Hide hidden shots' : 'Show hidden shots'}
            >
              {showHidden ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
              <span>{showHidden ? 'Hide' : 'Show'} Hidden ({hiddenCount})</span>
            </button>
          )}
        </div>
      </div>

      {/* Shot grid */}
      <div className="min-h-0 flex-1 overflow-x-auto overflow-y-hidden px-2 py-2">
        <div className="flex h-full flex-wrap content-start gap-1.5" style={{ flexDirection: 'column' }}>
          {/* New shot drop zone */}
          <div
            className="w-[110px] shrink-0"
            onDragOver={(e) => { if (isValidDropTarget(e)) { e.preventDefault(); e.stopPropagation(); } }}
            onDrop={handleNewShotDrop}
          >
            <div className={cn(
              'flex aspect-video w-full items-center justify-center rounded-md border-2 border-dashed border-border bg-card/50 text-muted-foreground transition-colors hover:border-accent hover:text-foreground',
              newShotDropState === 'loading' && 'border-primary/50',
              newShotDropState === 'success' && 'border-green-500',
            )}>
              {newShotDropState === 'loading' ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              ) : newShotDropState === 'success' ? (
                <Check className="h-4 w-4 text-green-500" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
            </div>
            <div className="px-1.5 py-1 text-center text-[10px] text-muted-foreground">New shot</div>
          </div>
          {visibleShots.map((shot) => (
            <div key={shot.id} className="w-[110px] shrink-0">
              <ShotCard
                shot={shot}
                finalVideo={finalVideoMap.get(shot.id)}
                isHidden={hiddenIds.has(shot.id)}
                onDoubleClick={() => setModalShot(shot)}
                onDuplicate={() => void handleDuplicate(shot.id)}
                onDuplicateWithVideos={() => void handleDuplicateWithVideos(shot.id)}
                duplicateWithVideosIsPending={duplicateShotWithVideos.isPending}
                onDelete={() => void handleDelete(shot.id)}
                onRename={(name) => void handleRename(shot.id, name)}
                onToggleHidden={() => toggleHidden(shot.id)}
                onGenerationDrop={(...args) => void handleGenerationDrop(...args)}
              />
            </div>
          ))}
        </div>
      </div>

      {filteredShots.length === 0 && searchQuery && (
        <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
          No shots match &ldquo;{searchQuery}&rdquo;
        </div>
      )}

      {modalShot && (
        <VideoGenerationModal
          isOpen={true}
          onClose={() => setModalShot(null)}
          shot={modalShot}
          defaultFinalVideoOpen={finalVideoMap.has(modalShot.id)}
        />
      )}
    </div>
  );
}
