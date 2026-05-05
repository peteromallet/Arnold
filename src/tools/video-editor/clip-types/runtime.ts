import { BUILTIN_CLIP_TYPES, type ResolvedTimelineClip, type TimelineClip, type TrackDefinition } from '@/tools/video-editor/types/index.ts';
import {
  defineClipType,
  isSequenceParamsSchema,
  type ClipTypeCommandConstraint,
  type ClipTypeCommandConstraintValue,
  type ClipTypeCommandMetadata,
  type ClipTypeDescriptor,
} from './defineClipType.ts';
import {
  createAvailableClipTypeRegistry,
  getTrustedClipTypeDescriptor,
  type AvailableClipTypeRegistration,
  type TrustedClipTypeRegistration,
} from './registry.ts';

export type BuiltinClipType = (typeof BUILTIN_CLIP_TYPES)[number];
export type ClipAssetMediaType = 'image' | 'video' | 'audio' | 'unknown';

type BuiltinClipTypeRegistration = {
  id: BuiltinClipType;
  source: 'builtin';
  descriptor: ClipTypeDescriptor;
};

type SequenceAvailableRegistration = AvailableClipTypeRegistration & {
  source: 'sequence';
};

type SequenceTrustedRegistration = TrustedClipTypeRegistration & {
  source: 'sequence';
};

export type AvailableRegisteredClipTypeRegistration =
  | BuiltinClipTypeRegistration
  | SequenceAvailableRegistration;

export type TrustedRegisteredClipTypeRegistration =
  | BuiltinClipTypeRegistration
  | SequenceTrustedRegistration;

export type RegisteredClipTypeLookupResult =
  | { status: 'available'; registration: AvailableRegisteredClipTypeRegistration }
  | { status: 'unavailable'; registration: SequenceTrustedRegistration }
  | { status: 'unknown'; clipType: string | undefined };

export type ClipTypeCommandEvaluationContext = {
  clip?: TimelineClip | ResolvedTimelineClip | null;
  track?: TrackDefinition | null;
  selectedClipIds?: readonly string[] | null;
};

export type ClipTypeCommandAvailability = {
  command: ClipTypeCommandMetadata;
  allowed: boolean;
};

export type ClipTypeOverlayDoubleClickAction =
  | 'none'
  | 'lightbox'
  | 'inline-text-edit';

export type ClipTypeDefaultBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ClipTypeOverlayBehavior = {
  excluded: boolean;
  alwaysVisible: boolean;
  allowsBoundsEditing: boolean;
  allowsCrop: boolean;
  supportsInlineTextEdit: boolean;
  doubleClickAction: ClipTypeOverlayDoubleClickAction;
  lightboxEnabled: boolean;
  defaultBounds: ClipTypeDefaultBounds | null;
};

const MEDIA_COMMANDS = [
  {
    id: 'split',
    label: 'Split',
    requirements: [
      {
        fact: 'selection.cardinality',
        operator: 'equals',
        value: 'single',
      },
    ],
  },
  {
    id: 'move-track-up',
    label: 'Move Track Up',
    requirements: [
      {
        fact: 'selection.cardinality',
        operator: 'equals',
        value: 'single',
      },
    ],
  },
  {
    id: 'move-track-down',
    label: 'Move Track Down',
    requirements: [
      {
        fact: 'selection.cardinality',
        operator: 'equals',
        value: 'single',
      },
    ],
  },
  {
    id: 'toggle-mute',
    label: 'Toggle Mute',
    requirements: [
      {
        fact: 'asset.mediaType',
        operator: 'in',
        value: ['audio', 'video'],
      },
    ],
  },
  {
    id: 'detach-audio',
    label: 'Detach Audio',
    requirements: [
      {
        fact: 'selection.cardinality',
        operator: 'equals',
        value: 'single',
      },
      {
        fact: 'track.kind',
        operator: 'equals',
        value: 'visual',
      },
      {
        fact: 'asset.mediaType',
        operator: 'equals',
        value: 'video',
      },
    ],
  },
] as const;

