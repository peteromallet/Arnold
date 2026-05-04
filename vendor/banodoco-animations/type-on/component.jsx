import { interpolate } from 'remotion';
export const TypeOn = ({ text, fps, durationFrames, elapsedFrames, params, }) => {
    if (!text) {
        return {};
    }
    const typedParams = params;
    const startFrame = typedParams.startFrame ?? 18;
    const durationFraction = typedParams.durationFraction ?? 0.55;
    const endFrame = Math.max(startFrame + 1, Math.floor(durationFrames * durationFraction));
    const revealRatio = interpolate(elapsedFrames, [startFrame, endFrame], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
    });
    const revealCount = Math.max(0, Math.min(text.length, Math.ceil(text.length * revealRatio)));
    const visibleText = text.slice(0, revealCount);
    const hiddenTail = text.slice(revealCount);
    const shouldShowCaret = (typedParams.showCaret ?? true) && revealRatio < 1;
    const caretOpacity = shouldShowCaret
        ? (Math.floor(elapsedFrames / Math.max(1, Math.round(fps / 3))) % 2 === 0 ? 1 : 0)
        : 0;
    return {
        content: (<span>
        <span>{visibleText}</span>
        <span aria-hidden style={{
                display: 'inline-block',
                width: '0.05em',
                marginLeft: shouldShowCaret ? '0.05em' : 0,
                opacity: caretOpacity,
                backgroundColor: 'currentColor',
                height: '1em',
                verticalAlign: '-0.15em',
            }}/>
        <span style={{ opacity: 0 }}>{hiddenTail}</span>
      </span>),
    };
};
export default TypeOn;
