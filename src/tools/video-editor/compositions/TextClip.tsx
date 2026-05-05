import type { FC } from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { getClipDurationInFrames, secondsToFrames } from '@/tools/video-editor/lib/config-utils.ts';
import { wrapWithClipEffects } from '@/tools/video-editor/effects/index.tsx';
import type { ResolvedTimelineClip, TrackDefinition } from '@/tools/video-editor/types/index.ts';

type TextClipProps = {
  clip: ResolvedTimelineClip;
  track: TrackDefinition;
  fps: number;
};

export const TextClip: FC<TextClipProps> = ({ clip, track: _track, fps }) => {
  const durationInFrames = getClipDurationInFrames(clip, fps);
  const text = clip.text;
  if (!text) {
    return null;
  }

  const content = (
    <AbsoluteFill
      style={{
        left: clip.x ?? 0,
        top: clip.y ?? 0,
        width: clip.width ?? 640,
        height: clip.height ?? 160,
        position: 'absolute',
        justifyContent: 'center',
        color: text.color ?? '#ffffff',
        fontFamily: text.fontFamily ?? 'Georgia, serif',
        fontSize: text.fontSize ?? 64,
        fontWeight: text.bold ? 700 : 400,
        fontStyle: text.italic ? 'italic' : 'normal',
        textAlign: text.align ?? 'center',
        whiteSpace: 'pre-wrap',
        lineHeight: 1.1,
        textShadow: '0 2px 18px rgba(0, 0, 0, 0.35)',
        opacity: clip.opacity ?? 1,
      }}
    >
      {text.content}
    </AbsoluteFill>
  );

  return <>{wrapWithClipEffects(content, clip, durationInFrames, fps)}</>;
};

export const TextClipSequence: FC<TextClipProps> = ({ clip, track, fps }) => {
  return (
    <Sequence
      key={clip.id}
      from={secondsToFrames(clip.at, fps)}
      durationInFrames={getClipDurationInFrames(clip, fps)}
    >
      <TextClip clip={clip} track={track} fps={fps} />
    </Sequence>
  );
};