const HOLD_ONLY_COMMANDS = [
  {
    id: 'split',
    label: 'Split',
    requirements: [
      {
        fact: 'selection.cardinality',
        operator: 'equals',
        value: 'single',
      },
    ],
  },
  {
    id: 'move-track-up',
    label: 'Move Track Up',
    requirements: [
      {
        fact: 'selection.cardinality',
        operator: 'equals',
        value: 'single',
      },
    ],
  },
  {
    id: 'move-track-down',
    label: 'Move Track Down',
    requirements: [
      {
        fact: 'selection.cardinality',
        operator: 'equals',
        value: 'single',
      },
    ],
  },
] as const;

const BUILTIN_CLIP_TYPE_REGISTRATIONS = [
  {
    id: 'media',
    source: 'builtin',
    descriptor: defineClipType({
      id: 'media',
      label: 'Media',
      description: 'Asset-backed video or audio clip.',
      defaults: {
        clip: {
          from: 0,
          speed: 1,
          volume: 1,
        },
      },
      commands: MEDIA_COMMANDS,
      renderCapabilities: {
        previewRoute: 'native-media',
        exportRoute: 'client',
        features: ['visual', 'manual-bounds', 'crop', 'lightbox', 'waveform'],
      },
    }),
  },
  {
    id: 'hold',
    source: 'builtin',
    descriptor: defineClipType({
      id: 'hold',
      label: 'Hold',
      description: 'Visual still or background hold clip.',
      hold: {
        kind: 'required',
        defaultSeconds: 5,
        minSeconds: 0.05,
        maxSeconds: 120,
        stepSeconds: 0.1,
      },
      defaults: {
        clip: {
          opacity: 1,
        },
      },
      commands: HOLD_ONLY_COMMANDS,
      renderCapabilities: {
        previewRoute: 'native-media',
        exportRoute: 'client',
        features: ['visual', 'manual-bounds', 'crop', 'lightbox', 'hold-duration'],
      },
    }),
  },
  {
    id: 'text',
    source: 'builtin',
    descriptor: defineClipType({
      id: 'text',
      label: 'Text',
      description: 'Inline-editable text overlay clip.',
      hold: {
        kind: 'required',
        defaultSeconds: 5,
        minSeconds: 0.05,
        maxSeconds: 120,
        stepSeconds: 0.1,
      },
      defaults: {
        clip: {
          opacity: 1,
          x: 120,
          y: 120,
          width: 640,
          height: 180,
          text: {
            content: 'Double-click to edit',
            fontSize: 64,
            color: '#ffffff',
            align: 'center',
          },
        },
      },
      commands: [
        ...HOLD_ONLY_COMMANDS,
        {
          id: 'edit-text',
          label: 'Edit Text',
          requirements: [
            {
              fact: 'clip.hasText',
              operator: 'equals',
              value: true,
            },
          ],
        },
      ],
      renderCapabilities: {
        previewRoute: 'native-text',
        exportRoute: 'client',
        features: ['visual', 'manual-bounds', 'overlay', 'inline-text-edit', 'hold-duration'],
      },
    }),
  },
  {
    id: 'effect-layer',
    source: 'builtin',
    descriptor: defineClipType({
      id: 'effect-layer',
      label: 'Effect Layer',
      description: 'Continuous effect layer applied over lower visual tracks.',
      hold: {
        kind: 'required',
        defaultSeconds: 5,
        minSeconds: 0.05,
        maxSeconds: 120,
        stepSeconds: 0.1,
      },
      commands: HOLD_ONLY_COMMANDS,
      renderCapabilities: {
        previewRoute: 'effect-layer',
        exportRoute: 'client',
        features: ['visual', 'hold-duration'],
        knownLimitations: ['Requires lower visual content to affect the frame.'],
      },
    }),
  },
] as const satisfies readonly BuiltinClipTypeRegistration[];

