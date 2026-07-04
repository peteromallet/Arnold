/**
 * M3b live event-table conversion.
 *
 * Converts validated deterministic event captures into graph-owned keyframe
 * operations. The converter is intentionally pure: it resolves timing and
 * target/value normalization through injected interfaces, applies collision
 * policy before emitting any operations, and never mutates timeline state,
 * sidecars, or the capture body.
 */

import type {
  BakedValueRef,
  CaptureCollisionPolicy,
  CaptureEventTableV1,
  CaptureEventV1,
  ClipKeyframe,
  DeterministicCapture,
  KeyframeInterpolation,
} from '@/tools/video-editor/types/index.ts';
import {
  validateEventTable,
} from '@/tools/video-editor/runtime/deterministicCapture.ts';
import type {
  GraphKeyframeAddOp,
} from '@/tools/video-editor/runtime/composition/patchPreview.ts';

export interface LiveEventConversionDiagnostic {
  readonly severity: 'error' | 'warning' | 'info';
  readonly code: string;
  readonly message: string;
  readonly detail?: Record<string, unknown>;
}

export interface TimingMapResolution {
  readonly ok: true;
  readonly mappedTime: number;
}

export interface TimingMapRejection {
  readonly ok: false;
  readonly diagnostic: LiveEventConversionDiagnostic;
}

export interface TimingMapResolver {
  resolveEventTime(
    event: CaptureEventV1,
    context: {
      readonly capture: DeterministicCapture;
      readonly captureRef: BakedValueRef;
      readonly eventIndex: number;
    },
  ): TimingMapResolution | TimingMapRejection;
}

export interface NormalizedEventValue {
  readonly clipId: string;
  readonly paramName: string;
  readonly targetPath: string;
  readonly value: ClipKeyframe['value'];
  readonly interpolation: KeyframeInterpolation;
}

export interface ValueNormalizationSuccess {
  readonly ok: true;
  readonly normalized: NormalizedEventValue;
}

export interface ValueNormalizationFailure {
  readonly ok: false;
  readonly diagnostic: LiveEventConversionDiagnostic;
}

export interface ValueSchemaNormalizer {
  normalizeEvent(
    event: CaptureEventV1,
    context: {
      readonly capture: DeterministicCapture;
      readonly captureRef: BakedValueRef;
      readonly eventIndex: number;
      readonly mappedTime: number;
    },
  ): ValueNormalizationSuccess | ValueNormalizationFailure;
}

export interface KeyframeCollisionResolution {
  readonly winner: PendingKeyframeCandidate | null;
  readonly rejectKey: boolean;
}

export interface KeyframeCollisionPolicyEngine {
  resolveCollision(
    existing: PendingKeyframeCandidate,
    incoming: PendingKeyframeCandidate,
  ): KeyframeCollisionResolution;
}

export interface LiveEventKeyframeDetail {
  readonly eventId: string;
  readonly targetPath: string;
  readonly mappedTime?: number;
  readonly normalizedValue?: ClipKeyframe['value'];
  readonly interpolation?: KeyframeInterpolation;
  readonly collisionPolicy: CaptureCollisionPolicy;
  readonly captureRef: string;
  readonly provenanceHash: string;
  readonly operationKind: GraphKeyframeAddOp['kind'] | 'blocked';
  readonly diagnostics: readonly LiveEventConversionDiagnostic[];
}

export interface LiveEventConversionResult {
  readonly operations: readonly GraphKeyframeAddOp[];
  readonly details: readonly LiveEventKeyframeDetail[];
  readonly diagnostics: readonly LiveEventConversionDiagnostic[];
}

export interface ConvertEventTableRequest {
  readonly capture: DeterministicCapture;
  readonly captureRef: BakedValueRef;
  readonly timingResolver: TimingMapResolver;
  readonly valueNormalizer: ValueSchemaNormalizer;
  readonly collisionPolicyEngine?: KeyframeCollisionPolicyEngine;
  /**
   * Opaque host state passed through for future callers. The converter must
   * never mutate it.
   */
  readonly timelineState?: unknown;
  /**
   * Opaque sidecar bundle passed through for future callers. The converter
   * must never mutate it.
   */
  readonly sidecars?: unknown;
}

