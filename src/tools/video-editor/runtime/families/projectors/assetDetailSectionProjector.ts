/**
 * Asset detail section projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/assetDetailSectionProjector
 */

import type { AssetDetailSectionContribution } from '@reigh/editor-sdk';
import type { VideoEditorAssetDetailSectionDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildAssetDetailSectionDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorAssetDetailSectionDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return sorted.map(({ contribution, extensionId }) => {
    const sectionContrib = contribution as unknown as AssetDetailSectionContribution;
    return freezeDescriptor({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      title: sectionContrib.title,
      placement: sectionContrib.placement,
      fieldPaths: sectionContrib.fieldPaths,
      when: sectionContrib.when,
    });
  });
}
