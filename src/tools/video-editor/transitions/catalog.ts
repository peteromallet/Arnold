/**
 * Transition catalog: host-owned built-in transition registry records,
 * resolver, and list helpers that prevent silent extension override of
 * built-in transitions.
 *
 * Built-in transitions are exposed as registry-compatible
 * {@link TransitionRegistryRecord} entries with provenance `'built-in'`
 * and deterministic renderability metadata. The resolver always prefers
 * built-in records over extension-contributed records with the same ID.
 *
 * The existing `transitions` record and `transitionTypes` array in
 * `effects/transitions.ts` remain compatible for unmigrated callers.
 */

import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type {
  TransitionRegistryRecord,
  TransitionRegistrySnapshot,
} from '@/tools/video-editor/transitions/registry/types.ts';
import { transitions as builtInRenderers } from '@/tools/video-editor/effects/transitions.ts';
import type { TransitionRenderer } from '@/tools/video-editor/effects/transitions.ts';
import type { ClipTransition, ParameterSchema } from '@/tools/video-editor/types/index.ts';
import type { ParameterDefinition } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Built-in transition records
// ---------------------------------------------------------------------------

const BUILT_IN_CONTRIBUTION_ID_PREFIX = 'host.built-in.transition.';

function makeBuiltInRecord(
  transitionId: string,
  renderer: TransitionRenderer,
): TransitionRegistryRecord {
  return Object.freeze({
    transitionId,
    contributionId: `${BUILT_IN_CONTRIBUTION_ID_PREFIX}${transitionId}`,
    // Cast the built-in renderer to the SDK-compatible TransitionRenderer
    // union. Built-in renderers are (progress: number) => CSSProperties,
    // which at runtime are called with a single number argument.  The SDK
    // type is intentionally broad (Record<string,unknown> | function) so
    // safe coercion through `unknown` is acceptable here.
    renderer: renderer as unknown as TransitionRegistryRecord['renderer'],
    provenance: 'built-in' as const,
    renderability: Object.freeze({
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: Object.freeze([
        Object.freeze({
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        }),
        Object.freeze({
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        }),
        Object.freeze({
          route: 'worker-export',
          status: 'blocked',
          determinism: 'deterministic',
          blockerReason: 'route-unsupported',
        }),
      ]),
    }),
    status: 'active' as const,
  });
}

/** Frozen array of all built-in transition registry records. */
export const BUILT_IN_TRANSITION_RECORDS: readonly TransitionRegistryRecord[] =
  Object.freeze(
    Object.entries(builtInRenderers).map(([id, renderer]) =>
      makeBuiltInRecord(id, renderer),
    ),
  );

// ---------------------------------------------------------------------------
// Built-in ID set for fast O(1) lookup
// ---------------------------------------------------------------------------

const BUILT_IN_IDS: ReadonlySet<string> = new Set(
  BUILT_IN_TRANSITION_RECORDS.map((r) => r.transitionId),
);

// ---------------------------------------------------------------------------
// Public helpers
// ---------------------------------------------------------------------------

/** Check whether a transition ID belongs to a host-owned built-in transition. */
export function isBuiltInTransition(transitionId: string): boolean {
  return BUILT_IN_IDS.has(transitionId);
}

/** Get a frozen set of all built-in transition IDs. */
export function getBuiltInTransitionIds(): ReadonlySet<string> {
  return BUILT_IN_IDS;
}

/** Get the frozen array of all built-in transition registry records. */
export function getBuiltInTransitionRecords(): readonly TransitionRegistryRecord[] {
  return BUILT_IN_TRANSITION_RECORDS;
}

/**
 * Resolve a transition by ID against built-in records and an optional
 * provider-scoped registry snapshot.
 *
 * Resolution order:
 * 1. Built-in records (host-owned, provenance `'built-in'`)
 * 2. Registry snapshot records (extension-contributed)
 *
 * Built-in transitions are never silently overridden by registry records
 * with the same ID. When a registry record clashes with a built-in, the
 * built-in is returned and a diagnostic is emitted into the optional
 * `diagnostics` array so the consumer can surface the conflict.
 *
 * @param transitionId - The transition ID to resolve.
 * @param registrySnapshot - Optional provider-scoped registry snapshot.
 * @param diagnostics - Optional mutable array for conflict diagnostics.
 * @returns The resolved record, or `undefined` if the ID is unknown.
 */
export function resolveTransition(
  transitionId: string,
  registrySnapshot?: TransitionRegistrySnapshot,
  diagnostics?: ExtensionDiagnostic[],
): TransitionRegistryRecord | undefined {
  // Built-ins always take priority
  const builtIn = BUILT_IN_TRANSITION_RECORDS.find(
    (r) => r.transitionId === transitionId,
  );
  if (builtIn) {
    // If the registry also has a record for this built-in ID, surface a
    // diagnostic so the override is not silent.
    if (registrySnapshot?.has(transitionId) && diagnostics) {
      const registryRecord = registrySnapshot.get(transitionId);
      if (registryRecord) {
        diagnostics.push({
          severity: 'warning',
          code: 'transition-catalog/built-in-override-blocked',
          message:
            `Extension transition "${transitionId}" ` +
            `(contribution: ${registryRecord.contributionId}) conflicts ` +
            `with a built-in transition. The built-in will be used.`,
          extensionId: registryRecord.ownerExtensionId,
          contributionId: registryRecord.contributionId,
          detail: { transitionId },
        });
      }
    }
    return builtIn;
  }

  // Fall back to registry snapshot
  return registrySnapshot?.get(transitionId);
}

