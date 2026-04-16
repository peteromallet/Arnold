import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { createPortal } from 'react-dom';
import { formatDistanceToNow } from 'date-fns';
import { Download, Eye, GripHorizontal, History, Maximize2, Minimize2, Redo2, Settings, SlidersHorizontal, Undo2, ZoomIn, ZoomOut } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/shared/components/ui/alert-dialog';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/components/ui/contracts/cn';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/shared/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { Slider } from '@/shared/components/ui/slider';
import { usePanes } from '@/shared/contexts/PanesContext';
import { useHomeNavigation } from '@/shared/hooks/useHomeNavigation';
import { CompactPreview } from '@/tools/video-editor/components/CompactPreview';
import { PreviewPanel } from '@/tools/video-editor/components/PreviewPanel/PreviewPanel';
import { RemotionPreview } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview';
import { PropertiesPanel } from '@/tools/video-editor/components/PropertiesPanel/PropertiesPanel';
import { TimelineEditor } from '@/tools/video-editor/components/TimelineEditor/TimelineEditor';
import {
  useTimelineChromeContext,
  useTimelineEditorData,
  useTimelineEditorOps,
  useTimelinePlaybackContext,
} from '@/tools/video-editor/hooks/timelineStore';
import { useKeyboardShortcuts } from '@/tools/video-editor/hooks/useKeyboardShortcuts';
import { useTimelineRealtime } from '@/tools/video-editor/hooks/useTimelineRealtime';
import { getTimelineDurationInFrames, parseResolution } from '@/tools/video-editor/lib/config-utils';
import { buildKeyboardDeleteMutation } from '@/tools/video-editor/lib/keyboard-delete';
import {
  areTimelineInteractionTargetsEqual,
  type TimelineInteractionMode,
  type TimelineInspectorTarget,
} from '@/tools/video-editor/lib/mobile-interaction-model';
import { bootDiagnostics, MemoryPressureDetector } from '@/tools/video-editor/lib/perf-diagnostics';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics';
import { dispatchAppEvent } from '@/shared/lib/typedEvents';

const MIN_TIMELINE_HEIGHT = 140;
const MIN_PREVIEW_HEIGHT = 180;
const CHROME_OVERHEAD = MIN_TIMELINE_HEIGHT + 40 + 28 + 24;
const STATUS_VARIANT = {
  saved: 'default',
  saving: 'secondary',
  dirty: 'outline',
  error: 'destructive',
} as const;
const CHECKPOINT_TRIGGER_LABELS = {
  session_boundary: 'Session boundary',
  edit_distance: 'Edit cap',
  semantic: 'Destructive edit',
  manual: 'Manual',
} as const;
const CHECKPOINT_TRIGGER_BADGE_VARIANT = {
  session_boundary: 'secondary',
  edit_distance: 'outline',
  semantic: 'destructive',
  manual: 'default',
} as const;
const PHONE_MODE_ITEMS: Array<{ mode: Exclude<TimelineInteractionMode, 'precision'>; label: string }> = [
  { mode: 'browse', label: 'Browse' },
  { mode: 'select', label: 'Select' },
  { mode: 'move', label: 'Move' },
  { mode: 'trim', label: 'Trim' },
];

interface VideoEditorShellProps {
  mode: 'full' | 'compact';
  timelineId?: string | null;
  onCreateTimeline?: () => void;
}

function getInspectorTargetForSelection(
  selectedClipIds: string[],
  selectedTrackId: string | null,
): TimelineInspectorTarget {
  if (selectedClipIds.length > 1) {
    return { kind: 'selection', clipIds: selectedClipIds };
  }

  if (selectedClipIds.length === 1) {
    return { kind: 'clip', clipId: selectedClipIds[0] };
  }

  if (selectedTrackId) {
    return { kind: 'track', trackId: selectedTrackId };
  }

  return { kind: 'timeline' };
}

