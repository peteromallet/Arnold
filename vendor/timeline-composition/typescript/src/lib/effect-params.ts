import type {TimelineClip} from '../types';

export const resolveParams = (clip: TimelineClip): unknown => {
  if (clip.clipType === 'text') {
    return clip.text;
  }
  return clip.params;
};
