import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, RefObject } from 'react';
import { Maximize2, RotateCcw } from 'lucide-react';
import {
  hasRenderableBounds,
} from '@/tools/video-editor/lib/render-bounds';
import { useEffectDiagnostic, useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics';
import {
  isTouchTimelineInput,
  type TimelineContextTarget,
  type TimelineDeviceClass,
  type TimelineGestureOwner,
  type TimelineInputModality,
  type TimelineInspectorTarget,
  type TimelineInteractionMode,
} from '@/tools/video-editor/lib/mobile-interaction-model';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';
import {
  clamp,
  getFullBoundsFromVisibleBounds,
  getVisibleBoundsFromCrop,
  getVisibleClipIds,
  MAX_CROP_FRACTION,
  MIN_CLIP_SIZE,
  normalizeCropValues,
  toOverlayStyle,
  type CropValues,
  type OverlayBounds,
  type OverlayLayout,
} from '@/tools/video-editor/lib/overlay-bounds';

interface OverlayEditorProps {
  rows: TimelineRow[];
  meta: Record<string, ClipMeta>;
  registry: ResolvedTimelineConfig['registry'];
  currentTime: number;
  playerContainerRef: RefObject<HTMLDivElement>;
  trackScaleMap: Record<string, number>;
  compositionWidth: number;
  compositionHeight: number;
  selectedClipId: string | null;
  deviceClass: TimelineDeviceClass;
  inputModality: TimelineInputModality;
  interactionMode: TimelineInteractionMode;
  gestureOwner: TimelineGestureOwner;
  onSelectClip: (clipId: string | null) => void;
  onOverlayChange: (actionId: string, patch: Partial<ClipMeta>) => void;
  setInputModalityFromPointerType: (pointerType: string | null | undefined) => TimelineInputModality;
  setGestureOwner: (owner: TimelineGestureOwner) => void;
  setContextTarget: (target: TimelineContextTarget) => void;
  setInspectorTarget: (target: TimelineInspectorTarget) => void;
  onDoubleClickAsset?: (assetKey: string, clipId?: string) => void;
}

type DragMode =
  | 'move'
  | 'resize-nw'
  | 'resize-ne'
  | 'resize-sw'
  | 'resize-se'
  | 'crop-n'
  | 'crop-s'
  | 'crop-e'
  | 'crop-w';
type OverlayViewModel = {
  actionId: string;
  track: string;
  label: string;
  bounds: OverlayBounds;
  fullBounds: OverlayBounds;
  cropValues: CropValues;
  isText: boolean;
};

function OverlayEditorComponent({
  rows,
  meta,
  registry: _registry,
  currentTime,
  playerContainerRef,
  trackScaleMap,
  compositionWidth,
  compositionHeight,
  selectedClipId,
  deviceClass,
  inputModality,
  interactionMode: _interactionMode,
  gestureOwner,
  onSelectClip,
  onOverlayChange,
  setInputModalityFromPointerType,
  setGestureOwner,
  setContextTarget,
  setInspectorTarget,
  onDoubleClickAsset,
}: OverlayEditorProps) {
  const [layout, setLayout] = useState<OverlayLayout | null>(null);
  const [editingClipId, setEditingClipId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [dragOverride, setDragOverride] = useState<{
    actionId: string;
    bounds: OverlayBounds;
    cropValues: CropValues;
    startBounds: OverlayBounds;
  } | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const dragState = useRef<{
    mode: DragMode;
    actionId: string;
    startMouseX: number;
    startMouseY: number;
    pointerId: number;
    scaleX: number;
    scaleY: number;
    target: HTMLElement;
    startBounds: OverlayBounds;
    startFullBounds: OverlayBounds;
    startCropValues: CropValues;
    startAspectRatio: number;
    latestBounds: OverlayBounds;
    cropValues: CropValues;
    claimedOwnership: boolean;
    hasChanges: boolean;
  } | null>(null);
  useRenderDiagnostic('OverlayEditor');
  const markLayoutEffect = useEffectDiagnostic('overlayEditor:layout');
  const touchPreviewInput = isTouchTimelineInput(deviceClass, inputModality);
  const allowsDirectManipulationControls = !(deviceClass === 'phone' && inputModality === 'touch');
  const previewTouchAction = deviceClass === 'phone' ? 'manipulation' : 'none';

  const getTrackDefaultBounds = useCallback((trackId: string): OverlayBounds => {
    const trackScale = Math.max(trackScaleMap[trackId] ?? 1, 0.01);
    return {
      x: Math.round(compositionWidth * (1 - trackScale) / 2),
      y: Math.round(compositionHeight * (1 - trackScale) / 2),
      width: Math.round(compositionWidth * trackScale),
      height: Math.round(compositionHeight * trackScale),
    };
  }, [compositionHeight, compositionWidth, trackScaleMap]);

  const getClipBounds = useCallback((clipMeta: ClipMeta, trackId: string): OverlayBounds => {
    if (clipMeta.clipType === 'text') {
      return {
        x: clipMeta.x ?? 0,
        y: clipMeta.y ?? 0,
        width: clipMeta.width ?? 640,
        height: clipMeta.height ?? 180,
      };
    }

    // Must match VisualClip's hasPositionOverride check (includes crop fields).
    // When any of these are set, Remotion renders with absolute positioning at
    // clip.x/y/width/height (with fallbacks 0/0/compositionW/compositionH).
    const hasPositionOverride = (
      clipMeta.x !== undefined
      || clipMeta.y !== undefined
      || clipMeta.width !== undefined
      || clipMeta.height !== undefined
      || clipMeta.cropTop !== undefined
      || clipMeta.cropBottom !== undefined
      || clipMeta.cropLeft !== undefined
      || clipMeta.cropRight !== undefined
    );

    if (hasPositionOverride) {
      return {
        x: clipMeta.x ?? 0,
        y: clipMeta.y ?? 0,
        width: clipMeta.width ?? compositionWidth,
        height: clipMeta.height ?? compositionHeight,
      };
    }

    return getTrackDefaultBounds(trackId);
  }, [compositionHeight, compositionWidth, getTrackDefaultBounds]);

  // Compute which clip IDs are visible at currentTime — this string only changes when clips enter/exit
  const visibleClipKey = useMemo(() => {
    const ids: string[] = [];
    for (const row of rows) {
      if (!row.id.startsWith('V')) continue;
      for (const action of row.actions) {
        if (currentTime >= action.start && currentTime < action.end) {
          ids.push(action.id);
        }
      }
    }
    return ids.join(',');
  }, [currentTime, rows]);

  const activeOverlays = useMemo(() => {
    const overlays: OverlayViewModel[] = [];
    for (const row of rows) {
      if (!row.id.startsWith('V')) {
        continue;
      }

      for (const action of row.actions) {
        if (currentTime < action.start || currentTime >= action.end) {
          continue;
        }

        const clipMeta = meta[action.id];
        if (!clipMeta || clipMeta.track !== row.id) {
          continue;
        }
        if (clipMeta.clipType === 'effect-layer') {
          continue;
        }

        const hasPositionOverride = clipMeta.clipType === 'text'
          || clipMeta.x !== undefined
          || clipMeta.y !== undefined
          || clipMeta.width !== undefined
          || clipMeta.height !== undefined
          || clipMeta.cropTop !== undefined
          || clipMeta.cropBottom !== undefined
          || clipMeta.cropLeft !== undefined
          || clipMeta.cropRight !== undefined;
        if (!hasPositionOverride && selectedClipId !== action.id) {
          continue;
        }

        const fullBounds = getClipBounds(clipMeta, row.id);
        const cropValues = normalizeCropValues({
          cropTop: clipMeta.cropTop,
          cropBottom: clipMeta.cropBottom,
          cropLeft: clipMeta.cropLeft,
          cropRight: clipMeta.cropRight,
        });
        const visibleBounds = getVisibleBoundsFromCrop(fullBounds, cropValues);
        overlays.push({
          actionId: action.id,
          track: row.id,
          label: clipMeta.text?.content || clipMeta.asset || action.id,
          bounds: visibleBounds,
          fullBounds,
          cropValues,
          isText: clipMeta.clipType === 'text',
        });
      }
    }

    return overlays;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- visibleClipKey is a stable proxy for currentTime
  }, [visibleClipKey, getClipBounds, meta, rows, selectedClipId]);

  const effectiveOverlays = useMemo(() => {
    if (!dragOverride) {
      return activeOverlays;
    }

    return activeOverlays.map((overlay) => (
      overlay.actionId === dragOverride.actionId
        ? {
            ...overlay,
            bounds: dragOverride.bounds,
            fullBounds: getFullBoundsFromVisibleBounds(dragOverride.bounds, dragOverride.cropValues),
            cropValues: dragOverride.cropValues,
          }
        : overlay
    ));
  }, [activeOverlays, dragOverride]);

  const computeLayout = useCallback((): OverlayLayout | null => {
    const player = playerContainerRef.current;
    if (!player || compositionWidth <= 0 || compositionHeight <= 0) {
      return null;
    }

    const parent = player.offsetParent as HTMLElement | null;
    if (!parent) {
      return null;
    }

    const playerRect = player.getBoundingClientRect();
    const parentRect = parent.getBoundingClientRect();
    const videoAspect = compositionWidth / compositionHeight;
    const containerAspect = playerRect.width / Math.max(1, playerRect.height);
    const videoWidth = containerAspect > videoAspect ? playerRect.height * videoAspect : playerRect.width;
    const videoHeight = containerAspect > videoAspect ? playerRect.height : playerRect.width / videoAspect;

    return {
      left: playerRect.left - parentRect.left + (playerRect.width - videoWidth) / 2,
      top: playerRect.top - parentRect.top + (playerRect.height - videoHeight) / 2,
      width: videoWidth,
      height: videoHeight,
    };
  }, [compositionHeight, compositionWidth, playerContainerRef]);

  useEffect(() => {
    markLayoutEffect();
    const updateLayout = () => setLayout(computeLayout());

    updateLayout();
    window.addEventListener('resize', updateLayout);
    const player = playerContainerRef.current;
    const observer = typeof ResizeObserver !== 'undefined' && player ? new ResizeObserver(updateLayout) : null;
    if (observer && player) {
      observer.observe(player);
    }

    return () => {
      window.removeEventListener('resize', updateLayout);
      observer?.disconnect();
    };
  }, [computeLayout, markLayoutEffect, playerContainerRef]);

  const finishDrag = useCallback((pointerId: number | null) => {
    const state = dragState.current;
    if (!state) {
      return;
    }

    const releasePointerId = pointerId ?? state.pointerId;
    if (state.target.hasPointerCapture(releasePointerId)) {
      state.target.releasePointerCapture(releasePointerId);
    }
    if (state.claimedOwnership) {
      setGestureOwner('none');
    }

    dragState.current = null;
    setDragOverride(null);
    setDragActive(false);
  }, [setGestureOwner]);

  useEffect(() => {
    if (!dragActive) {
      return;
    }

    const onPointerMove = (event: PointerEvent) => {
      const state = dragState.current;
      if (!state || state.pointerId !== event.pointerId) {
        return;
      }

      const deltaX = (event.clientX - state.startMouseX) * state.scaleX;
      const deltaY = (event.clientY - state.startMouseY) * state.scaleY;
      let nextBounds = { ...state.startBounds };
      let nextCropValues = state.cropValues;

      if (state.mode === 'move') {
        nextBounds.x += deltaX;
        nextBounds.y += deltaY;
      } else if (state.mode.startsWith('crop-')) {
        const minVisibleWidthFraction = Math.min(
          MAX_CROP_FRACTION,
          MIN_CLIP_SIZE / Math.max(MIN_CLIP_SIZE, state.startFullBounds.width),
        );
        const minVisibleHeightFraction = Math.min(
          MAX_CROP_FRACTION,
          MIN_CLIP_SIZE / Math.max(MIN_CLIP_SIZE, state.startFullBounds.height),
        );
        nextCropValues = { ...state.startCropValues };

        if (state.mode === 'crop-e') {
          nextCropValues.cropRight = clamp(
            state.startCropValues.cropRight - deltaX / Math.max(MIN_CLIP_SIZE, state.startFullBounds.width),
            0,
            1 - state.startCropValues.cropLeft - minVisibleWidthFraction,
          );
        }
        if (state.mode === 'crop-w') {
          nextCropValues.cropLeft = clamp(
            state.startCropValues.cropLeft + deltaX / Math.max(MIN_CLIP_SIZE, state.startFullBounds.width),
            0,
            1 - state.startCropValues.cropRight - minVisibleWidthFraction,
          );
        }
        if (state.mode === 'crop-s') {
          nextCropValues.cropBottom = clamp(
            state.startCropValues.cropBottom - deltaY / Math.max(MIN_CLIP_SIZE, state.startFullBounds.height),
            0,
            1 - state.startCropValues.cropTop - minVisibleHeightFraction,
          );
        }
        if (state.mode === 'crop-n') {
          nextCropValues.cropTop = clamp(
            state.startCropValues.cropTop + deltaY / Math.max(MIN_CLIP_SIZE, state.startFullBounds.height),
            0,
            1 - state.startCropValues.cropBottom - minVisibleHeightFraction,
          );
        }

        nextCropValues = normalizeCropValues(nextCropValues);
        nextBounds = getVisibleBoundsFromCrop(state.startFullBounds, nextCropValues);
      } else {
        // Corner resize — lock aspect ratio. Use the dominant axis (larger delta) to drive both.
        const ar = state.startAspectRatio;
        const absDX = Math.abs(deltaX);
        const absDY = Math.abs(deltaY);
        // Determine scale delta from the axis the user is dragging most
        const useWidth = absDX * (state.startBounds.height / Math.max(1, state.startBounds.width)) >= absDY;
        const east = state.mode.includes('e');
        const south = state.mode.includes('s');
        const west = state.mode.includes('w');
        const north = state.mode.includes('n');

        let newWidth: number;
        let newHeight: number;
        if (useWidth) {
          newWidth = Math.max(MIN_CLIP_SIZE, state.startBounds.width + (east ? deltaX : -deltaX));
          newHeight = Math.max(MIN_CLIP_SIZE, newWidth / ar);
        } else {
          newHeight = Math.max(MIN_CLIP_SIZE, state.startBounds.height + (south ? deltaY : -deltaY));
          newWidth = Math.max(MIN_CLIP_SIZE, newHeight * ar);
        }

        if (west) {
          nextBounds.x = state.startBounds.x + (state.startBounds.width - newWidth);
        }
        if (north) {
          nextBounds.y = state.startBounds.y + (state.startBounds.height - newHeight);
        }
        nextBounds.width = newWidth;
        nextBounds.height = newHeight;
      }

      state.latestBounds = nextBounds;
      state.cropValues = nextCropValues;
      state.hasChanges = true;
      setDragOverride({
        actionId: state.actionId,
        bounds: nextBounds,
        cropValues: nextCropValues,
        startBounds: state.startBounds,
      });

      // Push changes to Remotion live so IT renders the image (no fake preview).
      // This is cheap — just a shallow meta merge + React re-render.
      if (state.mode.startsWith('crop-')) {
        onOverlayChange(state.actionId, {
          ...state.startFullBounds,
          cropTop: nextCropValues.cropTop || undefined,
          cropBottom: nextCropValues.cropBottom || undefined,
          cropLeft: nextCropValues.cropLeft || undefined,
          cropRight: nextCropValues.cropRight || undefined,
        });
      } else {
        onOverlayChange(state.actionId, getFullBoundsFromVisibleBounds(nextBounds, nextCropValues));
      }
    };

    const onPointerUp = (event: PointerEvent) => {
      const state = dragState.current;
      if (!state || state.pointerId !== event.pointerId) {
        return;
      }

      finishDrag(event.pointerId);
    };

    const onPointerCancel = (event: PointerEvent) => {
      const state = dragState.current;
      if (!state || state.pointerId !== event.pointerId) {
        return;
      }

      finishDrag(event.pointerId);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        finishDrag(null);
      }
    };

    const onWindowBlur = () => {
      finishDrag(null);
    };

    const onWindowContextMenu = () => {
      finishDrag(null);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerCancel);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('blur', onWindowBlur);
    window.addEventListener('contextmenu', onWindowContextMenu);
    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerCancel);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('blur', onWindowBlur);
      window.removeEventListener('contextmenu', onWindowContextMenu);
    };
  }, [dragActive, finishDrag, onOverlayChange]);

  const startDrag = useCallback((event: ReactPointerEvent<HTMLElement>, overlay: OverlayViewModel, mode: DragMode) => {
    if (event.button !== 0) {
      return;
    }
    if (gestureOwner !== 'none' && gestureOwner !== 'preview') {
      return;
    }

    const nextInputModality = setInputModalityFromPointerType(event.pointerType);
    const nextContextTarget: TimelineContextTarget = { kind: 'overlay', clipId: overlay.actionId };
    const nextInspectorTarget: TimelineInspectorTarget = { kind: 'clip', clipId: overlay.actionId };

    setContextTarget(nextContextTarget);
    setInspectorTarget(nextInspectorTarget);
    onSelectClip(overlay.actionId);

    if (deviceClass === 'phone' && nextInputModality === 'touch') {
      event.stopPropagation();
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    setGestureOwner('preview');
    event.currentTarget.setPointerCapture(event.pointerId);

    const scaleX = compositionWidth / Math.max(1, layout?.width ?? 1);
    const scaleY = compositionHeight / Math.max(1, layout?.height ?? 1);
    dragState.current = {
      mode,
      actionId: overlay.actionId,
      startMouseX: event.clientX,
      startMouseY: event.clientY,
      pointerId: event.pointerId,
      scaleX,
      scaleY,
      target: event.currentTarget,
      startBounds: { ...overlay.bounds },
      startFullBounds: { ...overlay.fullBounds },
      startCropValues: { ...overlay.cropValues },
      startAspectRatio: overlay.bounds.width / Math.max(1, overlay.bounds.height),
      latestBounds: { ...overlay.bounds },
      cropValues: { ...overlay.cropValues },
      claimedOwnership: true,
      hasChanges: false,
    };
    setDragActive(true);
  }, [
    compositionHeight,
    compositionWidth,
    deviceClass,
    gestureOwner,
    layout,
    onSelectClip,
    setContextTarget,
    setGestureOwner,
    setInputModalityFromPointerType,
    setInspectorTarget,
  ]);

  const beginTextEdit = useCallback((actionId: string) => {
    const clipMeta = meta[actionId];
    if (clipMeta?.clipType !== 'text') {
      return;
    }

    setEditingClipId(actionId);
    setEditText(clipMeta.text?.content ?? '');
  }, [meta]);

  const commitText = useCallback(() => {
    if (!editingClipId) {
      return;
    }

    const clipMeta = meta[editingClipId];
    if (clipMeta?.clipType === 'text') {
      onOverlayChange(editingClipId, {
        text: {
          ...(clipMeta.text ?? { content: '' }),
          content: editText,
        },
      });
    }
    setEditingClipId(null);
  }, [editText, editingClipId, meta, onOverlayChange]);

  if (!layout) {
    return null;
  }

  const fontScale = layout.width / Math.max(1, compositionWidth);
  const draggingId = dragOverride?.actionId ?? null;
  const isCropDrag = dragState.current?.mode.startsWith('crop-') ?? false;

  return (
    <div
      className="pointer-events-none absolute"
      style={{ left: layout.left, top: layout.top, width: layout.width, height: layout.height, touchAction: previewTouchAction }}
    >
      {/* Dim entire composition during crop drag, with a hole for the visible crop area */}
      {isCropDrag && (() => {
        const cropOverlay = effectiveOverlays.find((o) => o.actionId === draggingId);
        if (!cropOverlay) return null;
        // The visible (kept) bounds in screen space as percentages of the layout
        const vl = ((cropOverlay.bounds.x) / compositionWidth) * 100;
        const vt = ((cropOverlay.bounds.y) / compositionHeight) * 100;
        const vr = ((cropOverlay.bounds.x + cropOverlay.bounds.width) / compositionWidth) * 100;
        const vb = ((cropOverlay.bounds.y + cropOverlay.bounds.height) / compositionHeight) * 100;
        // Clamp to composition edges (0-100%)
        const cl = Math.max(0, Math.min(100, vl));
        const ct = Math.max(0, Math.min(100, vt));
        const cr = Math.max(0, Math.min(100, vr));
        const cb = Math.max(0, Math.min(100, vb));
        return (
          <div
            className="absolute inset-0 bg-black/50"
            style={{
              clipPath: `polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% ${ct}%, ${cl}% ${ct}%, ${cl}% ${cb}%, ${cr}% ${cb}%, ${cr}% ${ct}%, 0% ${ct}%)`,
            }}
          />
        );
      })()}
      {effectiveOverlays.map((overlay) => {
        const clipMeta = meta[overlay.actionId];
        const isSelected = selectedClipId === overlay.actionId;
        const isDragging = draggingId === overlay.actionId;
        const isDraggingCrop = isDragging && isCropDrag;

        // During crop drag, show overlay at FULL bounds so the image stays in place;
        // crop is visualised as a mask over the cropped-out regions.
        // Do NOT clamp overlay bounds to composition — the overlay should extend
        // beyond the composition edge so users can see and drag their clip back.
        // Only Remotion's render layer (VisualClip) clamps to the viewport.
        const displayBounds = isDraggingCrop ? overlay.fullBounds : overlay.bounds;
        const style = toOverlayStyle(displayBounds, layout, compositionWidth, compositionHeight);
        const renderFullBounds = overlay.fullBounds;

        const hasCrop = (
          overlay.cropValues.cropTop > 0
          || overlay.cropValues.cropBottom > 0
          || overlay.cropValues.cropLeft > 0
          || overlay.cropValues.cropRight > 0
        );

        // Show full-bounds ghost when a cropped clip is selected (not during crop drag —
        // during crop drag the overlay is already at full bounds).
        const ghostStyle: CSSProperties | null = isSelected && hasCrop && !isDraggingCrop && hasRenderableBounds(renderFullBounds)
          ? {
              left: ((renderFullBounds.x - displayBounds.x) / compositionWidth) * layout.width,
              top: ((renderFullBounds.y - displayBounds.y) / compositionHeight) * layout.height,
              width: (renderFullBounds.width / compositionWidth) * layout.width,
              height: (renderFullBounds.height / compositionHeight) * layout.height,
            }
          : null;

        const scaledFontSize = Math.max(12, (clipMeta?.text?.fontSize ?? 64) * fontScale);

        // During move/resize drag, render the image at full bounds with clip-path
        // (exactly how Remotion renders it). This is a separate layer behind the
        // overlay controls so it's pixel-perfect regardless of crop.
        return (
          <div
            key={overlay.actionId}
            data-overlay-hit="true"
            className="absolute pointer-events-auto"
            style={style}
          >
              {ghostStyle && (
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute rounded border border-dashed border-white/35 bg-white/5 opacity-80"
                  style={ghostStyle}
                />
              )}
              {editingClipId === overlay.actionId && overlay.isText ? (
              <textarea
                data-inline-text-editor="true"
                className="h-full w-full resize-none rounded border border-sky-400 bg-black/80 p-2 text-white outline-none"
                value={editText}
                style={{
                  fontSize: scaledFontSize,
                  color: clipMeta?.text?.color ?? '#ffffff',
                  textAlign: clipMeta?.text?.align ?? 'left',
                }}
                onChange={(event) => setEditText(event.target.value)}
                onBlur={commitText}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                    commitText();
                  }
                }}
                autoFocus
              />
            ) : (
              <div
                role="button"
                tabIndex={0}
                className={`group relative h-full w-full rounded text-left transition motion-reduce:transition-none ${isSelected ? 'border border-sky-400 bg-sky-400/10 shadow-[0_0_0_1px_rgba(56,189,248,0.4)]' : 'border border-transparent hover:border-white/40'}`}
                style={{ touchAction: previewTouchAction }}
                aria-label={isSelected ? `Selected overlay ${overlay.label}` : `Select overlay ${overlay.label}`}
                aria-pressed={isSelected}
                onPointerDown={(event) => startDrag(event, overlay, 'move')}
                onDoubleClick={() => {
                  if (clipMeta?.clipType === 'text') {
                    beginTextEdit(overlay.actionId);
                  } else if (clipMeta?.asset) {
                    onDoubleClickAsset?.(clipMeta.asset, overlay.actionId);
                  }
                }}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectClip(overlay.actionId);
                }}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter' && event.key !== ' ') {
                    return;
                  }
                  event.preventDefault();
                  event.stopPropagation();
                  onSelectClip(overlay.actionId);
                }}
              >
                {isSelected && allowsDirectManipulationControls && (['resize-nw', 'resize-ne', 'resize-sw', 'resize-se'] as const).map((mode) => {
                  const pos = {
                    'resize-nw': 'left-0 top-0 -translate-x-1/2 -translate-y-1/2 cursor-nwse-resize',
                    'resize-ne': 'right-0 top-0 translate-x-1/2 -translate-y-1/2 cursor-nesw-resize',
                    'resize-sw': 'left-0 bottom-0 -translate-x-1/2 translate-y-1/2 cursor-nesw-resize',
                    'resize-se': 'right-0 bottom-0 translate-x-1/2 translate-y-1/2 cursor-nwse-resize',
                  }[mode];
                  return (
                    <span
                      key={mode}
                      aria-hidden="true"
                      className={`absolute rounded-full border border-white/60 bg-sky-400 ${touchPreviewInput ? 'h-11 w-11' : 'h-3 w-3'} ${pos}`}
                      style={{ touchAction: previewTouchAction }}
                      onPointerDown={(event) => startDrag(event, overlay, mode)}
                    />
                  );
                })}
                {isSelected && allowsDirectManipulationControls && !overlay.isText && ([
                  {
                    mode: 'crop-n',
                    hitClassName: 'left-1.5 right-1.5 top-0 h-3 -translate-y-1/2 cursor-ns-resize',
                    lineClassName: 'left-1 right-1 top-1/2 h-px -translate-y-1/2',
                  },
                  {
                    mode: 'crop-s',
                    hitClassName: 'bottom-0 left-1.5 right-1.5 h-3 translate-y-1/2 cursor-ns-resize',
                    lineClassName: 'bottom-1/2 left-1 right-1 h-px translate-y-1/2',
                  },
                  {
                    mode: 'crop-w',
                    hitClassName: 'bottom-1.5 left-0 top-1.5 w-3 -translate-x-1/2 cursor-ew-resize',
                    lineClassName: 'bottom-1 left-1/2 top-1 w-px -translate-x-1/2',
                  },
                  {
                    mode: 'crop-e',
                    hitClassName: 'bottom-1.5 right-0 top-1.5 w-3 translate-x-1/2 cursor-ew-resize',
                    lineClassName: 'bottom-1 right-1/2 top-1 w-px translate-x-1/2',
                  },
                ] as const).map(({ mode, hitClassName, lineClassName }) => (
                  <span
                    key={mode}
                    aria-hidden="true"
                    className={`absolute ${touchPreviewInput ? hitClassName.replace('h-3', 'h-11').replace('w-3', 'w-11') : hitClassName}`}
                    style={{ touchAction: previewTouchAction }}
                    onPointerDown={(event) => startDrag(event, overlay, mode)}
                  >
                    <span
                      className={`pointer-events-none absolute rounded-full transition motion-reduce:transition-none ${lineClassName} ${isSelected || touchPreviewInput ? 'bg-sky-300/70' : 'bg-white/0 group-hover:bg-white/50'}`}
                    />
                  </span>
                ))}
                {isSelected && allowsDirectManipulationControls && (
                  <div
                    className="absolute right-1 top-1 flex gap-1"
                    onPointerDown={(e) => e.stopPropagation()}
                  >
                    {/* Only show reset if the clip has been moved/resized/cropped */}
                    {(clipMeta?.x !== undefined || clipMeta?.y !== undefined
                      || clipMeta?.width !== undefined || clipMeta?.height !== undefined
                      || clipMeta?.cropTop !== undefined || clipMeta?.cropBottom !== undefined
                      || clipMeta?.cropLeft !== undefined || clipMeta?.cropRight !== undefined) && (
                      <button
                        type="button"
                        title="Reset to original size"
                        aria-label="Reset overlay to original size"
                        className={`flex items-center justify-center rounded bg-black/70 text-white/80 transition motion-reduce:transition-none hover:bg-black/90 hover:text-white ${touchPreviewInput ? 'h-11 w-11' : 'h-6 w-6'}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          // Keep current position (x/y), reset size to composition
                          // dimensions and clear crop
                          onOverlayChange(overlay.actionId, {
                            width: compositionWidth,
                            height: compositionHeight,
                            cropTop: undefined,
                            cropBottom: undefined,
                            cropLeft: undefined,
                            cropRight: undefined,
                          } as Partial<ClipMeta>);
                        }}
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </button>
                    )}
                    <button
                      type="button"
                      title="Fill composition"
                      aria-label="Fill overlay to composition"
                      className={`flex items-center justify-center rounded bg-black/70 text-white/80 transition motion-reduce:transition-none hover:bg-black/90 hover:text-white ${touchPreviewInput ? 'h-11 w-11' : 'h-6 w-6'}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onOverlayChange(overlay.actionId, {
                          x: 0,
                          y: 0,
                          width: compositionWidth,
                          height: compositionHeight,
                          cropTop: undefined,
                          cropBottom: undefined,
                          cropLeft: undefined,
                          cropRight: undefined,
                        } as Partial<ClipMeta>);
                      }}
                    >
                      <Maximize2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const OverlayEditor = memo(OverlayEditorComponent, (prev, next) => {
  // Skip re-render when only currentTime changed but visible clips are the same
  if (prev.currentTime !== next.currentTime) {
    const prevKey = getVisibleClipIds(prev.rows, prev.currentTime);
    const nextKey = getVisibleClipIds(next.rows, next.currentTime);
    if (prevKey === nextKey
      && prev.rows === next.rows
      && prev.meta === next.meta
      && prev.registry === next.registry
      && prev.selectedClipId === next.selectedClipId
      && prev.trackScaleMap === next.trackScaleMap
      && prev.compositionWidth === next.compositionWidth
      && prev.compositionHeight === next.compositionHeight
      && prev.deviceClass === next.deviceClass
      && prev.inputModality === next.inputModality
      && prev.interactionMode === next.interactionMode
      && prev.gestureOwner === next.gestureOwner
      && prev.playerContainerRef === next.playerContainerRef
      && prev.onSelectClip === next.onSelectClip
      && prev.onOverlayChange === next.onOverlayChange
      && prev.setInputModalityFromPointerType === next.setInputModalityFromPointerType
      && prev.setGestureOwner === next.setGestureOwner
      && prev.setContextTarget === next.setContextTarget
      && prev.setInspectorTarget === next.setInspectorTarget
      && prev.onDoubleClickAsset === next.onDoubleClickAsset
    ) {
      return true; // skip re-render
    }
  }
  // For all other prop changes, use default shallow comparison
  return false;
});

export default OverlayEditor;
