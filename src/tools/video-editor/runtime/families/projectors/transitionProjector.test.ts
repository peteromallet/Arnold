/**
 * Transition projector — descriptor projection tests.
 *
 * Validates that `buildTransitionDescriptors` correctly normalizes
 * TransitionContribution entries, including M5 material slot declarations,
 * into frozen VideoEditorTransitionDescriptor objects.
 *
 * @module families/projectors/transitionProjector.test
 */

import { describe, it, expect } from 'vitest';

import { buildTransitionDescriptors } from './transitionProjector';
import type { CollectedContribution } from '../FamilyContributionSequence';
import type {
  TransitionContribution,
  TransitionMaterialSlotDeclaration,
} from '@reigh/editor-sdk';
import type { VideoEditorTransitionDescriptor } from '../../extensionSurface';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal CollectedContribution for a transition with a transitionId. */
function collectedTransition(
  overrides: Partial<TransitionContribution> & { transitionId: string },
  extensionId = 'test.ext',
): CollectedContribution {
  const contribution: TransitionContribution = {
    id: overrides.id ?? ('test-transition' as any),
    kind: 'transition',
    transitionId: overrides.transitionId,
    label: overrides.label,
    allowBrowserExport: overrides.allowBrowserExport,
    allowWorkerExport: overrides.allowWorkerExport,
    order: overrides.order,
    materialSlots: overrides.materialSlots,
  };

  return {
    contribution: contribution as any,
    extensionId,
    scopedKey: `transition:${extensionId}:${contribution.id as string}`,
    duplicateOrdinal: 0,
    projectionEligible: true,
  };
}

