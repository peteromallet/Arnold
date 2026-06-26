/**
 * Parser projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/parserProjector
 */

import type { ParserContribution } from '@reigh/editor-sdk';
import type { VideoEditorAssetParserDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor, freezeDescriptors } from '../familyAdapterUtils';

export function buildParserDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorAssetParserDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return freezeDescriptors(sorted.map(({ contribution, extensionId }) => {
    const parserContrib = contribution as unknown as ParserContribution;
    return freezeDescriptor({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      label: parserContrib.label ?? contribution.id as string,
      acceptMimeTypes: parserContrib.acceptMimeTypes,
      acceptExtensions: parserContrib.acceptExtensions,
      maxBytes: parserContrib.maxBytes,
      required: parserContrib.required,
    });
  }));
}
