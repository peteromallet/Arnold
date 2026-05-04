export const CrossFade = ({ durationFrames, params, }) => {
    const typedParams = params;
    return {
        presentation: { type: 'cross-fade', easing: typedParams.easing ?? 'linear' },
        timing: { type: 'linear', durationFrames },
    };
};
export default CrossFade;
