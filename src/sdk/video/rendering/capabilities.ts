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
