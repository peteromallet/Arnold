import { describe, expect, it } from 'vitest';
import type { SteeringDecision, LiveChannelDescriptor } from '@reigh/editor-sdk';
import {
  evaluateGenerationSessionLiveDeliveryGate,
  resolveLiveSteering,
} from './liveSteering';

const CHANNEL = 'session-1:frames' as LiveChannelDescriptor;

function baseRequest() {
  return {
    sessionId: 'session-1',
    currentGenerationIndex: 0,
    parentRefs: ['session-0'],
    producerVersion: '1.2.3',
    provenance: {
      prompt: 'A slow pan across clouds',
      model: 'reigh-gen-v1',
      seed: 42,
      producerExtensionId: 'ext.generator',
      tags: ['user-approved'],
    },
    currentChannelId: CHANNEL,
    replacementChannelId: CHANNEL,
    parameters: [
      { path: 'params.prompt', hotness: 'hot' as const },
      { path: 'params.model', hotness: 'non-hot' as const },
    ],
    changes: [
      {
        path: 'params.prompt',
        previousValue: 'clouds',
        nextValue: 'storm clouds',
      },
    ],
    priorSamplePolicy: 'replace' as const,
  };
}

describe('resolveLiveSteering', () => {
  it('supersedes hot params with complete lineage and replace prior-sample policy', () => {
    const result = resolveLiveSteering(baseRequest());

    expect(result.decision.kind).toBe('supersede');
    expect(result.canActivateLiveDelivery).toBe(true);
    expect(result.hotChanges.map((change) => change.path)).toEqual(['params.prompt']);
    expect(result.nonHotChanges).toHaveLength(0);
    expect(result.decision.replacementChannelId).toBe(CHANNEL);
    expect(result.decision.lineage.generationIndex).toBe(1);
    expect(result.decision.lineage.parentRefs).toEqual(['session-0']);
    expect(result.decision.lineage.producerVersion).toBe('1.2.3');
    expect(result.decision.lineage.provenance).toMatchObject({
      prompt: 'A slow pan across clouds',
      model: 'reigh-gen-v1',
      seed: 42,
      producerExtensionId: 'ext.generator',
    });
    expect(result.decision.lineage.steerHash).toMatch(/^fnv1a-[0-9a-f]{8}$/);
    expect(result.decision.lineage.provenanceTags).toEqual(
      expect.arrayContaining([
        'steering:supersede',
        'prior-samples:replace',
        'model:reigh-gen-v1',
        'seed:42',
        'producer:ext.generator',
      ]),
    );
  });

  it('forks non-hot params when the prior-sample policy is explicit fork', () => {
    const result = resolveLiveSteering({
      ...baseRequest(),
      changes: [
        {
          path: 'params.model',
          previousValue: 'reigh-gen-v1',
          nextValue: 'reigh-gen-v2',
        },
      ],
      priorSamplePolicy: 'fork',
    });

    expect(result.decision.kind).toBe('fork');
    expect(result.canActivateLiveDelivery).toBe(true);
    expect(result.nonHotChanges.map((change) => change.path)).toEqual(['params.model']);
    expect(result.decision.replacementChannelId).toBeUndefined();
    expect(result.decision.lineage.generationIndex).toBe(1);
    expect(result.decision.lineage.provenanceTags).toEqual(
      expect.arrayContaining(['steering:fork', 'prior-samples:fork']),
    );
  });

  it('rejects invalid hot changes that would silently retain prior samples', () => {
    const result = resolveLiveSteering({
      ...baseRequest(),
      priorSamplePolicy: 'retain',
    });

    expect(result.decision.kind).toBe('reject');
    expect(result.canActivateLiveDelivery).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'live/steering-invalid-prior-sample-policy')).toBe(true);
  });

  it('rejects unsupported params with explicit diagnostics instead of fallback hotness', () => {
    const result = resolveLiveSteering({
      ...baseRequest(),
      changes: [
        {
          path: 'params.unknown',
          previousValue: 'a',
          nextValue: 'b',
        },
      ],
    });

    expect(result.decision.kind).toBe('reject');
    expect(result.canActivateLiveDelivery).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'live/steering-unsupported-param')).toBe(true);
  });

  it('blocks live delivery when provenance is incomplete', () => {
    const result = resolveLiveSteering({
      ...baseRequest(),
      provenance: {
        prompt: '',
        model: 'reigh-gen-v1',
        seed: 42,
      },
    });

    expect(result.decision.kind).toBe('reject');
    expect(result.canActivateLiveDelivery).toBe(false);
    expect(result.diagnostics.some((d) => d.code === 'live/steering-incomplete-provenance')).toBe(true);
  });

  it('changes the steer hash when prompt/model/seed provenance changes', () => {
    const first = resolveLiveSteering(baseRequest());
    const second = resolveLiveSteering({
      ...baseRequest(),
      provenance: {
        ...baseRequest().provenance,
        seed: 43,
      },
    });

    expect(first.decision.lineage.steerHash).not.toBe(second.decision.lineage.steerHash);
  });
});

describe('evaluateGenerationSessionLiveDeliveryGate', () => {
  it('blocks Step 15 activation when no explicit decision exists', () => {
    const gate = evaluateGenerationSessionLiveDeliveryGate(undefined);

    expect(gate.canActivate).toBe(false);
    expect(gate.diagnostics.some((d) => d.code === 'live/steering-missing-decision')).toBe(true);
  });

  it('blocks Step 15 activation when decision lineage omits required metadata', () => {
    const incompleteDecision: SteeringDecision = {
      kind: 'supersede',
      sessionId: 'session-1',
      lineage: {
        generationIndex: 1,
        steerHash: '',
        parentRefs: [],
        producerVersion: '',
        provenance: { prompt: '', model: '', seed: '' },
      },
    };
    const gate = evaluateGenerationSessionLiveDeliveryGate(incompleteDecision);

    expect(gate.canActivate).toBe(false);
    expect(gate.diagnostics.some((d) => d.code === 'live/steering-missing-hash')).toBe(true);
    expect(gate.diagnostics.some((d) => d.code === 'live/steering-incomplete-provenance')).toBe(true);
  });
});