/**
 * List all available transitions by merging built-in records with an
 * optional registry snapshot. Built-in records take precedence when IDs
 * conflict, so extension contributions can never silently displace a
 * built-in transition in the list.
 *
 * The returned array is NOT frozen — callers that need immutability should
 * freeze it themselves.
 *
 * @param registrySnapshot - Optional provider-scoped registry snapshot.
 * @returns Array of unique transition records (built-ins + contributed).
 */
export function listTransitions(
  registrySnapshot?: TransitionRegistrySnapshot,
): TransitionRegistryRecord[] {
  const merged = new Map<string, TransitionRegistryRecord>();

  // Registry records go in first (lower priority)
  for (const record of registrySnapshot?.records ?? []) {
    merged.set(record.transitionId, record);
  }

  // Built-in records overwrite any conflicting registry records
  for (const record of BUILT_IN_TRANSITION_RECORDS) {
    merged.set(record.transitionId, record);
  }

  return [...merged.values()];
}

/**
 * Create a complete registry-compatible snapshot that merges built-in
 * transitions with an optional provider-scoped registry snapshot.
 *
 * Built-in records take precedence over registry records with the same ID.
 * The returned snapshot is frozen and safe for use in React render
 * comparisons.
 *
 * @param registrySnapshot - Optional provider-scoped registry snapshot.
 * @returns Frozen snapshot with built-ins merged in.
 */
export function createTransitionSnapshot(
  registrySnapshot?: TransitionRegistrySnapshot,
): TransitionRegistrySnapshot {
  const allRecords = listTransitions(registrySnapshot);
  const recordMap = new Map(allRecords.map((r) => [r.transitionId, r]));

  return Object.freeze({
    records: Object.freeze(allRecords),
    diagnostics: Object.freeze([...(registrySnapshot?.diagnostics ?? [])]),
    get: (transitionId: string) => recordMap.get(transitionId),
    has: (transitionId: string) => recordMap.has(transitionId),
  });
}

// ---------------------------------------------------------------------------
// Transition parameter schema defaults
// ---------------------------------------------------------------------------

type ParameterValue = number | string | boolean | Record<string, unknown>;

const AUDIO_SOURCES: ReadonlyArray<string> = ['bass', 'mid', 'treble', 'amplitude'];

/**
 * Compute the fallback value for a single parameter definition.
 *
 * Mirrors the logic in `ParameterControls.getFallbackValue` so transition
 * defaults are consistent with effect defaults without importing the UI module.
 */
function getFallbackValue(parameter: ParameterDefinition): ParameterValue {
  if (parameter.default !== undefined) {
    return parameter.default as ParameterValue;
  }

  switch (parameter.type) {
    case 'number':
      return parameter.min ?? 0;
    case 'select':
      return parameter.options?.[0]?.value ?? '';
    case 'boolean':
      return false;
    case 'audio-binding':
      return { source: 'amplitude', min: 0, max: 1 };
    case 'color':
      return '#000000';
    default:
      return '';
  }
}

/**
 * Materialize default parameter values from a {@link ParameterSchema}.
 *
 * Returns a frozen record of parameter-name → default-value. If no schema is
 * provided, returns an empty frozen record.
 *
 * The returned record is a new object every call — callers that need reference
 * stability should memoize.
 */
export function materializeTransitionDefaults(
  schema: ParameterSchema | readonly ParameterDefinition[] | undefined,
): Readonly<Record<string, unknown>> {
  if (!schema || !Array.isArray(schema) || schema.length === 0) {
    return Object.freeze({});
  }

  const defaults: Record<string, unknown> = {};
  for (const parameter of schema) {
    defaults[parameter.name] = getFallbackValue(parameter);
  }
  return Object.freeze(defaults);
}

/**
 * Normalize a clip's `transition` so that stored params are merged with
 * schema defaults.
 *
 * When a clip has a transition type but no `params` (or an empty `params`
 * object), this function materializes the schema defaults from the resolved
 * transition record and returns a new `ClipTransition` with the defaults
 * applied.
 *
 * If the transition record has no schema, or the clip already has non-empty
 * params, the clip's transition is returned unchanged (immutable).
 *
 * @param clipTransition - The clip's current transition (may be undefined).
 * @param record - The resolved TransitionRegistryRecord for this transition type.
 * @returns A new ClipTransition with schema defaults applied, or undefined.
 */
export function normalizeClipTransition(
  clipTransition: ClipTransition | undefined,
  record: TransitionRegistryRecord | undefined,
): ClipTransition | undefined {
  if (!clipTransition) return undefined;

  // If params are already present and non-empty, preserve them as-is.
  if (clipTransition.params && Object.keys(clipTransition.params).length > 0) {
    return clipTransition;
  }

  // If no record or no schema, return the transition unchanged.
  if (!record?.schema || !Array.isArray(record.schema) || record.schema.length === 0) {
    return clipTransition;
  }

  // Materialize defaults and merge with existing params (if any).
  const defaults = materializeTransitionDefaults(record.schema);
  const existingParams = clipTransition.params ?? {};

  // Merge: defaults fill in missing keys, existing params take precedence.
  const merged: Record<string, unknown> = { ...defaults };
  for (const key of Object.keys(existingParams)) {
    merged[key] = existingParams[key];
  }

  return {
    ...clipTransition,
    params: Object.freeze(merged),
  };
}
