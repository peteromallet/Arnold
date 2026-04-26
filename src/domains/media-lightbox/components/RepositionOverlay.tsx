/**
 * RepositionOverlay
 *
 * Renders the visual overlays for reposition mode:
 * - Dashed bounds outline with corner indicators and center crosshair
 * - Zoom +/- buttons
 * - Corner rotation drag handles
 *
 * Extracted from MediaDisplayWithCanvas to reduce its size.
 */

import React from 'react';
import { RotateCw, Plus, Minus } from 'lucide-react';

interface RepositionOverlayProps {
  /** Display dimensions of the image */
  displaySize: { width: number; height: number };
  /** Offset of the image within its container */
  imageOffset: { left: number; top: number };
  /** CSS transform applied to the image */
  repositionTransformStyle?: React.CSSProperties;
  /** Current scale value */
  repositionScale: number;
  /** Layout variant */
  variant: 'desktop-side-panel' | 'mobile-stacked' | 'regular-centered';
  /** Ref for the handles overlay (used by touch gesture system) */
  handlesOverlayRef: React.RefObject<HTMLDivElement>;
  /** Scale change handler (null = zoom buttons hidden) */
  onRepositionScaleChange: ((value: number) => void) | undefined;
  /** Rotation change handler (null = rotation handles hidden) */
  onRepositionRotationChange: ((value: number) => void) | undefined;
  /** Corner rotation pointer handlers */
  handleCornerRotateStart: (e: React.PointerEvent) => void;
  handleCornerRotateMove: (e: React.PointerEvent) => void;
  handleCornerRotateEnd: (e: React.PointerEvent) => void;
}

/** A single corner rotation drag handle */
const RotationHandle: React.FC<{
  position: string;
  rotation?: string;
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  onPointerCancel: (e: React.PointerEvent) => void;
}> = ({ position, rotation, onPointerDown, onPointerMove, onPointerUp, onPointerCancel }) => (
  <div
    className={`absolute ${position} w-8 h-8 flex items-center justify-center cursor-grab active:cursor-grabbing`}
    style={{
      // Required because RepositionOverlay.tsx:114 sets the handles overlay wrapper to pointer-events-none.
      pointerEvents: 'auto',
      ...(rotation ? { transform: rotation } : {}),
    }}
    onPointerDown={onPointerDown}
    onPointerMove={onPointerMove}
    onPointerUp={onPointerUp}
    onPointerCancel={onPointerCancel}
    title="Drag to rotate"
  >
    <RotateCw className="h-4 w-4 text-blue-400 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]" />
  </div>
);

export const RepositionOverlay: React.FC<RepositionOverlayProps> = ({
  displaySize,
  imageOffset,
  repositionTransformStyle,
  repositionScale,
  variant,
  handlesOverlayRef,
  onRepositionScaleChange,
  onRepositionRotationChange,
  handleCornerRotateStart,
  handleCornerRotateMove,
  handleCornerRotateEnd,
}) => {
  if (displaySize.width <= 0 || displaySize.height <= 0) return null;

  const pointerHandlers = {
    onPointerDown: handleCornerRotateStart,
    onPointerMove: handleCornerRotateMove,
    onPointerUp: handleCornerRotateEnd,
    onPointerCancel: handleCornerRotateEnd,
  };

  return (
    <>
      {/* Original Image Bounds Outline - Shows the canvas/crop boundary */}
      <div
        className={`absolute pointer-events-none z-[45] border-2 border-dashed border-blue-500/70 ring-2 ring-inset ring-blue-500/20 ${variant === 'regular-centered' ? 'rounded' : ''}`}
        style={{
          left: imageOffset.left,
          top: imageOffset.top,
          width: displaySize.width,
          height: displaySize.height,
        }}
      >
        {/* Corner indicators */}
        <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-blue-500" />
        <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-blue-500" />
        <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-blue-500" />
        <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-blue-500" />

        {/* Center crosshair */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="w-6 h-0.5 bg-blue-500/50 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          <div className="w-0.5 h-6 bg-blue-500/50 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
        </div>
      </div>

      {/* Rotation corner handles + zoom buttons - follows the transformed image */}
      <div
        ref={handlesOverlayRef}
        className="absolute z-[46] pointer-events-none"
        style={{
          left: imageOffset.left,
          top: imageOffset.top,
          width: displaySize.width,
          height: displaySize.height,
          transform: repositionTransformStyle?.transform,
          transformOrigin: 'center center',
        }}
      >
        {/* Zoom +/- buttons */}
        {onRepositionScaleChange && (
          <div
            className="absolute left-1/2 -translate-x-1/2 flex items-center rounded-full bg-white/60 border border-black/30 px-0.5 py-0.5"
            style={{
              // Required because RepositionOverlay.tsx:114 sets the handles overlay wrapper to pointer-events-none.
              pointerEvents: 'auto',
              top: '5%',
            }}
          >
            <div
              className="w-7 h-7 flex items-center justify-center cursor-pointer rounded-full hover:bg-white/20 transition-colors"
              onClick={() => repositionScale > 0.25 && onRepositionScaleChange(Math.max(0.25, repositionScale - 0.05))}
              title="Zoom out"
            >
              <Minus className="h-4 w-4 text-blue-400" />
            </div>
            <div className="w-px h-4 bg-black/30" />
            <div
              className="w-7 h-7 flex items-center justify-center cursor-pointer rounded-full hover:bg-white/20 transition-colors"
              onClick={() => repositionScale < 2.0 && onRepositionScaleChange(Math.min(2.0, repositionScale + 0.05))}
              title="Zoom in"
            >
              <Plus className="h-4 w-4 text-blue-400" />
            </div>
          </div>
        )}

        {/* Corner rotation handles */}
        {onRepositionRotationChange && (
          <>
            <RotationHandle position="-top-4 -left-4" rotation="rotate(-90deg)" {...pointerHandlers} />
            <RotationHandle position="-top-4 -right-4" {...pointerHandlers} />
            <RotationHandle position="-bottom-4 -left-4" rotation="rotate(180deg)" {...pointerHandlers} />
            <RotationHandle position="-bottom-4 -right-4" rotation="rotate(90deg)" {...pointerHandlers} />
          </>
        )}
      </div>
    </>
  );
};
