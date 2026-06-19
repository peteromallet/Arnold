import { useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { DraggableAttributes } from '@dnd-kit/core';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { SyntheticListenerMap } from '@dnd-kit/core/dist/hooks/utilities';
import { Check, GripVertical, Settings, Trash2, Video, Volume2, VolumeX } from 'lucide-react';
import { Button } from '@/shared/components/ui/button.tsx';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/shared/components/ui/dialog.tsx';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select.tsx';
import { Slider } from '@/shared/components/ui/slider.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { usePortalMousedownGuard } from '@/shared/hooks/usePortalMousedownGuard.ts';
import {
  ExtensionContextMenuItems,
  hasEligibleExtensionContextMenuItems,
} from '@/tools/video-editor/components/TimelineEditor/ExtensionContextMenuItems.tsx';
import { DataProviderContext } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { isTrackMuted } from '@/tools/video-editor/lib/editor-utils.ts';
import type { TrackBlendMode, TrackDefinition, TrackFit } from '@/tools/video-editor/types/index.ts';
import type { TargetContextPayload } from '@reigh/editor-sdk';

interface TrackLabelProps {
  id: string;
  track: TrackDefinition;
  isSelected: boolean;
  hasClips: boolean;
  onSelect: (trackId: string) => void;
  onChange: (trackId: string, patch: Partial<TrackDefinition>) => void;
  onRemove: (trackId: string) => void;
}

interface TrackLabelContentProps {
  track: TrackDefinition;
  isSelected: boolean;
  hasClips: boolean;
  onSelect: (trackId: string) => void;
  onChange: (trackId: string, patch: Partial<TrackDefinition>) => void;
  onRemove: (trackId: string) => void;
  dragListeners?: SyntheticListenerMap;
  dragAttributes?: DraggableAttributes;
}

export const FIT_OPTIONS: { value: TrackFit; label: string }[] = [
  { value: 'cover', label: 'Cover' },
  { value: 'contain', label: 'Contain' },
  { value: 'manual', label: 'Manual' },
];

export const BLEND_OPTIONS: { value: TrackBlendMode; label: string }[] = [
  { value: 'normal', label: 'Normal' },
  { value: 'multiply', label: 'Multiply' },
  { value: 'screen', label: 'Screen' },
  { value: 'overlay', label: 'Overlay' },
  { value: 'darken', label: 'Darken' },
  { value: 'lighten', label: 'Lighten' },
  { value: 'soft-light', label: 'Soft Light' },
  { value: 'hard-light', label: 'Hard Light' },
];

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-medium text-muted-foreground">{children}</div>;
}

interface TrackContextMenuState {
  x: number;
  y: number;
  target: TargetContextPayload;
}

function validateTrackContextMenuTarget(
  target: TargetContextPayload,
  currentTrackId: string,
): string | null {
  if (target.target !== 'track') return null;
  if (target.trackId !== currentTrackId) {
    return `Track "${target.trackId}" is no longer available.`;
  }
  return null;
}

function TrackExtensionContextMenu({
  menu,
  menuRef,
  trackId,
  closeMenu,
}: {
  menu: TrackContextMenuState;
  menuRef: React.RefObject<HTMLDivElement>;
  trackId: string;
  closeMenu: () => void;
}) {
  const [adjusted, setAdjusted] = useState<{ x: number; y: number } | null>(null);
  const runtime = useContext(DataProviderContext);
  const commandRegistry = runtime?.commandRegistry;
  const extensions = runtime?.extensionRuntime?.extensions ?? [];
  const items = commandRegistry
    ? commandRegistry.getSnapshot().contextMenuItems.filter((item) => item.target === menu.target.target)
    : [];

  useLayoutEffect(() => {
    const node = menuRef.current;
    if (!node) {
      setAdjusted(null);
      return;
    }

    const recompute = () => {
      const rect = node.getBoundingClientRect();
      const pad = 8;
      setAdjusted({
        x: Math.max(pad, Math.min(menu.x, window.innerWidth - rect.width - pad)),
        y: Math.max(pad, Math.min(menu.y, window.innerHeight - rect.height - pad)),
      });
    };

    recompute();

    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(recompute);
    observer.observe(node);
    return () => observer.disconnect();
  }, [menu.x, menu.y, menuRef]);

  usePortalMousedownGuard(menuRef);

  const pos = adjusted ?? menu;

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[10rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95"
      style={{ left: pos.x, top: pos.y, visibility: adjusted ? 'visible' : 'hidden' }}
    >
      <ExtensionContextMenuItems
        items={items}
        target={menu.target}
        extensions={extensions}
        commandRegistry={commandRegistry}
        closeMenu={closeMenu}
        validateTarget={(target) => validateTrackContextMenuTarget(target, trackId)}
      />
    </div>,
    document.body,
  );
}

