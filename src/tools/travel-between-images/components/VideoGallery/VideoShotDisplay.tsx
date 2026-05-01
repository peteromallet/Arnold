import React, { useMemo, useState } from 'react';
import type { Shot, GenerationRow } from '@/domains/generation/types';
import { useUpdateShotName, useDeleteShot, useDuplicateShot } from '@/shared/hooks/shots';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { cn } from '@/shared/components/ui/contracts/cn';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/components/ui/alert-dialog';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { useClickRipple } from '@/shared/hooks/interaction/useClickRipple';
import { isVideoGeneration, isPositioned } from '@/shared/lib/typeGuards';
import { VideoGenerationModal } from '../VideoGenerationModal';
import { ImageGenerationModal } from '@/shared/components/modals/ImageGenerationModal';
import { useIsMobile } from '@/shared/hooks/mobile';
import { MediaLightbox } from '@/domains/media-lightbox/MediaLightbox';
import type { ShotFinalVideo } from '../../hooks/video/useShotFinalVideos';
import { useVideoShotDisplayState } from '../hooks/useVideoShotDisplayState';
import { ShotMetadata, ShotControls, ShotPreview } from './VideoShotDisplayParts';
import { useShotAdditionSelectionOptional } from '@/shared/state/selectionStore';
import { usePanesStore } from '@/shared/state/panesStore';

interface VideoShotDisplayProps {
  shot: Shot;
  onSelectShot: () => void;
  onDuplicateShot?: () => void;
  isHidden?: boolean;
  onToggleHidden?: (e?: React.MouseEvent) => void;
  currentProjectId: string | null;
  dragHandleProps?: {
    disabled?: boolean;
    [key: string]: unknown;
  };
  dragDisabledReason?: string;
  shouldLoadImages?: boolean;
  shotIndex?: number;
  projectAspectRatio?: string;
  isHighlighted?: boolean;
  pendingUploads?: number;
  imagesOverlay?: React.ReactNode;
  dropLoadingState?: 'idle' | 'loading' | 'success';
  dataTour?: string;
  finalVideo?: ShotFinalVideo;
}

const SKIP_DELETE_CONFIRMATION_KEY = 'reigh-skip-delete-shot-confirmation';

