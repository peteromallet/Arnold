import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, AudioWaveform, Globe, Lock, Monitor, RefreshCw, Server, Trash2, Volume2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { Input } from '@/shared/components/ui/input.tsx';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select.tsx';
import { Slider } from '@/shared/components/ui/slider.tsx';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs.tsx';
import { getDefaultValues } from '@/tools/video-editor/components/ParameterControls.tsx';
import {
  FieldLabel,
  NO_EFFECT,
  NO_TRANSITION,
  TAB_COLUMNS_CLASS,
} from '@/tools/video-editor/components/PropertiesPanel/ClipPanel.tsx';
import { continuousEffectTypes, entranceEffectTypes, exitEffectTypes } from '@/tools/video-editor/effects/index.tsx';
import { useEffectResources } from '@/tools/video-editor/hooks/useEffectResources.ts';
import type { ClipTab } from '@/tools/video-editor/hooks/useEditorPreferences.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';
import type { ResolvedTimelineClip, ClipTransition } from '@/tools/video-editor/types/index.ts';
import {
  useOptionalTransitionRegistryContext,
  type TransitionRegistryRecord,
} from '@/tools/video-editor/transitions/registry/index.ts';
import {
  listTransitions,
  resolveTransition,
  createTransitionSnapshot,
  materializeTransitionDefaults,
} from '@/tools/video-editor/transitions/catalog.ts';

const MIXED_SELECT_VALUE = '__mixed__';

type BulkScalarPatch = Partial<Pick<ClipMeta, 'speed' | 'from' | 'to' | 'x' | 'y' | 'width' | 'height' | 'opacity' | 'volume'>>;
type BulkDraftField = 'speed' | 'from' | 'to' | 'x' | 'y' | 'width' | 'height' | 'fontSize' | 'color';
type BulkNumberDraftField = Exclude<BulkDraftField, 'color'>;
type BulkDrafts = Record<BulkNumberDraftField, number | null> & { color: string };

export interface BulkClipPanelProps {
  clips: ResolvedTimelineClip[];
  visibleTabs: ClipTab[];
  compositionWidth: number;
  compositionHeight: number;
  sharedEntrance: ResolvedTimelineClip['entrance'] | null;
  sharedExit: ResolvedTimelineClip['exit'] | null;
  sharedContinuous: ResolvedTimelineClip['continuous'] | null;
  sharedText: ResolvedTimelineClip['text'] | null;
  sharedTransition: ClipTransition | null;
  sharedEntranceType: string | null;
  sharedExitType: string | null;
  sharedContinuousType: string | null;
  sharedTransitionType: string | null;
  sharedSpeed: number | null;
  sharedFrom: number | null;
  sharedTo: number | null;
  sharedX: number | null;
  sharedY: number | null;
  sharedWidth: number | null;
  sharedHeight: number | null;
  sharedOpacity: number | null;
  sharedVolume: number | null;
  sharedFontSize: number | null;
  sharedTextColor: string | null;
  sharedTransitionDuration: number | null;
  onChange: (patch: BulkScalarPatch) => void;
  onChangeDeep: (patchFn: (existing: ClipMeta) => Partial<ClipMeta>) => void;
  onResetPosition: () => void;
  onToggleMute: () => void;
  onClose: () => void;
  activeTab: ClipTab;
  setActiveTab: (tab: ClipTab) => void;
}

const toNumberDraft = (value: number | null | undefined): number | null => (typeof value === 'number' ? value : null);

const buildDrafts = (props: BulkClipPanelProps): BulkDrafts => ({
  speed: toNumberDraft(props.sharedSpeed),
  from: toNumberDraft(props.sharedFrom),
  to: toNumberDraft(props.sharedTo),
  x: toNumberDraft(props.sharedX),
  y: toNumberDraft(props.sharedY),
  width: toNumberDraft(props.sharedWidth),
  height: toNumberDraft(props.sharedHeight),
  fontSize: toNumberDraft(props.sharedFontSize ?? props.sharedText?.fontSize),
  color: props.sharedTextColor ?? props.sharedText?.color ?? '',
});

