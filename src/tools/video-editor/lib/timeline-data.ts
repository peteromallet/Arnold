import type {
  TimelineAction,
  TimelineEffect as EditorTimelineEffect,
  TimelineRow,
} from '@/tools/video-editor/types/timeline-canvas.ts';
import {
  getClipSourceDuration,
  getConfigSignature,
  getStableConfigSignature,
  resolveTimelineConfig as resolveTimelineConfigShared,
  type UrlResolver,
} from '@/tools/video-editor/lib/config-utils.ts';
import { TIMELINE_CLIP_FIELDS } from '@/tools/video-editor/lib/serialize.ts';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type {
  AssetMissingRequest,
  AssetResolver,
} from '@/tools/video-editor/data/AssetResolver.ts';
import type {
  AssetRegistry,
  ClipType,
  ResolvedTimelineConfig,
  TimelineClip,
  TimelineConfig,
  TimelineOutput,
  TrackDefinition,
  TrackKind,
} from '@/tools/video-editor/types/index.ts';
import {
  canonicalizeTimelinePair,
  serializeTimelineConfigSnapshot,
} from '@/tools/video-editor/lib/timeline-domain.ts';

export interface ClipMeta {
  asset?: string;
  track: string;
  clipType?: ClipType;
  from?: number;
  to?: number;
  speed?: number;
  hold?: number;
  volume?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  cropTop?: number;
  cropBottom?: number;
  cropLeft?: number;
  cropRight?: number;
  opacity?: number;
  text?: TimelineClip['text'];
  entrance?: TimelineClip['entrance'];
  exit?: TimelineClip['exit'];
  continuous?: TimelineClip['continuous'];
  transition?: TimelineClip['transition'];
  effects?: TimelineClip['effects'];
  params?: TimelineClip['params'];
  pool_id?: TimelineClip['pool_id'];
  clip_order?: TimelineClip['clip_order'];
  source_uuid?: TimelineClip['source_uuid'];
  generation?: TimelineClip['generation'];
  keyframes?: TimelineClip['keyframes'];
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export type ClipOrderMap = Record<string, string[]>;

export interface TimelineData {
  config: TimelineConfig;
  configVersion: number;
  registry: AssetRegistry;
  resolvedConfig: ResolvedTimelineConfig;
  rows: TimelineRow[];
  meta: Record<string, ClipMeta>;
  effects: Record<string, EditorTimelineEffect>;
  assetMap: Record<string, string>;
  output: TimelineOutput;
  tracks: TrackDefinition[];
  clipOrder: ClipOrderMap;
  signature: string;
  stableSignature: string;
}

const ASSET_COLORS: Record<string, string> = {
  'output-composition': '#e06c75',
  'venn-diagram': '#61afef',
  'demo-one': '#98c379',
  'demo-two': '#c678dd',
  'example-video': '#56b6c2',
  'example-image1': '#d19a66',
  'example-image2': '#e5c07b',
  input: '#61afef',
};

const TIMELINE_TIME_PRECISION = 4;
const TIMELINE_TIME_FACTOR = 10 ** TIMELINE_TIME_PRECISION;
const roundTimelineTime = (value: number): number => Math.round(value * TIMELINE_TIME_FACTOR) / TIMELINE_TIME_FACTOR;

const effectIdForClip = (clipId: string): string => `effect-${clipId}`;
const clonePinnedShotGroups = (
  pinnedShotGroups: TimelineConfig['pinnedShotGroups'],
): TimelineConfig['pinnedShotGroups'] => pinnedShotGroups?.map((group) => ({
  shotId: group.shotId,
  trackId: group.trackId,
  clipIds: [...group.clipIds],
  mode: group.mode,
  videoAssetKey: group.videoAssetKey,
  imageClipSnapshot: group.imageClipSnapshot?.map((snapshot) => ({
    ...snapshot,
    meta: { ...snapshot.meta },
  })),
}));

const getClipDurationSeconds = (clip: TimelineClip): number => {
  return getClipSourceDuration(clip) / (clip.speed ?? 1);
};

const getDefaultClipMeta = (clip: TimelineClip): ClipMeta => {
  return {
    asset: clip.asset,
    track: clip.track,
    clipType: clip.clipType,
    from: clip.from,
    to: clip.to,
    speed: clip.speed,
    hold: clip.hold,
    volume: clip.volume,
    x: clip.x,
    y: clip.y,
    width: clip.width,
    height: clip.height,
    cropTop: clip.cropTop,
    cropBottom: clip.cropBottom,
    cropLeft: clip.cropLeft,
    cropRight: clip.cropRight,
    opacity: clip.opacity,
    text: clip.text,
    entrance: clip.entrance,
    exit: clip.exit,
    continuous: clip.continuous,
    transition: clip.transition,
    effects: clip.effects,
    params: clip.params,
    pool_id: clip.pool_id,
    clip_order: clip.clip_order,
    source_uuid: clip.source_uuid,
    generation: clip.generation,
    keyframes: clip.keyframes,
  };
};

const resolveAssetUrl = (file: string): string => {
  if (/^https?:\/\//.test(file)) {
    return file;
  }

  const normalized = file.replace(/\\/g, '/').replace(/^\/+/, '');
  return `/${normalized}`;
};

const buildAssetMap = (registry: AssetRegistry): Record<string, string> => {
  return Object.fromEntries(
    Object.entries(registry.assets ?? {}).map(([assetId, entry]) => [assetId, entry.file]),
  );
};

export const resolveTimelineConfig = async (
  config: TimelineConfig,
  registry: AssetRegistry,
  urlResolver?: UrlResolver,
): Promise<ResolvedTimelineConfig> => {
  return resolveTimelineConfigShared(config, registry, urlResolver ?? resolveAssetUrl);
};

export const configToRows = (
  config: TimelineConfig,
): Pick<TimelineData, 'rows' | 'meta' | 'effects' | 'clipOrder' | 'tracks'> => {
  const clipOrder: ClipOrderMap = Object.fromEntries(
    (config.tracks ?? []).map((track) => [track.id, []]),
  );
  const effects: Record<string, EditorTimelineEffect> = {};
  const meta: Record<string, ClipMeta> = {};
  const rowsByTrack = new Map<string, TimelineAction[]>();

  for (const track of config.tracks ?? []) {
    rowsByTrack.set(track.id, []);
  }

  for (const clip of config.clips) {
    const clipId = clip.id;

    clipOrder[clip.track] ??= [];
    clipOrder[clip.track].push(clipId);
    effects[effectIdForClip(clipId)] = { id: effectIdForClip(clipId) };
    meta[clipId] = getDefaultClipMeta(clip);

    const action: TimelineAction = {
      id: clipId,
      start: clip.at,
      end: clip.at + getClipDurationSeconds(clip),
      effectId: effectIdForClip(clipId),
    };

    rowsByTrack.get(clip.track)?.push(action);
  }

  return {
    rows: (config.tracks ?? []).map((track) => ({
      id: track.id,
      actions: rowsByTrack.get(track.id) ?? [],
    })),
    meta,
    effects,
    clipOrder,
    tracks: config.tracks ?? [],
  };
};

export const rowsToConfig = (
  rows: TimelineRow[],
  meta: Record<string, ClipMeta>,
  output: TimelineOutput,
  clipOrder: ClipOrderMap,
  tracks: TrackDefinition[],
  pinnedShotGroups?: TimelineConfig['pinnedShotGroups'],
  extras?: Pick<TimelineConfig, 'theme' | 'theme_overrides' | 'generation_defaults'>,
): TimelineConfig => {
  const actionMap = new Map<string, TimelineAction>();
  const trackActionIds: Record<string, string[]> = Object.fromEntries(tracks.map((track) => [track.id, []]));

  for (const row of rows) {
    for (const action of row.actions) {
      if (action.id.startsWith('uploading-')) continue;
      const clipMeta = meta[action.id];
      if (!clipMeta) {
        continue;
      }

      actionMap.set(action.id, action);
      trackActionIds[row.id] ??= [];
      trackActionIds[row.id].push(action.id);
    }
  }

  const clips: TimelineClip[] = [];
  for (const track of tracks) {
    const baseOrder = (clipOrder[track.id] ?? []).filter((clipId) => actionMap.has(clipId));
    const appendedIds = (trackActionIds[track.id] ?? []).filter((clipId) => !baseOrder.includes(clipId));

    for (const clipId of [...baseOrder, ...appendedIds]) {
      const action = actionMap.get(clipId);
      const clipMeta = meta[clipId];
      if (!action || !clipMeta) {
        continue;
      }

      const roundedStart = roundTimelineTime(action.start);
      const roundedEnd = roundTimelineTime(action.end);

      const nextClip: Partial<TimelineClip> = {
        id: clipId,
        at: roundedStart,
        track: track.id,
        clipType: clipMeta.clipType,
        asset: clipMeta.asset,
        from: clipMeta.from,
        to: clipMeta.to,
        speed: clipMeta.speed,
        hold: clipMeta.hold,
        volume: clipMeta.volume,
        x: clipMeta.x,
        y: clipMeta.y,
        width: clipMeta.width,
        height: clipMeta.height,
        cropTop: clipMeta.cropTop,
        cropBottom: clipMeta.cropBottom,
        cropLeft: clipMeta.cropLeft,
        cropRight: clipMeta.cropRight,
        opacity: clipMeta.opacity,
        text: clipMeta.text,
        entrance: clipMeta.entrance,
        exit: clipMeta.exit,
        continuous: clipMeta.continuous,
        transition: clipMeta.transition,
        effects: clipMeta.effects,
        params: clipMeta.params,
        pool_id: clipMeta.pool_id,
        clip_order: clipMeta.clip_order,
        source_uuid: clipMeta.source_uuid,
        generation: clipMeta.generation,
        keyframes: clipMeta.keyframes,
      };

      if (typeof clipMeta.hold === 'number') {
        nextClip.hold = roundTimelineTime(roundedEnd - roundedStart);
        delete nextClip.from;
        delete nextClip.to;
        delete nextClip.speed;
      } else {
        const speed = clipMeta.speed ?? 1;
        const from = roundTimelineTime(clipMeta.from ?? 0);
        nextClip.from = from;
        nextClip.to = roundTimelineTime(getSourceTime({ from, start: roundedStart, speed }, roundedEnd));
      }

      const serializedClip: Partial<TimelineClip> = {
        id: nextClip.id,
        at: nextClip.at,
        track: nextClip.track,
      };

      if (nextClip.asset !== undefined) {
        serializedClip.asset = nextClip.asset;
      }

      for (const field of TIMELINE_CLIP_FIELDS) {
        if (field in serializedClip) {
          continue;
        }

        const value = nextClip[field];
        if (value !== undefined) {
          serializedClip[field] = value as never;
        }
      }

      clips.push(serializedClip as TimelineClip);
    }
  }

  const config: TimelineConfig = {
    output: { ...output },
    tracks: tracks.map((track) => ({ ...track })),
    clips,
  };
  if (pinnedShotGroups && pinnedShotGroups.length > 0) {
    config.pinnedShotGroups = clonePinnedShotGroups(pinnedShotGroups);
  }
  if (extras?.theme !== undefined) {
    config.theme = extras.theme;
  }
  if (extras?.theme_overrides !== undefined) {
    config.theme_overrides = extras.theme_overrides;
  }
  if (extras?.generation_defaults !== undefined) {
    config.generation_defaults = extras.generation_defaults;
  }
  return serializeTimelineConfigSnapshot(config).config;
};

interface AssembleTimelineDataParams {
  config: TimelineConfig;
  configVersion: number;
  registry: AssetRegistry;
  resolvedConfig: ResolvedTimelineConfig;
  output: TimelineOutput;
  assetMap: Record<string, string>;
}

/**
 * Assembles TimelineData from already-derived inputs.
 * The provided config must already be migrated to the canonical flat-track shape.
 */
export const assembleTimelineData = ({
  config,
  configVersion,
  registry,
  resolvedConfig,
  output,
  assetMap,
}: AssembleTimelineDataParams): TimelineData => {
  const rowData = configToRows(config);

  return {
    config,
    configVersion,
    registry,
    resolvedConfig,
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap,
    output,
    tracks: rowData.tracks,
    clipOrder: rowData.clipOrder,
    signature: getConfigSignature(resolvedConfig),
    stableSignature: getStableConfigSignature(config, registry),
  };
};

export const buildTimelineData = async (
  config: TimelineConfig,
  registry: AssetRegistry,
  urlResolver?: UrlResolver,
  configVersion = 1,
): Promise<TimelineData> => {
  const canonical = canonicalizeTimelinePair(config, registry);
  const resolvedConfig = await resolveTimelineConfig(canonical.config, canonical.registry, urlResolver);

  return assembleTimelineData({
    config: canonical.config,
    configVersion,
    registry: canonical.registry,
    resolvedConfig,
    output: { ...canonical.config.output },
    assetMap: buildAssetMap(canonical.registry),
  });
};

function isAssetResolverArg(value: unknown): value is AssetResolver {
  return (
    typeof value === 'object'
    && value !== null
    && typeof (value as { resolveAssetUrl?: unknown }).resolveAssetUrl === 'function'
  );
}

/**
 * Build a TimelineData using the resolver-hook contract (`onResolve`,
 * `onMissing`). Used for refresh paths and unit tests that exercise the
 * pluggable resolver lifecycle. Production load paths can keep calling
 * `buildTimelineData(config, registry, urlResolver, configVersion)`.
 */
export const buildTimelineDataWithResolver = async (
  config: TimelineConfig,
  registry: AssetRegistry,
  resolver: AssetResolver,
  configVersion = 1,
  timelineId?: string,
): Promise<TimelineData> => {
  const canonical = canonicalizeTimelinePair(config, registry);

  const urlResolver: UrlResolver = (file) => {
    if (resolver.onResolve) {
      return resolver.onResolve({ file, timelineId });
    }
    return resolver.resolveAssetUrl(file);
  };

  const resolvedConfig = await resolveTimelineConfig(canonical.config, canonical.registry, urlResolver);

  // Surface missing-asset references through the resolver lifecycle so
  // the host can render a tombstone / retry path.
  if (resolver.onMissing) {
    const registeredAssets = canonical.registry.assets ?? {};
    for (const clip of canonical.config.clips) {
      if (!clip.asset) continue;
      const entry = registeredAssets[clip.asset];
      if (!entry) {
        const missingRequest: AssetMissingRequest = {
          assetId: clip.asset,
          reason: 'missing_asset',
          clipId: clip.id,
          timelineId,
          clip,
          config: canonical.config,
          registry: canonical.registry,
        };
        // Fire-and-forget — host listens.
        await resolver.onMissing(missingRequest);
      }
    }
  }

  return assembleTimelineData({
    config: canonical.config,
    configVersion,
    registry: canonical.registry,
    resolvedConfig,
    output: { ...canonical.config.output },
    assetMap: buildAssetMap(canonical.registry),
  });
};

export function loadTimelineJsonFromProvider(
  provider: DataProvider,
  timelineIdOrResolver: string | AssetResolver,
  resolverOrTimelineId?: UrlResolver | string,
  legacyUrlResolver?: UrlResolver,
): Promise<TimelineData> {
  // New shape: (provider, assetResolver, timelineId)
  if (isAssetResolverArg(timelineIdOrResolver)) {
    const assetResolver = timelineIdOrResolver;
    const timelineId = String(resolverOrTimelineId ?? '');
    return (async () => {
      const [loadedTimeline, registry] = await Promise.all([
        provider.loadTimeline(timelineId),
        provider.loadAssetRegistry(timelineId),
      ]);
      return buildTimelineDataWithResolver(
        loadedTimeline.config,
        registry,
        assetResolver,
        loadedTimeline.configVersion,
        timelineId,
      );
    })();
  }

  // Legacy shape: (provider, timelineId, urlResolver?)
  const timelineId = timelineIdOrResolver as string;
  const urlResolver = (resolverOrTimelineId as UrlResolver | undefined)
    ?? legacyUrlResolver
    ?? ((file: string) => provider.resolveAssetUrl(file));
  return (async () => {
    const [loadedTimeline, registry] = await Promise.all([
      provider.loadTimeline(timelineId),
      provider.loadAssetRegistry(timelineId),
    ]);
    return buildTimelineData(
      loadedTimeline.config,
      registry,
      urlResolver,
      loadedTimeline.configVersion,
    );
  })();
}

export async function loadTranscript(
  providerOrResolver: DataProvider | AssetResolver,
  assetKey: string,
  timelineId?: string,
): Promise<TranscriptSegment[]> {
  // Resolver-aware path: prefer onProfileLoad if installed.
  if (
    typeof (providerOrResolver as AssetResolver).onProfileLoad === 'function'
  ) {
    const resolver = providerOrResolver as AssetResolver;
    const profile = await resolver.onProfileLoad?.({ assetId: assetKey, timelineId });
    return profile?.transcript?.segments ?? [];
  }

  // Legacy path: provider.loadAssetProfile(assetId) or resolver.loadAssetProfile.
  const legacy = (providerOrResolver as { loadAssetProfile?: (id: string) => Promise<{ transcript?: { segments?: TranscriptSegment[] } } | null> }).loadAssetProfile;
  const profile = legacy ? await legacy(assetKey) : null;
  return profile?.transcript?.segments ?? [];
}

export function getAssetColor(asset: string): string {
  return ASSET_COLORS[asset] ?? '#abb2bf';
}

export function getSourceTime(clip: { from: number; start: number; speed: number }, time: number): number {
  return clip.from + (time - clip.start) * clip.speed;
}

export function inferTrackType(filePath: string): TrackKind {
  const ext = filePath.slice(filePath.lastIndexOf('.')).toLowerCase();
  if (['.mp4', '.webm', '.mov'].includes(ext)) {
    return 'visual';
  }

  if (['.mp3', '.wav', '.aac', '.m4a'].includes(ext)) {
    return 'audio';
  }

  return 'visual';
}

export function preserveUploadingClips(source: TimelineData, target: TimelineData): TimelineData {
  const uploadingMeta: Record<string, ClipMeta> = {};
  const uploadingActions: Record<string, TimelineAction[]> = {};
  let found = false;
  for (const row of source.rows) {
    for (const action of row.actions) {
      if (action.id.startsWith('uploading-') && source.meta[action.id]) {
        uploadingActions[row.id] ??= [];
        uploadingActions[row.id].push(action);
        uploadingMeta[action.id] = source.meta[action.id];
        found = true;
      }
    }
  }
  if (!found) return target;

  const nextRows = target.rows.map((row) => {
    const extras = uploadingActions[row.id];
    return extras ? { ...row, actions: [...row.actions, ...extras] } : row;
  });
  return { ...target, rows: nextRows, meta: { ...target.meta, ...uploadingMeta } };
}

export function getNextClipId(meta: Record<string, ClipMeta>): string {
  let max = -1;
  for (const id of Object.keys(meta)) {
    const match = id.match(/^clip-(\d+)$/);
    if (match) {
      max = Math.max(max, Number.parseInt(match[1], 10));
    }
  }
  return `clip-${max + 1}`;
}

export function createEffectLayerClipMeta(trackId: string): ClipMeta {
  return {
    track: trackId,
    clipType: 'effect-layer',
    hold: 5,
  };
}
