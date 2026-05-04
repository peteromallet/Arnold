import { updateClipOrder } from '@/tools/video-editor/lib/coordinate-utils';
import { getNextClipId, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { AssetRegistry, TimelineClip } from '@/tools/video-editor/types';
import { applyTimelineCommandEffect, createTimelineCommandRunner } from './runner';
import { buildTimelineCommandData } from './timelineData';
import type {
  TimelineCommand,
  TimelineCommandDescriptor,
  TimelineCommandEffect,
} from './types';
import {
  estimateProvisionedAssetDuration,
  type TimelineProvisionedAsset,
} from './provisioning';

export type AddMediaCommand = TimelineCommand<'add-media', {
  trackId: string;
  at: number;
  asset: TimelineProvisionedAsset;
}>;

export type SwapMediaCommand = TimelineCommand<'swap', {
  clipId: string;
  asset: TimelineProvisionedAsset;
}>;

const roundSeconds = (value: number): number => Math.round(value * 1000) / 1000;

const getTrackForClip = (
  data: TimelineData,
  clipId: string,
) => {
  const trackId = data.meta[clipId]?.track;
  return trackId ? data.tracks.find((track) => track.id === trackId) ?? null : null;
};

const getClipMediaType = (
  data: TimelineData,
  clip: TimelineClip,
): 'image' | 'video' | 'audio' => {
  const track = getTrackForClip(data, clip.id);
  if (track?.kind === 'audio') {
    return 'audio';
  }

  return clip.clipType === 'hold' ? 'image' : 'video';
};

const getVisualClipType = (
  asset: TimelineProvisionedAsset,
): 'hold' | 'media' => {
  return asset.mediaType === 'image' ? 'hold' : 'media';
};

const validateProvisionedAsset = (
  asset: TimelineProvisionedAsset | undefined,
  path: string,
) => {
  const errors = [];
  if (!asset || typeof asset !== 'object') {
    errors.push({
      path,
      code: 'missing_asset',
      message: 'A provisioned asset is required.',
    });
    return errors;
  }

  if (typeof asset.assetKey !== 'string' || asset.assetKey.trim().length === 0) {
    errors.push({
      path: `${path}.assetKey`,
      code: 'invalid_asset_key',
      message: 'asset.assetKey must be a non-empty string.',
    });
  }

  if (!['image', 'video', 'audio'].includes(asset.mediaType)) {
    errors.push({
      path: `${path}.mediaType`,
      code: 'invalid_media_type',
      message: 'asset.mediaType must be image, video, or audio.',
    });
  }

  return errors;
};

export const buildAddMediaCommandEffect = (
  currentData: TimelineData,
  payload: AddMediaCommand['payload'],
): TimelineCommandEffect => {
  const track = currentData.tracks.find((candidate) => candidate.id === payload.trackId);
  if (!track) {
    throw new Error(`Track ${payload.trackId} does not exist.`);
  }

  const clipId = getNextClipId(currentData.meta);
  const duration = estimateProvisionedAssetDuration(payload.asset);
  const isManual = track.fit === 'manual';
  const clipType = track.kind === 'audio'
    ? 'media'
    : getVisualClipType(payload.asset);
  const nextMeta = track.kind === 'audio'
    ? {
        asset: payload.asset.assetKey,
        track: payload.trackId,
        clipType: 'media',
        from: 0,
        to: duration,
        speed: 1,
        volume: 1,
      }
    : payload.asset.mediaType === 'image'
      ? {
          asset: payload.asset.assetKey,
          track: payload.trackId,
          clipType,
          hold: 5,
          opacity: 1,
          x: isManual ? 100 : undefined,
          y: isManual ? 100 : undefined,
          width: isManual ? 320 : undefined,
          height: isManual ? 240 : undefined,
        }
      : {
          asset: payload.asset.assetKey,
          track: payload.trackId,
          clipType,
          from: 0,
          to: duration,
          speed: 1,
          volume: 1,
          opacity: 1,
          x: isManual ? 100 : undefined,
          y: isManual ? 100 : undefined,
          width: isManual ? 320 : undefined,
          height: isManual ? 240 : undefined,
        };
  const nextRows = currentData.rows.map((row) => (
    row.id === payload.trackId
      ? {
          ...row,
          actions: [
            ...row.actions,
            {
              id: clipId,
              start: payload.at,
              end: payload.at + duration,
              effectId: `effect-${clipId}`,
            },
          ],
        }
      : row
  ));

  return {
    mutation: {
      type: 'rows',
      rows: nextRows,
      metaUpdates: {
        [clipId]: nextMeta,
      },
      clipOrderOverride: updateClipOrder(currentData.clipOrder, payload.trackId, (ids) => [...ids, clipId]),
    },
    summary: `Added media clip ${clipId} on track ${payload.trackId} at ${roundSeconds(payload.at)}s using asset ${payload.asset.assetKey}.`,
    detail: {
      clipId,
      trackId: payload.trackId,
      assetKey: payload.asset.assetKey,
    },
  };
};

const buildSwappedClip = (
  clip: TimelineClip,
  asset: TimelineProvisionedAsset,
): TimelineClip => {
  const nextClip = {
    ...clip,
    asset: asset.assetKey,
  } as TimelineClip;
  const nextClipType = asset.mediaType === 'image' ? 'hold' : 'media';

  if (clip.clipType === nextClipType) {
    return nextClip;
  }

  if (asset.mediaType === 'image') {
    nextClip.clipType = 'hold';
    nextClip.hold = 5;
    delete nextClip.from;
    delete nextClip.to;
    delete nextClip.speed;
    delete nextClip.volume;
    return nextClip;
  }

  nextClip.clipType = nextClipType;
  nextClip.from = 0;
  nextClip.to = roundSeconds(estimateProvisionedAssetDuration(asset));
  nextClip.speed = 1;
  nextClip.volume = 1;
  delete nextClip.hold;
  return nextClip;
};

export const buildSwapMediaCommandEffect = (
  currentData: TimelineData,
  payload: SwapMediaCommand['payload'],
): TimelineCommandEffect => {
  const nextResolvedConfig: ResolvedTimelineConfig = {
    ...currentData.resolvedConfig,
    output: { ...currentData.resolvedConfig.output },
    tracks: currentData.resolvedConfig.tracks.map((track) => ({ ...track })),
    registry: {
      ...currentData.resolvedConfig.registry,
      [payload.asset.assetKey]: {
        ...payload.asset.entry,
        src: payload.asset.entry.file,
      },
    },
    clips: currentData.resolvedConfig.clips.map((clip) => (
      clip.id === payload.clipId
        ? buildSwappedClip(clip, payload.asset)
        : { ...clip }
    )),
    ...(currentData.resolvedConfig.theme !== undefined ? { theme: currentData.resolvedConfig.theme } : {}),
    ...(currentData.resolvedConfig.theme_overrides !== undefined ? { theme_overrides: currentData.resolvedConfig.theme_overrides } : {}),
    ...(currentData.resolvedConfig.generation_defaults !== undefined ? { generation_defaults: currentData.resolvedConfig.generation_defaults } : {}),
  };
  const currentClip = currentData.resolvedConfig.clips.find((clip) => clip.id === payload.clipId);
  const currentMediaType = currentClip
    ? getClipMediaType(currentData, currentClip)
    : null;
  const summary = currentMediaType === payload.asset.mediaType
    ? `Swapped asset on clip ${payload.clipId} to ${payload.asset.assetKey}.`
    : `Swapped clip ${payload.clipId} to ${payload.asset.mediaType} asset ${payload.asset.assetKey}.`;

  return {
    mutation: {
      type: 'resolved-config',
      resolvedConfig: nextResolvedConfig,
      pinnedShotGroupsOverride: currentData.config.pinnedShotGroups,
    },
    summary,
    detail: {
      clipId: payload.clipId,
      assetKey: payload.asset.assetKey,
    },
  };
};

export const ADD_MEDIA_COMMAND_DESCRIPTOR: TimelineCommandDescriptor<AddMediaCommand> = {
  type: 'add-media',
  validate: (context) => {
    const errors = [];
    const { trackId, at, asset } = context.command.payload ?? {};
    errors.push(...validateProvisionedAsset(asset, `$.commands[${context.commandIndex}].payload.asset`));

    if (typeof trackId !== 'string' || trackId.trim().length === 0) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.trackId`,
        code: 'invalid_track',
        message: 'trackId must be a non-empty string.',
      });
      return errors;
    }

    const track = context.currentData.tracks.find((candidate) => candidate.id === trackId);
    if (!track) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.trackId`,
        code: 'missing_track',
        message: `Track ${trackId} does not exist.`,
      });
    }

    if (typeof at !== 'number' || !Number.isFinite(at) || at < 0) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.at`,
        code: 'invalid_at',
        message: 'at must be a finite non-negative number.',
      });
    }

    if (track && asset) {
      if (track.kind === 'visual' && asset.mediaType === 'audio') {
        errors.push({
          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
          code: 'incompatible_asset',
          message: `Track ${track.id} does not accept audio assets.`,
        });
      }

      if (track.kind === 'audio' && asset.mediaType !== 'audio') {
        errors.push({
          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
          code: 'incompatible_asset',
          message: `Track ${track.id} only accepts audio assets.`,
        });
      }
    }

    return errors;
  },
  dryRun: (context) => buildAddMediaCommandEffect(context.currentData, context.command.payload!),
  apply: (context) => buildAddMediaCommandEffect(context.currentData, context.command.payload!),
  invert: () => null,
};

export const SWAP_MEDIA_COMMAND_DESCRIPTOR: TimelineCommandDescriptor<SwapMediaCommand> = {
  type: 'swap',
  validate: (context) => {
    const errors = [];
    const { clipId, asset } = context.command.payload ?? {};
    errors.push(...validateProvisionedAsset(asset, `$.commands[${context.commandIndex}].payload.asset`));

    if (typeof clipId !== 'string' || clipId.trim().length === 0) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.clipId`,
        code: 'invalid_clip_id',
        message: 'clipId must be a non-empty string.',
      });
      return errors;
    }

    const clip = context.currentData.resolvedConfig.clips.find((candidate) => candidate.id === clipId);
    if (!clip) {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.clipId`,
        code: 'missing_clip',
        message: `Clip ${clipId} was not found.`,
      });
      return errors;
    }

    if (clip.clipType === 'text' || clip.clipType === 'effect-layer') {
      errors.push({
        path: `$.commands[${context.commandIndex}].payload.clipId`,
        code: 'unsupported_clip_type',
        message: `Clip ${clip.id} cannot swap media assets.`,
      });
    }

    const track = getTrackForClip(context.currentData, clipId);
    if (track && asset) {
      if (track.kind === 'visual' && asset.mediaType === 'audio') {
        errors.push({
          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
          code: 'incompatible_asset',
          message: `Track ${track.id} does not accept audio assets.`,
        });
      }

      if (track.kind === 'audio' && asset.mediaType !== 'audio') {
        errors.push({
          path: `$.commands[${context.commandIndex}].payload.asset.mediaType`,
          code: 'incompatible_asset',
          message: `Track ${track.id} only accepts audio assets.`,
        });
      }
    }

    return errors;
  },
  dryRun: (context) => buildSwapMediaCommandEffect(context.currentData, context.command.payload!),
  apply: (context) => buildSwapMediaCommandEffect(context.currentData, context.command.payload!),
  invert: (context) => {
    const clip = context.currentData.resolvedConfig.clips.find((candidate) => candidate.id === context.command.payload?.clipId);
    if (!clip?.asset) {
      return null;
    }

    const assetEntry = context.currentData.registry.assets[clip.asset];
    if (!assetEntry) {
      return null;
    }

    return {
      type: 'swap',
      payload: {
        clipId: clip.id,
        asset: {
          assetKey: clip.asset,
          mediaType: getClipMediaType(context.currentData, clip),
          durationSeconds: typeof assetEntry.duration === 'number' ? assetEntry.duration : null,
          entry: { ...assetEntry },
          source: 'registered',
        },
      },
    };
  },
};

export const MEDIA_COMMAND_DESCRIPTORS = [
  ADD_MEDIA_COMMAND_DESCRIPTOR,
  SWAP_MEDIA_COMMAND_DESCRIPTOR,
] as const;

const mediaCommandRunner = createTimelineCommandRunner([...MEDIA_COMMAND_DESCRIPTORS]);

const getFailureMessage = (
  result: ReturnType<typeof mediaCommandRunner.apply>,
): string => {
  const validationMessage = result.errors[0]?.validationErrors?.[0]?.message;
  return validationMessage ?? result.errors[0]?.message ?? 'Command failed.';
};

export const applyProvisionedMediaCommandToConfig = (
  config: TimelineData['config'],
  registry: AssetRegistry,
  command: AddMediaCommand | SwapMediaCommand,
): { config?: TimelineData['config']; result: string } => {
  const data = buildTimelineCommandData(config, registry);
  const result = mediaCommandRunner.apply(data, { commands: [command] });
  if (result.status === 'rejected') {
    return { result: getFailureMessage(result) };
  }

  return {
    config: result.nextData.config,
    result: result.commandResults[0]?.summary ?? 'Applied media command.',
  };
};

export const dryRunProvisionedMediaCommand = (
  currentData: TimelineData,
  command: AddMediaCommand | SwapMediaCommand,
) => {
  return mediaCommandRunner.dryRun(currentData, { commands: [command] });
};

export const applyProvisionedMediaCommand = (
  currentData: TimelineData,
  command: AddMediaCommand | SwapMediaCommand,
) => {
  const result = mediaCommandRunner.apply(currentData, { commands: [command] });
  if (result.status === 'rejected') {
    return null;
  }

  return {
    nextData: result.nextData,
    commandResult: result.commandResults[0],
  };
};

export const materializeProvisionedMediaCommand = (
  currentData: TimelineData,
  effect: TimelineCommandEffect,
) => {
  return applyTimelineCommandEffect(currentData, effect);
};
