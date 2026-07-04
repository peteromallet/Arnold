import { describe, expect, it } from 'vitest';
import {
  isKnownCaptureProfileV1,
  isValidCollisionPolicy,
  isValidRouteConstraint,
  createRejection,
  validateContentHash,
  validateProvenance,
  validateProfile,
  validateRouteConstraints,
  validateEventTable,
  validateMotionCurve,
  validateSeedTable,
  validateScalarTable,
  validateBodyByProfile,
  hashCaptureBody,
  verifyCaptureContentHash,
  validateDeterministicCapture,
  DETERMINISTIC_CAPTURE_PROFILES_V1,
  CAPTURE_COLLISION_POLICIES,
  DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS,
  DETERMINISTIC_CAPTURE_REJECTION_RULES,
} from '@/tools/video-editor/runtime/deterministicCapture';
import type {
  DeterministicCapture,
  DeterministicCaptureProvenance,
  DeterministicCaptureRejection,
  DeterministicCaptureTableV1,
  CaptureSeedTableV1,
  CaptureEventTableV1,
  CaptureScalarTableV1,
  CaptureStructuredMotionCurveV1,
  DeterministicCaptureValidationResult,
} from '@/tools/video-editor/runtime/deterministicCapture';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function validSeedCapture(overrides: Partial<DeterministicCapture> = {}): DeterministicCapture {
  const body: CaptureSeedTableV1 = {
    profile: 'seed',
    seed: 42,
    label: 'test seed',
  };
  return {
    captureId: 'cap-seed-1',
    profile: 'seed',
    provenance: validProvenance(),
    contentHash: '',
    routeConstraints: ['preview'],
    determinism: 'deterministic',
    body,
    ...overrides,
  };
}

function validEventCapture(overrides: Partial<DeterministicCapture> = {}): DeterministicCapture {
  const body: CaptureEventTableV1 = {
    profile: 'event',
    events: [
      {
        eventId: 'evt-1',
        time: 0,
        targetPath: 'params.opacity',
        value: 1,
        interpolation: 'linear',
      },
      {
        eventId: 'evt-2',
        time: 2,
        targetPath: 'params.opacity',
        value: 0,
        interpolation: 'linear',
      },
    ],
    defaultCollisionPolicy: 'replace',
  };
  return {
    captureId: 'cap-event-1',
    profile: 'event',
    provenance: validProvenance(),
    contentHash: '',
    routeConstraints: ['preview', 'browser-export'],
    determinism: 'deterministic',
    body,
    ...overrides,
  };
}

function validScalarCapture(overrides: Partial<DeterministicCapture> = {}): DeterministicCapture {
  const body: CaptureScalarTableV1 = {
    profile: 'scalar',
    entries: [
      { targetPath: 'params.brightness', value: 0.8 },
      { targetPath: 'params.contrast', value: 1.2 },
    ],
  };
  return {
    captureId: 'cap-scalar-1',
    profile: 'scalar',
    provenance: validProvenance(),
    contentHash: '',
    routeConstraints: ['worker-export'],
    determinism: 'deterministic',
    body,
    ...overrides,
  };
}

function validMotionCurveCapture(
  overrides: Partial<DeterministicCapture> = {},
): DeterministicCapture {
  const body: CaptureStructuredMotionCurveV1 = {
    profile: 'structured-motion-curve',
    targetPath: 'params.zoom',
    keyframes: [
      { time: 0, value: 1, interpolation: 'linear' },
      { time: 1, value: 1.5 },
      { time: 2, value: 2, interpolation: 'hold' },
    ],
    defaultInterpolation: 'linear',
  };
  return {
    captureId: 'cap-curve-1',
    profile: 'structured-motion-curve',
    provenance: validProvenance(),
    contentHash: '',
    routeConstraints: ['sidecar-export'],
    determinism: 'deterministic',
    body,
    ...overrides,
  };
}

/**
 * Build a valid capture, compute its SHA-256 content hash, and return the
 * capture with the hash set.
 */
