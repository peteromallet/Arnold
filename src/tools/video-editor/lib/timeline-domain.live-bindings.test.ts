import { describe, expect, it } from 'vitest';
import {
  assertValidTimelineConfigSnapshot,
  scanTimelineLiveBindings,
  scanTimelineLiveUniformBindings,
  validateTimelineConfigSnapshot,
} from '@/tools/video-editor/lib/timeline-domain.ts';
import type { TimelineClip, TimelineConfig } from '@/tools/video-editor/types/index.ts';

const makeClip = (overrides: Partial<TimelineClip>): TimelineClip => ({
  id: 'clip-1',
  at: 0,
  track: 'V1',
  clipType: 'hold',
  hold: 2,
  ...overrides,
});

const makeConfig = (clips: TimelineClip[]): TimelineConfig => ({
  output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
  tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  clips,
});

describe('timeline live binding metadata scanner', () => {
  it('enumerates clip.app.live and params.liveBindings metadata without runtime registry state', () => {
    const config = makeConfig([
      makeClip({
        id: 'clip-app-live',
        app: {
          live: {
            bindings: [
              {
                bindingId: 'binding-app',
                sourceId: 'source-app',
                sourceKind: 'generated',
                channelId: 'source-app:video',
                sourceStatus: 'active',
              },
            ],
          },
        },
      }),
      makeClip({
        id: 'clip-param-live',
        params: {
          title: 'Live title',
          liveBindings: [
            {
              bindingId: 'binding-param',
              sourceId: 'source-param',
              sourceKind: 'midi',
              targetParamName: 'title',
              sourceStatus: 'inactive',
            },
          ],
        },
      }),
    ]);

    const scan = scanTimelineLiveBindings(config);

    expect(scan.bindings.map((record) => record.binding.bindingId)).toEqual([
      'binding-app',
      'binding-param',
    ]);
    expect(scan.counts.active).toBe(1);
    expect(scan.counts.inactive).toBe(1);
    expect(scan.hasBlockingLiveBindings).toBe(true);
    expect(() => assertValidTimelineConfigSnapshot(config)).not.toThrow();
  });

  it('classifies active, inactive, missing, disposed, orphaned, partially baked, and resolved bindings', () => {
    const config = makeConfig([
      makeClip({
        app: {
          live: [
            {
              bindingId: 'active-binding',
              sourceId: 'source-active',
              sourceKind: 'webcam',
            },
            {
              bindingId: 'inactive-binding',
              sourceId: 'source-inactive',
              sourceKind: 'microphone',
            },
            {
              bindingId: 'missing-binding',
              sourceId: 'source-missing',
              sourceKind: 'serial',
            },
            {
              bindingId: 'disposed-binding',
              sourceId: 'source-disposed',
              sourceKind: 'generated',
            },
            {
              bindingId: 'orphaned-binding',
              sourceId: 'source-orphaned',
              sourceKind: 'custom',
            },
            {
              bindingId: 'partial-binding',
              sourceId: 'source-partial',
              sourceKind: 'generated',
              bake: {
                status: 'partial',
                bakedRanges: [{ startFrame: 0, endFrame: 10 }],
                unresolvedRanges: [{ startFrame: 11, endFrame: 20 }],
              },
            },
            {
              bindingId: 'resolved-binding',
              sourceId: 'source-resolved',
              sourceKind: 'generated',
              bake: {
                status: 'complete',
                deterministicRefs: [{ kind: 'asset', ref: 'asset-live-baked' }],
              },
            },
          ],
        },
      }),
    ]);

    const scan = scanTimelineLiveBindings(config, {
      sources: [
        { sourceId: 'source-active', kind: 'webcam', status: 'active' },
        { sourceId: 'source-inactive', kind: 'microphone', status: 'inactive' },
        { sourceId: 'source-disposed', kind: 'generated', status: 'disposed' },
        { sourceId: 'source-orphaned', kind: 'custom', status: 'orphaned' },
      ],
    });
    const byId = new Map(scan.bindings.map((record) => [record.binding.bindingId, record]));

    expect(byId.get('active-binding')?.status).toBe('active');
    expect(byId.get('inactive-binding')?.status).toBe('inactive');
    expect(byId.get('missing-binding')?.status).toBe('missing');
    expect(byId.get('disposed-binding')?.status).toBe('disposed');
    expect(byId.get('orphaned-binding')?.status).toBe('orphaned');
    expect(byId.get('partial-binding')?.status).toBe('partiallyBaked');
    expect(byId.get('resolved-binding')?.status).toBe('resolved');
    expect(byId.get('resolved-binding')?.blocksExport).toBe(false);
    expect(byId.get('partial-binding')?.blocksExport).toBe(true);
    expect(scan.counts).toMatchObject({
      active: 1,
      inactive: 1,
      missing: 1,
      disposed: 1,
      orphaned: 1,
      partiallyBaked: 1,
      resolved: 1,
    });
  });

  it('keeps mixed resolved and unresolved bake ranges partially baked and export-blocked', () => {
    const config = makeConfig([
      makeClip({
        id: 'clip-partial-range',
        app: {
          live: [
            {
              bindingId: 'frame-range-partial',
              sourceId: 'source-range',
              sourceKind: 'generated',
              bake: {
                deterministicRefs: [{
                  kind: 'asset',
                  ref: 'asset-frame-range-0-10',
                  range: { startFrame: 0, endFrame: 10, takeId: 'take-a' },
                }],
                unresolvedRanges: [{ startFrame: 11, endFrame: 20, takeId: 'take-a' }],
              },
            },
            {
              bindingId: 'sample-range-partial',
              sourceId: 'source-sample',
              sourceKind: 'generated',
              deterministicRefs: [{
                kind: 'sidecar',
                ref: 'sidecar-sample-2-4',
                range: { startSample: 2, endSample: 4 },
              }],
              bake: {
                unresolvedRanges: [{ startSample: 5, endSample: 9 }],
              },
            },
          ],
        },
      }),
    ]);

    const scan = scanTimelineLiveBindings(config, {
      sources: [
        { sourceId: 'source-range', kind: 'generated', status: 'active' },
        { sourceId: 'source-sample', kind: 'generated', status: 'active' },
      ],
    });
    const byId = new Map(scan.bindings.map((record) => [record.binding.bindingId, record]));

    expect(byId.get('frame-range-partial')?.status).toBe('partiallyBaked');
    expect(byId.get('sample-range-partial')?.status).toBe('partiallyBaked');
    expect(byId.get('frame-range-partial')?.blocksExport).toBe(true);
    expect(byId.get('sample-range-partial')?.blocksExport).toBe(true);
    expect(scan.hasBlockingLiveBindings).toBe(true);
    expect(scan.counts.partiallyBaked).toBe(2);
    expect(scan.diagnostics.filter((diagnostic) => diagnostic.code === 'live-binding/partially-baked')).toHaveLength(2);
  });

  it('diagnoses malformed metadata and unsupported source kinds', () => {
    const config = makeConfig([
      makeClip({
        app: {
          live: [
            { bindingId: 'missing-source-kind', sourceId: 'source-1' },
            { bindingId: 'bad-kind', sourceId: 'source-2', sourceKind: 'neural-telemetry' },
            'not-a-binding',
          ],
        },
      }),
    ]);

    const scan = scanTimelineLiveBindings(config);
    const validation = validateTimelineConfigSnapshot(config);

    expect(scan.counts.malformed).toBe(3);
    expect(scan.diagnostics.map((diagnostic) => diagnostic.code)).toEqual(
      expect.arrayContaining([
        'live-binding/missing-source-kind',
        'live-binding/unsupported-source-kind',
        'live-binding/malformed-metadata',
      ]),
    );
    expect(validation.ok).toBe(false);
    expect(validation.issues.map((issue) => issue.code)).toEqual(
      expect.arrayContaining([
        'live_binding_missing_source_kind',
        'live_binding_unsupported_source_kind',
        'live_binding_malformed_metadata',
      ]),
    );
  });

  it('rejects sample payload data in persisted live binding metadata', () => {
    const config = makeConfig([
      makeClip({
        params: {
          liveBindings: [
            {
              bindingId: 'sampleful-binding',
              sourceId: 'source-sample',
              sourceKind: 'generated',
              frame: {
                timestamp: 100,
                data: { url: 'blob:runtime-only' },
              },
            },
          ],
        },
      }),
    ]);

    const validation = validateTimelineConfigSnapshot(config);
    const scan = scanTimelineLiveBindings(config);

    expect(scan.diagnostics.some((diagnostic) => diagnostic.code === 'live-binding/sample-payload-rejected')).toBe(true);
    expect(validation.ok).toBe(false);
    expect(validation.issues.some((issue) => issue.code === 'live_binding_sample_payload_rejected')).toBe(true);
  });
});

