/**
 * M3b: Deterministic Capture — host/editor-owned contracts and validators.
 *
 * This module defines the frozen V1 deterministic capture profiles, their
 * table shapes, and validation helpers. Concrete table bodies are host/editor-
 * owned and must NOT be re-exported through the public SDK. The public SDK
 * only gains the `deterministic-capture` bake-target discriminant.
 *
 * @module deterministicCapture
 * @milestone M3b
 */

import type {
  DeterministicCaptureProfileV1,
  DeterministicCaptureProvenance,
  DeterministicCaptureRouteConstraint,
  DeterministicCaptureRejectionRule,
  DeterministicCaptureRejection,
  DeterministicCapture,
  DeterministicCaptureTableV1,
  BakedValueRef,
  CaptureCollisionPolicy,
  CaptureSeedTableV1,
  CaptureEventTableV1,
  CaptureEventV1,
  CaptureScalarTableV1,
  CaptureScalarEntryV1,
  CaptureStructuredMotionCurveV1,
  CaptureCurveKeyframeV1,
} from '@/tools/video-editor/types';

// Re-export types for editor-internal consumers (NOT for the public SDK).
export type {
  DeterministicCaptureProfileV1,
  DeterministicCaptureProvenance,
  DeterministicCaptureRouteConstraint,
  DeterministicCaptureRejectionRule,
  DeterministicCaptureRejection,
  DeterministicCapture,
  DeterministicCaptureTableV1,
  BakedValueRef,
  CaptureCollisionPolicy,
  CaptureSeedTableV1,
  CaptureEventTableV1,
  CaptureEventV1,
  CaptureScalarTableV1,
  CaptureScalarEntryV1,
  CaptureStructuredMotionCurveV1,
  CaptureCurveKeyframeV1,
};

// ---------------------------------------------------------------------------
// Locked vocabularies
// ---------------------------------------------------------------------------

/** Frozen V1 profile discriminants. */
export const DETERMINISTIC_CAPTURE_PROFILES_V1: readonly DeterministicCaptureProfileV1[] = [
  'seed',
  'event',
  'scalar',
  'structured-motion-curve',
] as const;
Object.freeze(DETERMINISTIC_CAPTURE_PROFILES_V1);

/** Locked collision policy vocabulary. */
export const CAPTURE_COLLISION_POLICIES: readonly CaptureCollisionPolicy[] = [
  'replace',
  'merge-first-wins',
  'merge-last-wins',
  'reject',
] as const;
Object.freeze(CAPTURE_COLLISION_POLICIES);

/** Locked route constraint vocabulary (mirrors RenderRoute). */
export const DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS: readonly DeterministicCaptureRouteConstraint[] = [
  'preview',
  'browser-export',
  'worker-export',
  'sidecar-export',
] as const;
Object.freeze(DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS);

/** Locked rejection rule vocabulary. */
export const DETERMINISTIC_CAPTURE_REJECTION_RULES: readonly DeterministicCaptureRejectionRule[] = [
  'missing-provenance',
  'bad-content-hash',
  'unsupported-profile',
  'unsupported-event-type',
  'unsupported-interpolation',
  'bad-route-constraint',
  'deferred-profile',
  'malformed-value-ref',
] as const;
Object.freeze(DETERMINISTIC_CAPTURE_REJECTION_RULES);

// ---------------------------------------------------------------------------
// Validation helpers (scaffold for T3)
// ---------------------------------------------------------------------------

/**
 * Check whether a profile discriminant is a valid frozen V1 profile.
 * Deferred/unknown profiles are rejected.
 */
export function isKnownCaptureProfileV1(
  value: string,
): value is DeterministicCaptureProfileV1 {
  return (DETERMINISTIC_CAPTURE_PROFILES_V1 as readonly string[]).includes(value);
}

/**
 * Check whether a collision policy string is valid.
 */
export function isValidCollisionPolicy(
  value: string,
): value is CaptureCollisionPolicy {
  return (CAPTURE_COLLISION_POLICIES as readonly string[]).includes(value);
}

/**
 * Check whether a route constraint string is valid.
 */
export function isValidRouteConstraint(
  value: string,
): value is DeterministicCaptureRouteConstraint {
  return (DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS as readonly string[]).includes(value);
}

/**
 * Create a rejection diagnostic.
 */
export function createRejection(
  rule: DeterministicCaptureRejectionRule,
  message: string,
  detail?: Record<string, unknown>,
): DeterministicCaptureRejection {
  return { rule, message, detail };
}

