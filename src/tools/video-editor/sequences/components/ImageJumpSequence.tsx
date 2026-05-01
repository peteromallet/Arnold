import type { FC } from 'react';
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { useTheme, type RuntimeTheme } from '@banodoco/timeline-composition/theme-api';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types';

type ImageJumpSequenceParams = {
  images?: string[];
  imageAssetKeys?: string[];
  mode?: string;
};

type ImageJumpSequenceProps = {
  clip: ResolvedTimelineClip;
  params?: ImageJumpSequenceParams;
  theme?: RuntimeTheme;
  fps: number;
};

const imageFitForMode = (mode: string | undefined): 'cover' | 'contain' => (
  mode === 'gallery' ? 'contain' : 'cover'
);

export const ImageJumpSequence: FC<ImageJumpSequenceProps> = ({ params, fps }) => {
  const theme = useTheme();
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const images = Array.isArray(params?.images)
    ? params.images.filter((url) => typeof url === 'string' && url.trim().length > 0)
    : [];
  const mode = params?.mode;

  if (images.length === 0) {
    return (
      <AbsoluteFill
        style={{
          alignItems: 'center',
          background: theme.color.bg,
          color: theme.color.fg,
          display: 'flex',
          fontFamily: theme.type.families.mono,
          justifyContent: 'center',
          padding: 48,
        }}
      >
        No images selected
      </AbsoluteFill>
    );
  }

  const framesPerImage = Math.max(8, Math.round((fps * 0.72) / Math.max(1, Math.min(images.length, 3))));
  const activeIndex = Math.floor(frame / framesPerImage) % images.length;
  const localFrame = frame % framesPerImage;
  const pop = interpolate(localFrame, [0, 4, framesPerImage - 1], [0.92, 1.06, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const xJolt = interpolate(localFrame, [0, 3, framesPerImage - 1], [-32, 18, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const rotate = interpolate(localFrame, [0, 5, framesPerImage - 1], [-2.5, 1.25, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const nextIndex = (activeIndex + 1) % images.length;

  return (
    <AbsoluteFill
      style={{
        background: theme.color.bg,
        overflow: 'hidden',
      }}
    >
      <AbsoluteFill
        style={{
          opacity: 0.22,
          transform: 'scale(1.12)',
          filter: 'blur(18px)',
        }}
      >
        <Img
          src={images[nextIndex]}
          crossOrigin="anonymous"
          style={{
            height,
            objectFit: 'cover',
            width,
          }}
        />
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          alignItems: 'center',
          display: 'flex',
          justifyContent: 'center',
          padding: '5%',
        }}
      >
        <div
          style={{
            border: `2px solid ${theme.color.accent}`,
            boxShadow: `0 26px 90px ${theme.color.accent}2a`,
            height: '82%',
            overflow: 'hidden',
            position: 'relative',
            transform: `translate3d(${xJolt}px, 0, 0) scale(${pop}) rotate(${rotate}deg)`,
            width: '82%',
          }}
        >
          <Img
            src={images[activeIndex]}
            crossOrigin="anonymous"
            style={{
              background: theme.color.bg,
              height: '100%',
              objectFit: imageFitForMode(mode),
              width: '100%',
            }}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export default ImageJumpSequence;
