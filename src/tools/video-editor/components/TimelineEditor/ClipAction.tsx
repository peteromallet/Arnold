import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight, Clapperboard, Copy, Ellipsis, Film, FolderPlus, ImageIcon, Layers, Loader2, MapPin, MapPinOff, Music2, RefreshCw, Scissors, Sparkles, Trash2, Type, X } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { MediaVariantPicker } from '@/shared/components/MediaVariantPicker.tsx';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants.ts';
import type { Shot } from '@/domains/generation/types/index.ts';
import { usePortalMousedownGuard } from '@/shared/hooks/usePortalMousedownGuard.ts';
import { WaveformOverlay } from '@/tools/video-editor/components/TimelineEditor/WaveformOverlay.tsx';
import { useWaveformData } from '@/tools/video-editor/hooks/useWaveformData.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';
import type { TimelineAction } from '@/tools/video-editor/types/timeline-canvas.ts';

const log = import.meta.env.DEV ? (...args: Parameters<typeof console.log>) => console.log(...args) : () => {};

interface ContextMenuState {
  x: number;
  y: number;
  clientX: number;
}

interface ClipActionProps {
  action: TimelineAction;
  clipMeta: ClipMeta;
  isSelected: boolean;
  isPrimary?: boolean;
  /** Group members use the shot-group overlay for resize; clip-level handles stay hidden. */
  isInPinnedShotGroup?: boolean;
  selectedClipIds?: string[];
  thumbnailSrc?: string;
  audioSrc?: string;
  clipWidth?: number;
  onSelect: (clipId: string, trackId: string) => void;
  onDoubleClickAsset?: (assetKey: string, clipId?: string) => void;
  onDoubleClickVideoClip?: (clipId: string) => void;
  onExpandTinyClip?: (clipId: string) => void;
  onSplitHere?: (clipId: string, clientX: number) => void;
  onSplitClipsAtPlayhead?: (clipIds: string[]) => void;
  onTrimToMediaEnd?: (clipId: string) => void;
  onConvertOverhangToHold?: (clipId: string) => void;
  onDeleteClip?: (clipId: string) => void;
  onDeleteClips?: (clipIds: string[]) => void;
  onToggleMuteClips?: (clipIds: string[]) => void;
  onOpenSequenceCreator?: () => void;
  isVideoClip?: boolean;
  isTaskActive?: boolean;
  showOverflowMenu?: boolean;
  /** True when the clip's file no longer matches the generation's current primary variant */
  isVariantStale?: boolean;
  /** True when the clip is linked to a generation (enables "Update to current variant" in menu) */
  isGenerationAsset?: boolean;
  isDuplicatingGeneration?: boolean;
  onDuplicateGeneration?: (clipId: string) => void | Promise<void>;
  onUpdateVariant?: () => void;
  onDismissStale?: () => void;
  /** True when the clip has stale source-map entries. */
  isSourceMapStale?: boolean;
  /** Called when the user clicks the source-map stale badge to navigate to source. */
  onNavigateToSource?: (clipId: string) => void;
  /** True when the clip has any source-map entries (stale or not). */
  hasSourceMapEntry?: boolean;
  /** Generation id for the asset bound to this clip (enables the variant picker badge). */
  variantPickerGenerationId?: string;
  /** Variant id currently bound to this clip's asset (highlighted in picker). */
  variantPickerCurrentVariantId?: string | null;
  /** Apply a chosen variant to this clip's asset (patches registry). */
  onApplyVariant?: (variant: GenerationVariant) => void | Promise<void>;
  /** Promote a chosen variant into a new generation and insert it after this clip. */
  onAddVariantAsGeneration?: (variant: GenerationVariant) => void | Promise<void>;
  /** Returns true while a specific variant's add-as-generation action is in flight. */
  isAddingVariantAsGeneration?: (variantId: string) => boolean;
  canCreateShotFromSelection?: boolean;
  existingShots?: Shot[];
  onCreateShotFromSelection?: () => Promise<Shot | null>;
  onGenerateVideoFromSelection?: () => void | Promise<void>;
  onNavigateToShot?: (shot: Shot) => void;
  onOpenGenerateVideo?: (shot: Shot) => void;
  isCreatingShot?: boolean;
  overhangDurationSeconds?: number;
  overhangEndFraction?: number;
}

