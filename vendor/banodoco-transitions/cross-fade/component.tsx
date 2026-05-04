import type {TransitionComponentResult, TransitionProps} from '../../tools/remotion/src/effects.types';

type CrossFadeParams = {
  easing?: string;
};

export const CrossFade = ({
  durationFrames,
  params,
}: TransitionProps<Record<string, unknown>>): TransitionComponentResult => {
  const typedParams = params as CrossFadeParams;
  return {
    presentation: {type: 'cross-fade', easing: typedParams.easing ?? 'linear'},
    timing: {type: 'linear', durationFrames},
  };
};

export default CrossFade;
