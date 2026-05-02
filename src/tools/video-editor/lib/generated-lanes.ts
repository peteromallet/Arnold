export const GENERATED_SEQUENCE_LANES = [
  'trusted_v1',
  'schema_sequence',
  'remotion_module',
] as const;

export type GeneratedSequenceLane = (typeof GENERATED_SEQUENCE_LANES)[number];

export type GeneratedLaneClipShape = {
  generation?: {
    sequence_lane?: unknown;
    artifact_id?: unknown;
  } | null;
};

export type GeneratedRemotionModuleBlockReason =
  | 'remotion_module_missing_artifact'
  | 'remotion_module_invalid_artifact';

export type GeneratedRemotionModuleStatus =
  | { kind: 'not_module' }
  | { kind: 'valid_module'; artifactId: string }
  | { kind: 'blocked_module'; reason: GeneratedRemotionModuleBlockReason };

export const getGeneratedSequenceLane = (
  clip: GeneratedLaneClipShape | null | undefined,
): unknown => clip?.generation?.sequence_lane;

export const isGeneratedRemotionModuleClip = (
  clip: GeneratedLaneClipShape | null | undefined,
): boolean => getGeneratedSequenceLane(clip) === 'remotion_module';

export const getGeneratedRemotionModuleStatus = (
  clip: GeneratedLaneClipShape | null | undefined,
): GeneratedRemotionModuleStatus => {
  if (!isGeneratedRemotionModuleClip(clip)) {
    return { kind: 'not_module' };
  }

  if (!Object.prototype.hasOwnProperty.call(clip?.generation ?? {}, 'artifact_id')) {
    return { kind: 'blocked_module', reason: 'remotion_module_missing_artifact' };
  }

  const artifactId = clip?.generation?.artifact_id;
  if (typeof artifactId !== 'string' || artifactId.trim().length === 0) {
    return { kind: 'blocked_module', reason: 'remotion_module_invalid_artifact' };
  }

  return { kind: 'valid_module', artifactId: artifactId.trim() };
};
