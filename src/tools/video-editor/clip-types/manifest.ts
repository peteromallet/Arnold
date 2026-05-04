import { BUILTIN_CLIP_TYPES } from '@/tools/video-editor/types';
import {
  toClipTypeManifest,
  type ClipTypeManifest,
} from './defineClipType';
import {
  createAvailableClipTypeRegistry,
  TRUSTED_CLIP_TYPE_REGISTRATIONS,
} from './registry';
import { getBuiltinClipTypeDescriptor } from './runtime';

export type ClipTypeCapabilityManifestEntry = ClipTypeManifest & {
  source: 'builtin' | 'sequence';
  exposure: {
    trusted: boolean;
    available: boolean;
    availability: 'builtin' | 'available' | 'unavailable';
  };
  themeId?: string;
  whenToUse?: string;
};

export type VideoEditorClipTypeCapabilityManifest = {
  version: 1;
  clipTypes: readonly ClipTypeCapabilityManifestEntry[];
};

const buildBuiltinManifestEntries = (): ClipTypeCapabilityManifestEntry[] => {
  return BUILTIN_CLIP_TYPES.flatMap((clipType) => {
    const descriptor = getBuiltinClipTypeDescriptor(clipType);
    if (!descriptor) {
      return [];
    }

    return [{
      ...toClipTypeManifest(descriptor),
      source: 'builtin',
      exposure: {
        trusted: true,
        available: true,
        availability: 'builtin',
      },
    }];
  });
};

const buildSequenceManifestEntries = (
  sequenceRegistry: Partial<Record<string, unknown>>,
): ClipTypeCapabilityManifestEntry[] => {
  const availableView = createAvailableClipTypeRegistry(sequenceRegistry);

  return TRUSTED_CLIP_TYPE_REGISTRATIONS.map((registration) => {
    const availableRegistration = availableView.getAvailableClipTypeRegistration(registration.id);

    return {
      ...toClipTypeManifest(registration.descriptor),
      source: 'sequence',
      exposure: {
        trusted: true,
        available: Boolean(availableRegistration),
        availability: availableRegistration ? 'available' : 'unavailable',
      },
      themeId: registration.metadata.themeId,
      whenToUse: registration.metadata.whenToUse,
    };
  });
};

export const createVideoEditorClipTypeCapabilityManifest = (
  sequenceRegistry: Partial<Record<string, unknown>>,
): VideoEditorClipTypeCapabilityManifest => {
  return {
    version: 1,
    clipTypes: [
      ...buildBuiltinManifestEntries(),
      ...buildSequenceManifestEntries(sequenceRegistry),
    ],
  };
};
