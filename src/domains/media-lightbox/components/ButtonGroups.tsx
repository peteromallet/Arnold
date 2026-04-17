import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import {
  Star,
  Download,
  CheckCircle,
  Loader2,
  ImagePlus,
  Trash2,
  Film,
  ArrowRight,
} from 'lucide-react';
import {
  useLightboxCoreSafe,
  useLightboxMediaSafe,
} from '../contexts/LightboxStateContext';
import type { LightboxDeleteHandler } from '../types';

// ============================================================================
// TOP RIGHT CONTROLS - Download & Delete
// ============================================================================

interface TopRightControlsProps {
  showDownload: boolean;
  handleDownload?: () => Promise<void>;
  isDownloading?: boolean;
  onDelete?: LightboxDeleteHandler;
  handleDelete?: () => Promise<void>;
  isDeleting?: string | null;
}

export const TopRightControls: React.FC<TopRightControlsProps> = ({
  showDownload,
  handleDownload,
  isDownloading,
  onDelete,
  handleDelete,
  isDeleting,
}) => {
  // Get shared state from context
  const { readOnly, actualGenerationId } = useLightboxCoreSafe();
  const { isVideo } = useLightboxMediaSafe();

  return (
    <div className="absolute top-4 right-4 flex items-center gap-x-2 z-[70]">
      {/* Download Button - Keep visible in edit mode */}
      {/* Guard: only render if handleDownload is provided (parent must supply it) */}
      {showDownload && handleDownload && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                void handleDownload();
              }}
              disabled={isDownloading}
              className="bg-black/50 hover:bg-black/70 text-white"
            >
              {isDownloading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {isDownloading ? 'Downloading...' : `Download ${isVideo ? 'video' : 'image'}`}
          </TooltipContent>
        </Tooltip>
      )}

      {/* Delete Button - Keep visible in edit mode */}
      {onDelete && !readOnly && !isVideo && handleDelete && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="destructive"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                void handleDelete();
              }}
              disabled={isDeleting === actualGenerationId}
              className="bg-red-600/80 hover:bg-red-600 text-white"
            >
              {isDeleting === actualGenerationId ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>Delete from timeline</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
};

// ============================================================================
// BOTTOM LEFT CONTROLS - Star button
// ============================================================================

interface BottomLeftControlsProps {
  localStarred?: boolean;
  handleToggleStar?: () => void;
  toggleStarPending?: boolean;
}

export const BottomLeftControls: React.FC<BottomLeftControlsProps> = ({
  localStarred,
  handleToggleStar,
  toggleStarPending,
}) => {
  const { readOnly } = useLightboxCoreSafe();

  // Star button in bottom left
  if (readOnly || !handleToggleStar) return null;

  return (
    <div className="absolute bottom-4 left-4 flex items-center gap-x-2 z-10">
      <Button
        variant="secondary"
        size="sm"
        onClick={handleToggleStar}
        disabled={toggleStarPending}
        className="transition-colors bg-black/50 hover:bg-black/70 text-white"
      >
        <Star className={`h-4 w-4 ${localStarred ? 'fill-current' : ''}`} />
      </Button>
    </div>
  );
};

// ============================================================================
// BOTTOM RIGHT CONTROLS - Add to References / Add to Join Clips
// ============================================================================

interface BottomRightControlsProps {
  isAddingToReferences?: boolean;
  addToReferencesSuccess?: boolean;
  handleAddToReferences?: () => Promise<void>;
  showAddToReferences?: boolean;
  // Add to Join Clips
  handleAddToJoin?: () => void;
  isAddingToJoin?: boolean;
  addToJoinSuccess?: boolean;
  onGoToJoin?: () => void;
}

export const BottomRightControls: React.FC<BottomRightControlsProps> = ({
  isAddingToReferences = false,
  addToReferencesSuccess = false,
  handleAddToReferences,
  showAddToReferences = true,
  handleAddToJoin,
  isAddingToJoin,
  addToJoinSuccess,
  onGoToJoin,
}) => {
  // Get shared state from context
  const { readOnly, selectedProjectId } = useLightboxCoreSafe();
  const { isVideo } = useLightboxMediaSafe();

  // Keep visible in edit mode - users can add to references while editing
  return (
    <div className="absolute bottom-4 right-4 flex items-center gap-x-2 z-10">
      {/* Add to References Button */}
      {showAddToReferences && !readOnly && !isVideo && selectedProjectId && handleAddToReferences && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleAddToReferences}
              disabled={isAddingToReferences || addToReferencesSuccess}
              className={`transition-colors ${
                addToReferencesSuccess
                  ? 'bg-green-600/80 hover:bg-green-600 text-white'
                  : 'bg-black/50 hover:bg-black/70 text-white'
              }`}
            >
              {isAddingToReferences ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : addToReferencesSuccess ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <ImagePlus className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {isAddingToReferences ? 'Adding...' : addToReferencesSuccess ? 'Added!' : 'Add to references'}
          </TooltipContent>
        </Tooltip>
      )}

      {/* Add to Join Clips Button (videos only) */}
      {!readOnly && isVideo && handleAddToJoin && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="sm"
              onClick={addToJoinSuccess && onGoToJoin ? onGoToJoin : handleAddToJoin}
              disabled={isAddingToJoin}
              className={`transition-colors ${
                addToJoinSuccess
                  ? 'bg-green-600/80 hover:bg-green-600 text-white'
                  : 'bg-black/50 hover:bg-black/70 text-white'
              }`}
            >
              {isAddingToJoin ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : addToJoinSuccess ? (
                <ArrowRight className="h-4 w-4" />
              ) : (
                <Film className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {isAddingToJoin ? 'Adding...' : addToJoinSuccess ? 'Added! Go to Join Clips' : 'Add to Join Clips'}
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );
};