describe('timeline live uniform binding metadata scanner', () => {
  it('accepts scalar, vector, FFT-bin, RMS/amplitude, onset event, frame ref, and material ref mappings as metadata', () => {
    const config = makeConfig([
      makeClip({
        app: {
          liveUniformBindings: [
            {
              bindingId: 'uniform-scalar',
              sourceId: 'source-audio',
              sourceKind: 'microphone',
              mapping: { kind: 'scalar', uniform: 'u_gain', sourcePath: 'amplitude', scale: 2 },
            },
            {
              bindingId: 'uniform-vector',
              sourceId: 'source-midi',
              sourceKind: 'midi',
              mapping: { kind: 'vector', uniform: 'u_xy', components: ['x', 'y'], sourcePaths: ['cc.1', 'cc.2'] },
            },
            {
              bindingId: 'uniform-fft',
              sourceId: 'source-audio',
              sourceKind: 'microphone',
              mapping: { kind: 'fft-bin', uniform: 'u_fft8', bin: 8, fftSize: 1024, smoothing: 0.25 },
            },
            {
              bindingId: 'uniform-rms',
              sourceId: 'source-audio',
              sourceKind: 'microphone',
              mapping: { kind: 'rms-amplitude', uniform: 'u_rms', windowMs: 80 },
            },
            {
              bindingId: 'uniform-onset',
              sourceId: 'source-audio',
              sourceKind: 'microphone',
              mapping: { kind: 'onset-event', uniform: 'u_onset', threshold: 0.8, decayMs: 120 },
            },
          ],
        },
      }),
      makeClip({
        id: 'clip-param-uniforms',
        params: {
          liveUniformBindings: [
            {
              bindingId: 'uniform-frame-ref',
              sourceId: 'source-generated',
              sourceKind: 'generated',
              mapping: { kind: 'frame-ref', uniform: 'u_frame', ref: { kind: 'asset', ref: 'asset-frame-seq' } },
            },
            {
              bindingId: 'uniform-material-ref',
              sourceId: 'source-generated',
              sourceKind: 'generated',
              mapping: { kind: 'material-ref', uniform: 'u_material', ref: { kind: 'render-material', ref: 'mat-live' } },
            },
          ],
        },
      }),
    ]);

    const before = JSON.stringify(config);
    const scan = scanTimelineLiveUniformBindings(config);

    expect(scan.diagnostics).toEqual([]);
    expect(scan.bindings.map((record) => record.binding.bindingId)).toEqual([
      'uniform-scalar',
      'uniform-vector',
      'uniform-fft',
      'uniform-rms',
      'uniform-onset',
      'uniform-frame-ref',
      'uniform-material-ref',
    ]);
    expect(scan.bindings.map((record) => record.binding.mapping.kind)).toEqual([
      'scalar',
      'vector',
      'fft-bin',
      'rms-amplitude',
      'onset-event',
      'frame-ref',
      'material-ref',
    ]);
    expect(JSON.stringify(config)).toBe(before);
  });

  it('diagnoses invalid liveUniformBindings schemas and rejects embedded sample payloads without mutating timeline state', () => {
    const config = makeConfig([
      makeClip({
        app: {
          liveUniformBindings: [
            {
              bindingId: 'bad-vector',
              sourceId: 'source-midi',
              sourceKind: 'midi',
              mapping: { kind: 'vector', uniform: 'u_bad', components: ['x', 'bad'] },
            },
            {
              bindingId: 'bad-fft',
              sourceId: 'source-audio',
              sourceKind: 'microphone',
              mapping: { kind: 'fft-bin', uniform: 'u_fft', bin: -1 },
            },
            {
              bindingId: 'bad-ref',
              sourceId: 'source-generated',
              sourceKind: 'generated',
              mapping: { kind: 'material-ref', uniform: 'u_mat', ref: { kind: 'render-material' } },
            },
            {
              bindingId: 'sampleful-uniform',
              sourceId: 'source-generated',
              sourceKind: 'generated',
              frame: { timestamp: 10, data: { value: 1 }, format: 'json' },
              mapping: { kind: 'scalar', uniform: 'u_sample' },
            },
            {
              bindingId: 'bad-kind',
              sourceId: 'source-generated',
              sourceKind: 'neural-telemetry',
              mapping: { kind: 'scalar', uniform: 'u_kind' },
            },
            {
              bindingId: 'missing-uniform',
              sourceId: 'source-generated',
              sourceKind: 'generated',
              mapping: { kind: 'scalar' },
            },
          ],
        },
      }),
    ]);

    const before = JSON.stringify(config);
    const scan = scanTimelineLiveUniformBindings(config);

    expect(scan.bindings).toEqual([]);
    expect(scan.diagnostics.map((diagnostic) => diagnostic.code)).toEqual(
      expect.arrayContaining([
        'live-uniform-binding/invalid-vector-components',
        'live-uniform-binding/invalid-fft-bin',
        'live-uniform-binding/invalid-deterministic-ref',
        'live-uniform-binding/sample-payload-rejected',
        'live-uniform-binding/unsupported-source-kind',
        'live-uniform-binding/missing-uniform',
      ]),
    );
    expect(JSON.stringify(config)).toBe(before);
  });
});
