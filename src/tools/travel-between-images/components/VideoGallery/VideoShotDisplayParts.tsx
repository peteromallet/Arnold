import React, { useState } from 'react';
import type { GenerationRow } from '@/domains/generation/types';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Pencil, Trash2, Check, X, Copy, GripVertical, Loader2, Video, ChevronDown, ChevronUp, Images, Sparkles, Eye, EyeOff } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { getDisplayUrl } from '@/shared/lib/media/mediaUrl';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { HoverScrubVideo } from '@/shared/components/media/HoverScrubVideo';
import type { ShotFinalVideo } from '../../hooks/video/useShotFinalVideos';

interface ActionButtonsRowProps {
  isTempShot: boolean;
  displayImagesCount: number;
  isEditingName: boolean;
  dragHandleProps?: {
    disabled?: boolean;
    [key: string]: unknown;
  };
  dragDisabledReason?: string;
  duplicateIsPending: boolean;
  duplicateWithVideosIsPending: boolean;
  isHidden?: boolean;
  onVideoClick: () => void;
  onEditName: (e?: React.MouseEvent) => void;
  onDuplicate: (e?: React.MouseEvent) => void;
  onDuplicateWithVideos: (e?: React.MouseEvent) => void;
  onToggleHidden?: (e?: React.MouseEvent) => void;
  onDelete: (e?: React.MouseEvent) => void;
}

const ActionButtonsRow: React.FC<ActionButtonsRowProps> = ({
  isTempShot,
  displayImagesCount,
  isEditingName,
  dragHandleProps,
  dragDisabledReason,
  duplicateIsPending,
  duplicateWithVideosIsPending,
  isHidden = false,
  onVideoClick,
  onEditName,
  onDuplicate,
  onDuplicateWithVideos,
  onToggleHidden,
  onDelete,
}) => (
  <div className="flex items-center gap-x-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
    {isTempShot && (
      <div className="flex items-center gap-1 text-xs text-muted-foreground mr-2">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>Saving...</span>
      </div>
    )}
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation();
              if (displayImagesCount > 0 && !isTempShot) {
                onVideoClick();
              }
            }}
            disabled={displayImagesCount === 0 || isTempShot}
            className={`h-8 w-8 ${
              displayImagesCount === 0 || isTempShot
                ? 'text-zinc-400 cursor-not-allowed opacity-50'
                : 'text-violet-600 hover:text-violet-500 hover:bg-violet-100 dark:hover:bg-violet-950'
            }`}
          >
            <Video className="h-5 w-5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{isTempShot ? 'Saving...' : displayImagesCount === 0 ? 'Add images to generate video' : 'Generate Video'}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
    {dragHandleProps && (
      (dragHandleProps.disabled || isTempShot) && (dragDisabledReason || isTempShot) ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 cursor-not-allowed opacity-50"
                  disabled={true}
                >
                  <GripVertical className="h-4 w-4" />
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              <p>{isTempShot ? 'Saving...' : dragDisabledReason}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 cursor-grab active:cursor-grabbing"
                disabled={dragHandleProps.disabled}
                {...dragHandleProps}
              >
                <GripVertical className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Drag to reorder</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )
    )}
    {!isEditingName && (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={onEditName} className="h-8 w-8" disabled={isTempShot}>
              <Pencil className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>{isTempShot ? 'Saving...' : 'Edit shot name'}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )}
    <div className="group/duplicate relative flex">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onDuplicate}
              className="h-8 w-8"
              disabled={duplicateIsPending || isTempShot}
              aria-label="Duplicate shot"
              title="Duplicate shot"
            >
              {duplicateIsPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>{isTempShot ? 'Saving...' : duplicateIsPending ? 'Duplicating...' : 'Duplicate shot'}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onDuplicateWithVideos}
              className="absolute -right-1 -top-1 z-10 h-5 w-5 rounded-full bg-background/90 opacity-0 shadow-sm transition-opacity focus:opacity-100 group-hover/duplicate:opacity-100"
              disabled={duplicateIsPending || duplicateWithVideosIsPending || isTempShot}
              aria-label="Duplicate with videos"
              title="Duplicate with videos"
            >
              {duplicateWithVideosIsPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Video className="h-3 w-3" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>{isTempShot ? 'Saving...' : duplicateWithVideosIsPending ? 'Duplicating with videos...' : 'Duplicate with videos'}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
    {onToggleHidden && (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation();
                onToggleHidden(e);
              }}
              className="h-8 w-8"
              disabled={isTempShot}
              aria-label={isHidden ? 'Unhide shot' : 'Hide shot'}
            >
              {isHidden ? (
                <Eye className="h-4 w-4" />
              ) : (
                <EyeOff className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>{isTempShot ? 'Saving...' : isHidden ? 'Unhide shot' : 'Hide shot'}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )}
    {isHidden && (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={onDelete} className="text-destructive hover:text-destructive-foreground hover:bg-destructive h-8 w-8" disabled={isTempShot}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>{isTempShot ? 'Saving...' : 'Delete shot'}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )}
  </div>
);

