import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Gauge,
  Radio,
  RefreshCw,
  Scissors,
  ShieldAlert,
  SlidersHorizontal,
  Square,
  Trash2,
  WifiOff,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button.tsx';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { useOptionalVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  scanTimelineLiveBindings,
  type TimelineLiveBindingRecord,
  type TimelineLiveSourceSnapshot,
} from '@/tools/video-editor/lib/timeline-domain.ts';
import type { LiveDataRegistry, LiveDataRegistrySnapshot } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import {
  acceptLiveRecordingTake,
  createLiveRecordingPass,
  discardLiveRecordingTake,
  startLiveRecordingPass,
  stopLiveRecordingPass,
  type LiveRecordingPass,
} from '@/tools/video-editor/runtime/liveRecording.ts';
import {
  createLiveMappingTable,
  startLiveMappingLearn,
  type LiveMappingSession,
  type LiveMappingState,
  type LiveMappingTable,
} from '@/tools/video-editor/runtime/liveMapping.ts';
import type { LivePermissionService, PermissionRequestResult } from '@/tools/video-editor/runtime/livePermissions.ts';
import type { ResolvedTimelineConfig, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type {
  LiveBakeSelection,
  LiveBakeResult,
  LiveChannelDescriptor,
  LiveChannelMetadata,
  LivePermissionState,
  LiveSample,
  LiveSource,
  LiveSourceDiagnostic,
  LiveSourceStatus,
} from '@reigh/editor-sdk';

type LiveTimelineConfig = TimelineConfig | ResolvedTimelineConfig;

export interface LiveSourcesPanelProps {
  timelineConfig?: LiveTimelineConfig | null;
  liveDataRegistry?: LiveDataRegistry | null;
  livePermissionService?: LivePermissionService | null;
  onRemoveSourceBindings?: (sourceId: string) => void;
  compact?: boolean;
}

type SourceRow = {
  sourceId: string;
  source?: LiveSource;
  tombstone?: LiveDataRegistrySnapshot['tombstones'][number];
  bindings: readonly TimelineLiveBindingRecord[];
};

type PartialBakeRangeState = {
  mode: 'frame' | 'time' | 'sample';
  start: string;
  end: string;
  takeId: string;
};

type AudioOverlayState =
  | { status: 'empty'; message: string }
  | { status: 'error'; message: string }
  | { status: 'ready'; message: string; bars: readonly number[] };

const DEFAULT_RANGE_STATE: PartialBakeRangeState = {
  mode: 'frame',
  start: '',
  end: '',
  takeId: '',
};

const EMPTY_SNAPSHOT: LiveDataRegistrySnapshot = Object.freeze({
  sources: Object.freeze([]),
  channels: Object.freeze([]),
  tombstones: Object.freeze([]),
  bindings: Object.freeze([]),
  disposed: false,
});

const STATUS_CLASS: Record<LiveSourceStatus | 'missing' | 'partiallyBaked' | 'malformed', string> = {
  active: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  activating: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  inactive: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-300',
  error: 'border-red-500/30 bg-red-500/10 text-red-300',
  disposed: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  orphaned: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  missing: 'border-red-500/30 bg-red-500/10 text-red-300',
  partiallyBaked: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-300',
  malformed: 'border-red-500/30 bg-red-500/10 text-red-300',
};

const PERMISSION_LABEL: Record<LivePermissionState, string> = {
  prompt: 'permission prompt',
  granted: 'permission granted',
  denied: 'permission denied',
  unavailable: 'permission unavailable',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isEmptyRecord(value: Record<string, unknown>): boolean {
  return Object.keys(value).length === 0;
}

function filterBindingValue(value: unknown, sourceId: string): { value?: unknown; changed: boolean } {
  if (Array.isArray(value)) {
    const next = value.filter((item) => !isRecord(item) || item.sourceId !== sourceId);
    return { value: next, changed: next.length !== value.length };
  }

  if (isRecord(value)) {
    if (value.sourceId === sourceId) {
      return { changed: true };
    }

    let changed = false;
    const next: Record<string, unknown> = { ...value };
    for (const key of ['bindings', 'liveBindings'] as const) {
      if (Array.isArray(value[key])) {
        const filtered = value[key].filter((item) => !isRecord(item) || item.sourceId !== sourceId);
        if (filtered.length !== value[key].length) {
          changed = true;
          if (filtered.length > 0) {
            next[key] = filtered;
          } else {
            delete next[key];
          }
        }
      }
    }
    return { value: next, changed };
  }

  return { value, changed: false };
}

export function removeLiveBindingsFromResolvedConfig(
  config: ResolvedTimelineConfig,
  sourceId: string,
): ResolvedTimelineConfig | null {
  let changed = false;
  const clips = config.clips.map((clip) => {
    let nextClip = clip;

    if (clip.app?.live !== undefined) {
      const filtered = filterBindingValue(clip.app.live, sourceId);
      if (filtered.changed) {
        changed = true;
        const nextApp = { ...clip.app };
        if (filtered.value === undefined || (isRecord(filtered.value) && isEmptyRecord(filtered.value))) {
          delete nextApp.live;
        } else {
          nextApp.live = filtered.value;
        }
        nextClip = {
          ...nextClip,
          app: isEmptyRecord(nextApp) ? undefined : nextApp,
        };
      }
    }

    if (clip.params?.liveBindings !== undefined) {
      const filtered = filterBindingValue(clip.params.liveBindings, sourceId);
      if (filtered.changed) {
        changed = true;
        const nextParams = { ...clip.params };
        if (Array.isArray(filtered.value) && filtered.value.length > 0) {
          nextParams.liveBindings = filtered.value;
        } else if (filtered.value !== undefined && !Array.isArray(filtered.value)) {
          nextParams.liveBindings = filtered.value;
        } else {
          delete nextParams.liveBindings;
        }
        nextClip = {
          ...nextClip,
          params: isEmptyRecord(nextParams) ? undefined : nextParams,
        };
      }
    }

    return nextClip;
  });

  return changed ? { ...config, clips } : null;
}

function sourceStatusForRow(row: SourceRow): LiveSourceStatus | 'missing' {
  return row.source?.status ?? row.tombstone?.status ?? 'missing';
}

function sourceLabel(row: SourceRow): string {
  return row.source?.label ?? row.tombstone?.label ?? row.sourceId;
}

function diagnosticsForRow(row: SourceRow): readonly LiveSourceDiagnostic[] {
  return [
    ...(row.source?.diagnostics ?? []),
    ...row.bindings.flatMap((binding) => binding.diagnostics.map((diagnostic) => ({
      severity: diagnostic.severity,
      code: diagnostic.code,
      message: diagnostic.message,
      sourceId: diagnostic.sourceId,
      detail: diagnostic.details,
    }))),
  ];
}

function buildSourceSnapshots(snapshot: LiveDataRegistrySnapshot): TimelineLiveSourceSnapshot[] {
  return [
    ...snapshot.sources.map((source) => ({
      sourceId: source.id,
      kind: source.kind,
      status: source.status,
    })),
    ...snapshot.tombstones.map((tombstone) => ({
      sourceId: tombstone.id,
      kind: tombstone.kind,
      status: tombstone.status,
      ownerExtensionId: tombstone.extensionId,
    })),
  ];
}

function latestSampleSummary(
  registry: LiveDataRegistry | null | undefined,
  channelId: LiveChannelDescriptor,
): string {
  if (!registry) return 'no sample reader';
  const latest = registry.getLatestSample(channelId);
  if (!latest) return 'no samples yet';
  return `latest ${latest.sequenceNumber} @ ${latest.frame.timestamp}ms`;
}

function parseOptionalNumber(value: string): number | undefined {
  if (value.trim().length === 0) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function selectionForPartialBake(
  sourceId: string,
  channelIds: readonly LiveChannelDescriptor[],
  range: PartialBakeRangeState,
): LiveBakeSelection {
  const takeId = range.takeId.trim();
  const selection: LiveBakeSelection = {
    sourceId,
    channelIds,
    targets: [{ kind: 'sidecar', ref: `${sourceId}:live-bake-preview` }],
    ...(takeId.length > 0 ? { takeId } : {}),
  };
  const start = parseOptionalNumber(range.start);
  const end = parseOptionalNumber(range.end);
  if (start !== undefined && end !== undefined) {
    if (range.mode === 'frame') {
      return { ...selection, frameRange: [start, end] };
    }
    if (range.mode === 'time') {
      return { ...selection, timeRange: [start, end] };
    }
    return { ...selection, sampleRange: [start, end] };
  }
  return selection;
}

function readPath(data: unknown, path: string): unknown {
  if (!isRecord(data)) return undefined;
  return path.split('.').reduce<unknown>((current, key) => (
    isRecord(current) ? current[key] : undefined
  ), data);
}

function numberFromSample(sample: LiveSample | undefined, path: string): number | undefined {
  if (!sample) return undefined;
  const value = readPath(sample.frame.data, path) ?? readPath(sample.frame.metadata, path);
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function arrayFromSample(sample: LiveSample | undefined, path: string): readonly number[] | undefined {
  if (!sample) return undefined;
  const value = readPath(sample.frame.data, path) ?? readPath(sample.frame.metadata, path);
  if (!Array.isArray(value)) return undefined;
  return value.filter((item): item is number => typeof item === 'number' && Number.isFinite(item));
}

function audioOverlayForChannel(
  registry: LiveDataRegistry | null | undefined,
  channel: LiveChannelMetadata,
): AudioOverlayState {
  if (channel.kind !== 'audio') {
    return { status: 'empty', message: 'Audio analysis unavailable for this channel.' };
  }
  if (!registry) {
    return { status: 'error', message: 'Audio analysis has no live sample reader.' };
  }
  const latest = registry.getLatestSample(channel.channelId);
  if (!latest) {
    return { status: 'empty', message: 'Audio analysis waiting for samples.' };
  }

  const rms = numberFromSample(latest, 'rms');
  const amplitude = numberFromSample(latest, 'amplitude');
  const peak = numberFromSample(latest, 'peak');
  const fft = arrayFromSample(latest, 'fft');
  const bars = fft?.slice(0, 8) ?? [rms, amplitude, peak].filter((value): value is number => value !== undefined);

  if (bars.length === 0) {
    return { status: 'error', message: 'Audio analysis sample has no rms, amplitude, peak, or fft values.' };
  }

  const summary = [
    rms !== undefined ? `rms ${rms.toFixed(2)}` : undefined,
    amplitude !== undefined ? `amp ${amplitude.toFixed(2)}` : undefined,
    peak !== undefined ? `peak ${peak.toFixed(2)}` : undefined,
  ].filter(Boolean).join(' · ');
  return {
    status: 'ready',
    message: summary || `${bars.length} fft bins`,
    bars,
  };
}

function passForSource(
  current: LiveRecordingPass | undefined,
  row: SourceRow,
  channels: readonly LiveChannelMetadata[],
): LiveRecordingPass {
  return current ?? createLiveRecordingPass({
    id: `${row.sourceId}:pass`,
    armedSources: [{ sourceId: row.sourceId, channelIds: channels.map((channel) => channel.channelId) }],
    mappings: [],
  });
}

export function LiveSourcesPanel({
  timelineConfig,
  liveDataRegistry,
  livePermissionService,
  onRemoveSourceBindings,
  compact = false,
}: LiveSourcesPanelProps) {
  const runtime = useOptionalVideoEditorRuntime();
  const registry = liveDataRegistry ?? runtime?.liveDataRegistry ?? null;
  const permissionService = livePermissionService ?? runtime?.livePermissionService ?? null;
  const [bakeResults, setBakeResults] = useState<Record<string, LiveBakeResult>>({});
  const [permissionResults, setPermissionResults] = useState<Record<string, PermissionRequestResult>>({});
  const [partialBakeRanges, setPartialBakeRanges] = useState<Record<string, PartialBakeRangeState>>({});
  const [mappingTable, setMappingTable] = useState<LiveMappingTable>(() => createLiveMappingTable());
  const [learnStates, setLearnStates] = useState<Record<string, LiveMappingState>>({});
  const [mappingDiagnostics, setMappingDiagnostics] = useState<Record<string, string>>({});
  const learnSessions = useRef<Record<string, LiveMappingSession>>({});
  const [recordingPasses, setRecordingPasses] = useState<Record<string, LiveRecordingPass>>({});
  const [recordingDiagnostics, setRecordingDiagnostics] = useState<Record<string, string>>({});

  useEffect(() => () => {
    for (const session of Object.values(learnSessions.current)) {
      session.dispose();
    }
    learnSessions.current = {};
  }, []);

  const snapshot = useSyncExternalStore(
    useCallback((listener) => registry?.subscribe(listener).dispose ?? (() => undefined), [registry]),
    useCallback(() => registry?.getSnapshot() ?? EMPTY_SNAPSHOT, [registry]),
    () => EMPTY_SNAPSHOT,
  );

  const liveScan = useMemo(() => {
    if (!timelineConfig) return null;
    return scanTimelineLiveBindings(timelineConfig as TimelineConfig, {
      sources: buildSourceSnapshots(snapshot),
    });
  }, [snapshot, timelineConfig]);

  const rows = useMemo<SourceRow[]>(() => {
    const byId = new Map<string, SourceRow>();
    for (const source of snapshot.sources) {
      byId.set(source.id, { sourceId: source.id, source, bindings: [] });
    }
    for (const tombstone of snapshot.tombstones) {
      byId.set(tombstone.id, {
        ...byId.get(tombstone.id),
        sourceId: tombstone.id,
        tombstone,
        bindings: byId.get(tombstone.id)?.bindings ?? [],
      });
    }
    for (const binding of liveScan?.bindings ?? []) {
      const sourceId = binding.binding.sourceId;
      const existing = byId.get(sourceId);
      byId.set(sourceId, {
        sourceId,
        source: existing?.source,
        tombstone: existing?.tombstone,
        bindings: [...(existing?.bindings ?? []), binding],
      });
    }
    return [...byId.values()].sort((a, b) => a.sourceId.localeCompare(b.sourceId));
  }, [liveScan?.bindings, snapshot.sources, snapshot.tombstones]);

  const exportBlockers = liveScan?.bindings.filter((binding) => binding.blocksExport) ?? [];

  const handleBake = useCallback((row: SourceRow) => {
    if (!registry || !row.source) return;
    const channelIds = snapshot.channels
      .filter((channel) => channel.sourceId === row.sourceId)
      .map((channel) => channel.channelId);
    const result = registry.bake(selectionForPartialBake(
      row.sourceId,
      channelIds,
      partialBakeRanges[row.sourceId] ?? DEFAULT_RANGE_STATE,
    ));
    setBakeResults((current) => ({ ...current, [row.sourceId]: result }));
  }, [partialBakeRanges, registry, snapshot.channels]);

  const handleRemove = useCallback((row: SourceRow) => {
    registry?.removeLiveBindings(row.sourceId);
    onRemoveSourceBindings?.(row.sourceId);
  }, [onRemoveSourceBindings, registry]);

  const handleReconnect = useCallback((row: SourceRow) => {
    if (!registry || !row.source) return;
    registry.transitionSource(row.sourceId, 'activating', 'Reconnect requested from LiveSourcesPanel');
  }, [registry]);

  const handlePermissionRequest = useCallback((source: LiveSource) => {
    if (!permissionService) return;
    void permissionService.request(source.kind).then((result) => {
      setPermissionResults((current) => ({ ...current, [source.id]: result }));
    });
  }, [permissionService]);

  const updatePartialRange = useCallback((
    sourceId: string,
    patch: Partial<PartialBakeRangeState>,
  ) => {
    setPartialBakeRanges((current) => ({
      ...current,
      [sourceId]: {
        ...(current[sourceId] ?? DEFAULT_RANGE_STATE),
        ...patch,
      },
    }));
  }, []);

  const handleStartLearn = useCallback((row: SourceRow, channels: readonly LiveChannelMetadata[]) => {
    if (!registry || !row.source) return;
    const channel = channels[0];
    if (!channel) {
      setMappingDiagnostics((current) => ({
        ...current,
        [row.sourceId]: 'Learn mapping requires an active channel.',
      }));
      return;
    }

    learnSessions.current[row.sourceId]?.dispose();
    const binding = row.bindings[0];
    const session = startLiveMappingLearn(registry, {
      id: `${row.sourceId}:learn`,
      sourceId: row.sourceId,
      channelId: channel.channelId,
      target: {
        kind: 'clip',
        ref: binding?.clipId ?? row.sourceId,
        parameterPath: binding?.binding.targetParamName ?? 'params.live',
        label: binding?.binding.targetParamName ?? sourceLabel(row),
      },
      timeoutMs: 30_000,
      onStateChange: (state) => {
        setLearnStates((current) => ({ ...current, [row.sourceId]: state }));
      },
    });
    learnSessions.current[row.sourceId] = session;
    setLearnStates((current) => ({ ...current, [row.sourceId]: session.getState() }));
    setMappingDiagnostics((current) => {
      const next = { ...current };
      delete next[row.sourceId];
      return next;
    });
  }, [registry]);

  const handleAcceptLearn = useCallback((row: SourceRow) => {
    const session = learnSessions.current[row.sourceId];
    if (!session) return;
    const result = session.acceptCandidate({ table: mappingTable });
    setMappingTable(result.table);
    setLearnStates((current) => ({ ...current, [row.sourceId]: result.state }));
    setMappingDiagnostics((current) => ({
      ...current,
      [row.sourceId]: result.success
        ? 'Mapping accepted.'
        : result.diagnostics[0]?.message ?? 'Mapping has no candidate to accept.',
    }));
  }, [mappingTable]);

  const handleCancelLearn = useCallback((row: SourceRow) => {
    const session = learnSessions.current[row.sourceId];
    if (!session) return;
    const state = session.cancel('LiveSourcesPanel cancel');
    setLearnStates((current) => ({ ...current, [row.sourceId]: state }));
  }, []);

  const handleStartRecordingPass = useCallback((row: SourceRow, channels: readonly LiveChannelMetadata[]) => {
    setRecordingPasses((current) => {
      const pass = passForSource(current[row.sourceId], row, channels);
      const nextTakeId = `take-${pass.takes.length + 1}`;
      const result = startLiveRecordingPass(pass, { takeId: nextTakeId });
      setRecordingDiagnostics((diagnostics) => ({
        ...diagnostics,
        [row.sourceId]: result.success ? `Recording ${nextTakeId}.` : result.diagnostics[0]?.message ?? 'Recording could not start.',
      }));
      return { ...current, [row.sourceId]: result.pass };
    });
  }, []);

  const handleStopRecordingPass = useCallback((row: SourceRow, channels: readonly LiveChannelMetadata[]) => {
    setRecordingPasses((current) => {
      const pass = current[row.sourceId];
      if (!pass) return current;
      const result = stopLiveRecordingPass(pass, {
        channelIds: channels.map((channel) => channel.channelId),
        sampleCount: channels.reduce((total, channel) => total + (registry?.getSampleCount(channel.channelId) ?? 0), 0),
      });
      setRecordingDiagnostics((diagnostics) => ({
        ...diagnostics,
        [row.sourceId]: result.success ? 'Take ready for review.' : result.diagnostics[0]?.message ?? 'Recording could not stop.',
      }));
      return { ...current, [row.sourceId]: result.pass };
    });
  }, [registry]);

  const handleReviewTake = useCallback((
    row: SourceRow,
    takeId: string,
    action: 'accept' | 'discard',
  ) => {
    setRecordingPasses((current) => {
      const pass = current[row.sourceId];
      if (!pass) return current;
      const result = action === 'accept'
        ? acceptLiveRecordingTake(pass, takeId)
        : discardLiveRecordingTake(pass, takeId);
      setRecordingDiagnostics((diagnostics) => ({
        ...diagnostics,
        [row.sourceId]: result.success
          ? `Take ${takeId} ${action === 'accept' ? 'accepted' : 'discarded'}.`
          : result.diagnostics[0]?.message ?? 'Take review failed.',
      }));
      return { ...current, [row.sourceId]: result.pass };
    });
  }, []);

  if (!registry && !timelineConfig) {
    return null;
  }

  return (
    <section
      className={cn(
        'pointer-events-auto rounded-md border border-border/70 bg-background/90 text-left text-[10px] text-muted-foreground shadow-sm backdrop-blur-sm',
        compact ? 'w-72 p-2' : 'w-80 p-2',
      )}
      data-video-editor-live-sources-panel="true"
      aria-label="Live sources"
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-foreground">
          <Radio className="h-3.5 w-3.5 text-sky-300" aria-hidden="true" />
          <span>Live Sources</span>
        </div>
        {exportBlockers.length > 0 ? (
          <span
            className="inline-flex items-center gap-1 rounded border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] text-red-300"
            data-video-editor-live-export-blocked="true"
          >
            <ShieldAlert className="h-2.5 w-2.5" aria-hidden="true" />
            Export blocked
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] text-emerald-300">
            <CheckCircle2 className="h-2.5 w-2.5" aria-hidden="true" />
            Export clear
          </span>
        )}
      </div>

      {rows.length === 0 ? (
        <div className="rounded border border-dashed border-border/70 px-2 py-1.5 text-[10px] text-muted-foreground">
          No live sources or persisted live bindings.
        </div>
      ) : (
        <div className="space-y-1.5">
          {rows.map((row) => {
            const status = sourceStatusForRow(row);
            const channels = snapshot.channels.filter((channel) => channel.sourceId === row.sourceId);
            const diagnostics = diagnosticsForRow(row);
            const permission = row.source
              ? (permissionResults[row.sourceId]?.permission ?? row.source.permission ?? permissionService?.probe(row.source.kind).permission)
              : undefined;
            const recording = row.source?.recording;
            const bakeResult = bakeResults[row.sourceId];
            const blockedBindings = row.bindings.filter((binding) => binding.blocksExport);
            const partialRange = partialBakeRanges[row.sourceId] ?? DEFAULT_RANGE_STATE;
            const learnState = learnStates[row.sourceId];
            const mappingMessage = mappingDiagnostics[row.sourceId];
            const sourceMappings = mappingTable.entries.filter((entry) => entry.sourceId === row.sourceId);
            const pass = recordingPasses[row.sourceId];
            const recordingMessage = recordingDiagnostics[row.sourceId];
            const audioChannels = channels.filter((channel) => channel.kind === 'audio');

            return (
              <article
                key={row.sourceId}
                className="space-y-1 rounded border border-border/70 bg-card/80 px-2 py-1.5"
                data-video-editor-live-source-row={row.sourceId}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[11px] font-medium text-foreground">{sourceLabel(row)}</div>
                    <div className="truncate font-mono text-[9px] text-muted-foreground">{row.sourceId}</div>
                  </div>
                  <span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[9px]', STATUS_CLASS[status])}>
                    {status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-1 text-[9px]">
                  <div>
                    <span className="text-muted-foreground/70">Bindings </span>
                    <span className={blockedBindings.length > 0 ? 'text-red-300' : 'text-foreground'}>{row.bindings.length}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground/70">Channels </span>
                    <span className={channels.length > 0 ? 'text-foreground' : 'text-muted-foreground'}>{channels.length}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground/70">Permission </span>
                    <span className={permission?.state === 'granted' ? 'text-emerald-300' : permission?.state === 'denied' ? 'text-red-300' : 'text-foreground'}>
                      {permission ? PERMISSION_LABEL[permission.state] : 'not required'}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground/70">Recording </span>
                    <span className={recording?.active ? 'text-red-300' : 'text-foreground'}>
                      {recording
                        ? `${recording.active ? 'recording' : 'idle'} (${recording.mode === 'take' && recording.takeIndex !== undefined ? `take ${recording.takeIndex}` : recording.mode})`
                        : 'idle'}
                    </span>
                  </div>
                </div>

                {channels.length > 0 && (
                  <div className="space-y-0.5 rounded bg-background/60 px-1.5 py-1" data-video-editor-live-preview-health="true">
                    {channels.map((channel) => (
                      <div key={channel.channelId} className="flex items-center justify-between gap-2 text-[9px]">
                        <span className="truncate">{channel.kind} · {channel.channelId}</span>
                        <span className="shrink-0 text-muted-foreground/80">
                          {registry?.getSampleCount(channel.channelId) ?? 0} samples · {latestSampleSummary(registry, channel.channelId)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="space-y-1 rounded border border-border/60 bg-background/50 px-1.5 py-1" data-video-editor-live-partial-bake="true">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[9px] font-medium text-foreground">Partial bake</span>
                    <select
                      aria-label={`Bake range mode for ${row.sourceId}`}
                      className="h-5 rounded border border-border bg-background px-1 text-[9px] text-foreground"
                      value={partialRange.mode}
                      onChange={(event) => updatePartialRange(row.sourceId, { mode: event.currentTarget.value as PartialBakeRangeState['mode'] })}
                    >
                      <option value="frame">Frames</option>
                      <option value="time">Time ms</option>
                      <option value="sample">Samples</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-[1fr_1fr_1.2fr] gap-1">
                    <input
                      aria-label={`Bake range start for ${row.sourceId}`}
                      className="h-6 min-w-0 rounded border border-border bg-background px-1 text-[9px] text-foreground"
                      inputMode="numeric"
                      placeholder="start"
                      value={partialRange.start}
                      onChange={(event) => updatePartialRange(row.sourceId, { start: event.currentTarget.value })}
                    />
                    <input
                      aria-label={`Bake range end for ${row.sourceId}`}
                      className="h-6 min-w-0 rounded border border-border bg-background px-1 text-[9px] text-foreground"
                      inputMode="numeric"
                      placeholder="end"
                      value={partialRange.end}
                      onChange={(event) => updatePartialRange(row.sourceId, { end: event.currentTarget.value })}
                    />
                    <input
                      aria-label={`Bake take ID for ${row.sourceId}`}
                      className="h-6 min-w-0 rounded border border-border bg-background px-1 text-[9px] text-foreground"
                      placeholder="take id"
                      value={partialRange.takeId}
                      onChange={(event) => updatePartialRange(row.sourceId, { takeId: event.currentTarget.value })}
                    />
                  </div>
                </div>

                <div className="space-y-1 rounded border border-border/60 bg-background/50 px-1.5 py-1" data-video-editor-live-recording-pass="true">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[9px] font-medium text-foreground">Recording pass</span>
                    <span className="text-[9px] text-muted-foreground">
                      {pass ? `${pass.status} · ${pass.takes.length} take${pass.takes.length === 1 ? '' : 's'}` : 'idle · 0 takes'}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-6 gap-1 px-2 text-[9px]"
                      onClick={() => handleStartRecordingPass(row, channels)}
                      disabled={!row.source || pass?.status === 'recording'}
                    >
                      <Radio className="h-3 w-3" />
                      Start
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-6 gap-1 px-2 text-[9px]"
                      onClick={() => handleStopRecordingPass(row, channels)}
                      disabled={!pass || pass.status !== 'recording'}
                    >
                      <Square className="h-3 w-3" />
                      Stop
                    </Button>
                  </div>
                  {recordingMessage && (
                    <div className="text-[9px] text-muted-foreground">{recordingMessage}</div>
                  )}
                  {pass && pass.takes.length > 0 && (
                    <div className="space-y-1" data-video-editor-live-take-review="true">
                      {pass.takes.map((take) => (
                        <div key={take.id} className="grid grid-cols-[1fr_auto_auto] items-center gap-1 rounded bg-card/70 px-1 py-0.5 text-[9px]">
                          <span className="truncate">
                            Take {take.index + 1} · {take.status} · {take.sampleCount} samples
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-5 px-1.5 text-[9px]"
                            onClick={() => handleReviewTake(row, take.id, 'accept')}
                            disabled={take.status === 'accepted' || take.status === 'discarded' || take.status === 'baked'}
                          >
                            Accept
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-5 px-1.5 text-[9px]"
                            onClick={() => handleReviewTake(row, take.id, 'discard')}
                            disabled={take.status === 'accepted' || take.status === 'discarded' || take.status === 'baked'}
                          >
                            Discard
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-1 rounded border border-border/60 bg-background/50 px-1.5 py-1" data-video-editor-live-mapping="true">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[9px] font-medium text-foreground">Mapping</span>
                    <span className={cn('rounded border px-1 py-0.5 text-[9px]', (learnState?.visual.learnMode ?? row.source?.learnMode) === 'mapping'
                      ? 'border-sky-500/30 bg-sky-500/10 text-sky-300'
                      : 'border-border text-muted-foreground')}
                    >
                      {learnState?.visual.learnMode ?? row.source?.learnMode ?? 'idle'}
                    </span>
                  </div>
                  <div className="text-[9px] text-muted-foreground">
                    {learnState?.visual.message ?? mappingMessage ?? `${sourceMappings.length} mapping${sourceMappings.length === 1 ? '' : 's'}`}
                  </div>
                  {learnState?.candidate && (
                    <div className="rounded bg-sky-500/10 px-1 py-0.5 text-[9px] text-sky-200">
                      Candidate {learnState.candidate.sequenceNumber} · {learnState.candidate.sampleFormat}
                    </div>
                  )}
                  {sourceMappings.length > 0 && (
                    <div className="space-y-0.5" data-video-editor-live-mapping-table="true">
                      {sourceMappings.map((entry) => (
                        <div key={entry.mappingId} className="grid grid-cols-[1fr_auto] gap-1 text-[9px]">
                          <span className="truncate">{entry.target.label ?? entry.target.parameterPath}</span>
                          <span className="text-muted-foreground">{entry.channelKind}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-1">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-6 gap-1 px-2 text-[9px]"
                      onClick={() => handleStartLearn(row, channels)}
                      disabled={!row.source}
                    >
                      <SlidersHorizontal className="h-3 w-3" />
                      Learn
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-6 px-2 text-[9px]"
                      onClick={() => handleAcceptLearn(row)}
                      disabled={learnState?.status !== 'candidate'}
                    >
                      Accept mapping
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-[9px]"
                      onClick={() => handleCancelLearn(row)}
                      disabled={!learnState || learnState.status !== 'listening'}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>

                {audioChannels.length > 0 ? (
                  <div className="space-y-1 rounded border border-border/60 bg-background/50 px-1.5 py-1" data-video-editor-live-audio-overlay="true">
                    <div className="flex items-center gap-1 text-[9px] font-medium text-foreground">
                      <Gauge className="h-3 w-3" aria-hidden="true" />
                      Audio analysis
                    </div>
                    {audioChannels.map((channel) => {
                      const overlay = audioOverlayForChannel(registry, channel);
                      return (
                        <div key={channel.channelId} className="space-y-0.5">
                          <div className={cn('text-[9px]', overlay.status === 'error' ? 'text-red-300' : overlay.status === 'empty' ? 'text-muted-foreground' : 'text-emerald-300')}>
                            {overlay.message}
                          </div>
                          {overlay.status === 'ready' && (
                            <div className="grid h-4 grid-cols-8 items-end gap-0.5" aria-label={`Audio bars for ${channel.channelId}`}>
                              {overlay.bars.slice(0, 8).map((value, index) => (
                                <span
                                  key={`${channel.channelId}:bar:${index}`}
                                  className="block min-h-0.5 rounded-sm bg-emerald-300/80"
                                  style={{ height: `${Math.max(8, Math.min(100, value * 100))}%` }}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded border border-border/60 bg-background/50 px-1.5 py-1 text-[9px] text-muted-foreground" data-video-editor-live-audio-overlay="empty">
                    Audio analysis waiting for an audio channel.
                  </div>
                )}

                {(status === 'disposed' || status === 'orphaned' || status === 'missing') && (
                  <div className="flex items-start gap-1 rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-1 text-[9px] text-amber-200">
                    <WifiOff className="mt-0.5 h-2.5 w-2.5 shrink-0" aria-hidden="true" />
                    <span>Persisted bindings remain export-blocking until they are baked or removed.</span>
                  </div>
                )}

                {diagnostics.length > 0 && (
                  <div className="space-y-0.5" data-video-editor-live-source-diagnostics="true">
                    {diagnostics.slice(0, 3).map((diagnostic, index) => (
                      <div key={`${diagnostic.code}:${index}`} className="flex items-start gap-1 text-[9px] text-yellow-300">
                        <AlertTriangle className="mt-0.5 h-2.5 w-2.5 shrink-0" aria-hidden="true" />
                        <span className="line-clamp-2">{diagnostic.message}</span>
                      </div>
                    ))}
                  </div>
                )}

                {bakeResult && (
                  <div className={cn('rounded px-1.5 py-1 text-[9px]', bakeResult.success ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300')}>
                    Bake {bakeResult.success ? 'queued deterministic refs' : 'failed'} · {bakeResult.targets.length} target{bakeResult.targets.length === 1 ? '' : 's'}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-1">
                  {row.source && permission?.state === 'prompt' && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-6 gap-1 px-2 text-[9px]"
                      onClick={() => handlePermissionRequest(row.source!)}
                    >
                      <ShieldAlert className="h-3 w-3" />
                      Permit
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-6 gap-1 px-2 text-[9px]"
                    onClick={() => handleBake(row)}
                    disabled={!row.source}
                    title={row.source ? 'Bake live samples into deterministic output' : 'Cannot bake without a live source'}
                  >
                    <Scissors className="h-3 w-3" />
                    Bake
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-6 gap-1 px-2 text-[9px]"
                    onClick={() => handleReconnect(row)}
                    disabled={!row.source || row.source.status === 'active'}
                    title={row.source ? 'Request source reconnect' : 'Cannot reconnect a missing, disposed, or orphaned runtime source'}
                  >
                    <RefreshCw className="h-3 w-3" />
                    Reconnect
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-6 gap-1 px-2 text-[9px] text-red-300 hover:text-red-200"
                    onClick={() => handleRemove(row)}
                    disabled={row.bindings.length === 0}
                    title="Remove persisted live binding metadata for this source"
                  >
                    <Trash2 className="h-3 w-3" />
                    Remove
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