const menuItemClassName = 'relative flex w-full cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground';
const destructiveMenuItemClassName = `${menuItemClassName} hover:bg-destructive hover:text-destructive-foreground`;
const disabledMenuItemClassName = 'disabled:cursor-wait disabled:opacity-60';

type ClipContextMenuProps = Pick<ClipActionProps, 'isGenerationAsset' | 'isDuplicatingGeneration' | 'onDuplicateGeneration' | 'onUpdateVariant' | 'isVariantStale' | 'onDismissStale' | 'onSplitHere' | 'onSplitClipsAtPlayhead' | 'onTrimToMediaEnd' | 'onConvertOverhangToHold' | 'overhangDurationSeconds' | 'onToggleMuteClips' | 'onOpenSequenceCreator' | 'onCreateShotFromSelection' | 'onGenerateVideoFromSelection' | 'onNavigateToShot' | 'onOpenGenerateVideo' | 'isCreatingShot' | 'onDeleteClip' | 'onDeleteClips' | 'isInPinnedShotGroup'> & { actionId: string; contextMenu: ContextMenuState; menuRef: React.RefObject<HTMLDivElement>; closeMenu: () => void; hasBatchSelection: boolean; selectedClipIds: string[]; showShotActions: boolean; hasActionsBeforeShotSection: boolean; existingShots?: Shot[]; };
type ClipContextMenuItemProps = { icon: React.ComponentType<{ className?: string }>; onClick: () => void; children: React.ReactNode; disabled?: boolean; destructive?: boolean; suffix?: React.ReactNode; };

function ClipContextMenuItem({ icon: Icon, onClick, children, disabled = false, destructive = false, suffix }: ClipContextMenuItemProps) {
  return (
    <button
      type="button"
      className={cn(destructive ? destructiveMenuItemClassName : menuItemClassName, disabled && disabledMenuItemClassName)}
      onClick={onClick}
      disabled={disabled}
    >
      <Icon className="h-4 w-4" />
      {children}
      {suffix}
    </button>
  );
}

