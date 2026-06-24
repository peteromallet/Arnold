import { useMemo, useState } from 'react';
import { AlertTriangle, AudioWaveform, Globe, Lock, Monitor, Pencil, Plus, RefreshCw, Server, Trash2, Volume2, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { Input } from '@/shared/components/ui/input.tsx';
import { MediaVariantPicker } from '@/shared/components/MediaVariantPicker.tsx';
import type { GenerationVariant } from '@/shared/hooks/variants/useVariants.ts';
import { NumberInput } from '@/shared/components/ui/number-input.tsx';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select.tsx';
import { Slider } from '@/shared/components/ui/slider.tsx';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs.tsx';
import { Textarea } from '@/shared/components/ui/textarea.tsx';
import { ParameterControls, getDefaultValues } from '@/tools/video-editor/components/ParameterControls.tsx';
import { SequenceParamEditor } from '@/tools/video-editor/components/PropertiesPanel/SequenceParamEditor.tsx';
import {
  clipTypeUsesHoldTiming,
  getRegisteredClipTypeDescriptor,
  getClipTypeOverlayBehavior,
  isClipTypeCommandAvailable,
} from '@/tools/video-editor/clip-types/index.ts';
import { isEditorParamsSchema, isSequenceParamsSchema } from '@/tools/video-editor/clip-types/defineClipType.ts';
import { KeyframeInspector } from '@/tools/video-editor/components/KeyframeInspector/KeyframeInspector';
import { continuousEffectTypes, entranceEffectTypes, exitEffectTypes } from '@/tools/video-editor/effects/index.tsx';
import { EffectCreatorPanel } from '@/tools/video-editor/components/EffectCreatorPanel.tsx';
import { useEffectResources, type EffectCategory, type EffectResource } from '@/tools/video-editor/hooks/useEffectResources.ts';
import type { ClipTab } from '@/tools/video-editor/hooks/useEditorPreferences.ts';
import type { ClipMeta } from '@/tools/video-editor/lib/timeline-data.ts';
import { getVisibleClipTabs } from '@/tools/video-editor/lib/clip-inspector.ts';
import type { TimelineDeviceClass, TimelineInteractionMode } from '@/tools/video-editor/lib/mobile-interaction-model.ts';
import { resolveAvailableClipType } from '@/tools/video-editor/sequences/registry.ts';
import type {
  ResolvedTimelineClip,
  ResolvedTimelineConfig,
  TimelineClipShaderMetadata,
  TrackDefinition,
  ClipTransition,
  ParameterSchema,
} from '@/tools/video-editor/types/index.ts';
import {
  useOptionalTransitionRegistryContext,
  type TransitionRegistryRecord,
} from '@/tools/video-editor/transitions/registry/index.ts';
import {
  listTransitions,
  resolveTransition,
  isBuiltInTransition,
  createTransitionSnapshot,
  materializeTransitionDefaults,
} from '@/tools/video-editor/transitions/catalog.ts';
import { useOptionalClipTypeRegistryContext } from '@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx';
import type { ClipTypeRegistryRecord } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import {
  HostContributionErrorBoundary,
  type ContributionErrorInfo,
} from '@/tools/video-editor/runtime/ContributionErrorBoundary.tsx';
import {
  useOptionalShaderEffectRegistryContext,
  type ShaderEffectRegistryRecord,
} from '@/tools/video-editor/shaders/registry/index.ts';
import {
  NO_SHADER,
  createTimelineClipShaderMetadata,
  getShaderPassLabel,
  listClipShaderPickerEntries,
} from '@/tools/video-editor/lib/shader-catalog.ts';
import {
  sameTimelineShaderIdentity,
  timelineShaderScopeOccupiedMessage,
} from '@/tools/video-editor/lib/timeline-domain.ts';

export { getVisibleClipTabs } from '@/tools/video-editor/lib/clip-inspector.ts';

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
  /** Current playhead time in seconds, used by KeyframeInspector. */
  currentTime?: number;
}

