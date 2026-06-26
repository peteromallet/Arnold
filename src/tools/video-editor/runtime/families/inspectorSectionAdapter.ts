/**
 * Inspector section real compatibility adapter.
 *
 * Preserves M1 host-integrated inspector section behavior.
 *
 * @module families/inspectorSectionAdapter
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
import type { VideoEditorInspectorSectionDescriptor } from '../extensionSurface';
import { buildSlotSurfaceDescriptors } from './projectors/slotSurfaceProjector';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

const MANIFEST: HostAdapterManifest = Object.freeze({
  adapterId: 'inspectorSection-default',
  kind: 'inspectorSection',
  version: '1.0.0',
  maturity: 'host-integrated' as ExecutionMaturity,
  description: 'Compatibility adapter for M1 inspector section contributions.',
  metadata: Object.freeze({ classification: 'real' }),
});

export const inspectorSectionAdapter: HostFamilyAdapter<
  'inspectorSection',
  unknown,
  VideoEditorInspectorSectionDescriptor
> = Object.freeze({
  kind: 'inspectorSection' as const,
  classification: 'real',
  manifest: MANIFEST,

  normalize(
    input: NormalizeFamilyInput<unknown>,
  ): FamilyNormalizeResult<VideoEditorInspectorSectionDescriptor> {
    const wrapped = buildSlotSurfaceDescriptors('inspectorSection', input.contributions, input.extensionOrder);
    return {
      descriptors: Object.freeze(
        wrapped.map((item) => item.descriptor as VideoEditorInspectorSectionDescriptor),
      ),
    };
  },

  buildConformanceReport(): FamilyConformanceReport<'inspectorSection'> {
    const definition = getVideoFamilyDefinition('inspectorSection');
    if (!definition) {
      throw new Error('inspectorSectionAdapter: family definition not found for kind "inspectorSection".');
    }
    return buildConformanceReport(definition);
  },
});
