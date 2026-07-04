import { describe, expect, it } from 'vitest';
import {
  convertEventTableToGraphOperations,
  type TimingMapResolver,
  type ValueSchemaNormalizer,
} from '@/tools/video-editor/runtime/liveEventConversion.ts';
import {
  hashCaptureBody,
  validateDeterministicCapture,
} from '@/tools/video-editor/runtime/deterministicCapture.ts';
import type {
  CaptureEventTableV1,
  DeterministicCapture,
  DeterministicCaptureProvenance,
} from '@/tools/video-editor/runtime/deterministicCapture.ts';

function validProvenance(
  overrides: Partial<DeterministicCaptureProvenance> = {},
): DeterministicCaptureProvenance {
  return {
    capturedAt: '2026-07-04T00:00:00.000Z',
    producerExtensionId: 'ext.test',
    producerVersion: '1.0.0',
    sessionId: 'session-1',
    ...overrides,
  };
}

function eventCapture(
  table: CaptureEventTableV1,
): DeterministicCapture {
  return {
    captureId: 'cap-event-1',
    profile: 'event',
    provenance: validProvenance(),
    contentHash: '',
    routeConstraints: ['preview'],
    determinism: 'deterministic',
    body: table,
  };
}

const identityTimingResolver: TimingMapResolver = {
  resolveEventTime(event) {
    return { ok: true, mappedTime: event.time };
  },
};

const clipParamNormalizer: ValueSchemaNormalizer = {
  normalizeEvent(event) {
    if (typeof event.value !== 'number') {
      return {
        ok: false,
        diagnostic: {
          severity: 'error',
          code: 'test/invalid-value',
          message: 'Expected numeric value for clip param conversion.',
          detail: { eventId: event.eventId, value: event.value },
        },
      };
    }

    const targetPath = event.targetPath.startsWith('params.')
      ? event.targetPath
      : `params.${event.targetPath}`;

    return {
      ok: true,
      normalized: {
        clipId: 'clip-1',
        paramName: targetPath,
        targetPath,
        value: event.value,
        interpolation: event.interpolation,
      },
    };
  },
};

async function validatedEventRef(table: CaptureEventTableV1) {
  const capture = eventCapture(table);
  capture.contentHash = await hashCaptureBody(capture.body);
  const validation = await validateDeterministicCapture(capture);
  expect(validation.valid).toBe(true);
  expect(validation.ref).not.toBeNull();
  return {
    capture,
    captureRef: validation.ref!,
  };
}

