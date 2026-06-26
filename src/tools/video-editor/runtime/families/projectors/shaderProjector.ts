/**
 * Shader projector — pure descriptor projection.
 *
 * Contains no imports from `extensionSurface.ts`, `useTimelineState.types.ts`,
 * or broad runtime slice modules.
 *
 * Preserves the shader asymmetry: shader contributions remain projectable
 * through sequencing, and missing `shaderId` diagnostics are emitted here
 * rather than in Phase 2 filtering.
 *
 * @module families/projectors/shaderProjector
 */

import type { ShaderContribution, ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { VideoEditorShaderDescriptor } from '../../extensionSurface';
import type { CollectedContribution } from '../FamilyContributionSequence';
import { sortFamilyContributions, freezeDescriptor } from '../familyAdapterUtils';

export interface ShaderProjectionResult {
  readonly descriptors: readonly VideoEditorShaderDescriptor[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

export function buildShaderDescriptors(
  contributions: readonly CollectedContribution[],
  extensionOrder?: ReadonlyMap<string, number>,
): ShaderProjectionResult {
  const sorted = sortFamilyContributions(contributions, extensionOrder);
  const descriptors: VideoEditorShaderDescriptor[] = [];
  const diagnostics: ExtensionDiagnostic[] = [];

  for (const { contribution, extensionId } of sorted) {
    const shaderContrib = contribution as unknown as ShaderContribution;
    const id = contribution.id as string;
    if (!shaderContrib.shaderId) {
      diagnostics.push({
        severity: 'error',
        code: 'runtime/shader-missing-shader-id',
        message:
          `Shader contribution "${id}" in extension "${extensionId}" ` +
          'has no shaderId. The shader will be inactive.',
        extensionId,
        contributionId: id,
      });
      continue;
    }

    descriptors.push(freezeDescriptor({
      id,
      extensionId,
      order: contribution.order,
      shaderId: shaderContrib.shaderId,
      label: shaderContrib.label ?? shaderContrib.shaderId,
      description: shaderContrib.description,
      pass: shaderContrib.pass,
      source: shaderContrib.source,
      uniforms: shaderContrib.uniforms,
      textures: shaderContrib.textures,
      fallback: shaderContrib.fallback,
      materializer: shaderContrib.materializer,
      hasSourceMetadata: shaderContrib.source !== undefined,
    }));
  }

  return {
    descriptors: Object.freeze(descriptors),
    diagnostics: Object.freeze(diagnostics),
  };
}
