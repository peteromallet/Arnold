import type {
  AssetRegistry,
  ResolvedAssetRegistryEntry,
  ResolvedTimelineConfig,
  TimelineClip,
  TimelineConfig,
} from '@/tools/video-editor/types';

export const parseResolution = (resolution: string): { width: number; height: number } => {
  const [width, height] = resolution.toLowerCase().split('x');
  return {
    width: Number(width),
    height: Number(height),
  };
};

export const getClipSourceDuration = (clip: TimelineClip): number => {
  if (typeof clip.hold === 'number') {
    return clip.hold;
  }

  return (clip.to ?? 0) - (clip.from ?? 0);
};

export const getClipTimelineDuration = (clip: TimelineClip): number => {
  const speed = clip.speed ?? 1;
  return getClipSourceDuration(clip) / speed;
};

export const secondsToFrames = (seconds: number, fps: number): number => {
  return Math.round(seconds * fps);
};

export const getSanitizedMediaTrimProps = (
  clip: Pick<TimelineClip, 'from' | 'to'>,
  fps: number,
): { trimBefore: number; trimAfter?: number } => {
  const trimBeforeSeconds = typeof clip.from === 'number' && Number.isFinite(clip.from)
    ? Math.max(0, clip.from)
    : 0;
  const trimAfterSeconds = typeof clip.to === 'number' && Number.isFinite(clip.to) && clip.to > trimBeforeSeconds
    ? clip.to
    : undefined;

  return {
    trimBefore: secondsToFrames(trimBeforeSeconds, fps),
    ...(trimAfterSeconds === undefined ? {} : { trimAfter: secondsToFrames(trimAfterSeconds, fps) }),
  };
};

export const getSanitizedPlaybackRate = (speed: TimelineClip['speed']): number => {
  return typeof speed === 'number' && Number.isFinite(speed) && speed > 0 ? speed : 1;
};

export const getSanitizedVolume = (volume: number | undefined, fallback = 1): number => {
  return typeof volume === 'number' && Number.isFinite(volume)
    ? Math.max(0, volume)
    : fallback;
};

export const getSanitizedAssetFile = (file: string | undefined): string | null => {
  return typeof file === 'string' && file.trim().length > 0 ? file.trim() : null;
};

export const getSanitizedMediaSrc = (src: string | undefined): string | null => {
  if (typeof src !== 'string') {
    return null;
  }

  const trimmed = src.trim();
  if (trimmed.length === 0) {
    return null;
  }

  if (/^(?:https?:\/\/|\/)/.test(trimmed)) {
    try {
      const url = new URL(trimmed, 'http://localhost');
      if (url.pathname.endsWith('/')) {
        return null;
      }
    } catch {
      return null;
    }
  }

  return trimmed;
};

export const getClipDurationInFrames = (clip: TimelineClip, fps: number): number => {
  return Math.max(1, secondsToFrames(getClipTimelineDuration(clip), fps));
};

export const getTimelineDurationInFrames = (config: ResolvedTimelineConfig, fps: number): number => {
  return Math.max(
    1,
    ...config.clips.map((clip) => {
      return secondsToFrames(clip.at, fps) + getClipDurationInFrames(clip, fps);
    }),
  );
};

export const getEffectValue = (
  effects: TimelineClip['effects'],
  name: 'fade_in' | 'fade_out',
): number | null => {
  if (!effects) {
    return null;
  }

  if (!Array.isArray(effects)) {
    return typeof effects[name] === 'number' ? effects[name] : null;
  }

  for (const effect of effects) {
    if (typeof effect[name] === 'number') {
      return effect[name] ?? null;
    }
  }

  return null;
};

export const getConfigSignature = (
  config: ResolvedTimelineConfig | TimelineConfig,
): string => JSON.stringify(config);

const normalizeForStableJson = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map((item) => {
      const normalized = normalizeForStableJson(item);
      return normalized === undefined ? null : normalized;
    });
  }

  if (value && typeof value === 'object') {
    return Object.keys(value)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        const normalized = normalizeForStableJson((value as Record<string, unknown>)[key]);
        if (normalized !== undefined) {
          acc[key] = normalized;
        }
        return acc;
      }, {});
  }

  return value;
};

export const getStableConfigSignature = (
  config: TimelineConfig,
  registry: AssetRegistry,
): string => {
  return JSON.stringify(normalizeForStableJson({
    config,
    registry,
  }));
};

export type UrlResolver = (file: string) => string | Promise<string>;

export const isRemoteUrl = (url: string): boolean => /^https?:\/\//.test(url);

export const resolveTimelineConfig = async (
  config: TimelineConfig,
  registry: AssetRegistry,
  resolveUrl: UrlResolver,
): Promise<ResolvedTimelineConfig> => {
  const resolvedRegistry: Record<string, ResolvedAssetRegistryEntry> = {};

  await Promise.all(
    Object.entries(registry.assets ?? {}).map(async ([assetId, entry]) => {
      const sanitizedFile = getSanitizedAssetFile(entry.file);
      if (!sanitizedFile) {
        console.warn(`Asset '${assetId}' has no file path - skipping`);
        return;
      }

      let resolvedSrc: string;
      try {
        resolvedSrc = isRemoteUrl(sanitizedFile) ? sanitizedFile : await resolveUrl(sanitizedFile);
      } catch (error) {
        console.warn(`Asset '${assetId}' failed to resolve URL - skipping`, error);
        return;
      }

      const sanitizedSrc = getSanitizedMediaSrc(resolvedSrc);
      if (!sanitizedSrc) {
        console.warn(`Asset '${assetId}' resolved to an invalid media URL - skipping`, {
          file: sanitizedFile,
          src: resolvedSrc,
        });
        return;
      }

      resolvedRegistry[assetId] = {
        ...entry,
        file: sanitizedFile,
        src: sanitizedSrc,
      };
    }),
  );

  const clips = config.clips.map((clip) => {
    if (!clip.asset) {
      return {
        ...clip,
        assetEntry: undefined,
      };
    }

    const assetEntry = resolvedRegistry[clip.asset];
    if (!assetEntry) {
      console.warn(`Clip '${clip.id}' references missing asset '${clip.asset}' - skipping`);
      return {
        ...clip,
        assetEntry: undefined,
      };
    }

    return {
      ...clip,
      assetEntry,
    };
  });

  return {
    output: { ...config.output },
    tracks: config.tracks ?? [],
    clips,
    registry: resolvedRegistry,
    ...(config.theme !== undefined ? { theme: config.theme } : {}),
    ...(config.theme_overrides !== undefined ? { theme_overrides: config.theme_overrides } : {}),
    ...(config.generation_defaults !== undefined ? { generation_defaults: config.generation_defaults } : {}),
  };
};
