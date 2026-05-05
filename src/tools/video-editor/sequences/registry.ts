import {
  THEME_PACKAGE_REGISTRY,
} from '@banodoco/timeline-composition/registry.generated';
import { getGeneratedRemotionModuleStatus, type GeneratedLaneClipShape } from '@/tools/video-editor/lib/generated-lanes';
import { BUILTIN_CLIP_TYPES } from '@/tools/video-editor/types';
import {
  AVAILABLE_TIMELINE_THEME_IDS,
  INSTALLED_TIMELINE_THEMES,
} from '@/tools/video-editor/compositions/installed-themes';
import {
  TRUSTED_SEQUENCE_METADATA,
  type SequenceCapabilityOverrides,
  type TrustedSequenceMetadata,
} from '@/tools/video-editor/sequences/metadata';
import { ImageJumpSequence } from '@/tools/video-editor/sequences/components/ImageJumpSequence';
import { TitleCardSequence } from '@/tools/video-editor/sequences/components/TitleCardSequence';
import { createAvailableClipTypeRegistry } from '@/tools/video-editor/clip-types';

export type SequenceComponentRegistryEntry = {
  component?: unknown;
  themeId?: string;
  source?: string;
};

export type SequenceComponentRegistryShape = Partial<Record<string, SequenceComponentRegistryEntry | undefined>>;

export type ClipCapabilitySource =
  | 'builtin'
  | 'trusted-local-sequence'
  | 'installed-sequence'
  | 'registry-discovered'
  | 'generated-module'
  | 'db-sequence-component';

export interface ClipCapabilityDescriptor {
  clipType: string;
  source: ClipCapabilitySource;
  metadata?: TrustedSequenceMetadata;
  registryEntry?: SequenceComponentRegistryEntry;
  capabilities: {
    preview: 'browser' | 'placeholder';
    previewFallbackReason?: 'worker_only' | 'unsupported';
    browserRender: boolean;
    workerRender: boolean;
    externalRender: boolean;
  };
}

const BUILTIN_CAPABILITIES: ClipCapabilityDescriptor['capabilities'] = {
  preview: 'browser',
  browserRender: true,
  workerRender: false,
  externalRender: false,
};

const DEFAULT_SEQUENCE_CAPABILITIES: ClipCapabilityDescriptor['capabilities'] = {
  preview: 'browser',
  browserRender: false,
  workerRender: true,
  externalRender: false,
};

const GENERATED_MODULE_CAPABILITIES: ClipCapabilityDescriptor['capabilities'] = {
  preview: 'placeholder',
  previewFallbackReason: 'worker_only',
  browserRender: false,
  workerRender: true,
  externalRender: false,
};

function applyCapabilityOverrides(
  defaults: ClipCapabilityDescriptor['capabilities'],
  overrides?: SequenceCapabilityOverrides,
): ClipCapabilityDescriptor['capabilities'] {
  if (!overrides) {
    return defaults;
  }

  return {
    ...defaults,
    ...(overrides.preview !== undefined ? { preview: overrides.preview } : {}),
    ...(overrides.previewFallbackReason !== undefined
      ? { previewFallbackReason: overrides.previewFallbackReason }
      : {}),
    ...(overrides.browserRender !== undefined ? { browserRender: overrides.browserRender } : {}),
    ...(overrides.workerRender !== undefined ? { workerRender: overrides.workerRender } : {}),
    ...(overrides.externalRender !== undefined ? { externalRender: overrides.externalRender } : {}),
  };
}

function getTrustedMetadataMap(): Record<string, TrustedSequenceMetadata> {
  return Object.fromEntries(TRUSTED_SEQUENCE_METADATA.map((metadata) => [metadata.clipType, metadata]));
}

export const LOCAL_SEQUENCE_REGISTRY = {
  'image-jump': {
    component: ImageJumpSequence,
    themeId: '2rp',
    source: 'local:reigh',
  },
  'title-card': {
    component: TitleCardSequence,
    themeId: '2rp',
    source: 'local:reigh',
  },
} as const satisfies SequenceComponentRegistryShape;

