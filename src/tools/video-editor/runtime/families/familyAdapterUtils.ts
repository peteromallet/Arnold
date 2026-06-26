/**
 * Shared utilities for host family adapters.
 *
 * Pure helpers used by both real and placeholder adapters.  No imports
 * from extensionSurface or broad runtime slices.
 *
 * @module families/familyAdapterUtils
 */

import type { FamilyContributionRef } from '@reigh/editor-sdk';

/**
 * Sort family contributions using the canonical deterministic order:
 * extension order ascending, then contribution.order ascending, then
 * contribution.id alphabetically.
 *
 * When `extensionOrder` is omitted, the input order is preserved.
 */
export function sortFamilyContributions<TContribution>(
  contributions: readonly FamilyContributionRef<TContribution>[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly FamilyContributionRef<TContribution>[] {
  if (!extensionOrder || contributions.length <= 1) {
    return contributions;
  }

  return [...contributions].sort((a, b) => {
    const extOrderA = extensionOrder.get(a.extensionId) ?? Number.MAX_SAFE_INTEGER;
    const extOrderB = extensionOrder.get(b.extensionId) ?? Number.MAX_SAFE_INTEGER;
    if (extOrderA !== extOrderB) return extOrderA - extOrderB;

    const orderA = (a.contribution as { order?: number }).order ?? 0;
    const orderB = (b.contribution as { order?: number }).order ?? 0;
    if (orderA !== orderB) return orderA - orderB;

    const idA = (a.contribution as { id?: string }).id ?? '';
    const idB = (b.contribution as { id?: string }).id ?? '';
    return idA.localeCompare(idB);
  });
}

/**
 * Freeze a single descriptor object shallowly.
 */
export function freezeDescriptor<T>(descriptor: T): T {
  return Object.freeze(descriptor);
}

/**
 * Freeze an array of descriptors shallowly.
 */
export function freezeDescriptors<T>(descriptors: readonly T[]): readonly T[] {
  return Object.freeze([...descriptors]);
}
