import type {FC} from 'react';
import {Audio, staticFile} from 'remotion';
import type {AssetRegistryEntry, TimelineClip, TrackDefinition} from './types';
import {
  getSanitizedPlaybackRate,
  getSanitizedVolume,
} from './lib/duration';
import {computeMediaTrim} from './lib/trim';

type AudioTrackProps = {
  clip: TimelineClip;
  track: TrackDefinition;
  assetEntry?: AssetRegistryEntry;
  fps: number;
};

const toRenderableFileUrl = (file: string | undefined): string | null => {
  if (typeof file !== 'string' || file.trim().length === 0) {
    return null;
  }

  if (file.startsWith('http://') || file.startsWith('https://')) {
    return file;
  }

  return staticFile(file);
};

export const AudioTrack: FC<AudioTrackProps> = ({clip, track, assetEntry, fps}) => {
  const fileUrl = toRenderableFileUrl(assetEntry?.file);
  if (!fileUrl) {
    return null;
  }

  const effectiveVolume = track.muted
    ? 0
    : getSanitizedVolume(track.volume ?? 1) * getSanitizedVolume(clip.volume ?? 1);

  return (
    <Audio
      src={fileUrl}
      {...computeMediaTrim(clip, fps)}
      playbackRate={getSanitizedPlaybackRate(clip.speed)}
      volume={effectiveVolume}
    />
  );
};