/**
 * Verify that a capture's content hash matches a SHA-256 hash of its
 * serialized body. Returns a rejection if the hash is missing or mismatched.
 *
 * NOTE: Full SHA-256 hashing is implemented in T3. This scaffold accepts
 * a pre-computed hash for callers that hash externally.
 */
export function validateContentHash(
  capture: DeterministicCapture,
  actualBodyHash: string,
): DeterministicCaptureRejection | null {
  if (!capture.contentHash || capture.contentHash.length === 0) {
    return createRejection('bad-content-hash', 'Capture is missing a content hash.', {
      captureId: capture.captureId,
    });
  }

  if (capture.contentHash !== actualBodyHash) {
    return createRejection('bad-content-hash', 'Capture content hash does not match body.', {
      captureId: capture.captureId,
      expected: capture.contentHash,
      actual: actualBodyHash,
    });
  }

  return null;
}

/**
 * Validate that a capture has the minimum required provenance fields.
 */
export function validateProvenance(
  provenance: DeterministicCaptureProvenance,
): DeterministicCaptureRejection | null {
  if (!provenance.capturedAt || provenance.capturedAt.length === 0) {
    return createRejection('missing-provenance', 'Capture provenance is missing capturedAt timestamp.');
  }

  return null;
}

/**
 * Validate that a capture's profile is a known V1 profile (not deferred).
 */
export function validateProfile(
  profile: string,
): DeterministicCaptureRejection | null {
  if (!isKnownCaptureProfileV1(profile)) {
    return createRejection(
      'unsupported-profile',
      `Capture profile "${profile}" is not a supported V1 profile.`,
      { profile, supported: DETERMINISTIC_CAPTURE_PROFILES_V1 },
    );
  }

  return null;
}

/**
 * Validate that a capture's route constraints are all known.
 * Unknown constraints should block acceptance.
 */
export function validateRouteConstraints(
  constraints: string[],
): DeterministicCaptureRejection | null {
  for (const constraint of constraints) {
    if (!isValidRouteConstraint(constraint)) {
      return createRejection(
        'bad-route-constraint',
        `Capture route constraint "${constraint}" is not a known route.`,
        { constraint, supported: DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS },
      );
    }
  }

  if (constraints.length === 0) {
    return createRejection(
      'bad-route-constraint',
      'Capture has no route constraints.',
    );
  }

  return null;
}

/**
 * Validate that an event table's events have valid interpolation and no
 * unsupported event types. Full per-event schema validation lands in T3/T7.
 */
export function validateEventTable(
  table: CaptureEventTableV1,
): DeterministicCaptureRejection | null {
  if (!table.events || table.events.length === 0) {
    return createRejection(
      'unsupported-event-type',
      'Event table has no events.',
      { profile: table.profile },
    );
  }

  if (!isValidCollisionPolicy(table.defaultCollisionPolicy)) {
    return createRejection(
      'unsupported-event-type',
      `Event table has unknown default collision policy "${table.defaultCollisionPolicy}".`,
      { defaultCollisionPolicy: table.defaultCollisionPolicy },
    );
  }

  for (const event of table.events) {
    if (!event.eventId || event.eventId.length === 0) {
      return createRejection(
        'unsupported-event-type',
        'Event table entry is missing an eventId.',
        { event },
      );
    }

    if (!event.targetPath || event.targetPath.length === 0) {
      return createRejection(
        'unsupported-event-type',
        `Event "${event.eventId}" is missing a targetPath.`,
        { eventId: event.eventId },
      );
    }

    if (typeof event.time !== 'number' || !Number.isFinite(event.time)) {
      return createRejection(
        'unsupported-event-type',
        `Event "${event.eventId}" has an invalid time.`,
        { eventId: event.eventId, time: event.time },
      );
    }

    if (event.interpolation !== 'linear' && event.interpolation !== 'hold') {
      return createRejection(
        'unsupported-interpolation',
        `Event "${event.eventId}" has unsupported interpolation "${event.interpolation}".`,
        { eventId: event.eventId, interpolation: event.interpolation },
      );
    }

    if (event.collisionPolicy && !isValidCollisionPolicy(event.collisionPolicy)) {
      return createRejection(
        'unsupported-event-type',
        `Event "${event.eventId}" has unknown collision policy "${event.collisionPolicy}".`,
        { eventId: event.eventId, collisionPolicy: event.collisionPolicy },
      );
    }
  }

  return null;
}

/**
 * Validate that a structured motion curve's keyframes are well-formed.
 */
