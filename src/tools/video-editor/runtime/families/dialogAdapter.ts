/**
 * Dialog real compatibility adapter.
 *
 * Preserves M1 host-integrated dialog behavior.
 *
 * @module families/dialogAdapter
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
import type { VideoEditorDialogDescriptor } from '../extensionSurface';
import { buildSlotSurfaceDescriptors } from './projectors/slotSurfaceProjector';
import { buildConformanceReport } from '@/sdk/core/families/conformance';

const MANIFEST: HostAdapterManifest = Object.freeze({
  adapterId: 'dialog-default',
  kind: 'dialog',
  version: '1.0.0',
  maturity: 'host-integrated' as ExecutionMaturity,
  description: 'Compatibility adapter for M1 dialog contributions.',
  metadata: Object.freeze({ classification: 'real' }),
});

export const dialogAdapter: HostFamilyAdapter<
  'dialog',
  unknown,
  VideoEditorDialogDescriptor
> = Object.freeze({
  kind: 'dialog' as const,
  classification: 'real',
  manifest: MANIFEST,

  normalize(
    input: NormalizeFamilyInput<unknown>,
  ): FamilyNormalizeResult<VideoEditorDialogDescriptor> {
    const wrapped = buildSlotSurfaceDescriptors('dialog', input.contributions, input.extensionOrder);
    return {
      descriptors: Object.freeze(
        wrapped.map((item) => item.descriptor as VideoEditorDialogDescriptor),
      ),
    };
  },

  buildConformanceReport(): FamilyConformanceReport<'dialog'> {
    const definition = getVideoFamilyDefinition('dialog');
    if (!definition) {
      throw new Error('dialogAdapter: family definition not found for kind "dialog".');
    }
    return buildConformanceReport(definition);
  },
});