type MutableLiveEventKeyframeDetail = {
  eventId: string;
  targetPath: string;
  mappedTime?: number;
  normalizedValue?: ClipKeyframe['value'];
  interpolation?: KeyframeInterpolation;
  collisionPolicy: CaptureCollisionPolicy;
  captureRef: string;
  provenanceHash: string;
  operationKind: GraphKeyframeAddOp['kind'] | 'blocked';
  diagnostics: LiveEventConversionDiagnostic[];
};

export interface PendingKeyframeCandidate {
  readonly key: string;
  readonly event: CaptureEventV1;
  readonly eventIndex: number;
  readonly collisionPolicy: CaptureCollisionPolicy;
  readonly operation: GraphKeyframeAddOp;
  readonly detail: MutableLiveEventKeyframeDetail;
}

const COLLISION_REJECTED_CODE = 'live-event/conversion-collision-rejected';

function collisionKey(targetPath: string, mappedTime: number): string {
  return `${targetPath}\u0000${mappedTime}`;
}

function detailDiagnostic(
  severity: LiveEventConversionDiagnostic['severity'],
  code: string,
  message: string,
  detail?: Record<string, unknown>,
): LiveEventConversionDiagnostic {
  return { severity, code, message, detail };
}

function freezeDetail(detail: MutableLiveEventKeyframeDetail): LiveEventKeyframeDetail {
  return Object.freeze({
    ...detail,
    diagnostics: Object.freeze(detail.diagnostics.map((diagnostic) => Object.freeze({
      ...diagnostic,
      ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
    }))),
  });
}

function blockCandidate(
  candidate: PendingKeyframeCandidate,
  diagnostic: LiveEventConversionDiagnostic,
): void {
  candidate.detail.operationKind = 'blocked';
  candidate.detail.diagnostics.push(diagnostic);
}

function winnerDetail(
  candidate: PendingKeyframeCandidate,
  diagnostic: LiveEventConversionDiagnostic,
): void {
  candidate.detail.diagnostics.push(diagnostic);
}

function createCollisionPolicyEngine(): KeyframeCollisionPolicyEngine {
  return {
    resolveCollision(existing, incoming) {
      const collisionDetail = {
        key: existing.key,
        targetPath: incoming.detail.targetPath,
        mappedTime: incoming.detail.mappedTime,
        existingEventId: existing.event.eventId,
        incomingEventId: incoming.event.eventId,
      };

      switch (incoming.collisionPolicy) {
        case 'replace': {
          blockCandidate(
            existing,
            detailDiagnostic(
              'warning',
              'live-event/conversion-collision-replaced',
              `Event "${incoming.event.eventId}" replaced colliding event "${existing.event.eventId}".`,
              collisionDetail,
            ),
          );
          winnerDetail(
            incoming,
            detailDiagnostic(
              'info',
              'live-event/conversion-collision-replace-winner',
              `Event "${incoming.event.eventId}" survived collision by replacement.`,
              collisionDetail,
            ),
          );
          return { winner: incoming, rejectKey: false };
        }
        case 'merge-first-wins': {
          blockCandidate(
            incoming,
            detailDiagnostic(
              'warning',
              'live-event/conversion-collision-merged-first-wins',
              `Event "${incoming.event.eventId}" was dropped because "${existing.event.eventId}" won the collision.`,
              collisionDetail,
            ),
          );
          winnerDetail(
            existing,
            detailDiagnostic(
              'info',
              'live-event/conversion-collision-first-wins-winner',
              `Event "${existing.event.eventId}" survived collision by first-wins merge.`,
              collisionDetail,
            ),
          );
          return { winner: existing, rejectKey: false };
        }
        case 'merge-last-wins': {
          blockCandidate(
            existing,
            detailDiagnostic(
              'warning',
              'live-event/conversion-collision-merged-last-wins',
              `Event "${existing.event.eventId}" was dropped because "${incoming.event.eventId}" won the collision.`,
              collisionDetail,
            ),
          );
          winnerDetail(
            incoming,
            detailDiagnostic(
              'info',
              'live-event/conversion-collision-last-wins-winner',
              `Event "${incoming.event.eventId}" survived collision by last-wins merge.`,
              collisionDetail,
            ),
          );
          return { winner: incoming, rejectKey: false };
        }
        case 'reject': {
          const existingDiagnostic = detailDiagnostic(
            'error',
            COLLISION_REJECTED_CODE,
            `Event "${existing.event.eventId}" was rejected because "${incoming.event.eventId}" collided at the same target/time.`,
            collisionDetail,
          );
          const incomingDiagnostic = detailDiagnostic(
            'error',
            COLLISION_REJECTED_CODE,
            `Event "${incoming.event.eventId}" was rejected because it collided with "${existing.event.eventId}" at the same target/time.`,
            collisionDetail,
          );
          blockCandidate(existing, existingDiagnostic);
          blockCandidate(incoming, incomingDiagnostic);
          return { winner: null, rejectKey: true };
        }
      }
    },
  };
}