const BUILTIN_CLIP_TYPE_REGISTRATION_MAP = new Map(
  BUILTIN_CLIP_TYPE_REGISTRATIONS.map((registration) => [registration.id, registration]),
);

const asComparableArray = (
  value: ClipTypeCommandConstraintValue | undefined,
): readonly (string | number | boolean)[] => {
  if (Array.isArray(value)) {
    return value;
  }
  return value === undefined ? [] : [value];
};

const inferSelectionCardinality = (
  selectedClipIds: readonly string[] | null | undefined,
): 'none' | 'single' | 'multiple' => {
  const size = selectedClipIds?.length ?? 0;
  if (size <= 0) return 'none';
  if (size === 1) return 'single';
  return 'multiple';
};

const inferAssetMediaTypeFromString = (value: string): ClipAssetMediaType => {
  const lowerValue = value.toLowerCase();
  if (
    lowerValue.startsWith('image/')
    || /\.(png|jpe?g|gif|webp|avif|svg)$/i.test(lowerValue)
  ) {
    return 'image';
  }
  if (
    lowerValue.startsWith('video/')
    || /\.(mp4|mov|webm|m4v|avi)$/i.test(lowerValue)
  ) {
    return 'video';
  }
  if (
    lowerValue.startsWith('audio/')
    || /\.(mp3|wav|aac|m4a|ogg|flac)$/i.test(lowerValue)
  ) {
    return 'audio';
  }
  return 'unknown';
};

export const inferLegacyClipType = (
  clip: Pick<TimelineClip, 'clipType' | 'hold' | 'text'>,
): BuiltinClipType | string => {
  return clip.clipType
    ?? (clip.text ? 'text' : typeof clip.hold === 'number' ? 'hold' : 'media');
};

export const getClipAssetMediaType = (
  clip: Pick<ResolvedTimelineClip, 'assetEntry'> | Pick<TimelineClip, 'asset'> | null | undefined,
): ClipAssetMediaType => {
  const assetEntryValue = 'assetEntry' in (clip ?? {}) ? clip?.assetEntry : undefined;
  if (assetEntryValue?.type) {
    return inferAssetMediaTypeFromString(assetEntryValue.type);
  }
  if (assetEntryValue?.file) {
    return inferAssetMediaTypeFromString(assetEntryValue.file);
  }
  if (assetEntryValue?.src) {
    return inferAssetMediaTypeFromString(assetEntryValue.src);
  }
  return 'unknown';
};

const getBuiltinClipTypeRegistration = (
  clipType: string,
): BuiltinClipTypeRegistration | undefined => {
  return BUILTIN_CLIP_TYPE_REGISTRATION_MAP.get(clipType as BuiltinClipType);
};

export const getBuiltinClipTypeDescriptor = (
  clipType: string,
): ClipTypeDescriptor | undefined => {
  return getBuiltinClipTypeRegistration(clipType)?.descriptor;
};

export const getRegisteredClipTypeDescriptor = (
  clipType: string | undefined,
): ClipTypeDescriptor | undefined => {
  if (!clipType) {
    return getBuiltinClipTypeDescriptor('media');
  }
  return getBuiltinClipTypeDescriptor(clipType) ?? getTrustedClipTypeDescriptor(clipType);
};

