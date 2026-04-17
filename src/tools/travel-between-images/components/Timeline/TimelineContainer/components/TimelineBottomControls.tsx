import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/primitives/label';
import { Slider } from '@/shared/components/ui/slider';
import { Plus } from 'lucide-react';
import { framesToSeconds } from '@/shared/lib/media/videoUtils';
import { useTimelineFps } from '../../TimelineMediaContext';

export interface TimelineBottomControlsProps {
  resetGap: number;
  setResetGap: (value: number) => void;
  maxGap: number;
  onReset: () => void;
  onFileDrop?: (files: File[], targetFrame?: number) => Promise<void>;
  isUploadingImage: boolean;
  uploadProgress: number;
  readOnly?: boolean;
  hasNoImages?: boolean;
  zoomLevel: number;
  pushMode?: 'right' | 'left' | null;
  showDragHint?: boolean;
}

const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);

/** Bottom controls overlay with gap slider, reset button, and add images button */
export const TimelineBottomControls: React.FC<TimelineBottomControlsProps> = ({
  resetGap,
  setResetGap,
  maxGap,
  onReset,
  onFileDrop,
  isUploadingImage,
  uploadProgress,
  readOnly = false,
  hasNoImages = false,
  zoomLevel,
  pushMode,
  showDragHint = false,
}) => {
  const timelineFps = useTimelineFps();
  return (
    <div
      className="absolute bottom-4 left-0 z-30 flex items-center justify-between pointer-events-none px-8"
      style={{
        width: "100%",
        maxWidth: "100vw",
        bottom: zoomLevel > 1 ? '1.6rem' : '1rem'
      }}
    >
      {/* Bottom-left: Gap control and Reset button */}
      <div
        className={`flex items-center gap-2 w-fit pointer-events-auto bg-background/95 backdrop-blur-sm px-2 py-1 rounded shadow-md border border-border/50 ${hasNoImages ? 'opacity-30 blur-[0.5px]' : ''}`}
      >
        {/* Gap to reset */}
        <div className="flex items-center gap-1.5">
          <Label className="text-xs text-muted-foreground whitespace-nowrap">Gap: {framesToSeconds(resetGap, timelineFps)}</Label>
          <Slider
            value={resetGap}
            onValueChange={readOnly ? undefined : (value) => setResetGap(value)}
            min={1}
            max={maxGap}
            step={1}
            className="w-24 h-4"
            disabled={readOnly}
          />
        </div>

        {/* Reset button */}
        <Button
          variant="outline"
          size="sm"
          onClick={readOnly ? undefined : onReset}
          disabled={readOnly}
          className="h-7 text-xs px-2"
        >
          Reset
        </Button>
      </div>

      {/* Center: Modifier key hints during drag */}
      {showDragHint ? (
        <div className="flex gap-3 text-xs text-muted-foreground/70 select-none">
          <span className={pushMode === 'left' ? 'text-foreground font-medium' : ''}>
            {isMac ? '⌥' : 'Alt'} Pull left
          </span>
          <span className="text-muted-foreground/40">·</span>
          <span className={pushMode === 'right' ? 'text-foreground font-medium' : ''}>
            {isMac ? '⌘' : 'Ctrl'} Push right
          </span>
        </div>
      ) : <div />}

      {/* Bottom-right: Add Images button with progress */}
      {onFileDrop ? (
        <div
          className={`pointer-events-auto ${hasNoImages ? 'opacity-30 blur-[0.5px]' : ''}`}
        >
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              if (files.length > 0) {
                onFileDrop(files);
                e.target.value = '';
              }
            }}
            className="hidden"
            id="timeline-image-upload"
            disabled={isUploadingImage || readOnly}
          />
          {isUploadingImage ? (
            <div className="flex flex-col gap-1.5 min-w-[120px]">
              <div className="text-xs text-muted-foreground">
                Uploading... {Math.round(uploadProgress)}%
              </div>
              <div className="w-full bg-muted rounded-full h-1.5">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all duration-200"
                  style={{ width: `${Math.round(uploadProgress)}%` }}
                />
              </div>
            </div>
          ) : (
            <Label htmlFor={readOnly ? undefined : "timeline-image-upload"} className={`m-0 ${readOnly ? 'cursor-not-allowed pointer-events-none' : 'cursor-pointer'}`}>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs px-3 sm:px-2 lg:px-3"
                disabled={readOnly}
                asChild
              >
                <span className="flex items-center gap-1.5">
                  <Plus className="h-3.5 w-3.5" />
                  <span className="sm:hidden lg:inline">Add Images</span>
                </span>
              </Button>
            </Label>
          )}
        </div>
      ) : <div />}
    </div>
  );
};
