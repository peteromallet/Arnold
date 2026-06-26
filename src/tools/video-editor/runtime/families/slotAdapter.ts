/**
 * Slot real compatibility adapter.
 *
 * Preserves M1 host-integrated slot behavior.  The adapter produces
 * slot-name → renderer placeholder entries; real render functions are
 * wired during extension activation.
 *
 * @module families/slotAdapter
 */

import type {
  HostFamilyAdapter,
  HostAdapterManifest,
  NormalizeFamilyInput,
  FamilyNormalizeResult,
  FamilyConformanceReport,
  ExecutionMaturity,
} from '@reigh/editor-sdk';
import { getVideoFamilyDefinition } from '@reigh/editor-sdk';
import type {
  VideoEditorSlotName,
  VideoEditorSlotRenderer,
} from '../extensionSurface';
import { buildSlotSurfaceDescriptors } from './projectors/slotSurfaceProjector';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

export interface VideoEditorSlotDescriptor {
  readonly slot: VideoEditorSlotName;
  readonly render: VideoEditorSlotRenderer;
}

const MANIFEST: HostAdapterManifest = Object.freeze({
  adapterId: 'slot-default',
  kind: 'slot',
  version: '1.0.0',
  maturity: 'public-supported' as ExecutionMaturity,
  description: 'Compatibility adapter for M1 slot contributions.',
  metadata: Object.freeze({ classification: 'real' }),
});

export const slotAdapter: HostFamilyAdapter<
  'slot',
  unknown,
  VideoEditorSlotDescriptor
> = Object.freeze({
  kind: 'slot' as const,
  classification: 'real',
  manifest: MANIFEST,

  normalize(
    input: NormalizeFamilyInput<unknown>,
  ): FamilyNormalizeResult<VideoEditorSlotDescriptor> {
    const wrapped = buildSlotSurfaceDescriptors('slot', input.contributions, input.extensionOrder);
    const descriptors: VideoEditorSlotDescriptor[] = [];
    for (const item of wrapped) {
      const descriptor = item.descriptor as { slot?: VideoEditorSlotName };
      if (descriptor.slot) {
        descriptors.push(Object.freeze({
          slot: descriptor.slot,
          render: null as unknown as VideoEditorSlotRenderer,
        }));
      }
    }
    return { descriptors: Object.freeze(descriptors) };
  },

  buildConformanceReport(): FamilyConformanceReport<'slot'> {
    const definition = getVideoFamilyDefinition('slot');
    if (!definition) {
      throw new Error('slotAdapter: family definition not found for kind "slot".');
    }
    return buildConformanceReport(definition);
  },
});