export const createEditorClipTypeRegistry = (
  registry: Partial<Record<string, unknown>>,
) => {
  const availableSequenceView = createAvailableClipTypeRegistry(registry);

  const getAvailableRegistration = (
    clipType: string,
  ): AvailableRegisteredClipTypeRegistration | undefined => {
    return getBuiltinClipTypeRegistration(clipType)
      ?? (() => {
        const sequenceRegistration = availableSequenceView.getAvailableClipTypeRegistration(clipType);
        return sequenceRegistration
          ? { ...sequenceRegistration, source: 'sequence' as const }
          : undefined;
      })();
  };

  const resolveRegistration = (
    clipType: string | undefined,
  ): RegisteredClipTypeLookupResult => {
    if (!clipType) {
      const registration = getBuiltinClipTypeRegistration('media');
      return registration
        ? { status: 'available', registration }
        : { status: 'unknown', clipType };
    }

    const builtinRegistration = getBuiltinClipTypeRegistration(clipType);
    if (builtinRegistration) {
      return { status: 'available', registration: builtinRegistration };
    }

    const sequenceResolution = availableSequenceView.resolveAvailableClipTypeRegistration(clipType);
    if (sequenceResolution.status === 'available') {
      return {
        status: 'available',
        registration: {
          ...sequenceResolution.registration,
          source: 'sequence',
        },
      };
    }
    if (sequenceResolution.status === 'unavailable') {
      return {
        status: 'unavailable',
        registration: {
          ...sequenceResolution.registration,
          source: 'sequence',
        },
      };
    }
    return sequenceResolution;
  };

  return {
    clipTypes: [
      ...BUILTIN_CLIP_TYPE_REGISTRATIONS.map((registration) => registration.id),
      ...availableSequenceView.clipTypes,
    ] as const,
    getAvailableRegistration,
    getDescriptor: (clipType: string | undefined): ClipTypeDescriptor | undefined => {
      if (!clipType) {
        return getBuiltinClipTypeDescriptor('media');
      }
      return getAvailableRegistration(clipType)?.descriptor ?? getRegisteredClipTypeDescriptor(clipType);
    },
    resolveRegistration,
  };
};

export const createClipMetaFromDescriptor = ({
  clipType,
  trackId,
  clipOverrides,
  params,
  useDescriptorParamDefaults = false,
}: {
  clipType: string;
  trackId: string;
  clipOverrides?: Record<string, unknown>;
  params?: Record<string, unknown>;
  useDescriptorParamDefaults?: boolean;
}): Record<string, unknown> | null => {
  const descriptor = getRegisteredClipTypeDescriptor(clipType);
  if (!descriptor) {
    return null;
  }

  const nextParams = useDescriptorParamDefaults
    ? {
        ...descriptor.defaults.params,
        ...(params ?? {}),
      }
    : (params ?? {});

  return {
    ...descriptor.defaults.clip,
    ...(Object.keys(nextParams).length > 0 ? { params: nextParams } : {}),
    ...(clipOverrides ?? {}),
    track: trackId,
    clipType: descriptor.id,
  };
};

export const clipTypeUsesHoldTiming = (
  descriptor: ClipTypeDescriptor | undefined,
): boolean => {
  return Boolean(descriptor && descriptor.hold.kind !== 'unsupported');
};

export const getSequenceDescriptorParams = (
  descriptor: ClipTypeDescriptor | undefined,
) => {
  if (!descriptor || !isSequenceParamsSchema(descriptor.paramsSchema)) {
    return [];
  }
  return descriptor.paramsSchema.params;
};

const descriptorHasFeature = (
  descriptor: ClipTypeDescriptor | undefined,
  feature: string,
): boolean => {
  return descriptor?.renderCapabilities.features?.includes(feature) ?? false;
};

const getDescriptorDefaultBounds = (
  descriptor: ClipTypeDescriptor | undefined,
): ClipTypeDefaultBounds | null => {
  const x = descriptor?.defaults.clip.x;
  const y = descriptor?.defaults.clip.y;
  const width = descriptor?.defaults.clip.width;
  const height = descriptor?.defaults.clip.height;
  return typeof x === 'number'
    && typeof y === 'number'
    && typeof width === 'number'
    && typeof height === 'number'
    ? { x, y, width, height }
    : null;
};

