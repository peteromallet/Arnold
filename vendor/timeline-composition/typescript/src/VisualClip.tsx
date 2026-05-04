import type {CSSProperties, FC} from 'react';
import {Img, staticFile, useVideoConfig} from 'remotion';
import {Video} from '@remotion/media';
import type {AssetRegistryEntry, TimelineClip, TrackDefinition} from './types';
import {
  getSanitizedPlaybackRate,
  getSanitizedVolume,
} from './lib/duration';
import {
  computeViewportMediaLayout,
  getIntrinsicMediaSize,
  normalizeRenderCropValues,
} from './lib/render-bounds';
import {useFadeOpacity} from './lib/fade';
import {computeMediaTrim} from './lib/trim';

type VisualClipProps = {
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

export const VisualClip: FC<VisualClipProps> = ({clip, track, assetEntry, fps}) => {
  const {width: compositionWidth, height: compositionHeight} = useVideoConfig();
  const fileUrl = toRenderableFileUrl(assetEntry?.file);
  if (!fileUrl || !assetEntry) {
    return null;
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
  const useViewportLayout = (track.fit ?? 'contain') === 'manual' || hasPositionOverride;
  const effectiveVolume = track.muted
    ? 0
    : getSanitizedVolume(track.volume ?? 1) * getSanitizedVolume(clip.volume ?? 1);
  const opacity = useFadeOpacity(clip, fps) * (clip.opacity ?? 1);
  const mixBlendMode = track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined;
  const isImage = assetEntry.type?.startsWith('image');

  if (!useViewportLayout) {
    const sharedStyle: CSSProperties = {
      width: '100%',
      height: '100%',
      objectFit: track.fit === 'cover' ? 'cover' : 'contain',
      opacity,
      mixBlendMode,
    };

    if (isImage) {
      return <Img src={fileUrl} style={sharedStyle} crossOrigin="anonymous" />;
    }

    return (
      <Video
        src={fileUrl}
        {...computeMediaTrim(clip, fps)}
        playbackRate={getSanitizedPlaybackRate(clip.speed)}
        volume={effectiveVolume}
        muted={effectiveVolume <= 0}
        style={sharedStyle}
      />
    );
  }

  const fullBounds = {
    x: clip.x ?? 0,
    y: clip.y ?? 0,
    width: clip.width ?? compositionWidth,
    height: clip.height ?? compositionHeight,
  };
  const cropValues = normalizeRenderCropValues({
    cropTop: clip.cropTop,
    cropBottom: clip.cropBottom,
    cropLeft: clip.cropLeft,
    cropRight: clip.cropRight,
  });
  const intrinsicSize = getIntrinsicMediaSize(assetEntry.resolution);
  const viewportLayout = computeViewportMediaLayout({
    fullBounds,
    cropValues,
    compositionWidth,
    compositionHeight,
    intrinsicWidth: intrinsicSize.width,
    intrinsicHeight: intrinsicSize.height,
  });

  if (!viewportLayout) {
    return null;
  }

  const outerStyle: CSSProperties = {
    position: 'absolute',
    left: viewportLayout.renderBounds.x,
    top: viewportLayout.renderBounds.y,
    width: viewportLayout.renderBounds.width,
    height: viewportLayout.renderBounds.height,
    overflow: 'hidden',
    opacity,
  };
  const innerStyle: CSSProperties = {
    position: 'absolute',
    left: viewportLayout.mediaBounds.x,
    top: viewportLayout.mediaBounds.y,
    width: viewportLayout.mediaBounds.width,
    height: viewportLayout.mediaBounds.height,
    maxWidth: 'none',
    maxHeight: 'none',
    mixBlendMode,
  };

  if (isImage) {
    return (
      <div style={outerStyle}>
        <Img src={fileUrl} style={innerStyle} crossOrigin="anonymous" />
      </div>
    );
  }

  return (
    <div style={outerStyle}>
      <Video
        src={fileUrl}
        {...computeMediaTrim(clip, fps)}
        playbackRate={getSanitizedPlaybackRate(clip.speed)}
        volume={effectiveVolume}
        muted={effectiveVolume <= 0}
        style={innerStyle}
      />
    </div>
  );
};