export function validateMotionCurve(
  curve: CaptureStructuredMotionCurveV1,
): DeterministicCaptureRejection | null {
  if (!curve.targetPath || curve.targetPath.length === 0) {
    return createRejection(
      'unsupported-interpolation',
      'Motion curve is missing a targetPath.',
    );
  }

  if (curve.defaultInterpolation !== 'linear' && curve.defaultInterpolation !== 'hold') {
    return createRejection(
      'unsupported-interpolation',
      `Motion curve has unsupported default interpolation "${curve.defaultInterpolation}".`,
      { defaultInterpolation: curve.defaultInterpolation },
    );
  }

  if (!curve.keyframes || curve.keyframes.length === 0) {
    return createRejection(
      'unsupported-interpolation',
      'Motion curve has no keyframes.',
      { targetPath: curve.targetPath },
    );
  }

  for (const kf of curve.keyframes) {
    if (typeof kf.time !== 'number' || !Number.isFinite(kf.time)) {
      return createRejection(
        'unsupported-interpolation',
        'Motion curve keyframe has an invalid time.',
        { keyframe: kf },
      );
    }

    if (typeof kf.value !== 'number' || !Number.isFinite(kf.value)) {
      return createRejection(
        'unsupported-interpolation',
        'Motion curve keyframe has an invalid value.',
        { keyframe: kf },
      );
    }

    if (kf.interpolation && kf.interpolation !== 'linear' && kf.interpolation !== 'hold') {
      return createRejection(
        'unsupported-interpolation',
        `Motion curve keyframe has unsupported interpolation "${kf.interpolation}".`,
        { keyframe: kf },
      );
    }
  }

  return null;
}

/**
 * Validate that a seed table is well-formed.
 */
export function validateSeedTable(
  table: CaptureSeedTableV1,
): DeterministicCaptureRejection | null {
  if (table.seed === undefined || table.seed === null) {
    return createRejection(
      'unsupported-event-type',
      'Seed table is missing a seed value.',
      { profile: table.profile },
    );
  }

  if (typeof table.seed !== 'string' && typeof table.seed !== 'number') {
    return createRejection(
      'unsupported-event-type',
      `Seed table has an invalid seed type "${typeof table.seed}".`,
      { seed: table.seed },
    );
  }

  return null;
}

/**
 * Validate that a scalar table is well-formed.
 */
export function validateScalarTable(
  table: CaptureScalarTableV1,
): DeterministicCaptureRejection | null {
  if (!table.entries || table.entries.length === 0) {
    return createRejection(
      'unsupported-event-type',
      'Scalar table has no entries.',
      { profile: table.profile },
    );
  }

  const seenPaths = new Set<string>();
  for (const entry of table.entries) {
    if (!entry.targetPath || entry.targetPath.length === 0) {
      return createRejection(
        'unsupported-event-type',
        'Scalar entry is missing a targetPath.',
        { entry },
      );
    }

    if (seenPaths.has(entry.targetPath)) {
      return createRejection(
        'unsupported-event-type',
        `Duplicate targetPath "${entry.targetPath}" in scalar table.`,
        { targetPath: entry.targetPath },
      );
    }
    seenPaths.add(entry.targetPath);

    if (
      entry.value === undefined ||
      entry.value === null ||
      (typeof entry.value !== 'number' &&
        typeof entry.value !== 'string' &&
        typeof entry.value !== 'boolean')
    ) {
      return createRejection(
        'unsupported-event-type',
        `Scalar entry "${entry.targetPath}" has an invalid value type "${typeof entry.value}".`,
        { targetPath: entry.targetPath, value: entry.value },
      );
    }
  }

  return null;
}

/**
 * Validate a capture body based on its profile discriminant.
 * Routes to the appropriate per-profile validator.
 */
export function validateBodyByProfile(
  body: DeterministicCaptureTableV1,
): DeterministicCaptureRejection | null {
  switch (body.profile) {
    case 'seed':
      return validateSeedTable(body);
    case 'event':
      return validateEventTable(body);
    case 'scalar':
      return validateScalarTable(body);
    case 'structured-motion-curve':
      return validateMotionCurve(body);
    default:
      return createRejection(
        'unsupported-profile',
        `Unknown capture profile "${(body as { profile: string }).profile}".`,
        { profile: (body as { profile: string }).profile },
      );
  }
}

// ---------------------------------------------------------------------------
// SHA-256 hashing (T3)
// ---------------------------------------------------------------------------

/**
 * Compute a stable SHA-256 hex digest of a capture's body for content-hash
 * verification using the Web Crypto API.
 *
 * Serialization is deterministic: keys are sorted so JSON.stringify produces
 * a stable byte sequence regardless of insertion order.
 */
