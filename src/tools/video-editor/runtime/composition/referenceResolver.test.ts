import { describe, expect, it } from 'vitest';
import type { ContributionRef, ReferenceState } from '@reigh/editor-sdk';
import {
  resolveCompositionReferences,
  resolveCompositionReferenceState,
  resolveReferenceStateFromEntries,
} from '@/tools/video-editor/runtime/composition/referenceResolver.ts';
import type { ContributionIndex, ContributionIndexEntry } from '@/tools/video-editor/runtime/extensionSurface.ts';

const ref = (contributionId: string): ContributionRef => ({
  kind: 'shader',
  extensionId: 'com.example.shader',
  contributionId,
});

function indexEntry(
  contributionId: string,
  overrides: Partial<ContributionIndexEntry> = {},
): ContributionIndexEntry {
  const scopedKey = `shader:com.example.shader:${contributionId}`;
  return {
    scopedKey,
    kind: 'shader',
    extensionId: 'com.example.shader',
    contributionId,
    status: overrides.status ?? 'active',
    packageState: overrides.packageState,
    diagnostics: overrides.diagnostics ?? [],
    duplicateOrdinal: overrides.duplicateOrdinal ?? 0,
    projectionEligible: overrides.projectionEligible ?? true,
    projection: overrides.projection ?? {
      duplicateOrdinal: overrides.duplicateOrdinal ?? 0,
      eligible: overrides.projectionEligible ?? true,
      projected: true,
      source: 'descriptor-array',
    },
    renderId: overrides.renderId,
    routeFit: overrides.routeFit,
    resolutionPolicy: overrides.resolutionPolicy,
  };
}

function contributionIndex(
  entriesByContributionId: Readonly<Record<string, readonly ContributionIndexEntry[] | undefined>>,
): ContributionIndex {
  const index: Record<string, readonly ContributionIndexEntry[]> = {};
  for (const [contributionId, entries] of Object.entries(entriesByContributionId)) {
    if (!entries) {
      continue;
    }
    index[`shader:com.example.shader:${contributionId}`] = entries;
  }
  return index;
}

