import { describe, expect, it } from 'vitest';
import { bakeLiveSource } from '@/tools/video-editor/runtime/liveBake';
import type {
  LiveBakeSelection,
  LiveChannelDescriptor,
  LiveSample,
  LiveSource,
} from '@reigh/editor-sdk';

const source: LiveSource = {
  id: 'src-live',
  kind: 'generated',
  status: 'active',
  diagnostics: [],
};

function sample(
  channelId: LiveChannelDescriptor,
  sequenceNumber: number,
  timestamp: number,
  data: Record<string, unknown> | Uint8Array = { value: sequenceNumber },
  metadata?: Record<string, unknown>,
): LiveSample {
  return {
    channelId,
    sequenceNumber,
    frame: {
      timestamp,
      data,
      format: data instanceof Uint8Array ? 'raw' : 'json',
      metadata,
    },
  };
}

describe('liveBake planner', () => {
  it('fully bakes frame samples to deterministic asset replacement metadata', () => {
    const channelId = 'src-live:video' as LiveChannelDescriptor;
    const selection: LiveBakeSelection = {
      sourceId: source.id,
      channelIds: [channelId],
      targets: [{ kind: 'asset', ref: 'asset-live-frame' }],
    };

    const result = bakeLiveSource({
      selection,
      source,
      bindingIds: ['binding-frame'],
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'video' },
        samples: [
          sample(channelId, 0, 100, new Uint8Array([1, 2])),
          sample(channelId, 1, 200, new Uint8Array([3, 4])),
        ],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.targets[0].outputRef).toBe('asset-live-frame');
    expect(result.replacements).toHaveLength(1);
    expect(result.replacements[0].bindingIds).toEqual(['binding-frame']);
    expect(result.replacements[0].deterministicRef).toMatchObject({
      kind: 'asset',
      ref: 'asset-live-frame',
      metadata: {
        liveBake: {
          sourceId: source.id,
          targetKind: 'asset',
          sampleCount: 2,
          firstTimestamp: 100,
          lastTimestamp: 200,
        },
      },
    });
    expect(result.replacements[0].input.inputHash).toMatch(/^fnv1a-[0-9a-f]{8}$/);
    expect(result.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-complete')).toBe(true);
  });

  it('bakes audio and controller channels to keyframe, automation, and sidecar refs', () => {
    const audioChannelId = 'src-live:audio' as LiveChannelDescriptor;
    const controlChannelId = 'src-live:control' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        targets: [
          { kind: 'keyframe', ref: 'clip-1:opacity' },
          { kind: 'automation', ref: 'automation-live-volume' },
          { kind: 'sidecar', ref: 'sidecar-live-analysis' },
        ],
      },
      source,
      channels: [
        {
          metadata: { channelId: audioChannelId, sourceId: source.id, kind: 'audio' },
          samples: [sample(audioChannelId, 0, 0, { rms: 0.1 }), sample(audioChannelId, 1, 16, { rms: 0.2 })],
        },
        {
          metadata: { channelId: controlChannelId, sourceId: source.id, kind: 'control' },
          samples: [sample(controlChannelId, 0, 0, { knob: 0.5 })],
        },
      ],
    });

    expect(result.success).toBe(true);
    expect(result.targets.map((target) => target.outputRef)).toEqual([
      'clip-1:opacity',
      'automation-live-volume',
      'sidecar-live-analysis',
    ]);
    expect(result.replacements.map((replacement) => replacement.deterministicRef.kind)).toEqual([
      'keyframe',
      'automation',
      'sidecar',
    ]);
    expect(result.replacements[0].input.sampleCount).toBe(3);
  });

  it('bakes material destinations to RenderMaterial replacement refs', () => {
    const channelId = 'src-live:video' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        targets: [{
          kind: 'render-material',
          ref: 'material-live-frame',
          params: { producerExtensionId: 'ext.live', producerVersion: '1.2.3' },
        }],
      },
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'video' },
        samples: [sample(channelId, 0, 0, new Uint8Array([7, 8, 9]))],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.replacements[0].deterministicRef.kind).toBe('render-material');
    expect(result.replacements[0].renderMaterial).toMatchObject({
      id: 'material-live-frame',
      mediaKind: 'video',
      determinism: 'deterministic',
      replacementPolicy: 'replace-live-ref',
      producerExtensionId: 'ext.live',
      producerVersion: '1.2.3',
    });
    expect(result.replacements[0].renderMaterial?.locator.uri).toBe('live-bake://src-live/material-live-frame');
  });

  it('partially bakes by frame, time, sample-index range, and take ID', () => {
    const channelId = 'src-live:video' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        channelIds: [channelId],
        timeRange: [100, 300],
        frameRange: [10, 12],
        sampleRange: [1, 3],
        takeId: 'take-a',
        targets: [{ kind: 'asset', ref: 'asset-live-partial' }],
      },
      source,
      bindingIds: ['binding-partial'],
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'video' },
        samples: [
          sample(channelId, 0, 100, new Uint8Array([0]), { frameIndex: 10, takeId: 'take-a' }),
          sample(channelId, 1, 120, new Uint8Array([1]), { frameIndex: 11, takeId: 'take-a' }),
          sample(channelId, 2, 240, new Uint8Array([2]), { frameIndex: 12, takeId: 'take-a' }),
          sample(channelId, 3, 280, new Uint8Array([3]), { frameIndex: 13, takeId: 'take-a' }),
          sample(channelId, 4, 300, new Uint8Array([4]), { frameIndex: 12, takeId: 'take-b' }),
        ],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.replacements).toHaveLength(1);
    expect(result.replacements[0].input).toMatchObject({
      sampleCount: 2,
      firstTimestamp: 120,
      lastTimestamp: 240,
      range: {
        start: 100,
        end: 300,
        startFrame: 10,
        endFrame: 12,
        startSample: 1,
        endSample: 3,
        takeId: 'take-a',
      },
    });
    expect(result.replacements[0].deterministicRef).toMatchObject({
      kind: 'asset',
      ref: 'asset-live-partial',
      range: {
        start: 100,
        end: 300,
        startFrame: 10,
        endFrame: 12,
        startSample: 1,
        endSample: 3,
        takeId: 'take-a',
      },
      metadata: {
        liveBake: {
          partial: true,
          sampleCount: 2,
        },
      },
    });
  });

  it('fails without replacements for empty, targetless, invalid, or unmatched range bakes', () => {
    const channelId = 'src-live:control' as LiveChannelDescriptor;

    const empty = bakeLiveSource({
      selection: { sourceId: source.id, targets: [{ kind: 'keyframe', ref: 'clip-1:x' }] },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [] }],
    });
    expect(empty.success).toBe(false);
    expect(empty.replacements).toHaveLength(0);
    expect(empty.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-empty-selection')).toBe(true);

    const targetless = bakeLiveSource({
      selection: { sourceId: source.id, targets: [] },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [sample(channelId, 0, 0)] }],
    });
    expect(targetless.success).toBe(false);
    expect(targetless.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-no-targets')).toBe(true);

    const invalidRange = bakeLiveSource({
      selection: {
        sourceId: source.id,
        sampleRange: [2, 1],
        targets: [{ kind: 'keyframe', ref: 'clip-1:x' }],
      },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [sample(channelId, 0, 0)] }],
    });
    expect(invalidRange.success).toBe(false);
    expect(invalidRange.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-invalid-range')).toBe(true);

    const unmatchedRange = bakeLiveSource({
      selection: {
        sourceId: source.id,
        sampleRange: [5, 6],
        targets: [{ kind: 'keyframe', ref: 'clip-1:x' }],
      },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [sample(channelId, 0, 0)] }],
    });
    expect(unmatchedRange.success).toBe(false);
    expect(unmatchedRange.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-empty-selection')).toBe(true);
  });
});
