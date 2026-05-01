import {
  THEME_PACKAGE_REGISTRY,
  type ThemePackageClipType,
} from '@banodoco/timeline-composition/registry.generated';
import {
  TRUSTED_SEQUENCE_METADATA,
  type TrustedSequenceMetadata,
} from '@/tools/video-editor/sequences/metadata';

export type AvailableSequenceMetadata = TrustedSequenceMetadata & {
  clipType: ThemePackageClipType;
};

export const filterTrustedSequenceMetadataForRegistry = (
  registry: Partial<Record<string, unknown>>,
): AvailableSequenceMetadata[] => {
  return TRUSTED_SEQUENCE_METADATA.filter((metadata): metadata is AvailableSequenceMetadata => {
    return Object.prototype.hasOwnProperty.call(registry, metadata.clipType);
  });
};

export const AVAILABLE_SEQUENCE_METADATA = filterTrustedSequenceMetadataForRegistry(
  THEME_PACKAGE_REGISTRY,
);

export const AVAILABLE_SEQUENCE_CLIP_TYPES = AVAILABLE_SEQUENCE_METADATA.map(
  (metadata) => metadata.clipType,
) as readonly ThemePackageClipType[];

export const isAvailableSequenceClipType = (value: unknown): value is ThemePackageClipType => {
  return typeof value === 'string' && (AVAILABLE_SEQUENCE_CLIP_TYPES as readonly string[]).includes(value);
};

export const getAvailableSequenceMetadata = (
  clipType: string,
): AvailableSequenceMetadata | undefined => {
  return AVAILABLE_SEQUENCE_METADATA.find((metadata) => metadata.clipType === clipType);
};
