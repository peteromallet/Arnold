import type { TimelineConfig, TrackDefinition } from '@/tools/video-editor/types/index.ts';

export const DEFAULT_VIDEO_TRACKS: TrackDefinition[] = [
  {
    id: 'V1',
    kind: 'visual',
    label: 'V1',
    scale: 1,
    fit: 'contain',
    opacity: 1,
    blendMode: 'normal',
  },
  {
    id: 'A1',
    kind: 'audio',
    label: 'A1',
    scale: 1,
    fit: 'contain',
    opacity: 1,
    blendMode: 'normal',
  },
];

export function createDefaultTimelineConfig(): TimelineConfig {
  // Sprint 2 schema-lift: `theme`, `theme_overrides`, and `generation_defaults`
  // are intentionally left absent here. New timelines start with no theme bound
  // (the editor today renders without a theme registry); the Theme chip in
  // Sprint 3 is responsible for populating these once the user picks a theme.
  // Keeping them undefined preserves byte-equivalence for every existing
  // call site that snapshots a freshly-created config.
  return {
    output: {
      resolution: '1280x720',
      fps: 30,
      file: 'output.mp4',
      background: null,
      background_scale: null,
    },
    clips: [],
    tracks: DEFAULT_VIDEO_TRACKS.map((track) => ({ ...track })),
  };
}
