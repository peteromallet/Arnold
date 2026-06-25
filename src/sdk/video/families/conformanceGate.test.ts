/**
 * Conformance CLI gate tests — prove that release mode rejects incoherent
 * cross-axis maturity combinations.
 *
 * These tests directly exercise `checkCrossAxisCoherence` (the same function
 * the CLI uses in `scripts/quality/check-extension-family-conformance.mjs`)
 * across every declaration × execution maturity combination, plus
 * `buildConformanceReport` gap detection, to prove the gate correctly
 * identifies all incoherent families.
 *
 * Coverage:
 *   1. Full cross-axis matrix (3 declaration × 5 execution = 15 combinations)
 *   2. Specific release-mode rejection scenarios
 *   3. `buildConformanceReport` emits coherence-violation gaps for incoherent families
 *   4. `isFullyConformant` returns false when coherence is violated
 *   5. Coherent families produce no coherence-violation gaps
 *   6. `checkFamilyCoherence` matches `checkCrossAxisCoherence` for any Definition
 */

import { describe, expect, it } from 'vitest';

import {
  checkCrossAxisCoherence,
  checkFamilyCoherence,
  buildConformanceReport,
  computeGaps,
  isFullyConformant,
} from '@/sdk/core/families/conformance';

import type {
  DeclarationMaturity,
  ExecutionMaturity,
  FamilyDefinition,
  FamilyRequirementChecklist,
} from '@/sdk/core/families/maturity';

// ---------------------------------------------------------------------------
// Fixture builder
// ---------------------------------------------------------------------------

const EMPTY_REQUIREMENTS: FamilyRequirementChecklist = {
  manifestSchema: undefined,
  normalizedDescriptor: undefined,
  registrationApi: undefined,
  lifecycleCleanup: undefined,
  diagnostics: undefined,
  hostCapabilityProjection: undefined,
  uiIntegration: undefined,
  persistencePosture: undefined,
  examples: undefined,
  tests: undefined,
};