function isAudioReactiveEffect(effect: { code?: string; parameterSchema?: Array<{ type: string }> }): boolean {
  return effect.code?.includes('useAudioReactive') === true || effect.code?.includes('useAudioParam') === true
    || effect.parameterSchema?.some((p) => p.type === 'audio-binding') === true;
}

function AudioReactiveIcon() {
  return <AudioWaveform className="inline-block h-3 w-3 shrink-0 text-muted-foreground" />;
}

/** Check if an effect resource's registry status is 'error' (invalid schema, etc.). */
function isEffectInError(effect: { registryStatus?: string }): boolean {
  return effect.registryStatus === 'error';
}

/** Check if an effect resource is read-only (bundled-extension per SD3). */
function isReadOnlyEffect(effect: { readOnly?: boolean }): boolean {
  return effect.readOnly === true;
}

/** Returns a short provenance label for display in effect selectors. */
function getProvenanceLabel(effect: { provenance?: string }): string | null {
  switch (effect.provenance) {
    case 'bundled-extension':
      return 'Extension';
    case 'external-catalog':
      return 'Catalog';
    case 'db-resource':
      return 'DB';
    case 'ai-generated':
      return 'AI';
    case 'local-storage-draft':
      return 'Draft';
    case 'trusted-loader':
      return 'Trusted';
    default:
      return null;
  }
}

/** Returns blocked export routes for an effect's renderability. */
function getBlockedRoutes(effect: { renderability?: { capabilities?: Array<{ route: string; status: string }> } }): string[] {
  if (!effect.renderability?.capabilities) return [];
  return effect.renderability.capabilities
    .filter((cap) => cap.route !== 'preview' && cap.status === 'blocked')
    .map((cap) => cap.route);
}

function getDefaultEffectParams(
  type: string,
  effects: ReturnType<typeof useEffectResources>['effects'],
): Record<string, unknown> | undefined {
  if (!type.startsWith('custom:')) {
    return undefined;
  }

  const resourceId = type.slice(7);
  const effect = effects.find((entry) => entry.id === resourceId);
  return effect?.parameterSchema ? getDefaultValues(effect.parameterSchema) : undefined;
}

/** Returns a short provenance label for display in transition selectors. */
function getTransitionProvenanceLabel(record: TransitionRegistryRecord): string | null {
  switch (record.provenance) {
    case 'built-in':
      return 'Built-in';
    case 'bundled-extension':
      return 'Extension';
    case 'external-catalog':
      return 'Catalog';
    case 'db-resource':
      return 'DB';
    case 'ai-generated':
      return 'AI';
    case 'local-storage-draft':
      return 'Draft';
    case 'trusted-loader':
      return 'Trusted';
    default:
      return null;
  }
}

/** Returns rendered export routes that are blocked for a transition record. */
function getTransitionBlockedRoutes(record: TransitionRegistryRecord): string[] {
  if (!record.renderability?.capabilities) return [];
  return record.renderability.capabilities
    .filter((cap) => cap.route !== 'preview' && cap.status === 'blocked')
    .map((cap) => cap.route);
}

