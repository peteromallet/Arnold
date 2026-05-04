// Sprint 5: physically moved + renamed from
// tools/remotion/src/HypeComposition.tsx → TimelineComposition.tsx.
//
// Composition id rename: `HypeComposition` → `TimelineComposition`.
// Banodoco's CLI render path passes the new id; the in-tree shell at
// tools/remotion/src/Root.tsx imports this composition from the package.

import type {ReactElement} from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {AudioTrack} from './AudioTrack';
import {CLIP_TYPE_ALIASES, EFFECT_REGISTRY, type EffectId} from './effects.generated';
import {DEFAULT_THEME, ThemeProvider, useTheme} from './ThemeContext';
import {VisualClip} from './VisualClip';
import {resolveParams} from './lib/effect-params';
import {getClipDurationInFrames} from './lib/duration';
import {getAudioTracks, getVisualTracks} from './lib/tracks';
import {
  CrossFadeLayer,
  TransitionSeries,
  resolveTransitionReference,
} from './lib/transitions';
import type {
  AssetRegistryEntry,
  HypeCompositionProps,
  TimelineClip,
  TimelineCompositionProps,
  TrackDefinition,
} from './types';

const sortClipsByAt = (clips: TimelineClip[]): TimelineClip[] => {
  return [...clips].sort((left, right) => left.at - right.at);
};

const hasPositionOverride = (clip: TimelineClip): boolean => {
  return (
    clip.x !== undefined
    || clip.y !== undefined
    || clip.width !== undefined
    || clip.height !== undefined
    || clip.cropTop !== undefined
    || clip.cropBottom !== undefined
    || clip.cropLeft !== undefined
    || clip.cropRight !== undefined
  );
};

const getAssetEntry = (
  clip: TimelineClip,
  assets: TimelineCompositionProps['assets'],
): AssetRegistryEntry | undefined => {
  return clip.asset ? assets.assets[clip.asset] : undefined;
};

const renderVisualClipContent = (
  track: TrackDefinition,
  clip: TimelineClip,
  assets: TimelineCompositionProps['assets'],
  fps: number,
  theme: ReturnType<typeof useTheme>,
): ReactElement | null => {
  if (clip.clipType === 'effect-layer') {
    return null;
  }

  // Sprint 5 EFFECT_REGISTRY dispatch (the migration target cited at
  // tools/remotion/src/HypeComposition.tsx:58-64). Same shape; the
  // registry now lives inside the package.
  const effectId = (
    clip.clipType && clip.clipType in EFFECT_REGISTRY
      ? clip.clipType as EffectId
      : clip.clipType ? CLIP_TYPE_ALIASES[clip.clipType] : undefined
  );
  if (effectId) {
    const EffectComponent = EFFECT_REGISTRY[effectId];
    return <EffectComponent clip={clip} params={resolveParams(clip)} theme={theme} fps={fps} />;
  }

  const assetEntry = getAssetEntry(clip, assets);
  const baseVisual = (
    <VisualClip clip={clip} track={track} assetEntry={assetEntry} fps={fps} />
  );

  if (hasPositionOverride(clip)) {
    return baseVisual;
  }

  if ((track.scale ?? 1) !== 1) {
    return (
      <AbsoluteFill
        style={{
          transform: `scale(${track.scale})`,
          transformOrigin: 'center center',
          overflow: 'hidden',
          isolation: 'isolate',
        }}
      >
        {baseVisual}
      </AbsoluteFill>
    );
  }

  return baseVisual;
};

const renderVisualSequence = (
  track: TrackDefinition,
  clip: TimelineClip,
  assets: TimelineCompositionProps['assets'],
  fps: number,
  theme: ReturnType<typeof useTheme>,
): ReactElement | null => {
  const content = renderVisualClipContent(track, clip, assets, fps, theme);
  if (!content) {
    return null;
  }
  return (
    <Sequence
      key={clip.id}
      from={Math.round(clip.at * fps)}
      durationInFrames={getClipDurationInFrames(clip, fps)}
    >
      {content}
    </Sequence>
  );
};

const renderTransitionGroup = (
  track: TrackDefinition,
  fromClip: TimelineClip,
  toClip: TimelineClip,
  assets: TimelineCompositionProps['assets'],
  fps: number,
  theme: ReturnType<typeof useTheme>,
): ReactElement | null => {
  const transition = resolveTransitionReference(fromClip.transition as never, theme, fps);
  if (!transition) {
    return null;
  }
  const fromDuration = getClipDurationInFrames(fromClip, fps);
  const toDuration = getClipDurationInFrames(toClip, fps);
  if (transition.durationFrames <= 0 || transition.durationFrames > fromDuration || transition.durationFrames > toDuration) {
    return null;
  }

  const fromContent = renderVisualClipContent(track, fromClip, assets, fps, theme);
  const toContent = renderVisualClipContent(track, toClip, assets, fps, theme);
  if (!fromContent || !toContent) {
    return null;
  }

  const groupFrom = Math.round(fromClip.at * fps);
  const toOffset = Math.max(0, fromDuration - transition.durationFrames);
  const groupDuration = toOffset + toDuration;
  return (
    <Sequence
      key={`${fromClip.id}-${toClip.id}-transition`}
      from={groupFrom}
      durationInFrames={groupDuration}
    >
      <TransitionSeries>
        <Sequence from={0} durationInFrames={fromDuration}>
          <CrossFadeLayer
            role="from"
            durationFrames={fromDuration}
            transitionDurationFrames={transition.durationFrames}
          >
            {fromContent}
          </CrossFadeLayer>
        </Sequence>
        <Sequence from={toOffset} durationInFrames={toDuration}>
          <CrossFadeLayer
            role="to"
            durationFrames={toDuration}
            transitionDurationFrames={transition.durationFrames}
          >
            {toContent}
          </CrossFadeLayer>
        </Sequence>
      </TransitionSeries>
    </Sequence>
  );
};