describe('referenceResolver', () => {
  it('resolves all 10 composition reference states distinctly', () => {
    const states: Array<{
      readonly state: ReferenceState;
      readonly contributionId: string;
      readonly entries?: readonly ContributionIndexEntry[];
    }> = [
      {
        state: 'resolved',
        contributionId: 'resolved',
        entries: [indexEntry('resolved')],
      },
      {
        state: 'missing',
        contributionId: 'missing',
        entries: undefined,
      },
      {
        state: 'disabled',
        contributionId: 'disabled',
        entries: [indexEntry('disabled', { status: 'disabled', packageState: 'disabled-by-user' })],
      },
      {
        state: 'inactive-reserved',
        contributionId: 'inactive',
        entries: [indexEntry('inactive', { status: 'inactive-reserved' })],
      },
      {
        state: 'invalid-package',
        contributionId: 'invalid',
        entries: [indexEntry('invalid', { status: 'invalid', packageState: 'invalid' })],
      },
      {
        state: 'duplicate',
        contributionId: 'duplicate',
        entries: [
          indexEntry('duplicate', {
            duplicateOrdinal: 0,
            projection: {
              duplicateOrdinal: 0,
              eligible: true,
              projected: true,
              source: 'descriptor-array',
            },
          }),
          indexEntry('duplicate', {
            duplicateOrdinal: 1,
            projectionEligible: false,
            projection: {
              duplicateOrdinal: 1,
              eligible: false,
              projected: false,
              source: 'preserved-record',
            },
            resolutionPolicy: {
              kind: 'exact-duplicate',
              strategy: 'first-wins-projection',
              winnerScopedKey: 'shader:com.example.shader:duplicate',
              winnerDuplicateOrdinal: 0,
            },
          }),
        ],
      },
      {
        state: 'settings-error',
        contributionId: 'settings',
        entries: [indexEntry('settings', { status: 'disabled', packageState: 'settings-error' })],
      },
      {
        state: 'runtime-error',
        contributionId: 'runtime',
        entries: [indexEntry('runtime', { status: 'disabled', packageState: 'runtime-error' })],
      },
      {
        state: 'version-incompatible',
        contributionId: 'incompatible',
        entries: [indexEntry('incompatible', { status: 'disabled', packageState: 'incompatible' })],
      },
      {
        state: 'unknown',
        contributionId: 'unknown',
        entries: [indexEntry('unknown', { status: 'mystery' as ContributionIndexEntry['status'] })],
      },
    ];

    const index = contributionIndex(
      Object.fromEntries(states.map(({ contributionId, entries }) => [contributionId, entries])),
    );

    for (const testCase of states) {
      expect(resolveCompositionReferenceState(ref(testCase.contributionId), index)).toBe(testCase.state);
    }
  });

  it('applies locked precedence with package failures before inactive-reserved before resolved', () => {
    expect(resolveReferenceStateFromEntries([
      indexEntry('settings-first', { status: 'inactive-reserved' }),
      indexEntry('settings-first', { status: 'disabled', packageState: 'settings-error' }),
    ])).toBe('settings-error');

    expect(resolveReferenceStateFromEntries([
      indexEntry('inactive-before-resolved', { status: 'active' }),
      indexEntry('inactive-before-resolved', { status: 'inactive-reserved' }),
    ])).toBe('inactive-reserved');

    expect(resolveReferenceStateFromEntries([
      indexEntry('duplicate-before-resolved', { status: 'active' }),
      indexEntry('duplicate-before-resolved', {
        duplicateOrdinal: 1,
        projectionEligible: false,
        projection: {
          duplicateOrdinal: 1,
          eligible: false,
          projected: false,
          source: 'preserved-record',
        },
        resolutionPolicy: {
          kind: 'exact-duplicate',
          strategy: 'first-wins-projection',
          winnerScopedKey: 'shader:com.example.shader:duplicate-before-resolved',
          winnerDuplicateOrdinal: 0,
        },
      }),
    ])).toBe('duplicate');
  });

  it('defines missing only when there are zero scoped candidates', () => {
    expect(resolveReferenceStateFromEntries(undefined)).toBe('missing');
    expect(resolveReferenceStateFromEntries([])).toBe('missing');
    expect(resolveReferenceStateFromEntries([
      indexEntry('still-not-missing', { status: 'inactive-reserved' }),
    ])).toBe('inactive-reserved');
    expect(resolveReferenceStateFromEntries([
      indexEntry('disabled-not-missing', { status: 'disabled', packageState: 'disabled-by-user' }),
    ])).toBe('disabled');
  });

  it('emits canonical composition diagnostics for non-resolved refs used by graph edges', () => {
    const result = resolveCompositionReferences([
      {
        ref: ref('missing'),
        nodeId: 'clip:clip-1',
        scope: 'clip',
        shaderId: 'shader.clipMissing',
      },
      {
        ref: ref('missing'),
        nodeId: 'clip:clip-2',
        scope: 'clip',
        shaderId: 'shader.clipMissing',
      },
      {
        ref: ref('resolved'),
        nodeId: 'clip:clip-3',
        scope: 'clip',
        shaderId: 'shader.clipResolved',
      },
      {
        ref: ref('disabled'),
        nodeId: 'timeline-postprocess',
        scope: 'postprocess',
        shaderId: 'shader.postDisabled',
      },
    ], contributionIndex({
      resolved: [indexEntry('resolved', { status: 'active' })],
      disabled: [indexEntry('disabled', { status: 'disabled', packageState: 'disabled-by-user' })],
    }));

    expect(result.referenceStates).toEqual([
      {
        refKey: 'shader:com.example.shader:missing',
        state: 'missing',
        nodeIds: ['clip:clip-1', 'clip:clip-2'],
      },
      {
        refKey: 'shader:com.example.shader:resolved',
        state: 'resolved',
        nodeIds: ['clip:clip-3'],
      },
      {
        refKey: 'shader:com.example.shader:disabled',
        state: 'disabled',
        nodeIds: ['timeline-postprocess'],
      },
    ]);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        code: 'composition/missing-ref',
        severity: 'warning',
        extensionId: 'com.example.shader',
        contributionId: 'missing',
        detail: expect.objectContaining({
          nodeId: 'clip:clip-1',
          refKey: 'shader:com.example.shader:missing',
          refState: 'missing',
          scope: 'clip',
          extensionId: 'com.example.shader',
          contributionId: 'missing',
          shaderId: 'shader.clipMissing',
        }),
      }),
      expect.objectContaining({
        code: 'composition/missing-ref',
        severity: 'warning',
        detail: expect.objectContaining({
          nodeId: 'clip:clip-2',
          refKey: 'shader:com.example.shader:missing',
        }),
      }),
      expect.objectContaining({
        code: 'composition/disabled-ref',
        severity: 'error',
        extensionId: 'com.example.shader',
        contributionId: 'disabled',
        detail: expect.objectContaining({
          nodeId: 'timeline-postprocess',
          refKey: 'shader:com.example.shader:disabled',
          refState: 'disabled',
          scope: 'postprocess',
          shaderId: 'shader.postDisabled',
        }),
      }),
    ]);

    expect(result.byRefKey['shader:com.example.shader:resolved']).toEqual({
      ref: ref('resolved'),
      refKey: 'shader:com.example.shader:resolved',
      state: 'resolved',
      nodeIds: ['clip:clip-3'],
      diagnostics: [],
    });
  });
});
