/**
 * Search provider projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/searchProviderProjector
 */

import type { SearchProviderContribution } from '@reigh/editor-sdk';
import type { VideoEditorSearchProviderDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildSearchProviderDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorSearchProviderDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return sorted.map(({ contribution, extensionId }) => {
    const sp = contribution as unknown as SearchProviderContribution;
    const id = contribution.id as string;
    return freezeDescriptor({
      id,
      extensionId,
      order: contribution.order,
      label: sp.label ?? id,
      description: sp.description,
      resultKinds: sp.resultKinds,
    });
  });
}
