import { describe, expect, it } from 'vitest';
import {
  acceptLiveRecordingTake,
  bakeLiveRecording,
  bakeLiveRecordingPassTake,
  createLiveRecordingPass,
  discardLiveRecordingTake,
  startLiveRecordingPass,
  stopLiveRecordingPass,
} from '@/tools/video-editor/runtime/liveRecording';
import type {
  LiveChannelDescriptor,
  LiveSample,
  LiveSource,
} from '@reigh/editor-sdk';
import type { ParameterDefinition } from '@/tools/video-editor/types';

const source: LiveSource = {
  id: 'src-record',
  kind: 'midi',
  status: 'active',
  diagnostics: [],
};

const numberParam: ParameterDefinition = {
  name: 'opacity',
  label: 'Opacity',
  description: 'Opacity',
  type: 'number',
  min: 0,
  max: 1,
};

function sample(
  channelId: LiveChannelDescriptor,
  sequenceNumber: number,
  timestamp: number,
  data: Record<string, unknown>,
  metadata?: Record<string, unknown>,
): LiveSample {
  return {
    channelId,
    sequenceNumber,
    frame: {
      timestamp,
      data,
      format: 'json',
      metadata,
    },
  };
}

describe('liveRecording conversion', () => {
  it('records controller samples into deterministic keyframes without mutating input samples', () => {
    const channelId = 'src-record:knob' as LiveChannelDescriptor;
    const samples = [
      sample(channelId, 0, 1000, { controller: { knob: 0.103 } }),
      sample(channelId, 1, 1016, { controller: { knob: 0.106 } }),
      sample(channelId, 2, 1100, { controller: { knob: 0.49 } }),
      sample(channelId, 3, 1200, { controller: { knob: 0.93 } }),
    ];
    const before = JSON.stringify(samples);

    const result = bakeLiveRecording({
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'control' },
        samples,
      }],
      mappings: [{
        bindingId: 'binding-opacity',
        sourceId: source.id,
        channelId,
        sourcePath: 'controller.knob',
        parameter: numberParam,
        target: { kind: 'keyframe', clipId: 'clip-1', parameterPath: 'opacity' },
        clock: { sourceStartTimestampMs: 1000, timelineStartSeconds: 2 },
        recorderOptions: { quantizationStep: 0.01, tolerance: 0.05 },
      }],
    });

    expect(JSON.stringify(samples)).toBe(before);
    expect(result.success).toBe(true);
    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0]).toMatchObject({
      kind: 'keyframe',
      clipId: 'clip-1',
      parameterPath: 'opacity',
      keyframes: [
        { time: 2, value: 0.1, interpolation: 'linear' },
        { time: 2.1, value: 0.49, interpolation: 'linear' },
        { time: 2.2, value: 0.93, interpolation: 'linear' },
      ],
      metadata: {
        bindingId: 'binding-opacity',
        sourceId: source.id,
        channelIds: [channelId],
        sampleCount: 4,
        keyframeCount: 3,
        clock: {
          sourceStartTimestampMs: 1000,
          timelineStartSeconds: 2,
          firstSourceTimestamp: 1000,
          lastSourceTimestamp: 1200,
          firstTimelineTime: 2,
          lastTimelineTime: 2.2,
        },
      },
    });
    expect(result.outputs[0].metadata.inputHash).toMatch(/^fnv1a-[0-9a-f]{8}$/);
  });

  it('records audio-analysis samples into deterministic automation clips', () => {
    const channelId = 'src-record:rms' as LiveChannelDescriptor;

    const result = bakeLiveRecording({
      source: { ...source, kind: 'microphone' },
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'audio', metadata: { analysis: 'rms' } },
        samples: [
          sample(channelId, 0, 0, { rms: 0.1, takeId: 'take-a' }),
          sample(channelId, 1, 500, { rms: 0.6, takeId: 'take-a' }),
          sample(channelId, 2, 1000, { rms: 0.2, takeId: 'take-b' }),
        ],
      }],
      mappings: [{
        bindingId: 'binding-volume',
        sourceId: source.id,
        channelId,
        sourcePath: 'rms',
        parameter: { ...numberParam, name: 'volume' },
        target: {
          kind: 'automation',
          clipId: 'automation-live-volume',
          trackId: 'track-audio',
          contributionId: 'clip.audio-reactive',
          parameterPath: 'volume',
          at: 10,
        },
        selection: { takeId: 'take-a' },
        clock: { timelineStartSeconds: 10 },
      }],
    });

    expect(result.success).toBe(true);
    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0].kind).toBe('automation');
    if (result.outputs[0].kind !== 'automation') throw new Error('expected automation output');

    expect(result.outputs[0].clip).toMatchObject({
      id: 'automation-live-volume',
      at: 10,
      track: 'track-audio',
      clipType: 'automation',
      hold: 0.5,
      params: {
        target: {
          contributionId: 'clip.audio-reactive',
          parameterPath: 'volume',
        },
        keyframes: [
          { time: 10, value: 0.1, interpolation: 'linear' },
          { time: 10.5, value: 0.6, interpolation: 'linear' },
        ],
        enabled: true,
        liveRecording: {
          bindingId: 'binding-volume',
          sampleCount: 2,
          keyframeCount: 2,
        },
      },
    });
  });

  it('records scalar samples with default value inference and selection ranges', () => {
    const channelId = 'src-record:scalar' as LiveChannelDescriptor;

    const result = bakeLiveRecording({
      source: { ...source, kind: 'custom' },
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'data' },
        samples: [
          sample(channelId, 0, 0, { value: 0 }),
          sample(channelId, 1, 100, { value: 0.25 }),
          sample(channelId, 2, 200, { value: 0.5 }),
        ],
      }],
      mappings: [{
        sourceId: source.id,
        channelId,
        parameter: numberParam,
        target: { kind: 'keyframe', clipId: 'clip-1', parameterPath: 'opacity' },
        selection: { sampleRange: [1, 2] },
      }],
    });

    expect(result.success).toBe(true);
    expect(result.outputs[0]).toMatchObject({
      kind: 'keyframe',
      keyframes: [
        { time: 0.1, value: 0.25, interpolation: 'linear' },
        { time: 0.2, value: 0.5, interpolation: 'linear' },
      ],
      metadata: {
        sampleCount: 2,
        keyframeCount: 2,
      },
    });
  });

  it('diagnoses unresolved mappings instead of producing partial timeline writes', () => {
    const visualChannelId = 'src-record:video' as LiveChannelDescriptor;
    const controlChannelId = 'src-record:control' as LiveChannelDescriptor;

    const result = bakeLiveRecording({
      source,
      channels: [
        {
          metadata: { channelId: visualChannelId, sourceId: source.id, kind: 'video' },
          samples: [sample(visualChannelId, 0, 0, { value: 1 })],
        },
        {
          metadata: { channelId: controlChannelId, sourceId: source.id, kind: 'control' },
          samples: [sample(controlChannelId, 0, 0, { nested: { value: 1 } })],
        },
      ],
      mappings: [
        {
          sourceId: source.id,
          channelId: visualChannelId,
          parameter: numberParam,
          target: { kind: 'keyframe', clipId: 'clip-1', parameterPath: 'opacity' },
        },
        {
          sourceId: source.id,
          channelId: controlChannelId,
          sourcePath: 'missing.value',
          parameter: numberParam,
          target: { kind: 'keyframe', clipId: 'clip-1', parameterPath: 'opacity' },
        },
      ],
    });

    expect(result.success).toBe(false);
    expect(result.outputs).toEqual([]);
    expect(result.diagnostics.map((diagnostic) => diagnostic.code)).toEqual([
      'live/recording-incompatible-channel',
      'live/recording-empty-values',
    ]);
  });
});

