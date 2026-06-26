/**
 * Transition projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/transitionProjector
 */

import type { TransitionContribution } from '@reigh/editor-sdk';
import type { VideoEditorTransitionDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildTransitionDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorTransitionDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  const descriptors: VideoEditorTransitionDescriptor[] = [];
  for (const { contribution, extensionId } of sorted) {
    const transitionContrib = contribution as unknown as TransitionContribution;
    if (!transitionContrib.transitionId) continue;
    descriptors.push(freezeDescriptor({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      transitionId: transitionContrib.transitionId,
      label: transitionContrib.label ?? transitionContrib.transitionId,
      allowBrowserExport: transitionContrib.allowBrowserExport ?? false,
      allowWorkerExport: transitionContrib.allowWorkerExport ?? false,
      hasRendererMetadata: true,
    }));
  }
  return Object.freeze(descriptors);
}
