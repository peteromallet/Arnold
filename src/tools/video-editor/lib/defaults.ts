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

export const DEFAULT_OUTPUT = {
  resolution: '1280x720',
  fps: 30,
  file: 'output.mp4',
  background: null as string | null,
  background_scale: null as number | null,
} as const;

export function createDefaultTimelineConfig(): TimelineConfig {
  // Sprint 2 schema-lift: `theme`, `theme_overrides`, and `generation_defaults`
  // are intentionally left absent here. New timelines start with no theme bound
  // (the editor today renders without a theme registry); the Theme chip in
  // Sprint 3 is responsible for populating these once the user picks a theme.
  // Keeping them undefined preserves byte-equivalence for every existing
  // call site that snapshots a freshly-created config.
  return {
    output: { ...DEFAULT_OUTPUT },
    clips: [],
    tracks: DEFAULT_VIDEO_TRACKS.map((track) => ({ ...track })),
  };
}

/**
 * Fill missing or incomplete output fields on a timeline config while
 * preserving all existing values and non-output fields (clips, tracks,
 * theme, theme_overrides, generation_defaults, pinnedShotGroups, app, etc.).
 *
 * Only absent or null-ish output fields are filled from defaults. Existing
 * output values — even empty strings or zero — are left untouched because
 * they represent explicit user choices.
 *
 * This is useful when the bridge loads a timeline that was authored with
 * a partial output block, or when a fixture needs to guarantee a complete
 * output shape without overwriting a caller's actual data.
 */
export function withDefaultTimelineOutput(
  config: Partial<TimelineConfig> & { output?: Partial<TimelineConfig['output']> },
): TimelineConfig {
  const existingOutput = config.output ?? ({} as Partial<TimelineConfig['output']>);

  const output: TimelineConfig['output'] = {
    resolution: existingOutput.resolution ?? DEFAULT_OUTPUT.resolution,
    fps: existingOutput.fps ?? DEFAULT_OUTPUT.fps,
    file: existingOutput.file ?? DEFAULT_OUTPUT.file,
    background: existingOutput.background !== undefined ? existingOutput.background : DEFAULT_OUTPUT.background,
    background_scale:
      existingOutput.background_scale !== undefined ? existingOutput.background_scale : DEFAULT_OUTPUT.background_scale,
  };

  return {
    output,
    clips: config.clips ?? [],
    tracks: config.tracks ?? DEFAULT_VIDEO_TRACKS.map((track) => ({ ...track })),
    ...('theme' in config ? { theme: config.theme } : {}),
    ...('theme_overrides' in config ? { theme_overrides: config.theme_overrides } : {}),
    ...('generation_defaults' in config ? { generation_defaults: config.generation_defaults } : {}),
    ...('pinnedShotGroups' in config ? { pinnedShotGroups: config.pinnedShotGroups } : {}),
    ...('app' in config ? { app: config.app } : {}),
  };
}
