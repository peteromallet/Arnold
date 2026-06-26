/**
 * Timeline overlay real compatibility adapter.
 *
 * Preserves M2 host-integrated timeline overlay behavior.
 *
 * @module families/timelineOverlayAdapter
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
import type { VideoEditorOverlayDescriptor } from '../extensionSurface';
import { buildSlotSurfaceDescriptors } from './projectors/slotSurfaceProjector';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

const MANIFEST: HostAdapterManifest = Object.freeze({
  adapterId: 'timelineOverlay-default',
  kind: 'timelineOverlay',
  version: '1.0.0',
  maturity: 'host-integrated' as ExecutionMaturity,
  description: 'Compatibility adapter for M2 timeline overlay contributions.',
  metadata: Object.freeze({ classification: 'real' }),
});

export const timelineOverlayAdapter: HostFamilyAdapter<
  'timelineOverlay',
  unknown,
  VideoEditorOverlayDescriptor
> = Object.freeze({
  kind: 'timelineOverlay' as const,
  classification: 'real',
  manifest: MANIFEST,

  normalize(
    input: NormalizeFamilyInput<unknown>,
  ): FamilyNormalizeResult<VideoEditorOverlayDescriptor> {
    const wrapped = buildSlotSurfaceDescriptors('timelineOverlay', input.contributions, input.extensionOrder);
    return {
      descriptors: Object.freeze(
        wrapped.map((item) => item.descriptor as VideoEditorOverlayDescriptor),
      ),
    };
  },

  buildConformanceReport(): FamilyConformanceReport<'timelineOverlay'> {
    const definition = getVideoFamilyDefinition('timelineOverlay');
    if (!definition) {
      throw new Error('timelineOverlayAdapter: family definition not found for kind "timelineOverlay".');
    }
    return buildConformanceReport(definition);
  },
});
