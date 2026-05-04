import { interpolate, spring } from 'remotion';
export const Fade = ({ children, fps, phase, durationFrames, elapsedFrames, }) => {
    const progress = phase === 'exit'
        ? interpolate(elapsedFrames, [0, durationFrames], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
        })
        : spring({
            frame: elapsedFrames,
            fps,
            from: 0,
            to: 1,
            durationInFrames: durationFrames,
            config: { damping: 14, stiffness: 110 },
        });
    return (<div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: phase === 'exit' ? 1 - progress : progress }}>
      {children}
    </div>);
};
export default Fade;