const IMAGES_PER_ROW = 3;

interface ThumbnailMosaicProps {
  displayImages: GenerationRow[];
  pendingUploads: number;
  imagesOverlay?: React.ReactNode;
  finalVideo?: ShotFinalVideo;
  showVideo: boolean;
  onShowVideoChange: (show: boolean) => void;
  projectAspectRatio?: string;
  dropLoadingState: 'idle' | 'loading' | 'success';
  onFinalVideoLightboxOpen: () => void;
  showMobileSelect: boolean;
  isSelectedForAddition: boolean;
  onSelectShotForAddition: (e: React.MouseEvent) => void;
  onGenerate?: () => void;
}

const ThumbnailMosaic: React.FC<ThumbnailMosaicProps> = ({
  displayImages,
  pendingUploads,
  imagesOverlay,
  finalVideo,
  showVideo,
  onShowVideoChange,
  projectAspectRatio,
  dropLoadingState,
  onFinalVideoLightboxOpen,
  showMobileSelect,
  isSelectedForAddition,
  onSelectShotForAddition,
  onGenerate,
}) => {
  const [isImagesExpanded, setIsImagesExpanded] = useState(false);

  const totalImageCount = displayImages.length + pendingUploads;
  const hasMultipleRows = totalImageCount > IMAGES_PER_ROW;
  const collapsedRealImages = Math.min(displayImages.length, IMAGES_PER_ROW);
  const collapsedSkeletonCount = !isImagesExpanded
    ? Math.min(pendingUploads, IMAGES_PER_ROW - collapsedRealImages)
    : 0;
  const emptyPlaceholderCount = !isImagesExpanded
    ? Math.max(0, IMAGES_PER_ROW - collapsedRealImages - collapsedSkeletonCount)
    : 0;

  return (
    <div className="flex-grow relative">
      {imagesOverlay}

      {finalVideo && showVideo ? (
        <div className="relative group/video">
          <div
            className="rounded border border-border bg-muted shadow-sm overflow-hidden cursor-pointer"
            style={{
              aspectRatio: projectAspectRatio
                ? projectAspectRatio.replace(':', '/')
                : '16/9',
            }}
            onClick={(e) => {
              e.stopPropagation();
              onFinalVideoLightboxOpen();
            }}
          >
            <HoverScrubVideo
              src={finalVideo.location}
              poster={finalVideo.thumbnailUrl ?? undefined}
              loadOnDemand
              preload="metadata"
              className="w-full h-full"
              videoClassName="object-cover pointer-events-none"
            />
          </div>
          <button
            className="absolute bottom-1 left-1 text-xs bg-black/60 hover:bg-black/80 text-white px-2 py-0.5 rounded flex items-center gap-1 z-10"
            onClick={(e) => {
              e.stopPropagation();
              onShowVideoChange(false);
            }}
          >
            <Images className="w-3 h-3" />
            Shot images
          </button>
        </div>
      ) : (
        <>
          {dropLoadingState !== 'idle' && displayImages.length > IMAGES_PER_ROW && !isImagesExpanded && (
            <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
              <div
                className={cn(
                  'px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 shadow-lg',
                  dropLoadingState === 'loading' && 'bg-primary text-primary-foreground',
                  dropLoadingState === 'success' && 'bg-green-600 text-white'
                )}
              >
                {dropLoadingState === 'loading' && (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Adding...
                  </>
                )}
                {dropLoadingState === 'success' && (
                  <>
                    <Check className="h-4 w-4" />
                    Added
                  </>
                )}
              </div>
            </div>
          )}
          <div className="grid grid-cols-3 gap-2 relative">
            {(isImagesExpanded ? displayImages : displayImages.slice(0, IMAGES_PER_ROW)).map((image, index) => (
              <img
                key={`${image.thumbUrl || image.imageUrl || image.location || 'img'}-${index}`}
                src={getDisplayUrl(image.thumbUrl || image.imageUrl || image.location)}
                alt={`Shot image ${index + 1}`}
                className="w-full aspect-square object-cover rounded border border-border bg-muted shadow-sm"
                title={`Image ${index + 1}`}
              />
            ))}

            {collapsedSkeletonCount > 0 && Array.from({ length: collapsedSkeletonCount }).map((_, index) => (
              <div
                key={`pending-collapsed-${index}`}
                className="w-full aspect-square rounded border-2 border-dashed border-primary/30 bg-primary/5 flex items-center justify-center"
              >
                <Loader2 className="h-5 w-5 text-primary/60 animate-spin" />
              </div>
            ))}

            {emptyPlaceholderCount > 0 && Array.from({ length: emptyPlaceholderCount }).map((_, index) => (
              <div
                key={`empty-${index}`}
                className="w-full aspect-square rounded border-2 border-dashed border-border"
              />
            ))}

            {pendingUploads > 0 && isImagesExpanded && Array.from({ length: pendingUploads }).map((_, index) => (
              <div
                key={`pending-${index}`}
                className="w-full aspect-square rounded border-2 border-dashed border-primary/30 bg-primary/5 flex items-center justify-center"
              >
                <Loader2 className="h-5 w-5 text-primary/60 animate-spin" />
              </div>
            ))}

            {/* Bottom overlay buttons */}
            <div className="absolute bottom-1 right-1 flex items-center gap-1 z-10">
              {onGenerate && (
                <button
                  className="text-xs bg-black/60 hover:bg-black/80 text-white p-1 rounded flex items-center"
                  onClick={(e) => {
                    e.stopPropagation();
                    onGenerate();
                  }}
                >
                  <Sparkles className="w-3 h-3" />
                </button>
              )}

              {hasMultipleRows && !isImagesExpanded && (
                <button
                  className="text-xs bg-black/60 hover:bg-black/80 text-white px-2 py-0.5 rounded flex items-center gap-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsImagesExpanded(true);
                  }}
                >
                  Show All ({totalImageCount}) <ChevronDown className="w-3 h-3" />
                </button>
              )}

              {isImagesExpanded && hasMultipleRows && (
                <button
                  className="text-xs bg-black/60 hover:bg-black/80 text-white px-2 py-0.5 rounded flex items-center gap-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsImagesExpanded(false);
                  }}
                >
                  Hide <ChevronUp className="w-3 h-3" />
                </button>
              )}
            </div>

            {finalVideo && !showVideo && (
              <button
                className="absolute bottom-1 left-1 text-xs bg-black/60 hover:bg-black/80 text-white px-2 py-0.5 rounded flex items-center gap-1 z-10"
                onClick={(e) => {
                  e.stopPropagation();
                  onShowVideoChange(true);
                }}
              >
                <Video className="w-3 h-3" />
                Final video
              </button>
            )}
          </div>
        </>
      )}

      {showMobileSelect && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={isSelectedForAddition ? 'default' : 'secondary'}
                size="sm"
                onClick={onSelectShotForAddition}
                className={`absolute bottom-1 left-1 h-7 px-2 text-xs shadow-sm z-10 transition-all duration-200 ${
                  isSelectedForAddition
                    ? 'bg-green-600 hover:bg-green-700 text-white border-green-600'
                    : 'bg-background/90 hover:bg-background border'
                }`}
              >
                {isSelectedForAddition ? 'Selected' : 'Select'}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{isSelectedForAddition ? 'Images will be added to this shot' : 'Add images to this shot'}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
};

