import { AbsoluteFill, Sequence } from 'remotion';
import { memo, useMemo, type FC, type ReactNode } from 'react';
import { getAudioTracks, getVisualTracks } from '@/tools/video-editor/lib/editor-utils';
import { getTimelineDurationInFrames } from '@/tools/video-editor/lib/config-utils';
import { BUILTIN_CLIP_TYPES, type ResolvedTimelineClip, type ResolvedTimelineConfig, type TrackDefinition } from '@/tools/video-editor/types';
import { AudioTrack } from '@/tools/video-editor/compositions/AudioTrack';
import { AudioAnalysisProvider } from '@/tools/video-editor/compositions/AudioAnalysisProvider';
import { EffectLayerSequence } from '@/tools/video-editor/compositions/EffectLayerSequence';
import { TextClipSequence } from '@/tools/video-editor/compositions/TextClip';
import { VisualClipSequence } from '@/tools/video-editor/compositions/VisualClip';
import { UnknownClipPlaceholderSequence } from '@/tools/video-editor/compositions/UnknownClipPlaceholder';
import {
  THEME_PACKAGE_REGISTRY,
  type ThemePackageClipType,
} from '@banodoco/timeline-composition/registry.generated';

// Phase 4d (Sprint 5): EFFECT_REGISTRY dispatch.
//
// Mirrors `tools/remotion/src/HypeComposition.tsx:58-64` (lifted into
// `packages/timeline-composition/typescript/src/TimelineComposition.tsx`).
// Lookup chain for a clipType:
//
//   1. Reigh-native built-ins (effect-layer, text, media, hold) — same as
//      pre-Sprint-5 behavior.
//   2. THEME_PACKAGE_REGISTRY (codegenned from installed
//      @banodoco/timeline-theme-* packages) — render the theme component.
//   3. Sprint-3 loud placeholder — defensive fallback when the theme
//      package isn't installed OR the clipType is unknown.
const isBuiltinClipType = (value: string | undefined): boolean => {
  if (typeof value !== 'string') {
    return true; // legacy clips with no clipType default to media-equivalent dispatch
  }
  return (BUILTIN_CLIP_TYPES as readonly string[]).includes(value);
};

const isThemePackageClipType = (value: string | undefined): value is ThemePackageClipType => {
  if (typeof value !== 'string') return false;
  return Object.prototype.hasOwnProperty.call(THEME_PACKAGE_REGISTRY, value);
};

const sortClipsByAt = (clips: ResolvedTimelineClip[]): ResolvedTimelineClip[] => {
  return [...clips].sort((left, right) => left.at - right.at);
};

type ThemeEffectSequenceProps = {
  clip: ResolvedTimelineClip;
  fps: number;
};

const ThemeEffectSequence: FC<ThemeEffectSequenceProps> = ({ clip, fps }) => {
  const entry = THEME_PACKAGE_REGISTRY[clip.clipType as ThemePackageClipType];
  // Defensive: if the registry lookup somehow returned no entry, fall back
  // to the loud placeholder. This is the second layer of the SD-025
  // "loud placeholder" safety net for clipTypes that *are* in the
  // registry but somehow fail to render.
  if (!entry) {
    return <UnknownClipPlaceholderSequence clip={clip} fps={fps} reason="unsupported" />;
  }
  const Component = entry.component as FC<{
    clip: ResolvedTimelineClip;
    params: unknown;
    theme: unknown;
    fps: number;
  }>;
  const durationInFrames = Math.max(1, Math.round(((clip.hold ?? 0) + ((clip.to ?? 0) - (clip.from ?? 0))) * fps)) || Math.max(1, Math.round((clip.hold ?? 1) * fps));
  return (
    <Sequence
      key={clip.id}
      from={Math.round(clip.at * fps)}
      durationInFrames={durationInFrames}
    >
      <Component clip={clip} params={clip.params} theme={undefined} fps={fps} />
    </Sequence>
  );
};

