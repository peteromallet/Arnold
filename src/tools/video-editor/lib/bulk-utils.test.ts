import { describe, expect, it } from 'vitest';
import { getBulkVisibleTabs } from './bulk-utils';

describe('getBulkVisibleTabs', () => {
  const tracks = [
    { id: 'V1', kind: 'visual', label: 'Visual 1' },
    { id: 'A1', kind: 'audio', label: 'Audio 1' },
  ] as const;

  it('keeps text tabs only when every selected clip exposes inline text editing', () => {
    expect(getBulkVisibleTabs([
      {
        id: 'text-1',
        clipType: 'text',
        track: 'V1',
        at: 0,
        hold: 3,
      },
      {
        id: 'text-2',
        clipType: 'text',
        track: 'V1',
        at: 4,
        hold: 3,
      },
    ], [...tracks])).toEqual(['effects', 'timing', 'position', 'text']);

    expect(getBulkVisibleTabs([
      {
        id: 'text-1',
        clipType: 'text',
        track: 'V1',
        at: 0,
        hold: 3,
      },
      {
        id: 'hold-1',
        clipType: 'hold',
        track: 'V1',
        at: 4,
        hold: 3,
      },
    ], [...tracks])).toEqual(['effects', 'timing', 'position']);
  });

  it('surfaces audio controls when any selected clip exposes mute behavior', () => {
    expect(getBulkVisibleTabs([
      {
        id: 'hold-1',
        clipType: 'hold',
        track: 'V1',
        at: 0,
        hold: 3,
      },
      {
        id: 'media-1',
        clipType: 'media',
        track: 'V1',
        at: 4,
        from: 0,
        to: 3,
        assetEntry: {
          file: 'clip.mp4',
          src: 'https://cdn.example.test/clip.mp4',
          type: 'video/mp4',
        },
      },
    ], [...tracks])).toEqual(['effects', 'timing', 'position', 'audio']);
  });
});
