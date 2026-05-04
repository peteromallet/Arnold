import {
  defineClipType,
  isSequenceParamsSchema,
  type ClipTypeDescriptor,
  type ClipTypeHoldSupport,
  type ClipTypeSequenceParamDefinition,
} from './defineClipType';
import {
  TRUSTED_SEQUENCE_METADATA,
  type TrustedSequenceClipType,
  type TrustedSequenceMetadata,
} from '@/tools/video-editor/sequences/metadata';

export type TrustedClipTypeMetadata = TrustedSequenceMetadata;

export type AvailableClipTypeMetadata = TrustedClipTypeMetadata & {
  clipType: string;
};

type SequenceClipTypeDescriptor = ClipTypeDescriptor & {
  id: TrustedSequenceClipType;
  hold: Exclude<ClipTypeHoldSupport, { kind: 'unsupported' }>;
  paramsSchema: {
    kind: 'sequence';
    params: readonly ClipTypeSequenceParamDefinition[];
  };
};

export type TrustedClipTypeRegistration = {
  id: TrustedSequenceClipType;
  descriptor: SequenceClipTypeDescriptor;
  metadata: TrustedClipTypeMetadata;
};

export type AvailableClipTypeRegistration = TrustedClipTypeRegistration & {
  id: string;
  componentEntry: unknown;
  metadata: AvailableClipTypeMetadata;
};

export type TrustedClipTypeLookupResult =
  | { status: 'trusted'; registration: TrustedClipTypeRegistration }
  | { status: 'unknown'; clipType: string | undefined };

export type AvailableClipTypeLookupResult =
  | { status: 'available'; registration: AvailableClipTypeRegistration }
  | { status: 'unavailable'; registration: TrustedClipTypeRegistration }
  | { status: 'unknown'; clipType: string | undefined };

export type AvailableClipTypeRegistryView = {
  registrations: readonly AvailableClipTypeRegistration[];
  metadata: readonly AvailableClipTypeMetadata[];
  descriptors: readonly SequenceClipTypeDescriptor[];
  clipTypes: readonly string[];
  isAvailableClipType: (value: unknown) => value is string;
  getAvailableClipTypeRegistration: (clipType: string) => AvailableClipTypeRegistration | undefined;
  getAvailableClipTypeDescriptor: (clipType: string) => SequenceClipTypeDescriptor | undefined;
  getAvailableClipTypeMetadata: (clipType: string) => AvailableClipTypeMetadata | undefined;
  resolveAvailableClipTypeRegistration: (clipType: string | undefined) => AvailableClipTypeLookupResult;
};

const hasOwn = (
  registry: Partial<Record<string, unknown>>,
  key: string,
): boolean => Object.prototype.hasOwnProperty.call(registry, key);

const buildSequenceDescriptor = (
  metadata: TrustedSequenceMetadata,
): SequenceClipTypeDescriptor => defineClipType({
  id: metadata.clipType,
  label: metadata.label,
  description: metadata.description,
  hold: {
    kind: 'required',
    ...metadata.hold,
  },
  paramsSchema: {
    kind: 'sequence',
    params: metadata.params,
  },
  commands: [
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
  ],
  renderCapabilities: {
    previewRoute: 'sequence-component',
    exportRoute: 'custom',
    features: ['visual', 'hold-duration'],
    knownLimitations: [
      'Requires a registered sequence component in the available view before inspector and preview routes can use it.',
    ],
  },
}) as SequenceClipTypeDescriptor;

export const TRUSTED_CLIP_TYPE_REGISTRATIONS = TRUSTED_SEQUENCE_METADATA.map((metadata) => ({
  id: metadata.clipType,
  descriptor: buildSequenceDescriptor(metadata),
  metadata,
})) as readonly TrustedClipTypeRegistration[];

const TRUSTED_CLIP_TYPE_REGISTRATION_MAP = new Map(
  TRUSTED_CLIP_TYPE_REGISTRATIONS.map((registration) => [registration.id, registration]),
);

export const TRUSTED_CLIP_TYPE_METADATA = TRUSTED_CLIP_TYPE_REGISTRATIONS.map(
  (registration) => registration.metadata,
) as readonly TrustedClipTypeMetadata[];

