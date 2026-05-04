import { describe, expect, it } from 'vitest';
import {
  defineClipType,
  isEditorParamsSchema,
  isEmptyParamsSchema,
  isSequenceParamsSchema,
  toClipTypeManifest,
} from '@/tools/video-editor/clip-types';

describe('defineClipType', () => {
  it('normalizes hold defaults, injects the clipType id, and derives sequence param defaults', () => {
    const descriptor = defineClipType({
      id: 'title-card',
      label: 'Title Card',
      hold: {
        kind: 'required',
        defaultSeconds: 4,
        minSeconds: 1,
        maxSeconds: 12,
        stepSeconds: 0.5,
      },
      paramsSchema: {
        kind: 'sequence',
        params: [
          {
            key: 'title',
            label: 'Title',
            kind: 'string',
            description: 'Headline text.',
            required: true,
            defaultValue: 'Hello world',
          },
          {
            key: 'imageAssetKeys',
            label: 'Images',
            kind: 'asset-list',
            description: 'Registry asset keys.',
            defaultValue: [],
            componentParam: 'images',
            maxItems: 3,
          },
        ],
      },
      defaults: {
        clip: {
          opacity: 0.9,
        },
      },
      renderCapabilities: {
        previewRoute: 'sequence-component',
        exportRoute: 'banodoco',
        features: ['overlay', 'hold-duration'],
      },
    });

    expect(descriptor.hold).toMatchObject({
      kind: 'required',
      defaultSeconds: 4,
    });
    expect(descriptor.defaults.clip).toMatchObject({
      clipType: 'title-card',
      hold: 4,
      opacity: 0.9,
    });
    expect(descriptor.defaults.params).toEqual({
      title: 'Hello world',
      imageAssetKeys: [],
    });
    expect(isSequenceParamsSchema(descriptor.paramsSchema)).toBe(true);
  });

  it('preserves editor-shaped parameter schemas and explicit param overrides', () => {
    const descriptor = defineClipType({
      id: 'effect-layer',
      paramsSchema: {
        kind: 'editor',
        params: [
          {
            name: 'intensity',
            label: 'Intensity',
            description: 'Effect intensity',
            type: 'number',
            min: 0,
            max: 100,
            default: 50,
          },
          {
            name: 'reactive',
            label: 'Reactive',
            description: 'Audio reactive mode',
            type: 'audio-binding',
            default: {
              source: 'bass',
              min: 0.2,
              max: 0.8,
            },
          },
        ],
      },
      defaults: {
        params: {
          intensity: 75,
        },
      },
      renderCapabilities: {
        previewRoute: 'effect-layer',
        exportRoute: 'client',
        knownLimitations: ['Requires a visual track beneath it.'],
      },
    });

    expect(descriptor.defaults.clip).toMatchObject({
      clipType: 'effect-layer',
    });
    expect(descriptor.defaults.params).toEqual({
      intensity: 75,
      reactive: {
        source: 'bass',
        min: 0.2,
        max: 0.8,
      },
    });
    expect(isEditorParamsSchema(descriptor.paramsSchema)).toBe(true);
  });

  it('exports a manifest without runtime-only adapters and keeps command requirements inspectable', () => {
    const descriptor = defineClipType({
      id: 'hold',
      hold: {
        kind: 'required',
        defaultSeconds: 3,
        minSeconds: 1,
        maxSeconds: 12,
        stepSeconds: 0.5,
      },
      defaults: {
        clip: {
          opacity: 1,
        },
      },
      render: () => null,
      Inspector: () => null,
      timelineDisplay: {
        getLabel: () => 'Hold',
      },
      resize: {
        policy: 'hold-only',
      },
      drag: {
        policy: 'default',
        allowsCrossTrack: true,
      },
      commands: [
        {
          id: 'trim',
          label: 'Trim',
          requirements: [
            {
              fact: 'selection.cardinality',
              operator: 'equals',
              value: 'single',
              rationale: 'Trim operates on one focused clip.',
            },
          ],
          limitations: [
            {
              fact: 'track.kind',
              operator: 'equals',
              value: 'audio',
              rationale: 'Hold clips are visual-only.',
            },
          ],
        },
      ],
      renderCapabilities: {
        previewRoute: 'native-media',
        exportRoute: 'client',
        features: ['overlay', 'hold-duration'],
        knownLimitations: ['No source-media trimming surface.'],
      },
    });

    const manifest = toClipTypeManifest(descriptor);
    expect(manifest).toMatchObject({
      id: 'hold',
      hold: {
        kind: 'required',
        defaultSeconds: 3,
      },
      defaults: {
        clip: {
          clipType: 'hold',
          hold: 3,
          opacity: 1,
        },
      },
      commands: [
        {
          id: 'trim',
          requirements: [
            {
              fact: 'selection.cardinality',
              operator: 'equals',
              value: 'single',
            },
          ],
          limitations: [
            {
              fact: 'track.kind',
              operator: 'equals',
              value: 'audio',
            },
          ],
        },
      ],
      renderCapabilities: {
        previewRoute: 'native-media',
        exportRoute: 'client',
      },
    });
    expect('render' in manifest).toBe(false);
    expect('Inspector' in manifest).toBe(false);
    expect('timelineDisplay' in manifest).toBe(false);
    expect('resize' in manifest).toBe(false);
    expect('drag' in manifest).toBe(false);
  });

  it('defaults to an empty params schema when a clip type has no editable params', () => {
    const descriptor = defineClipType({
      id: 'media',
      renderCapabilities: {
        previewRoute: 'native-media',
        exportRoute: 'client',
      },
    });

    expect(isEmptyParamsSchema(descriptor.paramsSchema)).toBe(true);
    expect(descriptor.defaults).toEqual({
      clip: {
        clipType: 'media',
      },
      params: {},
    });
  });
});