const clipsCanTransition = (fromClip: TimelineClip, toClip: TimelineClip, fps: number): boolean => {
  if (!fromClip.transition || fromClip.clipType === 'effect-layer' || toClip.clipType === 'effect-layer') {
    return false;
  }
  const fromStart = Math.round(fromClip.at * fps);
  const fromEnd = fromStart + getClipDurationInFrames(fromClip, fps);
  const toStart = Math.round(toClip.at * fps);
  return toStart >= fromStart && toStart <= fromEnd;
};

const renderVisualTrack = (
  track: TrackDefinition,
  clips: TimelineClip[],
  assets: TimelineCompositionProps['assets'],
  fps: number,
  theme: ReturnType<typeof useTheme>,
): ReactElement | null => {
  const sortedClips = sortClipsByAt(clips);
  if (sortedClips.length === 0) {
    return null;
  }

  const rendered: Array<ReactElement | null> = [];
  for (let index = 0; index < sortedClips.length; index += 1) {
    const clip = sortedClips[index];
    const nextClip = sortedClips[index + 1];
    if (nextClip && clipsCanTransition(clip, nextClip, fps)) {
      const group = renderTransitionGroup(track, clip, nextClip, assets, fps, theme);
      if (group) {
        rendered.push(group);
        index += 1;
        continue;
      }
    }
    rendered.push(renderVisualSequence(track, clip, assets, fps, theme));
  }

  return (
    <AbsoluteFill
      key={track.id}
      style={{
        opacity: track.opacity ?? 1,
        mixBlendMode: track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined,
      }}
    >
      {rendered}
    </AbsoluteFill>
  );
};

const renderAudioTrack = (
  track: TrackDefinition,
  clips: TimelineClip[],
  assets: TimelineCompositionProps['assets'],
  fps: number,
): ReactElement[] => {
  return sortClipsByAt(clips).map((clip) => {
    const assetEntry = getAssetEntry(clip, assets);
    return (
      <Sequence
        key={clip.id}
        from={Math.round(clip.at * fps)}
        durationInFrames={getClipDurationInFrames(clip, fps)}
      >
        <AudioTrack clip={clip} track={track} assetEntry={assetEntry} fps={fps} />
      </Sequence>
    );
  });
};

export const TimelineComposition = (props: TimelineCompositionProps): ReactElement => {
  const {timeline, assets} = props;
  const {fps, width, height} = useVideoConfig();
  const visualTracks = [...getVisualTracks(timeline)].reverse();
  const audioTracks = getAudioTracks(timeline);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: props.theme?.visual.color.bg ?? 'black',
        width,
        height,
        overflow: 'hidden',
      }}
    >
      <ThemeProvider value={props.theme ?? DEFAULT_THEME}>
        <TimelineCompositionBody
          timeline={timeline}
          assets={assets}
          visualTracks={visualTracks}
          audioTracks={audioTracks}
          fps={fps}
        />
      </ThemeProvider>
    </AbsoluteFill>
  );
};

// Backwards-compatibility alias for callers that haven't migrated off the
// HypeComposition name yet. The exported component identity is the same.
export const HypeComposition = TimelineComposition;
export type {HypeCompositionProps, TimelineCompositionProps};

const TimelineCompositionBody = ({
  timeline,
  assets,
  visualTracks,
  audioTracks,
  fps,
}: {
  timeline: TimelineCompositionProps['timeline'];
  assets: TimelineCompositionProps['assets'];
  visualTracks: TrackDefinition[];
  audioTracks: TrackDefinition[];
  fps: number;
}): ReactElement => {
  const theme = useTheme();
  return (
    <>
      <AbsoluteFill style={{position: 'relative', overflow: 'hidden'}}>
        {visualTracks.map((track) => {
          const clips = timeline.clips.filter((clip) => clip.track === track.id);
          return renderVisualTrack(track, clips, assets, fps, theme);
        })}
      </AbsoluteFill>
      {audioTracks.map((track) => {
        const clips = timeline.clips.filter((clip) => clip.track === track.id);
        return renderAudioTrack(track, clips, assets, fps);
      })}
    </>
  );
};