export const NO_EFFECT = '__none__';
export const NO_TRANSITION = '__none__';
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

function ShaderSelectValue({
  shader,
  record,
}: {
  shader: TimelineClipShaderMetadata | undefined;
  record: ShaderEffectRegistryRecord | undefined;
}) {
  if (!shader) {
    return <SelectValue placeholder="None">None</SelectValue>;
  }

  const label = record?.label ?? shader.label ?? shader.shaderId;
  const passLabel = record ? getShaderPassLabel(record) : 'missing';
  return <SelectValue placeholder="None">{`${label} · Shader · ${passLabel}`}</SelectValue>;
}

function getShaderPickerValue(record: ShaderEffectRegistryRecord): string {
  return [
    record.ownerExtensionId ?? '',
    record.contributionId,
    record.shaderId,
  ].map(encodeURIComponent).join('|');
}

function getMissingShaderPickerValue(shader: TimelineClipShaderMetadata): string {
  return `missing|${encodeURIComponent(shader.extensionId)}|${encodeURIComponent(shader.contributionId)}|${encodeURIComponent(shader.shaderId)}`;
}

function removeClipShaderAppMetadata(app: ResolvedTimelineClip['app'] | undefined): ResolvedTimelineClip['app'] {
  const nextApp = { ...(app ?? {}) };
  delete nextApp.shader;
  return nextApp;
}

/** Check if an effect resource's registry status is 'error' (invalid schema, etc.). */
function isEffectInError(effect: EffectResource): boolean {
  return effect.registryStatus === 'error';
}

/** Check if an effect resource is read-only (bundled-extension per SD3). */
function isReadOnlyEffect(effect: EffectResource): boolean {
  return effect.readOnly === true;
}