function FullEditorLayout({ timelineId, forceCondensed = false }: { timelineId: string; forceCondensed?: boolean }) {
  useRenderDiagnostic('FullEditorLayout');
  const editorData = useTimelineEditorData();
  const editorOps = useTimelineEditorOps();
  const chrome = useTimelineChromeContext();
  const playback = useTimelinePlaybackContext();
  const { navigateHome } = useHomeNavigation();
  const { isEditorPaneLocked, isGenerationsPaneLocked, setIsGenerationsPaneLocked } = usePanes();
  const isPhone = editorData.deviceClass === 'phone';
  const isTablet = editorData.deviceClass === 'tablet';
  const location = useLocation();
  const navigate = useNavigate();
  const isOnEditorPage = location.pathname.startsWith('/tools/video-editor');
  const containerRef = useRef<HTMLDivElement>(null);
  const dividerRef = useRef<HTMLDivElement>(null);
  const [timelineHeight, setTimelineHeight] = useState<number | null>(null);
  const [isTimelineMaximized, setIsTimelineMaximized] = useState(false);
  /** In condensed mode: 'preview' (default) or 'properties' for the right panel. */
  const [condensedRightPanel, setCondensedRightPanel] = useState<'preview' | 'properties'>('preview');
  const [isMobilePropertiesOpen, setIsMobilePropertiesOpen] = useState(false);
  const timelineFps = Math.max(1, editorData.resolvedConfig?.output?.fps ?? 30);
  const conflict = useTimelineRealtime({
    timelineId,
    conflictExhausted: chrome.isConflictExhausted,
    onKeepLocalChanges: chrome.retrySaveAfterConflict,
    onDiscardRemoteChanges: chrome.reloadFromServer,
  });

  useEffect(() => {
    bootDiagnostics();
    MemoryPressureDetector.start();
    return MemoryPressureDetector.stop;
  }, []);

  const handleKeyboardDelete = useCallback(() => {
    const mutation = buildKeyboardDeleteMutation(editorData.dataRef.current, editorData.selectedClipIds);
    if (mutation) {
      editorOps.applyEdit(mutation, { semantic: true });
      return;
    }

    editorOps.handleDeleteClips([...editorData.selectedClipIds]);
  }, [editorData.dataRef, editorData.selectedClipIds, editorOps]);

  useKeyboardShortcuts({
    hasSelectedClip: editorData.selectedClipIds.size > 0,
    canMoveSelectedClipToTrack: editorData.selectedClipIds.size >= 1,
    precisionEnabled: editorData.precisionEnabled,
    selectedClipIds: editorData.selectedClipIds,
    timelineFps,
    moveSelectedClipsToTrack: editorOps.moveSelectedClipsToTrack,
    undo: chrome.undo,
    redo: chrome.redo,
    selectAllClips: () => editorOps.selectClips(Object.keys(editorData.data?.meta ?? {})),
    togglePlayPause: () => playback.previewRef.current?.togglePlayPause(),
    seekRelative: (deltaSeconds) => playback.previewRef.current?.seek(Math.max(0, playback.currentTime + deltaSeconds)),
    toggleMute: () => editorOps.handleToggleMuteClips([...editorData.selectedClipIds]),
    splitSelectedClip: editorOps.handleSplitSelectedClip,
    deleteSelectedClip: handleKeyboardDelete,
    clearSelection: editorOps.clearSelection,
  });

  const onDividerMouseDown = useCallback((event: ReactMouseEvent) => {
    event.preventDefault();
    setIsTimelineMaximized(false);
    const container = containerRef.current;
    const divider = dividerRef.current;
    if (!container || !divider) {
      return;
    }

    divider.classList.add('is-dragging');
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (moveEvent: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const nextHeight = Math.max(MIN_TIMELINE_HEIGHT, rect.bottom - moveEvent.clientY);
      if (rect.height - nextHeight < MIN_PREVIEW_HEIGHT) {
        return;
      }
      container.style.gridTemplateRows = `minmax(0,1fr) auto ${nextHeight}px`;
    };

    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      divider.classList.remove('is-dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      const match = container.style.gridTemplateRows.match(/(\d+)px$/);
      container.style.gridTemplateRows = '';
      if (match) {
        setTimelineHeight(Number.parseInt(match[1], 10));
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, []);

  const outputResolution = editorData.resolvedConfig?.output?.resolution;
  const aspectRatio = useMemo(() => {
    if (!outputResolution) {
      return 16 / 9;
    }

    const { width, height } = parseResolution(outputResolution);
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      return 16 / 9;
    }

    return width / height;
  }, [outputResolution]);
  const [tooSmall, setTooSmall] = useState(false);
  const outerRef = useRef<HTMLDivElement>(null);
  const condensedSlotRef = useRef<HTMLDivElement>(null);
  const fullSlotRef = useRef<HTMLDivElement>(null);
  const selectedClipIdsList = useMemo(() => [...editorData.selectedClipIds], [editorData.selectedClipIds]);
  const inspectorTarget = useMemo(
    () => getInspectorTargetForSelection(selectedClipIdsList, editorData.selectedTrackId),
    [editorData.selectedTrackId, selectedClipIdsList],
  );
  const [previewHostEl] = useState<HTMLDivElement | null>(() => {
    if (typeof document === 'undefined') {
      return null;
    }

    const host = document.createElement('div');
    host.style.display = 'contents';
    return host;
  });

  useEffect(() => {
    const el = outerRef.current;
    if (!el || forceCondensed) return;

    const observer = new ResizeObserver(([entry]) => {
      const minPreviewHeight = isTimelineMaximized
        ? MIN_PREVIEW_HEIGHT
        : Math.max(MIN_PREVIEW_HEIGHT, Math.min(360, entry.contentRect.width * 0.35) / aspectRatio);
      setTooSmall(entry.contentRect.height < minPreviewHeight + CHROME_OVERHEAD);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [forceCondensed, aspectRatio, isTimelineMaximized]);

  const mobileSinglePane = isPhone && !forceCondensed;
  const condensed = forceCondensed || tooSmall || mobileSinglePane || (isOnEditorPage && isEditorPaneLocked);
  const hasConfig = Boolean(editorData.resolvedConfig);
  const hasClipSelection = selectedClipIdsList.length > 0;
  const mobilePropertiesTitle = hasClipSelection
    ? selectedClipIdsList.length > 1
      ? `Selected clips (${selectedClipIdsList.length})`
      : 'Selected clip'
    : 'Inspector';
  const mobilePropertiesDescription = hasClipSelection
    ? 'Use inspector-first controls for trim, move, track changes, split, mute, and delete without relying on direct manipulation.'
    : 'Use the inspector for timeline controls and mode changes when you need more precision.';
  const inspectorButtonLabel = hasClipSelection
    ? selectedClipIdsList.length > 1
      ? `Selection (${selectedClipIdsList.length})`
      : 'Clip'
    : 'Inspector';
  const touchChrome = isPhone || isTablet;
  const toolbarButtonSizeClass = touchChrome ? 'h-11 w-11' : 'h-6 w-6';
  const previewActionButtonClass = touchChrome ? 'h-11 min-w-11 px-3 text-[11px]' : 'h-7 px-3 text-[11px]';
  const interactionStatusLabel = [
    `Timeline mode ${editorData.interactionMode}.`,
    `Precision ${editorData.precisionEnabled ? 'enabled' : 'disabled'}.`,
    editorData.gestureOwner === 'preview'
      ? 'Preview transform active.'
      : (touchChrome ? 'Touch controls are available for shell, timeline, and preview actions.' : 'Desktop pointer controls are active.'),
  ].join(' ');

  useEffect(() => {
    if (!areTimelineInteractionTargetsEqual(editorData.inspectorTarget, inspectorTarget)) {
      editorOps.setInspectorTarget(inspectorTarget);
    }
  }, [editorData.inspectorTarget, editorOps, inspectorTarget]);

  useEffect(() => {
    if (isTablet && condensed && hasClipSelection && condensedRightPanel !== 'properties') {
      setCondensedRightPanel('properties');
    }
  }, [condensed, condensedRightPanel, hasClipSelection, isTablet]);

  useLayoutEffect(() => {
    if (!previewHostEl) {
      return;
    }

    const activeSlot = condensed ? condensedSlotRef.current : fullSlotRef.current;
    if (!hasConfig || !activeSlot) {
      previewHostEl.remove();
      return () => {
        previewHostEl.remove();
      };
    }

    if (previewHostEl.parentElement !== activeSlot) {
      activeSlot.appendChild(previewHostEl);
    }

    return () => {
      previewHostEl.remove();
    };
  }, [condensed, hasConfig, previewHostEl]);

  const gridTemplateRows = isTimelineMaximized
    ? `${MIN_PREVIEW_HEIGHT}px auto 1fr`
    : (timelineHeight ? `minmax(0,1fr) auto ${timelineHeight}px` : 'minmax(0,1fr) auto minmax(200px,36%)');

  const totalSeconds = useMemo(() => {
    if (!editorData.resolvedConfig) return 1;
    return getTimelineDurationInFrames(editorData.resolvedConfig, editorData.resolvedConfig.output.fps) / editorData.resolvedConfig.output.fps;
  }, [editorData.resolvedConfig]);

  const openInspector = useCallback(() => {
    editorOps.setInspectorTarget(inspectorTarget);
    editorOps.setContextTarget(inspectorTarget);

    if (mobileSinglePane) {
      setIsMobilePropertiesOpen(true);
      return;
    }

    setCondensedRightPanel('properties');
  }, [editorOps, inspectorTarget, mobileSinglePane]);

  const handlePhoneModeChange = useCallback((mode: Exclude<TimelineInteractionMode, 'precision'>) => {
    editorOps.setInteractionMode(mode);
    editorOps.setContextTarget({ kind: 'timeline' });
    editorOps.setInspectorTarget(inspectorTarget);
  }, [editorOps, inspectorTarget]);

  const togglePhonePrecision = useCallback(() => {
    editorOps.setPrecisionEnabled(!editorData.precisionEnabled);
    editorOps.setContextTarget({ kind: 'timeline' });
    editorOps.setInspectorTarget(inspectorTarget);
  }, [editorData.precisionEnabled, editorOps, inspectorTarget]);

  const phoneModeBar = mobileSinglePane ? (
    <div
      className="rounded-xl border border-border bg-card/80 p-1"
      role="toolbar"
      aria-label="Phone timeline mode bar"
      data-shell-interaction="true"
    >
      <div className="grid grid-cols-5 gap-1">
        {PHONE_MODE_ITEMS.map((item) => {
          const isActive = editorData.interactionMode === item.mode;
          return (
            <button
              key={item.mode}
              type="button"
              className={cn(
                'min-h-11 rounded-lg px-2 py-2 text-[11px] font-medium uppercase tracking-[0.12em] transition-colors motion-reduce:transition-none',
                isActive
                  ? 'bg-accent text-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
              aria-pressed={isActive}
              onClick={() => handlePhoneModeChange(item.mode)}
            >
              {item.label}
            </button>
          );
        })}
        <button
          type="button"
          className={cn(
            'min-h-11 rounded-lg px-2 py-2 text-[11px] font-medium uppercase tracking-[0.12em] transition-colors motion-reduce:transition-none',
            editorData.precisionEnabled
              ? 'bg-sky-500/15 text-sky-100 ring-1 ring-sky-400/50'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
          aria-pressed={editorData.precisionEnabled}
          onClick={togglePhonePrecision}
        >
          Precision
        </button>
      </div>
      <div className="px-2 pt-2 text-[11px] text-muted-foreground">
        {hasClipSelection
          ? `${inspectorButtonLabel} actions are available in the inspector.`
          : 'Open the inspector for move, trim, and timeline actions.'}
      </div>
    </div>
  ) : null;

  // ── Save badge (left of track buttons in toolbar) ───────────────────

  const saveBadge = (
    <Badge variant={STATUS_VARIANT[chrome.saveStatus]} className="h-5 px-1.5 text-[10px] capitalize">
      {chrome.saveStatus}
    </Badge>
  );
  const historyControls = (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={toolbarButtonSizeClass}
        onClick={chrome.undo}
        disabled={!chrome.canUndo}
        title="Undo"
      >
        <Undo2 className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={toolbarButtonSizeClass}
        onClick={chrome.redo}
        disabled={!chrome.canRedo}
        title="Redo"
      >
        <Redo2 className="h-3.5 w-3.5" />
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="ghost" size="icon" className={toolbarButtonSizeClass} title="History">
            <History className="h-3.5 w-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-80">
          <DropdownMenuLabel className="pb-1 text-xs font-semibold text-muted-foreground">
            History
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {chrome.checkpoints.length === 0 ? (
            <div className="px-2 py-3 text-xs text-muted-foreground">
              No checkpoints yet. Save one manually or keep editing to build history.
            </div>
          ) : (
            chrome.checkpoints.map((checkpoint) => (
              <DropdownMenuItem
                key={checkpoint.id}
                className="flex flex-col items-start gap-1 py-2"
                onClick={() => chrome.jumpToCheckpoint(checkpoint.id)}
              >
                <div className="flex w-full items-start justify-between gap-2">
                  <span className="truncate text-sm text-foreground">{checkpoint.label}</span>
                  <Badge
                    variant={CHECKPOINT_TRIGGER_BADGE_VARIANT[checkpoint.triggerType]}
                    className="shrink-0 px-1.5 py-0 text-[9px] uppercase tracking-[0.12em]"
                  >
                    {CHECKPOINT_TRIGGER_LABELS[checkpoint.triggerType]}
                  </Badge>
                </div>
                <span className="text-[11px] text-muted-foreground">
                  {formatDistanceToNow(new Date(checkpoint.createdAt), { addSuffix: true })}
                </span>
              </DropdownMenuItem>
            ))
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => void chrome.createManualCheckpoint()}>
            Save checkpoint
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );

  // ── Toolbar (shared between both layouts) ──────────────────────────

  const toolbar = (
    <div className={cn('flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-card/80 px-2 text-muted-foreground', touchChrome ? 'min-h-11 py-1' : 'h-7')}>
      <div className="flex items-center gap-1">
        {condensed && !forceCondensed && (
          <button
            type="button"
            className="mr-2 min-h-11 shrink-0 px-2 text-[11px] transition-colors hover:text-foreground motion-reduce:transition-none"
            onClick={navigateHome}
          >
            ← Back
          </button>
        )}
        {saveBadge}
        {historyControls}
      </div>
      {!condensed && (
        <div
          className="flex h-full flex-1 cursor-row-resize items-center justify-center"
          onMouseDown={onDividerMouseDown}
        >
          <GripHorizontal className="h-4 w-4 text-border" />
        </div>
      )}
      <div className="flex items-center gap-1">
        {!condensed && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={toolbarButtonSizeClass}
            onClick={() => setIsTimelineMaximized((value) => !value)}
            title={isTimelineMaximized ? 'Restore preview and timeline split' : 'Maximize timeline'}
          >
            {isTimelineMaximized ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </Button>
        )}
        <Button type="button" variant="ghost" size="icon" className={toolbarButtonSizeClass} onClick={() => chrome.setScaleWidth((value) => Math.max(value / 1.4, 40))}>
          <ZoomOut className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" variant="ghost" size="icon" className={toolbarButtonSizeClass} onClick={() => chrome.setScaleWidth((value) => Math.min(value * 1.4, 500))}>
          <ZoomIn className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );

  // ── Preview overlay (time top-left, render top-right) ──────────────

  const previewOverlay = (
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-center justify-between px-3 py-3" data-shell-interaction="true">
      <span className="pointer-events-auto rounded bg-background/70 px-1.5 py-0.5 font-mono text-[11px] tracking-[0.08em] text-muted-foreground backdrop-blur-sm">{playback.formatTime(playback.currentTime)}</span>
      <div className="pointer-events-auto flex items-center gap-1">
        {mobileSinglePane && (
          <Dialog
            open={isMobilePropertiesOpen}
            onOpenChange={(open) => {
              setIsMobilePropertiesOpen(open);
              if (open) {
                editorOps.setInspectorTarget(inspectorTarget);
                editorOps.setContextTarget(inspectorTarget);
              }
            }}
          >
            <DialogTrigger asChild>
              <Button
                type="button"
                size="sm"
                variant={hasClipSelection ? 'secondary' : 'outline'}
                onClick={() => {
                  editorOps.setInspectorTarget(inspectorTarget);
                  editorOps.setContextTarget(inspectorTarget);
                }}
                className={cn(
                  `gap-1.5 ${previewActionButtonClass}`,
                  hasClipSelection && 'border-sky-400/60 bg-sky-500/10 text-sky-100 hover:bg-sky-500/20',
                )}
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                {inspectorButtonLabel}
              </Button>
            </DialogTrigger>
            <DialogContent className="top-auto bottom-0 max-h-[78dvh] w-[calc(100vw-1rem)] max-w-none translate-x-[-50%] translate-y-0 gap-0 overflow-hidden rounded-t-2xl border-border bg-background p-0 data-[ending-style]:slide-out-to-top-[100%] data-[open]:slide-in-from-top-[100%] motion-reduce:animate-none motion-reduce:transition-none sm:max-w-lg sm:translate-y-[-50%] sm:rounded-lg sm:p-6 sm:data-[ending-style]:slide-out-to-top-[48%] sm:data-[open]:slide-in-from-top-[48%]">
              <DialogHeader className="border-b border-border px-4 py-3 text-left">
                <DialogTitle className="text-base">{mobilePropertiesTitle}</DialogTitle>
                <DialogDescription>{mobilePropertiesDescription}</DialogDescription>
              </DialogHeader>
              <div className="min-h-0 flex-1 overflow-hidden p-3">
                <PropertiesPanel />
              </div>
            </DialogContent>
          </Dialog>
        )}
        {condensed && !mobileSinglePane && (
          <Button
            type="button"
            size="sm"
            variant={condensedRightPanel === 'properties' ? 'secondary' : hasClipSelection ? 'outline' : 'ghost'}
            className={cn(
              `gap-1.5 ${previewActionButtonClass}`,
              hasClipSelection && condensedRightPanel !== 'properties' && 'border-sky-400/60 text-sky-100 hover:bg-sky-500/10',
            )}
            onClick={openInspector}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            {inspectorButtonLabel}
          </Button>
        )}
        {condensed && !mobileSinglePane && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className={`gap-1.5 ${previewActionButtonClass}`}
            onClick={() => {
              if (isOnEditorPage && isGenerationsPaneLocked) {
                setIsGenerationsPaneLocked(false);
              } else {
                navigate(`/tools/video-editor?timeline=${timelineId}`);
              }
            }}
          >
            <Maximize2 className="h-3 w-3" />
            Editor
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          className={`gap-1.5 ${previewActionButtonClass}`}
          onClick={() => void chrome.startRender()}
          disabled={chrome.renderStatus === 'rendering'}
        >
          <Download className="h-3.5 w-3.5" />
          {chrome.renderStatus === 'rendering' && chrome.renderProgress
            ? `Render ${chrome.renderProgress.percent}%`
            : 'Render'}
        </Button>
        {chrome.renderResultUrl && chrome.renderStatus === 'done' && !chrome.renderDirty && (
          <a
            href={chrome.renderResultUrl}
            download={chrome.renderResultFilename ?? undefined}
            className={cn(
              'rounded-md border border-border/70 bg-background/80 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground transition-colors hover:text-foreground motion-reduce:transition-none',
              touchChrome ? 'min-h-11 px-3 py-2' : 'px-2 py-1',
            )}
          >
            Download
          </a>
        )}
      </div>
    </div>
  );

  const previewPortal =
    previewHostEl && editorData.resolvedConfig
      ? createPortal(
          <RemotionPreview
            ref={playback.previewRef}
            config={editorData.resolvedConfig}
            compact={condensed}
            initialTime={playback.currentTime}
            onTimeUpdate={playback.onPreviewTimeUpdate}
            playerContainerRef={playback.playerContainerRef}
          />,
          previewHostEl,
        )
      : null;

  return (
    <>
      <div ref={outerRef} className="flex h-full min-h-0 flex-col overflow-hidden bg-background text-foreground">
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {interactionStatusLabel}
        </div>
        {!condensed && (
          <div className="flex h-10 items-center gap-3 border-b border-border bg-background px-3 text-sm text-muted-foreground">
            <button
              type="button"
              className={cn('shrink-0 transition-colors hover:text-foreground motion-reduce:transition-none', touchChrome && 'min-h-11 px-2')}
              onClick={navigateHome}
            >
              ← Back
            </button>
            <div className="truncate text-foreground">{chrome.timelineName ?? 'Untitled timeline'}</div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={cn('ml-auto text-muted-foreground', touchChrome ? 'h-11 w-11' : 'h-7 w-7')}
              onClick={() => dispatchAppEvent('openSettings', {})}
              title="Settings"
            >
              <Settings className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {mobileSinglePane ? (
          <main className="grid h-full min-h-0 flex-1 animate-in fade-in duration-200 motion-reduce:animate-none motion-reduce:transition-none grid-rows-[auto_auto_minmax(260px,42dvh)_minmax(0,1fr)] gap-3 p-3 transition-opacity">
            <div>
              {toolbar}
            </div>

            {phoneModeBar}

            <div className="flex min-h-0 flex-col gap-3">
              <div className="relative min-h-0 flex-1">
                {previewOverlay}
                <PreviewPanel previewSlotRef={condensedSlotRef} />
              </div>
              <div className="rounded-xl border border-border bg-card/80 px-3 py-2">
                <Slider
                  value={[playback.currentTime]}
                  min={0}
                  max={Math.max(1, totalSeconds)}
                  step={0.05}
                  onValueChange={(value) => playback.previewRef.current?.seek(value)}
                />
              </div>
            </div>

            <div className="relative min-h-0 overflow-hidden">
              <TimelineEditor />
            </div>

          </main>
        ) : condensed ? (
          /* ── Condensed layout: timeline left, preview or props right ── */
          <main className="grid h-full min-h-0 flex-1 animate-in fade-in duration-200 motion-reduce:animate-none motion-reduce:transition-none grid-cols-[minmax(0,1fr)_320px] grid-rows-[auto_minmax(0,1fr)] gap-3 p-3 transition-opacity">
            <div className="col-span-1">
              {toolbar}
            </div>

            <div className="row-span-2 flex min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-card/80">
              <div className="flex items-center border-b border-border">
                <button
                  type="button"
                  className={`flex min-h-11 flex-1 items-center justify-center gap-1.5 px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.12em] transition-colors motion-reduce:transition-none ${condensedRightPanel === 'preview' ? 'bg-accent text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                  onClick={() => setCondensedRightPanel('preview')}
                >
                  <Eye className="h-3 w-3" />
                  Preview
                </button>
                <button
                  type="button"
                  className={`flex min-h-11 flex-1 items-center justify-center gap-1.5 border px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.12em] transition-colors motion-reduce:transition-none ${condensedRightPanel === 'properties' ? 'border-transparent bg-accent text-foreground' : editorData.selectedClipIds.size > 0 ? 'border-sky-400 text-muted-foreground hover:text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
                  onClick={openInspector}
                >
                  <SlidersHorizontal className="h-3 w-3" />
                  {inspectorButtonLabel}
                </button>
              </div>

              <div
                className={cn('relative flex min-h-0 flex-1 flex-col', condensedRightPanel !== 'preview' && 'hidden')}
                aria-hidden={condensedRightPanel !== 'preview'}
              >
                {previewOverlay}
                <div className="min-h-0 flex-1">
                  <div ref={condensedSlotRef} className="flex h-full w-full min-h-0 items-center justify-center" />
                </div>
                <div className="border-t border-border px-3 py-2">
                  <Slider
                    value={[playback.currentTime]}
                    min={0}
                    max={Math.max(1, totalSeconds)}
                    step={0.05}
                    onValueChange={(value) => playback.previewRef.current?.seek(value)}
                  />
                </div>
              </div>
              <div
                className={cn('min-h-0 flex-1 overflow-auto p-3', condensedRightPanel !== 'properties' && 'hidden')}
                aria-hidden={condensedRightPanel !== 'properties'}
              >
                <PropertiesPanel />
              </div>
            </div>

            <div className="relative col-span-1 min-h-0 overflow-hidden">
              <TimelineEditor />

            </div>

          </main>
        ) : (
          /* ── Standard layout: preview top, timeline bottom ── */
          <main
            ref={containerRef}
            className="grid h-full min-h-0 flex-1 animate-in fade-in duration-200 motion-reduce:animate-none motion-reduce:transition-none grid-cols-[minmax(0,1fr)_360px] gap-3 p-3 transition-[grid-template-rows,opacity] duration-300 ease-smooth"
            style={{ gridTemplateRows }}
          >
            <div className="relative min-h-0">
              {previewOverlay}
              <PreviewPanel previewSlotRef={fullSlotRef} />
            </div>

            <div className="row-span-2 min-h-0 overflow-hidden">
              <PropertiesPanel />
            </div>

            <div ref={dividerRef} className="col-span-1">
              {toolbar}
            </div>

            <div className="relative col-span-2 min-h-0 overflow-hidden">
              <TimelineEditor />

            </div>

          </main>
        )}
      </div>
      {previewPortal}

      <AlertDialog open={conflict.isOpen} onOpenChange={conflict.setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remote timeline changes detected</AlertDialogTitle>
            <AlertDialogDescription>
              Another tab updated this timeline while you still have unsaved local edits. Keep your local draft or discard it and reload the latest server version.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => void conflict.keepLocalChanges()}>Keep local draft</AlertDialogCancel>
            <AlertDialogAction onClick={() => void conflict.discardAndReload()}>Discard and reload</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function VideoEditorShellComponent({ mode, timelineId, onCreateTimeline }: VideoEditorShellProps) {
  if (!timelineId) {
    if (mode === 'compact') {
      return <CompactPreview timelineId={timelineId} onCreateTimeline={onCreateTimeline} />;
    }
    return null;
  }

  return <FullEditorLayout timelineId={timelineId} forceCondensed={mode === 'compact'} />;
}

export const VideoEditorShell = memo(VideoEditorShellComponent);