export function TrackLabelContent({
  track,
  isSelected,
  hasClips,
  onSelect,
  onChange,
  onRemove,
  dragListeners,
  dragAttributes,
}: TrackLabelContentProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [contextMenu, setContextMenu] = useState<TrackContextMenuState | null>(null);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const runtime = useContext(DataProviderContext);
  const commandRegistry = runtime?.commandRegistry;
  const extensions = runtime?.extensionRuntime?.extensions ?? [];

  const closeMenu = useCallback(() => setContextMenu(null), []);

  useEffect(() => {
    if (!confirmingDelete) return;
    confirmTimerRef.current = setTimeout(() => setConfirmingDelete(false), 2000);
    return () => { if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); };
  }, [confirmingDelete]);

  const handleRemoveClick = useCallback((event: React.MouseEvent) => {
    event.stopPropagation();
    if (!hasClips) {
      onRemove(track.id);
      return;
    }
    if (confirmingDelete) {
      setConfirmingDelete(false);
      onRemove(track.id);
    } else {
      setConfirmingDelete(true);
    }
  }, [confirmingDelete, hasClips, onRemove, track.id]);

  useEffect(() => {
    if (!contextMenu) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        closeMenu();
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeMenu();
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [contextMenu, closeMenu]);

  const handleContextMenu = useCallback((event: React.MouseEvent) => {
    const target: TargetContextPayload = { target: 'track', trackId: track.id };
    if (!hasEligibleExtensionContextMenuItems(commandRegistry, extensions, target)) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    onSelect(track.id);
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      target,
    });
  }, [commandRegistry, extensions, onSelect, track.id]);

  return (
    <>
      <div
        className={cn(
          'group relative flex h-9 items-center gap-1 border-b border-border px-2 text-xs text-foreground',
          isSelected ? 'bg-accent/70' : 'bg-card/60 hover:bg-accent/50',
        )}
        data-track-id={track.id}
        onClick={() => onSelect(track.id)}
        onContextMenu={handleContextMenu}
      >
        <span className="shrink-0 text-muted-foreground">
          {track.kind === 'visual' ? <Video className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
        </span>

        {/* Full label shown at rest, fades out on hover */}
        <span className="min-w-0 flex-1 truncate transition-opacity group-hover:opacity-0">
          {track.label}
        </span>

        {/* Editable input + action buttons on hover */}
        <div className="absolute inset-0 flex items-center gap-1 px-2 opacity-0 transition-opacity group-hover:opacity-100">
          <span className="w-[18px] shrink-0" />
          <input
            className="min-w-0 flex-1 bg-transparent text-xs outline-none"
            value={track.label}
            onChange={(event) => onChange(track.id, { label: event.target.value })}
            onClick={(event) => event.stopPropagation()}
          />
          <div className="flex shrink-0 items-center">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-6 w-6 cursor-grab touch-none text-muted-foreground active:cursor-grabbing"
              title="Reorder track"
              aria-label="Reorder track"
              onClick={(event) => event.stopPropagation()}
              {...dragAttributes}
              {...dragListeners}
            >
              <GripVertical className="h-3.5 w-3.5" />
            </Button>
            <Dialog>
              <DialogTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground"
                  title="Track defaults"
                  onClick={(event) => event.stopPropagation()}
                >
                  <Settings className="h-3.5 w-3.5" />
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-sm" onClick={(e) => e.stopPropagation()}>
                <DialogHeader>
                  <DialogTitle>{track.label} — Track Defaults</DialogTitle>
                  <DialogDescription>
                    New items dropped on this track will inherit these settings.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  {track.kind === 'visual' && (
                    <>
                      <div className="space-y-1.5">
                        <FieldLabel>Fit</FieldLabel>
                        <Select
                          value={track.fit ?? 'contain'}
                          onValueChange={(value) => onChange(track.id, { fit: value as TrackFit })}
                        >
                          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {FIT_OPTIONS.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1.5">
                        <FieldLabel>Scale ({((track.scale ?? 1) * 100).toFixed(0)}%)</FieldLabel>
                        <Slider
                          value={[track.scale ?? 1]}
                          min={0.1}
                          max={2}
                          step={0.05}
                          onValueChange={(v) => onChange(track.id, { scale: v })}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <FieldLabel>Opacity ({((track.opacity ?? 1) * 100).toFixed(0)}%)</FieldLabel>
                        <Slider
                          value={[track.opacity ?? 1]}
                          min={0}
                          max={1}
                          step={0.05}
                          onValueChange={(v) => onChange(track.id, { opacity: v })}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <FieldLabel>Blend Mode</FieldLabel>
                        <Select
                          value={track.blendMode ?? 'normal'}
                          onValueChange={(value) => onChange(track.id, { blendMode: value as TrackBlendMode })}
                        >
                          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {BLEND_OPTIONS.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </>
                  )}
                  {track.kind === 'audio' && (
                    <div className="space-y-2">
                      <div className="space-y-1.5">
                        <FieldLabel>Default Volume ({((track.volume ?? 1) * 100).toFixed(0)}%)</FieldLabel>
                        <Slider
                          value={[track.volume ?? 1]}
                          min={0}
                          max={1}
                          step={0.05}
                          onValueChange={(v) => onChange(track.id, { volume: v })}
                        />
                      </div>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="gap-1.5"
                        onClick={() => onChange(track.id, { muted: !isTrackMuted(track) })}
                      >
                        {isTrackMuted(track) ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />}
                        {isTrackMuted(track) ? 'Unmute Track' : 'Mute Track'}
                      </Button>
                    </div>
                  )}
                </div>
              </DialogContent>
            </Dialog>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={cn('h-6 w-6', confirmingDelete ? 'text-destructive hover:text-destructive' : 'text-muted-foreground')}
              title={confirmingDelete ? 'Click again to confirm deletion' : 'Remove track'}
              onClick={handleRemoveClick}
            >
              {confirmingDelete ? <Check className="h-3.5 w-3.5" /> : <Trash2 className="h-3.5 w-3.5" />}
            </Button>
          </div>
        </div>
      </div>
      {contextMenu && (
        <TrackExtensionContextMenu
          menu={contextMenu}
          menuRef={menuRef}
          trackId={track.id}
          closeMenu={closeMenu}
        />
      )}
    </>
  );
}

export function TrackLabel({
  id,
  track,
  isSelected,
  hasClips,
  onSelect,
  onChange,
  onRemove,
}: TrackLabelProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <TrackLabelContent
        track={track}
        isSelected={isSelected}
        hasClips={hasClips}
        onSelect={onSelect}
        onChange={onChange}
        onRemove={onRemove}
        dragListeners={listeners}
        dragAttributes={attributes}
      />
    </div>
  );
}
