/**
 * Common slot-surface projector for host-integrated UI families.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * @module families/projectors/slotSurfaceProjector
 */

import type {
  VideoEditorSlotName,
  VideoEditorSlotRenderer,
  VideoEditorDialogDescriptor,
  VideoEditorPanelDescriptor,
  VideoEditorInspectorSectionDescriptor,
  VideoEditorOverlayDescriptor,
} from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export interface SlotSurfaceDescriptor<T> {
  readonly descriptor: T;
  readonly slot?: VideoEditorSlotName;
}

export type SlotSurfaceKind = 'slot' | 'dialog' | 'panel' | 'inspectorSection' | 'timelineOverlay';

const PLACEMENT_DEFAULT = 'after-default' as const;

export function buildSlotSurfaceDescriptors(
  kind: SlotSurfaceKind,
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): readonly SlotSurfaceDescriptor<
  | { slot: VideoEditorSlotName; render: VideoEditorSlotRenderer }
  | VideoEditorDialogDescriptor
  | VideoEditorPanelDescriptor
  | VideoEditorInspectorSectionDescriptor
  | VideoEditorOverlayDescriptor
>[] {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  return sorted.map(({ contribution }) => {
    const id = contribution.id as string;
    switch (kind) {
      case 'slot': {
        const slotName = (contribution as { slot?: VideoEditorSlotName }).slot;
        return {
          slot: slotName,
          descriptor: {
            slot: slotName,
            render: null as unknown as VideoEditorSlotRenderer,
          },
        };
      }
      case 'dialog':
        return {
          descriptor: freezeDescriptor({
            id,
            order: contribution.order,
            layer: (contribution as { layer?: 'modal' | 'overlay' }).layer,
            render: null as unknown as VideoEditorSlotRenderer,
          }),
        };
      case 'panel':
        return {
          descriptor: freezeDescriptor({
            id,
            placement: 'asset-panel',
            order: contribution.order,
            render: null as unknown as VideoEditorSlotRenderer,
          }),
        };
      case 'inspectorSection':
        return {
          descriptor: freezeDescriptor({
            id,
            placement: (contribution as { placement?: 'before-default' | 'after-default' }).placement ?? PLACEMENT_DEFAULT,
            order: contribution.order,
            render: null as unknown as VideoEditorSlotRenderer,
          }),
        };
      case 'timelineOverlay':
        return {
          descriptor: freezeDescriptor({
            id,
            order: contribution.order,
            render: null as unknown as VideoEditorSlotRenderer,
          }),
        };
      default:
        // Exhaustive for known slot-surface kinds.
        return { descriptor: undefined as unknown as never };
    }
  });
}
