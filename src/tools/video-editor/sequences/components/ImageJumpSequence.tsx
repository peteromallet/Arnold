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

const normalizeMotionMode = (mode: string | undefined): 'jump' | 'snap' | 'gallery' | 'pulse' | 'shuffle' => {
  const normalized = mode?.trim().toLowerCase();
  if (normalized === 'snap' || normalized === 'gallery' || normalized === 'pulse' || normalized === 'shuffle') {
    return normalized;
  }
  return 'jump';
};

export const ImageJumpSequence: FC<ImageJumpSequenceProps> = ({ params, fps }) => {
  const theme = useTheme();
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const images = Array.isArray(params?.images)
    ? params.images.filter((url) => typeof url === 'string' && url.trim().length > 0)
    : [];
  const mode = normalizeMotionMode(params?.mode);

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
  const previousIndex = (activeIndex - 1 + images.length) % images.length;

  if (mode === 'gallery') {
    const progress = localFrame / Math.max(1, framesPerImage - 1);
    const slide = interpolate(progress, [0, 1], [16, -16], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

    return (
      <AbsoluteFill style={{ background: theme.color.bg, overflow: 'hidden' }}>
        <AbsoluteFill
          style={{
            alignItems: 'center',
            display: 'flex',
            gap: '2.5%',
            justifyContent: 'center',
            padding: '5%',
            transform: `translateX(${slide}px)`,
          }}
        >
          {[previousIndex, activeIndex, nextIndex].map((imageIndex, index) => (
            <div
              key={`${imageIndex}-${index}`}
              style={{
                border: index === 1 ? `2px solid ${theme.color.accent}` : `1px solid ${theme.color.fg}33`,
                boxShadow: index === 1 ? `0 26px 90px ${theme.color.accent}2a` : 'none',
                height: index === 1 ? '78%' : '62%',
                opacity: index === 1 ? 1 : 0.52,
                overflow: 'hidden',
                width: index === 1 ? '46%' : '24%',
              }}
            >
              <Img
                src={images[imageIndex]}
                crossOrigin="anonymous"
                style={{
                  background: theme.color.bg,
                  height: '100%',
                  objectFit: 'contain',
                  width: '100%',
                }}
              />
            </div>
          ))}
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }

  const pulseScale = interpolate(localFrame, [0, framesPerImage / 2, framesPerImage - 1], [1, 1.08, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const snapScale = interpolate(localFrame, [0, 2, 5, framesPerImage - 1], [0.78, 1.12, 1, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const shuffleOffset = ((activeIndex % 3) - 1) * 54;
  const shuffleRotate = ((activeIndex % 5) - 2) * 2.4;
  const transform = mode === 'pulse'
    ? `scale(${pulseScale})`
    : mode === 'snap'
      ? `scale(${snapScale})`
      : mode === 'shuffle'
        ? `translate3d(${shuffleOffset + xJolt * 0.45}px, ${(activeIndex % 2 === 0 ? -1 : 1) * 18}px, 0) scale(${pop}) rotate(${shuffleRotate}deg)`
        : `translate3d(${xJolt}px, 0, 0) scale(${pop}) rotate(${rotate}deg)`;

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
            transform,
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
