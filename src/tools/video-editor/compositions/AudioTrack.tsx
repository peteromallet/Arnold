import { memo, type FC } from 'react';
import { Audio as Html5Audio, Sequence, useRemotionEnvironment } from 'remotion';
import { Audio as MediaAudio } from '@remotion/media';
import {
  getClipDurationInFrames,
  getSanitizedMediaSrc,
  getSanitizedMediaTrimProps,
  getSanitizedPlaybackRate,
  getSanitizedVolume,
  secondsToFrames,
} from '@/tools/video-editor/lib/config-utils.ts';
import { MediaErrorBoundary } from '@/tools/video-editor/compositions/MediaErrorBoundary.tsx';
import type { ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types/index.ts';

const AudioTrackComponent: FC<{
  track: TrackDefinition;
  clips: ResolvedTimelineClip[];
  fps: number;
}> = ({ track, clips, fps }) => {
  const environment = useRemotionEnvironment();
  const AudioComponent = environment.isRendering || environment.isClientSideRendering
    ? MediaAudio
    : Html5Audio;

  return (
    <>
      {clips.map((clip) => {
        const mediaSrc = getSanitizedMediaSrc(clip.assetEntry?.src);
        const assetType = clip.assetEntry?.type ?? '';
        const isPlayableAudio = assetType.startsWith('audio/') || assetType.startsWith('video/');
        const effectiveVolume = track.muted ? 0 : getSanitizedVolume(track.volume) * getSanitizedVolume(clip.volume);
        const playbackRate = getSanitizedPlaybackRate(clip.speed);
        const trimProps = getSanitizedMediaTrimProps(clip, fps);

        return (
          <Sequence
            // Remotion's Sequence + Audio timing is not fully updated by prop changes during playback,
            // so audio clips need a remount whenever timing or playback-rate inputs change.
            key={`${clip.id}-${clip.at}-${clip.from ?? 0}-${clip.to ?? ''}-${clip.speed ?? 1}`}
            from={secondsToFrames(clip.at, fps)}
            durationInFrames={getClipDurationInFrames(clip, fps)}
            premountFor={fps}
          >
            {mediaSrc && isPlayableAudio ? (
              <MediaErrorBoundary
                clipId={clip.id}
                resetKey={`${clip.id}:${mediaSrc}:${trimProps.trimBefore}:${trimProps.trimAfter ?? 'none'}:${playbackRate}:${effectiveVolume}:audio`}
                fallback={null}
              >
                <AudioComponent
                  src={mediaSrc}
                  trimBefore={trimProps.trimBefore}
                  trimAfter={trimProps.trimAfter}
                  playbackRate={playbackRate}
                  volume={effectiveVolume}
                  // In the interactive player, blocking playback on every transient audio
                  // buffer underrun causes the preview to "randomly" pause. Let clips
                  // preload via premounting instead of hard-pausing the whole player.
                  pauseWhenBuffering={false}
                />
              </MediaErrorBoundary>
            ) : null}
          </Sequence>
        );
      })}
    </>
  );
};

export const AudioTrack = memo(AudioTrackComponent);
AudioTrack.displayName = 'AudioTrack';