function ClipContextMenu(props: ClipContextMenuProps) {
  const [adjusted, setAdjusted] = useState<{ x: number; y: number } | null>(null);
  const [createdShot, setCreatedShot] = useState<Shot | null>(null);
  const [isCreatingLocal, setIsCreatingLocal] = useState(false);
  const { onCreateShotFromSelection } = props;

  // Recompute position whenever the menu's size changes (e.g. async-loaded
  // shots arrive, or "Create Shot" expands the menu) so it never overflows
  // the viewport. Falls back to a one-shot measurement if ResizeObserver
  // isn't available.
  useLayoutEffect(() => {
    const node = props.menuRef.current;
    if (!node) {
      setAdjusted(null);
      return;
    }

    const recompute = () => {
      const rect = node.getBoundingClientRect();
      const pad = 8;
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let x = props.contextMenu.x;
      if (x + rect.width + pad > viewportWidth) {
        x = Math.max(pad, viewportWidth - rect.width - pad);
      }

      let y = props.contextMenu.y;
      if (y + rect.height + pad > viewportHeight) {
        // Try flipping above the click point first; clamp if there's no room.
        const flipped = props.contextMenu.y - rect.height;
        y = flipped >= pad ? flipped : Math.max(pad, viewportHeight - rect.height - pad);
      }

      setAdjusted({ x, y });
    };

    recompute();

    if (typeof ResizeObserver === 'undefined') {
      return;
    }
    const observer = new ResizeObserver(recompute);
    observer.observe(node);
    return () => observer.disconnect();
  }, [props.contextMenu.x, props.contextMenu.y, props.menuRef]);

  usePortalMousedownGuard(props.menuRef);

  const handleCreateShot = useCallback(async () => {
    if (!onCreateShotFromSelection) return;
    setIsCreatingLocal(true);
    const shot = await onCreateShotFromSelection();
    setIsCreatingLocal(false);
    if (shot) {
      setCreatedShot(shot);
    }
  }, [onCreateShotFromSelection]);

  const pos = adjusted ?? props.contextMenu;
  const visibleExistingShots = (props.existingShots ?? []).filter((shot) => shot.id !== createdShot?.id);
  const hasOverhang = typeof props.overhangDurationSeconds === 'number' && props.overhangDurationSeconds > 0.0001;
  const hasAssetStateActions = !props.hasBatchSelection && Boolean(
    (!props.isInPinnedShotGroup && props.isGenerationAsset && props.onDuplicateGeneration)
    || (props.isGenerationAsset && props.onUpdateVariant)
    || (props.isVariantStale && props.onDismissStale),
  );
  const hasOverhangActions = !props.hasBatchSelection && hasOverhang && Boolean(
    props.onTrimToMediaEnd || props.onConvertOverhangToHold,
  );
  const showOverhangDivider = hasAssetStateActions && hasOverhangActions;
  const hasGenerationActions = !props.hasBatchSelection && Boolean(
    !props.isInPinnedShotGroup && props.isGenerationAsset && (
      props.onDuplicateGeneration || props.onUpdateVariant
    ),
  );
  const hasLowerShotActions = Boolean(
    (!createdShot && (props.onCreateShotFromSelection || props.onGenerateVideoFromSelection))
    || (createdShot && (props.onNavigateToShot || props.onOpenGenerateVideo)),
  );

  return createPortal(
    <div
      ref={props.menuRef}
      className="fixed z-50 min-w-[10rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95"
      style={{ left: pos.x, top: pos.y, visibility: adjusted ? 'visible' : 'hidden' }}
    >
      {!props.hasBatchSelection && !props.isInPinnedShotGroup && props.isGenerationAsset && props.onDuplicateGeneration && (
        <ClipContextMenuItem
          icon={props.isDuplicatingGeneration ? Loader2 : Copy}
          onClick={() => {
            props.closeMenu();
            void props.onDuplicateGeneration?.(props.actionId);
          }}
          disabled={props.isDuplicatingGeneration}
        >
          {props.isDuplicatingGeneration ? 'Duplicating generation…' : 'Duplicate generation'}
        </ClipContextMenuItem>
      )}
      {!props.hasBatchSelection && props.isGenerationAsset && props.onUpdateVariant && (
        <ClipContextMenuItem icon={RefreshCw} onClick={() => { props.onUpdateVariant?.(); props.closeMenu(); }}>
          Update to current variant
        </ClipContextMenuItem>
      )}
      {!props.hasBatchSelection && props.isVariantStale && props.onDismissStale && (
        <ClipContextMenuItem icon={X} onClick={() => { props.onDismissStale?.(); props.closeMenu(); }}>
          Dismiss reminder
        </ClipContextMenuItem>
      )}
      {showOverhangDivider && (
        <div className="my-1 h-px bg-border" />
      )}
      {!props.hasBatchSelection && hasOverhang && props.onTrimToMediaEnd && (
        <ClipContextMenuItem icon={Scissors} onClick={() => { props.onTrimToMediaEnd?.(props.actionId); props.closeMenu(); }}>
          Trim to media end
        </ClipContextMenuItem>
      )}
      {!props.hasBatchSelection && hasOverhang && props.onConvertOverhangToHold && (
        <ClipContextMenuItem icon={Film} onClick={() => { props.onConvertOverhangToHold?.(props.actionId); props.closeMenu(); }}>
          Hold last frame
        </ClipContextMenuItem>
      )}
      {!props.isInPinnedShotGroup && (
        <>
          {!props.hasBatchSelection && props.onSplitHere && (
            <ClipContextMenuItem icon={Scissors} onClick={() => { props.onSplitHere?.(props.actionId, props.contextMenu.clientX); props.closeMenu(); }}>
              Split Here
            </ClipContextMenuItem>
          )}
          {props.hasBatchSelection && props.onToggleMuteClips && (
            <ClipContextMenuItem icon={Music2} onClick={() => { props.onToggleMuteClips?.(props.selectedClipIds); props.closeMenu(); }}>
              Mute/Unmute {props.selectedClipIds.length} clips
            </ClipContextMenuItem>
          )}
          {props.hasBatchSelection && props.onSplitClipsAtPlayhead && (
            <ClipContextMenuItem icon={Scissors} onClick={() => { props.onSplitClipsAtPlayhead?.(props.selectedClipIds); props.closeMenu(); }}>
              Split {props.selectedClipIds.length} clips at playhead
            </ClipContextMenuItem>
          )}
          {props.onOpenSequenceCreator && (
            <ClipContextMenuItem icon={Sparkles} onClick={() => { props.onOpenSequenceCreator?.(); props.closeMenu(); }}>
              Create animation sequence
            </ClipContextMenuItem>
          )}
          {props.showShotActions && (props.hasActionsBeforeShotSection || hasGenerationActions) && <div className="my-1 h-px bg-border" />}
          {props.showShotActions && visibleExistingShots.map((shot) => (
            <div key={shot.id} className="flex w-full items-center gap-1 rounded-sm px-2 py-1.5 text-sm">
              <span className="min-w-0 flex-1 truncate">{shot.name}</span>
              {props.onOpenGenerateVideo && (
                <button type="button" className="flex h-5 w-5 shrink-0 items-center justify-center rounded hover:bg-accent hover:text-accent-foreground" onClick={() => { props.onOpenGenerateVideo?.(shot); props.closeMenu(); }} title="Generate Video">
                  <Clapperboard className="h-3.5 w-3.5" />
                </button>
              )}
              {props.onNavigateToShot && (
                <button type="button" className="flex h-5 w-5 shrink-0 items-center justify-center rounded hover:bg-accent hover:text-accent-foreground" onClick={() => { props.onNavigateToShot?.(shot); props.closeMenu(); }} title="Jump to shot">
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
          {props.showShotActions && visibleExistingShots.length > 0 && hasLowerShotActions && (
            <div className="my-1 h-px bg-border" />
          )}
          {props.showShotActions && !createdShot && props.onCreateShotFromSelection && (
            <ClipContextMenuItem icon={FolderPlus} onClick={() => void handleCreateShot()} disabled={isCreatingLocal || props.isCreatingShot}>
              {isCreatingLocal ? 'Creating…' : 'Create Shot'}
            </ClipContextMenuItem>
          )}
          {props.showShotActions && createdShot && props.onNavigateToShot && (
            <ClipContextMenuItem icon={ArrowRight} onClick={() => { props.onNavigateToShot?.(createdShot); props.closeMenu(); }}>
              Jump to {createdShot.name}
            </ClipContextMenuItem>
          )}
          {props.showShotActions && createdShot && props.onOpenGenerateVideo && (
            <ClipContextMenuItem icon={Clapperboard} onClick={() => { props.onOpenGenerateVideo?.(createdShot); props.closeMenu(); }}>
              Generate Video
            </ClipContextMenuItem>
          )}
          {props.showShotActions && !createdShot && props.onGenerateVideoFromSelection && (
            <ClipContextMenuItem icon={Clapperboard} onClick={() => { props.closeMenu(); void props.onGenerateVideoFromSelection?.(); }} disabled={props.isCreatingShot}>
              Generate Video
            </ClipContextMenuItem>
          )}
          {props.hasBatchSelection && props.onDeleteClips ? (
            <ClipContextMenuItem
              icon={Trash2}
              onClick={() => { props.onDeleteClips?.(props.selectedClipIds); props.closeMenu(); }}
              destructive
              suffix={<span className="ml-auto text-xs tracking-widest opacity-60">Del</span>}
            >
              Delete {props.selectedClipIds.length} clips
            </ClipContextMenuItem>
          ) : props.onDeleteClip && (
            <ClipContextMenuItem
              icon={Trash2}
              onClick={() => { props.onDeleteClip?.(props.actionId); props.closeMenu(); }}
              destructive
              suffix={<span className="ml-auto text-xs tracking-widest opacity-60">Del</span>}
            >
              Delete Clip
            </ClipContextMenuItem>
          )}
        </>
      )}
    </div>,
    document.body,
  );
}

function ClipActionComponent({
  action,
  clipMeta,
  isSelected,
  isPrimary: _isPrimary = false,
  isInPinnedShotGroup = false,
  selectedClipIds = [],
  thumbnailSrc,
  onSelect,
  onDoubleClickAsset,
  onDoubleClickVideoClip,
  onExpandTinyClip,
  onSplitHere,
  onSplitClipsAtPlayhead,
  onTrimToMediaEnd,
  onConvertOverhangToHold,
  onDeleteClip,
  onDeleteClips,
  onToggleMuteClips,
  onOpenSequenceCreator,
  isVideoClip,
  isTaskActive,
  showOverflowMenu = false,
  isVariantStale,
  isGenerationAsset,
  isDuplicatingGeneration = false,
  isSourceMapStale = false,
  hasSourceMapEntry = false,
  onNavigateToSource,
  onDuplicateGeneration,
  onUpdateVariant,
  onDismissStale,
  variantPickerGenerationId,
  variantPickerCurrentVariantId,
  onApplyVariant,
  onAddVariantAsGeneration,
  isAddingVariantAsGeneration,
  canCreateShotFromSelection = false,
  existingShots,
  onCreateShotFromSelection,
  onGenerateVideoFromSelection,
  onNavigateToShot,
  onOpenGenerateVideo,
  isCreatingShot = false,
  audioSrc,
  clipWidth,
  overhangDurationSeconds,
  overhangEndFraction,
}: ClipActionProps) {
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const openMenuWithSelectionRef = useRef<(clientX: number, clientY: number) => void>(() => undefined);
  const { waveform } = useWaveformData(audioSrc, {
    from: clipMeta.from,
    to: clipMeta.to,
    speed: clipMeta.speed,
    numBuckets: Math.max(2, Math.floor((clipWidth ?? 60) / 3)),
  });

  const closeMenu = useCallback(() => setContextMenu(null), []);
  const openMenuAt = useCallback((x: number, y: number) => { setContextMenu({ x, y, clientX: x }); }, []);

  useEffect(() => {
    if (!contextMenu) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeMenu();
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMenu();
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [contextMenu, closeMenu]);

  openMenuWithSelectionRef.current = (clientX: number, clientY: number) => {
    if (!isSelected) {
      onSelect(action.id, clipMeta.track);
      requestAnimationFrame(() => openMenuAt(clientX, clientY));
      return;
    }

    openMenuAt(clientX, clientY);
  };

  const isEffectLayer = clipMeta.clipType === 'effect-layer';
  const icon = isEffectLayer
    ? <Layers className="h-3 w-3" />
    : clipMeta.clipType === 'text'
    ? <Type className="h-3 w-3" />
    : clipMeta.track.startsWith('A')
      ? <Music2 className="h-3 w-3" />
      : isVideoClip
        ? <Film className="h-3 w-3" />
        : <ImageIcon className="h-3 w-3" />;
  const hasBatchSelection = isSelected && selectedClipIds.length > 1;
  const hasOverhang = typeof overhangDurationSeconds === 'number'
    && overhangDurationSeconds > 0.0001
    && typeof overhangEndFraction === 'number'
    && overhangEndFraction >= 0
    && overhangEndFraction < 0.9999;
  const hasPinnedShotGroupContextActions = !hasBatchSelection && (
    Boolean(
      (isGenerationAsset && onUpdateVariant)
      || (isVariantStale && onDismissStale),
    )
    || (hasOverhang && Boolean(onTrimToMediaEnd || onConvertOverhangToHold))
  );
  const canOpenContextMenu = !isInPinnedShotGroup || hasPinnedShotGroupContextActions;
  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!canOpenContextMenu) {
      return;
    }
    const { clientX, clientY } = e;
    openMenuWithSelectionRef.current(clientX, clientY);
  }, [canOpenContextMenu]);
  const showShotActions = Boolean(canCreateShotFromSelection && (
    typeof onCreateShotFromSelection === 'function' || typeof onGenerateVideoFromSelection === 'function'
  ));
  const hasActionsBeforeShotSection = Boolean(
    (!hasBatchSelection && isGenerationAsset && !isInPinnedShotGroup && onDuplicateGeneration)
    || (!hasBatchSelection && isGenerationAsset && onUpdateVariant)
    || (!hasBatchSelection && isVariantStale && onDismissStale)
    || (!hasBatchSelection && hasOverhang && onTrimToMediaEnd)
    || (!hasBatchSelection && hasOverhang && onConvertOverhangToHold)
    || (!hasBatchSelection && onSplitHere)
    || (hasBatchSelection && onToggleMuteClips)
    || (hasBatchSelection && onSplitClipsAtPlayhead)
    || onOpenSequenceCreator
  );
  const effectBadges = [clipMeta.entrance?.type ? `In:${clipMeta.entrance.type}` : null, clipMeta.continuous?.type ? `Loop:${clipMeta.continuous.type}` : null, clipMeta.exit?.type ? `Out:${clipMeta.exit.type}` : null].filter(Boolean);

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        className={cn(
          'clip-action group relative flex h-full w-full select-none overflow-hidden rounded-md border text-left outline-none',
          isEffectLayer && isSelected
            ? 'border-violet-400 bg-violet-500/20 text-violet-50'
            : isEffectLayer
              ? 'border-violet-500/30 bg-violet-500/10 text-violet-300 hover:border-violet-400/60'
            : isSelected
            ? 'border-sky-400 bg-sky-500/20 text-sky-50'
            : 'border-border bg-card/90 text-foreground hover:border-accent',
        )}
        data-clip-id={action.id}
        data-row-id={clipMeta.track}
        onKeyDown={(event) => {
          if (event.currentTarget !== event.target) {
            return;
          }
          if (event.key !== 'Enter' && event.key !== ' ') {
            return;
          }
          event.preventDefault();
          onSelect(action.id, clipMeta.track);
        }}
        onDoubleClick={(event) => {
          event.stopPropagation();
          if (isEffectLayer || clipMeta.clipType === 'text') return;
          log('[video-editor] clip double-click', {
            clipId: action.id,
            assetKey: clipMeta.asset ?? null,
            trackId: clipMeta.track,
            isVideoClip: Boolean(isVideoClip),
            clipType: clipMeta.clipType ?? null,
          });
          const clipDuration = action.end - action.start;
          if (clipDuration < 0.5 && onExpandTinyClip) {
            onExpandTinyClip(action.id);
            return;
          }
          if (isVideoClip && onDoubleClickVideoClip) {
            onDoubleClickVideoClip(action.id);
          } else if (clipMeta.asset) {
            onDoubleClickAsset?.(clipMeta.asset, action.id);
          }
        }}
        onContextMenu={handleContextMenu}
      >
        {waveform ? <WaveformOverlay waveform={waveform} /> : null}
        {hasOverhang && (
          <div
            aria-hidden="true"
            data-overhang-overlay="true"
            className="pointer-events-none absolute inset-y-0 right-0 z-[1] border-l border-amber-300/80 bg-[repeating-linear-gradient(135deg,rgba(251,191,36,0.2)_0px,rgba(251,191,36,0.2)_8px,rgba(120,53,15,0.28)_8px,rgba(120,53,15,0.28)_16px)]"
            style={{ left: `${Math.min(100, Math.max(0, overhangEndFraction * 100))}%` }}
            title={`Media ends ${overhangDurationSeconds.toFixed(2)}s before the clip ends`}
          />
        )}
        {thumbnailSrc ? (
          <div className="relative z-10 h-full w-10 shrink-0">
            <img src={thumbnailSrc} alt="" className="h-full w-full object-cover opacity-80" draggable={false} />
            {isVideoClip && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Film className="h-3 w-3 text-white drop-shadow-sm" />
              </div>
            )}
          </div>
        ) : (
          <div className="relative z-10 flex h-full w-8 shrink-0 items-center justify-center bg-background/60 text-muted-foreground">
            {icon}
          </div>
        )}
        <div className={`relative z-10 min-w-0 flex-1 px-2 py-1 transition-opacity ${isSelected ? 'opacity-100' : 'opacity-20'}`}>
          <div className="truncate text-[11px] font-medium">
            {isEffectLayer
              ? (clipMeta.continuous?.type || 'Effect Layer')
              : (clipMeta.text?.content || clipMeta.asset || action.id)}
          </div>
          {effectBadges.length > 0 && (
            <div className="mt-1 flex gap-1 overflow-hidden">
              {effectBadges.slice(0, 2).map((badge) => (
                <span key={badge} className="truncate rounded bg-background/60 px-1 py-0.5 text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                  {badge}
                </span>
              ))}
            </div>
          )}
        </div>
        {variantPickerGenerationId && (
          <div
            className={cn(
              'absolute z-20',
              (isTaskActive || isDuplicatingGeneration || isVariantStale) ? 'right-6 top-0' : 'right-1 top-0',
            )}
            data-no-clip-drag
            onMouseDown={(e) => e.stopPropagation()}
          >
            <MediaVariantPicker
              generationId={variantPickerGenerationId}
              currentVariantId={variantPickerCurrentVariantId ?? null}
              onVariantApplied={onApplyVariant}
              onAddVariantAsGeneration={onAddVariantAsGeneration}
              isAddingVariantAsGeneration={isAddingVariantAsGeneration}
              inline
              defaultMediaKind={isVideoClip ? 'video' : 'image'}
            />
          </div>
        )}
        {isTaskActive || isDuplicatingGeneration ? (
          <div
            className="absolute right-1 top-1 z-20 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-white"
            title={isDuplicatingGeneration ? 'Duplicating generation' : 'Task in progress'}
          >
            <Loader2 className="h-2.5 w-2.5 animate-spin" />
          </div>
        ) : isVariantStale ? (
          <div
            className="absolute right-1 top-1 z-20 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-amber-500 text-white hover:bg-amber-400"
            title="Variant outdated"
            role="button"
            onClick={(e) => {
              e.stopPropagation();
              if (isInPinnedShotGroup && !hasPinnedShotGroupContextActions) {
                return;
              }
              const { clientX, clientY } = e;
              openMenuWithSelectionRef.current(clientX, clientY);
            }}
          >
            <RefreshCw className="h-2.5 w-2.5" />
          </div>
        ) : null}
        {/* Source-map stale badge */}
        {isSourceMapStale && (
          <div
            className="absolute left-1 bottom-1 z-20 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-purple-500 text-white hover:bg-purple-400"
            title="Source map stale — click to navigate to source"
            role="button"
            data-source-map-stale="true"
            aria-label="Stale source map — click to navigate to source"
            onClick={(e) => {
              e.stopPropagation();
              onNavigateToSource?.(action.id);
            }}
          >
            <MapPinOff className="h-2.5 w-2.5" />
          </div>
        )}
        {/* Source-map indicator (non-stale) */}
        {hasSourceMapEntry && !isSourceMapStale && (
          <div
            className="absolute left-1 bottom-1 z-20 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-purple-500/60 text-white hover:bg-purple-400"
            title="Source map — click to navigate to source"
            role="button"
            data-source-map-entry="true"
            aria-label="Source map — click to navigate to source"
            onClick={(e) => {
              e.stopPropagation();
              onNavigateToSource?.(action.id);
            }}
          >
            <MapPin className="h-2.5 w-2.5" />
          </div>
        )}
        {showOverflowMenu && canOpenContextMenu && (
          <div
            role="button"
            tabIndex={0}
            data-no-clip-drag
            className={cn(
              'absolute bottom-0 right-0 z-20 flex h-10 w-10 items-center justify-center rounded-tl-md bg-background/80 text-muted-foreground shadow-sm transition-colors',
              'hover:bg-accent hover:text-accent-foreground',
            )}
            aria-label={hasBatchSelection ? `Open actions for ${selectedClipIds.length} selected clips` : 'Open clip actions'}
            onClick={(event) => {
              event.stopPropagation();
              const { clientX, clientY } = event;
              openMenuWithSelectionRef.current(clientX, clientY);
            }}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' && event.key !== ' ') {
                return;
              }
              event.preventDefault();
              event.stopPropagation();
              const target = event.currentTarget.getBoundingClientRect();
              openMenuWithSelectionRef.current(target.left + target.width / 2, target.top + target.height / 2);
            }}
          >
            <Ellipsis className="h-4 w-4" />
          </div>
        )}
      </div>

      {contextMenu && (
        <ClipContextMenu
          actionId={action.id}
          contextMenu={contextMenu}
          menuRef={menuRef}
          closeMenu={closeMenu}
          hasBatchSelection={hasBatchSelection}
          selectedClipIds={selectedClipIds}
          isInPinnedShotGroup={isInPinnedShotGroup}
          isGenerationAsset={isGenerationAsset}
          isDuplicatingGeneration={isDuplicatingGeneration}
          onDuplicateGeneration={onDuplicateGeneration}
          onUpdateVariant={onUpdateVariant}
          isVariantStale={isVariantStale}
          onDismissStale={onDismissStale}
          onSplitHere={onSplitHere}
          onTrimToMediaEnd={onTrimToMediaEnd}
          onConvertOverhangToHold={onConvertOverhangToHold}
          overhangDurationSeconds={overhangDurationSeconds}
          onToggleMuteClips={onToggleMuteClips}
          onOpenSequenceCreator={onOpenSequenceCreator}
          onSplitClipsAtPlayhead={onSplitClipsAtPlayhead}
          showShotActions={showShotActions}
          hasActionsBeforeShotSection={hasActionsBeforeShotSection}
          existingShots={existingShots}
          onCreateShotFromSelection={onCreateShotFromSelection}
          onGenerateVideoFromSelection={onGenerateVideoFromSelection}
          onNavigateToShot={onNavigateToShot}
          onOpenGenerateVideo={onOpenGenerateVideo}
          isCreatingShot={isCreatingShot}
          onDeleteClip={onDeleteClip}
          onDeleteClips={onDeleteClips}
        />
      )}
    </>
  );
}

