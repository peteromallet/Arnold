/**
 * M9: Provider-scoped clip-type registry for contributed extension clip types.
 *
 * Follows the same ownership / lifecycle / snapshot / freeze / dispose
 * pattern as the EffectRegistry so consumers (activation, UI, render,
 * export) get a consistent integration surface.
 */

import type {
  DisposeHandle,
  ExtensionDiagnostic,
  DiagnosticSeverity,
  LiveChannelDescriptor,
  LiveChannelMetadata,
  LiveSample,
  LiveSource,
} from '@reigh/editor-sdk';
import type {
  ContributionRenderability,
  RenderCapability,
  DeterminismStatus,
} from '@/tools/video-editor/runtime/renderability.ts';
import type {
  TimelineLiveBinding,
  TimelineLiveBindingResolutionStatus,
  TimelineLiveDeterministicRef,
} from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Record status, matching the EffectRegistry vocabulary. */
export type ClipTypeRegistryRecordStatus = 'active' | 'inactive' | 'error';

export interface ClipRendererLiveBinding {
  readonly bindingId: string;
  readonly sourceId: string;
  readonly channelId?: string;
  readonly targetParamName?: string;
  readonly status: TimelineLiveBindingResolutionStatus;
  readonly binding: TimelineLiveBinding;
  readonly deterministicRefs: readonly TimelineLiveDeterministicRef[];
  readonly diagnostics: readonly {
    readonly severity: 'info' | 'warning' | 'error';
    readonly code: string;
    readonly message: string;
    readonly path: string;
  }[];
}

/**
 * Synchronous live data read facade for renderers.
 *
 * Helpers are source-ID first so extension renderers do not depend on transient
 * registry/channel object identity. They intentionally return values directly,
 * never promises, to keep React/Remotion rendering synchronous.
 */
export interface ClipRendererLiveProps {
  readonly bindings: readonly ClipRendererLiveBinding[];
  readonly diagnostics: readonly ClipRendererLiveBinding['diagnostics'][number][];
  readonly getSource: (sourceId: string) => LiveSource | undefined;
  readonly getChannelMetadata: (
    sourceId: string,
    channelId?: string,
  ) => LiveChannelMetadata | undefined;
  readonly readLatestSample: (sourceId: string, channelId?: string) => LiveSample | undefined;
  readonly readSampleAt: (
    sourceId: string,
    sequenceNumber: number,
    channelId?: string,
  ) => LiveSample | undefined;
  readonly readSamples: (sourceId: string, channelId?: string) => readonly LiveSample[];
  readonly getSampleCount: (sourceId: string, channelId?: string) => number;
  /**
   * Escape hatch for integrations that need to persist a descriptor in
   * renderer-owned state. Reads should still use the source-ID helpers above.
   */
  readonly resolveChannelId: (sourceId: string, channelId?: string) => LiveChannelDescriptor | undefined;
}

/**
 * Props the host passes to an extension clip renderer.
 *
 * The host interpolates keyframes before constructing these props so
 * extension renderers never need to implement interpolation themselves.
 */
export interface ClipRendererProps {
  readonly clipId: string;
  readonly clipTypeId: string;
  readonly time: number;
  readonly params: Record<string, unknown>;
  readonly width: number;
  readonly height: number;
  readonly live: ClipRendererLiveProps;
}

/**
 * Props the host passes to an extension clip inspector.
 */
export interface ClipInspectorProps {
  readonly clipId: string;
  readonly clipTypeId: string;
  readonly params: Record<string, unknown>;
  readonly onParamsChange: (params: Record<string, unknown>) => void;
}