async function validCapture(
  overrides: Partial<DeterministicCapture> = {},
): Promise<DeterministicCapture> {
  const capture = validSeedCapture(overrides);
  capture.contentHash = await hashCaptureBody(capture.body);
  return capture;
}

// ---------------------------------------------------------------------------
// Vocabulary checks
// ---------------------------------------------------------------------------

describe('locked vocabularies', () => {
  it('DETERMINISTIC_CAPTURE_PROFILES_V1 contains exactly the four frozen profiles', () => {
    expect(DETERMINISTIC_CAPTURE_PROFILES_V1).toEqual([
      'seed',
      'event',
      'scalar',
      'structured-motion-curve',
    ]);
    expect(Object.isFrozen(DETERMINISTIC_CAPTURE_PROFILES_V1)).toBe(true);
  });

  it('CAPTURE_COLLISION_POLICIES contains exactly the four allowed policies', () => {
    expect(CAPTURE_COLLISION_POLICIES).toEqual([
      'replace',
      'merge-first-wins',
      'merge-last-wins',
      'reject',
    ]);
    expect(Object.isFrozen(CAPTURE_COLLISION_POLICIES)).toBe(true);
  });

  it('DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS contains the four route constraints', () => {
    expect(DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS).toEqual([
      'preview',
      'browser-export',
      'worker-export',
      'sidecar-export',
    ]);
    expect(Object.isFrozen(DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS)).toBe(true);
  });

  it('DETERMINISTIC_CAPTURE_REJECTION_RULES contains all eight rules', () => {
    expect(DETERMINISTIC_CAPTURE_REJECTION_RULES).toEqual([
      'missing-provenance',
      'bad-content-hash',
      'unsupported-profile',
      'unsupported-event-type',
      'unsupported-interpolation',
      'bad-route-constraint',
      'deferred-profile',
      'malformed-value-ref',
    ]);
    expect(Object.isFrozen(DETERMINISTIC_CAPTURE_REJECTION_RULES)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// isKnownCaptureProfileV1
// ---------------------------------------------------------------------------

describe('isKnownCaptureProfileV1', () => {
  it('accepts all four frozen V1 profiles', () => {
    for (const profile of DETERMINISTIC_CAPTURE_PROFILES_V1) {
      expect(isKnownCaptureProfileV1(profile)).toBe(true);
    }
  });

  it('rejects deferred / unknown profiles', () => {
    expect(isKnownCaptureProfileV1('anti-scope')).toBe(false);
    expect(isKnownCaptureProfileV1('v2-experimental')).toBe(false);
    expect(isKnownCaptureProfileV1('')).toBe(false);
    expect(isKnownCaptureProfileV1('UNKNOWN')).toBe(false);
  });

  it('narrows the type correctly', () => {
    const value: string = 'seed';
    if (isKnownCaptureProfileV1(value)) {
      // Type-level check: value should be narrowed to DeterministicCaptureProfileV1
      const _profile: 'seed' | 'event' | 'scalar' | 'structured-motion-curve' = value;
      expect(_profile).toBe('seed');
    }
  });
});

// ---------------------------------------------------------------------------
// isValidCollisionPolicy
// ---------------------------------------------------------------------------

describe('isValidCollisionPolicy', () => {
  it('accepts all four policies', () => {
    for (const policy of CAPTURE_COLLISION_POLICIES) {
      expect(isValidCollisionPolicy(policy)).toBe(true);
    }
  });

  it('rejects unknown policies', () => {
    expect(isValidCollisionPolicy('first-wins')).toBe(false);
    expect(isValidCollisionPolicy('')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isValidRouteConstraint
// ---------------------------------------------------------------------------

describe('isValidRouteConstraint', () => {
  it('accepts all four route constraints', () => {
    for (const constraint of DETERMINISTIC_CAPTURE_ROUTE_CONSTRAINTS) {
      expect(isValidRouteConstraint(constraint)).toBe(true);
    }
  });

  it('rejects unknown constraints', () => {
    expect(isValidRouteConstraint('cloud-export')).toBe(false);
    expect(isValidRouteConstraint('')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// createRejection
// ---------------------------------------------------------------------------

describe('createRejection', () => {
  it('returns a properly shaped rejection', () => {
    const rejection = createRejection('missing-provenance', 'Test message', { key: 'val' });
    expect(rejection).toEqual({
      rule: 'missing-provenance',
      message: 'Test message',
      detail: { key: 'val' },
    });
  });

  it('works without optional detail', () => {
    const rejection = createRejection('bad-content-hash', 'No detail');
    expect(rejection).toEqual({
      rule: 'bad-content-hash',
      message: 'No detail',
      detail: undefined,
    });
  });
});

// ---------------------------------------------------------------------------
// validateProvenance
// ---------------------------------------------------------------------------

describe('validateProvenance', () => {
  it('accepts provenance with capturedAt', () => {
    const result = validateProvenance(validProvenance());
    expect(result).toBeNull();
  });

  it('rejects missing capturedAt', () => {
    const result = validateProvenance({ capturedAt: '' });
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('missing-provenance');
    expect(result!.message).toContain('capturedAt');
  });

  it('rejects provenance with empty capturedAt string', () => {
    const result = validateProvenance({ capturedAt: '' });
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('missing-provenance');
  });
});

// ---------------------------------------------------------------------------
// validateProfile
// ---------------------------------------------------------------------------

describe('validateProfile', () => {
  it('accepts all four frozen V1 profiles', () => {
    for (const profile of DETERMINISTIC_CAPTURE_PROFILES_V1) {
      expect(validateProfile(profile)).toBeNull();
    }
  });

  it('rejects unsupported profiles (deferred / anti-scope)', () => {
    const result = validateProfile('anti-scope');
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-profile');
    expect(result!.message).toContain('anti-scope');
    expect(result!.detail).toMatchObject({
      profile: 'anti-scope',
      supported: DETERMINISTIC_CAPTURE_PROFILES_V1,
    });
  });

  it('rejects empty string profile', () => {
    const result = validateProfile('');
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-profile');
  });

  it('rejects unknown future profile', () => {
    const result = validateProfile('quantum-random-v2');
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-profile');
  });
});

// ---------------------------------------------------------------------------
// validateRouteConstraints
// ---------------------------------------------------------------------------

describe('validateRouteConstraints', () => {
  it('accepts valid single constraint', () => {
    expect(validateRouteConstraints(['preview'])).toBeNull();
  });

  it('accepts multiple valid constraints', () => {
    expect(validateRouteConstraints(['preview', 'browser-export', 'worker-export'])).toBeNull();
  });

  it('rejects unknown constraint', () => {
    const result = validateRouteConstraints(['preview', 'unknown-route']);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-route-constraint');
    expect(result!.message).toContain('unknown-route');
  });

  it('rejects empty constraints array', () => {
    const result = validateRouteConstraints([]);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-route-constraint');
    expect(result!.message).toContain('no route constraints');
  });
});

// ---------------------------------------------------------------------------
// validateContentHash (pre-computed hash)
// ---------------------------------------------------------------------------

describe('validateContentHash', () => {
  it('accepts matching content hash', () => {
    const capture = validSeedCapture({ contentHash: 'abcd1234' });
    const result = validateContentHash(capture, 'abcd1234');
    expect(result).toBeNull();
  });

  it('rejects missing content hash', () => {
    const capture = validSeedCapture({ contentHash: '' });
    const result = validateContentHash(capture, 'any-hash');
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-content-hash');
    expect(result!.message).toContain('missing');
  });

  it('rejects mismatched content hash', () => {
    const capture = validSeedCapture({ contentHash: 'expected-hash' });
    const result = validateContentHash(capture, 'different-hash');
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-content-hash');
    expect(result!.detail).toMatchObject({
      expected: 'expected-hash',
      actual: 'different-hash',
    });
  });
});

// ---------------------------------------------------------------------------
// hashCaptureBody (SHA-256)
// ---------------------------------------------------------------------------

describe('hashCaptureBody', () => {
  it('returns a 64-character hex string', async () => {
    const body: DeterministicCaptureTableV1 = {
      profile: 'seed',
      seed: 42,
    };
    const hash = await hashCaptureBody(body);
    expect(hash).toHaveLength(64);
    expect(/^[0-9a-f]{64}$/.test(hash)).toBe(true);
  });

  it('produces deterministic output for same input', async () => {
    const body: DeterministicCaptureTableV1 = {
      profile: 'seed',
      seed: 42,
    };
    const a = await hashCaptureBody(body);
    const b = await hashCaptureBody(body);
    expect(a).toBe(b);
  });

  it('produces different hashes for different bodies', async () => {
    const bodyA: DeterministicCaptureTableV1 = {
      profile: 'seed',
      seed: 42,
    };
    const bodyB: DeterministicCaptureTableV1 = {
      profile: 'seed',
      seed: 99,
    };
    const a = await hashCaptureBody(bodyA);
    const b = await hashCaptureBody(bodyB);
    expect(a).not.toBe(b);
  });

  it('is stable regardless of key insertion order', async () => {
    // Construct two semantically identical bodies with different key order
    const bodyA = { profile: 'seed' as const, seed: 42, label: 'test' };
    const bodyB = { label: 'test', seed: 42, profile: 'seed' as const };
    const hashA = await hashCaptureBody(bodyA as CaptureSeedTableV1);
    const hashB = await hashCaptureBody(bodyB as CaptureSeedTableV1);
    expect(hashA).toBe(hashB);
  });

  it('handles event table bodies', async () => {
    const body: CaptureEventTableV1 = {
      profile: 'event',
      events: [{ eventId: 'e1', time: 0, targetPath: 'x', value: 1, interpolation: 'linear' }],
      defaultCollisionPolicy: 'replace',
    };
    const hash = await hashCaptureBody(body);
    expect(hash).toHaveLength(64);
  });

  it('handles motion curve bodies', async () => {
    const body: CaptureStructuredMotionCurveV1 = {
      profile: 'structured-motion-curve',
      targetPath: 'params.x',
      keyframes: [{ time: 0, value: 0 }],
      defaultInterpolation: 'linear',
    };
    const hash = await hashCaptureBody(body);
    expect(hash).toHaveLength(64);
  });
});

// ---------------------------------------------------------------------------
// verifyCaptureContentHash (async SHA-256 verification)
// ---------------------------------------------------------------------------

describe('verifyCaptureContentHash', () => {
  it('accepts a valid capture with correct content hash', async () => {
    const capture = validSeedCapture();
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await verifyCaptureContentHash(capture);
    expect(result).toBeNull();
  });

  it('rejects missing content hash', async () => {
    const capture = validSeedCapture({ contentHash: '' });
    const result = await verifyCaptureContentHash(capture);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-content-hash');
    expect(result!.message).toContain('missing');
  });

  it('rejects malformed hash (not hex)', async () => {
    const capture = validSeedCapture({ contentHash: 'not-a-sha256-hash!!!' });
    const result = await verifyCaptureContentHash(capture);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-content-hash');
    expect(result!.message).toContain('valid SHA-256 hex');
  });

  it('rejects wrong-length hash', async () => {
    const capture = validSeedCapture({ contentHash: 'abcdef' });
    const result = await verifyCaptureContentHash(capture);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-content-hash');
  });

  it('rejects mismatched hash', async () => {
    const capture = validSeedCapture();
    // Set a valid-looking hash that doesn't match the body
    capture.contentHash = 'a'.repeat(64);
    const result = await verifyCaptureContentHash(capture);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('bad-content-hash');
    expect(result!.detail).toMatchObject({
      expected: 'a'.repeat(64),
    });
  });
});

// ---------------------------------------------------------------------------
// validateSeedTable
// ---------------------------------------------------------------------------

describe('validateSeedTable', () => {
  it('accepts a valid seed table with number seed', () => {
    const table: CaptureSeedTableV1 = { profile: 'seed', seed: 42 };
    expect(validateSeedTable(table)).toBeNull();
  });

  it('accepts a valid seed table with string seed', () => {
    const table: CaptureSeedTableV1 = { profile: 'seed', seed: 'my-seed-value' };
    expect(validateSeedTable(table)).toBeNull();
  });

  it('rejects missing seed value', () => {
    const table = { profile: 'seed' } as unknown as CaptureSeedTableV1;
    const result = validateSeedTable(table);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-event-type');
  });

  it('rejects null seed value', () => {
    const table = { profile: 'seed', seed: null } as unknown as CaptureSeedTableV1;
    const result = validateSeedTable(table);
    expect(result).not.toBeNull();
  });

  it('rejects boolean seed value', () => {
    const table = { profile: 'seed', seed: true } as unknown as CaptureSeedTableV1;
    const result = validateSeedTable(table);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-event-type');
  });
});

// ---------------------------------------------------------------------------
// validateEventTable
// ---------------------------------------------------------------------------

describe('validateEventTable', () => {
  it('accepts a valid event table', () => {
    const table: CaptureEventTableV1 = {
      profile: 'event',
      events: [
        {
          eventId: 'evt-1',
          time: 0,
          targetPath: 'params.opacity',
          value: 1,
          interpolation: 'linear',
        },
      ],
      defaultCollisionPolicy: 'replace',
    };
    expect(validateEventTable(table)).toBeNull();
  });

  it('rejects empty events array', () => {
    const table: CaptureEventTableV1 = {
      profile: 'event',
      events: [],
      defaultCollisionPolicy: 'replace',
    };
    const result = validateEventTable(table);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-event-type');
  });

  it('rejects unknown default collision policy', () => {
    const table = {
      profile: 'event',
      events: [
        { eventId: 'evt-1', time: 0, targetPath: 'x', value: 1, interpolation: 'linear' as const },
      ],
      defaultCollisionPolicy: 'unknown-policy',
    } as unknown as CaptureEventTableV1;
    const result = validateEventTable(table);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-event-type');
  });

  it('rejects event missing eventId', () => {
    const table = {
      profile: 'event',
      events: [
        { time: 0, targetPath: 'x', value: 1, interpolation: 'linear' },
      ],
      defaultCollisionPolicy: 'replace',
    } as unknown as CaptureEventTableV1;
    const result = validateEventTable(table);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('eventId');
  });

  it('rejects event missing targetPath', () => {
    const table = {
      profile: 'event',
      events: [
        { eventId: 'evt-1', time: 0, value: 1, interpolation: 'linear' },
      ],
      defaultCollisionPolicy: 'replace',
    } as unknown as CaptureEventTableV1;
    const result = validateEventTable(table);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('targetPath');
  });

  it('rejects event with invalid time', () => {
    const table: CaptureEventTableV1 = {
      profile: 'event',
      events: [
        {
          eventId: 'evt-1',
          time: NaN,
          targetPath: 'x',
          value: 1,
          interpolation: 'linear',
        },
      ],
      defaultCollisionPolicy: 'replace',
    };
    const result = validateEventTable(table);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('invalid time');
  });

  it('rejects unknown event interpolation (unsupported)', () => {
    const table = {
      profile: 'event',
      events: [
        {
          eventId: 'evt-1',
          time: 0,
          targetPath: 'x',
          value: 1,
          interpolation: 'ease-in-out',
        },
      ],
      defaultCollisionPolicy: 'replace',
    } as unknown as CaptureEventTableV1;
    const result = validateEventTable(table);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-interpolation');
    expect(result!.message).toContain('ease-in-out');
  });

  it('rejects unknown per-event collision policy', () => {
    const table = {
      profile: 'event',
      events: [
        {
          eventId: 'evt-1',
          time: 0,
          targetPath: 'x',
          value: 1,
          interpolation: 'linear',
          collisionPolicy: 'bogus',
        },
      ],
      defaultCollisionPolicy: 'replace',
    } as unknown as CaptureEventTableV1;
    const result = validateEventTable(table);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('bogus');
  });
});

// ---------------------------------------------------------------------------
// validateMotionCurve
// ---------------------------------------------------------------------------

describe('validateMotionCurve', () => {
  it('accepts a valid motion curve', () => {
    const curve: CaptureStructuredMotionCurveV1 = {
      profile: 'structured-motion-curve',
      targetPath: 'params.x',
      keyframes: [
        { time: 0, value: 0, interpolation: 'linear' },
        { time: 1, value: 1 },
      ],
      defaultInterpolation: 'linear',
    };
    expect(validateMotionCurve(curve)).toBeNull();
  });

  it('rejects missing targetPath', () => {
    const curve = {
      profile: 'structured-motion-curve',
      targetPath: '',
      keyframes: [{ time: 0, value: 0 }],
      defaultInterpolation: 'linear',
    } as CaptureStructuredMotionCurveV1;
    const result = validateMotionCurve(curve);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('targetPath');
  });

  it('rejects unsupported default interpolation', () => {
    const curve = {
      profile: 'structured-motion-curve',
      targetPath: 'x',
      keyframes: [{ time: 0, value: 0 }],
      defaultInterpolation: 'bezier',
    } as unknown as CaptureStructuredMotionCurveV1;
    const result = validateMotionCurve(curve);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-interpolation');
  });

  it('rejects empty keyframes array', () => {
    const curve: CaptureStructuredMotionCurveV1 = {
      profile: 'structured-motion-curve',
      targetPath: 'x',
      keyframes: [],
      defaultInterpolation: 'linear',
    };
    const result = validateMotionCurve(curve);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('no keyframes');
  });

  it('rejects keyframe with invalid time', () => {
    const curve: CaptureStructuredMotionCurveV1 = {
      profile: 'structured-motion-curve',
      targetPath: 'x',
      keyframes: [{ time: Infinity, value: 0 }],
      defaultInterpolation: 'linear',
    };
    const result = validateMotionCurve(curve);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('invalid time');
  });

  it('rejects keyframe with invalid value', () => {
    const curve: CaptureStructuredMotionCurveV1 = {
      profile: 'structured-motion-curve',
      targetPath: 'x',
      keyframes: [{ time: 0, value: NaN }],
      defaultInterpolation: 'linear',
    };
    const result = validateMotionCurve(curve);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('invalid value');
  });

  it('rejects keyframe with unsupported interpolation override', () => {
    const curve = {
      profile: 'structured-motion-curve',
      targetPath: 'x',
      keyframes: [{ time: 0, value: 0, interpolation: 'cubic' }],
      defaultInterpolation: 'linear',
    } as unknown as CaptureStructuredMotionCurveV1;
    const result = validateMotionCurve(curve);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-interpolation');
  });
});

// ---------------------------------------------------------------------------
// validateScalarTable
// ---------------------------------------------------------------------------

describe('validateScalarTable', () => {
  it('accepts a valid scalar table', () => {
    const table: CaptureScalarTableV1 = {
      profile: 'scalar',
      entries: [
        { targetPath: 'params.brightness', value: 0.8 },
        { targetPath: 'params.contrast', value: 1.2 },
      ],
    };
    expect(validateScalarTable(table)).toBeNull();
  });

  it('accepts scalar entries with string and boolean values', () => {
    const table: CaptureScalarTableV1 = {
      profile: 'scalar',
      entries: [
        { targetPath: 'params.mode', value: 'dark' },
        { targetPath: 'params.enabled', value: true },
        { targetPath: 'params.opacity', value: 0.5 },
      ],
    };
    expect(validateScalarTable(table)).toBeNull();
  });

  it('rejects empty entries array', () => {
    const table: CaptureScalarTableV1 = {
      profile: 'scalar',
      entries: [],
    };
    const result = validateScalarTable(table);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-event-type');
  });

  it('rejects entry missing targetPath', () => {
    const table = {
      profile: 'scalar',
      entries: [{ value: 1 }],
    } as unknown as CaptureScalarTableV1;
    const result = validateScalarTable(table);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('targetPath');
  });

  it('rejects duplicate targetPaths', () => {
    const table: CaptureScalarTableV1 = {
      profile: 'scalar',
      entries: [
        { targetPath: 'params.x', value: 1 },
        { targetPath: 'params.x', value: 2 },
      ],
    };
    const result = validateScalarTable(table);
    expect(result).not.toBeNull();
    expect(result!.message).toContain('Duplicate targetPath');
  });

  it('rejects entry with null value', () => {
    const table = {
      profile: 'scalar',
      entries: [{ targetPath: 'x', value: null }],
    } as unknown as CaptureScalarTableV1;
    const result = validateScalarTable(table);
    expect(result).not.toBeNull();
  });

  it('rejects entry with object value', () => {
    const table = {
      profile: 'scalar',
      entries: [{ targetPath: 'x', value: { nested: true } }],
    } as unknown as CaptureScalarTableV1;
    const result = validateScalarTable(table);
    expect(result).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// validateBodyByProfile
// ---------------------------------------------------------------------------

describe('validateBodyByProfile', () => {
  it('routes seed bodies to validateSeedTable', () => {
    const body: CaptureSeedTableV1 = { profile: 'seed', seed: 42 };
    expect(validateBodyByProfile(body)).toBeNull();
  });

  it('routes event bodies to validateEventTable', () => {
    const body: CaptureEventTableV1 = {
      profile: 'event',
      events: [
        { eventId: 'e1', time: 0, targetPath: 'x', value: 1, interpolation: 'linear' },
      ],
      defaultCollisionPolicy: 'replace',
    };
    expect(validateBodyByProfile(body)).toBeNull();
  });

  it('routes scalar bodies to validateScalarTable', () => {
    const body: CaptureScalarTableV1 = {
      profile: 'scalar',
      entries: [{ targetPath: 'x', value: 1 }],
    };
    expect(validateBodyByProfile(body)).toBeNull();
  });

  it('routes motion curve bodies to validateMotionCurve', () => {
    const body: CaptureStructuredMotionCurveV1 = {
      profile: 'structured-motion-curve',
      targetPath: 'x',
      keyframes: [{ time: 0, value: 0 }],
      defaultInterpolation: 'linear',
    };
    expect(validateBodyByProfile(body)).toBeNull();
  });

  it('rejects unknown profile body', () => {
    const body = { profile: 'v2-future' } as unknown as DeterministicCaptureTableV1;
    const result = validateBodyByProfile(body);
    expect(result).not.toBeNull();
    expect(result!.rule).toBe('unsupported-profile');
    expect(result!.message).toContain('v2-future');
  });
});

// ---------------------------------------------------------------------------
// validateDeterministicCapture (comprehensive pipeline)
// ---------------------------------------------------------------------------

describe('validateDeterministicCapture', () => {
  it('accepts a fully valid seed capture', async () => {
    const capture = validSeedCapture();
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(true);
    expect(result.rejections).toHaveLength(0);
    expect(result.ref).not.toBeNull();
    expect(result.ref!.captureId).toBe('cap-seed-1');
    expect(result.ref!.profile).toBe('seed');
    expect(result.ref!.contentHash).toBe(capture.contentHash);
    expect(result.ref!.provenanceHash).toHaveLength(64);
    expect(result.ref!.routeConstraints).toEqual(['preview']);
    expect(result.ref!.determinism).toBe('deterministic');
  });

  it('accepts a fully valid event capture', async () => {
    const capture = validEventCapture();
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(true);
    expect(result.ref).not.toBeNull();
    expect(result.ref!.profile).toBe('event');
  });

  it('accepts a fully valid scalar capture', async () => {
    const capture = validScalarCapture();
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(true);
    expect(result.ref!.profile).toBe('scalar');
  });

  it('accepts a fully valid motion curve capture', async () => {
    const capture = validMotionCurveCapture();
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(true);
    expect(result.ref!.profile).toBe('structured-motion-curve');
  });

  it('rejects unsupported profile (deferred / anti-scope)', async () => {
    const capture = validSeedCapture({
      profile: 'anti-scope' as unknown as DeterministicCapture['profile'],
    });
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.ref).toBeNull();
    expect(result.rejections.some((r) => r.rule === 'unsupported-profile')).toBe(true);
    expect(result.rejections.some((r) => r.rule === 'deferred-profile')).toBe(true);
  });

  it('rejects missing provenance (capturedAt)', async () => {
    const capture = validSeedCapture({
      provenance: { capturedAt: '' },
    });
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'missing-provenance')).toBe(true);
  });

  it('rejects bad content hash', async () => {
    const capture = validSeedCapture({ contentHash: 'bad' });
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'bad-content-hash')).toBe(true);
  });

  it('rejects missing content hash', async () => {
    const capture = validSeedCapture({ contentHash: '' });
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'bad-content-hash')).toBe(true);
  });

  it('rejects bad route constraints', async () => {
    const capture = validSeedCapture({
      routeConstraints: ['unknown-route'],
    });
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'bad-route-constraint')).toBe(true);
  });

  it('rejects empty route constraints', async () => {
    const capture = validSeedCapture({ routeConstraints: [] });
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'bad-route-constraint')).toBe(true);
  });

  it('rejects unsupported interpolation in event table', async () => {
    const capture = validEventCapture({
      body: {
        profile: 'event',
        events: [
          {
            eventId: 'evt-1',
            time: 0,
            targetPath: 'x',
            value: 1,
            interpolation: 'bezier' as unknown as 'linear',
          },
        ],
        defaultCollisionPolicy: 'replace',
      } as unknown as DeterministicCaptureTableV1,
    });
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'unsupported-interpolation')).toBe(true);
  });

  it('rejects unknown event type / missing fields', async () => {
    const capture = validEventCapture({
      body: {
        profile: 'event',
        events: [],
        defaultCollisionPolicy: 'replace',
      } as CaptureEventTableV1,
    });
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'unsupported-event-type')).toBe(true);
  });

  it('rejects malformed seed table body', async () => {
    const capture = validSeedCapture({
      body: { profile: 'seed', seed: null } as unknown as CaptureSeedTableV1,
    });
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'unsupported-event-type')).toBe(true);
  });

  it('collects multiple rejections', async () => {
    const capture = validSeedCapture({
      contentHash: 'bad',
      routeConstraints: [],
    });
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.length).toBeGreaterThanOrEqual(2);
  });

  it('stops at profile rejection (does not continue to provenance/hash)', async () => {
    const capture = validSeedCapture({
      profile: 'future-v99' as unknown as DeterministicCapture['profile'],
      provenance: { capturedAt: '' }, // Also bad provenance
      contentHash: '', // Also bad hash
    });
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    // Should only have profile rejections, not provenance/hash (short-circuits)
    expect(result.rejections.every((r) =>
      r.rule === 'unsupported-profile' || r.rule === 'deferred-profile',
    )).toBe(true);
  });

  it('stops at provenance rejection (does not continue to hash)', async () => {
    const capture = validSeedCapture({
      provenance: { capturedAt: '' },
      contentHash: '', // Also bad hash
    });
    capture.contentHash = await hashCaptureBody(capture.body); // fix hash
    // But provenance is still bad
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(false);
    expect(result.rejections.some((r) => r.rule === 'missing-provenance')).toBe(true);
    expect(result.rejections.every((r) => r.rule === 'missing-provenance')).toBe(true);
  });

  it('produces a BakedValueRef with provenanceHash on success', async () => {
    const capture = validScalarCapture();
    capture.contentHash = await hashCaptureBody(capture.body);
    const result = await validateDeterministicCapture(capture);
    expect(result.valid).toBe(true);
    expect(result.ref!.provenanceHash).toHaveLength(64);
    expect(/^[0-9a-f]{64}$/.test(result.ref!.provenanceHash)).toBe(true);
  });
});
