import { memo, type ReactNode } from 'react';
import { shallow } from 'zustand/shallow';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import OverlayEditor from '@/tools/video-editor/components/PreviewPanel/OverlayEditor.tsx';
import type { VideoEditorPreviewSurface } from '@/tools/video-editor/components/PreviewPanel/useVideoEditorPreviewSurface.tsx';
import {
  useTimelineDataSelector,
  useTimelineOpsSelector,
  useTimelinePlaybackSelector,
} from '@/tools/video-editor/hooks/timelineStore.ts';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics.ts';
import { isTouchTimelineInput } from '@/tools/video-editor/lib/mobile-interaction-model.ts';
import { useRenderBudget } from '@/shared/dev/useRenderBudget.ts';
import { userClearAllSelection, userSelectTimelineClip } from '@/shared/state/selectionStore.ts';

export interface PreviewPanelProps {
  surface: VideoEditorPreviewSurface;
  overlay?: ReactNode;
  footer?: ReactNode;
  showOverlayEditor?: boolean;
  panelClassName?: string;
  surfaceClassName?: string;
}

function PreviewPanelComponent({
  surface,
  overlay,
  footer,
  showOverlayEditor = true,
  panelClassName,
  surfaceClassName,
}: PreviewPanelProps) {
  useRenderBudget('PreviewPanel', 5);
  useRenderDiagnostic('PreviewPanel');
  const {
    data,
    resolvedConfig,
    trackScaleMap,
    compositionSize,
    selectedClipId,
    deviceClass,
    inputModality,
    interactionMode,
    gestureOwner,
    precisionEnabled,
  } = useTimelineDataSelector((timeline) => ({
    data: timeline.data,
    resolvedConfig: timeline.resolvedConfig,
    trackScaleMap: timeline.trackScaleMap,
    compositionSize: timeline.compositionSize,
    selectedClipId: timeline.selectedClipId,
    deviceClass: timeline.deviceClass,
    inputModality: timeline.inputModality,
    interactionMode: timeline.interactionMode,
    gestureOwner: timeline.gestureOwner,
    precisionEnabled: timeline.precisionEnabled,
  }), shallow);
  const {
    onOverlayChange,
    onDoubleClickAsset,
    setInputModalityFromPointerType,
    setGestureOwner,
    setContextTarget,
    setInspectorTarget,
  } = useTimelineOpsSelector((ops) => ({
    onOverlayChange: ops.onOverlayChange,
    onDoubleClickAsset: ops.onDoubleClickAsset,
    setInputModalityFromPointerType: ops.setInputModalityFromPointerType,
    setGestureOwner: ops.setGestureOwner,
    setContextTarget: ops.setContextTarget,
    setInspectorTarget: ops.setInspectorTarget,
  }), shallow);
  const {
    playerContainerRef,
    currentTime,
  } = useTimelinePlaybackSelector((playback) => ({
    playerContainerRef: playback.playerContainerRef,
    currentTime: playback.currentTime,
  }), shallow);

  if (!data || !resolvedConfig || !surface.hasConfig) {
    return null;
  }

  const interactionStateLabel = gestureOwner === 'preview'
    ? 'Preview overlay transform active.'
    : (isTouchTimelineInput(deviceClass, inputModality) && deviceClass === 'phone'
        ? 'Phone touch preview uses inspector-first overlay editing.'
        : 'Preview overlay transforms are available in the preview.');

  return (
    <>
      <div
        className={cn(
          'flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-card/80',
          panelClassName,
        )}
        role="region"
        aria-label="Preview panel"
      >
        <div className="relative flex min-h-0 flex-1">
          <div
            className={cn(
              'relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-background',
              surfaceClassName,
            )}
            style={{ touchAction: gestureOwner === 'preview' ? 'none' : 'manipulation' }}
            onPointerDownCapture={(event) => {
              const target = event.target;
              if (!(target instanceof Element)) {
                return;
              }

              if (target.closest("[data-overlay-hit='true'], [data-inline-text-editor='true']")) {
                return;
              }

              setInputModalityFromPointerType(event.pointerType);
              if (gestureOwner !== 'none' && gestureOwner !== 'preview') {
                return;
              }

              setContextTarget({ kind: 'preview' });
              setInspectorTarget({ kind: 'preview' });
              if (gestureOwner === 'preview') {
                setGestureOwner('none');
              }
              userClearAllSelection();
            }}
          >
            <div className="sr-only" aria-live="polite" aria-atomic="true">
              {interactionStateLabel}
              {' '}
              Mode {interactionMode}. Precision {precisionEnabled ? 'enabled' : 'disabled'}.
            </div>
            {overlay}
            <div
              ref={surface.slotRef}
              className="flex h-full w-full min-h-0 items-center justify-center"
              data-testid="video-editor-preview-surface"
              data-current-time={currentTime}
            />
            {showOverlayEditor ? (
              <OverlayEditor
                rows={data.rows}
                meta={data.meta}
                registry={resolvedConfig.registry}
                currentTime={currentTime}
                playerContainerRef={playerContainerRef}
                trackScaleMap={trackScaleMap}
                compositionWidth={compositionSize.width}
                compositionHeight={compositionSize.height}
                selectedClipId={selectedClipId}
                deviceClass={deviceClass}
                inputModality={inputModality}
                interactionMode={interactionMode}
                gestureOwner={gestureOwner}
                onSelectClip={(clipId) => {
                  if (clipId === null) {
                    userClearAllSelection();
                    return;
                  }
                  userSelectTimelineClip(clipId, { additive: false });
                }}
                onOverlayChange={onOverlayChange}
                setInputModalityFromPointerType={setInputModalityFromPointerType}
                setGestureOwner={setGestureOwner}
                setContextTarget={setContextTarget}
                setInspectorTarget={setInspectorTarget}
                onDoubleClickAsset={onDoubleClickAsset}
              />
            ) : null}
          </div>
        </div>
        {footer ? <div className="border-t border-border px-3 py-2">{footer}</div> : null}
      </div>
      {surface.portal}
    </>
  );
}

export const PreviewPanel = memo(PreviewPanelComponent);