export const TRUSTED_CLIP_TYPE_DESCRIPTORS = TRUSTED_CLIP_TYPE_REGISTRATIONS.map(
  (registration) => registration.descriptor,
) as readonly SequenceClipTypeDescriptor[];

export const TRUSTED_CLIP_TYPES = TRUSTED_CLIP_TYPE_REGISTRATIONS.map(
  (registration) => registration.id,
) as readonly TrustedSequenceClipType[];

export const isTrustedClipType = (
  value: unknown,
): value is TrustedSequenceClipType => {
  return typeof value === 'string' && TRUSTED_CLIP_TYPE_REGISTRATION_MAP.has(value);
};

export const getTrustedClipTypeRegistration = (
  clipType: string,
): TrustedClipTypeRegistration | undefined => {
  return TRUSTED_CLIP_TYPE_REGISTRATION_MAP.get(clipType);
};

export const getTrustedClipTypeDescriptor = (
  clipType: string,
): SequenceClipTypeDescriptor | undefined => {
  return getTrustedClipTypeRegistration(clipType)?.descriptor;
};

export const getTrustedClipTypeMetadata = (
  clipType: string,
): TrustedClipTypeMetadata | undefined => {
  return getTrustedClipTypeRegistration(clipType)?.metadata;
};

export const resolveTrustedClipTypeRegistration = (
  clipType: string | undefined,
): TrustedClipTypeLookupResult => {
  if (!clipType) {
    return { status: 'unknown', clipType };
  }
  const registration = getTrustedClipTypeRegistration(clipType);
  return registration
    ? { status: 'trusted', registration }
    : { status: 'unknown', clipType };
};

export const filterTrustedClipTypeRegistrationsForRegistry = (
  registry: Partial<Record<string, unknown>>,
): AvailableClipTypeRegistration[] => {
  return TRUSTED_CLIP_TYPE_REGISTRATIONS.flatMap((registration) => {
    if (!hasOwn(registry, registration.id)) {
      return [];
    }
    const componentEntry = registry[registration.id];
    if (!componentEntry) {
      return [];
    }
    return [{
      ...registration,
      id: registration.id,
      metadata: {
        ...registration.metadata,
        clipType: registration.id,
      },
      componentEntry,
    }];
  });
};

export const createAvailableClipTypeRegistry = (
  registry: Partial<Record<string, unknown>>,
): AvailableClipTypeRegistryView => {
  const registrations = filterTrustedClipTypeRegistrationsForRegistry(registry);
  const registrationMap = new Map(
    registrations.map((registration) => [registration.id, registration]),
  );

  const getAvailableClipTypeRegistration = (
    clipType: string,
  ): AvailableClipTypeRegistration | undefined => {
    return registrationMap.get(clipType);
  };

  const resolveAvailableClipTypeRegistration = (
    clipType: string | undefined,
  ): AvailableClipTypeLookupResult => {
    if (!clipType) {
      return { status: 'unknown', clipType };
    }
    const availableRegistration = getAvailableClipTypeRegistration(clipType);
    if (availableRegistration) {
      return { status: 'available', registration: availableRegistration };
    }
    const trustedRegistration = getTrustedClipTypeRegistration(clipType);
    if (trustedRegistration) {
      return { status: 'unavailable', registration: trustedRegistration };
    }
    return { status: 'unknown', clipType };
  };

  return {
    registrations,
    metadata: registrations.map((registration) => registration.metadata),
    descriptors: registrations.map((registration) => registration.descriptor),
    clipTypes: registrations.map((registration) => registration.id),
    isAvailableClipType: (value: unknown): value is string => (
      typeof value === 'string' && registrationMap.has(value)
    ),
    getAvailableClipTypeRegistration,
    getAvailableClipTypeDescriptor: (clipType: string) => getAvailableClipTypeRegistration(clipType)?.descriptor,
    getAvailableClipTypeMetadata: (clipType: string) => getAvailableClipTypeRegistration(clipType)?.metadata,
    resolveAvailableClipTypeRegistration,
  };
};

export const getTrustedSequenceParamDefinitions = (
  clipType: string | undefined,
): readonly ClipTypeSequenceParamDefinition[] => {
  const descriptor = clipType ? getTrustedClipTypeDescriptor(clipType) : undefined;
  if (!descriptor || !isSequenceParamsSchema(descriptor.paramsSchema)) {
    return [];
  }
  return descriptor.paramsSchema.params;
};
