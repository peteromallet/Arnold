import { memo, type RefObject } from 'react';
import { shallow } from 'zustand/shallow';
import OverlayEditor from '@/tools/video-editor/components/PreviewPanel/OverlayEditor';
import {
  useTimelineDataSelector,
  useTimelineOpsSelector,
  useTimelinePlaybackSelector,
} from '@/tools/video-editor/hooks/timelineStore';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics';
import { isTouchTimelineInput } from '@/tools/video-editor/lib/mobile-interaction-model';
import { useRenderBudget } from '@/shared/dev/useRenderBudget';

interface PreviewPanelProps {
  previewSlotRef: RefObject<HTMLDivElement>;
}

function PreviewPanelComponent({ previewSlotRef }: PreviewPanelProps) {
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
    setSelectedClipId,
    onOverlayChange,
    onDoubleClickAsset,
    setInputModalityFromPointerType,
    setGestureOwner,
    setContextTarget,
    setInspectorTarget,
  } = useTimelineOpsSelector((ops) => ({
    setSelectedClipId: ops.setSelectedClipId,
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

  if (!data || !resolvedConfig) {
    return null;
  }

  const interactionStateLabel = gestureOwner === 'preview'
    ? 'Preview overlay transform active.'
    : (isTouchTimelineInput(deviceClass, inputModality) && deviceClass === 'phone'
        ? 'Phone touch preview uses inspector-first overlay editing.'
        : 'Preview overlay transforms are available in the preview.');

  return (
    <div
      className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-card/80"
      role="region"
      aria-label="Preview panel"
    >
      <div className="relative flex min-h-0 flex-1">
        <div
          className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-background"
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
            setSelectedClipId(null);
          }}
        >
          <div className="sr-only" aria-live="polite" aria-atomic="true">
            {interactionStateLabel}
            {' '}
            Mode {interactionMode}. Precision {precisionEnabled ? 'enabled' : 'disabled'}.
          </div>
          <div ref={previewSlotRef} className="flex h-full w-full min-h-0 items-center justify-center" />
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
            onSelectClip={setSelectedClipId}
            onOverlayChange={onOverlayChange}
            setInputModalityFromPointerType={setInputModalityFromPointerType}
            setGestureOwner={setGestureOwner}
            setContextTarget={setContextTarget}
            setInspectorTarget={setInspectorTarget}
            onDoubleClickAsset={onDoubleClickAsset}
          />
        </div>
      </div>
    </div>
  );
}

export const PreviewPanel = memo(PreviewPanelComponent);