export async function hashCaptureBody(body: DeterministicCaptureTableV1): Promise<string> {
  const serialized = JSON.stringify(body, Object.keys(body).sort());
  const data = new TextEncoder().encode(serialized);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Verify that a capture's content hash matches a freshly-computed SHA-256
 * hash of its serialized body. Returns a rejection if the hash is missing,
 * malformed, or mismatched.
 */
export async function verifyCaptureContentHash(
  capture: DeterministicCapture,
): Promise<DeterministicCaptureRejection | null> {
  if (!capture.contentHash || capture.contentHash.length === 0) {
    return createRejection('bad-content-hash', 'Capture is missing a content hash.', {
      captureId: capture.captureId,
    });
  }

  if (!/^[0-9a-f]{64}$/.test(capture.contentHash)) {
    return createRejection('bad-content-hash', 'Capture content hash is not a valid SHA-256 hex digest.', {
      captureId: capture.captureId,
      contentHash: capture.contentHash,
    });
  }

  const actualHash = await hashCaptureBody(capture.body);

  if (capture.contentHash !== actualHash) {
    return createRejection('bad-content-hash', 'Capture content hash does not match body.', {
      captureId: capture.captureId,
      expected: capture.contentHash,
      actual: actualHash,
    });
  }

  return null;
}

// ---------------------------------------------------------------------------
// Comprehensive validation (T3)
// ---------------------------------------------------------------------------

/**
 * Result of a full deterministic capture validation.
 */
export interface DeterministicCaptureValidationResult {
  /** Whether the capture passed all validation checks. */
  valid: boolean;
  /** All rejections found during validation. */
  rejections: DeterministicCaptureRejection[];
  /** The BakedValueRef produced on success (null if validation failed). */
  ref: BakedValueRef | null;
}

/**
 * Run the full deterministic capture validation pipeline.
 *
 * Checks, in order:
 * 1. Profile discriminant — must be a known frozen V1 profile (deferred/unknown → reject).
 * 2. Provenance — must include at least `capturedAt`.
 * 3. Route constraints — must be non-empty with known constraint values.
 * 4. Content hash — must be present, valid SHA-256 hex, and match the serialized body.
 * 5. Body schema — routed to the per-profile table validator.
 *
 * On success, a {@link BakedValueRef} is returned with the capture's provenance hash,
 * route constraints, and determinism posture.
 */
export async function validateDeterministicCapture(
  capture: DeterministicCapture,
): Promise<DeterministicCaptureValidationResult> {
  const rejections: DeterministicCaptureRejection[] = [];

  // 1. Profile check — deferred/anti-scope profiles must be rejected.
  const profileRejection = validateProfile(capture.profile);
  if (profileRejection) {
    rejections.push(profileRejection);
    // For deferred profiles, also emit the specific deferred-profile rejection.
    if (!isKnownCaptureProfileV1(capture.profile)) {
      rejections.push(
        createRejection(
          'deferred-profile',
          `Capture profile "${capture.profile}" is a deferred or anti-scope profile and cannot be accepted.`,
          { profile: capture.profile },
        ),
      );
    }
    return { valid: false, rejections, ref: null };
  }

  // 2. Provenance check.
  const provenanceRejection = validateProvenance(capture.provenance);
  if (provenanceRejection) {
    rejections.push(provenanceRejection);
    return { valid: false, rejections, ref: null };
  }

  // 3. Route constraint check.
  const routeRejection = validateRouteConstraints(capture.routeConstraints);
  if (routeRejection) {
    rejections.push(routeRejection);
  }

  // 4. Content hash check (async — requires SHA-256).
  const hashRejection = await verifyCaptureContentHash(capture);
  if (hashRejection) {
    rejections.push(hashRejection);
  }

  // 5. Body schema check.
  const bodyRejection = validateBodyByProfile(capture.body);
  if (bodyRejection) {
    rejections.push(bodyRejection);
  }

  if (rejections.length > 0) {
    return { valid: false, rejections, ref: null };
  }

  // Compute provenance hash for the BakedValueRef.
  const provenanceSerialized = JSON.stringify(
    capture.provenance,
    Object.keys(capture.provenance).sort(),
  );
  const provenanceData = new TextEncoder().encode(provenanceSerialized);
  const provenanceHashBuffer = await crypto.subtle.digest('SHA-256', provenanceData);
  const provenanceHashArray = Array.from(new Uint8Array(provenanceHashBuffer));
  const provenanceHash = provenanceHashArray
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  const ref: BakedValueRef = {
    captureId: capture.captureId,
    profile: capture.profile,
    contentHash: capture.contentHash,
    provenanceHash,
    routeConstraints: capture.routeConstraints,
    valuePath: '',
    determinism: capture.determinism,
  };

  return { valid: true, rejections: [], ref };
}
