/**
 * Effect projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/effectProjector
 */

import type { EffectContribution } from '@reigh/editor-sdk';
import type { VideoEditorEffectDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export function buildEffectDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly VideoEditorEffectDescriptor[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  const descriptors: VideoEditorEffectDescriptor[] = [];
  for (const { contribution, extensionId } of sorted) {
    const effectContrib = contribution as unknown as EffectContribution;
    if (!effectContrib.effectId) continue;
    descriptors.push(freezeDescriptor({
      id: contribution.id as string,
      extensionId,
      order: contribution.order,
      effectId: effectContrib.effectId,
      label: effectContrib.label ?? effectContrib.effectId,
      allowBrowserExport: effectContrib.allowBrowserExport ?? false,
      allowWorkerExport: effectContrib.allowWorkerExport ?? false,
      hasComponentMetadata: true,
    }));
  }
  return Object.freeze(descriptors);
}
