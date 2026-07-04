import type {
  DiagnosticSeverity,
  RenderMaterialRef,
  RenderMaterialStatus,
  RenderBlockerReason,
  ProcessStatus,
  RenderMaterialStatusDetail,
  RenderMaterialStatusPhase,
  RenderMaterialStatusQuality,
  RenderMaterialStatusState,
  RenderRoute,
  RouteFitMetadata,
} from '@reigh/editor-sdk';
import {
  hasProvenance,
  isActiveBake,
  isLiveOnly,
  isRouteIncompatible,
  isWeakerProvenance,
  RENDER_MATERIAL_STATUS_PHASES,
  RENDER_MATERIAL_STATUS_QUALITIES,
  RENDER_MATERIAL_STATUSES,
  RENDER_ROUTES,
} from '@reigh/editor-sdk';
import type { ProvenanceGap } from '@reigh/editor-sdk';
import type { VideoEditorPlannerNextActionKind } from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  buildCompositionDiagnostic,
  COMPOSITION_DIAGNOSTIC_CODE,
  type CompositionDiagnosticCode,
  type CompositionDiagnosticDetail,
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { ReferenceState } from '@reigh/editor-sdk';
import type {
  ContributionIndex,
  ContributionIndexEntry,
  VideoEditorProcessDescriptor,
  VideoEditorShaderDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

/**
 * Centralized material planner matrix for M3a. Later planner/UI consumers
 * should resolve status/detail semantics through this table rather than
 * branching independently on state/phase/quality.
 */

const MATRIX_PHASES = [
  undefined,
  ...RENDER_MATERIAL_STATUS_PHASES,
] as const satisfies readonly (RenderMaterialStatusPhase | undefined)[];

const MATRIX_QUALITIES = [
  undefined,
  ...RENDER_MATERIAL_STATUS_QUALITIES,
] as const satisfies readonly (RenderMaterialStatusQuality | undefined)[];

export type MaterialRuntimeRouteFitKind = RouteFitMetadata['fit'];

export type MaterialRuntimeRouteFitSensitivity =
  | 'route-agnostic'
  | 'route-category'
  | 'route-derived'
  | 'route-selection-required';

export interface MaterialRuntimeRouteFitPosture {
  readonly preview: MaterialRuntimeRouteFitKind;
  readonly authoritative: MaterialRuntimeRouteFitKind;
  readonly sensitivity: MaterialRuntimeRouteFitSensitivity;
}

export type MaterialRuntimeDeterminismPosture =
  | 'missing'
  | 'live-runtime-only'
  | 'materialization-pending'
  | 'materialization-active'
  | 'resolved'
  | 'stale'
  | 'failed'
  | 'invalid';

export type MaterialRuntimeLegacySemantic =
  | 'native-v1'
  | 'legacy-unbaked'
  | 'legacy-baking'
  | 'legacy-degraded'
  | 'legacy-live-runtime-only';

export type MaterialRuntimeDiagnosticCode =
  | 'composition/material-status-invalid'
  | 'composition/material-missing-provenance'
  | 'composition/material-live-only'
  | 'composition/material-stale'
  | 'composition/material-failed'
  | 'composition/material-weaker-provenance'
  | 'composition/material-route-incompatible';

export const MATERIAL_RUNTIME_DIAGNOSTIC_CODE = {
  STATUS_INVALID: 'composition/material-status-invalid',
  MISSING_PROVENANCE: 'composition/material-missing-provenance',
  LIVE_ONLY: 'composition/material-live-only',
  STALE: 'composition/material-stale',
  FAILED: 'composition/material-failed',
  WEAKER_PROVENANCE: 'composition/material-weaker-provenance',
  ROUTE_INCOMPATIBLE: 'composition/material-route-incompatible',
} as const satisfies Record<string, MaterialRuntimeDiagnosticCode>;
Object.freeze(MATERIAL_RUNTIME_DIAGNOSTIC_CODE);

export type MaterialRuntimeBlockerPolicy =
  | Readonly<{
      readonly kind: 'none';
    }>
  | Readonly<{
      readonly kind: 'fixed';
      readonly reason: RenderBlockerReason;
      readonly severity: Extract<DiagnosticSeverity, 'error' | 'warning'>;
    }>
  | Readonly<{
      readonly kind: 'determinism-derived';
      readonly fallbackReason: RenderBlockerReason;
      readonly severity: Extract<DiagnosticSeverity, 'error' | 'warning'>;
    }>;

export type MaterialRuntimeMatrixValidity = 'valid' | 'invalid';

export type MaterialRuntimeMatrixKey = `${RenderMaterialStatusState}|${RenderMaterialStatusPhase | '-'}|${RenderMaterialStatusQuality | '-'}`;

export interface MaterialRuntimeMatrixRow {
  readonly key: MaterialRuntimeMatrixKey;
  readonly state: RenderMaterialStatusState;
  readonly phase?: RenderMaterialStatusPhase;
  readonly quality?: RenderMaterialStatusQuality;
  readonly validity: MaterialRuntimeMatrixValidity;
  readonly normalizedDetail?: RenderMaterialStatusDetail;
  readonly migrationSemantics: readonly MaterialRuntimeLegacySemantic[];
  readonly blocker: MaterialRuntimeBlockerPolicy;
  readonly diagnosticSeverity: DiagnosticSeverity;
  readonly determinismPosture: MaterialRuntimeDeterminismPosture;
  readonly routeFit: MaterialRuntimeRouteFitPosture;
  readonly diagnosticCodes: readonly MaterialRuntimeDiagnosticCode[];
  readonly nextActionKind?: VideoEditorPlannerNextActionKind;
}

export type LegacyMaterialStatusAlias =
  | 'unbaked'
  | 'baking'
  | 'degraded'
  | 'live-runtime-only';

export interface LegacyMaterialStatusMigration {
  readonly state: RenderMaterialStatusState;
  readonly detail?: RenderMaterialStatusDetail;
  readonly semantics: readonly MaterialRuntimeLegacySemantic[];
}

export interface HostMaterialRuntimeProjectionInput {
  readonly materialRefs?: readonly RenderMaterialRef[];
  readonly materialStatuses?: readonly RenderMaterialStatus[];
  readonly contributionIndex?: ContributionIndex;
  readonly shaders?: readonly VideoEditorShaderDescriptor[];
  readonly processes?: readonly VideoEditorProcessDescriptor[];
  readonly processStatuses?: readonly ProcessStatus[];
  readonly requestedRoutes?: readonly RenderRoute[];
  readonly canonicalRoutes?: readonly RenderRoute[];
}

export interface HostMaterialRuntimePredicates {
  readonly activeBake: boolean;
  readonly liveOnly: boolean;
  readonly weakerProvenance: boolean;
  readonly routeIncompatible: boolean;
}

export interface HostMaterialRuntimeBlockerPlaceholder {
  readonly reason: RenderBlockerReason;
  readonly severity: Extract<DiagnosticSeverity, 'error' | 'warning'>;
  readonly route?: RenderRoute;
}

export interface HostMaterialRuntimeActionPlaceholder {
  readonly kind: VideoEditorPlannerNextActionKind;
  readonly route?: RenderRoute;
}

export type MaterialRuntimeProvenancePosture =
  | 'recorded'
  | 'derivable'
  | 'unattributed';

export interface HostMaterialRuntimeContributionFact {
  readonly scopedKey: string;
  readonly status: ContributionIndexEntry['status'];
  readonly packageState?: ContributionIndexEntry['packageState'];
  readonly routeFit?: RouteFitMetadata;
}

export interface HostMaterialRuntimeShaderFact {
  readonly extensionId: string;
  readonly contributionId: string;
  readonly shaderId: string;
  readonly label: string;
  readonly declaredRoutes: readonly RenderRoute[];
  readonly processId?: string;
  readonly operationId?: string;
}

export interface HostMaterialRuntimeProcessFact {
  readonly processId: string;
  readonly operationId?: string;
  readonly state?: ProcessStatus['state'];
  readonly availableRoutes: readonly RenderRoute[];
  readonly supportsMaterialOutput: boolean;
  readonly declarative: true;
}

export interface HostMaterialRuntimeDescriptorFacts {
  readonly contribution?: HostMaterialRuntimeContributionFact;
  readonly shader?: HostMaterialRuntimeShaderFact;
  readonly process?: HostMaterialRuntimeProcessFact;
}

export interface HostMaterialRuntimeRouteScope {
  readonly route: RenderRoute;
  readonly fit: MaterialRuntimeRouteFitKind;
  readonly sensitivity: MaterialRuntimeRouteFitSensitivity;
  readonly blocker?: HostMaterialRuntimeBlockerPlaceholder;
  readonly nextAction?: HostMaterialRuntimeActionPlaceholder;
}

export interface HostMaterialRuntimeEntry {
  readonly materialRef: RenderMaterialRef;
  readonly status: RenderMaterialStatus;
  readonly matrix: MaterialRuntimeMatrixRow;
  readonly predicates: HostMaterialRuntimePredicates;
  readonly determinism: RenderMaterialRef['determinism'];
  readonly determinismPosture: MaterialRuntimeDeterminismPosture;
  readonly provenancePosture: MaterialRuntimeProvenancePosture;
  readonly routeFit: MaterialRuntimeRouteFitPosture;
  readonly blocksAuthoritativeExport: boolean;
  readonly descriptorFacts: HostMaterialRuntimeDescriptorFacts;
  readonly blocker?: HostMaterialRuntimeBlockerPlaceholder;
  readonly nextAction?: HostMaterialRuntimeActionPlaceholder;
  readonly routeScopes: readonly HostMaterialRuntimeRouteScope[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

export interface HostMaterialRuntimeProjection {
  readonly requestedRoutes: readonly RenderRoute[];
  readonly canonicalRoutes: readonly RenderRoute[];
  readonly routeEvidence: readonly RenderRoute[];
  readonly materialRefIds: readonly string[];
  readonly materials: readonly HostMaterialRuntimeEntry[];
  readonly byMaterialRefId: ReadonlyMap<string, HostMaterialRuntimeEntry>;
  readonly diagnostics: readonly ExtensionDiagnostic[];
  readonly authoritativeBlockedMaterialRefIds: readonly string[];
  readonly hasAuthoritativeBlockers: boolean;
}

export type ResolveMaterialAttachEntryResult =
  | Readonly<{
      readonly ok: true;
      readonly entry: HostMaterialRuntimeEntry;
    }>
  | Readonly<{
      readonly ok: false;
      readonly diagnostic: ExtensionDiagnostic;
    }>;

export interface MaterialAttachDiagnosticContext {
  readonly clipId?: string;
  readonly scope?: 'clip' | 'postprocess';
  readonly ownerKind?: string;
  readonly ownerId?: string;
  readonly materialSlot?: string;
  readonly refKey?: string;
  readonly extensionId?: string;
  readonly contributionId?: string;
  readonly resolverState?: ReferenceState;
  readonly packageState?: string;
}

function freezeDetail(
  detail: RenderMaterialStatusDetail | undefined,
): RenderMaterialStatusDetail | undefined {
  return detail ? Object.freeze({ ...detail }) : undefined;
}

function freezeRouteFit(
  routeFit: MaterialRuntimeRouteFitPosture,
): MaterialRuntimeRouteFitPosture {
  return Object.freeze({ ...routeFit });
}

function freezeBlocker(
  blocker: MaterialRuntimeBlockerPolicy,
): MaterialRuntimeBlockerPolicy {
  return Object.freeze({ ...blocker });
}

function freezeRow(row: MaterialRuntimeMatrixRow): MaterialRuntimeMatrixRow {
  return Object.freeze({
    ...row,
    normalizedDetail: freezeDetail(row.normalizedDetail),
    migrationSemantics: Object.freeze([...row.migrationSemantics]),
    blocker: freezeBlocker(row.blocker),
    routeFit: freezeRouteFit(row.routeFit),
    diagnosticCodes: Object.freeze([...row.diagnosticCodes]),
  });
}

function freezeRecord(
  record: Record<string, unknown> | undefined,
): Readonly<Record<string, unknown>> | undefined {
  return record ? Object.freeze({ ...record }) : undefined;
}

function freezeLocator(
  locator: RenderMaterialRef['locator'],
): RenderMaterialRef['locator'] {
  return Object.freeze({ ...locator });
}

function freezeMaterialRef(materialRef: RenderMaterialRef): RenderMaterialRef {
  return Object.freeze({
    ...materialRef,
    locator: freezeLocator(materialRef.locator),
    provenance: freezeRecord(materialRef.provenance),
  });
}

function freezeMaterialStatus(status: RenderMaterialStatus): RenderMaterialStatus {
  return Object.freeze({
    ...status,
    detail: freezeDetail(status.detail),
  });
}

function createReadonlyMap<K, V>(
  entries: readonly (readonly [K, V])[],
): ReadonlyMap<K, V> {
  const inner = new Map(entries);
  const readonlyMap: ReadonlyMap<K, V> = {
    get size() {
      return inner.size;
    },
    has(key: K): boolean {
      return inner.has(key);
    },
    get(key: K): V | undefined {
      return inner.get(key);
    },
    forEach(
      callbackfn: (value: V, key: K, map: ReadonlyMap<K, V>) => void,
      thisArg?: unknown,
    ): void {
      inner.forEach((value, key) => callbackfn.call(thisArg, value, key, readonlyMap));
    },
    entries(): IterableIterator<[K, V]> {
      return inner.entries();
    },
    keys(): IterableIterator<K> {
      return inner.keys();
    },
    values(): IterableIterator<V> {
      return inner.values();
    },
    [Symbol.iterator](): IterableIterator<[K, V]> {
      return inner[Symbol.iterator]();
    },
  };

  return Object.freeze(readonlyMap);
}

function stableRouteOrder(routes: readonly RenderRoute[] | undefined): readonly RenderRoute[] {
  if (!routes?.length) {
    return Object.freeze([]);
  }

  const seen = new Set<RenderRoute>();
  for (const route of routes) {
    seen.add(route);
  }

  return Object.freeze(RENDER_ROUTES.filter((route) => seen.has(route)));
}

function freezePredicates(
  predicates: HostMaterialRuntimePredicates,
): HostMaterialRuntimePredicates {
  return Object.freeze({ ...predicates });
}

function freezeBlockerPlaceholder(
  blocker: HostMaterialRuntimeBlockerPlaceholder | undefined,
): HostMaterialRuntimeBlockerPlaceholder | undefined {
  return blocker ? Object.freeze({ ...blocker }) : undefined;
}

function freezeActionPlaceholder(
  nextAction: HostMaterialRuntimeActionPlaceholder | undefined,
): HostMaterialRuntimeActionPlaceholder | undefined {
  return nextAction ? Object.freeze({ ...nextAction }) : undefined;
}

function freezeContributionFact(
  contribution: HostMaterialRuntimeContributionFact | undefined,
): HostMaterialRuntimeContributionFact | undefined {
  return contribution
    ? Object.freeze({
        ...contribution,
        routeFit: contribution.routeFit ? Object.freeze({ ...contribution.routeFit }) : undefined,
      })
    : undefined;
}

function freezeShaderFact(
  shader: HostMaterialRuntimeShaderFact | undefined,
): HostMaterialRuntimeShaderFact | undefined {
  return shader
    ? Object.freeze({
        ...shader,
        declaredRoutes: Object.freeze([...shader.declaredRoutes]),
      })
    : undefined;
}

function freezeProcessFact(
  process: HostMaterialRuntimeProcessFact | undefined,
): HostMaterialRuntimeProcessFact | undefined {
  return process
    ? Object.freeze({
        ...process,
        availableRoutes: Object.freeze([...process.availableRoutes]),
      })
    : undefined;
}

function freezeDescriptorFacts(
  descriptorFacts: HostMaterialRuntimeDescriptorFacts,
): HostMaterialRuntimeDescriptorFacts {
  return Object.freeze({
    contribution: freezeContributionFact(descriptorFacts.contribution),
    shader: freezeShaderFact(descriptorFacts.shader),
    process: freezeProcessFact(descriptorFacts.process),
  });
}

function freezeRouteScope(
  routeScope: HostMaterialRuntimeRouteScope,
): HostMaterialRuntimeRouteScope {
  return Object.freeze({
    ...routeScope,
    blocker: freezeBlockerPlaceholder(routeScope.blocker),
    nextAction: freezeActionPlaceholder(routeScope.nextAction),
  });
}

function freezeHostMaterialRuntimeEntry(
  entry: HostMaterialRuntimeEntry,
): HostMaterialRuntimeEntry {
  return Object.freeze({
    ...entry,
    materialRef: freezeMaterialRef(entry.materialRef),
    status: freezeMaterialStatus(entry.status),
    predicates: freezePredicates(entry.predicates),
    routeFit: freezeRouteFit(entry.routeFit),
    descriptorFacts: freezeDescriptorFacts(entry.descriptorFacts),
    blocker: freezeBlockerPlaceholder(entry.blocker),
    nextAction: freezeActionPlaceholder(entry.nextAction),
    routeScopes: Object.freeze(entry.routeScopes.map(freezeRouteScope)),
    diagnostics: Object.freeze([...entry.diagnostics]),
  });
}

function defaultMaterialRuntimeStatus(
  materialRef: RenderMaterialRef,
): RenderMaterialStatus {
  if (materialRef.determinism === 'deterministic') {
    return {
      materialRefId: materialRef.id,
      state: 'resolved',
    };
  }

  return {
    materialRefId: materialRef.id,
    state: 'pending',
    detail: {
      phase: 'queued',
    },
  };
}

function statusBlockerReason(
  materialRef: RenderMaterialRef,
  row: MaterialRuntimeMatrixRow,
): RenderBlockerReason | undefined {
  if (row.blocker.kind === 'none') {
    return undefined;
  }

  if (row.blocker.kind === 'fixed') {
    return row.blocker.reason;
  }

  if (
    materialRef.determinism === 'preview-only'
    || materialRef.determinism === 'live-unbaked'
    || materialRef.determinism === 'process-dependent'
    || materialRef.determinism === 'unknown'
  ) {
    return materialRef.determinism;
  }

  return row.blocker.fallbackReason;
}

function buildBlockerPlaceholder(
  materialRef: RenderMaterialRef,
  row: MaterialRuntimeMatrixRow,
  route?: RenderRoute,
): HostMaterialRuntimeBlockerPlaceholder | undefined {
  if (row.blocker.kind === 'none') {
    return undefined;
  }

  const reason = statusBlockerReason(materialRef, row);
  if (!reason) {
    return undefined;
  }

  return Object.freeze({
    reason,
    severity: row.blocker.severity,
    route,
  });
}

function buildActionPlaceholder(
  row: MaterialRuntimeMatrixRow,
  route?: RenderRoute,
): HostMaterialRuntimeActionPlaceholder | undefined {
  if (!row.nextActionKind) {
    return undefined;
  }

  return Object.freeze({
    kind: row.nextActionKind,
    route,
  });
}

function routeFitForRoute(
  row: MaterialRuntimeMatrixRow,
  route: RenderRoute,
): MaterialRuntimeRouteFitKind {
  return route === 'preview' ? row.routeFit.preview : row.routeFit.authoritative;
}

function buildRouteScope(
  materialRef: RenderMaterialRef,
  row: MaterialRuntimeMatrixRow,
  route: RenderRoute,
): HostMaterialRuntimeRouteScope {
  const fit = routeFitForRoute(row, route);
  const routeIsBlocked = fit === 'blocked';

  return freezeRouteScope({
    route,
    fit,
    sensitivity: row.routeFit.sensitivity,
    blocker: routeIsBlocked
      ? buildBlockerPlaceholder(materialRef, row, route)
      : undefined,
    nextAction: routeIsBlocked
      ? buildActionPlaceholder(row, route)
      : undefined,
  });
}

function normalizeMaterialStatus(
  materialRef: RenderMaterialRef,
  status: RenderMaterialStatus | undefined,
): RenderMaterialStatus {
  const resolved = status ?? defaultMaterialRuntimeStatus(materialRef);
  const matrix = getMaterialRuntimeMatrixRow(resolved.state, resolved.detail);

  return freezeMaterialStatus({
    materialRefId: materialRef.id,
    state: resolved.state,
    ...(resolved.message ? { message: resolved.message } : {}),
    ...(resolved.updatedAt ? { updatedAt: resolved.updatedAt } : {}),
    ...(matrix.normalizedDetail ? { detail: matrix.normalizedDetail } : {}),
  });
}

function buildPredicates(
  status: RenderMaterialStatus,
): HostMaterialRuntimePredicates {
  return freezePredicates({
    activeBake: isActiveBake(status),
    liveOnly: isLiveOnly(status),
    weakerProvenance: isWeakerProvenance(status),
    routeIncompatible: isRouteIncompatible(status),
  });
}

function hasOwnKeys(record: Record<string, unknown> | undefined): boolean {
  return !!record && Object.keys(record).length > 0;
}

function provenanceString(
  materialRef: RenderMaterialRef,
  key: string,
): string | undefined {
  const value = materialRef.provenance?.[key];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function materialContributionScopedKey(materialRef: RenderMaterialRef): string | undefined {
  const contributionId = provenanceString(materialRef, 'contributionId');
  if (!materialRef.producerExtensionId || !contributionId) {
    return undefined;
  }

  const kind = provenanceString(materialRef, 'contributionKind') ?? 'shader';
  return `${kind}:${materialRef.producerExtensionId}:${contributionId}`;
}

function findContributionFact(
  materialRef: RenderMaterialRef,
  contributionIndex: ContributionIndex | undefined,
): HostMaterialRuntimeContributionFact | undefined {
  const scopedKey = materialContributionScopedKey(materialRef);
  if (!scopedKey) {
    return undefined;
  }

  const entry = (contributionIndex?.[scopedKey] ?? []).find((candidate) => candidate.status === 'active')
    ?? contributionIndex?.[scopedKey]?.[0];
  if (!entry) {
    return undefined;
  }

  return Object.freeze({
    scopedKey: entry.scopedKey,
    status: entry.status,
    packageState: entry.packageState,
    routeFit: entry.routeFit ? Object.freeze({ ...entry.routeFit }) : undefined,
  });
}

function findShaderDescriptor(
  materialRef: RenderMaterialRef,
  shaders: readonly VideoEditorShaderDescriptor[] | undefined,
): VideoEditorShaderDescriptor | undefined {
  if (!shaders?.length || !materialRef.producerExtensionId) {
    return undefined;
  }

  const contributionId = provenanceString(materialRef, 'contributionId');
  const shaderId = provenanceString(materialRef, 'shaderId');
  const extensionMatches = shaders.filter(
    (shader) => shader.extensionId === materialRef.producerExtensionId,
  );

  if (contributionId) {
    const exact = extensionMatches.find((shader) => shader.id === contributionId);
    if (exact) {
      return exact;
    }
  }

  if (shaderId) {
    const byShaderId = extensionMatches.find((shader) => shader.shaderId === shaderId);
    if (byShaderId) {
      return byShaderId;
    }
  }

  return extensionMatches.length === 1 ? extensionMatches[0] : undefined;
}

function supportsMaterialOutput(
  process: VideoEditorProcessDescriptor | undefined,
  operationId: string | undefined,
): boolean {
  if (!process) {
    return false;
  }

  return process.operations.some((operation) => {
    if (operationId && operation.id !== operationId) {
      return false;
    }
    return !operation.outputKinds || operation.outputKinds.includes('material');
  });
}

function findProcessFact(
  shader: VideoEditorShaderDescriptor | undefined,
  processes: readonly VideoEditorProcessDescriptor[] | undefined,
  processStatuses: readonly ProcessStatus[] | undefined,
): HostMaterialRuntimeProcessFact | undefined {
  const processId = shader?.materializer?.processId;
  if (!processId) {
    return undefined;
  }

  const process = processes?.find((candidate) => candidate.processId === processId);
  const status = processStatuses?.find((candidate) => candidate.processId === processId);
  const availableRoutes = process
    ? process.availableRoutes
    : Object.freeze([...(shader?.materializer?.routes ?? [])]);

  return Object.freeze({
    processId,
    operationId: shader?.materializer?.operationId,
    state: status?.state,
    availableRoutes,
    supportsMaterialOutput: supportsMaterialOutput(process, shader?.materializer?.operationId),
    declarative: true,
  });
}

function buildDescriptorFacts(
  materialRef: RenderMaterialRef,
  input: HostMaterialRuntimeProjectionInput,
): HostMaterialRuntimeDescriptorFacts {
  const shader = findShaderDescriptor(materialRef, input.shaders);
  const contribution = findContributionFact(materialRef, input.contributionIndex);
  const process = findProcessFact(shader, input.processes, input.processStatuses);

  return freezeDescriptorFacts({
    contribution,
    shader: shader ? {
      extensionId: shader.extensionId,
      contributionId: shader.id,
      shaderId: shader.shaderId,
      label: shader.label,
      declaredRoutes: Object.freeze([...(shader.materializer?.routes ?? [])]),
      processId: shader.materializer?.processId,
      operationId: shader.materializer?.operationId,
    } : undefined,
    process,
  });
}

function provenancePosture(
  materialRef: RenderMaterialRef,
  descriptorFacts: HostMaterialRuntimeDescriptorFacts,
): MaterialRuntimeProvenancePosture {
  if (hasOwnKeys(materialRef.provenance)) {
    return 'recorded';
  }

  if (
    materialRef.producerExtensionId
    || materialRef.producerVersion
    || descriptorFacts.contribution
    || descriptorFacts.shader
  ) {
    return 'derivable';
  }

  return 'unattributed';
}

function blocksAuthoritativeExport(row: MaterialRuntimeMatrixRow): boolean {
  return row.validity === 'invalid' || row.routeFit.authoritative === 'blocked';
}

export function materialRuntimeMatrixKey(
  state: RenderMaterialStatusState,
  detail?: Readonly<RenderMaterialStatusDetail> | null,
): MaterialRuntimeMatrixKey {
  return `${state}|${detail?.phase ?? '-'}|${detail?.quality ?? '-'}`;
}

function createInvalidRow(
  state: RenderMaterialStatusState,
  phase: RenderMaterialStatusPhase | undefined,
  quality: RenderMaterialStatusQuality | undefined,
): MaterialRuntimeMatrixRow {
  const normalizedDetail = phase || quality ? {
    ...(phase ? { phase } : {}),
    ...(quality ? { quality } : {}),
  } satisfies RenderMaterialStatusDetail : undefined;

  return freezeRow({
    key: materialRuntimeMatrixKey(state, normalizedDetail),
    state,
    phase,
    quality,
    validity: 'invalid',
    normalizedDetail,
    migrationSemantics: Object.freeze(['native-v1']),
    blocker: {
      kind: 'fixed',
      reason: 'unknown',
      severity: 'error',
    },
    diagnosticSeverity: 'error',
    determinismPosture: 'invalid',
    routeFit: {
      preview: 'blocked',
      authoritative: 'blocked',
      sensitivity: 'route-agnostic',
    },
    diagnosticCodes: Object.freeze([MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STATUS_INVALID]),
    nextActionKind: 'open-settings',
  });
}

function createValidRow(
  state: RenderMaterialStatusState,
  phase: RenderMaterialStatusPhase | undefined,
  quality: RenderMaterialStatusQuality | undefined,
): MaterialRuntimeMatrixRow {
  if (state === 'missing') {
    if (quality) return createInvalidRow(state, phase, quality);
    if (phase === 'queued' || phase === 'active') return createInvalidRow(state, phase, quality);
    if (phase === 'live-only') {
      return freezeRow({
        key: materialRuntimeMatrixKey(state, { phase }),
        state,
        phase,
        quality,
        validity: 'valid',
        normalizedDetail: { phase },
        migrationSemantics: Object.freeze(['native-v1', 'legacy-live-runtime-only']),
        blocker: {
          kind: 'fixed',
          reason: 'live-unbaked',
          severity: 'error',
        },
        diagnosticSeverity: 'warning',
        determinismPosture: 'live-runtime-only',
        routeFit: {
          preview: 'supported',
          authoritative: 'blocked',
          sensitivity: 'route-category',
        },
        diagnosticCodes: Object.freeze([MATERIAL_RUNTIME_DIAGNOSTIC_CODE.LIVE_ONLY]),
        nextActionKind: 'materialize',
      });
    }

    return freezeRow({
      key: materialRuntimeMatrixKey(state),
      state,
      phase,
      quality,
      validity: 'valid',
      normalizedDetail: undefined,
      migrationSemantics: Object.freeze(['native-v1']),
      blocker: {
        kind: 'fixed',
        reason: 'missing-material',
        severity: 'error',
      },
      diagnosticSeverity: 'error',
      determinismPosture: 'missing',
      routeFit: {
        preview: 'blocked',
        authoritative: 'blocked',
        sensitivity: 'route-agnostic',
      },
      diagnosticCodes: Object.freeze([]),
      nextActionKind: 'materialize',
    });
  }

  if (state === 'pending') {
    if (quality || phase === 'live-only') return createInvalidRow(state, phase, quality);

    const normalizedPhase = phase ?? 'queued';
    return freezeRow({
      key: materialRuntimeMatrixKey(state, phase ? { phase } : undefined),
      state,
      phase,
      quality,
      validity: 'valid',
      normalizedDetail: { phase: normalizedPhase },
      migrationSemantics: Object.freeze(
        normalizedPhase === 'active'
          ? ['native-v1', 'legacy-baking']
          : ['native-v1', 'legacy-unbaked'],
      ),
      blocker: {
        kind: 'determinism-derived',
        fallbackReason: 'unknown',
        severity: 'error',
      },
      diagnosticSeverity: 'warning',
      determinismPosture: normalizedPhase === 'active'
        ? 'materialization-active'
        : 'materialization-pending',
      routeFit: {
        preview: 'supported',
        authoritative: 'blocked',
        sensitivity: 'route-category',
      },
      diagnosticCodes: Object.freeze([]),
      nextActionKind: normalizedPhase === 'active' ? 'bake' : 'materialize',
    });
  }

  if (phase) {
    return createInvalidRow(state, phase, quality);
  }

  if (state === 'resolved') {
    if (quality === 'weaker-provenance') {
      return freezeRow({
        key: materialRuntimeMatrixKey(state, { quality }),
        state,
        phase,
        quality,
        validity: 'valid',
        normalizedDetail: { quality },
        migrationSemantics: Object.freeze(['native-v1']),
        blocker: {
          kind: 'none',
        },
        diagnosticSeverity: 'warning',
        determinismPosture: 'resolved',
        routeFit: {
          preview: 'supported',
          authoritative: 'degraded',
          sensitivity: 'route-derived',
        },
        diagnosticCodes: Object.freeze([MATERIAL_RUNTIME_DIAGNOSTIC_CODE.WEAKER_PROVENANCE]),
      });
    }

    if (quality === 'route-incompatible') {
      return freezeRow({
        key: materialRuntimeMatrixKey(state, { quality }),
        state,
        phase,
        quality,
        validity: 'valid',
        normalizedDetail: { quality },
        migrationSemantics: Object.freeze(['native-v1']),
        blocker: {
          kind: 'fixed',
          reason: 'route-unsupported',
          severity: 'error',
        },
        diagnosticSeverity: 'error',
        determinismPosture: 'resolved',
        routeFit: {
          preview: 'supported',
          authoritative: 'blocked',
          sensitivity: 'route-selection-required',
        },
        diagnosticCodes: Object.freeze([MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE]),
        nextActionKind: 'select-route',
      });
    }

    return freezeRow({
      key: materialRuntimeMatrixKey(state),
      state,
      phase,
      quality,
      validity: 'valid',
      normalizedDetail: undefined,
      migrationSemantics: Object.freeze(['native-v1']),
      blocker: {
        kind: 'none',
      },
      diagnosticSeverity: 'info',
      determinismPosture: 'resolved',
      routeFit: {
        preview: 'supported',
        authoritative: 'supported',
        sensitivity: 'route-agnostic',
      },
      diagnosticCodes: Object.freeze([]),
    });
  }

  if (state === 'stale') {
    if (quality === 'route-incompatible') {
      return freezeRow({
        key: materialRuntimeMatrixKey(state, { quality }),
        state,
        phase,
        quality,
        validity: 'valid',
        normalizedDetail: { quality },
        migrationSemantics: Object.freeze(['native-v1', 'legacy-degraded']),
        blocker: {
          kind: 'fixed',
          reason: 'route-unsupported',
          severity: 'error',
        },
        diagnosticSeverity: 'error',
        determinismPosture: 'stale',
        routeFit: {
          preview: 'degraded',
          authoritative: 'blocked',
          sensitivity: 'route-selection-required',
        },
        diagnosticCodes: Object.freeze([
          MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STALE,
          MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE,
        ]),
        nextActionKind: 'select-route',
      });
    }

    return freezeRow({
      key: materialRuntimeMatrixKey(state, quality ? { quality } : undefined),
      state,
      phase,
      quality,
      validity: 'valid',
      normalizedDetail: quality ? { quality } : undefined,
      migrationSemantics: Object.freeze(['native-v1', 'legacy-degraded']),
      blocker: {
        kind: 'fixed',
        reason: 'materialization-failed',
        severity: 'error',
      },
      diagnosticSeverity: 'warning',
      determinismPosture: 'stale',
      routeFit: {
        preview: 'degraded',
        authoritative: 'blocked',
        sensitivity: quality === 'weaker-provenance' ? 'route-derived' : 'route-category',
      },
      diagnosticCodes: Object.freeze(
        quality === 'weaker-provenance'
          ? [
              MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STALE,
              MATERIAL_RUNTIME_DIAGNOSTIC_CODE.WEAKER_PROVENANCE,
            ]
          : [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STALE],
      ),
      nextActionKind: 'materialize',
    });
  }

  if (state === 'failed') {
    if (quality === 'route-incompatible') {
      return freezeRow({
        key: materialRuntimeMatrixKey(state, { quality }),
        state,
        phase,
        quality,
        validity: 'valid',
        normalizedDetail: { quality },
        migrationSemantics: Object.freeze(['native-v1']),
        blocker: {
          kind: 'fixed',
          reason: 'route-unsupported',
          severity: 'error',
        },
        diagnosticSeverity: 'error',
        determinismPosture: 'failed',
        routeFit: {
          preview: 'blocked',
          authoritative: 'blocked',
          sensitivity: 'route-selection-required',
        },
        diagnosticCodes: Object.freeze([
          MATERIAL_RUNTIME_DIAGNOSTIC_CODE.FAILED,
          MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE,
        ]),
        nextActionKind: 'select-route',
      });
    }

    return freezeRow({
      key: materialRuntimeMatrixKey(state, quality ? { quality } : undefined),
      state,
      phase,
      quality,
      validity: 'valid',
      normalizedDetail: quality ? { quality } : undefined,
      migrationSemantics: Object.freeze(['native-v1']),
      blocker: {
        kind: 'fixed',
        reason: 'materialization-error',
        severity: 'error',
      },
      diagnosticSeverity: 'error',
      determinismPosture: 'failed',
      routeFit: {
        preview: 'blocked',
        authoritative: 'blocked',
        sensitivity: quality === 'weaker-provenance' ? 'route-derived' : 'route-agnostic',
      },
      diagnosticCodes: Object.freeze(
        quality === 'weaker-provenance'
          ? [
              MATERIAL_RUNTIME_DIAGNOSTIC_CODE.FAILED,
              MATERIAL_RUNTIME_DIAGNOSTIC_CODE.WEAKER_PROVENANCE,
            ]
          : [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.FAILED],
      ),
      nextActionKind: 'open-settings',
    });
  }

  const _exhaustive: never = state;
  return _exhaustive;
}

export const MATERIAL_RUNTIME_LEGACY_MIGRATIONS = Object.freeze({
  unbaked: Object.freeze<LegacyMaterialStatusMigration>({
    state: 'pending',
    detail: Object.freeze({ phase: 'queued' }),
    semantics: Object.freeze(['legacy-unbaked']),
  }),
  baking: Object.freeze<LegacyMaterialStatusMigration>({
    state: 'pending',
    detail: Object.freeze({ phase: 'active' }),
    semantics: Object.freeze(['legacy-baking']),
  }),
  degraded: Object.freeze<LegacyMaterialStatusMigration>({
    state: 'stale',
    semantics: Object.freeze(['legacy-degraded']),
  }),
  'live-runtime-only': Object.freeze<LegacyMaterialStatusMigration>({
    state: 'missing',
    detail: Object.freeze({ phase: 'live-only' }),
    semantics: Object.freeze(['legacy-live-runtime-only']),
  }),
} satisfies Record<LegacyMaterialStatusAlias, LegacyMaterialStatusMigration>);

export const MATERIAL_RUNTIME_PLANNER_MATRIX = Object.freeze(
  RENDER_MATERIAL_STATUSES.flatMap((state) =>
    MATRIX_PHASES.flatMap((phase) =>
      MATRIX_QUALITIES.map((quality) => createValidRow(state, phase, quality))
    )
  ),
) as readonly MaterialRuntimeMatrixRow[];

export const MATERIAL_RUNTIME_PLANNER_MATRIX_BY_KEY = createReadonlyMap(
  MATERIAL_RUNTIME_PLANNER_MATRIX.map((row) => [row.key, row] as const),
);

if (MATERIAL_RUNTIME_PLANNER_MATRIX.length !== 60) {
  throw new Error(
    `Expected 60 material runtime planner matrix rows, received ${MATERIAL_RUNTIME_PLANNER_MATRIX.length}.`,
  );
}

export function getMaterialRuntimeMatrixRow(
  state: RenderMaterialStatusState,
  detail?: Readonly<RenderMaterialStatusDetail> | null,
): MaterialRuntimeMatrixRow {
  return MATERIAL_RUNTIME_PLANNER_MATRIX_BY_KEY.get(materialRuntimeMatrixKey(state, detail))
    ?? createInvalidRow(state, detail?.phase, detail?.quality);
}

export function migrateLegacyMaterialStatus(
  alias: LegacyMaterialStatusAlias,
): LegacyMaterialStatusMigration {
  return MATERIAL_RUNTIME_LEGACY_MIGRATIONS[alias];
}

export function projectHostMaterialRuntime(
  input: HostMaterialRuntimeProjectionInput,
): HostMaterialRuntimeProjection {
  const requestedRoutes = stableRouteOrder(input.requestedRoutes);
  const canonicalRoutes = stableRouteOrder(input.canonicalRoutes);
  const routeEvidence = stableRouteOrder([
    ...requestedRoutes,
    ...canonicalRoutes,
  ]);

  const explicitStatuses = new Map<string, RenderMaterialStatus>();
  for (const status of input.materialStatuses ?? []) {
    if (!explicitStatuses.has(status.materialRefId)) {
      explicitStatuses.set(status.materialRefId, status);
    }
  }

  const uniqueMaterialRefs = [...(input.materialRefs ?? [])]
    .map((materialRef, index) => ({ materialRef, index }))
    .sort(
      (left, right) =>
        left.materialRef.id.localeCompare(right.materialRef.id)
        || left.index - right.index,
    )
    .filter((candidate, index, candidates) =>
      index === 0 || candidates[index - 1]!.materialRef.id !== candidate.materialRef.id
    )
    .map((candidate) => candidate.materialRef);

  const materials = Object.freeze(uniqueMaterialRefs.map((materialRef) => {
    const status = normalizeMaterialStatus(materialRef, explicitStatuses.get(materialRef.id));
    const matrix = getMaterialRuntimeMatrixRow(status.state, status.detail);
    const descriptorFacts = buildDescriptorFacts(materialRef, input);
    const blocker = buildBlockerPlaceholder(materialRef, matrix);
    const nextAction = buildActionPlaceholder(matrix);
    const routeScopes = Object.freeze(routeEvidence.map((route) => buildRouteScope(
      materialRef,
      matrix,
      route,
    )));

    const materialProvenancePosture = provenancePosture(materialRef, descriptorFacts);

    const entry = freezeHostMaterialRuntimeEntry({
      materialRef,
      status,
      matrix,
      predicates: buildPredicates(status),
      determinism: materialRef.determinism,
      determinismPosture: matrix.determinismPosture,
      provenancePosture: materialProvenancePosture,
      routeFit: matrix.routeFit,
      blocksAuthoritativeExport: blocksAuthoritativeExport(matrix),
      descriptorFacts,
      blocker,
      nextAction,
      routeScopes,
      diagnostics: Object.freeze([]),
    });

    const matrixDiagnostics = buildMaterialDiagnosticsForEntry(entry);
    const provenanceDiagnostics =
      materialProvenancePosture === 'unattributed'
        ? Object.freeze([
            buildCompositionDiagnostic(
              COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_MISSING_PROVENANCE,
              materialDiagnosticMessage(
                MATERIAL_RUNTIME_DIAGNOSTIC_CODE.MISSING_PROVENANCE,
                entry,
              ),
              buildMaterialDiagnosticDetail(entry),
            ),
          ])
        : Object.freeze([]);

    return freezeHostMaterialRuntimeEntry({
      ...entry,
      diagnostics: Object.freeze([
        ...matrixDiagnostics,
        ...provenanceDiagnostics,
        ...entry.routeScopes
          .filter((routeScope) => routeScope.fit === 'blocked')
          .flatMap((routeScope) => buildMaterialDiagnosticsForEntry(entry, routeScope.route)),
      ]),
    });
  }));

  const byMaterialRefId = createReadonlyMap(
    materials.map((material) => [material.materialRef.id, material] as const),
  );
  const diagnostics = Object.freeze(materials.flatMap((material) => material.diagnostics));
  const authoritativeBlockedMaterialRefIds = Object.freeze(
    materials
      .filter((material) => material.blocksAuthoritativeExport)
      .map((material) => material.materialRef.id),
  );

  return Object.freeze({
    requestedRoutes,
    canonicalRoutes,
    routeEvidence,
    materialRefIds: Object.freeze(materials.map((material) => material.materialRef.id)),
    materials,
    byMaterialRefId,
    diagnostics,
    authoritativeBlockedMaterialRefIds,
    hasAuthoritativeBlockers: authoritativeBlockedMaterialRefIds.length > 0,
  });
}

// ---------------------------------------------------------------------------
// Material diagnostic builders (M3a)
// ---------------------------------------------------------------------------

/** Map from material runtime diagnostic code to canonical composition code. */
const MATERIAL_RUNTIME_TO_COMPOSITION_CODE: Readonly<
  Record<MaterialRuntimeDiagnosticCode, CompositionDiagnosticCode>
> = Object.freeze({
  [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STATUS_INVALID]:
    COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STATUS_INVALID,
  [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.MISSING_PROVENANCE]:
    COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_MISSING_PROVENANCE,
  [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.LIVE_ONLY]:
    COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_LIVE_ONLY,
  [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STALE]:
    COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STALE,
  [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.FAILED]:
    COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_FAILED,
  [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.WEAKER_PROVENANCE]:
    COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_WEAKER_PROVENANCE,
  [MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE]:
    COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_ROUTE_INCOMPATIBLE,
});

/**
 * Translate a {@link MaterialRuntimeDiagnosticCode} to its canonical
 * {@link CompositionDiagnosticCode}.
 */
export function toCompositionDiagnosticCode(
  code: MaterialRuntimeDiagnosticCode,
): CompositionDiagnosticCode {
  return MATERIAL_RUNTIME_TO_COMPOSITION_CODE[code];
}

/**
 * Build a structured {@link ProvenanceGap} for a material entry whose
 * provenance posture is `unattributed`.  Derives gap details exclusively
 * from producer metadata and determinism — no bake/capture/agent/process
 * inspection.
 */
function buildProvenanceGapForEntry(
  entry: HostMaterialRuntimeEntry,
): ProvenanceGap | undefined {
  if (entry.provenancePosture !== 'unattributed') {
    return undefined;
  }

  const provenance = entry.materialRef.provenance;
  const producerExtensionId = entry.materialRef.producerExtensionId;
  const producerVersion = entry.materialRef.producerVersion;

  if (!hasProvenance(provenance)) {
    if (!producerExtensionId && !producerVersion) {
      return {
        reason: 'no-producer-metadata',
        message:
          'No provenance record or producer metadata; material origin cannot be verified.',
      };
    }
    return {
      reason: 'empty',
      message:
        'Provenance record is empty; material origin derived from producer metadata only.',
    };
  }

  return {
    reason: 'absent',
    message:
      'No provenance record available; material origin cannot be independently verified.',
  };
}

/**
 * Build material detail for a diagnostic from a host material entry.
 */
function buildMaterialDiagnosticDetail(
  entry: HostMaterialRuntimeEntry,
  routeScope?: RenderRoute,
): CompositionDiagnosticDetail {
  const nextAction = routeScope
    ? entry.routeScopes.find((scope) => scope.route === routeScope)?.nextAction
    : entry.nextAction;
  const provenanceGap = buildProvenanceGapForEntry(entry);
  const detail: CompositionDiagnosticDetail = {
    materialRefId: entry.materialRef.id,
    materialStatus: entry.status.state,
    detailPhase: entry.status.detail?.phase,
    detailQuality: entry.status.detail?.quality,
    provenance: entry.materialRef.provenance,
    nextAction: nextAction ? { ...nextAction } : undefined,
    ...(provenanceGap ? { provenanceGap: provenanceGap.message } : {}),
  };

  if (routeScope) {
    detail.routeScope = routeScope;
  }

  return detail;
}

/**
 * Produce canonical {@link ExtensionDiagnostic} payloads for every
 * diagnostic code present in a material's matrix row.
 *
 * Route-scoped diagnostics receive a route-specific `routeScope` detail
 * field; bare-material diagnostics omit `routeScope`.
 */
export function buildMaterialDiagnosticsForEntry(
  entry: HostMaterialRuntimeEntry,
  routeScope?: RenderRoute,
): readonly ExtensionDiagnostic[] {
  const detail = buildMaterialDiagnosticDetail(entry, routeScope);
  const codes = routeScope
    ? entry.matrix.diagnosticCodes.filter(
        (code) => code === MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE,
      )
    : entry.matrix.diagnosticCodes.filter(
        (code) => code !== MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE,
      );

  return Object.freeze(
    codes.map((code) =>
      buildCompositionDiagnostic(
        toCompositionDiagnosticCode(code),
        materialDiagnosticMessage(code, entry, routeScope),
        detail,
      ),
    ),
  );
}

/**
 * Material diagnostic message templates keyed by runtime diagnostic code.
 */
function materialDiagnosticMessage(
  code: MaterialRuntimeDiagnosticCode,
  entry: HostMaterialRuntimeEntry,
  routeScope?: RenderRoute,
): string {
  const id = entry.materialRef.id;

  switch (code) {
    case MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STATUS_INVALID:
      return `Material "${id}" has an invalid status/detail combination.`;
    case MATERIAL_RUNTIME_DIAGNOSTIC_CODE.MISSING_PROVENANCE:
      return `Material "${id}" is missing provenance evidence.`;
    case MATERIAL_RUNTIME_DIAGNOSTIC_CODE.LIVE_ONLY:
      return `Material "${id}" exists only as live runtime data with no baked asset.`;
    case MATERIAL_RUNTIME_DIAGNOSTIC_CODE.STALE:
      return `Material "${id}" is stale and must be re-materialized.`;
    case MATERIAL_RUNTIME_DIAGNOSTIC_CODE.FAILED:
      return `Materialization failed for "${id}".`;
    case MATERIAL_RUNTIME_DIAGNOSTIC_CODE.WEAKER_PROVENANCE:
      return `Material "${id}" carries weaker provenance than required.`;
    case MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE:
      return routeScope
        ? `Material "${id}" is incompatible with route "${routeScope}".`
        : `Material "${id}" is incompatible with the selected render route.`;
    default: {
      const _exhaustive: never = code;
      return `Material "${id}" has an unrecognised diagnostic: ${_exhaustive}`;
    }
  }
}

/**
 * Collect all material diagnostics from a {@link HostMaterialRuntimeProjection}.
 *
 * Bare-material diagnostics are emitted once per material for each
 * material-level diagnostic code.  Route-scoped diagnostics are emitted
 * for every route × route-sensitive material combination.
 *
 * Provenance diagnostics are emitted for materials whose provenance
 * posture is `unattributed` — this is a declarative data-only check
 * that derives origin from producer metadata and determinism without
 * bake/capture/agent/process execution behavior.
 */
export function collectMaterialRuntimeDiagnostics(
  projection: HostMaterialRuntimeProjection,
): readonly ExtensionDiagnostic[] {
  const diagnostics: ExtensionDiagnostic[] = [];

  for (const material of projection.materials) {
    // Bare-material diagnostics (non-route-scoped codes)
    for (const code of material.matrix.diagnosticCodes) {
      diagnostics.push(
        buildCompositionDiagnostic(
          toCompositionDiagnosticCode(code),
          materialDiagnosticMessage(code, material),
          buildMaterialDiagnosticDetail(material),
        ),
      );
    }

    // Provenance diagnostics for materials with unattributed provenance
    if (material.provenancePosture === 'unattributed') {
      diagnostics.push(
        buildCompositionDiagnostic(
          COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_MISSING_PROVENANCE,
          materialDiagnosticMessage(
            MATERIAL_RUNTIME_DIAGNOSTIC_CODE.MISSING_PROVENANCE,
            material,
          ),
          buildMaterialDiagnosticDetail(material),
        ),
      );
    }

    // Route-scoped diagnostics for route-incompatible materials
    if (
      material.matrix.diagnosticCodes.includes(
        MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE,
      )
    ) {
      for (const routeScope of material.routeScopes.filter((scope) => scope.fit === 'blocked')) {
        diagnostics.push(
          buildCompositionDiagnostic(
            COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_ROUTE_INCOMPATIBLE,
            materialDiagnosticMessage(
              MATERIAL_RUNTIME_DIAGNOSTIC_CODE.ROUTE_INCOMPATIBLE,
              material,
              routeScope.route,
            ),
            buildMaterialDiagnosticDetail(material, routeScope.route),
          ),
        );
      }
    }
  }

  return Object.freeze(diagnostics);
}

function attachBoundaryNextAction(
  entry: HostMaterialRuntimeEntry,
  routeScope?: RenderRoute,
): Record<string, unknown> | undefined {
  const nextAction = routeScope
    ? entry.routeScopes.find((scope) => scope.route === routeScope)?.nextAction ?? entry.nextAction
    : entry.nextAction;
  return nextAction ? { ...nextAction } : undefined;
}

function buildAttachBoundaryRepairAction(
  action: Record<string, unknown> | undefined,
  materialRefId: string,
  context: MaterialAttachDiagnosticContext,
): Record<string, unknown> | undefined {
  if (!action) {
    return undefined;
  }

  return {
    ...action,
    materialRefId,
    ...(context.clipId ? { clipId: context.clipId } : {}),
    ...(context.ownerKind ? { ownerKind: context.ownerKind } : {}),
    ...(context.ownerId ? { ownerId: context.ownerId } : {}),
    ...(context.materialSlot ? { materialSlot: context.materialSlot } : {}),
  };
}

function buildMaterialAttachDiagnosticDetail(
  materialRefId: string,
  context: MaterialAttachDiagnosticContext,
  entry?: HostMaterialRuntimeEntry,
  routeScope?: RenderRoute,
  fallbackAction?: Record<string, unknown>,
): CompositionDiagnosticDetail {
  const baseDetail = entry
    ? buildMaterialDiagnosticDetail(entry, routeScope)
    : { materialRefId } satisfies CompositionDiagnosticDetail;
  const nextAction = baseDetail.nextAction
    ? { ...baseDetail.nextAction }
    : fallbackAction;
  const repairAction = buildAttachBoundaryRepairAction(nextAction, materialRefId, context);

  return {
    ...baseDetail,
    materialRefId,
    ...(context.clipId ? { clipId: context.clipId } : {}),
    ...(context.scope ? { scope: context.scope } : {}),
    ...(context.ownerKind ? { ownerKind: context.ownerKind } : {}),
    ...(context.ownerId ? { ownerId: context.ownerId } : {}),
    ...(context.materialSlot ? { materialSlot: context.materialSlot } : {}),
    ...(context.refKey ? { refKey: context.refKey } : {}),
    ...(context.resolverState
      ? {
          refState: context.resolverState,
          resolverState: context.resolverState,
        }
      : {}),
    ...(context.extensionId ? { extensionId: context.extensionId } : {}),
    ...(context.contributionId ? { contributionId: context.contributionId } : {}),
    ...(context.packageState ? { packageState: context.packageState } : {}),
    ...(nextAction ? { nextAction } : {}),
    ...(repairAction ? { repairAction } : {}),
  };
}

function selectMaterialAttachDiagnostic(
  entry: HostMaterialRuntimeEntry,
): Readonly<{
  code: CompositionDiagnosticCode;
  routeScope?: RenderRoute;
}> | undefined {
  if (entry.matrix.validity === 'invalid') {
    return { code: COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STATUS_INVALID };
  }

  if (entry.status.detail?.quality === 'route-incompatible') {
    return {
      code: COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_ROUTE_INCOMPATIBLE,
      routeScope: entry.routeScopes.find((scope) => scope.fit === 'blocked')?.route,
    };
  }

  switch (entry.status.state) {
    case 'missing':
    case 'pending':
      return { code: COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_NOT_RESOLVED };
    case 'stale':
      return { code: COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STALE };
    case 'failed':
      return { code: COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_FAILED };
    case 'resolved':
      return undefined;
    default: {
      const _exhaustive: never = entry.status.state;
      return _exhaustive;
    }
  }
}

function materialAttachDiagnosticMessage(
  code: CompositionDiagnosticCode,
  materialRefId: string,
  context: MaterialAttachDiagnosticContext,
  entry?: HostMaterialRuntimeEntry,
  routeScope?: RenderRoute,
): string {
  const ownerLabel = context.ownerKind && context.ownerId
    ? `${context.ownerKind} "${context.ownerId}"`
    : 'owner';
  const slotLabel = context.materialSlot
    ? `slot "${context.materialSlot}" on ${ownerLabel}`
    : `owner ${ownerLabel}`;

  switch (code) {
    case COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_NOT_RESOLVED:
      return entry
        ? `Material "${materialRefId}" cannot attach to ${slotLabel} while it is ${entry.status.state}.`
        : `Material "${materialRefId}" could not be resolved for ${slotLabel} attach preview.`;
    case COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STALE:
      return `Material "${materialRefId}" is stale and cannot attach to ${slotLabel} until it is re-materialized.`;
    case COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_FAILED:
      return `Material "${materialRefId}" failed materialization and cannot attach to ${slotLabel}.`;
    case COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_ROUTE_INCOMPATIBLE:
      return routeScope
        ? `Material "${materialRefId}" is incompatible with route "${routeScope}" for ${slotLabel}.`
        : `Material "${materialRefId}" is route-incompatible for ${slotLabel}.`;
    case COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_STATUS_INVALID:
      return `Material "${materialRefId}" has an invalid runtime state for ${slotLabel} attach preview.`;
    default:
      return `Material "${materialRefId}" cannot attach to ${slotLabel}.`;
  }
}

function firstAttachBlockingDiagnostic(
  entry: HostMaterialRuntimeEntry,
  context: MaterialAttachDiagnosticContext = {},
): ExtensionDiagnostic | undefined {
  const selected = selectMaterialAttachDiagnostic(entry);
  if (selected) {
    const fallbackAction = selected.code === COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_NOT_RESOLVED
      ? { kind: 'materialize' }
      : undefined;
    return buildCompositionDiagnostic(
      selected.code,
      materialAttachDiagnosticMessage(
        selected.code,
        entry.materialRef.id,
        context,
        entry,
        selected.routeScope,
      ),
      buildMaterialAttachDiagnosticDetail(
        entry.materialRef.id,
        context,
        entry,
        selected.routeScope,
        fallbackAction,
      ),
    );
  }

  return undefined;
}

export function resolveMaterialAttachEntry(
  projection: HostMaterialRuntimeProjection | undefined,
  materialRefId: string,
  context: MaterialAttachDiagnosticContext = {},
): ResolveMaterialAttachEntryResult {
  const normalizedMaterialRefId = materialRefId.trim();
  const entry = normalizedMaterialRefId.length > 0
    ? projection?.byMaterialRefId.get(normalizedMaterialRefId)
    : undefined;

  if (!entry) {
    const fallbackAction = { kind: 'materialize' };
    return Object.freeze({
      ok: false,
      diagnostic: buildCompositionDiagnostic(
        COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_NOT_RESOLVED,
        materialAttachDiagnosticMessage(
          COMPOSITION_DIAGNOSTIC_CODE.MATERIAL_NOT_RESOLVED,
          normalizedMaterialRefId,
          context,
        ),
        buildMaterialAttachDiagnosticDetail(
          normalizedMaterialRefId,
          context,
          undefined,
          undefined,
          fallbackAction,
        ),
      ),
    });
  }

  const attachDiagnostic = firstAttachBlockingDiagnostic(entry, context);
  if (attachDiagnostic) {
    return Object.freeze({
      ok: false,
      diagnostic: attachDiagnostic,
    });
  }

  return Object.freeze({
    ok: true,
    entry,
  });
}
