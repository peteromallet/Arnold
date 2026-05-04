import type {TimelineConfig, TrackDefinition} from '../types';

const DEFAULT_VISUAL_TRACK: TrackDefinition = {
  id: 'v1',
  kind: 'visual',
  label: 'Video',
};

export const getVisualTracks = (
  timeline: Partial<Pick<TimelineConfig, 'tracks'>>,
): TrackDefinition[] => {
  const tracks = timeline.tracks ?? [DEFAULT_VISUAL_TRACK];
  return tracks.filter((track) => track.kind === 'visual');
};

export const getAudioTracks = (
  timeline: Partial<Pick<TimelineConfig, 'tracks'>>,
): TrackDefinition[] => {
  return (timeline.tracks ?? []).filter((track) => track.kind === 'audio');
};
