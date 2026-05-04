import { interpolate, spring } from 'remotion';
export const FadeUp = ({ children, fps, durationFrames, elapsedFrames, }) => {
    const progress = spring({
        frame: elapsedFrames,
        fps,
        from: 0,
        to: 1,
        durationInFrames: durationFrames,
        config: { damping: 14, stiffness: 110 },
    });
    return (<div style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: progress,
            transform: `translateY(${interpolate(progress, [0, 1], [40, 0])}px)`,
        }}>
      {children}
    </div>);
};
export default FadeUp;