export const getClipTypeOverlayBehavior = (
  descriptor: ClipTypeDescriptor | undefined,
): ClipTypeOverlayBehavior => {
  const previewRoute = descriptor?.renderCapabilities.previewRoute;
  const supportsInlineTextEdit = descriptorHasFeature(descriptor, 'inline-text-edit');
  const allowsBoundsEditing = descriptorHasFeature(descriptor, 'manual-bounds')
    || supportsInlineTextEdit;
  const lightboxEnabled = descriptorHasFeature(descriptor, 'lightbox');
  const defaultBounds = getDescriptorDefaultBounds(descriptor);
  const excluded = previewRoute === 'effect-layer'
    || (!allowsBoundsEditing && !supportsInlineTextEdit);

  return {
    excluded,
    alwaysVisible: supportsInlineTextEdit || defaultBounds !== null,
    allowsBoundsEditing,
    allowsCrop: descriptorHasFeature(descriptor, 'crop'),
    supportsInlineTextEdit,
    doubleClickAction: supportsInlineTextEdit
      ? 'inline-text-edit'
      : lightboxEnabled
        ? 'lightbox'
        : 'none',
    lightboxEnabled,
    defaultBounds,
  };
};

const getCommandFactValue = (
  descriptor: ClipTypeDescriptor,
  context: ClipTypeCommandEvaluationContext,
  fact: ClipTypeCommandConstraint['fact'],
): unknown => {
  switch (fact) {
    case 'selection.cardinality':
      return inferSelectionCardinality(context.selectedClipIds);
    case 'selection.sameClipType': {
      const selectedClipIds = context.selectedClipIds ?? [];
      return selectedClipIds.length <= 1;
    }
    case 'track.kind':
      return context.track?.kind ?? null;
    case 'asset.mediaType':
      return getClipAssetMediaType(context.clip);
    case 'clip.hasAsset':
      return Boolean(context.clip && 'asset' in context.clip && context.clip.asset);
    case 'clip.hasText':
      return Boolean(context.clip && 'text' in context.clip && context.clip.text);
    case 'clip.hold.kind':
      return descriptor.hold.kind;
    case 'clip.isInPinnedShotGroup':
      return false;
    default:
      return undefined;
  }
};

const constraintMatches = (
  descriptor: ClipTypeDescriptor,
  context: ClipTypeCommandEvaluationContext,
  constraint: ClipTypeCommandConstraint,
): boolean => {
  const actual = getCommandFactValue(descriptor, context, constraint.fact);
  const expectedValues = asComparableArray(constraint.value);

  switch (constraint.operator) {
    case 'exists':
      return actual !== undefined && actual !== null;
    case 'equals':
      return expectedValues.length > 0 && actual === expectedValues[0];
    case 'notEquals':
      return expectedValues.length > 0 && actual !== expectedValues[0];
    case 'in':
      return expectedValues.includes(actual as string | number | boolean);
    case 'notIn':
      return !expectedValues.includes(actual as string | number | boolean);
    default:
      return false;
  }
};

export const getClipTypeCommandAvailability = (
  descriptor: ClipTypeDescriptor | undefined,
  context: ClipTypeCommandEvaluationContext,
): ClipTypeCommandAvailability[] => {
  if (!descriptor?.commands?.length) {
    return [];
  }

  return descriptor.commands.map((command) => {
    const requirements = command.requirements ?? [];
    const limitations = command.limitations ?? [];
    const meetsRequirements = requirements.every((constraint) => constraintMatches(descriptor, context, constraint));
    const hitsLimitations = limitations.some((constraint) => constraintMatches(descriptor, context, constraint));
    return {
      command,
      allowed: meetsRequirements && !hitsLimitations,
    };
  });
};

export const isClipTypeCommandAvailable = (
  descriptor: ClipTypeDescriptor | undefined,
  commandId: string,
  context: ClipTypeCommandEvaluationContext,
): boolean => {
  if (!descriptor) {
    return false;
  }
  const command = getClipTypeCommandAvailability(descriptor, context).find(
    (entry) => entry.command.id === commandId,
  );
  return command?.allowed ?? false;
};
