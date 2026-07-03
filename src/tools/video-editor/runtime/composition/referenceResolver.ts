import {
  contributionRefKey,
  type CompositionReferenceStateEntry,
  type ContributionRef,
  type ExtensionDiagnostic,
  type ReferenceState,
} from '@reigh/editor-sdk';
import {
  buildCompositionDiagnostic,
  referenceStateDiagnosticCode,
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import type {
  ContributionIndex,
  ContributionIndexEntry,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

export interface CompositionReferenceUsage {
  readonly ref: ContributionRef;
  readonly nodeId: string;
  readonly scope?: 'clip' | 'postprocess';
  readonly shaderId?: string;
}

export interface ResolvedCompositionReference {
  readonly ref: ContributionRef;
  readonly refKey: string;
  readonly state: ReferenceState;
  readonly nodeIds: readonly string[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

export interface ResolveCompositionReferencesResult {
  readonly referenceStates: readonly CompositionReferenceStateEntry[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
  readonly byRefKey: Readonly<Record<string, ResolvedCompositionReference>>;
}

interface MutableResolvedCompositionReference {
  ref: ContributionRef;
  refKey: string;
  state: ReferenceState;
  nodeIds: string[];
  diagnostics: ExtensionDiagnostic[];
}

const EMPTY_REFERENCE_STATES: readonly CompositionReferenceStateEntry[] = Object.freeze([]);
const EMPTY_DIAGNOSTICS: readonly ExtensionDiagnostic[] = Object.freeze([]);
const EMPTY_RESOLVED_REFS = Object.freeze({});
const EMPTY_RESOLVE_RESULT: ResolveCompositionReferencesResult = Object.freeze({
  referenceStates: EMPTY_REFERENCE_STATES,
  diagnostics: EMPTY_DIAGNOSTICS,
  byRefKey: EMPTY_RESOLVED_REFS as ResolveCompositionReferencesResult['byRefKey'],
});

function hasPackageState(
  entry: ContributionIndexEntry,
  packageState: ContributionIndexEntry['packageState'],
): boolean {
  return entry.packageState === packageState;
}

function hasExactDuplicate(entries: readonly ContributionIndexEntry[]): boolean {
  return entries.some(
    (entry) => entry.duplicateOrdinal > 0 || entry.resolutionPolicy?.kind === 'exact-duplicate',
  );
}

function diagnosticMessage(refKey: string, state: ReferenceState): string {
  switch (state) {
    case 'missing':
      return `Composition ref "${refKey}" has no scoped candidates in the contribution index.`;
    case 'disabled':
      return `Composition ref "${refKey}" comes from a user-disabled package.`;
    case 'inactive-reserved':
      return `Composition ref "${refKey}" is declared but not yet bridged in this runtime.`;
    case 'invalid-package':
      return `Composition ref "${refKey}" comes from an invalid package.`;
    case 'duplicate':
      return `Composition ref "${refKey}" has duplicate scoped candidates, so graph authority cannot resolve it.`;
    case 'settings-error':
      return `Composition ref "${refKey}" comes from a package with a settings migration error.`;
    case 'runtime-error':
      return `Composition ref "${refKey}" comes from a package that failed runtime activation.`;
    case 'version-incompatible':
      return `Composition ref "${refKey}" comes from a version-incompatible package.`;
    case 'unknown':
      return `Composition ref "${refKey}" could not be resolved to a known graph state.`;
    case 'resolved':
      return `Composition ref "${refKey}" resolved successfully.`;
  }
}

export function resolveReferenceStateFromEntries(
  entries: readonly ContributionIndexEntry[] | undefined,
): ReferenceState {
  if (!entries || entries.length === 0) {
    return 'missing';
  }

  if (entries.some((entry) => entry.status === 'invalid' || hasPackageState(entry, 'invalid'))) {
    return 'invalid-package';
  }

  if (entries.some((entry) => hasPackageState(entry, 'settings-error'))) {
    return 'settings-error';
  }

  if (entries.some((entry) => hasPackageState(entry, 'runtime-error'))) {
    return 'runtime-error';
  }

  if (entries.some((entry) => hasPackageState(entry, 'incompatible'))) {
    return 'version-incompatible';
  }

  if (hasExactDuplicate(entries) || entries.some((entry) => hasPackageState(entry, 'duplicate'))) {
    return 'duplicate';
  }

  if (
    entries.some((entry) => entry.status === 'disabled' || hasPackageState(entry, 'disabled-by-user'))
  ) {
    return 'disabled';
  }

  if (entries.some((entry) => entry.status === 'inactive-reserved')) {
    return 'inactive-reserved';
  }

  if (entries.some((entry) => entry.status === 'active')) {
    return 'resolved';
  }

  return 'unknown';
}

export function resolveCompositionReferenceState(
  ref: ContributionRef,
  contributionIndex: ContributionIndex | undefined,
): ReferenceState {
  return resolveReferenceStateFromEntries(contributionIndex?.[contributionRefKey(ref)]);
}

export function resolveCompositionReferences(
  usages: readonly CompositionReferenceUsage[],
  contributionIndex: ContributionIndex | undefined,
): ResolveCompositionReferencesResult {
  if (usages.length === 0) {
    return EMPTY_RESOLVE_RESULT;
  }

  const diagnostics: ExtensionDiagnostic[] = [];
  const orderedRefKeys: string[] = [];
  const mutableByRefKey: Record<string, MutableResolvedCompositionReference> = {};

  for (const usage of usages) {
    const refKey = contributionRefKey(usage.ref);
    let resolved = mutableByRefKey[refKey];
    if (!resolved) {
      resolved = {
        ref: usage.ref,
        refKey,
        state: resolveCompositionReferenceState(usage.ref, contributionIndex),
        nodeIds: [],
        diagnostics: [],
      };
      mutableByRefKey[refKey] = resolved;
      orderedRefKeys.push(refKey);
    }

    if (!resolved.nodeIds.includes(usage.nodeId)) {
      resolved.nodeIds.push(usage.nodeId);
    }

    const code = referenceStateDiagnosticCode(resolved.state);
    if (!code) {
      continue;
    }

    const diagnostic = {
      ...buildCompositionDiagnostic(code, diagnosticMessage(refKey, resolved.state), {
        nodeId: usage.nodeId,
        refKey,
        refState: resolved.state,
        scope: usage.scope,
        extensionId: usage.ref.extensionId,
        contributionId: usage.ref.contributionId,
        shaderId: usage.shaderId,
      }),
      extensionId: usage.ref.extensionId,
      contributionId: usage.ref.contributionId,
    } satisfies ExtensionDiagnostic;

    diagnostics.push(diagnostic);
    resolved.diagnostics.push(diagnostic);
  }

  const referenceStates = Object.freeze(orderedRefKeys.map((refKey) => {
    const resolved = mutableByRefKey[refKey]!;
    return Object.freeze({
      refKey,
      state: resolved.state,
      nodeIds: Object.freeze([...resolved.nodeIds]),
    });
  }));

  const byRefKey = orderedRefKeys.reduce<Record<string, ResolvedCompositionReference>>((acc, refKey) => {
    const resolved = mutableByRefKey[refKey]!;
    acc[refKey] = Object.freeze({
      ref: resolved.ref,
      refKey,
      state: resolved.state,
      nodeIds: Object.freeze([...resolved.nodeIds]),
      diagnostics: Object.freeze([...resolved.diagnostics]),
    });
    return acc;
  }, {});

  return Object.freeze({
    referenceStates,
    diagnostics: Object.freeze(diagnostics),
    byRefKey: Object.freeze(byRefKey),
  });
}