/** A single record in the provider-scoped clip-type registry. */
export interface ClipTypeRegistryRecord {
  readonly clipTypeId: string;
  readonly contributionId: string;
  readonly renderer: Record<string, unknown> | ((...args: unknown[]) => unknown);
  readonly inspector?: Record<string, unknown> | ((...args: unknown[]) => unknown);
  readonly schema?: ReadonlyArray<{
    readonly name: string;
    readonly label: string;
    readonly description: string;
    readonly type: 'number' | 'select' | 'boolean' | 'color' | 'audio-binding';
    readonly default?: number | string | boolean | Record<string, unknown>;
    readonly min?: number;
    readonly max?: number;
    readonly step?: number;
    readonly options?: readonly { label: string; value: string }[];
  }>;
  readonly ownerExtensionId?: string;
  readonly renderability: ContributionRenderability;
  readonly status: ClipTypeRegistryRecordStatus;
  readonly diagnostics?: readonly ExtensionDiagnostic[];
  readonly dispose?: DisposeHandle['dispose'];
}

/** Immutable snapshot of registry state for consumers. */
export interface ClipTypeRegistrySnapshot {
  readonly records: readonly ClipTypeRegistryRecord[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
  readonly get: (clipTypeId: string) => ClipTypeRegistryRecord | undefined;
  readonly has: (clipTypeId: string) => boolean;
}

export type ClipTypeRegistrySubscriber = (snapshot: ClipTypeRegistrySnapshot) => void;

/** Provider-scoped mutable clip-type registry. */
export interface ClipTypeRegistry {
  register(record: ClipTypeRegistryRecord): DisposeHandle;
  updateRecord(
    clipTypeId: string,
    updater: (current: ClipTypeRegistryRecord) => ClipTypeRegistryRecord,
    newDispose?: DisposeHandle['dispose'],
  ): DisposeHandle;
  unregister(clipTypeId: string): void;
  unregisterOwner(ownerExtensionId: string): void;
  resolve(clipTypeId: string): ClipTypeRegistryRecord | undefined;
  subscribe(subscriber: ClipTypeRegistrySubscriber): DisposeHandle;
  getSnapshot(): ClipTypeRegistrySnapshot;
  dispose(): void;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

interface InternalRecord {
  readonly token: symbol;
  readonly record: ClipTypeRegistryRecord;
  disposed: boolean;
}

function emitDiagnostic(
  diagnostics: ExtensionDiagnostic[],
  severity: DiagnosticSeverity,
  code: string,
  message: string,
  extensionId?: string,
  contributionId?: string,
  detail?: Record<string, unknown>,
): void {
  diagnostics.push(Object.freeze({
    severity,
    code,
    message,
    ...(extensionId ? { extensionId } : {}),
    ...(contributionId ? { contributionId } : {}),
    ...(detail ? { detail } : {}),
  }));
}

function safeDispose(entry: InternalRecord, diagnostics: ExtensionDiagnostic[]): void {
  if (entry.disposed) return;
  entry.disposed = true;

  try {
    entry.record.dispose?.();
  } catch (error) {
    emitDiagnostic(
      diagnostics,
      'error',
      'clip-type-registry/dispose-failed',
      `Clip type "${entry.record.clipTypeId}" dispose failed: ${String(error)}`,
      entry.record.ownerExtensionId,
      entry.record.contributionId,
      { clipTypeId: entry.record.clipTypeId },
    );
  }
}

function freezeDiagnostics(
  diagnostics: readonly ExtensionDiagnostic[] | undefined,
): readonly ExtensionDiagnostic[] {
  return Object.freeze([...(diagnostics ?? [])].map((d) => Object.freeze({ ...d })));
}

function freezeRenderability(
  renderability: ContributionRenderability,
): ContributionRenderability {
  return Object.freeze({
    ...renderability,
    capabilities: Object.freeze(
      renderability.capabilities.map((c) => Object.freeze({ ...c })),
    ),
    ...(renderability.blockers
      ? {
          blockers: Object.freeze(
            renderability.blockers.map((b) => Object.freeze({ ...b })),
          ),
        }
      : {}),
  });
}

function freezeRecord(record: ClipTypeRegistryRecord): ClipTypeRegistryRecord {
  return Object.freeze({
    ...record,
    renderability: freezeRenderability(record.renderability),
    ...(record.diagnostics ? { diagnostics: freezeDiagnostics(record.diagnostics) } : {}),
  });
}

function sortEntries(entries: InternalRecord[]): InternalRecord[] {
  return [...entries].sort((a, b) => {
    const ownerA = a.record.ownerExtensionId ?? '';
    const ownerB = b.record.ownerExtensionId ?? '';
    const ownerCmp = ownerA.localeCompare(ownerB);
    if (ownerCmp !== 0) return ownerCmp;
    return a.record.clipTypeId.localeCompare(b.record.clipTypeId);
  });
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a new provider-scoped clip-type registry.
 *
 * The returned registry manages contributed extension clip types with
 * ownership, lifecycle, snapshots, and diagnostics matching the
 * EffectRegistry pattern.
 */
export function createClipTypeRegistry(): ClipTypeRegistry {
  const records = new Map<string, InternalRecord>();
  const subscribers = new Set<ClipTypeRegistrySubscriber>();
  const diagnostics: ExtensionDiagnostic[] = [];

  let frozenSnapshot: ClipTypeRegistrySnapshot | null = null;
  let disposed = false;

  function invalidateSnapshot(): void {
    frozenSnapshot = null;
  }

  function getSnapshot(): ClipTypeRegistrySnapshot {
    if (frozenSnapshot) return frozenSnapshot;

    const snapshotRecords = Object.freeze(
      sortEntries([...records.values()]).map((entry) => entry.record),
    );

    frozenSnapshot = Object.freeze({
      records: snapshotRecords,
      diagnostics: Object.freeze([...diagnostics]),
      get: (clipTypeId: string) => records.get(clipTypeId)?.record,
      has: (clipTypeId: string) => records.has(clipTypeId),
    });

    return frozenSnapshot;
  }

  function notifySubscribers(): void {
    const snapshot = getSnapshot();
    subscribers.forEach((subscriber) => {
      try {
        subscriber(snapshot);
      } catch {
        // Subscriber failures are isolated from registry lifecycle work.
      }
    });
  }

  function guardDisposed(operation: string): boolean {
    if (!disposed) return false;
    emitDiagnostic(
      diagnostics,
      'warning',
      'clip-type-registry/disposed',
      `ClipTypeRegistry operation "${operation}" called after dispose.`,
    );
    invalidateSnapshot();
    return true;
  }

  function removeEntry(clipTypeId: string, expectedToken?: symbol): void {
    const existing = records.get(clipTypeId);
    if (!existing || (expectedToken && existing.token !== expectedToken)) return;

    records.delete(clipTypeId);
    safeDispose(existing, diagnostics);
    invalidateSnapshot();
    notifySubscribers();
  }

  function register(record: ClipTypeRegistryRecord): DisposeHandle {
    if (guardDisposed('register')) {
      return { dispose(): void {} };
    }

    const frozenRecord = freezeRecord(record);
    const existing = records.get(frozenRecord.clipTypeId);

    if (existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'clip-type-registry/duplicate-clip-type',
        `Clip type "${frozenRecord.clipTypeId}" is already registered. The previous record will be replaced.`,
        frozenRecord.ownerExtensionId,
        frozenRecord.contributionId,
        {
          clipTypeId: frozenRecord.clipTypeId,
          previousOwnerExtensionId: existing.record.ownerExtensionId,
          previousContributionId: existing.record.contributionId,
        },
      );
      safeDispose(existing, diagnostics);
    }

    const token = Symbol(frozenRecord.clipTypeId);
    records.set(frozenRecord.clipTypeId, {
      token,
      record: frozenRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(frozenRecord.clipTypeId, token);
      },
    };
  }

  function updateRecord(
    clipTypeId: string,
    updater: (current: ClipTypeRegistryRecord) => ClipTypeRegistryRecord,
    newDispose?: DisposeHandle['dispose'],
  ): DisposeHandle {
    if (guardDisposed('updateRecord')) {
      return { dispose(): void {} };
    }

    const existing = records.get(clipTypeId);
    if (!existing) {
      emitDiagnostic(
        diagnostics,
        'warning',
        'clip-type-registry/update-missing-clip-type',
        `Clip type "${clipTypeId}" cannot be updated because it is not registered.`,
        undefined,
        undefined,
        { clipTypeId },
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    const nextRecord = freezeRecord({
      ...updater(existing.record),
      ...(newDispose ? { dispose: newDispose } : {}),
    });

    if (nextRecord.clipTypeId !== clipTypeId) {
      emitDiagnostic(
        diagnostics,
        'error',
        'clip-type-registry/update-clip-type-id-mismatch',
        `Clip type "${clipTypeId}" update returned mismatched clip type ID "${nextRecord.clipTypeId}".`,
        nextRecord.ownerExtensionId,
        nextRecord.contributionId,
        { clipTypeId, nextClipTypeId: nextRecord.clipTypeId },
      );
      invalidateSnapshot();
      notifySubscribers();
      return { dispose(): void {} };
    }

    safeDispose(existing, diagnostics);

    const token = Symbol(clipTypeId);
    records.set(clipTypeId, {
      token,
      record: nextRecord,
      disposed: false,
    });

    invalidateSnapshot();
    notifySubscribers();

    return {
      dispose(): void {
        removeEntry(clipTypeId, token);
      },
    };
  }

  function unregister(clipTypeId: string): void {
    if (guardDisposed('unregister')) return;
    removeEntry(clipTypeId);
  }

  function unregisterOwner(ownerExtensionId: string): void {
    if (guardDisposed('unregisterOwner')) return;

    const owned = [...records.values()].filter(
      (entry) => entry.record.ownerExtensionId === ownerExtensionId,
    );
    if (owned.length === 0) return;

    owned.forEach((entry) => {
      records.delete(entry.record.clipTypeId);
      safeDispose(entry, diagnostics);
    });

    invalidateSnapshot();
    notifySubscribers();
  }

  function resolve(clipTypeId: string): ClipTypeRegistryRecord | undefined {
    return records.get(clipTypeId)?.record;
  }

  function subscribe(subscriber: ClipTypeRegistrySubscriber): DisposeHandle {
    subscribers.add(subscriber);
    return {
      dispose(): void {
        subscribers.delete(subscriber);
      },
    };
  }

  function dispose(): void {
    if (disposed) return;
    disposed = true;

    const entries = [...records.values()];
    records.clear();
    entries.forEach((entry) => safeDispose(entry, diagnostics));
    invalidateSnapshot();
    notifySubscribers();
    subscribers.clear();
  }

  return {
    register,
    updateRecord,
    unregister,
    unregisterOwner,
    resolve,
    subscribe,
    getSnapshot,
    dispose,
  };
}

// ---------------------------------------------------------------------------
// Snapshot / standalone resolver helpers
// ---------------------------------------------------------------------------

/**
 * Resolve a clip type from the live registry.
 * Standalone convenience wrapper around registry.resolve().
 */
export function resolveClipType(
  registry: ClipTypeRegistry,
  clipTypeId: string,
): ClipTypeRegistryRecord | undefined {
  return registry.resolve(clipTypeId);
}

/**
 * Resolve a clip type from an immutable snapshot.
 * Useful for render/export paths that consume snapshots.
 */
export function resolveSnapshotClipType(
  snapshot: ClipTypeRegistrySnapshot,
  clipTypeId: string,
): ClipTypeRegistryRecord | undefined {
  return snapshot.get(clipTypeId);
}

// ---------------------------------------------------------------------------
// Parameter schema validation
// ---------------------------------------------------------------------------

const VALID_CLIP_PARAMETER_TYPES = new Set<string>([
  'number',
  'select',
  'boolean',
  'color',
  'audio-binding',
]);

/**
 * Validate a clip-type parameter schema at registration time.
 *
 * Returns diagnostics for each invalid parameter definition.
 * An empty array means the schema is valid.
 */
export function validateClipTypeParameterSchema(
  schema: ReadonlyArray<{
    name: string;
    label: string;
    description: string;
    type: string;
    default?: unknown;
    min?: unknown;
    max?: unknown;
    step?: unknown;
    options?: unknown;
  }> | undefined,
): ExtensionDiagnostic[] {
  if (!schema || !Array.isArray(schema)) return [];

  const diags: ExtensionDiagnostic[] = [];

  for (let i = 0; i < schema.length; i++) {
    const def = schema[i]!;
    const ctx = `parameter[${i}]`;

    // name: required, non-empty string
    if (typeof def.name !== 'string' || def.name.length === 0) {
      diags.push({
        severity: 'error',
        code: 'clip-types/invalid-schema-name',
        message: `${ctx}: name must be a non-empty string.`,
        detail: { index: i, field: 'name', value: def.name },
      });
    }

    // label: required, non-empty string
    if (typeof def.label !== 'string' || def.label.length === 0) {
      diags.push({
        severity: 'error',
        code: 'clip-types/invalid-schema-label',
        message: `${ctx}: label must be a non-empty string.`,
        detail: { index: i, field: 'label', value: def.label },
      });
    }

    // type: must be a valid parameter type
    if (!VALID_CLIP_PARAMETER_TYPES.has(def.type)) {
      diags.push({
        severity: 'error',
        code: 'clip-types/invalid-schema-type',
        message: `${ctx}: type must be one of ${[...VALID_CLIP_PARAMETER_TYPES].join(', ')}.`,
        detail: { index: i, field: 'type', value: def.type },
      });
    }

    // number type: default/min/max/step must be numbers if present
    if (def.type === 'number') {
      if (def.default !== undefined && typeof def.default !== 'number') {
        diags.push({
          severity: 'error',
          code: 'clip-types/invalid-schema-default',
          message: `${ctx}: default must be a number for type 'number'.`,
          detail: { index: i, field: 'default', value: def.default },
        });
      }
      if (def.min !== undefined && typeof def.min !== 'number') {
        diags.push({
          severity: 'error',
          code: 'clip-types/invalid-schema-min',
          message: `${ctx}: min must be a number.`,
          detail: { index: i, field: 'min', value: def.min },
        });
      }
      if (def.max !== undefined && typeof def.max !== 'number') {
        diags.push({
          severity: 'error',
          code: 'clip-types/invalid-schema-max',
          message: `${ctx}: max must be a number.`,
          detail: { index: i, field: 'max', value: def.max },
        });
      }
      if (def.step !== undefined && typeof def.step !== 'number') {
        diags.push({
          severity: 'error',
          code: 'clip-types/invalid-schema-step',
          message: `${ctx}: step must be a number.`,
          detail: { index: i, field: 'step', value: def.step },
        });
      }
      if (
        typeof def.min === 'number' &&
        typeof def.max === 'number' &&
        def.min > def.max
      ) {
        diags.push({
          severity: 'error',
          code: 'clip-types/invalid-schema-range',
          message: `${ctx}: min (${def.min}) must not exceed max (${def.max}).`,
          detail: { index: i, min: def.min, max: def.max },
        });
      }
    }

    // boolean type: default must be boolean if present
    if (def.type === 'boolean' && def.default !== undefined && typeof def.default !== 'boolean') {
      diags.push({
        severity: 'error',
        code: 'clip-types/invalid-schema-default',
        message: `${ctx}: default must be a boolean for type 'boolean'.`,
        detail: { index: i, field: 'default', value: def.default },
      });
    }

    // select type: options must be a non-empty array
    if (def.type === 'select') {
      if (!Array.isArray(def.options) || def.options.length === 0) {
        diags.push({
          severity: 'error',
          code: 'clip-types/invalid-schema-options',
          message: `${ctx}: options must be a non-empty array for type 'select'.`,
          detail: { index: i, field: 'options', value: def.options },
        });
      }
    }

    // color type: default must be a valid hex string if present
    if (def.type === 'color' && def.default !== undefined) {
      if (typeof def.default !== 'string' || !/^#[0-9a-fA-F]{3,8}$/.test(def.default)) {
        diags.push({
          severity: 'error',
          code: 'clip-types/invalid-schema-color-default',
          message: `${ctx}: default must be a hex color string (e.g. #fff, #ff0000) for type 'color'.`,
          detail: { index: i, field: 'default', value: def.default },
        });
      }
    }
  }

  return diags;
}
