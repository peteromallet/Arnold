import React, { useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { getDisplayUrl } from '@/shared/lib/media/mediaUrl';
import { useProgressiveImage } from '@/shared/hooks/ui-image/useProgressiveImage';
import { isProgressiveLoadingEnabled } from '@/shared/settings/progressiveLoading';
import { useMarkVariantViewed } from '@/shared/hooks/variants/useMarkVariantViewed';
import { useIsTouchDevice } from '@/shared/hooks/mobile';
import { INTERACTION_TIMING } from '@/shared/lib/interactions/timing';
import { framesToSeconds } from '@/shared/lib/media/videoUtils';
import { useTimelineFps } from './TimelineMediaContext';
import { getTimelineItemAspectRatioStyle, getTimelineItemPosition } from './TimelineItem.helpers';
import { TimelineItemActionButtons } from './TimelineItemActionButtons';
import type { TimelineItemProps } from './TimelineItem.types';
import { VariantDropOverlay } from '@/shared/components/VariantDropOverlay';
import { useImageVariantDrop } from '@/shared/hooks/dnd/useImageVariantDrop';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';

const SCROLL_THRESHOLD = 10;

const TimelineItem: React.FC<TimelineItemProps> = ({
  image,
  framePosition,
  layout,
  interaction,
  actions,
  selection,
  presentation,
}) => {
  const timelineFps = useTimelineFps();
  const { timelineWidth, fullMinFrames, fullRange } = layout;
  const {
    isDragging,
    isSwapTarget,
    dragOffset,
    onMouseDown,
    onDoubleClick,
    onMobileTap,
    currentDragFrame,
    originalFramePos,
    onPrefetch,
  } = interaction;
  const {
    onDelete,
    onDuplicate,
    onVariantDrop,
    onVariantDropTargetChange,
    onInpaintClick,
    duplicatingImageId,
    duplicateSuccessImageId,
  } = actions ?? {};
  const {
    isSelected = false,
    onSelectionClick,
  } = selection ?? {};
  const {
    shouldLoad = true,
    projectAspectRatio,
    readOnly = false,
    isJustDropped = false,
  } = presentation ?? {};

  const [isHovered, setIsHovered] = useState(false);
  const [showDropEffect, setShowDropEffect] = useState(false);

  const { markAllViewed } = useMarkVariantViewed();
  const isTouchDevice = useIsTouchDevice();

  const handleMarkAllVariantsViewed = useCallback(() => {
    if (image.generation_id) {
      markAllViewed(image.generation_id);
    }
  }, [image.generation_id, markAllViewed]);

  useEffect(() => {
    if (!isJustDropped) {
      return;
    }

    setShowDropEffect(true);
    const timer = setTimeout(() => {
      setShowDropEffect(false);
    }, INTERACTION_TIMING.timelineDropHighlightMs);
    return () => clearTimeout(timer);
  }, [isJustDropped]);

  const isElevated = isHovered || showDropEffect || isDragging || isSelected;
  const imageKey = image.id;
  const generationId = getGenerationId(image as {
    generation_id?: string | null;
    id?: string | null;
    metadata?: Record<string, unknown>;
  });

  const buttonClickedRef = useRef(false);
  const mouseDownPosRef = useRef<{ x: number; y: number } | null>(null);
  const touchStartPosRef = useRef<{ x: number; y: number } | null>(null);

  const scheduleButtonClickReset = useCallback(() => {
    setTimeout(() => {
      buttonClickedRef.current = false;
    }, INTERACTION_TIMING.minimalDeferralMs);
  }, []);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (readOnly) {
      return;
    }
    const touch = e.touches[0];
    touchStartPosRef.current = { x: touch.clientX, y: touch.clientY };
  }, [readOnly]);

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    if (readOnly || !touchStartPosRef.current) {
      return;
    }

    const touch = e.changedTouches[0];
    const deltaX = Math.abs(touch.clientX - touchStartPosRef.current.x);
    const deltaY = Math.abs(touch.clientY - touchStartPosRef.current.y);
    touchStartPosRef.current = null;

    if (deltaX > SCROLL_THRESHOLD || deltaY > SCROLL_THRESHOLD) {
      return;
    }

    const target = e.target as HTMLElement;
    if (target.closest('button')) {
      return;
    }

    if (onSelectionClick) {
      onSelectionClick({ preventDefault: () => {}, stopPropagation: () => {} } as React.MouseEvent);
      return;
    }

    onMobileTap?.();
  }, [readOnly, onSelectionClick, onMobileTap]);

  const aspectRatioStyle = getTimelineItemAspectRatioStyle(image, projectAspectRatio);

  const progressiveEnabled = isProgressiveLoadingEnabled();
  const {
    src: progressiveSrc,
    isThumbShowing,
    isFullLoaded,
    ref: progressiveRef,
  } = useProgressiveImage(
    progressiveEnabled ? image.thumbUrl : null,
    image.imageUrl,
    {
      priority: false,
      lazy: true,
      enabled: progressiveEnabled && shouldLoad,
      crossfadeMs: 180,
    },
  );

  const displayImageUrl = progressiveEnabled && progressiveSrc
    ? progressiveSrc
    : getDisplayUrl(image.thumbUrl || image.imageUrl);

  const handleDeleteClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    e.nativeEvent.stopImmediatePropagation();
    onDelete?.(image.id);
  };

  const handleDuplicateClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    e.nativeEvent.stopImmediatePropagation();
    onDuplicate?.(image.id, framePosition);
  };

  const { leftPercent, displayFrame } = getTimelineItemPosition({
    timelineWidth,
    fullMinFrames,
    fullRange,
    framePosition,
    isDragging,
    dragOffset,
    originalFramePos,
    currentDragFrame,
  });

  const { isVariantDropTarget, activeRegion, dragHandlers } = useImageVariantDrop({
    generationId,
    onVariantDrop: onVariantDrop ?? (async () => {}),
    disabled: readOnly || !onVariantDrop,
    onTargetStateChange: (isActive) => {
      onVariantDropTargetChange?.(isActive ? imageKey : null);
    },
  });

  return (
    <div
      data-item-id={imageKey}
      {...dragHandlers}
      style={{
        position: 'absolute',
        left: `${leftPercent}%`,
        top: '50%',
        transform: `translate(-50%, -50%) ${isElevated ? 'scale(1.15)' : 'scale(1)'}`,
        transition: isDragging ? 'none' : 'transform 0.2s ease-out, opacity 0.2s ease-out, box-shadow 0.2s ease-out',
        opacity: isDragging ? 0.8 : 1,
        zIndex: isElevated ? 20 : 1,
        cursor: isSelected ? 'pointer' : 'move',
        boxShadow: isSelected
          ? '0 0 0 4px rgba(249, 115, 22, 1), 0 0 0 6px rgba(249, 115, 22, 0.3)'
          : (isElevated ? '0 8px 25px rgba(0, 0, 0, 0.15)' : 'none'),
        pointerEvents: 'auto',
      }}
      onMouseDown={(e) => {
        mouseDownPosRef.current = { x: e.clientX, y: e.clientY };

        const target = e.target as HTMLElement;
        const isClickingButton = target.closest('button') || target.closest('[data-click-blocker]');

        if (isClickingButton || buttonClickedRef.current) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }

        onMouseDown?.(e, imageKey);
      }}
      onMouseEnter={() => {
        setIsHovered(true);
        onPrefetch?.();
      }}
      onMouseLeave={() => {
        setIsHovered(false);
      }}
      onClick={(e) => {
        const target = e.target as HTMLElement;
        if (target.closest('button') || target.closest('[data-click-blocker]')) {
          return;
        }

        if (mouseDownPosRef.current) {
          const dx = Math.abs(e.clientX - mouseDownPosRef.current.x);
          const dy = Math.abs(e.clientY - mouseDownPosRef.current.y);
          mouseDownPosRef.current = null;
          if (dx > 5 || dy > 5) {
            return;
          }
        }

        onSelectionClick?.(e);
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        onDoubleClick?.();
      }}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      className={isSwapTarget ? 'ring-4 ring-primary/60' : ''}
    >
      <div className="flex flex-col items-center relative group">
        <div
          className={`relative border-2 ${isDragging ? 'border-primary/50' : 'border-primary'} rounded-lg overflow-hidden group`}
          style={{
            width: '120px',
            maxHeight: '120px',
            transform: isElevated ? 'scale(1.05)' : 'scale(1)',
            transition: isDragging ? 'none' : 'all 0.2s ease-out',
            ...aspectRatioStyle,
          }}
        >
          <VariantDropOverlay
            isVisible={isVariantDropTarget}
            activeRegion={activeRegion}
          />

          <img
            ref={progressiveRef}
            src={shouldLoad ? displayImageUrl : '/placeholder.svg'}
            alt={`Time ${framesToSeconds(displayFrame, timelineFps)}`}
            className={cn(
              'w-full h-full object-cover',
              progressiveEnabled && isThumbShowing && 'opacity-95',
              progressiveEnabled && isFullLoaded && 'opacity-100',
            )}
            draggable={false}
            loading="lazy"
          />

          <TimelineItemActionButtons
            image={image}
            imageKey={imageKey}
            isDragging={isDragging}
            readOnly={readOnly}
            isSelected={isSelected}
            isTouchDevice={isTouchDevice}
            onMobileTap={onMobileTap}
            onInpaintClick={onInpaintClick}
            onDuplicateClick={handleDuplicateClick}
            onDeleteClick={handleDeleteClick}
            duplicatingImageId={duplicatingImageId}
            duplicateSuccessImageId={duplicateSuccessImageId}
            onMarkAllVariantsViewed={handleMarkAllVariantsViewed}
            buttonClickedRef={buttonClickedRef}
            scheduleButtonClickReset={scheduleButtonClickReset}
          />

          <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] leading-none text-center py-0.5 pointer-events-none whitespace-nowrap overflow-hidden">
            <span className="inline-block">{framesToSeconds(displayFrame, timelineFps)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const MemoizedTimelineItem = React.memo(TimelineItem);

export { MemoizedTimelineItem as TimelineItem };
