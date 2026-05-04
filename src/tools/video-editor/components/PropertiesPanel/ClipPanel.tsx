import { useMemo, useState } from 'react';
import { AudioWaveform, Pencil, Plus, RefreshCw, Trash2, Volume2, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/components/ui/contracts/cn';
import { Input } from '@/shared/components/ui/input';
import { MediaVariantPicker } from '@/shared/components/MediaVariantPicker';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants';
import { NumberInput } from '@/shared/components/ui/number-input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Slider } from '@/shared/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Textarea } from '@/shared/components/ui/textarea';
import { ParameterControls, getDefaultValues } from '@/tools/video-editor/components/ParameterControls';
import { SequenceParamEditor } from '@/tools/video-editor/components/PropertiesPanel/SequenceParamEditor';
import {
  clipTypeUsesHoldTiming,
  getRegisteredClipTypeDescriptor,
  getClipTypeOverlayBehavior,
  isClipTypeCommandAvailable,
} from '@/tools/video-editor/clip-types';
import { isSequenceParamsSchema } from '@/tools/video-editor/clip-types/defineClipType';
import { continuousEffectTypes, entranceEffectTypes, exitEffectTypes } from '@/tools/video-editor/effects';
import { EffectCreatorPanel } from '@/tools/video-editor/components/EffectCreatorPanel';
import { useEffectResources, type EffectCategory, type EffectResource } from '@/tools/video-editor/hooks/useEffectResources';
import type { ClipTab } from '@/tools/video-editor/hooks/useEditorPreferences';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data';
import { getVisibleClipTabs } from '@/tools/video-editor/lib/clip-inspector';
import type { TimelineDeviceClass, TimelineInteractionMode } from '@/tools/video-editor/lib/mobile-interaction-model';
import { resolveAvailableClipType } from '@/tools/video-editor/sequences/registry';
import type { ResolvedTimelineClip, ResolvedTimelineConfig, TrackDefinition } from '@/tools/video-editor/types';

export { getVisibleClipTabs } from '@/tools/video-editor/lib/clip-inspector';

interface ClipPanelProps {
  clip: ResolvedTimelineClip | null;
  track: TrackDefinition | null;
  deviceClass: TimelineDeviceClass;
  interactionMode: TimelineInteractionMode;
  precisionEnabled: boolean;
  hasPredecessor: boolean;
  onChange: (patch: Partial<ClipMeta> & { at?: number }) => void;
  onResetPosition: () => void;
  onClose: () => void;
  onDelete?: () => void;
  onToggleMute: () => void;
  onDetachAudio?: () => void;
  onSplitAtPlayhead: () => void;
  onMoveTrackUp: () => void;
  onMoveTrackDown: () => void;
  onSetInteractionMode: (mode: 'move' | 'trim') => void;
  onSetPrecisionEnabled: (enabled: boolean) => void;
  compositionWidth: number;
  compositionHeight: number;
  registry: ResolvedTimelineConfig['registry'];
  activeTab: ClipTab;
  setActiveTab: (tab: ClipTab) => void;
  isVariantStale?: boolean;
  onUpdateVariant?: () => void;
  onDismissStale?: () => void;
  onApplyVariant?: (variant: GenerationVariant) => void | Promise<void>;
  onAddVariantAsGeneration?: (variant: GenerationVariant) => void | Promise<void>;
  isAddingVariantAsGeneration?: (variantId: string) => boolean;
  timelineFps?: number;
}

export const NO_EFFECT = '__none__';
export const TAB_COLUMNS_CLASS = {
  2: 'grid-cols-2',
  3: 'grid-cols-3',
  4: 'grid-cols-4',
  5: 'grid-cols-5',
} as const;

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-xs font-medium text-muted-foreground">{children}</div>;
}

/** Find a resource-based effect by its `custom:{id}` type string */
function findEffectResourceByType(
  type: string | undefined,
  effects: EffectResource[],
): EffectResource | undefined {
  if (!type?.startsWith('custom:')) return undefined;
  const id = type.slice(7);
  return effects.find((e) => e.id === id);
}

