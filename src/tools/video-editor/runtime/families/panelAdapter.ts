/**
 * Panel real compatibility adapter.
 *
 * Preserves M1 host-integrated panel behavior.
 *
 * @module families/panelAdapter
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
import type { VideoEditorPanelDescriptor } from '../extensionSurface';
import { buildSlotSurfaceDescriptors } from './projectors/slotSurfaceProjector';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

const MANIFEST: HostAdapterManifest = Object.freeze({
  adapterId: 'panel-default',
  kind: 'panel',
  version: '1.0.0',
  maturity: 'host-integrated' as ExecutionMaturity,
  description: 'Compatibility adapter for M1 panel contributions.',
  metadata: Object.freeze({ classification: 'real' }),
});

export const panelAdapter: HostFamilyAdapter<
  'panel',
  unknown,
  VideoEditorPanelDescriptor
> = Object.freeze({
  kind: 'panel' as const,
  classification: 'real',
  manifest: MANIFEST,

  normalize(
    input: NormalizeFamilyInput<unknown>,
  ): FamilyNormalizeResult<VideoEditorPanelDescriptor> {
    const wrapped = buildSlotSurfaceDescriptors('panel', input.contributions, input.extensionOrder);
    return {
      descriptors: Object.freeze(
        wrapped.map((item) => item.descriptor as VideoEditorPanelDescriptor),
      ),
    };
  },

  buildConformanceReport(): FamilyConformanceReport<'panel'> {
    const definition = getVideoFamilyDefinition('panel');
    if (!definition) {
      throw new Error('panelAdapter: family definition not found for kind "panel".');
    }
    return buildConformanceReport(definition);
  },
});