export const VideoShotDisplay: React.FC<VideoShotDisplayProps> = ({
  shot,
  onSelectShot,
  onDuplicateShot,
  isHidden = false,
  onToggleHidden,
  currentProjectId,
  dragHandleProps,
  dragDisabledReason,
  projectAspectRatio,
  isHighlighted = false,
  pendingUploads = 0,
  imagesOverlay,
  dropLoadingState = 'idle',
  dataTour,
  finalVideo,
}) => {
  const isTempShot = shot.id.startsWith('temp-');

  const { triggerRipple, rippleStyles, isRippleActive } = useClickRipple();

  const handleRippleTrigger = (e: React.PointerEvent) => {
    const target = e.target as HTMLElement;
    const isButton = target.closest('button, [role="button"], input');
    if (!isButton) {
      triggerRipple(e);
    }
  };

  const updateShotNameMutation = useUpdateShotName();
  const deleteShotMutation = useDeleteShot();
  const duplicateShotMutation = useDuplicateShot();

  const isGenerationsPaneLocked = usePanesStore((state) => state.isGenerationsPaneLocked);
  const isMobile = useIsMobile();
  const shotAdditionSelection = useShotAdditionSelectionOptional();
  const {
    isEditingName,
    editableName,
    isDeleteDialogOpen,
    isVideoModalOpen,
    showVideo,
    isFinalVideoLightboxOpen,
    skipConfirmationChecked,
    isSelectedForAddition,
    startNameEdit,
    cancelNameEdit,
    setEditableName,
    finishNameEdit,
    setDeleteDialogOpen,
    setSkipConfirmationChecked,
    setVideoModalOpen,
    setShowVideo,
    setFinalVideoLightboxOpen,
    setSelectedForAddition,
  } = useVideoShotDisplayState({
    shotId: shot.id,
    shotName: shot.name,
    selectedShotId: shotAdditionSelection?.selectedShotId,
    isGenerationsPaneLocked,
  });

  const [isImageGenModalOpen, setIsImageGenModalOpen] = useState(false);

  const finalVideoRow = useMemo((): GenerationRow | null => {
    if (!finalVideo) return null;
    return {
      id: finalVideo.id,
      location: finalVideo.location,
      thumbUrl: finalVideo.thumbnailUrl ?? undefined,
      type: 'video',
    };
  }, [finalVideo]);

  const handleSelectShotForAddition = (e: React.MouseEvent) => {
    e.stopPropagation();
    shotAdditionSelection?.selectShotForAddition(shot.id);
    setSelectedForAddition(true);
  };

  const handleNameEditToggle = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (isEditingName) {
      cancelNameEdit(shot.name);
      return;
    }
    startNameEdit();
  };

  const handleSaveName = async () => {
    if (!currentProjectId) {
      toast.error('Cannot update shot: Project ID is missing.');
      return;
    }
    if (editableName.trim() === '') {
      toast.error('Shot name cannot be empty.');
      cancelNameEdit(shot.name);
      return;
    }
    if (editableName.trim() === shot.name) {
      finishNameEdit();
      return;
    }

    try {
      await updateShotNameMutation.mutateAsync(
        { shotId: shot.id, newName: editableName.trim(), projectId: currentProjectId },
        {
          onError: (error) => {
            toast.error(`Failed to update shot: ${error.message}`);
            cancelNameEdit(shot.name);
          },
        }
      );
    } finally {
      finishNameEdit();
    }
  };

  const performDelete = async () => {
    if (!currentProjectId) {
      toast.error('Cannot delete shot: Project ID is missing.');
      return;
    }

    try {
      await deleteShotMutation.mutateAsync(
        { shotId: shot.id, projectId: currentProjectId },
        {
          onError: (error) => {
            toast.error(`Failed to delete shot: ${error.message}`);
          },
        }
      );
    } catch (error) {
      normalizeAndPresentError(error, { context: 'VideoShotDisplay', showToast: false });
    }
  };

  const handleDeleteShot = async (e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!currentProjectId) {
      toast.error('Cannot delete shot: Project ID is missing.');
      return;
    }

    const skipConfirmation = localStorage.getItem(SKIP_DELETE_CONFIRMATION_KEY) === 'true';
    if (skipConfirmation) {
      await performDelete();
      return;
    }

    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (skipConfirmationChecked) {
      localStorage.setItem(SKIP_DELETE_CONFIRMATION_KEY, 'true');
    }

    setDeleteDialogOpen(false);
    await performDelete();
  };

  const handleDuplicateShot = async (e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!currentProjectId) {
      return;
    }

    try {
      onDuplicateShot?.();
      await duplicateShotMutation.mutateAsync({
        shotId: shot.id,
        projectId: currentProjectId,
      });
    } catch (error) {
      normalizeAndPresentError(error, { context: 'VideoShotDisplay', toastTitle: 'Failed to duplicate shot' });
    }
  };

  const displayImages = (shot.images || [])
    .filter(img => !isVideoGeneration(img) && isPositioned(img))
    .sort((a, b) => {
      const fa = a.timeline_frame ?? 0;
      const fb = b.timeline_frame ?? 0;
      return fa - fb;
    });

  const handleClick = () => {
    if (isTempShot) return;
    onSelectShot();
  };

  return (
    <>
      <div
        key={shot.id}
        className={cn(
          'click-ripple group p-4 border rounded-lg bg-card/50 dark:bg-card/70 dark:border-border transition-all duration-700 relative flex flex-col',
          isRippleActive && 'ripple-active',
          isHighlighted && 'ring-4 ring-blue-500 ring-opacity-75 shadow-[0_0_30px_rgba(59,130,246,0.6)] scale-105 animate-pulse',
          isHidden && 'opacity-50',
          isTempShot
            ? 'opacity-70 cursor-wait animate-pulse'
            : 'hover:bg-card/80 hover:shadow-wes-hover hover:border-primary/30 hover:scale-105 cursor-pointer',
        )}
        style={rippleStyles}
        onPointerDown={isTempShot ? undefined : handleRippleTrigger}
        onClick={handleClick}
        data-tour={dataTour}
      >
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <ShotMetadata
              displayName={editableName || shot.name}
              isEditingName={isEditingName}
              editableName={editableName}
              onEditableNameChange={setEditableName}
              onSaveName={handleSaveName}
              onCancelEdit={() => cancelNameEdit(shot.name)}
              generationMode={(shot.settings as Record<string, unknown>)?.generationMode as string | undefined}
            />
            {isHidden && (
              <span className="text-[10px] font-medium uppercase tracking-wider text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded shrink-0">
                Hidden
              </span>
            )}
          </div>
          <ShotControls
            isTempShot={isTempShot}
            displayImagesCount={displayImages.length}
            isEditingName={isEditingName}
            dragHandleProps={dragHandleProps}
            dragDisabledReason={dragDisabledReason}
            duplicateIsPending={duplicateShotMutation.isPending}
            isHidden={isHidden}
            onVideoClick={() => setVideoModalOpen(true)}
            onEditName={handleNameEditToggle}
            onDuplicate={handleDuplicateShot}
            onToggleHidden={onToggleHidden}
            onDelete={handleDeleteShot}
          />
        </div>

        <ShotPreview
          displayImages={displayImages}
          pendingUploads={pendingUploads}
          imagesOverlay={imagesOverlay}
          finalVideo={finalVideo}
          showVideo={showVideo}
          onShowVideoChange={setShowVideo}
          projectAspectRatio={projectAspectRatio}
          dropLoadingState={dropLoadingState}
          onFinalVideoLightboxOpen={() => setFinalVideoLightboxOpen(true)}
          showMobileSelect={isGenerationsPaneLocked && isMobile}
          isSelectedForAddition={isSelectedForAddition}
          onSelectShotForAddition={handleSelectShotForAddition}
          onGenerate={() => setIsImageGenModalOpen(true)}
        />
      </div>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Shot</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete shot "<span className="preserve-case">{shot.name}</span>"? This will permanently remove the shot and all its associated data. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex items-center gap-x-2 py-2">
            <Checkbox
              id="skip-confirmation"
              checked={skipConfirmationChecked}
              onCheckedChange={(checked) => setSkipConfirmationChecked(checked === true)}
            />
            <label
              htmlFor="skip-confirmation"
              className="text-sm text-muted-foreground cursor-pointer select-none"
            >
              Don't ask for confirmation
            </label>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteShotMutation.isPending}
            >
              {deleteShotMutation.isPending ? 'Deleting...' : 'Delete Shot'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {isVideoModalOpen && (
        <VideoGenerationModal
          isOpen={isVideoModalOpen}
          onClose={() => setVideoModalOpen(false)}
          shot={shot}
          defaultTopOpen={false}
          defaultFinalVideoOpen={Boolean(finalVideo)}
          defaultBottomOpen={true}
        />
      )}

      {isImageGenModalOpen && (
        <ImageGenerationModal
          isOpen={isImageGenModalOpen}
          onClose={() => setIsImageGenModalOpen(false)}
          initialShotId={shot.id}
        />
      )}

      {isFinalVideoLightboxOpen && finalVideoRow && (
        <MediaLightbox
          media={finalVideoRow}
          variantFetchGenerationIdOverride={finalVideo.variantFetchGenerationId ?? undefined}
          onClose={() => setFinalVideoLightboxOpen(false)}
          navigation={{
            showNavigation: false,
            hasNext: false,
            hasPrevious: false,
          }}
          features={{
            showImageEditTools: false,
            showDownload: true,
          }}
          actions={{ starred: false }}
          shotId={shot.id}
        />
      )}
    </>
  );
};