function areClipActionPropsEqual(prev: ClipActionProps, next: ClipActionProps): boolean {
  const prevSelectedClipIds = prev.selectedClipIds ?? [];
  const nextSelectedClipIds = next.selectedClipIds ?? [];
  if (prev.action !== next.action) return false;
  if (prev.clipMeta !== next.clipMeta) return false;
  if (prev.isSelected !== next.isSelected) return false;
  if (prev.isPrimary !== next.isPrimary) return false;
  if (prev.isInPinnedShotGroup !== next.isInPinnedShotGroup) return false;
  if (prev.thumbnailSrc !== next.thumbnailSrc) return false;
  if (prev.audioSrc !== next.audioSrc) return false;
  if (prev.clipWidth !== next.clipWidth) return false;
  if (prev.overhangDurationSeconds !== next.overhangDurationSeconds) return false;
  if (prev.overhangEndFraction !== next.overhangEndFraction) return false;
  if (prev.isVideoClip !== next.isVideoClip) return false;
  if (prev.isTaskActive !== next.isTaskActive) return false;
  if (prev.isVariantStale !== next.isVariantStale) return false;
  if (prev.isSourceMapStale !== next.isSourceMapStale) return false;
  if (prev.hasSourceMapEntry !== next.hasSourceMapEntry) return false;
  if (prev.isGenerationAsset !== next.isGenerationAsset) return false;
  if (prev.isDuplicatingGeneration !== next.isDuplicatingGeneration) return false;
  if (prev.variantPickerGenerationId !== next.variantPickerGenerationId) return false;
  if (prev.variantPickerCurrentVariantId !== next.variantPickerCurrentVariantId) return false;
  if (prev.canCreateShotFromSelection !== next.canCreateShotFromSelection) return false;
  if (prev.isCreatingShot !== next.isCreatingShot) return false;
  if (prevSelectedClipIds.length !== nextSelectedClipIds.length) return false;
  if ((prev.existingShots?.length ?? 0) !== (next.existingShots?.length ?? 0)) return false;

  for (let index = 0; index < prevSelectedClipIds.length; index += 1) {
    if (prevSelectedClipIds[index] !== nextSelectedClipIds[index]) {
      return false;
    }
  }

  const previousShots = prev.existingShots ?? [];
  const nextShots = next.existingShots ?? [];
  for (let index = 0; index < previousShots.length; index += 1) {
    if (previousShots[index]?.id !== nextShots[index]?.id) {
      return false;
    }
  }

  return (
    prev.onSelect === next.onSelect
    && prev.onDoubleClickAsset === next.onDoubleClickAsset
    && prev.onDoubleClickVideoClip === next.onDoubleClickVideoClip
    && prev.onExpandTinyClip === next.onExpandTinyClip
    && prev.onSplitHere === next.onSplitHere
    && prev.onSplitClipsAtPlayhead === next.onSplitClipsAtPlayhead
    && prev.onTrimToMediaEnd === next.onTrimToMediaEnd
    && prev.onConvertOverhangToHold === next.onConvertOverhangToHold
    && prev.onDeleteClip === next.onDeleteClip
    && prev.onDeleteClips === next.onDeleteClips
    && prev.onToggleMuteClips === next.onToggleMuteClips
    && prev.onOpenSequenceCreator === next.onOpenSequenceCreator
    && prev.onDuplicateGeneration === next.onDuplicateGeneration
    && prev.onCreateShotFromSelection === next.onCreateShotFromSelection
    && prev.onGenerateVideoFromSelection === next.onGenerateVideoFromSelection
    && prev.onNavigateToShot === next.onNavigateToShot
    && prev.onOpenGenerateVideo === next.onOpenGenerateVideo
    && prev.onApplyVariant === next.onApplyVariant
    && prev.onAddVariantAsGeneration === next.onAddVariantAsGeneration
    && prev.isAddingVariantAsGeneration === next.isAddingVariantAsGeneration
    && prev.onNavigateToSource === next.onNavigateToSource
  );
}

export const ClipAction = React.memo(ClipActionComponent, areClipActionPropsEqual);
ClipAction.displayName = 'ClipAction';