/** Returns a short provenance label for display in effect selectors. */
function getProvenanceLabel(effect: EffectResource): string | null {
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

/**
 * Returns a compact summary of export capability status for an applied effect.
 * Shows which routes are blocked so users see export limitations immediately after apply.
 */
function getBlockedRoutes(effect: EffectResource): string[] {
  if (!effect.renderability?.capabilities) return [];
  return effect.renderability.capabilities
    .filter((cap) => cap.route !== 'preview' && cap.status === 'blocked')
    .map((cap) => cap.route);
}

/** Check if an effect is preview-only (browser-export and worker-export both blocked). */
function isPreviewOnly(effect: EffectResource): boolean {
  if (!effect.renderability?.capabilities) return false;
  const hasBrowserExport = effect.renderability.capabilities.some(
    (cap) => cap.route === 'browser-export' && cap.status === 'supported',
  );
  const hasWorkerExport = effect.renderability.capabilities.some(
    (cap) => cap.route === 'worker-export' && cap.status === 'supported',
  );
  const hasPreview = effect.renderability.capabilities.some(
    (cap) => cap.route === 'preview' && cap.status === 'supported',
  );
  return hasPreview && !hasBrowserExport && !hasWorkerExport;
}

function hasParameterSchema(effect: EffectResource | undefined): effect is EffectResource & { parameterSchema: NonNullable<EffectResource['parameterSchema']> } {
  return Boolean(effect?.parameterSchema?.length);
}

/** Check if stored params differ from schema defaults (for reset-to-defaults affordance). */
function hasCustomParams(
  effect: EffectResource | undefined,
  storedParams: Record<string, unknown> | undefined,
): boolean {
  if (!effect?.parameterSchema?.length) return false;
  const defaults = getDefaultValues(effect.parameterSchema);
  const params = storedParams ?? {};
  const allKeys = new Set([...Object.keys(defaults), ...Object.keys(params)]);
  for (const key of allKeys) {
    if (JSON.stringify(params[key]) !== JSON.stringify(defaults[key])) {
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Transition helpers (T11: single-clip transition controls)
// ---------------------------------------------------------------------------

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

/** Check if a transition is preview-only (browser-export and worker-export both blocked). */
function isTransitionPreviewOnly(record: TransitionRegistryRecord): boolean {
  if (!record.renderability?.capabilities) return false;
  const hasBrowserExport = record.renderability.capabilities.some(
    (cap) => cap.route === 'browser-export' && cap.status === 'supported',
  );
  const hasWorkerExport = record.renderability.capabilities.some(
    (cap) => cap.route === 'worker-export' && cap.status === 'supported',
  );
  const hasPreview = record.renderability.capabilities.some(
    (cap) => cap.route === 'preview' && cap.status === 'supported',
  );
  return hasPreview && !hasBrowserExport && !hasWorkerExport;
}

/** Check if stored transition params differ from schema defaults. */
function hasCustomTransitionParams(
  record: TransitionRegistryRecord | undefined,
  storedParams: Record<string, unknown> | undefined,
): boolean {
  if (!record?.schema?.length) return false;
  const defaults = materializeTransitionDefaults(record.schema);
  const params = storedParams ?? {};
  const allKeys = new Set([...Object.keys(defaults), ...Object.keys(params)]);
  for (const key of allKeys) {
    if (JSON.stringify(params[key]) !== JSON.stringify(defaults[key])) {
      return true;
    }
  }
  return false;
}

/** Merge stored transition params with schema defaults. */
function getMergedTransitionParams(
  record: TransitionRegistryRecord | undefined,
  storedParams: Record<string, unknown> | undefined,
): Record<string, unknown> {
  return {
    ...materializeTransitionDefaults(record?.schema),
    ...(storedParams ?? {}),
  };
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
  currentTime = 0,
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

  // Transition registry (T11: single-clip transition controls)
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
    if (!clip?.transition?.type || clip.transition.type === NO_TRANSITION) return undefined;
    return resolveTransition(clip.transition.type, mergedTransitionSnapshot);
  }, [clip?.transition?.type, mergedTransitionSnapshot]);
  const isTransitionUnresolvable =
    clip?.transition?.type != null &&
    clip.transition.type !== NO_TRANSITION &&
    !resolvedTransitionRecord;
  const isTransitionInError = resolvedTransitionRecord?.status === 'error';
  const isTransitionInactive = resolvedTransitionRecord?.status === 'inactive';

  // M13: Clip-local shader picker. Postprocess shaders are timeline-scoped and
  // intentionally excluded from ClipPanel until a render graph exists.
  const [shaderDiagnostic, setShaderDiagnostic] = useState<string | null>(null);
  const shaderRegistryContext = useOptionalShaderEffectRegistryContext();
  const shaderPickerEntries = useMemo(
    () => listClipShaderPickerEntries(shaderRegistryContext?.snapshot),
    [shaderRegistryContext?.snapshot],
  );
  const clipShader = clip?.app?.shader;
  const resolvedClipShaderRecord = useMemo(() => {
    if (!clipShader) return undefined;
    return shaderRegistryContext?.snapshot.get(clipShader.shaderId, clipShader.extensionId);
  }, [clipShader, shaderRegistryContext?.snapshot]);
  const selectedShaderValue = clipShader
    ? resolvedClipShaderRecord
      ? getShaderPickerValue(resolvedClipShaderRecord)
      : getMissingShaderPickerValue(clipShader)
    : NO_SHADER;

  // M9 T9: Extension-provided clip inspector section
  const clipTypeRegistryContext = useOptionalClipTypeRegistryContext();
  const clipTypeRegistryRecord: ClipTypeRegistryRecord | undefined = useMemo(() => {
    if (!clip?.clipType || !clipTypeRegistryContext) return undefined;
    return clipTypeRegistryContext.snapshot.get(clip.clipType);
  }, [clip?.clipType, clipTypeRegistryContext]);

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
                {entranceEffect && (() => {
                  const blockedEntrance = getBlockedRoutes(entranceEffect);
                  const isRO = isReadOnlyEffect(entranceEffect);
                  const previewOnlyEntrance = isPreviewOnly(entranceEffect);
                  return (
                    <>
                      {(blockedEntrance.length > 0 || isRO || previewOnlyEntrance) && (
                        <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/8 px-2 py-1 text-[11px] text-amber-200">
                          {previewOnlyEntrance && (
                            <span className="inline-flex items-center gap-1"><Monitor className="h-3 w-3" />Preview only</span>
                          )}
                          {blockedEntrance.includes('browser-export') && !previewOnlyEntrance && (
                            <span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />No browser export</span>
                          )}
                          {blockedEntrance.includes('worker-export') && !previewOnlyEntrance && (
                            <span className="inline-flex items-center gap-1"><Server className="h-3 w-3" />No worker export</span>
                          )}
                          {isRO && (
                            <span className="inline-flex items-center gap-1"><Lock className="h-3 w-3" />Read-only</span>
                          )}
                        </div>
                      )}
                    </>
                  );
                })()}
                {clip.entrance && (
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 text-xs text-destructive hover:text-destructive"
                      onClick={() => onChange({ entrance: undefined })}
                    >
                      <Trash2 className="h-3 w-3" /> Remove
                    </Button>
                    {hasParameterSchema(entranceEffect) && hasCustomParams(entranceEffect, clip.entrance.params) && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 gap-1 text-xs"
                        onClick={() => onChange({
                          entrance: {
                            type: clip.entrance!.type,
                            duration: clip.entrance!.duration ?? 0.4,
                            params: getDefaultValues(entranceEffect!.parameterSchema),
                          },
                        })}
                      >
                        <RefreshCw className="h-3 w-3" /> Reset defaults
                      </Button>
                    )}
                    {entranceEffect && !isReadOnlyEffect(entranceEffect) && canEditEffects && (
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
                  </div>
                )}
                {!clip.entrance && entranceEffect && !isReadOnlyEffect(entranceEffect) && canEditEffects && (
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
                    disabled={isEffectInError(entranceEffect)}
                    diagnostics={entranceEffect.diagnostics}
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
                {exitEffect && (() => {
                  const blockedExit = getBlockedRoutes(exitEffect);
                  const isRO = isReadOnlyEffect(exitEffect);
                  const previewOnlyExit = isPreviewOnly(exitEffect);
                  return (
                    <>
                      {(blockedExit.length > 0 || isRO || previewOnlyExit) && (
                        <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/8 px-2 py-1 text-[11px] text-amber-200">
                          {previewOnlyExit && (
                            <span className="inline-flex items-center gap-1"><Monitor className="h-3 w-3" />Preview only</span>
                          )}
                          {blockedExit.includes('browser-export') && !previewOnlyExit && (
                            <span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />No browser export</span>
                          )}
                          {blockedExit.includes('worker-export') && !previewOnlyExit && (
                            <span className="inline-flex items-center gap-1"><Server className="h-3 w-3" />No worker export</span>
                          )}
                          {isRO && (
                            <span className="inline-flex items-center gap-1"><Lock className="h-3 w-3" />Read-only</span>
                          )}
                        </div>
                      )}
                    </>
                  );
                })()}
                {clip.exit && (
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 text-xs text-destructive hover:text-destructive"
                      onClick={() => onChange({ exit: undefined })}
                    >
                      <Trash2 className="h-3 w-3" /> Remove
                    </Button>
                    {hasParameterSchema(exitEffect) && hasCustomParams(exitEffect, clip.exit.params) && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 gap-1 text-xs"
                        onClick={() => onChange({
                          exit: {
                            type: clip.exit!.type,
                            duration: clip.exit!.duration ?? 0.4,
                            params: getDefaultValues(exitEffect!.parameterSchema),
                          },
                        })}
                      >
                        <RefreshCw className="h-3 w-3" /> Reset defaults
                      </Button>
                    )}
                    {exitEffect && !isReadOnlyEffect(exitEffect) && canEditEffects && (
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
                  </div>
                )}
                {!clip.exit && exitEffect && !isReadOnlyEffect(exitEffect) && canEditEffects && (
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
                    disabled={isEffectInError(exitEffect)}
                    diagnostics={exitEffect.diagnostics}
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
                {continuousEffect && (() => {
                  const blockedContinuous = getBlockedRoutes(continuousEffect);
                  const isRO = isReadOnlyEffect(continuousEffect);
                  const previewOnlyContinuous = isPreviewOnly(continuousEffect);
                  return (
                    <>
                      {(blockedContinuous.length > 0 || isRO || previewOnlyContinuous) && (
                        <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/8 px-2 py-1 text-[11px] text-amber-200">
                          {previewOnlyContinuous && (
                            <span className="inline-flex items-center gap-1"><Monitor className="h-3 w-3" />Preview only</span>
                          )}
                          {blockedContinuous.includes('browser-export') && !previewOnlyContinuous && (
                            <span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />No browser export</span>
                          )}
                          {blockedContinuous.includes('worker-export') && !previewOnlyContinuous && (
                            <span className="inline-flex items-center gap-1"><Server className="h-3 w-3" />No worker export</span>
                          )}
                          {isRO && (
                            <span className="inline-flex items-center gap-1"><Lock className="h-3 w-3" />Read-only</span>
                          )}
                        </div>
                      )}
                    </>
                  );
                })()}
                {clip.continuous && (
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 text-xs text-destructive hover:text-destructive"
                      onClick={() => onChange({ continuous: undefined })}
                    >
                      <Trash2 className="h-3 w-3" /> Remove
                    </Button>
                    {hasParameterSchema(continuousEffect) && hasCustomParams(continuousEffect, clip.continuous.params) && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 gap-1 text-xs"
                        onClick={() => onChange({
                          continuous: {
                            type: clip.continuous!.type,
                            intensity: clip.continuous!.intensity ?? 0.5,
                            params: getDefaultValues(continuousEffect!.parameterSchema),
                          },
                        })}
                      >
                        <RefreshCw className="h-3 w-3" /> Reset defaults
                      </Button>
                    )}
                    {continuousEffect && !isReadOnlyEffect(continuousEffect) && canEditEffects && (
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
                  </div>
                )}
                {!clip.continuous && continuousEffect && !isReadOnlyEffect(continuousEffect) && canEditEffects && (
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
                    disabled={isEffectInError(continuousEffect)}
                    diagnostics={continuousEffect.diagnostics}
                  />
                )}
              </div>
              <div className="space-y-2 md:col-span-2" data-testid="clip-panel-shader-section">
                <FieldLabel>Shader</FieldLabel>
                <Select
                  value={selectedShaderValue}
                  onValueChange={(value) => {
                    if (value === NO_SHADER) {
                      setShaderDiagnostic(null);
                      onChange({ app: removeClipShaderAppMetadata(clip.app) });
                      return;
                    }

                    const entry = shaderPickerEntries.find((candidate) => (
                      getShaderPickerValue(candidate.record) === value
                    ));
                    if (!entry || entry.disabled) {
                      return;
                    }

                    const nextShader = createTimelineClipShaderMetadata(entry.record);
                    if (clipShader && !sameTimelineShaderIdentity(clipShader, nextShader)) {
                      setShaderDiagnostic(timelineShaderScopeOccupiedMessage(
                        'clip',
                        clipShader.shaderId,
                        nextShader.shaderId,
                        clip.id,
                      ));
                      return;
                    }

                    setShaderDiagnostic(null);
                    onChange({
                      app: {
                        ...(clip.app ?? {}),
                        shader: nextShader,
                      },
                    });
                  }}
                >
                  <SelectTrigger>
                    <ShaderSelectValue shader={clipShader} record={resolvedClipShaderRecord} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_SHADER}>None</SelectItem>
                    {shaderPickerEntries.length > 0 && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        {shaderPickerEntries.map((entry) => {
                          const record = entry.record;
                          const passLabel = getShaderPassLabel(record);
                          const nextShader = createTimelineClipShaderMetadata(record);
                          return (
                            <SelectItem
                              key={`${record.ownerExtensionId ?? ''}:${record.contributionId}:${record.shaderId}`}
                              value={getShaderPickerValue(record)}
                              disabled={entry.disabled}
                              onPointerDown={(event) => {
                                if (!clipShader || sameTimelineShaderIdentity(clipShader, nextShader)) {
                                  return;
                                }
                                event.preventDefault();
                                setShaderDiagnostic(timelineShaderScopeOccupiedMessage(
                                  'clip',
                                  clipShader.shaderId,
                                  nextShader.shaderId,
                                  clip.id,
                                ));
                              }}
                            >
                              <span className="flex items-center gap-1.5">
                                {entry.disabled && <AlertTriangle className="h-3 w-3 shrink-0 text-destructive" />}
                                {record.label}
                                <span className="ml-0.5 rounded-sm bg-blue-500/15 px-1 text-[9px] font-medium text-blue-300">
                                  Shader
                                </span>
                                <span className="rounded-sm bg-cyan-500/15 px-1 text-[9px] font-medium text-cyan-300">
                                  {passLabel}
                                </span>
                                {entry.previewOnly && (
                                  <span className="rounded-sm bg-emerald-500/15 px-1 text-[9px] font-medium text-emerald-300">
                                    Preview only
                                  </span>
                                )}
                                {entry.blockedRoutes.length > 0 && !entry.previewOnly && (
                                  <span className="rounded-sm bg-amber-500/15 px-1 text-[9px] font-medium text-amber-300">
                                    {entry.blockedRoutes.map((route) => route === 'browser-export' ? 'No B' : route === 'worker-export' ? 'No W' : route).join(', ')}
                                  </span>
                                )}
                                {record.status === 'inactive' && <span className="ml-1 text-[10px] text-muted-foreground">(inactive)</span>}
                                {record.status === 'error' && <span className="ml-1 text-[10px] text-destructive">(invalid)</span>}
                              </span>
                            </SelectItem>
                          );
                        })}
                      </>
                    )}
                    {clipShader && !resolvedClipShaderRecord && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        <SelectItem value={getMissingShaderPickerValue(clipShader)} disabled>
                          <span className="text-muted-foreground">
                            {clipShader.label ?? clipShader.shaderId} (missing)
                          </span>
                        </SelectItem>
                      </>
                    )}
                  </SelectContent>
                </Select>

                {shaderDiagnostic && (
                  <div
                    className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1.5 text-xs text-destructive"
                    data-testid="clip-panel-shader-diagnostic"
                    role="alert"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    <span>{shaderDiagnostic}</span>
                  </div>
                )}

                {resolvedClipShaderRecord && (() => {
                  const entry = shaderPickerEntries.find((candidate) => (
                    candidate.record === resolvedClipShaderRecord
                  ));
                  if (!entry) return null;
                  if (entry.blockedRoutes.length === 0 && !entry.previewOnly) return null;
                  return (
                    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/8 px-2 py-1 text-[11px] text-amber-200">
                      {entry.previewOnly && (
                        <span className="inline-flex items-center gap-1"><Monitor className="h-3 w-3" />Preview only</span>
                      )}
                      {entry.blockedRoutes.includes('browser-export') && !entry.previewOnly && (
                        <span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />No browser export</span>
                      )}
                      {entry.blockedRoutes.includes('worker-export') && !entry.previewOnly && (
                        <span className="inline-flex items-center gap-1"><Server className="h-3 w-3" />No worker export</span>
                      )}
                    </div>
                  );
                })()}

                {clipShader && !resolvedClipShaderRecord && (
                  <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1.5 text-xs text-destructive">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    <span>Shader "{clipShader.shaderId}" is not available. The extension may have been removed.</span>
                  </div>
                )}

                {clipShader && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 gap-1 text-xs text-destructive hover:text-destructive"
                    onClick={() => {
                      setShaderDiagnostic(null);
                      onChange({ app: removeClipShaderAppMetadata(clip.app) });
                    }}
                  >
                    <Trash2 className="h-3 w-3" /> Remove
                  </Button>
                )}
              </div>
              <div className="space-y-2 md:col-span-2">
                <FieldLabel>Transition</FieldLabel>
                <Select
                  value={clip.transition?.type ?? NO_TRANSITION}
                  onValueChange={(value) => {
                    if (value === NO_TRANSITION) {
                      onChange({ transition: undefined });
                      return;
                    }
                    const record = resolveTransition(value, mergedTransitionSnapshot);
                    const defaults = record?.schema
                      ? materializeTransitionDefaults(record.schema)
                      : undefined;
                    onChange({
                      transition: {
                        type: value,
                        duration: clip.transition?.duration ?? 0.5,
                        params: defaults && Object.keys(defaults).length > 0 ? defaults : undefined,
                      },
                    });
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="None">
                      {!clip.transition?.type || clip.transition.type === NO_TRANSITION
                        ? 'None'
                        : isTransitionUnresolvable
                          ? `${clip.transition.type} (missing)`
                          : resolvedTransitionRecord
                            ? (() => {
                                const label = getTransitionProvenanceLabel(resolvedTransitionRecord);
                                return label
                                  ? `${clip.transition.type} · ${label}`
                                  : clip.transition.type;
                              })()
                            : clip.transition.type}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
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
                    {/* Show the current transition if it's not in the list (e.g. removed contributed) */}
                    {isTransitionUnresolvable && clip.transition?.type && (
                      <>
                        <div className="my-1 h-px bg-border" />
                        <SelectItem value={clip.transition.type} disabled>
                          <span className="text-muted-foreground">
                            {clip.transition.type} (missing)
                          </span>
                        </SelectItem>
                      </>
                    )}
                  </SelectContent>
                </Select>

                {/* Renderability / provenance badges */}
                {resolvedTransitionRecord && (() => {
                  const blocked = getTransitionBlockedRoutes(resolvedTransitionRecord);
                  const previewOnly = isTransitionPreviewOnly(resolvedTransitionRecord);
                  if (blocked.length === 0 && !previewOnly) return null;
                  return (
                    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/8 px-2 py-1 text-[11px] text-amber-200">
                      {previewOnly && (
                        <span className="inline-flex items-center gap-1"><Monitor className="h-3 w-3" />Preview only</span>
                      )}
                      {blocked.includes('browser-export') && !previewOnly && (
                        <span className="inline-flex items-center gap-1"><Globe className="h-3 w-3" />No browser export</span>
                      )}
                      {blocked.includes('worker-export') && !previewOnly && (
                        <span className="inline-flex items-center gap-1"><Server className="h-3 w-3" />No worker export</span>
                      )}
                    </div>
                  );
                })()}

                {/* Unresolvable / missing transition row */}
                {isTransitionUnresolvable && clip.transition && (
                  <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1.5 text-xs text-destructive">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    <span>Transition "{clip.transition.type}" is not available. The extension may have been removed.</span>
                  </div>
                )}

                {/* Duration editing */}
                {clip.transition && clip.transition.type !== NO_TRANSITION && (
                  <div className="space-y-1">
                    <FieldLabel>Duration (seconds)</FieldLabel>
                    <NumberInput
                      value={clip.transition.duration}
                      min={0.05}
                      max={10}
                      step={0.05}
                      onChange={(value) => {
                        if (value !== null && clip.transition) {
                          onChange({
                            transition: {
                              ...clip.transition,
                              duration: value,
                            },
                          });
                        }
                      }}
                    />
                  </div>
                )}

                {/* Remove / Reset buttons */}
                {clip.transition && clip.transition.type !== NO_TRANSITION && (
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 text-xs text-destructive hover:text-destructive"
                      onClick={() => onChange({ transition: undefined })}
                    >
                      <Trash2 className="h-3 w-3" /> Remove
                    </Button>
                    {resolvedTransitionRecord?.schema?.length &&
                      hasCustomTransitionParams(resolvedTransitionRecord, clip.transition?.params) && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 gap-1 text-xs"
                        onClick={() => {
                          if (!clip.transition || !resolvedTransitionRecord?.schema) return;
                          onChange({
                            transition: {
                              type: clip.transition.type,
                              duration: clip.transition.duration,
                              params: materializeTransitionDefaults(resolvedTransitionRecord.schema),
                            },
                          });
                        }}
                      >
                        <RefreshCw className="h-3 w-3" /> Reset defaults
                      </Button>
                    )}
                  </div>
                )}

                {/* Parameter controls */}
                {resolvedTransitionRecord?.schema?.length && clip.transition && (
                  <ParameterControls
                    schema={resolvedTransitionRecord.schema}
                    values={getMergedTransitionParams(resolvedTransitionRecord, clip.transition?.params)}
                    onChange={(paramName, value) => {
                      if (!clip.transition) return;
                      onChange({
                        transition: {
                          type: clip.transition.type,
                          duration: clip.transition.duration,
                          params: {
                            ...(clip.transition.params ?? {}),
                            [paramName]: value,
                          },
                        },
                      });
                    }}
                    disabled={isTransitionInError || isTransitionInactive}
                    diagnostics={resolvedTransitionRecord.diagnostics}
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
              {/* M9: Keyframe Inspector — shown when clip type has editor params schema */}
              {clipDescriptor && isEditorParamsSchema(clipDescriptor.paramsSchema) && (
                <KeyframeInspector
                  schema={clipDescriptor.paramsSchema.params}
                  keyframes={clip.keyframes ?? {}}
                  currentTime={currentTime}
                  onChange={(updatedKeyframes) => onChange({ keyframes: updatedKeyframes })}
                />
              )}
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

      {/* M9 T9: Extension-provided clip inspector section after host controls */}
      {clipTypeRegistryRecord?.inspector && (() => {
        const InspectorRenderer = clipTypeRegistryRecord.inspector as (props: {
          clipId: string;
          clipTypeId: string;
          params: Record<string, unknown>;
          onParamsChange: (params: Record<string, unknown>) => void;
        }) => React.ReactNode;

        const handleContributionError = (info: ContributionErrorInfo) => {
          if (typeof console !== 'undefined') {
            console.warn(
              '[ClipPanel] Extension clip inspector error captured by boundary:',
              info,
            );
          }
        };

        return (
          <div className="mt-3 rounded-xl border border-border bg-card/70 p-3">
            <HostContributionErrorBoundary
              contributionId={
                clipTypeRegistryRecord.contributionId ??
                `clip-inspector:${clip.clipType}`
              }
              extensionId={clipTypeRegistryRecord.ownerExtensionId}
              kind="inspectorSection"
              label={
                clipTypeRegistryRecord.contributionId
                  ? `${clipTypeRegistryRecord.clipTypeId} inspector`
                  : `Clip inspector: ${clipTypeRegistryRecord.clipTypeId}`
              }
              onError={handleContributionError}
            >
              <InspectorRenderer
                clipId={clip.id}
                clipTypeId={clip.clipType ?? 'unknown'}
                params={clip.params ?? {}}
                onParamsChange={(params: Record<string, unknown>) =>
                  onChange({ params })
                }
              />
            </HostContributionErrorBoundary>
          </div>
        );
      })()}
    </div>
  );
}
