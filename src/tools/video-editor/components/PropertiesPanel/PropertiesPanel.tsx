import { memo, useEffect, useMemo, useRef } from 'react';
import { Button } from '@/shared/components/ui/button.tsx';
import { BulkClipPanel } from '@/tools/video-editor/components/PropertiesPanel/BulkClipPanel.tsx';
import { ClipPanel, getVisibleClipTabs, NO_EFFECT } from '@/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx';
import {
  useTimelineEditorData,
  useTimelineEditorOps,
} from '@/tools/video-editor/hooks/timelineStore.ts';
import { useStaleVariants } from '@/tools/video-editor/hooks/useStaleVariants.ts';
import { useAddVariantAsGeneration } from '@/tools/video-editor/hooks/useAddVariantAsGeneration.ts';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics.ts';
import { getFallbackClipTab, getSelectionDefaultClipTab } from '@/tools/video-editor/lib/clip-inspector.ts';
import { getBulkVisibleTabs, getSharedNestedValue, getSharedValue } from '@/tools/video-editor/lib/bulk-utils.ts';
import { VIDEO_EDITOR_THEME_VARS } from '@/tools/video-editor/lib/themeTokens.ts';
import {
  useVideoEditorInspectorSections,
  useVideoEditorRenderContext,
} from '@/tools/video-editor/runtime/useVideoEditorRenderContext.ts';
import {
  ContributionErrorBoundary,
  type ContributionErrorInfo,
} from '@/tools/video-editor/runtime/ContributionErrorBoundary.tsx';

