import { describe, it, expect } from 'vitest';
import {
  DEFAULT_OUTPUT,
  DEFAULT_VIDEO_TRACKS,
  createDefaultTimelineConfig,
  withDefaultTimelineOutput,
} from './defaults';
import type { TimelineConfig } from '@/tools/video-editor/types/index.ts';

describe('createDefaultTimelineConfig', () => {
  it('returns output with default resolution', () => {
    const config = createDefaultTimelineConfig();
    expect(config.output.resolution).toBe('1280x720');
  });

  it('returns output with default fps', () => {
    const config = createDefaultTimelineConfig();
    expect(config.output.fps).toBe(30);
  });

  it('returns output with default file', () => {
    const config = createDefaultTimelineConfig();
    expect(config.output.file).toBe('output.mp4');
  });

  it('returns default clips as empty array', () => {
    const config = createDefaultTimelineConfig();
    expect(config.clips).toEqual([]);
  });

  it('returns default tracks', () => {
    const config = createDefaultTimelineConfig();
    expect(config.tracks).toHaveLength(2);
    expect(config.tracks![0].id).toBe('V1');
    expect(config.tracks![1].id).toBe('A1');
  });
});

describe('DEFAULT_OUTPUT', () => {
  it('has expected resolution', () => {
    expect(DEFAULT_OUTPUT.resolution).toBe('1280x720');
  });

  it('has expected fps', () => {
    expect(DEFAULT_OUTPUT.fps).toBe(30);
  });

  it('has expected file', () => {
    expect(DEFAULT_OUTPUT.file).toBe('output.mp4');
  });

  it('has null background', () => {
    expect(DEFAULT_OUTPUT.background).toBeNull();
  });

  it('has null background_scale', () => {
    expect(DEFAULT_OUTPUT.background_scale).toBeNull();
  });
});

describe('withDefaultTimelineOutput', () => {
  it('fills completely missing output from defaults', () => {
    const result = withDefaultTimelineOutput({});
    expect(result.output.resolution).toBe('1280x720');
    expect(result.output.fps).toBe(30);
    expect(result.output.file).toBe('output.mp4');
    expect(result.output.background).toBeNull();
    expect(result.output.background_scale).toBeNull();
  });

  it('fills missing output fields while preserving existing ones', () => {
    const result = withDefaultTimelineOutput({
      output: { resolution: '1920x1080' },
    });
    expect(result.output.resolution).toBe('1920x1080'); // preserved
    expect(result.output.fps).toBe(30); // filled
    expect(result.output.file).toBe('output.mp4'); // filled
  });

  it('preserves all existing output fields', () => {
    const result = withDefaultTimelineOutput({
      output: {
        resolution: '3840x2160',
        fps: 60,
        file: '4k-output.mp4',
        background: '#000000',
        background_scale: 1.5,
      },
    });
    expect(result.output.resolution).toBe('3840x2160');
    expect(result.output.fps).toBe(60);
    expect(result.output.file).toBe('4k-output.mp4');
    expect(result.output.background).toBe('#000000');
    expect(result.output.background_scale).toBe(1.5);
  });

  it('preserves zero fps as explicit value', () => {
    const result = withDefaultTimelineOutput({
      output: { fps: 0 },
    });
    expect(result.output.fps).toBe(0);
  });

  it('preserves empty string file as explicit value', () => {
    const result = withDefaultTimelineOutput({
      output: { file: '' },
    });
    expect(result.output.file).toBe('');
  });

  it('preserves existing clips', () => {
    const result = withDefaultTimelineOutput({
      clips: [{ id: 'c1', at: 0, track: 'V1' }],
    });
    expect(result.clips).toEqual([{ id: 'c1', at: 0, track: 'V1' }]);
  });

  it('defaults clips to empty array when absent', () => {
    const result = withDefaultTimelineOutput({});
    expect(result.clips).toEqual([]);
  });

  it('preserves existing tracks', () => {
    const customTracks = [{ id: 'V2', kind: 'visual' as const, label: 'V2' }];
    const result = withDefaultTimelineOutput({ tracks: customTracks });
    expect(result.tracks).toEqual(customTracks);
  });

  it('defaults tracks when absent', () => {
    const result = withDefaultTimelineOutput({});
    expect(result.tracks).toHaveLength(2);
    expect(result.tracks![0].id).toBe('V1');
  });

  it('preserves theme when present', () => {
    const result = withDefaultTimelineOutput({ theme: 'dark-cinema' });
    expect(result.theme).toBe('dark-cinema');
  });

  it('omits theme when absent', () => {
    const result = withDefaultTimelineOutput({});
    expect(result).not.toHaveProperty('theme');
  });

  it('preserves theme_overrides when present', () => {
    const overrides = { visual: { contrast: 1.2 } };
    const result = withDefaultTimelineOutput({ theme_overrides: overrides });
    expect(result.theme_overrides).toEqual(overrides);
  });

  it('preserves generation_defaults when present', () => {
    const gd = { seed: 42 };
    const result = withDefaultTimelineOutput({ generation_defaults: gd });
    expect(result.generation_defaults).toEqual(gd);
  });

  it('preserves pinnedShotGroups when present', () => {
    const psg = [{ shotId: 's1', trackId: 'V1', clipIds: ['c1'] }];
    const result = withDefaultTimelineOutput({ pinnedShotGroups: psg });
    expect(result.pinnedShotGroups).toEqual(psg);
  });

  it('preserves app metadata when present', () => {
    const app = { importedFrom: 'bridge' };
    const result = withDefaultTimelineOutput({ app });
    expect(result.app).toEqual(app);
  });

  it('fills only output when other config fields are present', () => {
    const config: TimelineConfig = createDefaultTimelineConfig();
    // Remove the output entirely
    const { output: _output, ...rest } = config;
    const result = withDefaultTimelineOutput(rest);
    // output should be filled from defaults
    expect(result.output.resolution).toBe('1280x720');
    expect(result.output.fps).toBe(30);
    // other fields preserved
    expect(result.clips).toEqual(config.clips);
    expect(result.tracks).toEqual(config.tracks);
  });

  it('does not mutate the input config', () => {
    const input = {
      output: { resolution: '640x480' },
      clips: [{ id: 'c1', at: 0, track: 'V1' }],
    };
    const snapshot = JSON.stringify(input);
    withDefaultTimelineOutput(input);
    expect(JSON.stringify(input)).toBe(snapshot);
  });

  it('returns a new object (not same reference as input)', () => {
    const input = { output: { resolution: '640x480' } };
    const result = withDefaultTimelineOutput(input);
    expect(result).not.toBe(input);
    expect(result.output).not.toBe(input.output);
  });
});