const renderVisualTrack = (
  track: TrackDefinition,
  clips: ResolvedTimelineClip[],
  fps: number,
) => {
  const sortedClips = sortClipsByAt(clips);
  if (sortedClips.length === 0) {
    return null;
  }

  return (
    <AbsoluteFill
      key={track.id}
      style={{
        opacity: track.opacity ?? 1,
        mixBlendMode: track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined,
      }}
    >
      {sortedClips.map((clip, index) => {
        if (clip.clipType === 'effect-layer') {
          return null;
        }

        if (clip.clipType === 'text') {
          return <TextClipSequence key={clip.id} clip={clip} track={track} fps={fps} />;
        }

        // EFFECT_REGISTRY dispatch (Sprint 5 / SD-026): if the clipType
        // is provided by an installed theme package, render via the
        // codegenned registry entry. Mirrors HypeComposition.tsx:58-64.
        if (isThemePackageClipType(clip.clipType)) {
          return <ThemeEffectSequence key={clip.id} clip={clip} fps={fps} />;
        }

        // SD-025 (Sprint 3): loud placeholder for unknown clipTypes that
        // are NOT in BUILTIN_CLIP_TYPES and NOT in the theme registry —
        // theme package missing, typo, or future clipType not yet
        // supported. Surfaces as a labeled band rather than a silent
        // black void.
        if (!isBuiltinClipType(clip.clipType)) {
          return (
            <UnknownClipPlaceholderSequence
              key={clip.id}
              clip={clip}
              fps={fps}
              reason="unsupported"
            />
          );
        }

        const predecessor = index > 0 ? sortedClips[index - 1] : null;
        const hasPositionOverride = (
          clip.x !== undefined
          || clip.y !== undefined
          || clip.width !== undefined
          || clip.height !== undefined
          || clip.cropTop !== undefined
          || clip.cropBottom !== undefined
          || clip.cropLeft !== undefined
          || clip.cropRight !== undefined
        );
        if (hasPositionOverride) {
          return (
            <VisualClipSequence
              key={clip.id}
              clip={clip}
              track={track}
              fps={fps}
              predecessor={predecessor}
            />
          );
        }

        const effectiveScale = track.scale ?? 1;
        const needsScaleWrapper = effectiveScale !== 1;
        if (needsScaleWrapper) {
          return (
            <AbsoluteFill
              key={clip.id}
              style={{
                transform: `scale(${effectiveScale})`,
                transformOrigin: 'center center',
                overflow: 'hidden',
                isolation: 'isolate',
              }}
            >
              <VisualClipSequence
                clip={clip}
                track={track}
                fps={fps}
                predecessor={predecessor}
              />
            </AbsoluteFill>
          );
        }
        return (
          <VisualClipSequence
            key={clip.id}
            clip={clip}
            track={track}
            fps={fps}
            predecessor={predecessor}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export const TimelineRenderer: FC<{ config: ResolvedTimelineConfig }> = memo(({ config }) => {
  const fps = config.output.fps;
  const visualTracks = useMemo(() => [...getVisualTracks(config)].reverse(), [config]);
  const audioTracks = useMemo(() => getAudioTracks(config), [config]);
  const totalDurationInFrames = useMemo(() => getTimelineDurationInFrames(config, fps), [config, fps]);
  const audioClips = useMemo(() => {
    const audioTrackIds = new Set(audioTracks.map((track) => track.id));
    return config.clips.filter((clip) => audioTrackIds.has(clip.track));
  }, [audioTracks, config.clips]);
  const clipsByTrack = useMemo(() => {
    return config.clips.reduce<{
      regular: Record<string, ResolvedTimelineClip[]>;
      effectLayers: Record<string, ResolvedTimelineClip[]>;
      all: Record<string, ResolvedTimelineClip[]>;
    }>((groups, clip) => {
      groups.all[clip.track] ??= [];
      groups.all[clip.track].push(clip);
      if (clip.clipType === 'effect-layer') {
        groups.effectLayers[clip.track] ??= [];
        groups.effectLayers[clip.track].push(clip);
      } else {
        groups.regular[clip.track] ??= [];
        groups.regular[clip.track].push(clip);
      }
      return groups;
    }, { regular: {}, effectLayers: {}, all: {} });
  }, [config]);

  const visualContent = useMemo(() => {
    let accumulated: ReactNode = null;

    for (const track of visualTracks) {
      const trackContent = renderVisualTrack(track, clipsByTrack.regular[track.id] ?? [], fps);
      let lowerTrackContent: ReactNode = accumulated;
      const effectLayers = sortClipsByAt(clipsByTrack.effectLayers[track.id] ?? []);

      if (lowerTrackContent && effectLayers.length > 0) {
        for (const effectLayer of effectLayers) {
          lowerTrackContent = (
            <EffectLayerSequence key={effectLayer.id} clip={effectLayer} fps={fps}>
              {lowerTrackContent}
            </EffectLayerSequence>
          );
        }
      }

      accumulated = lowerTrackContent && trackContent
        ? <>{lowerTrackContent}{trackContent}</>
        : (trackContent ?? lowerTrackContent);
    }

    return accumulated;
  }, [clipsByTrack.effectLayers, clipsByTrack.regular, fps, visualTracks]);

  return (
    <AudioAnalysisProvider clips={audioClips} fps={fps} totalDurationInFrames={totalDurationInFrames}>
      <AbsoluteFill style={{ backgroundColor: 'black', overflow: 'hidden' }}>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <AbsoluteFill style={{ position: 'relative', overflow: 'hidden' }}>{visualContent}</AbsoluteFill>
        </AbsoluteFill>
        {audioTracks.map((track) => (
          <AudioTrack
            key={track.id}
            track={track}
            clips={clipsByTrack.all[track.id] ?? []}
            fps={fps}
          />
        ))}
      </AbsoluteFill>
    </AudioAnalysisProvider>
  );
});