function eventTableFromCapture(capture: DeterministicCapture): CaptureEventTableV1 | null {
  return capture.profile === 'event' && capture.body.profile === 'event'
    ? capture.body
    : null;
}

export function convertEventTableToGraphOperations(
  request: ConvertEventTableRequest,
): LiveEventConversionResult {
  const details: MutableLiveEventKeyframeDetail[] = [];
  const diagnostics: LiveEventConversionDiagnostic[] = [];
  const acceptedByKey = new Map<string, PendingKeyframeCandidate>();
  const rejectedKeys = new Set<string>();
  const collisionPolicyEngine = request.collisionPolicyEngine ?? createCollisionPolicyEngine();
  const table = eventTableFromCapture(request.capture);

  if (!table) {
    const diagnostic = detailDiagnostic(
      'error',
      'live-event/conversion-unsupported-profile',
      `Capture "${request.capture.captureId}" is not an event-table capture.`,
      {
        captureId: request.capture.captureId,
        profile: request.capture.profile,
      },
    );
    diagnostics.push(diagnostic);
    return { operations: Object.freeze([]), details: Object.freeze([]), diagnostics: Object.freeze(diagnostics) };
  }

  if (request.captureRef.profile !== 'event') {
    const diagnostic = detailDiagnostic(
      'error',
      'live-event/conversion-ref-profile-mismatch',
      `Capture ref for "${request.capture.captureId}" does not reference an event-table profile.`,
      {
        captureId: request.capture.captureId,
        refProfile: request.captureRef.profile,
      },
    );
    diagnostics.push(diagnostic);
    return { operations: Object.freeze([]), details: Object.freeze([]), diagnostics: Object.freeze(diagnostics) };
  }

  const validationRejection = validateEventTable(table);
  if (validationRejection) {
    const diagnostic = detailDiagnostic(
      'error',
      'live-event/conversion-invalid-event-table',
      validationRejection.message,
      validationRejection.detail,
    );
    diagnostics.push(diagnostic);
    return { operations: Object.freeze([]), details: Object.freeze([]), diagnostics: Object.freeze(diagnostics) };
  }

  for (const [eventIndex, event] of table.events.entries()) {
    const collisionPolicy = event.collisionPolicy ?? table.defaultCollisionPolicy;
    const baseDetail: MutableLiveEventKeyframeDetail = {
      eventId: event.eventId,
      targetPath: event.targetPath,
      collisionPolicy,
      captureRef: request.captureRef.captureId,
      provenanceHash: request.captureRef.provenanceHash,
      operationKind: 'blocked',
      diagnostics: [],
    };
    details.push(baseDetail);

    const timingResolution = request.timingResolver.resolveEventTime(event, {
      capture: request.capture,
      captureRef: request.captureRef,
      eventIndex,
    });
    if (!timingResolution.ok) {
      baseDetail.diagnostics.push(timingResolution.diagnostic);
      continue;
    }

    baseDetail.mappedTime = timingResolution.mappedTime;

    const normalizedValue = request.valueNormalizer.normalizeEvent(event, {
      capture: request.capture,
      captureRef: request.captureRef,
      eventIndex,
      mappedTime: timingResolution.mappedTime,
    });
    if (!normalizedValue.ok) {
      baseDetail.diagnostics.push(normalizedValue.diagnostic);
      continue;
    }

    baseDetail.targetPath = normalizedValue.normalized.targetPath;
    baseDetail.normalizedValue = normalizedValue.normalized.value;
    baseDetail.interpolation = normalizedValue.normalized.interpolation;

    const operation: GraphKeyframeAddOp = {
      kind: 'keyframe.add',
      clipId: normalizedValue.normalized.clipId,
      paramName: normalizedValue.normalized.paramName,
      keyframe: {
        time: timingResolution.mappedTime,
        value: normalizedValue.normalized.value,
        interpolation: normalizedValue.normalized.interpolation,
      },
      metadata: {
        captureRef: request.captureRef.captureId,
        eventId: event.eventId,
        provenanceHash: request.captureRef.provenanceHash,
        collisionPolicy,
        targetPath: normalizedValue.normalized.targetPath,
      },
    };

    const candidate: PendingKeyframeCandidate = {
      key: collisionKey(normalizedValue.normalized.targetPath, timingResolution.mappedTime),
      event,
      eventIndex,
      collisionPolicy,
      operation,
      detail: baseDetail,
    };

    if (rejectedKeys.has(candidate.key)) {
      const diagnostic = detailDiagnostic(
        'error',
        COLLISION_REJECTED_CODE,
        `Event "${event.eventId}" was rejected because its target/time collision was already marked reject.`,
        {
          key: candidate.key,
          targetPath: normalizedValue.normalized.targetPath,
          mappedTime: timingResolution.mappedTime,
        },
      );
      blockCandidate(candidate, diagnostic);
      continue;
    }

    const existing = acceptedByKey.get(candidate.key);
    if (!existing) {
      baseDetail.operationKind = 'keyframe.add';
      acceptedByKey.set(candidate.key, candidate);
      continue;
    }

    const resolution = collisionPolicyEngine.resolveCollision(existing, candidate);
    if (resolution.rejectKey) {
      acceptedByKey.delete(candidate.key);
      rejectedKeys.add(candidate.key);
    } else if (resolution.winner) {
      resolution.winner.detail.operationKind = 'keyframe.add';
      acceptedByKey.set(candidate.key, resolution.winner);
    }
  }

  const operations = Array.from(acceptedByKey.values())
    .sort((left, right) => {
      const timeDelta = left.operation.keyframe.time - right.operation.keyframe.time;
      return timeDelta !== 0 ? timeDelta : left.eventIndex - right.eventIndex;
    })
    .map((candidate) => Object.freeze({
      ...candidate.operation,
      keyframe: Object.freeze({ ...candidate.operation.keyframe }),
      ...(candidate.operation.metadata
        ? {
            metadata: Object.freeze({ ...candidate.operation.metadata }),
          }
        : {}),
    }) as GraphKeyframeAddOp);

  const combinedDiagnostics = [
    ...diagnostics,
    ...details.flatMap((detail) => detail.diagnostics),
  ];

  return {
    operations: Object.freeze(operations),
    details: Object.freeze(details.map(freezeDetail)),
    diagnostics: Object.freeze(combinedDiagnostics.map((diagnostic) => Object.freeze({
      ...diagnostic,
      ...(diagnostic.detail ? { detail: Object.freeze({ ...diagnostic.detail }) } : {}),
    }))),
  };
}