describe('convertEventTableToGraphOperations', () => {
  it.each([
    {
      policy: 'replace' as const,
      expectedEventIds: ['evt-2'],
      blockedEventIds: ['evt-1'],
    },
    {
      policy: 'merge-first-wins' as const,
      expectedEventIds: ['evt-1'],
      blockedEventIds: ['evt-2'],
    },
    {
      policy: 'merge-last-wins' as const,
      expectedEventIds: ['evt-2'],
      blockedEventIds: ['evt-1'],
    },
    {
      policy: 'reject' as const,
      expectedEventIds: [],
      blockedEventIds: ['evt-1', 'evt-2'],
    },
  ])('applies $policy collisions before emitting operations', async ({
    policy,
    expectedEventIds,
    blockedEventIds,
  }) => {
    const { capture, captureRef } = await validatedEventRef({
      profile: 'event',
      defaultCollisionPolicy: policy,
      events: [
        {
          eventId: 'evt-1',
          time: 1,
          targetPath: 'params.opacity',
          value: 0.2,
          interpolation: 'linear',
        },
        {
          eventId: 'evt-2',
          time: 1,
          targetPath: 'params.opacity',
          value: 0.8,
          interpolation: 'hold',
        },
      ],
    });

    const result = convertEventTableToGraphOperations({
      capture,
      captureRef,
      timingResolver: identityTimingResolver,
      valueNormalizer: clipParamNormalizer,
    });

    expect(result.operations).toHaveLength(expectedEventIds.length);
    expect(result.operations.map((operation) => operation.kind)).toEqual(
      expectedEventIds.map(() => 'keyframe.add'),
    );
    expect(result.operations.map((operation) => operation.metadata?.eventId)).toEqual(expectedEventIds);
    expect(result.details.filter((detail) => detail.operationKind === 'blocked').map((detail) => detail.eventId))
      .toEqual(blockedEventIds);

    for (const operation of result.operations) {
      expect(operation.metadata).toMatchObject({
        captureRef: captureRef.captureId,
        provenanceHash: captureRef.provenanceHash,
        collisionPolicy: policy,
        targetPath: 'params.opacity',
      });
    }
  });

  it('preserves per-event detail and leaves timeline state and sidecars untouched', async () => {
    const timelineState = {
      clips: [{ id: 'clip-1', keyframes: { opacity: [{ time: 0, value: 0.1, interpolation: 'linear' }] } }],
    };
    const sidecars = {
      captures: {
        'cap-event-1': { bodyPath: '/tmp/capture-1.json' },
      },
    };
    const timelineSnapshot = structuredClone(timelineState);
    const sidecarSnapshot = structuredClone(sidecars);
    const { capture, captureRef } = await validatedEventRef({
      profile: 'event',
      defaultCollisionPolicy: 'replace',
      events: [
        {
          eventId: 'evt-1',
          time: 0,
          targetPath: 'params.opacity',
          value: 0.25,
          interpolation: 'linear',
        },
        {
          eventId: 'evt-2',
          time: 2,
          targetPath: 'params.opacity',
          value: 0.75,
          interpolation: 'hold',
        },
      ],
    });

    const result = convertEventTableToGraphOperations({
      capture,
      captureRef,
      timingResolver: identityTimingResolver,
      valueNormalizer: clipParamNormalizer,
      timelineState,
      sidecars,
    });

    expect(result.operations).toHaveLength(2);
    expect(result.details).toEqual([
      expect.objectContaining({
        eventId: 'evt-1',
        targetPath: 'params.opacity',
        mappedTime: 0,
        normalizedValue: 0.25,
        interpolation: 'linear',
        collisionPolicy: 'replace',
        captureRef: captureRef.captureId,
        provenanceHash: captureRef.provenanceHash,
        operationKind: 'keyframe.add',
      }),
      expect.objectContaining({
        eventId: 'evt-2',
        targetPath: 'params.opacity',
        mappedTime: 2,
        normalizedValue: 0.75,
        interpolation: 'hold',
        collisionPolicy: 'replace',
        captureRef: captureRef.captureId,
        provenanceHash: captureRef.provenanceHash,
        operationKind: 'keyframe.add',
      }),
    ]);
    expect(timelineState).toEqual(timelineSnapshot);
    expect(sidecars).toEqual(sidecarSnapshot);
  });

  it('blocks timing-map and value-schema failures before emitting operations', async () => {
    const { capture, captureRef } = await validatedEventRef({
      profile: 'event',
      defaultCollisionPolicy: 'replace',
      events: [
        {
          eventId: 'evt-bad-time',
          time: 1,
          targetPath: 'params.opacity',
          value: 0.5,
          interpolation: 'linear',
        },
        {
          eventId: 'evt-bad-value',
          time: 2,
          targetPath: 'params.opacity',
          value: 'wrong-type',
          interpolation: 'linear',
        },
      ],
    });

    const result = convertEventTableToGraphOperations({
      capture,
      captureRef,
      timingResolver: {
        resolveEventTime(event) {
          if (event.eventId === 'evt-bad-time') {
            return {
              ok: false,
              diagnostic: {
                severity: 'error',
                code: 'test/invalid-time',
                message: 'Mapped time is not deterministic.',
                detail: { eventId: event.eventId },
              },
            };
          }
          return { ok: true, mappedTime: event.time };
        },
      },
      valueNormalizer: clipParamNormalizer,
    });

    expect(result.operations).toEqual([]);
    expect(result.details).toEqual([
      expect.objectContaining({
        eventId: 'evt-bad-time',
        operationKind: 'blocked',
        diagnostics: [expect.objectContaining({ code: 'test/invalid-time' })],
      }),
      expect.objectContaining({
        eventId: 'evt-bad-value',
        operationKind: 'blocked',
        diagnostics: [expect.objectContaining({ code: 'test/invalid-value' })],
      }),
    ]);
  });
});
