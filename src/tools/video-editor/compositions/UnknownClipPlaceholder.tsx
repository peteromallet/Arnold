import type { CSSProperties, FC } from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { getClipDurationInFrames, secondsToFrames } from '@/tools/video-editor/lib/config-utils';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types';

/**
 * Loud placeholder for clips the editor cannot render — either because
 * `clipType` is unknown to the editor (Phase 4 will enable), or because a
 * known clipType is missing the asset it needs to render. Per SD-025 these
 * cases must be visible, never silent.
 *
 * Two styles:
 *   - "unsupported": yellow/amber band — the clipType is an unknown id that
 *     this editor build doesn't dispatch.
 *   - "missing-asset": red band — the clipType is a known id but the
 *     resolved asset isn't available.
 */

export type UnknownClipReason = 'unsupported' | 'missing-asset';

const STYLES: Record<UnknownClipReason, CSSProperties> = {
  unsupported: {
    backgroundColor: '#5B3A00',
    borderTop: '2px solid #F4B400',
    borderBottom: '2px solid #F4B400',
    color: '#FFE082',
  },
  'missing-asset': {
    backgroundColor: '#5B0000',
    borderTop: '2px solid #FF5252',
    borderBottom: '2px solid #FF5252',
    color: '#FFCDD2',
  },
};

const messageFor = (reason: UnknownClipReason, clipType: string): string => {
  switch (reason) {
    case 'unsupported':
      return `clipType '${clipType}' not yet supported by editor — Phase 4 will enable`;
    case 'missing-asset':
      return `clipType '${clipType}' missing asset — clip will not appear in render`;
  }
};

const Body: FC<{ reason: UnknownClipReason; clipType: string; clipId: string }> = ({
  reason,
  clipType,
  clipId,
}) => {
  const message = messageFor(reason, clipType);
  return (
    <AbsoluteFill
      data-testid="unknown-clip-placeholder"
      data-clip-id={clipId}
      data-clip-type={clipType}
      data-placeholder-reason={reason}
      style={{
        ...STYLES[reason],
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
        {message}
      </div>
    </AbsoluteFill>
  );
};

/**
 * Placeholder rendered as a Remotion <Sequence> at the clip's full
 * duration. Drop-in sibling of <VisualClipSequence>.
 */
export const UnknownClipPlaceholderSequence: FC<{
  clip: ResolvedTimelineClip;
  fps: number;
  reason: UnknownClipReason;
}> = ({ clip, fps, reason }) => {
  const durationInFrames = getClipDurationInFrames(clip, fps);
  const from = Math.max(0, secondsToFrames(clip.at, fps));
  return (
    <Sequence key={clip.id} from={from} durationInFrames={durationInFrames}>
      <Body reason={reason} clipType={clip.clipType ?? 'unknown'} clipId={clip.id} />
    </Sequence>
  );
};