export function BulkClipPanel(props: BulkClipPanelProps) {
  const {
    clips,
    visibleTabs,
    compositionWidth,
    compositionHeight,
    sharedEntrance,
    sharedExit,
    sharedContinuous,
    sharedText,
    sharedTransition,
    sharedEntranceType,
    sharedExitType,
    sharedContinuousType,
    sharedTransitionType,
    sharedTransitionDuration,
    sharedOpacity,
    sharedVolume,
    onChange,
    onChangeDeep,
    onResetPosition,
    onToggleMute,
    onClose,
    activeTab,
    setActiveTab,
  } = props;
  const effectResources = useEffectResources();
  const [drafts, setDrafts] = useState<BulkDrafts>(() => buildDrafts(props));

  // Transition registry (T12: bulk transition controls)
  const transitionRegistryContext = useOptionalTransitionRegistryContext();
  const mergedTransitionSnapshot = useMemo(
    () => createTransitionSnapshot(transitionRegistryContext?.snapshot),
    [transitionRegistryContext?.snapshot],
  );
  const availableTransitions = useMemo(
    () => listTransitions(mergedTransitionSnapshot),
    [mergedTransitionSnapshot],
  );
  const resolvedTransitionRecord = useMemo(() => {
    if (!sharedTransitionType || sharedTransitionType === NO_TRANSITION || sharedTransitionType === NO_EFFECT) return undefined;
    return resolveTransition(sharedTransitionType, mergedTransitionSnapshot);
  }, [sharedTransitionType, mergedTransitionSnapshot]);
  const isTransitionUnresolvable =
    sharedTransitionType != null &&
    sharedTransitionType !== NO_TRANSITION &&
    sharedTransitionType !== NO_EFFECT &&
    !resolvedTransitionRecord;

  useEffect(() => {
    setDrafts(buildDrafts(props));
  }, [
    props.compositionHeight,
    props.compositionWidth,
    props.sharedFrom,
    props.sharedFontSize,
    props.sharedHeight,
    props.sharedSpeed,
    props.sharedText,
    props.sharedTextColor,
    props.sharedTo,
    props.sharedWidth,
    props.sharedX,
    props.sharedY,
  ]);

  useEffect(() => {
    if (!visibleTabs.includes(activeTab)) {
      setActiveTab('effects');
    }
  }, [activeTab, setActiveTab, visibleTabs]);

  const setNumberDraft = (field: BulkNumberDraftField, value: number | null) => {
    setDrafts((current) => ({ ...current, [field]: value }));
  };

  const setColorDraft = (value: string) => {
    setDrafts((current) => ({ ...current, color: value }));
  };

  const commitScalarField = (field: Exclude<BulkDraftField, 'fontSize' | 'color'>, value: number | null) => {
    if (value === null || !Number.isFinite(value)) {
      return;
    }

    switch (field) {
      case 'speed':
        onChange({ speed: Math.max(0.05, value) });
        return;
      case 'from':
        onChange({ from: Math.max(0, value) });
        return;
      case 'to':
        onChange({ to: Math.max(0, value) });
        return;
      case 'x':
        onChange({ x: value });
        return;
      case 'y':
        onChange({ y: value });
        return;
      case 'width':
        onChange({ width: Math.min(compositionWidth, Math.max(0, value)) });
        return;
      case 'height':
        onChange({ height: Math.min(compositionHeight, Math.max(0, value)) });
        return;
      default:
        return;
    }
  };

  const commitTextFontSize = (value: number | null) => {
    if (value === null || !Number.isFinite(value)) {
      return;
    }

    onChangeDeep((meta) => ({
      text: {
        ...(meta.text ?? sharedText ?? { content: '' }),
        fontSize: Math.max(1, value),
      },
    }));
  };

  const commitTextColor = (value: string) => {
    const normalized = value.trim();
    if (normalized === '') {
      return;
    }

    onChangeDeep((meta) => ({
      text: {
        ...(meta.text ?? sharedText ?? { content: '' }),
        color: normalized,
      },
    }));
  };

  const renderNumberInput = (
    field: Exclude<BulkDraftField, 'fontSize' | 'color'>,
    label: string,
    options?: { min?: number; max?: number; step?: number },
  ) => (
    <div className="space-y-2">
      <FieldLabel>{label}</FieldLabel>
      <NumberInput
        min={options?.min}
        max={options?.max}
        step={options?.step}
        value={drafts[field]}
        placeholder="Mixed"
        onChange={(value) => setNumberDraft(field, value)}
        onValueCommitted={(value) => commitScalarField(field, value)}
      />
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3 rounded-xl border border-border bg-card/70 p-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">
            {clips.length} clips selected
          </div>
          <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            Bulk settings
          </div>
        </div>
        <Button type="button" variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
          ×
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as ClipTab)}>
        <TabsList className={cn('grid w-full bg-muted/60', TAB_COLUMNS_CLASS[visibleTabs.length as keyof typeof TAB_COLUMNS_CLASS] ?? 'grid-cols-4')}>
          {visibleTabs.includes('effects') && <TabsTrigger value="effects">Effects</TabsTrigger>}
          {visibleTabs.includes('timing') && <TabsTrigger value="timing">Timing</TabsTrigger>}
          {visibleTabs.includes('position') && <TabsTrigger value="position">Position</TabsTrigger>}
          {visibleTabs.includes('audio') && <TabsTrigger value="audio">Audio</TabsTrigger>}
          {visibleTabs.includes('text') && <TabsTrigger value="text">Text</TabsTrigger>}
        </TabsList>

        {visibleTabs.includes('effects') && (
          <TabsContent value="effects" className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <FieldLabel>Entrance</FieldLabel>
                <Select
                  value={sharedEntranceType ?? MIXED_SELECT_VALUE}
                  onValueChange={(value) => onChangeDeep((meta) => ({
                    entrance: value === NO_EFFECT
                      ? undefined
                      : {
                          type: value,
                          duration: meta.entrance?.duration ?? 0.4,
                          params: getDefaultEffectParams(value, effectResources.effects),
                        },
                  }))}
                >
                  <SelectTrigger><SelectValue placeholder="None" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={MIXED_SELECT_VALUE} disabled>Mixed</SelectItem>
                    <SelectItem value={NO_EFFECT}>None</SelectItem>
                    {entranceEffectTypes.map((effect) => <SelectItem key={effect} value={effect}>{effect}</SelectItem>)}
                    {effectResources.entrance.length > 0 && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        {effectResources.entrance.map((effect) => {
                          const error = isEffectInError(effect);
                          const provenanceLabel = getProvenanceLabel(effect);
                          const readOnly = isReadOnlyEffect(effect);
                          const blocked = getBlockedRoutes(effect);
                          return (
                            <SelectItem
                              key={`custom:${effect.id}`}
                              value={`custom:${effect.id}`}
                              disabled={error}
                            >
                              <span className="flex items-center gap-1.5">
                                {error && <AlertTriangle className="h-3 w-3 shrink-0 text-destructive" />}
                                {isAudioReactiveEffect(effect) && <AudioReactiveIcon />}
                                {readOnly && <Lock className="h-3 w-3 shrink-0 text-muted-foreground" />}
                                {effect.name}
                                {provenanceLabel && (
                                  <span className="ml-0.5 rounded-sm bg-blue-500/15 px-1 text-[9px] font-medium text-blue-300">
                                    {provenanceLabel}
                                  </span>
                                )}
                                {blocked.length > 0 && (
                                  <span className="ml-0.5 rounded-sm bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300">
                                    {blocked.map((r) => r === 'browser-export' ? 'No B' : r === 'worker-export' ? 'No W' : r).join(', ')}
                                  </span>
                                )}
                                {error && <span className="ml-1 text-[10px] text-destructive">(invalid schema)</span>}
                              </span>
                            </SelectItem>
                          );
                        })}
                      </>
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <FieldLabel>Exit</FieldLabel>
                <Select
                  value={sharedExitType ?? MIXED_SELECT_VALUE}
                  onValueChange={(value) => onChangeDeep((meta) => ({
                    exit: value === NO_EFFECT
                      ? undefined
                      : {
                          type: value,
                          duration: meta.exit?.duration ?? 0.4,
                          params: getDefaultEffectParams(value, effectResources.effects),
                        },
                  }))}
                >
                  <SelectTrigger><SelectValue placeholder="None" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={MIXED_SELECT_VALUE} disabled>Mixed</SelectItem>
                    <SelectItem value={NO_EFFECT}>None</SelectItem>
                    {exitEffectTypes.map((effect) => <SelectItem key={effect} value={effect}>{effect}</SelectItem>)}
                    {effectResources.exit.length > 0 && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        {effectResources.exit.map((effect) => {
                          const error = isEffectInError(effect);
                          const provenanceLabel = getProvenanceLabel(effect);
                          const readOnly = isReadOnlyEffect(effect);
                          const blocked = getBlockedRoutes(effect);
                          return (
                            <SelectItem
                              key={`custom:${effect.id}`}
                              value={`custom:${effect.id}`}
                              disabled={error}
                            >
                              <span className="flex items-center gap-1.5">
                                {error && <AlertTriangle className="h-3 w-3 shrink-0 text-destructive" />}
                                {isAudioReactiveEffect(effect) && <AudioReactiveIcon />}
                                {readOnly && <Lock className="h-3 w-3 shrink-0 text-muted-foreground" />}
                                {effect.name}
                                {provenanceLabel && (
                                  <span className="ml-0.5 rounded-sm bg-blue-500/15 px-1 text-[9px] font-medium text-blue-300">
                                    {provenanceLabel}
                                  </span>
                                )}
                                {blocked.length > 0 && (
                                  <span className="ml-0.5 rounded-sm bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300">
                                    {blocked.map((r) => r === 'browser-export' ? 'No B' : r === 'worker-export' ? 'No W' : r).join(', ')}
                                  </span>
                                )}
                                {error && <span className="ml-1 text-[10px] text-destructive">(invalid schema)</span>}
                              </span>
                            </SelectItem>
                          );
                        })}
                      </>
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2 md:col-span-2">
                <FieldLabel>Continuous</FieldLabel>
                <Select
                  value={sharedContinuousType ?? MIXED_SELECT_VALUE}
                  onValueChange={(value) => onChangeDeep((meta) => ({
                    continuous: value === NO_EFFECT
                      ? undefined
                      : {
                          type: value,
                          intensity: meta.continuous?.intensity ?? 0.5,
                          params: getDefaultEffectParams(value, effectResources.effects),
                        },
                  }))}
                >
                  <SelectTrigger><SelectValue placeholder="None" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={MIXED_SELECT_VALUE} disabled>Mixed</SelectItem>
                    <SelectItem value={NO_EFFECT}>None</SelectItem>
                    {continuousEffectTypes.map((effect) => <SelectItem key={effect} value={effect}>{effect}</SelectItem>)}
                    {effectResources.continuous.length > 0 && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        {effectResources.continuous.map((effect) => {
                          const error = isEffectInError(effect);
                          const provenanceLabel = getProvenanceLabel(effect);
                          const readOnly = isReadOnlyEffect(effect);
                          const blocked = getBlockedRoutes(effect);
                          return (
                            <SelectItem
                              key={`custom:${effect.id}`}
                              value={`custom:${effect.id}`}
                              disabled={error}
                            >
                              <span className="flex items-center gap-1.5">
                                {error && <AlertTriangle className="h-3 w-3 shrink-0 text-destructive" />}
                                {isAudioReactiveEffect(effect) && <AudioReactiveIcon />}
                                {readOnly && <Lock className="h-3 w-3 shrink-0 text-muted-foreground" />}
                                {effect.name}
                                {provenanceLabel && (
                                  <span className="ml-0.5 rounded-sm bg-blue-500/15 px-1 text-[9px] font-medium text-blue-300">
                                    {provenanceLabel}
                                  </span>
                                )}
                                {blocked.length > 0 && (
                                  <span className="ml-0.5 rounded-sm bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300">
                                    {blocked.map((r) => r === 'browser-export' ? 'No B' : r === 'worker-export' ? 'No W' : r).join(', ')}
                                  </span>
                                )}
                                {error && <span className="ml-1 text-[10px] text-destructive">(invalid schema)</span>}
                              </span>
                            </SelectItem>
                          );
                        })}
                      </>
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2 md:col-span-2">
                <FieldLabel>Transition</FieldLabel>
                <Select
                  value={sharedTransitionType ?? MIXED_SELECT_VALUE}
                  onValueChange={(value) => {
                    if (value === NO_TRANSITION || value === MIXED_SELECT_VALUE) {
                      onChangeDeep(() => ({ transition: undefined }));
                      return;
                    }
                    const record = resolveTransition(value, mergedTransitionSnapshot);
                    const defaults = record?.schema
                      ? materializeTransitionDefaults(record.schema)
                      : undefined;
                    onChangeDeep((meta) => ({
                      transition: {
                        type: value,
                        duration: meta.transition?.duration ?? sharedTransitionDuration ?? 0.5,
                        params: defaults && Object.keys(defaults).length > 0 ? defaults : undefined,
                      },
                    }));
                  }}
                >
                  <SelectTrigger><SelectValue placeholder="None" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={MIXED_SELECT_VALUE} disabled>Mixed</SelectItem>
                    <SelectItem value={NO_TRANSITION}>None</SelectItem>
                    {availableTransitions.map((record) => {
                      const error = record.status === 'error';
                      const inactive = record.status === 'inactive';
                      const provenanceLabel = getTransitionProvenanceLabel(record);
                      const blocked = getTransitionBlockedRoutes(record);
                      return (
                        <SelectItem
                          key={record.transitionId}
                          value={record.transitionId}
                          disabled={error}
                        >
                          <span className="flex items-center gap-1.5">
                            {error && <AlertTriangle className="h-3 w-3 shrink-0 text-destructive" />}
                            {record.transitionId}
                            {provenanceLabel && (
                              <span className="ml-0.5 rounded-sm bg-blue-500/15 px-1 text-[9px] font-medium text-blue-300">
                                {provenanceLabel}
                              </span>
                            )}
                            {blocked.length > 0 && (
                              <span className="ml-0.5 rounded-sm bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300">
                                {blocked.map((r) => r === 'browser-export' ? 'No B' : r === 'worker-export' ? 'No W' : r).join(', ')}
                              </span>
                            )}
                            {inactive && <span className="ml-1 text-[10px] text-muted-foreground">(inactive)</span>}
                            {error && <span className="ml-1 text-[10px] text-destructive">(invalid)</span>}
                          </span>
                        </SelectItem>
                      );
                    })}
                    {isTransitionUnresolvable && sharedTransitionType && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        <SelectItem value={sharedTransitionType} disabled>
                          <span className="text-muted-foreground">
                            {sharedTransitionType} (missing)
                          </span>
                        </SelectItem>
                      </>
                    )}
                  </SelectContent>
                </Select>

                {/* Renderability badges */}
                {resolvedTransitionRecord && (() => {
                  const blocked = getTransitionBlockedRoutes(resolvedTransitionRecord);
                  if (blocked.length === 0) return null;
                  return (
                    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/8 px-2 py-1 text-[11px] text-amber-200">
                      {blocked.includes('browser-export') && (
                        <span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />No browser export</span>
                      )}
                      {blocked.includes('worker-export') && (
                        <span className="inline-flex items-center gap-1"><Server className="h-3 w-3" />No worker export</span>
                      )}
                    </div>
                  );
                })()}

                {/* Unresolvable / missing transition row */}
                {isTransitionUnresolvable && sharedTransitionType && (
                  <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1.5 text-xs text-destructive">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    <span>Transition "{sharedTransitionType}" is not available. The extension may have been removed.</span>
                  </div>
                )}

                {/* Duration editing */}
                {sharedTransitionType && sharedTransitionType !== NO_TRANSITION && sharedTransitionType !== NO_EFFECT && sharedTransitionDuration !== null && (
                  <div className="space-y-1">
                    <FieldLabel>Duration (seconds)</FieldLabel>
                    <NumberInput
                      value={sharedTransitionDuration}
                      min={0.05}
                      max={10}
                      step={0.05}
                      onChange={(value) => {
                        if (value !== null) {
                          onChangeDeep((meta) => ({
                            transition: {
                              type: sharedTransitionType!,
                              duration: value,
                              params: meta.transition?.params ?? sharedTransition?.params,
                            },
                          }));
                        }
                      }}
                    />
                  </div>
                )}

                {/* Remove / Reset buttons */}
                {sharedTransitionType && sharedTransitionType !== NO_TRANSITION && sharedTransitionType !== NO_EFFECT && (
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 text-xs text-destructive hover:text-destructive"
                      onClick={() => onChangeDeep(() => ({ transition: undefined }))}
                    >
                      <Trash2 className="h-3 w-3" /> Remove
                    </Button>
                    {resolvedTransitionRecord?.schema?.length && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 gap-1 text-xs"
                        onClick={() => {
                          if (!sharedTransitionType || !resolvedTransitionRecord?.schema) return;
                          onChangeDeep(() => ({
                            transition: {
                              type: sharedTransitionType,
                              duration: sharedTransitionDuration ?? 0.5,
                              params: materializeTransitionDefaults(resolvedTransitionRecord.schema),
                            },
                          }));
                        }}
                      >
                        <RefreshCw className="h-3 w-3" /> Reset defaults
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
        )}

        {visibleTabs.includes('timing') && (
          <TabsContent value="timing" className="space-y-3">
            <div className="rounded-lg border border-border bg-card/60 px-3 py-2 text-xs text-muted-foreground">
              Source In and Source Out apply the same trim to all selected clips.
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {renderNumberInput('speed', 'Speed', { min: 0.05, step: 0.1 })}
              {renderNumberInput('from', 'Source In', { min: 0, step: 0.1 })}
              {renderNumberInput('to', 'Source Out', { min: 0, step: 0.1 })}
            </div>
          </TabsContent>
        )}

        {visibleTabs.includes('position') && (
          <TabsContent value="position" className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              {renderNumberInput('x', 'X')}
              {renderNumberInput('y', 'Y')}
              {renderNumberInput('width', 'Width', { min: 0, max: compositionWidth })}
              {renderNumberInput('height', 'Height', { min: 0, max: compositionHeight })}
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <FieldLabel>Opacity</FieldLabel>
                <span className="text-xs text-muted-foreground">
                  {sharedOpacity === null ? 'Mixed' : sharedOpacity.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[sharedOpacity ?? 1]}
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
              <div className="mb-2 flex items-center justify-between gap-3 text-sm text-foreground">
                <div className="flex items-center gap-2">
                  <Volume2 className="h-4 w-4" />
                  Volume
                </div>
                <span className="text-xs text-muted-foreground">
                  {sharedVolume === null ? 'Mixed' : sharedVolume.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[sharedVolume ?? 1]}
                min={0}
                max={1}
                step={0.05}
                onValueChange={(value) => onChange({ volume: value })}
              />
              <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={onToggleMute}>
                Toggle mute
              </Button>
            </div>
          </TabsContent>
        )}

        {visibleTabs.includes('text') && (
          <TabsContent value="text" className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <FieldLabel>Font size</FieldLabel>
                <NumberInput
                  min={1}
                  value={drafts.fontSize}
                  placeholder="Mixed"
                  onChange={(value) => setNumberDraft('fontSize', value)}
                  onValueCommitted={(value) => commitTextFontSize(value)}
                />
              </div>
              <div className="space-y-2">
                <FieldLabel>Color</FieldLabel>
                <Input
                  type="text"
                  value={drafts.color}
                  placeholder="Mixed"
                  onChange={(event) => setColorDraft(event.target.value)}
                  onBlur={() => commitTextColor(drafts.color)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      commitTextColor(drafts.color);
                    }
                  }}
                />
              </div>
            </div>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
