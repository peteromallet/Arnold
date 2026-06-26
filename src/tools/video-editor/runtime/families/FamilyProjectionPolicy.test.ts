/**
 * Family projection policy tests.
 *
 * @module families/FamilyProjectionPolicy.test
 */

import { describe, it, expect } from 'vitest';

import {
  evaluateProjectionPolicy,
  getContributionRuntimeStatus,
  type ProjectionStatus,
} from './FamilyProjectionPolicy';
import { VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY } from './familyAdapterRegistry';

import type { FamilyAdapterRegistry } from '@/sdk/core/families/familyAdapter';

describe('evaluateProjectionPolicy', () => {
  it('treats adapter-owned delegated families as surfacing and bridged', () => {
    const status = evaluateProjectionPolicy(
      'parser',
      VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
    );
    expect(status.kind).toBe('parser');
    expect(status.adapterOwned).toBe(true);
    expect(status.shouldSurface).toBe(true);
    expect(status.isDelegated).toBe(true);
    expect(status.legacyBridgeStatus).toBeNull();
    expect(status.executionMaturity).toBe('delegated');
  });

  it('treats real compatibility adapters as bridged', () => {
    const status = evaluateProjectionPolicy(
      'slot',
      VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
    );
    expect(status.adapterOwned).toBe(true);
    expect(status.shouldSurface).toBe(true);
    expect(status.isDelegated).toBe(false);
    expect(status.legacyBridgeStatus).toBeNull();
    expect(status.executionMaturity).toBe('public-supported');
  });

  it('treats null-registered agent as delegated-but-projectable', () => {
    const status = evaluateProjectionPolicy(
      'agent',
      VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
    );
    expect(status.adapterOwned).toBe(true);
    expect(status.shouldSurface).toBe(true);
    expect(status.isDelegated).toBe(true);
    expect(status.executionMaturity).toBe('delegated');
  });

  it('falls back to SDK legacy bridge status when no registry is provided', () => {
    const status = evaluateProjectionPolicy('outputFormat');
    expect(status.adapterOwned).toBe(false);
    expect(status.shouldSurface).toBe(true);
    expect(status.isDelegated).toBe(true);
    expect(status.legacyBridgeStatus).toBe('M6');
  });

  it('returns non-surfacing status for unknown/absent kinds', () => {
    const status = evaluateProjectionPolicy(
      'nonexistent-kind' as any,
      VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
    );
    expect(status.shouldSurface).toBe(false);
    expect(status.adapterOwned).toBe(false);
  });

  it('freezes every returned status object', () => {
    const status = evaluateProjectionPolicy(
      'effect',
      VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
    );
    expect(Object.isFrozen(status)).toBe(true);
  });

  it('uses adapter manifest maturity for registry-owned families', () => {
    const registry: FamilyAdapterRegistry = new Map([
      [
        'customKind',
        {
          kind: 'customKind',
          classification: 'real',
          manifest: {
            adapterId: 'custom',
            kind: 'customKind',
            version: '1.0.0',
            maturity: 'host-integrated',
          },
          normalize: () => ({ descriptors: [] }),
          buildConformanceReport: () =>
            ({
              kind: 'customKind',
              declarationMaturity: 'documented',
              executionMaturity: 'host-integrated',
            } as any),
        },
      ],
    ]);

    const status = evaluateProjectionPolicy('customKind', registry);
    expect(status.executionMaturity).toBe('host-integrated');
    expect(status.shouldSurface).toBe(true);
    expect(status.isDelegated).toBe(false);
  });
});

describe('getContributionRuntimeStatus', () => {
  it('returns legacy-compatible shape for bridged families', () => {
    const status = getContributionRuntimeStatus(
      'slot',
      VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
    );
    expect(status.legacyBridgeStatus).toBeNull();
    expect(status.isDelegated).toBe(false);
  });

  it('returns legacy-compatible shape for delegated families', () => {
    const status = getContributionRuntimeStatus(
      'effect',
      VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY,
    );
    expect(status.legacyBridgeStatus).toBeNull();
    expect(status.isDelegated).toBe(true);
  });
});
