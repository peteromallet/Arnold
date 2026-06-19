import {
  defineClipType,
  isSequenceParamsSchema,
  type ClipTypeDescriptor,
  type ClipTypeHoldSupport,
  type ClipTypeSequenceParamDefinition,
} from './defineClipType.ts';
import {
  TRUSTED_SEQUENCE_METADATA,
  type TrustedSequenceClipType,
  type TrustedSequenceMetadata,
} from '../sequences/metadata.ts';

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

// ---------------------------------------------------------------------------
// Dynamic-aware resolution (M9 T6)
// ---------------------------------------------------------------------------

/**
 * Result of resolving a clip type against built-ins, trusted sequence
 * descriptors, and dynamic extension records with deterministic precedence
 * (builtins > trusted sequences > extensions).
 *
 * Duplicate detection fires when an extension record claims the same
 * `clipTypeId` as a built-in or trusted sequence descriptor, surfacing
 * the conflicting extension IDs for diagnostics.
 */
export type DynamicClipTypeResolutionResult =
  | { status: 'available'; clipType: string; source: 'builtin' }
  | { status: 'available'; clipType: string; source: 'trusted-sequence'; descriptor: SequenceClipTypeDescriptor; metadata: TrustedClipTypeMetadata }
  | { status: 'available'; clipType: string; source: 'extension'; extensionRecord: Record<string, unknown> }
  | { status: 'unavailable'; clipType: string; source: 'trusted-sequence'; descriptor: SequenceClipTypeDescriptor; metadata: TrustedClipTypeMetadata }
  | { status: 'duplicate'; clipType: string; source: 'trusted-sequence'; descriptor: SequenceClipTypeDescriptor; metadata: TrustedClipTypeMetadata; duplicateExtensionIds: readonly string[] }
  | { status: 'unknown'; clipType: string | undefined };

/**
 * Lightweight shape expected from a dynamic extension record for resolution.
 * Accepts either full ClipTypeRegistryRecord or a minimal subset.
 */
export interface DynamicExtensionClipRecord {
  readonly clipTypeId: string;
  readonly ownerExtensionId?: string;
  readonly [key: string]: unknown;
}

/**
 * Build a dynamic-aware resolution view that merges built-ins (caller provides
 * the set of built-in clip type IDs), trusted-sequence descriptors, and
 * extension clip records with deterministic precedence.
 *
 * Precedence (first-match-wins):
 * 1. Built-in clip types (e.g. 'media', 'hold', 'text', 'effect-layer')
 * 2. Trusted-sequence descriptors
 * 3. Extension records
 *
 * When an extension record shares a `clipTypeId` with a trusted-sequence
 * descriptor, the resolution returns `duplicate` status with the conflicting
 * extension IDs surfaced for diagnostics.
 *
 * Unknown clip types (not in any source) return `unknown` status.
 */
export function resolveDynamicClipType(
  clipType: string | undefined,
  builtinClipTypeIds: ReadonlySet<string>,
  extensionRecords: readonly DynamicExtensionClipRecord[] | undefined,
): DynamicClipTypeResolutionResult {
  if (!clipType) {
    return { status: 'unknown', clipType };
  }

  // 1. Built-ins take highest precedence
  if (builtinClipTypeIds.has(clipType)) {
    return { status: 'available', clipType, source: 'builtin' };
  }

  // 2. Trusted-sequence descriptors
  const trustedRegistration = getTrustedClipTypeRegistration(clipType);

  // 3. Check extension records for duplicates against trusted
  const matchingExtensions = (extensionRecords ?? []).filter(
    (record) => record.clipTypeId === clipType,
  );

  if (trustedRegistration && matchingExtensions.length > 0) {
    // Duplicate: both trusted and extension claim this clipTypeId
    return {
      status: 'duplicate',
      clipType,
      source: 'trusted-sequence',
      descriptor: trustedRegistration.descriptor,
      metadata: trustedRegistration.metadata,
      duplicateExtensionIds: matchingExtensions.map(
        (record) => record.ownerExtensionId ?? '(unknown)',
      ),
    };
  }

  if (trustedRegistration) {
    // Trusted-sequence descriptor exists — available (has component rendering)
    // or unavailable based on whether it was registered in the available view.
    // At this resolution layer, trusted descriptors are always "available" in
    // the sense that their metadata/descriptor is known. The
    // "unavailable" distinction (trusted but component not in build) is
    // handled by the caller when it checks the sequence component registry.
    return {
      status: 'available',
      clipType,
      source: 'trusted-sequence',
      descriptor: trustedRegistration.descriptor,
      metadata: trustedRegistration.metadata,
    };
  }

  // 4. Extension records
  if (matchingExtensions.length > 0) {
    // If multiple extensions claim the same clipTypeId, the first one wins
    // (the ClipTypeRegistry already emitted duplicate diagnostics).
    return {
      status: 'available',
      clipType,
      source: 'extension',
      extensionRecord: matchingExtensions[0]! as Record<string, unknown>,
    };
  }

  // 5. Unknown
  return { status: 'unknown', clipType };
}

/**
 * Resolve a clip type for descriptor-only consumers that do not need
 * the full extension record payload. Returns the ClipTypeDescriptor
 * for built-ins and trusted sequences, or undefined for extensions
 * and unknowns.
 */
export function resolveDynamicClipTypeDescriptor(
  clipType: string | undefined,
  builtinClipTypeIds: ReadonlySet<string>,
  _extensionRecords: readonly DynamicExtensionClipRecord[] | undefined,
): ClipTypeDescriptor | undefined {
  if (!clipType) return undefined;

  // Built-ins are not in this module; caller provides via getBuiltinClipTypeDescriptor
  // Trusted sequences
  const trusted = getTrustedClipTypeDescriptor(clipType);
  if (trusted) return trusted;

  return undefined;
}
