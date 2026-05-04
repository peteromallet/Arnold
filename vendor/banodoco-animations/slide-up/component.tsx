import type {ReactElement} from 'react';
import {interpolate} from 'remotion';
import type {WrapperAnimationProps} from '../../tools/remotion/src/effects.types';

export const SlideUp = ({
  children,
  durationFrames,
  elapsedFrames,
}: WrapperAnimationProps): ReactElement => {
  const progress = interpolate(elapsedFrames, [0, durationFrames], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: 1 - progress,
        transform: `translateY(${interpolate(progress, [0, 1], [0, -30])}px)`,
      }}
    >
      {children}
    </div>
  );
};

export default SlideUp;
