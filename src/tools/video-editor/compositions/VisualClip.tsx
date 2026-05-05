import type { CSSProperties, FC, ReactNode } from 'react';
import { AbsoluteFill, Img, Sequence, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { Video } from '@remotion/media';
import {
  getClipDurationInFrames,
  getSanitizedMediaSrc,
  getSanitizedMediaTrimProps,
  getSanitizedPlaybackRate,
  getSanitizedVolume,
  parseResolution,
  secondsToFrames,
} from '@/tools/video-editor/lib/config-utils.ts';
import { wrapWithClipEffects } from '@/tools/video-editor/effects/index.tsx';
import { transitions } from '@/tools/video-editor/effects/transitions.ts';
import { MediaErrorBoundary } from '@/tools/video-editor/compositions/MediaErrorBoundary.tsx';
import { computeViewportMediaLayout } from '@/tools/video-editor/lib/render-bounds.ts';
import type { ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types/index.ts';

// SD-025 (Sprint 3): inline missing-asset placeholder body. Mirrors the
// styling of UnknownClipPlaceholder so the two loud cases look like a pair.
// Lives inline (not a shared component) because VisualClip already wraps
// content in a Sequence/AbsoluteFill upstream — we only need the visible
// label here.
const MissingAssetBody: FC<{ clipId: string; clipType: string }> = ({ clipId, clipType }) => (
  <AbsoluteFill
    data-testid="missing-asset-placeholder"
    data-clip-id={clipId}
    data-clip-type={clipType}
    style={{
      backgroundColor: '#5B0000',
      borderTop: '2px solid #FF5252',
      borderBottom: '2px solid #FF5252',
      color: '#FFCDD2',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '12px 24px',
      textAlign: 'center',
      fontFamily:
        'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, Consolas, monospace',
      fontSize: 14,
      lineHeight: 1.4,
      letterSpacing: '0.04em',
    }}
  >
    <div
      style={{
        maxWidth: '80%',
        padding: '8px 16px',
        borderRadius: 4,
        background: 'rgba(0, 0, 0, 0.45)',
      }}
    >
      {`clipType '${clipType}' missing asset — clip will not appear in render`}
    </div>
  </AbsoluteFill>
);

const UnsupportedAssetBody: FC<{ clipId: string; clipType: string; assetType?: string }> = ({ clipId, clipType, assetType }) => (
  <AbsoluteFill
    data-testid="unsupported-asset-placeholder"
    data-clip-id={clipId}
    data-clip-type={clipType}
    data-asset-type={assetType}
    style={{
      backgroundColor: '#332600',
      borderTop: '2px solid #FBBF24',
      borderBottom: '2px solid #FBBF24',
      color: '#FEF3C7',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '12px 24px',
      textAlign: 'center',
      fontFamily:
        'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, Consolas, monospace',
      fontSize: 14,
      lineHeight: 1.4,
      letterSpacing: '0.04em',
    }}
  >
    <div
      style={{
        maxWidth: '80%',
        padding: '8px 16px',
        borderRadius: 4,
        background: 'rgba(0, 0, 0, 0.45)',
      }}
    >
      {`clipType '${clipType}' references unsupported asset type '${assetType ?? 'unknown'}' — clip will not appear in render`}
    </div>
  </AbsoluteFill>
);

type VisualClipProps = {
  clip: ResolvedTimelineClip;
  track: TrackDefinition;
  fps: number;
  predecessor?: ResolvedTimelineClip | null;
};

const getClipBoxStyle = (
  clip: ResolvedTimelineClip,
  track: TrackDefinition,
  compositionWidth: number,
  compositionHeight: number,
): CSSProperties => {
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
  const fit = track.fit ?? 'contain';
  const style: CSSProperties = fit === 'manual' || hasPositionOverride
    ? {
        position: 'absolute',
        left: clip.x ?? 0,
        top: clip.y ?? 0,
        width: clip.width ?? compositionWidth,
        height: clip.height ?? compositionHeight,
        objectFit: 'cover',
        opacity: clip.opacity ?? 1,
      }
    : {
        width: '100%',
        height: '100%',
        objectFit: fit,
        opacity: clip.opacity ?? 1,
      };
  const cropTop = clip.cropTop ?? 0;
  const cropRight = clip.cropRight ?? 0;
  const cropBottom = clip.cropBottom ?? 0;
  const cropLeft = clip.cropLeft ?? 0;

  if (cropTop || cropRight || cropBottom || cropLeft) {
    style.clipPath = `inset(${cropTop * 100}% ${cropRight * 100}% ${cropBottom * 100}% ${cropLeft * 100}%)`;
  }

  return style;
};

const getIntrinsicMediaSize = (
  clip: ResolvedTimelineClip,
  compositionWidth: number,
  compositionHeight: number,
): { width: number; height: number } => {
  const resolution = clip.assetEntry?.resolution;
  if (resolution) {
    const parsed = parseResolution(resolution);
    if (Number.isFinite(parsed.width) && Number.isFinite(parsed.height) && parsed.width > 0 && parsed.height > 0) {
      return parsed;
    }
  }

  return {
    width: clip.width ?? compositionWidth,
    height: clip.height ?? compositionHeight,
  };
};

const VisualAsset: FC<VisualClipProps> = ({ clip, track, fps }) => {
  const { width: compositionWidth, height: compositionHeight } = useVideoConfig();
  // SD-025: never silent-null when a built-in clip is missing its asset.
  // Render a labeled red band so the gap is obvious in preview/export.
  if (!clip.assetEntry) {
    return <MissingAssetBody clipId={clip.id} clipType={clip.clipType ?? 'media'} />;
  }

  const mediaSrc = getSanitizedMediaSrc(clip.assetEntry.src);
  if (!mediaSrc) {
    return <MissingAssetBody clipId={clip.id} clipType={clip.clipType ?? 'media'} />;
  }

  const clipVolume = getSanitizedVolume(clip.volume);
  const effectiveVolume = track.muted ? 0 : getSanitizedVolume(track.volume) * clipVolume;
  const playbackRate = getSanitizedPlaybackRate(clip.speed);
  const trimProps = getSanitizedMediaTrimProps(clip, fps);
  const isImage = clip.assetEntry.type?.startsWith('image');
  const isVideo = clip.assetEntry.type?.startsWith('video');
  if (!isImage && !isVideo) {
    return (
      <UnsupportedAssetBody
        clipId={clip.id}
        clipType={clip.clipType ?? 'media'}
        assetType={clip.assetEntry.type}
      />
    );
  }
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
  const fit = track.fit ?? 'contain';
  const useViewportLayout = fit === 'manual' || hasPositionOverride;

  if (!useViewportLayout) {
    const style = getClipBoxStyle(clip, track, compositionWidth, compositionHeight);
    const sharedStyle: CSSProperties = {
      ...style,
      mixBlendMode: track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined,
    };

    if (isImage) {
      return <Img src={mediaSrc} style={sharedStyle} crossOrigin="anonymous" />;
    }

    return (
      <MediaErrorBoundary
        clipId={clip.id}
        resetKey={`${clip.id}:${mediaSrc}:${trimProps.trimBefore}:${trimProps.trimAfter ?? 'none'}:${playbackRate}:${effectiveVolume}`}
        fallback={null}
      >
        <Video
          src={mediaSrc}
          trimBefore={trimProps.trimBefore}
          trimAfter={trimProps.trimAfter}
          playbackRate={playbackRate}
          volume={effectiveVolume}
          muted={effectiveVolume <= 0}
          style={sharedStyle}
        />
      </MediaErrorBoundary>
    );
  }

  const fullBounds = {
    x: clip.x ?? 0,
    y: clip.y ?? 0,
    width: clip.width ?? compositionWidth,
    height: clip.height ?? compositionHeight,
  };
  const intrinsicSize = getIntrinsicMediaSize(clip, compositionWidth, compositionHeight);
  const viewportLayout = computeViewportMediaLayout({
    fullBounds,
    cropValues: {
      cropTop: clip.cropTop,
      cropBottom: clip.cropBottom,
      cropLeft: clip.cropLeft,
      cropRight: clip.cropRight,
    },
    compositionWidth,
    compositionHeight,
    intrinsicWidth: intrinsicSize.width,
    intrinsicHeight: intrinsicSize.height,
  });

  if (!viewportLayout) {
    return null;
  }

  const viewportStyle: CSSProperties = {
    position: 'absolute',
    left: viewportLayout.renderBounds.x,
    top: viewportLayout.renderBounds.y,
    width: viewportLayout.renderBounds.width,
    height: viewportLayout.renderBounds.height,
    overflow: 'hidden',
    opacity: clip.opacity ?? 1,
  };
  const mediaStyle: CSSProperties = {
    position: 'absolute',
    left: viewportLayout.mediaBounds.x,
    top: viewportLayout.mediaBounds.y,
    width: viewportLayout.mediaBounds.width,
    height: viewportLayout.mediaBounds.height,
    // Override Tailwind preflight's `img { max-width: 100%; height: auto; }`
    // which would squash the media to fit the viewport container. The media
    // must overflow the container (clipped by overflow:hidden) for the
    // manual cover layout to work correctly.
    maxWidth: 'none',
    maxHeight: 'none',
    mixBlendMode: track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined,
  };

  if (isImage) {
    return (
      <div style={viewportStyle}>
        <Img src={mediaSrc} style={mediaStyle} crossOrigin="anonymous" />
      </div>
    );
  }

  return (
    <div style={viewportStyle}>
      <MediaErrorBoundary
        clipId={clip.id}
        resetKey={`${clip.id}:${mediaSrc}:${trimProps.trimBefore}:${trimProps.trimAfter ?? 'none'}:${playbackRate}:${effectiveVolume}:viewport`}
        fallback={null}
      >
        <Video
          src={mediaSrc}
          trimBefore={trimProps.trimBefore}
          trimAfter={trimProps.trimAfter}
          playbackRate={playbackRate}
          volume={effectiveVolume}
          muted={effectiveVolume <= 0}
          style={mediaStyle}
        />
      </MediaErrorBoundary>
    </div>
  );
};

export const VisualClip: FC<VisualClipProps> = ({ clip, track, fps }) => {
  if (clip.clipType === 'effect-layer') {
    return null;
  }

  const durationInFrames = getClipDurationInFrames(clip, fps);
  const frame = useCurrentFrame();
  const transitionRenderer = clip.transition ? transitions[clip.transition.type] : undefined;
  const transitionProgress = interpolate(
    frame,
    [0, Math.max(1, secondsToFrames(clip.transition?.duration ?? 0.4, fps))],
    [0, 1],
    {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    },
  );
  const transitionStyle = transitionRenderer ? transitionRenderer(transitionProgress) : undefined;

  const content: ReactNode = (
    <AbsoluteFill style={{ overflow: 'hidden', ...transitionStyle }}>
      <VisualAsset clip={clip} track={track} fps={fps} />
    </AbsoluteFill>
  );

  return <>{wrapWithClipEffects(content, clip, durationInFrames, fps)}</>;
};

const LazyGuard: FC<{ durationInFrames: number; children: ReactNode }> = ({ durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const bufferFrames = Math.max(1, Math.round(fps));

  if (frame < -bufferFrames || frame > durationInFrames + bufferFrames) {
    return null;
  }

  return <>{children}</>;
};

export const VisualClipSequence: FC<VisualClipProps> = ({ clip, track, fps, predecessor }) => {
  const durationInFrames = getClipDurationInFrames(clip, fps);
  const transitionFrames = predecessor && clip.transition
    ? secondsToFrames(clip.transition.duration, fps)
    : 0;
  const from = Math.max(0, secondsToFrames(clip.at, fps) - transitionFrames);
  // Extend by transitionFrames so the clip isn't cut short when `from` is
  // pulled back for a transition-in, plus 1 overlap frame so the outgoing
  // clip stays mounted while the next clip's <Video> element loads.
  const effectiveDuration = durationInFrames + transitionFrames + 1;

  return (
    <Sequence
      key={clip.id}
      from={from}
      durationInFrames={effectiveDuration}
      premountFor={fps}
    >
      <LazyGuard durationInFrames={effectiveDuration}>
        <VisualClip clip={clip} track={track} fps={fps} predecessor={predecessor} />
      </LazyGuard>
    </Sequence>
  );
};