function InspectorRegistrySections({
  placement,
}: {
  placement: 'before-default' | 'after-default';
}) {
  const renderContext = useVideoEditorRenderContext();
  const sections = useVideoEditorInspectorSections(placement);

  if (sections.length === 0) {
    return null;
  }

  const handleContributionError = (info: ContributionErrorInfo) => {
    if (typeof console !== 'undefined') {
      console.warn(
        '[PropertiesPanel] Inspector section error captured by boundary:',
        info,
      );
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {sections.map((section) => (
        <ContributionErrorBoundary
          key={section.id}
          contributionId={section.id}
          kind="inspectorSection"
          onError={handleContributionError}
        >
          <div data-video-editor-inspector-section-id={section.id}>
            {section.render(renderContext)}
          </div>
        </ContributionErrorBoundary>
      ))}
    </div>
  );
}

function PropertiesPanelComponent() {
  useRenderDiagnostic('PropertiesPanel');
  const {
    data,
    resolvedConfig,
    selectedClip,
    selectedClipIds,
    deviceClass,
    interactionMode,
    precisionEnabled,
    selectedTrack,
    selectedTrackId,
    selectedClipHasPredecessor,
    compositionSize,
    preferences,
  } = useTimelineEditorData();
  const {
    clearSelection,
    handleUpdateClips,
    handleUpdateClipsDeep,
    handleDeleteClip,
    handleDeleteClips,
    handleSelectedClipChange,
    handleResetClipPosition,
    handleResetClipsPosition,
    handleSplitClipsAtPlayhead,
    handleSplitSelectedClip,
    handleToggleMuteClips,
    handleToggleMute,
    handleDetachAudioClip,
    moveSelectedClipsToTrack,
    setContextTarget,
    setActiveClipTab,
    setInspectorTarget,
    setInteractionMode,
    setPrecisionEnabled,
    patchRegistry,
    registerAsset,
  } = useTimelineEditorOps();
  const { staleAssetKeys, dismissedAssetKeys, dismissAsset, updateAssetToCurrentVariant, applyVariantToAsset } = useStaleVariants({
    registry: resolvedConfig?.registry,
    patchRegistry,
    registerAsset,
  });
  const { addVariantAsGenerationAfterClip, isPending: isAddingVariantAsGenerationPending } = useAddVariantAsGeneration();
  const prevClipIdRef = useRef(selectedClip?.id);
  const selectedClipIdsList = useMemo(() => [...selectedClipIds], [selectedClipIds]);
  const inspectorSelectionTarget = useMemo(() => {
    if (selectedClipIdsList.length > 1) {
      return { kind: 'selection' as const, clipIds: selectedClipIdsList };
    }

    if (selectedClip) {
      return { kind: 'clip' as const, clipId: selectedClip.id };
    }

    if (selectedTrackId) {
      return { kind: 'track' as const, trackId: selectedTrackId };
    }

    return { kind: 'timeline' as const };
  }, [selectedClip, selectedClipIdsList, selectedTrackId]);
  const bulkSelectedClips = resolvedConfig?.clips.filter((clip) => selectedClipIds.has(clip.id)) ?? [];
  const bulkVisibleTabs = getBulkVisibleTabs(bulkSelectedClips, data?.resolvedConfig?.tracks ?? []);
  const bulkEntrance = getSharedNestedValue(bulkSelectedClips, (clip) => clip.entrance);
  const bulkExit = getSharedNestedValue(bulkSelectedClips, (clip) => clip.exit);
  const bulkContinuous = getSharedNestedValue(bulkSelectedClips, (clip) => clip.continuous);
  const bulkText = getSharedNestedValue(bulkSelectedClips, (clip) => clip.text);
  const bulkEntranceType = getSharedValue(bulkSelectedClips.map((clip) => clip.entrance?.type ?? NO_EFFECT));
  const bulkExitType = getSharedValue(bulkSelectedClips.map((clip) => clip.exit?.type ?? NO_EFFECT));
  const bulkContinuousType = getSharedValue(bulkSelectedClips.map((clip) => clip.continuous?.type ?? NO_EFFECT));
  const bulkSpeed = getSharedValue(bulkSelectedClips.map((clip) => clip.speed ?? 1));
  const bulkFrom = getSharedValue(bulkSelectedClips.map((clip) => clip.from ?? 0));
  const bulkTo = getSharedValue(bulkSelectedClips.map((clip) => clip.to ?? clip.assetEntry?.duration ?? 5));
  const bulkX = getSharedValue(bulkSelectedClips.map((clip) => clip.x ?? 0));
  const bulkY = getSharedValue(bulkSelectedClips.map((clip) => clip.y ?? 0));
  const bulkWidth = getSharedValue(bulkSelectedClips.map((clip) => clip.width ?? compositionSize.width));
  const bulkHeight = getSharedValue(bulkSelectedClips.map((clip) => clip.height ?? compositionSize.height));
  const bulkOpacity = getSharedValue(bulkSelectedClips.map((clip) => clip.opacity ?? 1));
  const bulkVolume = getSharedValue(bulkSelectedClips.map((clip) => clip.volume ?? 1));
  const bulkFontSize = getSharedValue(bulkSelectedClips.map((clip) => clip.text?.fontSize ?? 64));
  const bulkTextColor = getSharedValue(bulkSelectedClips.map((clip) => clip.text?.color ?? '#ffffff'));

  useEffect(() => {
    if (selectedClipIds.size > 1) {
      if (!bulkVisibleTabs.includes(preferences.activeClipTab)) {
        setActiveClipTab('effects');
      }
      return;
    }

    const nextVisibleTabs = getVisibleClipTabs(selectedClip, selectedTrack);
    const isClipChange = selectedClip?.id !== prevClipIdRef.current;

    if (isClipChange && selectedClip) {
      setActiveClipTab(getSelectionDefaultClipTab(selectedClip, selectedTrack));
    } else if (!nextVisibleTabs.includes(preferences.activeClipTab)) {
      setActiveClipTab(getFallbackClipTab(preferences.activeClipTab, nextVisibleTabs));
    }

    prevClipIdRef.current = selectedClip?.id;
  }, [
    bulkVisibleTabs,
    preferences.activeClipTab,
    selectedClip,
    selectedClipIds.size,
    selectedTrack,
    setActiveClipTab,
  ]);

  if (!data) {
    return null;
  }

  const hasSelection = selectedClipIds.size > 0;
  const showInspectorActions = deviceClass !== 'desktop' && selectedClipIds.size > 1;

  const focusInspectorMode = (mode: 'move' | 'trim', tab: 'timing' | 'position' = 'timing') => {
    setInteractionMode(mode);
    setInspectorTarget(inspectorSelectionTarget);
    setContextTarget(inspectorSelectionTarget);
    setActiveClipTab(tab);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3" style={VIDEO_EDITOR_THEME_VARS}>
      {showInspectorActions && (
        <div className="rounded-xl border border-[color:var(--video-editor-accent-border)] bg-[var(--video-editor-accent-bg)] p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-foreground">Selection actions</div>
              <div className="mt-1 text-xs text-muted-foreground">
                Use explicit inspector controls for touch editing instead of relying on timeline gestures.
              </div>
            </div>
            <div className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--video-editor-accent-text)]">
              {interactionMode}
              {precisionEnabled ? ' + precision' : ''}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button type="button" variant="secondary" size="sm" className="justify-start" onClick={() => focusInspectorMode('trim')}>
              Trim in inspector
            </Button>
            <Button type="button" variant="secondary" size="sm" className="justify-start" onClick={() => focusInspectorMode('move')}>
              Move in inspector
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={() => moveSelectedClipsToTrack('up', selectedClipIds)}>
              Track up
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={() => moveSelectedClipsToTrack('down', selectedClipIds)}>
              Track down
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={() => handleSplitClipsAtPlayhead(selectedClipIdsList)}>
              Split at playhead
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={() => handleToggleMuteClips(selectedClipIdsList)}>
              Mute or unmute
            </Button>
            <Button
              type="button"
              variant={precisionEnabled ? 'secondary' : 'outline'}
              size="sm"
              className="justify-start"
              onClick={() => {
                setInspectorTarget(inspectorSelectionTarget);
                setContextTarget(inspectorSelectionTarget);
                setPrecisionEnabled(!precisionEnabled);
              }}
            >
              {precisionEnabled ? 'Disable precision' : 'Enable precision'}
            </Button>
            <Button type="button" variant="destructive" size="sm" className="justify-start" onClick={() => handleDeleteClips(selectedClipIdsList)}>
              Delete selection
            </Button>
          </div>
        </div>
      )}
      <InspectorRegistrySections placement="before-default" />
      <div className={`min-h-0 flex-1 overflow-auto rounded-xl border bg-card/80 p-3 transition-colors ${hasSelection ? 'border-[color:var(--video-editor-accent-border)] ring-1 ring-[var(--video-editor-accent-ring)]' : 'border-border'}`}>
        {selectedClipIds.size > 1 ? (
          <BulkClipPanel
            clips={bulkSelectedClips}
            visibleTabs={bulkVisibleTabs}
            compositionWidth={compositionSize.width}
            compositionHeight={compositionSize.height}
            sharedEntrance={bulkEntrance}
            sharedExit={bulkExit}
            sharedContinuous={bulkContinuous}
            sharedText={bulkText}
            sharedEntranceType={bulkEntranceType}
            sharedExitType={bulkExitType}
            sharedContinuousType={bulkContinuousType}
            sharedSpeed={bulkSpeed}
            sharedFrom={bulkFrom}
            sharedTo={bulkTo}
            sharedX={bulkX}
            sharedY={bulkY}
            sharedWidth={bulkWidth}
            sharedHeight={bulkHeight}
            sharedOpacity={bulkOpacity}
            sharedVolume={bulkVolume}
            sharedFontSize={bulkFontSize}
            sharedTextColor={bulkTextColor}
            onChange={(patch) => handleUpdateClips(selectedClipIdsList, patch)}
            onChangeDeep={(patchFn) => handleUpdateClipsDeep(selectedClipIdsList, patchFn)}
            onResetPosition={() => handleResetClipsPosition(selectedClipIdsList)}
            onToggleMute={() => handleToggleMuteClips(selectedClipIdsList)}
            onClose={clearSelection}
            activeTab={preferences.activeClipTab}
            setActiveTab={setActiveClipTab}
          />
        ) : (
          <ClipPanel
            clip={selectedClip}
            track={selectedTrack}
            deviceClass={deviceClass}
            interactionMode={interactionMode}
            precisionEnabled={precisionEnabled}
            hasPredecessor={selectedClipHasPredecessor}
            onChange={handleSelectedClipChange}
            onResetPosition={handleResetClipPosition}
            onClose={clearSelection}
            onDelete={selectedClip ? () => handleDeleteClip(selectedClip.id) : undefined}
            onToggleMute={handleToggleMute}
            onDetachAudio={selectedClip ? () => handleDetachAudioClip(selectedClip.id) : undefined}
            onSplitAtPlayhead={() => {
              setInspectorTarget(inspectorSelectionTarget);
              setContextTarget(inspectorSelectionTarget);
              handleSplitSelectedClip();
            }}
            onMoveTrackUp={() => moveSelectedClipsToTrack('up', selectedClipIds)}
            onMoveTrackDown={() => moveSelectedClipsToTrack('down', selectedClipIds)}
            onSetInteractionMode={(mode) => {
              setInspectorTarget(inspectorSelectionTarget);
              setContextTarget(inspectorSelectionTarget);
              setInteractionMode(mode);
            }}
            onSetPrecisionEnabled={(enabled) => {
              setInspectorTarget(inspectorSelectionTarget);
              setContextTarget(inspectorSelectionTarget);
              setPrecisionEnabled(enabled);
            }}
            compositionWidth={compositionSize.width}
            compositionHeight={compositionSize.height}
            registry={resolvedConfig?.registry ?? {}}
            activeTab={preferences.activeClipTab}
            setActiveTab={setActiveClipTab}
            isVariantStale={selectedClip?.asset ? staleAssetKeys.has(selectedClip.asset) && !dismissedAssetKeys.has(selectedClip.asset) : false}
            onUpdateVariant={selectedClip?.asset ? () => void updateAssetToCurrentVariant(selectedClip.asset!) : undefined}
            onDismissStale={selectedClip?.asset && staleAssetKeys.has(selectedClip.asset) ? () => dismissAsset(selectedClip.asset!) : undefined}
            onApplyVariant={selectedClip?.asset ? (variant) => applyVariantToAsset(selectedClip.asset!, variant) : undefined}
            onAddVariantAsGeneration={selectedClip ? (variant) => addVariantAsGenerationAfterClip(selectedClip.id, variant) : undefined}
            isAddingVariantAsGeneration={selectedClip ? (variantId) => isAddingVariantAsGenerationPending(selectedClip.id, variantId) : undefined}
            timelineFps={resolvedConfig?.output.fps}
          />
        )}
      </div>
      <InspectorRegistrySections placement="after-default" />
    </div>
  );
}

export const PropertiesPanel = memo(PropertiesPanelComponent);
