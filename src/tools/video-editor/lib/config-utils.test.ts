import { describe, expect, it } from 'vitest';
import {
  getClipTimelineDuration,
  getSanitizedAssetFile,
  getSanitizedMediaSrc,
  getSanitizedMediaTrimProps,
  getSanitizedPlaybackRate,
  getSanitizedVolume,
  resolveTimelineConfig,
} from '@/tools/video-editor/lib/config-utils';
import {
  canonicalizeTimelineConfigSnapshot,
  canonicalizeTimelinePair,
  getConfigTimelineClipDuration,
  getPairTimelineClipDuration,
} from '@/tools/video-editor/lib/timeline-domain';

describe('config-utils media sanitizers', () => {
  it('omits trimAfter when source out is not greater than source in', () => {
    expect(getSanitizedMediaTrimProps({ from: 4, to: 4 }, 30)).toEqual({ trimBefore: 120 });
    expect(getSanitizedMediaTrimProps({ from: 4, to: 3 }, 30)).toEqual({ trimBefore: 120 });
  });

  it('clamps invalid trim, speed, and volume values to safe playback props', () => {
    expect(getSanitizedMediaTrimProps({ from: -2, to: Number.NaN }, 30)).toEqual({ trimBefore: 0 });
    expect(getSanitizedPlaybackRate(0)).toBe(1);
    expect(getSanitizedPlaybackRate(Number.NaN)).toBe(1);
    expect(getSanitizedVolume(-3)).toBe(0);
    expect(getSanitizedVolume(Number.NaN)).toBe(1);
  });

  it('accepts only non-empty string media sources', () => {
    expect(getSanitizedMediaSrc('https://example.com/video.mp4')).toBe('https://example.com/video.mp4');
    expect(getSanitizedMediaSrc(' https://example.com/video.mp4 ')).toBe('https://example.com/video.mp4');
    expect(getSanitizedMediaSrc('https://example.com/storage/v1/object/public/timeline-assets/')).toBeNull();
    expect(getSanitizedMediaSrc('')).toBeNull();
    expect(getSanitizedMediaSrc(undefined)).toBeNull();
  });

  it('accepts only non-empty asset file references', () => {
    expect(getSanitizedAssetFile(' uploads/test.mp4 ')).toBe('uploads/test.mp4');
    expect(getSanitizedAssetFile('')).toBeNull();
    expect(getSanitizedAssetFile('   ')).toBeNull();
    expect(getSanitizedAssetFile(undefined)).toBeNull();
  });

  it('drops clips whose asset entries resolve to invalid sources', async () => {
    const resolved = await resolveTimelineConfig(
      {
        output: { file: 'out.mp4', resolution: '1920x1080' },
        clips: [
          {
            id: 'clip-1',
            at: 0,
            track: 'track-1',
            asset: 'asset-1',
          },
        ],
        tracks: [
          {
            id: 'track-1',
            kind: 'audio',
            label: 'Audio',
          },
        ],
      },
      {
        assets: {
          'asset-1': {
            file: '',
            type: 'audio/mpeg',
          },
        },
      },
      async (file: string) => `https://example.com/${file}`,
    );

    expect(resolved.registry).toEqual({});
    expect(resolved.clips[0].assetEntry).toBeUndefined();
  });

  it('carries optional timeline theme extras into resolved config', async () => {
    const resolved = await resolveTimelineConfig(
      {
        output: { file: 'out.mp4', resolution: '1920x1080', fps: 30 },
        tracks: [{ id: 'V1', kind: 'visual', label: 'Visual' }],
        clips: [{ id: 'clip-1', at: 0, track: 'V1', clipType: 'hold', hold: 2 }],
        theme: '2rp',
        theme_overrides: { visual: { canvas: { fps: 24 } } },
        generation_defaults: { model: 'sequence-v1' },
      },
      { assets: {} },
      async (file: string) => `https://example.com/${file}`,
    );

    expect(resolved.theme).toBe('2rp');
    expect(resolved.theme_overrides).toEqual({ visual: { canvas: { fps: 24 } } });
    expect(resolved.generation_defaults).toEqual({ model: 'sequence-v1' });
  });

  it('keeps config-only malformed non-hold trims at zero duration but repairs pair-aware trims from registry duration', () => {
    const malformedClip = {
      id: 'clip-1',
      at: 0,
      track: 'V1',
      clipType: 'media' as const,
      asset: 'asset-1',
    };

    expect(getClipTimelineDuration(malformedClip)).toBe(0);
    expect(getConfigTimelineClipDuration(malformedClip)).toBe(0);
    expect(getPairTimelineClipDuration(malformedClip, {
      assets: { 'asset-1': { file: 'video.mp4', duration: 2.25 } },
    })).toBe(2.25);

    const configOnly = canonicalizeTimelineConfigSnapshot({
      output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [malformedClip],
    });
    expect(configOnly.config.clips[0]).toEqual(malformedClip);
    expect(configOnly.issues.map((issue) => issue.code)).toContain('malformed_non_hold_trim_zero_duration');

    const pairAware = canonicalizeTimelinePair(configOnly.config, {
      assets: { 'asset-1': { file: 'video.mp4', duration: 2.25 } },
    });
    expect(pairAware.config.clips[0]).toMatchObject({ from: 0, to: 2.25 });
    expect(pairAware.issues.map((issue) => issue.code)).toContain('malformed_non_hold_trim_repaired');
  });

  it('emits a structured zero-duration issue when malformed non-hold trims have no registry duration', () => {
    const pairAware = canonicalizeTimelinePair({
      output: { file: 'out.mp4', fps: 30, resolution: '1920x1080' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [{
        id: 'clip-1',
        at: 0,
        track: 'V1',
        clipType: 'media',
        asset: 'asset-1',
      }],
    }, {
      assets: { 'asset-1': { file: 'video.mp4' } },
    });

    expect(pairAware.config.clips[0]).not.toHaveProperty('from');
    expect(pairAware.config.clips[0]).not.toHaveProperty('to');
    expect(getPairTimelineClipDuration(pairAware.config.clips[0], pairAware.registry)).toBe(0);
    expect(pairAware.issues).toContainEqual(expect.objectContaining({
      code: 'malformed_non_hold_trim_zero_duration',
      clipId: 'clip-1',
      level: 'pair-aware',
      repairApplied: false,
    }));
  });
});