export const SEQUENCE_COMPONENT_REGISTRY = {
  ...THEME_PACKAGE_REGISTRY,
  ...LOCAL_SEQUENCE_REGISTRY,
} as const satisfies SequenceComponentRegistryShape;

export type AvailableSequenceMetadata = TrustedSequenceMetadata & {
  clipType: keyof typeof SEQUENCE_COMPONENT_REGISTRY;
};

export const filterTrustedSequenceMetadataForRegistry = (
  registry: Partial<Record<string, unknown>>,
  themeRegistry: Partial<Record<string, unknown>> = INSTALLED_TIMELINE_THEMES,
): AvailableSequenceMetadata[] => {
  return TRUSTED_SEQUENCE_METADATA.filter((metadata): metadata is AvailableSequenceMetadata => {
    return Object.prototype.hasOwnProperty.call(registry, metadata.clipType)
      && Object.prototype.hasOwnProperty.call(themeRegistry, metadata.themeId);
  });
};

export function buildSequenceClipCapabilityRegistry(
  registry: SequenceComponentRegistryShape,
): Record<string, ClipCapabilityDescriptor> {
  const trustedMetadataByClipType = getTrustedMetadataMap();

  return Object.fromEntries(
    Object.entries(registry)
      .filter(([, entry]): entry is SequenceComponentRegistryEntry => Boolean(entry))
      .map(([clipType, entry]) => {
        const metadata = trustedMetadataByClipType[clipType];
        const isLocal = Object.prototype.hasOwnProperty.call(LOCAL_SEQUENCE_REGISTRY, clipType)
          || entry.source?.startsWith('local:') === true;

        const source: ClipCapabilitySource = metadata
          ? (isLocal ? 'trusted-local-sequence' : 'installed-sequence')
          : 'registry-discovered';

        const capabilities = applyCapabilityOverrides(
          DEFAULT_SEQUENCE_CAPABILITIES,
          metadata?.capabilities,
        );

        return [clipType, {
          clipType,
          source,
          metadata,
          registryEntry: entry,
          capabilities,
        } satisfies ClipCapabilityDescriptor];
      }),
  );
}

function buildBuiltinClipCapabilityRegistry(): Record<string, ClipCapabilityDescriptor> {
  return Object.fromEntries(
    BUILTIN_CLIP_TYPES.map((clipType) => [clipType, {
      clipType,
      source: 'builtin',
      capabilities: BUILTIN_CAPABILITIES,
    } satisfies ClipCapabilityDescriptor]),
  );
}

export const BUILTIN_CLIP_CAPABILITY_REGISTRY = buildBuiltinClipCapabilityRegistry();

export const SEQUENCE_CLIP_CAPABILITY_REGISTRY = buildSequenceClipCapabilityRegistry(
  SEQUENCE_COMPONENT_REGISTRY,
);

export const CLIP_CAPABILITY_REGISTRY: Record<string, ClipCapabilityDescriptor> = {
  ...BUILTIN_CLIP_CAPABILITY_REGISTRY,
  ...SEQUENCE_CLIP_CAPABILITY_REGISTRY,
};

export const GENERATED_MODULE_CLIP_CAPABILITY: ClipCapabilityDescriptor = {
  clipType: '__generated-module__',
  source: 'generated-module',
  capabilities: GENERATED_MODULE_CAPABILITIES,
};

export const AVAILABLE_SEQUENCE_METADATA = filterTrustedSequenceMetadataForRegistry(
  SEQUENCE_COMPONENT_REGISTRY,
);

export const AVAILABLE_SEQUENCE_CLIP_TYPES = AVAILABLE_SEQUENCE_METADATA.map(
  (metadata) => metadata.clipType,
) as readonly string[];