function makeFixture(overrides: Partial<FamilyDefinition> = {}): FamilyDefinition {
  return {
    kind: 'testFamily',
    declarationMaturity: 'typed',
    executionMaturity: 'absent',
    requiresTrustedCode: false,
    manifestSchemaDefinition: 'TestFamilyContribution',
    sdkModules: ['test/module'],
    hostAdapter: null,
    requirements: { ...EMPTY_REQUIREMENTS },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Full cross-axis matrix
// ---------------------------------------------------------------------------

describe('Cross-axis coherence — full matrix (release-mode gate)', () => {
  const allDeclarationLevels: DeclarationMaturity[] = [
    'typed',
    'schema-backed',
    'documented',
  ];
  const allExecutionLevels: ExecutionMaturity[] = [
    'absent',
    'delegated',
    'runtime-bridged',
    'host-integrated',
    'public-supported',
  ];

  /**
   * Incoherent combinations per `checkCrossAxisCoherence` rules:
   * - runtime-bridged+  → declaration at least schema-backed
   * - host-integrated+  → declaration at least documented
   * - public-supported  → declaration must be documented (caught by rule 2)
   */
  const incoherentPairs = new Set([
    'typed::runtime-bridged',
    'typed::host-integrated',
    'typed::public-supported',
    'schema-backed::host-integrated',
    'schema-backed::public-supported',
  ]);

  for (const dec of allDeclarationLevels) {
    for (const exec of allExecutionLevels) {
      const key = `${dec}::${exec}`;
      const expectCoherent = !incoherentPairs.has(key);

      it(`${expectCoherent ? 'accepts' : 'rejects'} ${dec} + ${exec}`, () => {
        const result = checkCrossAxisCoherence(dec, exec);
        expect(result.coherent).toBe(expectCoherent);

        if (!expectCoherent) {
          expect(result.violations.length).toBeGreaterThan(0);
        } else {
          expect(result.violations.length).toBe(0);
        }
      });
    }
  }
});

// ---------------------------------------------------------------------------
// Incoherent combinations — specific violation messages
// ---------------------------------------------------------------------------

describe('Cross-axis coherence — specific violation messages', () => {
  it('rejects typed + runtime-bridged with schema-backed requirement', () => {
    const result = checkCrossAxisCoherence('typed', 'runtime-bridged');
    expect(result.coherent).toBe(false);
    expect(
      result.violations.some((v) =>
        v.includes('Execution maturity "runtime-bridged" requires declaration maturity at least "schema-backed"'),
      ),
    ).toBe(true);
  });

  it('rejects typed + host-integrated with both schema-backed and documented requirements', () => {
    const result = checkCrossAxisCoherence('typed', 'host-integrated');
    expect(result.coherent).toBe(false);
    expect(
      result.violations.some((v) => v.includes('at least "schema-backed"')),
    ).toBe(true);
    expect(
      result.violations.some((v) => v.includes('at least "documented"')),
    ).toBe(true);
  });

  it('rejects typed + public-supported with both requirements', () => {
    const result = checkCrossAxisCoherence('typed', 'public-supported');
    expect(result.coherent).toBe(false);
    expect(
      result.violations.some((v) => v.includes('at least "schema-backed"')),
    ).toBe(true);
    expect(
      result.violations.some((v) => v.includes('at least "documented"')),
    ).toBe(true);
  });

  it('rejects schema-backed + host-integrated with documented requirement', () => {
    const result = checkCrossAxisCoherence('schema-backed', 'host-integrated');
    expect(result.coherent).toBe(false);
    expect(
      result.violations.some((v) =>
        v.includes('Execution maturity "host-integrated" requires declaration maturity at least "documented"'),
      ),
    ).toBe(true);
  });

  it('rejects schema-backed + public-supported with documented requirement', () => {
    const result = checkCrossAxisCoherence('schema-backed', 'public-supported');
    expect(result.coherent).toBe(false);
    expect(
      result.violations.some((v) =>
        v.includes('Execution maturity "public-supported" requires declaration maturity "documented"'),
      ),
    ).toBe(true);
  });

  it('deduplicates violations when multiple rules catch the same issue', () => {
    // typed + public-supported triggers rule 1, 2, and 3 — all violations
    // but "requires documented" appears in both rule 2 and rule 3
    const result = checkCrossAxisCoherence('typed', 'public-supported');
    // Count unique violations — rule 2 and 3 produce the same message
    const uniqueMessages = new Set(result.violations);
    expect(uniqueMessages.size).toBe(result.violations.length);
  });
});

// ---------------------------------------------------------------------------
// Coherent combinations pass without violations
// ---------------------------------------------------------------------------

describe('Cross-axis coherence — coherent combinations', () => {
  const coherentCases: [DeclarationMaturity, ExecutionMaturity][] = [
    ['typed', 'absent'],
    ['typed', 'delegated'],
    ['schema-backed', 'absent'],
    ['schema-backed', 'delegated'],
    ['schema-backed', 'runtime-bridged'],
    ['documented', 'absent'],
    ['documented', 'delegated'],
    ['documented', 'runtime-bridged'],
    ['documented', 'host-integrated'],
    ['documented', 'public-supported'],
  ];

  for (const [dec, exec] of coherentCases) {
    it(`${dec} + ${exec} passes with zero violations`, () => {
      const result = checkCrossAxisCoherence(dec, exec);
      expect(result.coherent).toBe(true);
      expect(result.violations).toEqual([]);
    });
  }
});

// ---------------------------------------------------------------------------
// Conformance report gap detection for incoherent families
// ---------------------------------------------------------------------------

describe('buildConformanceReport — coherence gaps for incoherent families', () => {
  it('emits coherence-violation gap for typed + runtime-bridged', () => {
    const def = makeFixture({
      declarationMaturity: 'typed',
      executionMaturity: 'runtime-bridged',
    });
    const report = buildConformanceReport(def);
    expect(report.coherent).toBe(false);

    const coherenceGaps = report.gaps.filter(
      (g) => g.category === 'coherence-violation',
    );
    expect(coherenceGaps.length).toBeGreaterThan(0);
    expect(
      coherenceGaps.some((g) =>
        g.message.includes('at least "schema-backed"'),
      ),
    ).toBe(true);
  });

  it('emits coherence-violation gap for typed + host-integrated', () => {
    const def = makeFixture({
      declarationMaturity: 'typed',
      executionMaturity: 'host-integrated',
    });
    const report = buildConformanceReport(def);
    expect(report.coherent).toBe(false);

    const coherenceGaps = report.gaps.filter(
      (g) => g.category === 'coherence-violation',
    );
    expect(coherenceGaps.length).toBeGreaterThanOrEqual(2); // at least 2 violations
  });

  it('emits coherence-violation gap for schema-backed + host-integrated', () => {
    const def = makeFixture({
      declarationMaturity: 'schema-backed',
      executionMaturity: 'host-integrated',
    });
    const report = buildConformanceReport(def);
    expect(report.coherent).toBe(false);

    const coherenceGaps = report.gaps.filter(
      (g) => g.category === 'coherence-violation',
    );
    expect(coherenceGaps.length).toBe(1);
    expect(coherenceGaps[0].message).toContain('at least "documented"');
  });

  it('emits coherence-violation gap for schema-backed + public-supported', () => {
    const def = makeFixture({
      declarationMaturity: 'schema-backed',
      executionMaturity: 'public-supported',
    });
    const report = buildConformanceReport(def);
    expect(report.coherent).toBe(false);

    const coherenceGaps = report.gaps.filter(
      (g) => g.category === 'coherence-violation',
    );
    expect(coherenceGaps.length).toBeGreaterThanOrEqual(1);
    expect(
      coherenceGaps.some((g) => g.message.includes('documented')),
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Coherent families produce no coherence-violation gaps
// ---------------------------------------------------------------------------

describe('buildConformanceReport — no coherence gaps for coherent families', () => {
  it('typed + absent has no coherence-violation gaps', () => {
    const def = makeFixture({
      declarationMaturity: 'typed',
      executionMaturity: 'absent',
    });
    const report = buildConformanceReport(def);
    expect(report.coherent).toBe(true);
    expect(
      report.gaps.filter((g) => g.category === 'coherence-violation'),
    ).toEqual([]);
  });

  it('schema-backed + runtime-bridged has no coherence-violation gaps', () => {
    const def = makeFixture({
      declarationMaturity: 'schema-backed',
      executionMaturity: 'runtime-bridged',
      hostAdapter: 'src/host/adapters/test',
    });
    const report = buildConformanceReport(def);
    expect(report.coherent).toBe(true);
    expect(
      report.gaps.filter((g) => g.category === 'coherence-violation'),
    ).toEqual([]);
  });

  it('documented + public-supported has no coherence-violation gaps', () => {
    const def = makeFixture({
      declarationMaturity: 'documented',
      executionMaturity: 'public-supported',
      hostAdapter: 'src/host/adapters/test',
      requirements: {
        ...EMPTY_REQUIREMENTS,
        manifestSchema: true,
      },
    });
    const report = buildConformanceReport(def);
    expect(report.coherent).toBe(true);
    expect(
      report.gaps.filter((g) => g.category === 'coherence-violation'),
    ).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// isFullyConformant rejects incoherent families
// ---------------------------------------------------------------------------

describe('isFullyConformant — rejects incoherent families', () => {
  it('returns false for typed + runtime-bridged', () => {
    const def = makeFixture({
      declarationMaturity: 'typed',
      executionMaturity: 'runtime-bridged',
    });
    expect(isFullyConformant(def)).toBe(false);
  });

  it('returns false for schema-backed + host-integrated', () => {
    const def = makeFixture({
      declarationMaturity: 'schema-backed',
      executionMaturity: 'host-integrated',
    });
    expect(isFullyConformant(def)).toBe(false);
  });

  it('returns false for typed + public-supported', () => {
    const def = makeFixture({
      declarationMaturity: 'typed',
      executionMaturity: 'public-supported',
    });
    expect(isFullyConformant(def)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// checkFamilyCoherence matches checkCrossAxisCoherence
// ---------------------------------------------------------------------------

describe('checkFamilyCoherence delegates to checkCrossAxisCoherence', () => {
  it('matches for an incoherent definition', () => {
    const def = makeFixture({
      kind: 'incoherentFamily',
      declarationMaturity: 'typed',
      executionMaturity: 'runtime-bridged',
    });
    const familyResult = checkFamilyCoherence(def);
    const directResult = checkCrossAxisCoherence(
      def.declarationMaturity,
      def.executionMaturity,
    );
    expect(familyResult.coherent).toBe(directResult.coherent);
    expect(familyResult.violations).toEqual(directResult.violations);
  });

  it('matches for a coherent definition', () => {
    const def = makeFixture({
      kind: 'coherentFamily',
      declarationMaturity: 'documented',
      executionMaturity: 'public-supported',
    });
    const familyResult = checkFamilyCoherence(def);
    const directResult = checkCrossAxisCoherence(
      def.declarationMaturity,
      def.executionMaturity,
    );
    expect(familyResult.coherent).toBe(directResult.coherent);
    expect(familyResult.violations).toEqual(directResult.violations);
  });
});

// ---------------------------------------------------------------------------
// computeGaps returns coherence-violation gaps for incoherent families
// ---------------------------------------------------------------------------

describe('computeGaps — includes coherence gaps', () => {
  it('returns coherence-violation gaps for typed + runtime-bridged', () => {
    const def = makeFixture({
      declarationMaturity: 'typed',
      executionMaturity: 'runtime-bridged',
    });
    const gaps = computeGaps(def);
    expect(gaps.filter((g) => g.category === 'coherence-violation').length).toBeGreaterThan(0);
  });

  it('returns no coherence-violation gaps for documented + runtime-bridged', () => {
    const def = makeFixture({
      declarationMaturity: 'documented',
      executionMaturity: 'runtime-bridged',
      hostAdapter: 'src/host/adapters/test',
    });
    const gaps = computeGaps(def);
    expect(gaps.filter((g) => g.category === 'coherence-violation')).toEqual([]);
  });
});
