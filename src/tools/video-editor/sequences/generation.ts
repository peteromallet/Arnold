import type { SelectedMediaClip } from '@/tools/video-editor/hooks/useSelectedMediaClips';
import type { ValidatedSequenceDraft } from '@/tools/video-editor/sequences/validation';
import type {
  ResolvedAssetRegistryEntry,
  ResolvedTimelineConfig,
} from '@/tools/video-editor/types';

export type AllowedSequenceAsset = {
  key: string;
  url: string;
  mediaType: SelectedMediaClip['mediaType'];
  source: 'selected' | 'attached';
  label: string;
  clipId: string;
  generationId?: string;
  shotId?: string;
  shotName?: string;
  shotSelectionClipCount?: number;
  isPlaceholder?: boolean;
};

export type EditableSequenceDraft = {
  clipType: string;
  hold: number;
  params: Record<string, unknown>;
};

export type SequenceCreatorMode = 'generate' | 'edit';

export type SequenceAnimationIntent = {
  freeform: string;
};

export type SequenceDraftGroup = {
  id: string;
  name: string;
  prompt: string;
  intent?: SequenceAnimationIntent;
  drafts: EditableSequenceDraft[];
};

export type GenerateSequenceResponse = {
  drafts?: unknown[];
  invalid_drafts?: Array<{ index: number; errors: unknown[] }>;
  model?: string;
  error?: string;
  details?: string;
};

export type SequenceGenerationClipPayload = {
  clipId: string;
  assetKey: string;
  url: string;
  mediaType: SelectedMediaClip['mediaType'];
  shotId?: string;
  shotName?: string;
};

export type SequenceGenerationMetadata = {
  sequence_lane: 'trusted_v1';
  sequence_creator: {
    name: string;
    prompt: string;
    draft_index: number;
    intent?: SequenceAnimationIntent;
  };
};

export type SequenceMetadataPatch = Record<string, unknown>;

export type SequenceMetadataMutation = {
  metaUpdates?: Record<string, SequenceMetadataPatch>;
};

const MAX_DRAFT_GROUP_NAME_LENGTH = 52;

export const createEditableDraft = (draft: ValidatedSequenceDraft): EditableSequenceDraft => ({
  clipType: draft.clipType,
  hold: draft.hold,
  params: { ...draft.params },
});

export const createDraftGroupId = (): string => (
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `sequence-${Date.now()}-${Math.random().toString(16).slice(2)}`
);

export const buildAnimationIntentPayload = (
  value: string,
): SequenceAnimationIntent | undefined => {
  const freeform = value.trim();
  return freeform ? { freeform } : undefined;
};

export const sanitizeAnimationIntentForProvenance = (
  intent: SequenceAnimationIntent | undefined,
): SequenceAnimationIntent | undefined => {
  const freeform = intent?.freeform
    .replace(/\b(?:https?:\/\/|data:|blob:)\S+/gi, '[redacted-url]')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 1000);
  return freeform ? { freeform } : undefined;
};

export const buildSequenceGenerationMetadata = (
  group: SequenceDraftGroup | null,
  draftIndex: number,
): SequenceGenerationMetadata | undefined => {
  if (!group) return undefined;
  const intent = sanitizeAnimationIntentForProvenance(group.intent);
  return {
    sequence_lane: 'trusted_v1',
    sequence_creator: {
      name: group.name,
      prompt: group.prompt,
      draft_index: draftIndex,
      ...(intent ? { intent } : {}),
    },
  };
};

export const attachSequenceGenerationMetadata = <TMutation extends SequenceMetadataMutation>(
  mutation: TMutation,
  clipId: string,
  generation: SequenceGenerationMetadata | undefined,
): TMutation => {
  if (!generation) return mutation;
  const existingMeta = mutation.metaUpdates?.[clipId] ?? {};
  return {
    ...mutation,
    metaUpdates: {
      ...mutation.metaUpdates,
      [clipId]: {
        ...existingMeta,
        generation,
      },
    },
  };
};

export const nameDraftGroupFromPrompt = (prompt: string, index: number): string => {
  const normalized = prompt.trim().replace(/\s+/g, ' ');
  const base = normalized || `Animation ${index + 1}`;
  return base.length > MAX_DRAFT_GROUP_NAME_LENGTH
    ? `${base.slice(0, MAX_DRAFT_GROUP_NAME_LENGTH - 1).trim()}…`
    : base;
};

export const buildAllowedSequenceAssets = (
  selectedClips: readonly SelectedMediaClip[],
  attachedClips: readonly SelectedMediaClip[],
  registry: ResolvedTimelineConfig['registry'],
): AllowedSequenceAsset[] => {
  const byKey = new Map<string, AllowedSequenceAsset>();

  const addClip = (clip: SelectedMediaClip, source: AllowedSequenceAsset['source']) => {
    if (!clip.assetKey || clip.isPlaceholder) return;
    const entry = registry[clip.assetKey];
    if (!entry?.src) return;
    if (byKey.has(clip.assetKey)) return;
    byKey.set(clip.assetKey, {
      key: clip.assetKey,
      url: entry.src,
      mediaType: clip.mediaType,
      source,
      label: clip.shotName ?? clip.assetKey,
      clipId: clip.clipId,
      generationId: clip.generationId,
      shotId: clip.shotId,
      shotName: clip.shotName,
      shotSelectionClipCount: clip.shotSelectionClipCount,
      isPlaceholder: clip.isPlaceholder,
    });
  };

  selectedClips.forEach((clip) => addClip(clip, 'selected'));
  attachedClips.forEach((clip) => addClip(clip, 'attached'));

  return [...byKey.values()];
};

export const buildAllowedAssetRegistry = (
  assets: readonly AllowedSequenceAsset[],
  registry: ResolvedTimelineConfig['registry'],
): ResolvedTimelineConfig['registry'] => {
  return assets.reduce<Record<string, ResolvedAssetRegistryEntry>>((next, asset) => {
    const entry = registry[asset.key];
    if (entry) next[asset.key] = entry;
    return next;
  }, {});
};

export const buildGenerationClipPayloads = (
  clips: readonly SelectedMediaClip[],
  allowedAssets: readonly AllowedSequenceAsset[],
): SequenceGenerationClipPayload[] => {
  const allowedByKey = new Map(allowedAssets.map((asset) => [asset.key, asset]));
  return clips.flatMap((clip) => {
    if (!clip.assetKey || clip.isPlaceholder) return [];
    const asset = allowedByKey.get(clip.assetKey);
    if (!asset) return [];
    return [{
      clipId: clip.clipId,
      assetKey: asset.key,
      url: asset.url,
      mediaType: clip.mediaType,
      shotId: clip.shotId,
      shotName: clip.shotName,
    }];
  });
};