export const AVAILABLE_SEQUENCE_THEME_IDS = AVAILABLE_TIMELINE_THEME_IDS.filter((themeId) => (
  AVAILABLE_SEQUENCE_METADATA.some((metadata) => metadata.themeId === themeId)
)) as readonly string[];

const AVAILABLE_CLIP_TYPE_REGISTRY_VIEW = createAvailableClipTypeRegistry(SEQUENCE_COMPONENT_REGISTRY);

export const isAvailableSequenceClipType = (value: unknown): value is AvailableSequenceMetadata['clipType'] => {
  return typeof value === 'string' && (AVAILABLE_SEQUENCE_CLIP_TYPES as readonly string[]).includes(value);
};

export const getAvailableSequenceMetadata = (
  clipType: string,
): AvailableSequenceMetadata | undefined => {
  return AVAILABLE_SEQUENCE_METADATA.find((metadata) => metadata.clipType === clipType);
};

export const getAvailableClipTypeDescriptor = (
  clipType: string,
) => AVAILABLE_CLIP_TYPE_REGISTRY_VIEW.getAvailableClipTypeDescriptor(clipType);

export const resolveAvailableClipType = (
  clipType: string | undefined,
):
  | { status: 'available'; metadata: AvailableSequenceMetadata }
  | { status: 'unavailable'; metadata: TrustedSequenceMetadata }
  | { status: 'unknown'; clipType: string | undefined } => {
  if (!clipType) {
    return { status: 'unknown', clipType };
  }

  const available = getAvailableSequenceMetadata(clipType);
  if (available) {
    return { status: 'available', metadata: available };
  }

  const trusted = TRUSTED_SEQUENCE_METADATA.find((metadata) => metadata.clipType === clipType);
  if (trusted) {
    return { status: 'unavailable', metadata: trusted };
  }

  return { status: 'unknown', clipType };
};

export const getClipCapabilityDescriptor = (
  clipType: string | undefined,
): ClipCapabilityDescriptor | undefined => {
  if (typeof clipType !== 'string') {
    return undefined;
  }

  return CLIP_CAPABILITY_REGISTRY[clipType];
};

export const describeClipCapability = (
  clip: GeneratedLaneClipShape & { clipType?: string } | null | undefined,
): ClipCapabilityDescriptor | undefined => {
  const moduleStatus = getGeneratedRemotionModuleStatus(clip);
  if (moduleStatus.kind !== 'not_module') {
    return GENERATED_MODULE_CLIP_CAPABILITY;
  }

  return getClipCapabilityDescriptor(clip?.clipType);
};

// ─── Dynamic (DB-stored sequence component) resolvers ────────────────
//
// MVP scope notes (FLAG-001/002 wiring + capabilityManifest scope):
// - DB-stored sequences are stored in the dynamic registry under their
//   plain clipType (e.g. `my-pulse`); referenced from timeline JSON as
//   `custom:my-pulse`. The dynamic-aware resolvers below strip the
//   `custom:` prefix on lookup, mirroring DynamicComponentRegistry's
//   default normalizeName.
// - DB entries always emit `{ preview: 'browser', browserRender: true,
//   workerRender: false, externalRender: false }` because the worker
//   cannot compile arbitrary user-authored TSX yet (see Section 4 of
//   the reuse plan: "force `workerRender:false` for DB-stored rows").
// - capabilityManifest.ts is built at module load and can NOT reflect
//   DB rows. MVP scope decision: keep that static manifest for built-ins
//   only; DB-aware capability lookups go through these resolvers in
//   React-hosted code paths only. If a non-React caller ever needs to
//   resolve a DB-stored clipType, plumb the dynamic registry through
//   explicitly rather than mutating the static manifest.
// - FLAG-003 divergence (intentional): the effects side uses a module-
//   level singleton + `lookupEffect()` (effects/index.tsx:80-110) but
//   sequences use a React context with `useSyncExternalStore`. Do NOT
//   rewrite the effects side to match — keep them divergent for MVP.

import type { FC } from 'react';

