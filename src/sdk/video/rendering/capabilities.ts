/**
 * Shader materializer capability contracts — portable public contracts.
 *
 * Representative render-relevant family boundary (M0 sanity check):
 * - Portable: scope identifiers, blocker messages, and requirement shapes.
 *   These are pure data / string helpers; they carry no WebGL context,
 *   no materializer runtime, and no host renderer state.
 * - Host-only: the actual shader materializer registry, GPU/material runtime,
 *   render pipeline orchestration, and `describeShaderMaterializerRequirementScope`
 *   callers that format diagnostics for the host UI.
 *
 * @publicContract
 */
export type ShaderMaterializerRequirementScope = 'clip' | 'postprocess';

export function describeShaderMaterializerRequirementScope(
  scope: ShaderMaterializerRequirementScope,
  ownerId?: string,
): string {
  if (scope === 'clip') {
    return ownerId ? `clip "${ownerId}"` : 'clip scope';
  }
  return 'timeline postprocess';
}

export function shaderMissingMaterializerBlockerMessage(
  shaderId: string,
  scope: ShaderMaterializerRequirementScope,
  ownerId?: string,
): string {
  return `Shader "${shaderId}" cannot export because no shader materializer produced RenderMaterial for ${
    describeShaderMaterializerRequirementScope(scope, ownerId)
  }.`;
}
