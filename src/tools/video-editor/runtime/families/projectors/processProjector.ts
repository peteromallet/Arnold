/**
 * Process projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/processProjector
 */

import type { ProcessContribution } from '@reigh/editor-sdk';
import type {
  VideoEditorProcessDescriptor,
  VideoEditorPlannerNextActionDescriptor,
} from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildProcessDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorProcessDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return sorted.map(({ contribution, extensionId }) => {
    const processContrib = contribution as unknown as ProcessContribution;
    const spec = processContrib.spec;
    const operations = Object.freeze([...(spec.operations ?? [])]);
    const availableRoutes = Object.freeze(
      Array.from(new Set(operations.flatMap((operation) => operation.routes ?? []))),
    );
    const id = contribution.id as string;
    const label = processContrib.label ?? spec.label ?? spec.id;

    return freezeDescriptor({
      id,
      extensionId,
      order: contribution.order,
      processId: spec.id,
      label,
      description: spec.description,
      spec,
      protocol: spec.protocol,
      operations,
      availableRoutes,
      capabilities: spec.capabilities,
      requiredBy: Object.freeze([...(spec.requiredBy ?? [])]),
      blockers: Object.freeze([]),
      nextActions: Object.freeze([] as VideoEditorPlannerNextActionDescriptor[]),
    });
  });
}
