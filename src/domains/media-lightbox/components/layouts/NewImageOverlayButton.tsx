/**
 * NewImageOverlayButton - Creates a standalone image from current variant
 *
 * Shows at top-left of the lightbox for images (not videos).
 * Promotes the current variant to a new generation.
 */

import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { Plus, Check, Loader2 } from 'lucide-react';

interface NewImageOverlayButtonProps {
  isVideo: boolean;
  readOnly: boolean;
  activeVariantId: string | undefined;
  primaryVariantId: string | undefined;
  selectedProjectId: string | null;
  isPromoting: boolean;
  promoteSuccess: boolean;
  onPromote: (variantId: string) => void;
}

export const NewImageOverlayButton: React.FC<NewImageOverlayButtonProps> = ({
  isVideo,
  readOnly,
  activeVariantId,
  primaryVariantId,
  selectedProjectId,
  isPromoting,
  promoteSuccess,
  onPromote,
}) => {
  // Only show for images, not videos
  if (isVideo || readOnly) {
    return null;
  }

  const variantId = activeVariantId || primaryVariantId;
  const isDisabled = isPromoting || promoteSuccess || !selectedProjectId || !variantId;

  return (
    <div
      className="absolute top-4 left-4 z-[70] select-none"
      onClick={(e) => e.stopPropagation()}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              if (variantId) {
                onPromote(variantId);
              }
            }}
            disabled={isDisabled}
            className={`text-white ${
              promoteSuccess
                ? 'bg-green-500/90 hover:bg-green-500/90'
                : 'bg-black/50 hover:bg-black/70'
            }`}
          >
            {isPromoting ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
            ) : promoteSuccess ? (
              <Check className="w-4 h-4 mr-1.5" />
            ) : (
              <Plus className="w-4 h-4 mr-1.5" />
            )}
            {promoteSuccess ? 'Created' : 'New image'}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          Create a standalone image from this variant
        </TooltipContent>
      </Tooltip>
    </div>
  );
};