describe('liveRecording pass state machine', () => {
  it('groups armed sources and mappings through transport start and captured take review', () => {
    const channelId = 'src-record:knob' as LiveChannelDescriptor;
    const pass = createLiveRecordingPass({
      id: 'pass-1',
      armedSources: [{ sourceId: source.id, channelIds: [channelId] }],
      mappings: [{
        bindingId: 'binding-opacity',
        sourceId: source.id,
        channelId,
        sourcePath: 'controller.knob',
        parameter: numberParam,
        target: { kind: 'keyframe', clipId: 'clip-1', parameterPath: 'opacity' },
      }],
      now: '2026-06-20T00:00:00.000Z',
    });

    const started = startLiveRecordingPass(pass, {
      takeId: 'take-a',
      startedAt: '2026-06-20T00:00:01.000Z',
    });
    expect(started.success).toBe(true);
    expect(started.pass).toMatchObject({
      status: 'recording',
      activeTakeId: 'take-a',
      takes: [{ id: 'take-a', status: 'captured', startedAt: '2026-06-20T00:00:01.000Z' }],
    });

    const stopped = stopLiveRecordingPass(started.pass, {
      stoppedAt: '2026-06-20T00:00:03.000Z',
      sampleCount: 3,
    });
    expect(stopped.success).toBe(true);
    expect(stopped.pass).toMatchObject({
      status: 'reviewing',
      activeTakeId: undefined,
      stoppedAt: '2026-06-20T00:00:03.000Z',
      takes: [{
        id: 'take-a',
        status: 'captured',
        sourceIds: [source.id],
        channelIds: [channelId],
        sampleCount: 3,
      }],
    });
    expect(pass.takes).toHaveLength(0);
  });

  it('prevents discarded takes from baking and bakes accepted takes by take ID', () => {
    const channelId = 'src-record:knob' as LiveChannelDescriptor;
    const pass = stopLiveRecordingPass(
      startLiveRecordingPass(createLiveRecordingPass({
        id: 'pass-accepted',
        armedSources: [{ sourceId: source.id, channelIds: [channelId] }],
        mappings: [{
          bindingId: 'binding-opacity',
          sourceId: source.id,
          channelId,
          sourcePath: 'controller.knob',
          parameter: numberParam,
          target: { kind: 'keyframe', clipId: 'clip-1', parameterPath: 'opacity' },
          clock: { sourceStartTimestampMs: 0 },
        }],
      }), { takeId: 'take-a' }).pass,
      { sampleCount: 2 },
    ).pass;

    const discarded = discardLiveRecordingTake(pass, 'take-a');
    expect(discarded.success).toBe(true);
    const discardedBake = bakeLiveRecordingPassTake(discarded.pass, {
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'control' },
        samples: [
          sample(channelId, 0, 0, { controller: { knob: 0.1 }, takeId: 'take-a' }),
          sample(channelId, 1, 100, { controller: { knob: 0.9 }, takeId: 'take-a' }),
        ],
      }],
    }, 'take-a');

    expect(discardedBake.success).toBe(false);
    expect(discardedBake.recording.outputs).toEqual([]);
    expect(discardedBake.diagnostics[0].code).toBe('live/recording-take-discarded');

    const accepted = acceptLiveRecordingTake(pass, 'take-a');
    expect(accepted.success).toBe(true);
    const acceptedBake = bakeLiveRecordingPassTake(accepted.pass, {
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'control' },
        samples: [
          sample(channelId, 0, 0, { controller: { knob: 0.1 }, takeId: 'take-a' }),
          sample(channelId, 1, 100, { controller: { knob: 0.9 }, takeId: 'take-a' }),
          sample(channelId, 2, 200, { controller: { knob: 0.5 }, takeId: 'take-b' }),
        ],
      }],
    }, 'take-a');

    expect(acceptedBake.success).toBe(true);
    expect(acceptedBake.recording.outputs).toHaveLength(1);
    expect(acceptedBake.recording.outputs[0]).toMatchObject({
      kind: 'keyframe',
      keyframes: [
        { time: 0, value: 0.1 },
        { time: 0.1, value: 0.9 },
      ],
    });
    expect(acceptedBake.pass.takes[0]).toMatchObject({
      id: 'take-a',
      status: 'baked',
      outputRefs: ['clip-1:opacity'],
    });
  });

  it('allows captured takes to bake before explicit acceptance but blocks repeat bake', () => {
    const channelId = 'src-record:rms' as LiveChannelDescriptor;
    const captured = stopLiveRecordingPass(
      startLiveRecordingPass(createLiveRecordingPass({
        id: 'pass-captured',
        armedSources: [{ sourceId: source.id, channelIds: [channelId] }],
        mappings: [{
          sourceId: source.id,
          channelId,
          sourcePath: 'rms',
          parameter: numberParam,
          target: { kind: 'automation', clipId: 'automation-rms', trackId: 'track-a', contributionId: 'clip.fx', parameterPath: 'opacity' },
        }],
      }), { takeId: 'take-live' }).pass,
    ).pass;

    const baked = bakeLiveRecordingPassTake(captured, {
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'audio' },
        samples: [
          sample(channelId, 0, 0, { rms: 0.2 }, { takeId: 'take-live' }),
          sample(channelId, 1, 100, { rms: 0.4 }, { takeId: 'take-live' }),
        ],
      }],
    }, 'take-live');

    expect(baked.success).toBe(true);
    expect(baked.recording.outputs[0].kind).toBe('automation');
    expect(baked.pass.takes[0].status).toBe('baked');

    const repeat = bakeLiveRecordingPassTake(baked.pass, {
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'audio' },
        samples: [sample(channelId, 0, 0, { rms: 0.2 }, { takeId: 'take-live' })],
      }],
    }, 'take-live');
    expect(repeat.success).toBe(false);
    expect(repeat.diagnostics[0].code).toBe('live/recording-take-already-baked');
  });
});
