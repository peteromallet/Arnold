/**
 * Agent tool projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/agentToolProjector
 */

import type { AgentToolContribution, ToolResultFamily } from '@reigh/editor-sdk';
import type { VideoEditorAgentToolDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildAgentToolDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorAgentToolDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return sorted.map(({ contribution, extensionId }) => {
    const at = contribution as unknown as AgentToolContribution;
    return freezeDescriptor({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      toolId: at.toolId,
      label: at.label,
      description: at.description,
      resultFamilies: (at.resultFamilies ?? []) as readonly ToolResultFamily[],
      hasHandler: false,
    });
  });
}
