import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LiveChannelDescriptor, LiveSampleFormat } from '@reigh/editor-sdk';
import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry';
import {
  createLiveMappingTable,
  startLiveMappingLearn,
  type LiveMappingTarget,
} from '@/tools/video-editor/runtime/liveMapping';

const TARGET: LiveMappingTarget = {
  kind: 'clip',
  ref: 'clip-1',
  parameterPath: 'params.opacity',
  label: 'Opacity',
};

function makeFrame(
  timestamp: number,
  data: Record<string, unknown> = { value: 0.5 },
  format: LiveSampleFormat = 'json',
) {
  return {
    timestamp,
    data,
    format,
    metadata: { unit: 'normalized' },
  };
}

function setupRegistry(sourceId = 'src-1', channelKind: 'control' | 'audio' | 'midi' = 'control') {
  const registry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
  registry.registerSource({ id: sourceId, kind: channelKind === 'audio' ? 'microphone' : 'midi' });
  const channelId = registry.openChannel(sourceId, channelKind, { label: 'Controller' });
  return { registry, sourceId, channelId };
}

afterEach(() => {
  vi.useRealTimers();
});

describe('liveMapping learn runtime', () => {
  it('captures the next sample as a metadata-only candidate and accepts it into a mapping table', () => {
    const { registry, sourceId, channelId } = setupRegistry();
    const states: string[] = [];
    const session = startLiveMappingLearn(registry, {
      id: 'learn-1',
      sourceId,
      channelId,
      target: TARGET,
      timeoutMs: 1_000,
      now: () => new Date('2026-06-20T00:00:00.000Z'),
      onStateChange: (state) => states.push(state.status),
    });

    expect(session.getState().status).toBe('listening');
    expect(session.getState().visual).toMatchObject({
      status: 'listening',
      learnMode: 'mapping',
      progress: 0,
      targetLabel: 'Opacity',
    });

    registry.pushSample(channelId, makeFrame(42, { midiNote: 64, velocity: 0.8 }));
    registry.pushSample(channelId, makeFrame(84, { midiNote: 65, velocity: 0.7 }));

    const candidateState = session.getState();
    expect(candidateState.status).toBe('candidate');
    expect(candidateState.visual).toMatchObject({ learnMode: 'mapping', progress: 1 });
    expect(candidateState.candidate).toMatchObject({
      id: 'learn-1:candidate:0',
      sourceId,
      channelId,
      channelKind: 'control',
      sequenceNumber: 0,
      sampleTimestamp: 42,
      sampleFormat: 'json',
      frameMetadata: { unit: 'normalized' },
    });
    expect(candidateState.candidate).not.toHaveProperty('data');
    expect(candidateState.candidate).not.toHaveProperty('value');

    const accepted = session.acceptCandidate({
      candidateId: candidateState.candidate!.id,
      table: createLiveMappingTable(),
      metadata: { curve: 'linear' },
      now: () => new Date('2026-06-20T00:00:01.000Z'),
    });

    expect(accepted.success).toBe(true);
    expect(accepted.table.entries).toHaveLength(1);
    expect(accepted.mapping).toMatchObject({
      mappingId: 'learn-1:mapping',
      sourceId,
      channelId,
      target: TARGET,
      createdAt: '2026-06-20T00:00:01.000Z',
      metadata: { curve: 'linear' },
    });
    expect(accepted.mapping!.candidate).not.toHaveProperty('data');
    expect(session.getState().status).toBe('mapped');
    expect(states).toEqual(['listening', 'candidate', 'mapped']);
  });

  it('times out without selecting a candidate and unsubscribes from later samples', () => {
    vi.useFakeTimers();
    const { registry, sourceId, channelId } = setupRegistry();
    const session = startLiveMappingLearn(registry, {
      id: 'learn-timeout',
      sourceId,
      channelId,
      target: TARGET,
      timeoutMs: 500,
    });

    vi.advanceTimersByTime(500);

    expect(session.getState().status).toBe('timed-out');
    expect(session.getState().diagnostics.map((diagnostic) => diagnostic.code)).toContain('live/learn-timeout');

    registry.pushSample(channelId, makeFrame(1));
    expect(session.getState().candidate).toBeUndefined();
    expect(session.getState().visual).toMatchObject({ status: 'timed-out', learnMode: 'idle' });
  });

  it('cancels an active learn session without accepting later samples', () => {
    const { registry, sourceId, channelId } = setupRegistry();
    const session = startLiveMappingLearn(registry, {
      id: 'learn-cancel',
      sourceId,
      channelId,
      target: TARGET,
      timeoutMs: 1_000,
    });

    session.cancel('user-dismissed');
    registry.pushSample(channelId, makeFrame(1));

    expect(session.getState().status).toBe('cancelled');
    expect(session.getState().candidate).toBeUndefined();
    expect(session.getState().diagnostics).toContainEqual(expect.objectContaining({
      code: 'live/learn-cancelled',
      detail: { reason: 'user-dismissed' },
    }));
  });

  it('rejects mismatched candidate selection without creating a mapping', () => {
    const { registry, sourceId, channelId } = setupRegistry();
    const session = startLiveMappingLearn(registry, {
      id: 'learn-select',
      sourceId,
      channelId,
      target: TARGET,
    });
    registry.pushSample(channelId, makeFrame(10));

    const result = session.acceptCandidate({ candidateId: 'other-candidate' });

    expect(result.success).toBe(false);
    expect(result.table.entries).toHaveLength(0);
    expect(result.diagnostics).toContainEqual(expect.objectContaining({
      code: 'live/learn-candidate-mismatch',
      detail: {
        candidateId: 'other-candidate',
        expectedCandidateId: 'learn-select:candidate:0',
      },
    }));
    expect(session.getState().status).toBe('candidate');
  });

  it('reports validation diagnostics for malformed requests before subscribing', () => {
    const { registry, sourceId, channelId } = setupRegistry('src-valid');
    registry.registerSource({ id: 'src-other', kind: 'custom' });
    const otherChannelId = registry.openChannel('src-other', 'data');

    const session = startLiveMappingLearn(registry, {
      id: '   ',
      sourceId,
      channelId: otherChannelId,
      target: { ...TARGET, ref: '', parameterPath: '' },
      timeoutMs: 0,
    });

    expect(session.getState().status).toBe('error');
    expect(session.getState().diagnostics.map((diagnostic) => diagnostic.code)).toEqual(expect.arrayContaining([
      'live/learn-invalid-request',
      'live/learn-invalid-target',
      'live/learn-invalid-timeout',
      'live/learn-channel-source-mismatch',
    ]));

    registry.pushSample(otherChannelId, makeFrame(1));
    expect(session.getState().candidate).toBeUndefined();
    expect(channelId).toEqual(expect.any(String));
  });

  it('uses the same host mapping shape for audio and MIDI without interpreting payloads', () => {
    const audio = setupRegistry('audio-src', 'audio');
    const midi = setupRegistry('midi-src', 'midi');

    const audioSession = startLiveMappingLearn(audio.registry, {
      id: 'learn-audio',
      sourceId: audio.sourceId,
      channelId: audio.channelId,
      target: TARGET,
    });
    const midiSession = startLiveMappingLearn(midi.registry, {
      id: 'learn-midi',
      sourceId: midi.sourceId,
      channelId: midi.channelId,
      target: TARGET,
    });

    audio.registry.pushSample(audio.channelId, makeFrame(1, { rms: 0.7, fft: [0.1, 0.2] }));
    midi.registry.pushSample(midi.channelId, makeFrame(1, { controller: 74, value: 32 }));

    const audioMapping = audioSession.acceptCandidate().mapping!;
    const midiMapping = midiSession.acceptCandidate().mapping!;

    expect(audioMapping.channelKind).toBe('audio');
    expect(midiMapping.channelKind).toBe('midi');
    expect(audioMapping.candidate).not.toHaveProperty('data');
    expect(midiMapping.candidate).not.toHaveProperty('data');
    expect(Object.keys(audioMapping.candidate).sort()).toEqual(Object.keys(midiMapping.candidate).sort());
  });

  it('surfaces channel-close diagnostics during capture', () => {
    const { registry, sourceId, channelId } = setupRegistry();
    const session = startLiveMappingLearn(registry, {
      id: 'learn-close',
      sourceId,
      channelId: channelId as LiveChannelDescriptor,
      target: TARGET,
    });

    registry.closeChannel(channelId);

    expect(session.getState().status).toBe('error');
    expect(session.getState().diagnostics).toContainEqual(expect.objectContaining({
      code: 'live/learn-channel-closed',
    }));
  });
});