export interface DynamicSequenceComponentEntry {
  clipType: string;
  component: FC<{
    clip: ResolvedTimelineClipForDynamic;
    params?: Record<string, unknown>;
    theme?: unknown;
    fps: number;
  }>;
  schemaJson?: object;
  themeId?: string;
}

// Local type alias to avoid a circular dependency with `@/tools/video-editor/types`.
type ResolvedTimelineClipForDynamic = {
  id: string;
  clipType?: string;
  params?: Record<string, unknown>;
} & Record<string, unknown>;

const DB_SEQUENCE_COMPONENT_CAPABILITIES: ClipCapabilityDescriptor['capabilities'] = {
  preview: 'browser',
  browserRender: true,
  workerRender: false,
  externalRender: false,
};

const CUSTOM_PREFIX = 'custom:';

function stripCustomPrefix(clipType: string | undefined): string | undefined {
  if (typeof clipType !== 'string') return undefined;
  return clipType.startsWith(CUSTOM_PREFIX) ? clipType.slice(CUSTOM_PREFIX.length) : clipType;
}

/**
 * Resolve a clipType to a DB-stored dynamic entry, preferring the dynamic
 * registry when the clipType uses the `custom:` prefix. Returns undefined
 * if no dynamic entry matches (caller should fall back to the static
 * SEQUENCE_COMPONENT_REGISTRY lookup).
 */
export function resolveSequenceClipEntry(
  clipType: string | undefined,
  dynamic: readonly DynamicSequenceComponentEntry[] | undefined,
): DynamicSequenceComponentEntry | undefined {
  if (!clipType || !dynamic || dynamic.length === 0) return undefined;
  const normalized = stripCustomPrefix(clipType);
  if (!normalized) return undefined;
  // Only resolve dynamic entries when the clipType actually used the
  // `custom:` prefix OR matches a dynamic entry's plain clipType. This
  // keeps built-in clipTypes routed through the static registry.
  const isCustom = clipType.startsWith(CUSTOM_PREFIX);
  for (const entry of dynamic) {
    if (entry.clipType === normalized) {
      // Prefer the dynamic match for `custom:` lookups; for plain
      // clipTypes, only return the dynamic entry if no static entry
      // exists (caller still controls priority via the helpers below).
      if (isCustom) return entry;
      if (!Object.prototype.hasOwnProperty.call(SEQUENCE_COMPONENT_REGISTRY, normalized)) {
        return entry;
      }
    }
  }
  return undefined;
}

/**
 * Dynamic-aware capability descriptor lookup. DB-stored sequence components
 * always surface `workerRender: false` per the MVP scope decision.
 */
export function resolveClipCapabilityDescriptor(
  clipType: string | undefined,
  dynamic: readonly DynamicSequenceComponentEntry[] | undefined,
): ClipCapabilityDescriptor | undefined {
  if (typeof clipType !== 'string') return undefined;
  const dynamicEntry = resolveSequenceClipEntry(clipType, dynamic);
  if (dynamicEntry) {
    return {
      clipType: dynamicEntry.clipType,
      source: 'db-sequence-component',
      capabilities: DB_SEQUENCE_COMPONENT_CAPABILITIES,
    };
  }
  return CLIP_CAPABILITY_REGISTRY[clipType];
}

/**
 * Dynamic-aware variant of `describeClipCapability`. Generated-module
 * placeholder takes precedence (worker-only render path), then DB
 * entries (browser-only), then the static registry.
 */
export function describeClipCapabilityWith(
  clip: GeneratedLaneClipShape & { clipType?: string } | null | undefined,
  dynamic: readonly DynamicSequenceComponentEntry[] | undefined,
): ClipCapabilityDescriptor | undefined {
  const moduleStatus = getGeneratedRemotionModuleStatus(clip);
  if (moduleStatus.kind !== 'not_module') {
    return GENERATED_MODULE_CLIP_CAPABILITY;
  }
  return resolveClipCapabilityDescriptor(clip?.clipType, dynamic);
}