interface ShotMetadataProps {
  displayName: string;
  isEditingName: boolean;
  editableName: string;
  onEditableNameChange: (value: string) => void;
  onSaveName: () => void;
  onCancelEdit: () => void;
  generationMode?: string;
}

export const ShotMetadata: React.FC<ShotMetadataProps> = ({
  displayName,
  isEditingName,
  editableName,
  onEditableNameChange,
  onSaveName,
  onCancelEdit,
  generationMode,
}) => {
  if (!isEditingName) {
    return (
      <div className="flex items-center gap-2 flex-grow mr-2 min-w-0">
        <h3 className="text-xl font-light group-hover:text-primary/80 transition-colors duration-300 truncate preserve-case">
          {displayName}
        </h3>
        {generationMode && (
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70 bg-muted/50 px-1.5 py-0.5 rounded shrink-0">
            {generationMode === 'by-pair' ? 'pair' : generationMode}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 flex-grow" onClick={(e) => e.stopPropagation()}>
      <Input
        value={editableName}
        onChange={(e) => onEditableNameChange(e.target.value)}
        onBlur={onSaveName}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSaveName();
          if (e.key === 'Escape') onCancelEdit();
        }}
        className="!text-xl font-light h-auto py-0 px-2 border-0 bg-transparent shadow-none focus:ring-0 focus:border-0"
        autoFocus
        maxLength={30}
      />
      <Button variant="ghost" size="icon" onClick={(e) => {
        e.stopPropagation();
        onSaveName();
      }} className="h-9 w-9">
        <Check className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" onClick={(e) => {
        e.stopPropagation();
        onCancelEdit();
      }} className="h-9 w-9">
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
};