/** Extract a single descriptor from the result, failing if count != 1. */
function singleDescriptor(
  descriptors: readonly VideoEditorTransitionDescriptor[],
): VideoEditorTransitionDescriptor {
  if (descriptors.length !== 1) {
    throw new Error(
      `Expected exactly 1 descriptor, got ${descriptors.length}`,
    );
  }
  return descriptors[0];
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('buildTransitionDescriptors', () => {
  // ---- Basic projection ---------------------------------------------------

  it('projects a transition contribution with transitionId into a descriptor', () => {
    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 'wipe' as any,
        transitionId: 'com.reigh.flagship.transition.wipe',
        label: 'Flagship Wipe',
        order: 10,
      }),
    ]);

    expect(result).toHaveLength(1);
    const d = singleDescriptor(result);
    expect(d.id).toBe('wipe');
    expect(d.transitionId).toBe('com.reigh.flagship.transition.wipe');
    expect(d.label).toBe('Flagship Wipe');
    expect(d.order).toBe(10);
    expect(d.allowBrowserExport).toBe(false);
    expect(d.allowWorkerExport).toBe(false);
    expect(d.hasRendererMetadata).toBe(true);
    expect(d.materialSlots).toEqual([]);
  });

  it('defaults allowBrowserExport and allowWorkerExport to false', () => {
    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 'minimal' as any,
        transitionId: 'com.reigh.minimal',
      }),
    ]);

    const d = singleDescriptor(result);
    expect(d.allowBrowserExport).toBe(false);
    expect(d.allowWorkerExport).toBe(false);
  });

  it('preserves explicit allowBrowserExport and allowWorkerExport', () => {
    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 'exportable' as any,
        transitionId: 'com.reigh.exportable',
        allowBrowserExport: true,
        allowWorkerExport: true,
      }),
    ]);

    const d = singleDescriptor(result);
    expect(d.allowBrowserExport).toBe(true);
    expect(d.allowWorkerExport).toBe(true);
  });

  it('falls back label to transitionId when no label is provided', () => {
    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 'nolabel' as any,
        transitionId: 'com.reigh.nolabel',
      }),
    ]);

    const d = singleDescriptor(result);
    expect(d.label).toBe('com.reigh.nolabel');
  });

  // ---- Skipping contributions without transitionId ------------------------

  it('skips contributions without a transitionId', () => {
    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 'no-transition-id' as any,
        transitionId: '' as any, // empty string is falsy-like, treated as missing
      }),
    ]);

    expect(result).toHaveLength(0);
  });

  it('skips a contribution with undefined transitionId', () => {
    const contribution = {
      id: 'no-transition-id-2' as any,
      kind: 'transition' as const,
      label: 'Missing ID',
      order: 5,
    } as TransitionContribution;

    const collected: CollectedContribution = {
      contribution: contribution as any,
      extensionId: 'test.ext',
      scopedKey: 'transition:test.ext:no-transition-id-2',
      duplicateOrdinal: 0,
      projectionEligible: true,
    };

    const result = buildTransitionDescriptors([collected]);
    expect(result).toHaveLength(0);
  });

  // ---- M5: Material slot projection ---------------------------------------

  describe('material slot projection (M5)', () => {
    it('projects a single material slot into the descriptor', () => {
      const materialSlots: readonly TransitionMaterialSlotDeclaration[] = [
        { name: 'transition-mask', label: 'Transition Mask' },
      ];

      const result = buildTransitionDescriptors([
        collectedTransition({
          id: 'wipe' as any,
          transitionId: 'com.reigh.flagship.transition.wipe',
          label: 'Flagship Wipe',
          materialSlots,
        }),
      ]);

      const d = singleDescriptor(result);
      expect(d.materialSlots).toHaveLength(1);
      const slot = d.materialSlots[0];
      expect(slot.name).toBe('transition-mask');
      expect(slot.label).toBe('Transition Mask');
    });

    it('projects multiple material slots', () => {
      const materialSlots: readonly TransitionMaterialSlotDeclaration[] = [
        { name: 'transition-mask', label: 'Transition Mask' },
        { name: 'secondary-mask', label: 'Secondary Mask' },
        { name: 'displacement-map' },
      ];

      const result = buildTransitionDescriptors([
        collectedTransition({
          id: 'multi-slot' as any,
          transitionId: 'com.reigh.multi-slot',
          materialSlots,
        }),
      ]);

      const d = singleDescriptor(result);
      expect(d.materialSlots).toHaveLength(3);

      expect(d.materialSlots[0].name).toBe('transition-mask');
      expect(d.materialSlots[0].label).toBe('Transition Mask');

      expect(d.materialSlots[1].name).toBe('secondary-mask');
      expect(d.materialSlots[1].label).toBe('Secondary Mask');

      expect(d.materialSlots[2].name).toBe('displacement-map');
      expect(d.materialSlots[2].label).toBeUndefined();
    });

    it('produces an empty materialSlots array when contribution has no materialSlots', () => {
      const result = buildTransitionDescriptors([
        collectedTransition({
          id: 'no-slots' as any,
          transitionId: 'com.reigh.no-slots',
        }),
      ]);

      const d = singleDescriptor(result);
      expect(d.materialSlots).toEqual([]);
    });

    it('produces an empty materialSlots array when materialSlots is an empty array', () => {
      const result = buildTransitionDescriptors([
        collectedTransition({
          id: 'empty-slots' as any,
          transitionId: 'com.reigh.empty-slots',
          materialSlots: [],
        }),
      ]);

      const d = singleDescriptor(result);
      expect(d.materialSlots).toEqual([]);
    });

    it('produces an empty materialSlots array when materialSlots is undefined', () => {
      const result = buildTransitionDescriptors([
        collectedTransition({
          id: 'undefined-slots' as any,
          transitionId: 'com.reigh.undefined-slots',
          materialSlots: undefined,
        }),
      ]);

      const d = singleDescriptor(result);
      expect(d.materialSlots).toEqual([]);
    });

    it('frozen descriptors have frozen materialSlots arrays', () => {
      const materialSlots: readonly TransitionMaterialSlotDeclaration[] = [
        { name: 'transition-mask', label: 'Transition Mask' },
      ];

      const result = buildTransitionDescriptors([
        collectedTransition({
          id: 'frozen' as any,
          transitionId: 'com.reigh.frozen',
          materialSlots,
        }),
      ]);

      const d = singleDescriptor(result);
      expect(Object.isFrozen(d)).toBe(true);
      expect(Object.isFrozen(d.materialSlots)).toBe(true);

      // Individual slot descriptors should also be frozen
      for (const slot of d.materialSlots) {
        expect(Object.isFrozen(slot)).toBe(true);
      }
    });

    it('treats the transition-mask slot as example/test data (not SDK constant)', () => {
      // This test explicitly validates that the Flagship Wipe material slot
      // is projected as example/test metadata — not as a production SDK
      // constant.  The slot values are derived from the contribution's
      // materialSlots field and do not reference any hardcoded SDK symbol.

      const materialSlots: readonly TransitionMaterialSlotDeclaration[] = [
        { name: 'transition-mask', label: 'Transition Mask' },
      ];

      const result = buildTransitionDescriptors([
        collectedTransition({
          id: 'wipe' as any,
          transitionId: 'com.reigh.flagship.transition.wipe',
          label: 'Flagship Wipe',
          materialSlots,
        }),
      ]);

      const d = singleDescriptor(result);
      const slot = d.materialSlots[0];

      // The slot name is a plain string — no enum or SDK constant
      expect(typeof slot.name).toBe('string');
      expect(slot.name).toBe('transition-mask');

      // The label is the raw contribution label, not a localized SDK key
      expect(typeof slot.label).toBe('string');
      expect(slot.label).toBe('Transition Mask');

      // The descriptor does not expose any internal SDK symbol path
      expect((d as any).__sdkConstant).toBeUndefined();
      expect((slot as any).__sdkConstant).toBeUndefined();
    });
  });

  // ---- Multiple contributions ---------------------------------------------

  it('projects multiple transition contributions in input order', () => {
    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 'first' as any,
        transitionId: 'com.reigh.first',
        order: 1,
      }),
      collectedTransition({
        id: 'second' as any,
        transitionId: 'com.reigh.second',
        order: 2,
      }),
    ]);

    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('first');
    expect(result[1].id).toBe('second');
  });

  it('returns a frozen array', () => {
    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 't' as any,
        transitionId: 'com.reigh.t',
      }),
    ]);

    expect(Object.isFrozen(result)).toBe(true);
  });

  // ---- Mixed with and without materialSlots --------------------------------

  it('handles mixed contributions (some with materialSlots, some without)', () => {
    const materialSlots: readonly TransitionMaterialSlotDeclaration[] = [
      { name: 'transition-mask', label: 'Transition Mask' },
    ];

    const result = buildTransitionDescriptors([
      collectedTransition({
        id: 'with-slots' as any,
        transitionId: 'com.reigh.with-slots',
        materialSlots,
      }),
      collectedTransition({
        id: 'without-slots' as any,
        transitionId: 'com.reigh.without-slots',
      }),
    ]);

    expect(result).toHaveLength(2);
    expect(result[0].materialSlots).toHaveLength(1);
    expect(result[0].materialSlots[0].name).toBe('transition-mask');
    expect(result[1].materialSlots).toEqual([]);
  });
});