function getDefaultEffectParams(
  type: string | undefined,
  effects: EffectResource[],
): Record<string, unknown> | undefined {
  const effect = findEffectResourceByType(type, effects);
  return effect?.parameterSchema ? getDefaultValues(effect.parameterSchema) : undefined;
}

function getMergedEffectParams(
  effect: EffectResource | undefined,
  storedParams: Record<string, unknown> | undefined,
): Record<string, unknown> {
  return {
    ...getDefaultValues(effect?.parameterSchema ?? []),
    ...(storedParams ?? {}),
  };
}

/** Returns a display label for an effect type — handles both built-in and custom */
function getEffectDisplayLabel(type: string | undefined, effects: EffectResource[]): string | null {
  if (!type || type === NO_EFFECT) return null;
  if (!type.startsWith('custom:')) return type; // built-in: just use the name
  const effect = findEffectResourceByType(type, effects);
  if (effect) return effect.name;
  const id = type.slice(7);
  return `Effect ${id.slice(0, 8)}… (missing)`;
}

/** Check if a custom effect type is already in the resource list */
function isCustomEffectInList(type: string | undefined, categoryEffects: EffectResource[]): boolean {
  if (!type?.startsWith('custom:')) return true;
  const id = type.slice(7);
  return categoryEffects.some((e) => e.id === id);
}

function EffectSelectValue({ type, effects }: { type: string | undefined; effects: EffectResource[] }) {
  const label = getEffectDisplayLabel(type, effects);
  return <SelectValue placeholder="None">{label ?? 'None'}</SelectValue>;
}

function hasParameterSchema(effect: EffectResource | undefined): effect is EffectResource & { parameterSchema: NonNullable<EffectResource['parameterSchema']> } {
  return Boolean(effect?.parameterSchema?.length);
}

function isAudioReactiveEffect(effect: EffectResource): boolean {
  return effect.code?.includes('useAudioReactive') || effect.code?.includes('useAudioParam')
    || effect.parameterSchema?.some((p) => p.type === 'audio-binding') === true;
}

function AudioReactiveIcon() {
  return <AudioWaveform className="inline-block h-3 w-3 shrink-0 text-muted-foreground" />;
}