interface ShotControlsProps {
  isTempShot: boolean;
  displayImagesCount: number;
  isEditingName: boolean;
  dragHandleProps?: {
    disabled?: boolean;
    [key: string]: unknown;
  };
  dragDisabledReason?: string;
  duplicateIsPending: boolean;
  duplicateWithVideosIsPending: boolean;
  isHidden?: boolean;
  onVideoClick: () => void;
  onEditName: (e?: React.MouseEvent) => void;
  onDuplicate: (e?: React.MouseEvent) => void;
  onDuplicateWithVideos: (e?: React.MouseEvent) => void;
  onToggleHidden?: (e?: React.MouseEvent) => void;
  onDelete: (e?: React.MouseEvent) => void;
}

export const ShotControls: React.FC<ShotControlsProps> = (props) => (
  <ActionButtonsRow {...props} />
);

interface ShotPreviewProps {
  displayImages: GenerationRow[];
  pendingUploads: number;
  imagesOverlay?: React.ReactNode;
  finalVideo?: ShotFinalVideo;
  showVideo: boolean;
  onShowVideoChange: (show: boolean) => void;
  projectAspectRatio?: string;
  dropLoadingState: 'idle' | 'loading' | 'success';
  onFinalVideoLightboxOpen: () => void;
  showMobileSelect: boolean;
  isSelectedForAddition: boolean;
  onSelectShotForAddition: (e: React.MouseEvent) => void;
  onGenerate?: () => void;
}

export const ShotPreview: React.FC<ShotPreviewProps> = (props) => (
  <ThumbnailMosaic {...props} />
);
