import { describe, expect, it } from 'vitest';
import { createVideoEditorClipTypeCapabilityManifest } from './manifest';

describe('clip type capability manifest', () => {
  it('exports a stable machine-readable manifest with builtin and trusted sequence entries', () => {
    const manifest = createVideoEditorClipTypeCapabilityManifest({});

    expect(manifest.version).toBe(1);

    const media = manifest.clipTypes.find((entry) => entry.id === 'media');
    expect(media).toMatchObject({
      id: 'media',
      source: 'builtin',
      exposure: {
        trusted: true,
        available: true,
        availability: 'builtin',
      },
      renderCapabilities: {
        previewRoute: 'native-media',
        exportRoute: 'client',
      },
    });

    const resourceCard = manifest.clipTypes.find((entry) => entry.id === 'resource-card');
    expect(resourceCard).toMatchObject({
      id: 'resource-card',
      source: 'sequence',
      exposure: {
        trusted: true,
        available: false,
        availability: 'unavailable',
      },
      themeId: '2rp',
      whenToUse: expect.stringContaining('resource reveal'),
      paramsSchema: {
        kind: 'sequence',
      },
      renderCapabilities: {
        previewRoute: 'sequence-component',
        exportRoute: 'custom',
      },
    });
  });

  it('preserves structured command metadata and reports available sequence registrations', () => {
    const manifest = createVideoEditorClipTypeCapabilityManifest({
      'image-jump': { component: 'test-sequence' },
      'title-card': { component: 'title-card-sequence' },
    });

    const imageJump = manifest.clipTypes.find((entry) => entry.id === 'image-jump');
    expect(imageJump).toMatchObject({
      exposure: {
        trusted: true,
        available: true,
        availability: 'available',
      },
    });
    expect(imageJump?.commands).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: 'split',
          requirements: [
            {
              fact: 'selection.cardinality',
              operator: 'equals',
              value: 'single',
            },
          ],
        }),
      ]),
    );

    const titleCard = manifest.clipTypes.find((entry) => entry.id === 'title-card');
    expect(titleCard).toMatchObject({
      id: 'title-card',
      exposure: {
        trusted: true,
        available: true,
        availability: 'available',
      },
      defaults: {
        params: {
          title: 'Build on the registry',
        },
      },
      renderCapabilities: {
        previewRoute: 'sequence-component',
        exportRoute: 'custom',
      },
    });

    const hold = manifest.clipTypes.find((entry) => entry.id === 'hold');
    expect(hold?.commands).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: 'split',
          label: 'Split',
        }),
      ]),
    );
    expect('render' in (hold ?? {})).toBe(false);
    expect('Inspector' in (hold ?? {})).toBe(false);
    expect('timelineDisplay' in (hold ?? {})).toBe(false);
    expect('resize' in (hold ?? {})).toBe(false);
    expect('drag' in (hold ?? {})).toBe(false);
  });
});