export function ClipPanel({
  clip,
  track,
  deviceClass,
  interactionMode,
  precisionEnabled,
  hasPredecessor,
  onChange,
  onResetPosition,
  onClose,
  onDelete,
  onToggleMute,
  onDetachAudio,
  onSplitAtPlayhead,
  onMoveTrackUp,
  onMoveTrackDown,
  onSetInteractionMode,
  onSetPrecisionEnabled,
  compositionWidth,
  compositionHeight,
  registry,
  activeTab,
  setActiveTab,
  isVariantStale,
  onUpdateVariant,
  onDismissStale,
  onApplyVariant,
  onAddVariantAsGeneration,
  isAddingVariantAsGeneration,
  timelineFps,
}: ClipPanelProps) {
  const effectResources = useEffectResources();
  const [creatorOpen, setCreatorOpen] = useState(false);
  const [editingEffect, setEditingEffect] = useState<EffectResource | null>(null);
  const canCreateEffects = effectResources.canCreateEffect;
  const canEditEffects = effectResources.canUpdateEffect;
  const visibleTabs = useMemo(() => getVisibleClipTabs(clip, track), [clip, track]);
  const clipDescriptor = clip
    ? getRegisteredClipTypeDescriptor(clip.clipType)
    : undefined;
  const clipTypeResolution = resolveAvailableClipType(clip?.clipType);
  const isEffectLayer = clipDescriptor?.renderCapabilities.previewRoute === 'effect-layer';
  const isSequenceClip = Boolean(clipDescriptor && isSequenceParamsSchema(clipDescriptor.paramsSchema));
  const overlayBehavior = getClipTypeOverlayBehavior(clipDescriptor);
  const supportsInlineTextEdit = overlayBehavior.supportsInlineTextEdit;
  const commandContext = useMemo(() => (
    clip
      ? { clip, track, selectedClipIds: [clip.id] }
      : { clip, track, selectedClipIds: [] }
  ), [clip, track]);
  const canSplit = Boolean(
    clipDescriptor && isClipTypeCommandAvailable(clipDescriptor, 'split', commandContext),
  );
  const canMoveTrack = Boolean(
    clipDescriptor && isClipTypeCommandAvailable(clipDescriptor, 'move-track-up', commandContext),
  );
  const canToggleMute = Boolean(
    clipDescriptor && isClipTypeCommandAvailable(clipDescriptor, 'toggle-mute', commandContext),
  );
  const canDetachAudio = Boolean(
    clipDescriptor && isClipTypeCommandAvailable(clipDescriptor, 'detach-audio', commandContext),
  );
  const entranceEffect = findEffectResourceByType(clip?.entrance?.type, effectResources.effects);
  const exitEffect = findEffectResourceByType(clip?.exit?.type, effectResources.effects);
  const continuousEffect = findEffectResourceByType(clip?.continuous?.type, effectResources.effects);
  const showInspectorActions = deviceClass !== 'desktop';

  if (!clip) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        Select a clip to edit timing, position, audio, text, or effects.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3 rounded-xl border border-border bg-card/70 p-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">
            {isEffectLayer
              ? (getEffectDisplayLabel(clip.continuous?.type, effectResources.effects) ?? 'Effect Layer')
              : isSequenceClip
                ? (clipDescriptor?.label ?? clip.clipType ?? clip.id)
                : supportsInlineTextEdit
                  ? (clip.text?.content || clipDescriptor?.label || clip.id)
                  : (clip.asset || clipDescriptor?.label || clip.id)}
          </div>
          <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            {clip.clipType ?? 'media'} · {track?.label ?? clip.track}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {clip.assetEntry?.generationId && (
            <MediaVariantPicker
              generationId={clip.assetEntry.generationId}
              currentVariantId={clip.assetEntry.variantId ?? null}
              onVariantApplied={onApplyVariant}
              onAddVariantAsGeneration={onAddVariantAsGeneration}
              isAddingVariantAsGeneration={isAddingVariantAsGeneration}
              inline
              defaultMediaKind={clip.assetEntry.type?.startsWith('video') ? 'video' : 'image'}
            />
          )}
          {onDelete && (
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={onDelete}>
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
          <Button type="button" variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
            ×
          </Button>
        </div>
      </div>

      {isVariantStale && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
          <RefreshCw className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">Variant outdated</span>
          {onUpdateVariant && (
            <Button type="button" variant="ghost" size="sm" className="h-6 gap-1 px-2 text-xs text-amber-200 hover:bg-amber-500/20 hover:text-amber-100" onClick={onUpdateVariant}>
              Update
            </Button>
          )}
          {onDismissStale && (
            <Button type="button" variant="ghost" size="icon" className="h-6 w-6 text-amber-200/60 hover:bg-amber-500/20 hover:text-amber-100" onClick={onDismissStale}>
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      )}

      {showInspectorActions && (
        <div className="rounded-xl border border-sky-400/40 bg-sky-500/10 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-foreground">Inspector-first actions</div>
              <div className="mt-1 text-xs text-muted-foreground">
                Use explicit controls for trim, move, track changes, split, mute, and delete when touch editing needs to stay stable.
              </div>
            </div>
            <div className="text-[11px] uppercase tracking-[0.12em] text-sky-100">
              {interactionMode}
              {precisionEnabled ? ' + precision' : ''}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button type="button" variant="secondary" size="sm" className="justify-start" onClick={() => { onSetInteractionMode('trim'); setActiveTab('timing'); }}>
              Trim in inspector
            </Button>
            <Button type="button" variant="secondary" size="sm" className="justify-start" onClick={() => { onSetInteractionMode('move'); setActiveTab('timing'); }}>
              Move in inspector
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={onMoveTrackUp} disabled={!canMoveTrack}>
              Track up
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={onMoveTrackDown} disabled={!canMoveTrack}>
              Track down
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={onSplitAtPlayhead} disabled={!canSplit}>
              Split at playhead
            </Button>
            <Button type="button" variant="outline" size="sm" className="justify-start" onClick={onToggleMute} disabled={!canToggleMute}>
              Mute or unmute
            </Button>
            <Button type="button" variant={precisionEnabled ? 'secondary' : 'outline'} size="sm" className="justify-start" onClick={() => onSetPrecisionEnabled(!precisionEnabled)}>
              {precisionEnabled ? 'Disable precision' : 'Enable precision'}
            </Button>
            {onDelete && (
              <Button type="button" variant="destructive" size="sm" className="justify-start" onClick={onDelete}>
                Delete clip
              </Button>
            )}
          </div>
        </div>
      )}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as ClipTab)}>
        <TabsList className={cn('grid w-full bg-muted/60', TAB_COLUMNS_CLASS[visibleTabs.length as keyof typeof TAB_COLUMNS_CLASS] ?? 'grid-cols-4')}>
          {visibleTabs.includes('effects') && <TabsTrigger value="effects">{isSequenceClip ? 'Sequence' : 'Effects'}</TabsTrigger>}
          {visibleTabs.includes('timing') && <TabsTrigger value="timing">Timing</TabsTrigger>}
          {visibleTabs.includes('position') && <TabsTrigger value="position">Position</TabsTrigger>}
          {visibleTabs.includes('audio') && <TabsTrigger value="audio">Audio</TabsTrigger>}
          {visibleTabs.includes('text') && <TabsTrigger value="text">Text</TabsTrigger>}
        </TabsList>

        {visibleTabs.includes('effects') && (
          <TabsContent value="effects" className="space-y-3">
            {!clipDescriptor && clip.clipType ? (
              <div className="rounded-xl border border-dashed border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-100">
                {clip.clipType} is not registered in the clip-type registry for this editor build.
              </div>
            ) : isSequenceClip && clipTypeResolution.status === 'available' ? (
              <SequenceParamEditor
                clipType={clip.clipType}
                params={clip.params}
                registry={registry}
                onChange={(nextParams) => onChange({ params: nextParams })}
              />
            ) : isSequenceClip && clipTypeResolution.status === 'unavailable' ? (
              <div className="rounded-xl border border-dashed border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-100">
                {clip.clipType} is trusted in the clip-type registry, but its render component is not available in this editor build.
              </div>
            ) : (
              <>
            <div className="grid gap-3 md:grid-cols-2">
              {!isEffectLayer && (
                <div className="space-y-2">
                <FieldLabel>Entrance</FieldLabel>
                <Select
                  value={clip.entrance?.type ?? NO_EFFECT}
                  onValueChange={(value) => onChange({
                    entrance: value === NO_EFFECT
                      ? undefined
                      : {
                          type: value,
                          duration: clip.entrance?.duration ?? 0.4,
                          params: getDefaultEffectParams(value, effectResources.effects),
                        },
                  })}
                >
                  <SelectTrigger><EffectSelectValue type={clip.entrance?.type} effects={effectResources.effects} /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_EFFECT}>None</SelectItem>
                    {entranceEffectTypes.map((effect) => <SelectItem key={effect} value={effect}>{effect}</SelectItem>)}
                    {(effectResources.entrance.length > 0 || (clip.entrance?.type?.startsWith('custom:') && !isCustomEffectInList(clip.entrance.type, effectResources.entrance))) && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        {!isCustomEffectInList(clip.entrance?.type, effectResources.entrance) && clip.entrance?.type && (
                          <SelectItem value={clip.entrance.type}>
                            <span className="text-muted-foreground">{getEffectDisplayLabel(clip.entrance.type, effectResources.effects) ?? clip.entrance.type}</span>
                          </SelectItem>
                        )}
                        {effectResources.entrance.map((effect) => (
                          <SelectItem key={`custom:${effect.id}`} value={`custom:${effect.id}`}>
                            <span className="flex items-center gap-1.5">{isAudioReactiveEffect(effect) && <AudioReactiveIcon />}{effect.name}</span>
                          </SelectItem>
                        ))}
                      </>
                    )}
                  </SelectContent>
                </Select>
                {entranceEffect && canEditEffects && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 gap-1 text-xs"
                    onClick={() => {
                      setEditingEffect(entranceEffect);
                      setCreatorOpen(true);
                    }}
                  >
                    <Pencil className="h-3 w-3" /> Edit
                  </Button>
                )}
                {hasParameterSchema(entranceEffect) && (
                  <ParameterControls
                    schema={entranceEffect.parameterSchema}
                    values={getMergedEffectParams(entranceEffect, clip.entrance?.params)}
                    onChange={(paramName, value) => onChange({
                      entrance: {
                        type: clip.entrance?.type ?? `custom:${entranceEffect.id}`,
                        duration: clip.entrance?.duration ?? 0.4,
                        params: {
                          ...(clip.entrance?.params ?? {}),
                          [paramName]: value,
                        },
                      },
                    })}
                  />
                )}
              </div>
              )}
              {!isEffectLayer && (
                <div className="space-y-2">
                <FieldLabel>Exit</FieldLabel>
                <Select
                  value={clip.exit?.type ?? NO_EFFECT}
                  onValueChange={(value) => onChange({
                    exit: value === NO_EFFECT
                      ? undefined
                      : {
                          type: value,
                          duration: clip.exit?.duration ?? 0.4,
                          params: getDefaultEffectParams(value, effectResources.effects),
                        },
                  })}
                >
                  <SelectTrigger><EffectSelectValue type={clip.exit?.type} effects={effectResources.effects} /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_EFFECT}>None</SelectItem>
                    {exitEffectTypes.map((effect) => <SelectItem key={effect} value={effect}>{effect}</SelectItem>)}
                    {(effectResources.exit.length > 0 || (clip.exit?.type?.startsWith('custom:') && !isCustomEffectInList(clip.exit.type, effectResources.exit))) && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        {!isCustomEffectInList(clip.exit?.type, effectResources.exit) && clip.exit?.type && (
                          <SelectItem value={clip.exit.type}>
                            <span className="text-muted-foreground">{getEffectDisplayLabel(clip.exit.type, effectResources.effects) ?? clip.exit.type}</span>
                          </SelectItem>
                        )}
                        {effectResources.exit.map((effect) => (
                          <SelectItem key={`custom:${effect.id}`} value={`custom:${effect.id}`}>
                            <span className="flex items-center gap-1.5">{isAudioReactiveEffect(effect) && <AudioReactiveIcon />}{effect.name}</span>
                          </SelectItem>
                        ))}
                      </>
                    )}
                  </SelectContent>
                </Select>
                {exitEffect && canEditEffects && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 gap-1 text-xs"
                    onClick={() => {
                      setEditingEffect(exitEffect);
                      setCreatorOpen(true);
                    }}
                  >
                    <Pencil className="h-3 w-3" /> Edit
                  </Button>
                )}
                {hasParameterSchema(exitEffect) && (
                  <ParameterControls
                    schema={exitEffect.parameterSchema}
                    values={getMergedEffectParams(exitEffect, clip.exit?.params)}
                    onChange={(paramName, value) => onChange({
                      exit: {
                        type: clip.exit?.type ?? `custom:${exitEffect.id}`,
                        duration: clip.exit?.duration ?? 0.4,
                        params: {
                          ...(clip.exit?.params ?? {}),
                          [paramName]: value,
                        },
                      },
                    })}
                  />
                )}
              </div>
              )}
              <div className="space-y-2 md:col-span-2">
                <FieldLabel>Continuous</FieldLabel>
                <Select
                  value={clip.continuous?.type ?? NO_EFFECT}
                  onValueChange={(value) => onChange({
                    continuous: value === NO_EFFECT
                      ? undefined
                      : {
                          type: value,
                          intensity: clip.continuous?.intensity ?? 0.5,
                          params: getDefaultEffectParams(value, effectResources.effects),
                        },
                  })}
                >
                  <SelectTrigger><EffectSelectValue type={clip.continuous?.type} effects={effectResources.effects} /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_EFFECT}>None</SelectItem>
                    {continuousEffectTypes.map((effect) => <SelectItem key={effect} value={effect}>{effect}</SelectItem>)}
                    {(effectResources.continuous.length > 0 || (clip.continuous?.type?.startsWith('custom:') && !isCustomEffectInList(clip.continuous.type, effectResources.continuous))) && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        {!isCustomEffectInList(clip.continuous?.type, effectResources.continuous) && clip.continuous?.type && (
                          <SelectItem value={clip.continuous.type}>
                            <span className="text-muted-foreground">{getEffectDisplayLabel(clip.continuous.type, effectResources.effects) ?? clip.continuous.type}</span>
                          </SelectItem>
                        )}
                        {effectResources.continuous.map((effect) => (
                          <SelectItem key={`custom:${effect.id}`} value={`custom:${effect.id}`}>
                            <span className="flex items-center gap-1.5">{isAudioReactiveEffect(effect) && <AudioReactiveIcon />}{effect.name}</span>
                          </SelectItem>
                        ))}
                      </>
                    )}
                  </SelectContent>
                </Select>
                {continuousEffect && canEditEffects && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 gap-1 text-xs"
                    onClick={() => {
                      setEditingEffect(continuousEffect);
                      setCreatorOpen(true);
                    }}
                  >
                    <Pencil className="h-3 w-3" /> Edit
                  </Button>
                )}
                {hasParameterSchema(continuousEffect) && (
                  <ParameterControls
                    schema={continuousEffect.parameterSchema}
                    values={getMergedEffectParams(continuousEffect, clip.continuous?.params)}
                    onChange={(paramName, value) => onChange({
                      continuous: {
                        type: clip.continuous?.type ?? `custom:${continuousEffect.id}`,
                        intensity: clip.continuous?.intensity ?? 0.5,
                        params: {
                          ...(clip.continuous?.params ?? {}),
                          [paramName]: value,
                        },
                      },
                    })}
                  />
                )}
              </div>
            </div>
            {isEffectLayer && !clip.continuous && (
              <div className="rounded-lg border border-dashed border-violet-400/40 bg-violet-500/10 p-3 text-sm text-violet-100">
                Select a continuous effect to turn this layer into an active adjustment clip.
              </div>
            )}
            {canCreateEffects && (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="gap-1.5"
                onClick={() => {
                  setEditingEffect(null);
                  setCreatorOpen(true);
                }}
              >
                <Plus className="h-3.5 w-3.5" />
                Create Effect
              </Button>
            )}
            <EffectCreatorPanel
              open={creatorOpen}
              onOpenChange={setCreatorOpen}
              editingEffect={editingEffect}
              previewAssetSrc={clip?.assetEntry?.src}
              timelineFps={timelineFps}
              onSaved={(resourceId, savedCategory, defaultParams) => {
                const effectType = `custom:${resourceId}`;
                const params = Object.keys(defaultParams).length > 0 ? defaultParams : undefined;
                if (isEffectLayer) {
                  if (savedCategory !== 'continuous') {
                    return;
                  }
                  onChange({ continuous: { type: effectType, intensity: clip.continuous?.intensity ?? 0.5, params } });
                  return;
                }
                if (!isEffectLayer && savedCategory === 'entrance') {
                  onChange({ entrance: { type: effectType, duration: clip.entrance?.duration ?? 0.4, params } });
                } else if (!isEffectLayer && savedCategory === 'exit') {
                  onChange({ exit: { type: effectType, duration: clip.exit?.duration ?? 0.4, params } });
                } else {
                  onChange({ continuous: { type: effectType, intensity: clip.continuous?.intensity ?? 0.5, params } });
                }
              }}
            />
              </>
            )}
          </TabsContent>
        )}

        {visibleTabs.includes('timing') && (
          <TabsContent value="timing" className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <FieldLabel>Start (seconds)</FieldLabel>
                <NumberInput value={clip.at} step={0.1} onChange={(value) => { if (value !== null) onChange({ at: value }); }} />
              </div>
              {clipTypeUsesHoldTiming(clipDescriptor) ? (
                <div className="space-y-2">
                  <FieldLabel>Duration (seconds)</FieldLabel>
                  <NumberInput
                    value={clip.hold ?? (clipDescriptor && clipDescriptor.hold.kind !== 'unsupported' ? clipDescriptor.hold.defaultSeconds : 5)}
                    min={clipDescriptor?.hold.kind !== 'unsupported' ? clipDescriptor.hold.minSeconds : 0.1}
                    max={clipDescriptor?.hold.kind !== 'unsupported' ? clipDescriptor.hold.maxSeconds : undefined}
                    step={clipDescriptor?.hold.kind !== 'unsupported' ? clipDescriptor.hold.stepSeconds : 0.1}
                    onChange={(value) => { if (value !== null) onChange({ hold: value }); }}
                  />
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    <FieldLabel>Speed</FieldLabel>
                    <NumberInput value={clip.speed ?? 1} min={0.1} step={0.1} onChange={(value) => { if (value !== null) onChange({ speed: value }); }} />
                  </div>
                  <div className="space-y-2">
                    <FieldLabel>Source In</FieldLabel>
                    <NumberInput value={clip.from ?? 0} min={0} step={0.1} onChange={(value) => { if (value !== null) onChange({ from: value }); }} />
                  </div>
                  <div className="space-y-2">
                    <FieldLabel>Source Out</FieldLabel>
                    <NumberInput value={clip.to ?? clip.assetEntry?.duration ?? 5} min={0} step={0.1} onChange={(value) => { if (value !== null) onChange({ to: value }); }} />
                  </div>
                </>
              )}
            </div>
          </TabsContent>
        )}

        {visibleTabs.includes('position') && (
          <TabsContent value="position" className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <FieldLabel>X</FieldLabel>
                <NumberInput value={clip.x ?? 0} onChange={(value) => { if (value !== null) onChange({ x: value }); }} />
              </div>
              <div className="space-y-2">
                <FieldLabel>Y</FieldLabel>
                <NumberInput value={clip.y ?? 0} onChange={(value) => { if (value !== null) onChange({ y: value }); }} />
              </div>
              <div className="space-y-2">
                <FieldLabel>Width</FieldLabel>
                <NumberInput value={clip.width ?? compositionWidth} min={0} max={compositionWidth} onChange={(value) => { if (value !== null) onChange({ width: value }); }} />
              </div>
              <div className="space-y-2">
                <FieldLabel>Height</FieldLabel>
                <NumberInput value={clip.height ?? compositionHeight} min={0} max={compositionHeight} onChange={(value) => { if (value !== null) onChange({ height: value }); }} />
              </div>
            </div>
            <div className="space-y-2">
              <FieldLabel>Opacity</FieldLabel>
              <Slider
                value={[clip.opacity ?? 1]}
                min={0}
                max={1}
                step={0.05}
                onValueChange={(value) => onChange({ opacity: value })}
              />
            </div>
            <Button type="button" variant="outline" size="sm" onClick={onResetPosition}>
              Reset position
            </Button>
          </TabsContent>
        )}

        {visibleTabs.includes('audio') && (
          <TabsContent value="audio" className="space-y-3">
            <div className="rounded-lg border border-border bg-card/70 p-3">
              <div className="mb-2 flex items-center gap-2 text-sm text-foreground">
                <Volume2 className="h-4 w-4" />
                Volume
              </div>
              <Slider
                value={[clip.volume ?? 1]}
                min={0}
                max={1}
                step={0.05}
                onValueChange={(value) => onChange({ volume: value })}
              />
              <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={onToggleMute} disabled={!canToggleMute}>
                Toggle mute
              </Button>
              {canDetachAudio && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={onDetachAudio}
                  disabled={!onDetachAudio}
                >
                  Detach audio
                </Button>
              )}
            </div>
          </TabsContent>
        )}

        {visibleTabs.includes('text') && (
          <TabsContent value="text" className="space-y-3">
            {supportsInlineTextEdit ? (
              <>
                <Textarea
                  value={clip.text?.content ?? ''}
                  onChange={(event) => onChange({ text: { ...(clip.text ?? { content: '' }), content: event.target.value } })}
                  rows={5}
                />
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-2">
                    <FieldLabel>Font size</FieldLabel>
                    <NumberInput
                      value={clip.text?.fontSize ?? 64}
                      min={1}
                      step={1}
                      onChange={(value) => {
                        if (value !== null) {
                          onChange({ text: { ...(clip.text ?? { content: '' }), fontSize: value } });
                        }
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <FieldLabel>Color</FieldLabel>
                    <Input
                      type="color"
                      value={clip.text?.color ?? '#ffffff'}
                      onChange={(event) => onChange({ text: { ...(clip.text ?? { content: '' }), color: event.target.value } })}
                    />
                  </div>
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                The selected clip is not a text clip.
              </div>
            )}
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
