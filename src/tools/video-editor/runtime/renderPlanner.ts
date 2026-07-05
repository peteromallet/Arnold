import {
  contributionRefKey,
  type CapabilityFinding,
  type CapabilityRequirement,
  type CompositionGraph,
  type DeterminismStatus,
  type ProcessStatus,
  type RenderBlocker,
  type RenderMaterialStatus as SdkRenderMaterialStatus,
  type RenderMaterialStatusState,
  type RenderBlockerReason,
  type RenderMaterialRef,
  type RenderRoute,
  RENDER_ROUTES,
  type TimelineSnapshot,
  type TimelineShaderSummary,
  getCapabilityRequirements,
} from '@reigh/editor-sdk';
import { shaderMissingMaterializerBlockerMessage } from '@/sdk/video/rendering/capabilities.ts';
import {
  COMPOSITION_DIAGNOSTIC_CODE,
  isBlockingTargetCompositionDiagnosticCode,
  isBlockingM5CompositionDiagnosticCode,
  m5CompositionBlockerReason,
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';
import {
  projectHostMaterialRuntime,
  type HostMaterialRuntimeEntry,
  type HostMaterialRuntimeProjection,
} from '@/tools/video-editor/runtime/composition/materialRuntime.ts';
import {
  projectProcessResultContracts,
  type ProcessResultAttachRecord,
} from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import {
  projectShaderRefs,
  validateShaderComposition,
} from '@/tools/video-editor/runtime/composition/shaderValidation.ts';
import type {
  ContributionIndex,
  ExtensionRuntime,
  VideoEditorOutputFormatDescriptor,
  VideoEditorPlannerBlockerDescriptor,
  VideoEditorPlannerNextActionDescriptor,
  VideoEditorProcessDescriptor,
  VideoEditorProcessRequirementDescriptor,
  VideoEditorRouteRequirementDescriptor,
  VideoEditorShaderDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';

export interface RenderPlannerRequest {
  readonly route?: RenderRoute;
  readonly routes?: readonly RenderRoute[];
  readonly outputFormatId?: string;
  readonly requiredCapabilities?: readonly string[];
}

export type RenderPlannerMaterialState = RenderMaterialStatusState;

export type RenderPlannerMaterialStatus = SdkRenderMaterialStatus;

export interface RenderPlannerInput {
  readonly snapshot?: TimelineSnapshot | null;
  readonly requirements?: readonly CapabilityRequirement[];
  readonly compositionGraph?: CompositionGraph;
  readonly extensionRuntime?: Pick<
    ExtensionRuntime,
    'outputFormats' | 'processes' | 'shaders' | 'contributionIndex' | 'compositionGraph'
  >;
  readonly outputFormats?: readonly VideoEditorOutputFormatDescriptor[];
  readonly processes?: readonly VideoEditorProcessDescriptor[];
  readonly shaders?: readonly VideoEditorShaderDescriptor[];
  readonly processStatuses?: readonly ProcessStatus[];
  readonly processResultAttachRecords?: readonly ProcessResultAttachRecord[];
  readonly materialRefs?: readonly RenderMaterialRef[];
  readonly materialStatuses?: readonly RenderPlannerMaterialStatus[];
  readonly materialRuntime?: HostMaterialRuntimeProjection;
  readonly request?: RenderPlannerRequest;
  readonly diagnostics?: readonly CapabilityFinding[];
}

export interface RenderRouteSummary {
  readonly route: RenderRoute;
  readonly blockerCount: number;
  readonly findingCount: number;
  readonly blocked: boolean;
}

export interface RenderRoutePlan extends RenderRouteSummary {
  readonly requiredCapabilities: readonly string[];
  readonly determinism: DeterminismStatus;
  readonly blockers: readonly RenderBlocker[];
  readonly diagnostics: readonly CapabilityFinding[];
  readonly outputFormatIds: readonly string[];
  readonly processRequirements: readonly VideoEditorProcessRequirementDescriptor[];
  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
}

export interface RenderPlannerGuardCompatibility {
  readonly diagnostics: readonly CapabilityFinding[];
  readonly findings: readonly CapabilityFinding[];
  readonly blockers: readonly RenderBlocker[];
  readonly unknownClipTypes: readonly string[];
  readonly unknownEffects: readonly string[];
  readonly unknownTransitions: readonly string[];
  readonly inactiveExtensionIds: {
    readonly effectIds: ReadonlySet<string>;
    readonly transitionIds: ReadonlySet<string>;
    readonly clipTypeIds: ReadonlySet<string>;
  };
  readonly hasBlockingErrors: boolean;
}

export interface RenderPlannerResult {
  readonly guard: RenderPlannerGuardCompatibility;
  readonly findings: readonly CapabilityFinding[];
  readonly blockers: readonly RenderBlocker[];
  readonly routes: readonly RenderRouteSummary[];
  readonly routePlans: readonly RenderRoutePlan[];
  readonly diagnostics: readonly CapabilityFinding[];
  readonly nextActions: readonly VideoEditorPlannerNextActionDescriptor[];
  readonly canBrowserExport: boolean;
  readonly canWorkerExport: boolean;
}

interface PlanAccumulator {
  findings: CapabilityFinding[];
  blockers: RenderBlocker[];
  nextActions: VideoEditorPlannerNextActionDescriptor[];
  routeCapabilities: Map<RenderRoute, Set<string>>;
  routeOutputFormatIds: Map<RenderRoute, Set<string>>;
  routeProcessRequirements: Map<RenderRoute, VideoEditorProcessRequirementDescriptor[]>;
  routeDeterminism: Map<RenderRoute, DeterminismStatus[]>;
}

interface ShaderCompositionDiagnosis {
  readonly snapshot: TimelineSnapshot | null | undefined;
  readonly shaders: readonly TimelineShaderSummary[] | undefined;
  readonly findings: CapabilityFinding[];
}

type ProcessOperationDescriptor = VideoEditorProcessDescriptor['operations'][number];

interface OutputFormatProcessDependencyDescriptor {
  readonly scope: 'process-requirement' | 'route-requirement';
  readonly outputFormat: VideoEditorOutputFormatDescriptor;
  readonly route: RenderRoute;
  readonly processId: string;
  readonly operationId?: string;
  readonly requiredCapabilities: readonly string[];
  readonly determinism?: DeterminismStatus;
  readonly unavailableMessage?: string;
}

const EMPTY_IDS = Object.freeze({
  effectIds: Object.freeze(new Set<string>()),
  transitionIds: Object.freeze(new Set<string>()),
  clipTypeIds: Object.freeze(new Set<string>()),
});

const GRAPH_PLANNER_ROUTES = [
  'browser-export',
  'worker-export',
] as const satisfies readonly RenderRoute[];

const LEGACY_GRAPH_COMPATIBILITY_WARNING_ID = 'planner.compositionGraph.legacy-shader-ref-compatibility';

const PROCESS_NON_DEGRADED_CAPABILITY_IDS = new Set([
  'process-health/non-degraded',
  'process-health:non-degraded',
]);

const TRUSTED_LOCAL_PROCESS_PROTOCOLS = new Set<VideoEditorProcessDescriptor['protocol']>([
  'stdio-jsonrpc',
]);

const DETERMINISM_RANK: Record<DeterminismStatus, number> = {
  deterministic: 0,
  'preview-only': 1,
  'live-unbaked': 2,
  'process-dependent': 3,
  unknown: 4,
};

function createAccumulator(): PlanAccumulator {
  return {
    findings: [],
    blockers: [],
    nextActions: [],
    routeCapabilities: new Map(),
    routeOutputFormatIds: new Map(),
    routeProcessRequirements: new Map(),
    routeDeterminism: new Map(),
  };
}

function addRouteValue<T>(map: Map<RenderRoute, T[]>, route: RenderRoute, value: T): void {
  const values = map.get(route);
  if (values) {
    values.push(value);
    return;
  }
  map.set(route, [value]);
}

function addRouteSetValue(map: Map<RenderRoute, Set<string>>, route: RenderRoute, value: string): void {
  const values = map.get(route);
  if (values) {
    values.add(value);
    return;
  }
  map.set(route, new Set([value]));
}

function freezeFinding(finding: CapabilityFinding): CapabilityFinding {
  return Object.freeze({
    ...finding,
    ...(finding.detail ? { detail: Object.freeze({ ...finding.detail }) } : {}),
  });
}

function freezeBlocker(blocker: RenderBlocker): RenderBlocker {
  return Object.freeze({
    ...blocker,
    ...(blocker.detail ? { detail: Object.freeze({ ...blocker.detail }) } : {}),
  });
}

function dedupeById<T extends { readonly id: string }>(items: readonly T[]): T[] {
  const seen = new Set<string>();
  const deduped: T[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    deduped.push(item);
  }
  return deduped;
}

function sortedFindings(findings: readonly CapabilityFinding[]): readonly CapabilityFinding[] {
  return Object.freeze(
    dedupeById(findings.map(freezeFinding)).sort((a, b) => a.id.localeCompare(b.id)),
  );
}

function sortedBlockers(blockers: readonly RenderBlocker[]): readonly RenderBlocker[] {
  return Object.freeze(
    dedupeById(blockers.map(freezeBlocker)).sort((a, b) => a.id.localeCompare(b.id)),
  );
}

function blockerForFinding(finding: CapabilityFinding): RenderBlocker | undefined {
  if (finding.severity !== 'error' || !finding.route || !finding.reason) return undefined;
  return {
    ...finding,
    severity: 'error',
    route: finding.route,
    reason: finding.reason,
  };
}

function routeFitFinding(requirement: CapabilityRequirement): CapabilityFinding | undefined {
  const routeFit = requirement.routeFit;
  if (!routeFit && !requirement.blocking) return undefined;
  if (routeFit?.fit === 'supported' && !requirement.blocking) return undefined;

  const reason = routeFit?.reason ?? blockerReasonForDeterminism(requirement.determinism);
  const severity = requirement.blocking || routeFit?.fit === 'blocked' ? 'error' : 'warning';
  return {
    id: `${requirement.id}.${requirement.route}.${reason}`,
    severity,
    route: requirement.route,
    reason,
    message: routeFit?.message
      ?? `Capability requirement "${requirement.id}" is ${routeFit?.fit ?? 'blocked'} for ${requirement.route}.`,
    extensionId: requirement.sourceRef.extensionId,
    contributionId: requirement.sourceRef.contributionId,
    detail: {
      source: 'capability-requirement',
      sourceRef: requirement.sourceRef,
      requiredCapabilities: [...requirement.requiredCapabilities].sort(),
      determinism: requirement.determinism,
      routeFit: routeFit ? { ...routeFit } : undefined,
    },
  };
}

function blockerReasonForDeterminism(determinism: DeterminismStatus): RenderBlockerReason {
  switch (determinism) {
    case 'preview-only':
    case 'live-unbaked':
    case 'process-dependent':
    case 'unknown':
      return determinism;
    case 'deterministic':
      return 'unknown';
  }
}

function collectRequirement(acc: PlanAccumulator, requirement: CapabilityRequirement): void {
  addRouteValue(acc.routeDeterminism, requirement.route, requirement.determinism);
  for (const capability of requirement.requiredCapabilities) {
    addRouteSetValue(acc.routeCapabilities, requirement.route, capability);
  }

  for (const finding of requirement.findings ?? []) {
    acc.findings.push(finding);
    const blocker = blockerForFinding(finding);
    if (blocker) acc.blockers.push(blocker);
  }

  const routeFit = routeFitFinding(requirement);
  if (!routeFit) return;
  acc.findings.push(routeFit);
  const blocker = blockerForFinding(routeFit);
  if (blocker) acc.blockers.push(blocker);
}

function shaderDescriptorKey(extensionId: string | undefined, contributionId: string | undefined): string {
  return `${extensionId ?? ''}:${contributionId ?? ''}`;
}

function projectSnapshotShaderRefs(
  snapshot: TimelineSnapshot | null | undefined,
  contributionIndex: ContributionIndex | undefined,
  compositionGraph?: CompositionGraph,
): TimelineSnapshot | null | undefined {
  if (!snapshot?.shaders) {
    return snapshot;
  }

  const shaders = projectShaderRefs(snapshot.shaders, contributionIndex, compositionGraph);
  if (shaders === snapshot.shaders) {
    return snapshot;
  }

  return {
    ...snapshot,
    shaders: shaders && shaders.length > 0 ? shaders : undefined,
  };
}

function stripSnapshotShaders(
  snapshot: TimelineSnapshot | null | undefined,
): TimelineSnapshot | null | undefined {
  if (!snapshot?.shaders) {
    return snapshot;
  }

  return {
    ...snapshot,
    shaders: undefined,
  };
}

function plannerCompositionGraph(input: RenderPlannerInput): CompositionGraph | undefined {
  return input.compositionGraph ?? input.extensionRuntime?.compositionGraph;
}

function shaderRefKey(
  shader: Pick<TimelineShaderSummary, 'extensionId' | 'contributionId'>,
): string {
  return contributionRefKey({
    kind: 'shader',
    extensionId: shader.extensionId,
    contributionId: shader.contributionId,
  });
}

function shaderScopeNodeId(shader: Pick<TimelineShaderSummary, 'scope' | 'clipId'>): string {
  return shader.scope === 'clip'
    ? `clip:${shader.clipId ?? 'unknown'}`
    : 'timeline-postprocess';
}

function compositionDiagnosticReason(code: string): RenderBlockerReason {
  switch (code) {
    case COMPOSITION_DIAGNOSTIC_CODE.MISSING_REF:
    case COMPOSITION_DIAGNOSTIC_CODE.UNKNOWN_TARGET_REF:
      return 'missing-contribution';
    case COMPOSITION_DIAGNOSTIC_CODE.DISABLED_REF:
    case COMPOSITION_DIAGNOSTIC_CODE.INACTIVE_RESERVED_REF:
    case COMPOSITION_DIAGNOSTIC_CODE.UNSUPPORTED_RESERVED_TARGET:
      return 'inactive-extension';
    default: {
      // Delegate M5-specific blocker reasons
      if (isBlockingM5CompositionDiagnosticCode(code)) {
        return m5CompositionBlockerReason(code as Parameters<typeof m5CompositionBlockerReason>[0]) as RenderBlockerReason;
      }
      return 'unknown';
    }
  }
}

function graphDiagnosticFindings(
  compositionGraph: CompositionGraph | undefined,
): CapabilityFinding[] {
  if (!compositionGraph || compositionGraph.diagnostics.length === 0) {
    return [];
  }

  const findings: CapabilityFinding[] = [];
  compositionGraph.diagnostics.forEach((diagnostic, diagnosticIndex) => {
    const severity = isBlockingTargetCompositionDiagnosticCode(diagnostic.code) || isBlockingM5CompositionDiagnosticCode(diagnostic.code)
      ? 'error'
      : diagnostic.severity === 'info'
        ? 'info'
        : diagnostic.severity;
    for (const route of GRAPH_PLANNER_ROUTES) {
      findings.push({
        id: `${diagnostic.code}.${route}.${diagnosticIndex}`,
        severity,
        route,
        reason: compositionDiagnosticReason(diagnostic.code),
        message: diagnostic.message,
        extensionId: diagnostic.extensionId
          ?? (diagnostic.detail?.extensionId as string | undefined),
        contributionId: diagnostic.contributionId
          ?? (diagnostic.detail?.contributionId as string | undefined),
        detail: {
          source: 'composition-graph',
          code: diagnostic.code,
          ...(diagnostic.detail ?? {}),
        },
      });
    }
  });

  return findings;
}

function graphShaderMaterializerRequirements(
  shaders: readonly TimelineShaderSummary[] | undefined,
  compositionGraph: CompositionGraph | undefined,
): CapabilityRequirement[] {
  if (!compositionGraph || !shaders?.length) {
    return [];
  }

  const refStateByKey = new Map(
    compositionGraph.referenceStates.map((entry) => [entry.refKey, entry.state]),
  );
  const requirements: CapabilityRequirement[] = [];
  let shaderOrdinal = 0;
  for (const shader of shaders) {
    if (shader.enabled === false) {
      continue;
    }

    const refState = refStateByKey.get(shaderRefKey(shader));
    if (refState !== 'resolved') {
      continue;
    }

    const sourceRef: CapabilityRequirement['sourceRef'] = {
      source: 'extension',
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
    };

    for (const route of GRAPH_PLANNER_ROUTES) {
      requirements.push({
        id: `graph.shader.${shaderOrdinal}.${route}`,
        sourceRef,
        route,
        requiredCapabilities: ['render-material', 'shader-materializer'],
        determinism: 'preview-only',
        blocking: true,
        routeFit: {
          route,
          fit: 'blocked',
          reason: 'missing-material',
          message: shaderMissingMaterializerBlockerMessage(
            shader.shaderId,
            shader.scope,
            shader.clipId,
          ),
        },
      });
    }
    shaderOrdinal += 1;
  }

  return requirements;
}

function legacyGraphCompatibilityWarning(
  snapshot: TimelineSnapshot | null | undefined,
  requirements: readonly CapabilityRequirement[] | undefined,
  compositionGraph: CompositionGraph | undefined,
): CapabilityFinding | undefined {
  if (compositionGraph) {
    return undefined;
  }

  const hasLegacyShaderFacts = Boolean(snapshot?.shaders?.some((shader) => shader.enabled !== false))
    || Boolean(requirements?.some(isShaderMaterializerRequirement));
  if (!hasLegacyShaderFacts) {
    return undefined;
  }

  return {
    id: LEGACY_GRAPH_COMPATIBILITY_WARNING_ID,
    severity: 'warning',
    message:
      'CompositionGraph was not provided; planner shader/ref decisions are using legacy compatibility inputs and are not authoritative for M1b.',
    detail: {
      source: 'composition-graph-compatibility',
      compatibilityMode: 'legacy-shader-ref',
    },
  };
}

function createShaderDescriptorMap(
  descriptors: readonly VideoEditorShaderDescriptor[],
): ReadonlyMap<string, VideoEditorShaderDescriptor> {
  return new Map(descriptors.map((descriptor) => [
    shaderDescriptorKey(descriptor.extensionId, descriptor.id),
    descriptor,
  ]));
}

function createProcessDescriptorMap(
  descriptors: readonly VideoEditorProcessDescriptor[],
): ReadonlyMap<string, VideoEditorProcessDescriptor> {
  return new Map(descriptors.map((descriptor) => [descriptor.processId, descriptor]));
}

function isShaderMaterializerRequirement(requirement: CapabilityRequirement): boolean {
  return requirement.sourceRef.source === 'extension'
    && requirement.requiredCapabilities.includes('shader-materializer')
    && requirement.requiredCapabilities.includes('render-material');
}

function processOperationSupportsMaterializerRoute(
  process: VideoEditorProcessDescriptor | undefined,
  operationId: string | undefined,
  route: RenderRoute,
): boolean {
  if (!process) return false;
  return process.operations.some((operation) => {
    if (operationId && operation.id !== operationId) return false;
    if (!operation.routes?.includes(route)) return false;
    return !operation.outputKinds || operation.outputKinds.includes('material');
  });
}

function shaderMaterializerSupportsRoute(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  processById: ReadonlyMap<string, VideoEditorProcessDescriptor>,
): boolean {
  const materializer = descriptor.materializer;
  if (!materializer) return false;
  if (materializer.routes?.includes(requirement.route)) return true;
  if (!materializer.processId) return false;
  return processOperationSupportsMaterializerRoute(
    processById.get(materializer.processId),
    materializer.operationId,
    requirement.route,
  );
}

function shaderMaterializationMessage(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
): string {
  if (descriptor.materializer?.unavailableMessage) return descriptor.materializer.unavailableMessage;
  if (descriptor.materializer?.processId) {
    return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
      `run process "${descriptor.materializer.processId}" to produce RenderMaterial.`;
  }
  return `Shader "${descriptor.shaderId}" has a materializer route for ${requirement.route}; ` +
    'materialize it to produce RenderMaterial.';
}

function shaderMaterializationAction(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  message: string,
): VideoEditorPlannerNextActionDescriptor {
  return {
    kind: 'materialize',
    label: `Materialize shader ${descriptor.shaderId}`,
    route: requirement.route,
    processId: descriptor.materializer?.processId,
    operationId: descriptor.materializer?.operationId,
    message,
    detail: {
      specificKind: 'resolve-blocker',
    },
  };
}

function shaderMaterializerFinding(
  descriptor: VideoEditorShaderDescriptor,
  requirement: CapabilityRequirement,
  action: VideoEditorPlannerNextActionDescriptor,
  processStatus: ProcessStatus | undefined,
): CapabilityFinding {
  return {
    id: `${requirement.id}.${requirement.route}.shader-materializer.discovered`,
    severity: 'info',
    route: requirement.route,
    message: `Shader materializer route discovered for "${descriptor.shaderId}" on ${requirement.route}.`,
    extensionId: descriptor.extensionId,
    contributionId: descriptor.id,
    detail: {
      source: 'shader-materializer',
      shaderId: descriptor.shaderId,
      processId: descriptor.materializer?.processId,
      operationId: descriptor.materializer?.operationId,
      processState: processStatus?.state ?? 'unknown',
      materializationState: processStatus?.state === 'busy' ? 'in-progress' : 'pending',
      nextAction: action,
    },
  };
}

function collectShaderMaterializerRequirement(
  acc: PlanAccumulator,
  requirement: CapabilityRequirement,
  descriptor: VideoEditorShaderDescriptor,
  processStatusById: ReadonlyMap<string, ProcessStatus>,
): void {
  const processStatus = descriptor.materializer?.processId
    ? processStatusById.get(descriptor.materializer.processId)
    : undefined;
  const message = shaderMaterializationMessage(descriptor, requirement);
  const action = shaderMaterializationAction(descriptor, requirement, message);

  collectRequirement(acc, {
    ...requirement,
    determinism: 'process-dependent',
    blocking: true,
    routeFit: {
      route: requirement.route,
      fit: 'supported',
      reason: 'process-dependent',
      message,
    },
    findings: [
      ...(requirement.findings ?? []),
      shaderMaterializerFinding(descriptor, requirement, action, processStatus),
    ],
  });
  acc.nextActions.push(action);
}

function shaderCompositionScopeLabel(shader: TimelineShaderSummary): string {
  return shader.scope === 'clip' ? `clip:${shader.clipId ?? 'unknown'}` : 'postprocess';
}

function diagnoseSnapshotShaderComposition(
  snapshot: TimelineSnapshot | null | undefined,
  contributionIndex: ContributionIndex | undefined,
  compositionGraph?: CompositionGraph,
): ShaderCompositionDiagnosis {
  if (compositionGraph) {
    const validation = validateShaderComposition(undefined, compositionGraph);
    const graphShaders = validation.shaders && validation.shaders.length > 0
      ? validation.shaders
      : undefined;
    const graphSnapshot = snapshot
      ? {
          ...snapshot,
          shaders: graphShaders,
        }
      : snapshot;

    if (!graphShaders || graphShaders.length === 0) {
      return {
        snapshot: graphSnapshot,
        shaders: graphShaders,
        findings: graphDiagnosticFindings(compositionGraph),
      };
    }

    const findings = graphDiagnosticFindings(compositionGraph);
    const refStateByKey = new Map(
      compositionGraph.referenceStates.map((entry) => [entry.refKey, entry.state]),
    );

    for (const occupied of validation.occupied) {
      const shader = occupied.incoming;
      const refKey = shaderRefKey(shader);
      const refState = refStateByKey.get(refKey);
      for (const route of GRAPH_PLANNER_ROUTES) {
        findings.push({
          id: `${COMPOSITION_DIAGNOSTIC_CODE.SCOPE_OCCUPIED}.${route}.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}`,
          severity: 'error',
          route,
          reason: 'unknown',
          message: occupied.message,
          extensionId: shader.extensionId,
          contributionId: shader.contributionId,
          detail: {
            source: 'composition-graph',
            code: COMPOSITION_DIAGNOSTIC_CODE.SCOPE_OCCUPIED,
            nodeId: shaderScopeNodeId(shader),
            refKey,
            refState,
            scope: occupied.scope,
            extensionId: shader.extensionId,
            contributionId: shader.contributionId,
            shaderId: shader.shaderId,
            clipId: occupied.clipId,
            existingShaderId: occupied.existing.shaderId,
            incomingShaderId: occupied.incoming.shaderId,
          },
        });
      }
    }

    const updatedGraphSnapshot = graphSnapshot
      ? {
          ...graphSnapshot,
          shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
        }
      : graphSnapshot;

    return {
      snapshot: updatedGraphSnapshot,
      shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
      findings,
    };
  }

  const projectedSnapshot = projectSnapshotShaderRefs(snapshot, contributionIndex);
  if (!projectedSnapshot?.shaders || projectedSnapshot.shaders.length === 0) {
    return { snapshot: projectedSnapshot, shaders: projectedSnapshot?.shaders, findings: [] };
  }

  const validation = validateShaderComposition(projectedSnapshot.shaders);
  if (validation.occupied.length === 0) {
    return { snapshot: projectedSnapshot, shaders: validation.shaders, findings: [] };
  }

  const findings: CapabilityFinding[] = [];
  for (const occupied of validation.occupied) {
    const shader = occupied.incoming;
    for (const route of ['browser-export', 'worker-export'] as const satisfies readonly RenderRoute[]) {
      findings.push({
        id: `planner.shaderComposition.${shaderCompositionScopeLabel(shader)}.${shader.shaderId}.${route}.scope-occupied`,
        severity: 'error',
        route,
        reason: 'unknown',
        message: occupied.message,
        extensionId: shader.extensionId,
        contributionId: shader.contributionId,
        detail: {
          source: 'shader-composition-limit',
          scope: occupied.scope,
          clipId: occupied.clipId,
          existingShaderId: occupied.existing.shaderId,
          incomingShaderId: occupied.incoming.shaderId,
        },
      });
    }
  }

  return {
    snapshot: {
      ...projectedSnapshot,
      shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
    },
    shaders: validation.shaders && validation.shaders.length > 0 ? validation.shaders : undefined,
    findings,
  };
}

function sortedRoutes(routes: readonly RenderRoute[]): readonly RenderRoute[] {
  const requested = new Set(routes);
  return Object.freeze(RENDER_ROUTES.filter((route) => requested.has(route)));
}

function requestedRoutes(request: RenderPlannerRequest | undefined): readonly RenderRoute[] {
  if (!request) return Object.freeze([]);
  if (request.routes && request.routes.length > 0) return sortedRoutes(request.routes);
  if (request.route) return Object.freeze([request.route]);
  return Object.freeze([]);
}

function collectRequestCapabilities(acc: PlanAccumulator, request: RenderPlannerRequest | undefined): void {
  if (!request?.requiredCapabilities || request.requiredCapabilities.length === 0) return;
  const routes = requestedRoutes(request);
  const targetRoutes = routes.length > 0 ? routes : RENDER_ROUTES;

  for (const route of targetRoutes) {
    for (const capability of request.requiredCapabilities) {
      addRouteSetValue(acc.routeCapabilities, route, capability);
    }
  }
}

function descriptorBlockerToFinding(
  blocker: VideoEditorPlannerBlockerDescriptor,
  fallbackRoute: RenderRoute,
  source: 'output-format' | 'process',
): CapabilityFinding {
  return {
    id: blocker.id,
    severity: 'error',
    route: blocker.route ?? fallbackRoute,
    reason: blocker.reason,
    message: blocker.message,
    extensionId: blocker.extensionId,
    contributionId: blocker.contributionId,
    detail: {
      source,
      nextAction: blocker.nextAction,
    },
  };
}

function collectDescriptorBlocker(
  acc: PlanAccumulator,
  blocker: VideoEditorPlannerBlockerDescriptor,
  fallbackRoute: RenderRoute,
  source: 'output-format' | 'process',
): void {
  const finding = descriptorBlockerToFinding(blocker, fallbackRoute, source);
  acc.findings.push(finding);
  const routeBlocker = blockerForFinding(finding);
  if (routeBlocker) acc.blockers.push(routeBlocker);
  if (blocker.nextAction) acc.nextActions.push(blocker.nextAction);
}

function findProcessOperation(
  process: VideoEditorProcessDescriptor | undefined,
  operationId: string | undefined,
): ProcessOperationDescriptor | undefined {
  if (!process || !operationId) {
    return undefined;
  }
  return process.operations.find((operation) => operation.id === operationId);
}

function matchingProcessOperations(
  process: VideoEditorProcessDescriptor | undefined,
  operationId: string | undefined,
  route: RenderRoute,
): readonly ProcessOperationDescriptor[] {
  if (!process) {
    return [];
  }
  if (operationId) {
    const operation = findProcessOperation(process, operationId);
    return operation ? [operation] : [];
  }
  return process.operations.filter((operation) => operation.routes?.includes(route));
}

function routeScopedProcessOperationId(
  process: VideoEditorProcessDescriptor | undefined,
  route: RenderRoute,
): string | undefined {
  if (!process) return undefined;
  const operationIds = [...new Set(
    matchingProcessOperations(process, undefined, route).map((operation) => operation.id),
  )].sort();
  return operationIds.length === 1 ? operationIds[0] : undefined;
}

function processLifecycleRouteScopes(
  process: VideoEditorProcessDescriptor,
): readonly { route: RenderRoute; operationId?: string }[] {
  const routes = new Set<RenderRoute>(process.availableRoutes);
  for (const operation of process.operations) {
    for (const route of operation.routes ?? []) {
      routes.add(route);
    }
  }

  return Object.freeze(sortedRoutes([...routes]).map((route) => {
    const operationId = routeScopedProcessOperationId(process, route);
    return Object.freeze({
      route,
      ...(operationId ? { operationId } : {}),
    });
  }));
}

function hasNonDegradedHealthRequirement(requiredCapabilities: readonly string[] | undefined): boolean {
  return Boolean(requiredCapabilities?.some((capability) => PROCESS_NON_DEGRADED_CAPABILITY_IDS.has(capability)));
}

function processRequiresNonDegradedHealth(
  dependency: OutputFormatProcessDependencyDescriptor,
  operations: readonly ProcessOperationDescriptor[],
): boolean {
  return hasNonDegradedHealthRequirement(dependency.requiredCapabilities)
    || operations.some((operation) => hasNonDegradedHealthRequirement(operation.requiredCapabilities));
}

function processDependencyBaseId(dependency: OutputFormatProcessDependencyDescriptor): string {
  const operationSuffix = dependency.operationId ? `.${dependency.operationId}` : '';
  const scopeSuffix = dependency.scope === 'route-requirement' ? '.route' : '';
  return `planner.outputFormat.${dependency.outputFormat.extensionId}.${dependency.outputFormat.id}.${dependency.route}.${dependency.processId}${operationSuffix}${scopeSuffix}`;
}

function processStatusReason(
  status: ProcessStatus | undefined,
  requireNonDegradedHealth: boolean,
): RenderBlockerReason {
  switch (status?.state) {
    case 'not-installed':
      return 'process-not-installed';
    case 'failed':
      return 'process-failed';
    case 'degraded':
      return 'process-degraded';
    case 'ready':
      return requireNonDegradedHealth ? 'process-degraded' : 'process-dependent';
    default:
      return 'process-dependent';
  }
}

function processStatusBlocks(
  status: ProcessStatus | undefined,
  requireNonDegradedHealth: boolean,
): boolean {
  if (!status) return true;
  if (status.state === 'ready') return false;
  if (status.state === 'degraded') return requireNonDegradedHealth;
  return true;
}

function processStatusWarns(
  status: ProcessStatus | undefined,
  requireNonDegradedHealth: boolean,
): boolean {
  return status?.state === 'degraded' && !requireNonDegradedHealth;
}

function processStatusDetail(status: ProcessStatus | undefined): Record<string, unknown> {
  return {
    processState: status?.state ?? 'unknown',
    lifecycleState: status?.state ?? 'unknown',
    ...(status?.blockingOperations?.length
      ? { blockingOperations: [...status.blockingOperations] }
      : {}),
    ...(status?.diagnostics?.length
      ? { diagnostics: status.diagnostics }
      : {}),
    ...(status?.state === 'busy' && status.operationId
      ? { activeOperationId: status.operationId }
      : {}),
    ...(status?.state === 'degraded' && status.healthCheck
      ? { healthCheck: status.healthCheck }
      : {}),
    ...(status?.state === 'failed'
      ? {
          ...(status.errorCode ? { errorCode: status.errorCode } : {}),
          ...(status.recoverable !== undefined ? { recoverable: status.recoverable } : {}),
        }
      : {}),
    ...(status?.state === 'not-installed' && status.installHint
      ? { installHint: status.installHint }
      : {}),
  };
}

function buildProcessDependencyFinding(
  dependency: OutputFormatProcessDependencyDescriptor,
  reason: RenderBlockerReason,
  severity: CapabilityFinding['severity'],
  message: string,
  requireNonDegradedHealth: boolean,
  process?: VideoEditorProcessDescriptor,
  status?: ProcessStatus,
  nextAction?: VideoEditorPlannerNextActionDescriptor,
): CapabilityFinding {
  const resolvedOperationId = dependency.operationId ?? routeScopedProcessOperationId(process, dependency.route);
  return {
    id: `${processDependencyBaseId(dependency)}.${reason}`,
    severity,
    route: dependency.route,
    reason,
    message,
    extensionId: dependency.outputFormat.extensionId,
    contributionId: dependency.outputFormat.id,
    processId: dependency.processId,
    ...(resolvedOperationId ? { operationId: resolvedOperationId } : {}),
    detail: {
      source: 'output-format',
      outputFormatId: dependency.outputFormat.id,
      outputLabel: dependency.outputFormat.label,
      processId: dependency.processId,
      ...(resolvedOperationId ? { operationId: resolvedOperationId } : {}),
      routeScope: dependency.route,
      requiredCapabilities: [...dependency.requiredCapabilities].sort(),
      ...(process ? { processProtocol: process.protocol } : {}),
      ...(dependency.determinism ? { determinism: dependency.determinism } : {}),
      requireNonDegradedHealth,
      ...processStatusDetail(status),
      ...(nextAction ? { nextAction } : {}),
    },
  };
}

function processMissingMessage(
  outputFormat: VideoEditorOutputFormatDescriptor,
  processId: string,
  route: RenderRoute,
): string {
  return `Output format "${outputFormat.label}" requires process "${processId}" for ${route}, ` +
    'but no registered process descriptor declares it.';
}

function processConfigurationMessage(
  outputFormat: VideoEditorOutputFormatDescriptor,
  process: VideoEditorProcessDescriptor,
  processId: string,
  operationId: string | undefined,
  route: RenderRoute,
): string {
  if (operationId) {
    const operation = findProcessOperation(process, operationId);
    if (!operation) {
      return `Output format "${outputFormat.label}" requires operation "${operationId}" on process "${processId}" for ${route}, ` +
        'but that operation is not declared.';
    }
    return `Output format "${outputFormat.label}" requires operation "${operationId}" on ${route}, ` +
      `but process "${processId}" does not declare that route for the operation.`;
  }
  return `Output format "${outputFormat.label}" requires process "${processId}" on ${route}, ` +
    'but the process does not declare that route.';
}

function processDependencyConfigurationFinding(
  dependency: OutputFormatProcessDependencyDescriptor,
  process: VideoEditorProcessDescriptor | undefined,
): CapabilityFinding | undefined {
  if (!process) {
    return buildProcessDependencyFinding(
      dependency,
      'missing-contribution',
      'error',
      processMissingMessage(dependency.outputFormat, dependency.processId, dependency.route),
      false,
      process,
    );
  }

  if (dependency.operationId) {
    const operation = findProcessOperation(process, dependency.operationId);
    if (!operation || !operation.routes?.includes(dependency.route)) {
      return buildProcessDependencyFinding(
        dependency,
        'process-configuration-error',
        'error',
        processConfigurationMessage(
          dependency.outputFormat,
          process,
          dependency.processId,
          dependency.operationId,
          dependency.route,
        ),
        false,
        process,
      );
    }
    return undefined;
  }

  if (!process.availableRoutes.includes(dependency.route)) {
    return buildProcessDependencyFinding(
      dependency,
      'process-configuration-error',
      'error',
      processConfigurationMessage(
        dependency.outputFormat,
        process,
        dependency.processId,
        undefined,
        dependency.route,
      ),
      false,
      process,
    );
  }

  return undefined;
}

function processStatusMessage(
  outputLabel: string,
  processId: string,
  route: RenderRoute,
  status?: ProcessStatus,
): string {
  if (!status) return `Output format "${outputLabel}" requires process "${processId}" before ${route} can run.`;
  if (status.message) return status.message;
  switch (status.state) {
    case 'not-installed':
      return `Process "${processId}" is not installed for ${route}.${status.installHint ? ` Hint: ${status.installHint}` : ''}`;
    case 'busy':
      return `Process "${processId}" is busy for ${route}${status.operationId ? ` (operation "${status.operationId}")` : ''}.`;
    case 'failed':
      return `Process "${processId}" has failed for ${route}.${status.errorCode ? ` Error: ${status.errorCode}.` : ''}`;
    case 'degraded':
      return `Process "${processId}" is degraded for ${route}.${status.healthCheck ? ` Health: ${status.healthCheck}.` : ''}`;
    default:
      return `Process "${processId}" is ${status.state} for ${route}.`;
  }
}

function buildStartProcessAction(
  process: VideoEditorProcessDescriptor,
  route: RenderRoute,
  message: string,
  operationId?: string,
): VideoEditorPlannerNextActionDescriptor {
  return {
    kind: 'start-process',
    label: `Start ${process.label}`,
    route,
    processId: process.processId,
    ...(operationId ? { operationId } : {}),
    message,
    detail: {
      specificKind: 'start-process',
    },
  };
}

function buildProcessDependencyStartAction(
  dependency: OutputFormatProcessDependencyDescriptor,
  process: VideoEditorProcessDescriptor | undefined,
  status: ProcessStatus | undefined,
  message: string,
): VideoEditorPlannerNextActionDescriptor | undefined {
  if (!process || status?.state !== 'stopped' || !TRUSTED_LOCAL_PROCESS_PROTOCOLS.has(process.protocol)) {
    return undefined;
  }

  return buildStartProcessAction(
    process,
    dependency.route,
    message,
    dependency.operationId ?? routeScopedProcessOperationId(process, dependency.route),
  );
}

function buildProcessDependencyStatusFinding(
  dependency: OutputFormatProcessDependencyDescriptor,
  process: VideoEditorProcessDescriptor | undefined,
  status: ProcessStatus | undefined,
): CapabilityFinding | undefined {
  const configurationFinding = processDependencyConfigurationFinding(dependency, process);
  if (configurationFinding) {
    return configurationFinding;
  }

  const operations = matchingProcessOperations(process, dependency.operationId, dependency.route);
  const requireNonDegradedHealth = processRequiresNonDegradedHealth(dependency, operations);
  if (processStatusWarns(status, requireNonDegradedHealth)) {
    return buildProcessDependencyFinding(
      dependency,
      processStatusReason(status, requireNonDegradedHealth),
      'warning',
      processStatusMessage(
        dependency.outputFormat.label,
        dependency.processId,
        dependency.route,
        status,
      ),
      requireNonDegradedHealth,
      process,
      status,
    );
  }
  if (!processStatusBlocks(status, requireNonDegradedHealth)) {
    return undefined;
  }

  const message = status
    ? processStatusMessage(
        dependency.outputFormat.label,
        dependency.processId,
        dependency.route,
        status,
      )
    : (dependency.unavailableMessage
      ?? processStatusMessage(
        dependency.outputFormat.label,
        dependency.processId,
        dependency.route,
        status,
      ));
  const nextAction = buildProcessDependencyStartAction(
    dependency,
    process,
    status,
    message,
  );

  return buildProcessDependencyFinding(
    dependency,
    processStatusReason(status, requireNonDegradedHealth),
    'error',
    message,
    requireNonDegradedHealth,
    process,
    status,
    nextAction,
  );
}

function routeRequirementDependency(
  outputFormat: VideoEditorOutputFormatDescriptor,
  routeRequirement: VideoEditorRouteRequirementDescriptor,
  route: RenderRoute,
): OutputFormatProcessDependencyDescriptor | undefined {
  if (!routeRequirement.processId && routeRequirement.requiredCapabilities.length === 0) return undefined;
  if (!routeRequirement.processId) return undefined;

  return {
    scope: 'route-requirement',
    outputFormat,
    route,
    processId: routeRequirement.processId,
    operationId: routeRequirement.operationId,
    requiredCapabilities: routeRequirement.requiredCapabilities,
    determinism: routeRequirement.determinism,
    unavailableMessage: routeRequirement.unavailableMessage,
  };
}

function processRequirementRoutes(
  outputFormat: VideoEditorOutputFormatDescriptor,
  requirement: VideoEditorProcessRequirementDescriptor,
  process: VideoEditorProcessDescriptor | undefined,
): readonly RenderRoute[] {
  if (process) {
    if (requirement.operationId) {
      const operation = findProcessOperation(process, requirement.operationId);
      if (operation?.routes?.length) {
        return sortedRoutes(operation.routes);
      }
    } else if (process.availableRoutes.length > 0) {
      return process.availableRoutes;
    }
  }

  const fallbackRoutes = outputFormat.routeRequirements
    .filter((routeRequirement) =>
      routeRequirement.processId === requirement.processId
      && routeRequirement.operationId === requirement.operationId)
    .flatMap((routeRequirement) => routeRequirement.routes);
  if (fallbackRoutes.length > 0) {
    return sortedRoutes(fallbackRoutes);
  }

  return outputFormat.availableRoutes.length > 0
    ? outputFormat.availableRoutes
    : RENDER_ROUTES;
}

function processRequirementDependency(
  outputFormat: VideoEditorOutputFormatDescriptor,
  requirement: VideoEditorProcessRequirementDescriptor,
  route: RenderRoute,
): OutputFormatProcessDependencyDescriptor {
  return {
    scope: 'process-requirement',
    outputFormat,
    route,
    processId: requirement.processId,
    operationId: requirement.operationId,
    requiredCapabilities: requirement.requiredCapabilities,
  };
}

function collectOutputFormat(
  acc: PlanAccumulator,
  outputFormat: VideoEditorOutputFormatDescriptor,
  processStatusById: ReadonlyMap<string, ProcessStatus>,
  processById: ReadonlyMap<string, VideoEditorProcessDescriptor>,
): void {
  const availableRoutes = outputFormat.availableRoutes.length > 0
    ? outputFormat.availableRoutes
    : (outputFormat.requiresRender ? (['sidecar-export'] as const) : ([] as const));

  for (const route of availableRoutes) {
    addRouteSetValue(acc.routeOutputFormatIds, route, outputFormat.id);
  }

  for (const requirement of outputFormat.capabilities?.capabilityRequirements ?? []) {
    collectRequirement(acc, requirement);
  }

  for (const routeRequirement of outputFormat.routeRequirements) {
    for (const route of routeRequirement.routes) {
      addRouteValue(acc.routeDeterminism, route, routeRequirement.determinism);
      for (const capability of routeRequirement.requiredCapabilities) {
        addRouteSetValue(acc.routeCapabilities, route, capability);
      }
      const dependency = routeRequirementDependency(outputFormat, routeRequirement, route);
      const status = routeRequirement.processId ? processStatusById.get(routeRequirement.processId) : undefined;
      const finding = dependency
        ? buildProcessDependencyStatusFinding(
            dependency,
            processById.get(dependency.processId),
            status,
          )
        : undefined;
      if (finding) {
        acc.findings.push(finding);
        const blocker = blockerForFinding(finding);
        if (blocker) acc.blockers.push(blocker);
        const nextAction = finding.detail?.nextAction as VideoEditorPlannerNextActionDescriptor | undefined;
        if (nextAction) acc.nextActions.push(nextAction);
      }
    }
  }

  for (const requirement of outputFormat.processRequirements) {
    const process = processById.get(requirement.processId);
    const routes = processRequirementRoutes(outputFormat, requirement, process);
    for (const route of routes) {
      addRouteValue(acc.routeProcessRequirements, route, requirement);
      const status = processStatusById.get(requirement.processId);
      const finding = buildProcessDependencyStatusFinding(
        processRequirementDependency(outputFormat, requirement, route),
        process,
        status,
      );
      if (finding) {
        acc.findings.push(finding);
        const blocker = blockerForFinding(finding);
        if (blocker) acc.blockers.push(blocker);
        const nextAction = finding.detail?.nextAction as VideoEditorPlannerNextActionDescriptor | undefined;
        if (nextAction) acc.nextActions.push(nextAction);
      }
    }
  }

  for (const blocker of outputFormat.blockers) {
    collectDescriptorBlocker(acc, blocker, availableRoutes[0] ?? 'sidecar-export', 'output-format');
  }
  acc.nextActions.push(...outputFormat.nextActions);
}

function collectRequestedOutputRouteSupport(
  acc: PlanAccumulator,
  outputFormat: VideoEditorOutputFormatDescriptor | undefined,
  request: RenderPlannerRequest | undefined,
): void {
  if (!outputFormat) return;
  const routes = requestedRoutes(request);
  if (routes.length === 0) return;

  const availableRoutes = outputFormat.availableRoutes.length > 0
    ? outputFormat.availableRoutes
    : (outputFormat.requiresRender ? ([] as const) : (['browser-export'] as const));
  const available = new Set(availableRoutes);

  for (const route of routes) {
    if (available.has(route)) continue;
    const blocker: RenderBlocker = {
      id: `planner.outputFormat.${outputFormat.extensionId}.${outputFormat.id}.${route}.route-unsupported`,
      severity: 'error',
      route,
      reason: 'route-unsupported',
      message: `Output format "${outputFormat.label}" is not available on ${route}.`,
      extensionId: outputFormat.extensionId,
      contributionId: outputFormat.id,
      detail: {
        source: 'render-request',
        outputFormatId: outputFormat.id,
        requestedRoute: route,
        availableRoutes: [...availableRoutes].sort(),
      },
    };
    acc.findings.push(blocker);
    acc.blockers.push(blocker);
  }
}

function collectProcess(
  acc: PlanAccumulator,
  process: VideoEditorProcessDescriptor,
  status: ProcessStatus | undefined,
): void {
  for (const route of process.availableRoutes) {
    addRouteSetValue(acc.routeCapabilities, route, process.processId);
  }
  for (const requirement of process.capabilities?.capabilityRequirements ?? []) {
    collectRequirement(acc, requirement);
  }
  for (const blocker of process.blockers) {
    collectDescriptorBlocker(acc, blocker, process.availableRoutes[0] ?? 'sidecar-export', 'process');
  }
  acc.nextActions.push(...process.nextActions);

  if (status?.state !== 'stopped' || !TRUSTED_LOCAL_PROCESS_PROTOCOLS.has(process.protocol)) {
    return;
  }

  for (const scope of processLifecycleRouteScopes(process)) {
    const message = status.message ?? `Process "${process.processId}" is stopped for ${scope.route}.`;
    const nextAction = buildStartProcessAction(process, scope.route, message, scope.operationId);
    acc.findings.push({
      id: `planner.process.${process.extensionId}.${process.id}.${scope.route}${scope.operationId ? `.${scope.operationId}` : ''}.stopped`,
      severity: 'info',
      route: scope.route,
      reason: 'process-dependent',
      message,
      extensionId: process.extensionId,
      contributionId: process.id,
      processId: process.processId,
      ...(scope.operationId ? { operationId: scope.operationId } : {}),
      detail: {
        source: 'process',
        processId: process.processId,
        ...(scope.operationId ? { operationId: scope.operationId } : {}),
        routeScope: scope.route,
        processProtocol: process.protocol,
        ...processStatusDetail(status),
        nextAction,
      },
    });
    acc.nextActions.push(nextAction);
  }
}

function createProcessStatusMap(statuses: readonly ProcessStatus[] | undefined): ReadonlyMap<string, ProcessStatus> {
  return new Map((statuses ?? []).map((status) => [status.processId, status]));
}

function materialActionLabel(
  material: HostMaterialRuntimeEntry,
  routeScope?: HostMaterialRuntimeEntry['routeScopes'][number],
): string {
  const kind = routeScope?.nextAction?.kind ?? material.nextAction?.kind;
  // Only annotate with route when the action comes from explicit route evidence,
  // not when falling back to the entry-level action in the absence of routes.
  const routeLabel = routeScope?.route && routeScope.nextAction
    ? ` for ${routeScope.route}`
    : '';
  switch (kind) {
    case 'bake':
      return `Bake ${material.materialRef.id}${routeLabel}`;
    case 'open-settings':
      return `Open settings for ${material.materialRef.id}${routeLabel}`;
    case 'select-route':
      return `Select route for ${material.materialRef.id}${routeLabel}`;
    case 'materialize':
    default:
      return `Materialize ${material.materialRef.id}${routeLabel}`;
  }
}

function materialPlannerMessage(material: HostMaterialRuntimeEntry): string {
  return material.status.message ?? `Material "${material.materialRef.id}" must be materialized before browser export.`;
}

function buildResolveBlockerAction(
  kind: VideoEditorPlannerNextActionDescriptor['kind'],
  label: string,
  message: string,
  route?: RenderRoute,
): VideoEditorPlannerNextActionDescriptor {
  return {
    kind,
    label,
    ...(route ? { route } : {}),
    message,
    detail: {
      specificKind: 'resolve-blocker',
    },
  };
}

function buildMaterialPlannerAction(
  material: HostMaterialRuntimeEntry,
  routeScope?: HostMaterialRuntimeEntry['routeScopes'][number],
): VideoEditorPlannerNextActionDescriptor | undefined {
  const action = routeScope?.nextAction ?? material.nextAction;
  if (!action) {
    return undefined;
  }

  return buildResolveBlockerAction(
    action.kind,
    materialActionLabel(material, routeScope),
    materialPlannerMessage(material),
    action.route,
  );
}

function plannerRequestedRoutes(
  request: RenderPlannerRequest | undefined,
): readonly RenderRoute[] {
  if (!request) {
    return Object.freeze([]);
  }

  return Object.freeze(
    Array.from(new Set([
      ...(request.routes ?? []),
      ...(request.route ? [request.route] : []),
    ])),
  );
}

function buildMaterialRuntimeProjection(
  input: RenderPlannerInput,
  outputFormats: readonly VideoEditorOutputFormatDescriptor[],
  processes: readonly VideoEditorProcessDescriptor[],
  shaders: readonly VideoEditorShaderDescriptor[],
): HostMaterialRuntimeProjection {
  if (input.materialRuntime) {
    return input.materialRuntime;
  }

  const requestedOutputFormat = input.request?.outputFormatId
    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
    : undefined;

  return projectHostMaterialRuntime({
    materialRefs: input.materialRefs,
    materialStatuses: input.materialStatuses,
    contributionIndex: input.extensionRuntime?.contributionIndex,
    shaders,
    processes,
    processStatuses: input.processStatuses,
    processResultAttachRecords: input.processResultAttachRecords,
    requestedRoutes: plannerRequestedRoutes(input.request),
    canonicalRoutes: requestedOutputFormat?.availableRoutes,
  });
}

function mergeProjectedProcessResultContracts(
  input: RenderPlannerInput,
): Pick<RenderPlannerInput, 'materialRefs' | 'materialStatuses'> {
  if (!input.processResultAttachRecords?.length) {
    return {
      materialRefs: input.materialRefs,
      materialStatuses: input.materialStatuses,
    };
  }

  const mergedMaterialRefs = new Map<string, RenderMaterialRef>();
  for (const materialRef of input.materialRefs ?? []) {
    mergedMaterialRefs.set(materialRef.id, materialRef);
  }

  const mergedMaterialStatuses = new Map<string, RenderPlannerMaterialStatus>();
  for (const materialStatus of input.materialStatuses ?? []) {
    mergedMaterialStatuses.set(materialStatus.materialRefId, materialStatus);
  }

  for (const record of input.processResultAttachRecords) {
    const projection = projectProcessResultContracts(record);
    for (const materialRef of projection.materialRefs) {
      mergedMaterialRefs.set(materialRef.id, materialRef);
    }
    for (const materialStatus of projection.materialStatuses) {
      mergedMaterialStatuses.set(materialStatus.materialRefId, materialStatus);
    }
  }

  return {
    materialRefs: mergedMaterialRefs.size > 0
      ? Object.freeze([...mergedMaterialRefs.values()])
      : undefined,
    materialStatuses: mergedMaterialStatuses.size > 0
      ? Object.freeze([...mergedMaterialStatuses.values()].sort(
        (left, right) => left.materialRefId.localeCompare(right.materialRefId),
      ))
      : undefined,
  };
}

function collectMaterialRef(
  acc: PlanAccumulator,
  material: HostMaterialRuntimeEntry,
): void {
  const materialRef = material.materialRef;

  // Add determinism for every route the material has evidence for, or
  // fall back to browser-export when no route evidence is available.
  const scopes = material.routeScopes.length > 0
    ? material.routeScopes
    : [{ route: 'browser-export' as RenderRoute, fit: 'blocked' as const, sensitivity: 'route-agnostic' as const, blocker: material.blocker }];

  for (const routeScope of scopes) {
    addRouteValue(acc.routeDeterminism, routeScope.route, materialRef.determinism);
  }

  if (materialRef.replacementPolicy !== 'materialize-on-export') return;

  // Emit route-scoped blockers and actions from the projection.
  for (const routeScope of scopes) {
    const routeBlocker = routeScope.blocker;
    if (!routeBlocker) continue;

    const reason = routeBlocker.reason;
    const message = materialPlannerMessage(material);
    const blocker: RenderBlocker = {
      id: `planner.material.${materialRef.id}.${routeScope.route}.${reason}`,
      severity: routeBlocker.severity,
      route: routeScope.route,
      reason,
      message,
      materialRefId: materialRef.id,
      extensionId: materialRef.producerExtensionId,
      detail: {
        source: 'material-ref',
        mediaKind: materialRef.mediaKind,
        locatorKind: materialRef.locator.kind,
        replacementPolicy: materialRef.replacementPolicy,
        determinism: materialRef.determinism,
        materialState: material.status.state,
        materialPhase: material.status.detail?.phase,
        materialQuality: material.status.detail?.quality,
        ...(material.descriptorFacts.process
          ? {
              materializerProcessId: material.descriptorFacts.process.processId,
              materializerSupportsMaterialOutput:
                material.descriptorFacts.process.supportsMaterialOutput,
            }
          : {}),
      },
    };
    acc.findings.push(blocker);
    acc.blockers.push(blocker);

    const nextAction = buildMaterialPlannerAction(material, routeScope);
    if (nextAction) {
      acc.nextActions.push(nextAction);
    }
  }
}

function collectRenderGroups(
  acc: PlanAccumulator,
  snapshot: TimelineSnapshot | null | undefined,
  materialProjection?: HostMaterialRuntimeProjection,
): void {
  for (const group of snapshot?.renderGroups ?? []) {
    for (const pass of group.passes ?? []) {
      if (!pass.required) continue;
      if (pass.status !== 'missing' && pass.status !== 'stale') continue;

      // Cross-reference with the material projection for status/detail enrichment.
      const projectedMaterial = pass.materialRefId
        ? materialProjection?.byMaterialRefId.get(pass.materialRefId)
        : undefined;

      const reason: RenderBlockerReason = pass.status === 'missing'
        ? 'missing-material'
        : 'materialization-failed';
      const message = `Render group "${group.id}" pass "${pass.passName}" is ${pass.status}.`;
      const blocker: RenderBlocker = {
        id: `planner.renderGroup.${group.id}.${pass.id}.browser-export.${reason}`,
        severity: 'error',
        route: 'browser-export',
        reason,
        message,
        materialRefId: pass.materialRefId,
        detail: {
          source: 'render-group',
          renderGroupId: group.id,
          passId: pass.id,
          passName: pass.passName,
          passStatus: pass.status,
          composable: pass.composable,
          required: pass.required,
          ...(projectedMaterial
            ? {
                materialState: projectedMaterial.status.state,
                materialPhase: projectedMaterial.status.detail?.phase,
                materialQuality: projectedMaterial.status.detail?.quality,
                ...(projectedMaterial.descriptorFacts.process
                  ? {
                      materializerProcessId:
                        projectedMaterial.descriptorFacts.process.processId,
                      materializerSupportsMaterialOutput:
                        projectedMaterial.descriptorFacts.process.supportsMaterialOutput,
                    }
                  : {}),
              }
            : {}),
        },
      };
      addRouteSetValue(acc.routeCapabilities, 'browser-export', 'render-groups');
      addRouteValue(acc.routeDeterminism, 'browser-export', 'process-dependent');
      acc.findings.push(blocker);
      acc.blockers.push(blocker);
      acc.nextActions.push(buildResolveBlockerAction(
        'materialize',
        `Materialize ${group.id}:${pass.passName}`,
        message,
        'browser-export',
      ));
    }
  }
}

function mostConservativeDeterminism(statuses: readonly DeterminismStatus[]): DeterminismStatus {
  if (statuses.length === 0) return 'deterministic';
  return [...statuses].sort((a, b) => DETERMINISM_RANK[b] - DETERMINISM_RANK[a])[0];
}

function sortedActions(
  actions: readonly VideoEditorPlannerNextActionDescriptor[],
): readonly VideoEditorPlannerNextActionDescriptor[] {
  const seen = new Set<string>();
  return Object.freeze([...actions]
    .sort((a, b) =>
      `${a.kind}:${a.route ?? ''}:${a.processId ?? ''}:${a.operationId ?? ''}:${a.label}`
        .localeCompare(`${b.kind}:${b.route ?? ''}:${b.processId ?? ''}:${b.operationId ?? ''}:${b.label}`))
    .filter((action) => {
      const key = `${action.kind}:${action.route ?? ''}:${action.processId ?? ''}:${action.operationId ?? ''}:${action.label}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((action) => Object.freeze({ ...action })));
}

function buildRoutePlan(
  route: RenderRoute,
  findings: readonly CapabilityFinding[],
  blockers: readonly RenderBlocker[],
  acc: PlanAccumulator,
): RenderRoutePlan {
  const routeBlockers = blockers.filter((blocker) => blocker.route === route);
  const routeFindings = findings.filter((finding) => !finding.route || finding.route === route);
  const requiredCapabilities = Object.freeze([...(acc.routeCapabilities.get(route) ?? new Set())].sort());
  const outputFormatIds = Object.freeze([...(acc.routeOutputFormatIds.get(route) ?? new Set())].sort());
  const processRequirements = Object.freeze([...(acc.routeProcessRequirements.get(route) ?? [])]
    .sort((a, b) =>
      `${a.processId}:${a.operationId ?? ''}:${a.requiredCapabilities.join(',')}`
        .localeCompare(`${b.processId}:${b.operationId ?? ''}:${b.requiredCapabilities.join(',')}`))
    .map((requirement) => Object.freeze({
      ...requirement,
      requiredCapabilities: Object.freeze([...requirement.requiredCapabilities].sort()),
    })));

  const actions = sortedActions(acc.nextActions.filter((action) => !action.route || action.route === route));
  return Object.freeze({
    route,
    blockerCount: routeBlockers.length,
    findingCount: routeFindings.length,
    blocked: routeBlockers.length > 0,
    requiredCapabilities,
    determinism: mostConservativeDeterminism(acc.routeDeterminism.get(route) ?? []),
    blockers: Object.freeze(routeBlockers),
    diagnostics: Object.freeze(routeFindings),
    outputFormatIds,
    processRequirements,
    nextActions: actions,
  });
}

function emptyGuard(
  findings: readonly CapabilityFinding[],
  blockers: readonly RenderBlocker[],
): RenderPlannerGuardCompatibility {
  return Object.freeze({
    diagnostics: findings,
    findings,
    blockers,
    unknownClipTypes: Object.freeze([]),
    unknownEffects: Object.freeze([]),
    unknownTransitions: Object.freeze([]),
    inactiveExtensionIds: EMPTY_IDS,
    hasBlockingErrors: blockers.length > 0,
  });
}

export function planRender(input: RenderPlannerInput): RenderPlannerResult {
  const acc = createAccumulator();
  const compositionGraph = plannerCompositionGraph(input);
  const nonShaderSnapshot = compositionGraph ? stripSnapshotShaders(input.snapshot) : input.snapshot;
  const shaderComposition = diagnoseSnapshotShaderComposition(
    input.snapshot,
    input.extensionRuntime?.contributionIndex,
    compositionGraph,
  );
  const requirements = compositionGraph
    ? [
        ...(input.requirements
          ?? (nonShaderSnapshot
            ? getCapabilityRequirements(nonShaderSnapshot)
            : [])),
        ...graphShaderMaterializerRequirements(shaderComposition.shaders, compositionGraph),
      ]
    : (input.requirements ?? (shaderComposition.snapshot
      ? getCapabilityRequirements(shaderComposition.snapshot)
      : []));
  const outputFormats = input.outputFormats ?? input.extensionRuntime?.outputFormats ?? [];
  const processes = input.processes ?? input.extensionRuntime?.processes ?? [];
  const shaders = input.shaders ?? input.extensionRuntime?.shaders ?? [];
  const processStatusById = createProcessStatusMap(input.processStatuses);
  const processById = createProcessDescriptorMap(processes);
  const shaderBySourceRef = createShaderDescriptorMap(shaders);
  const legacyCompatibilityWarning = legacyGraphCompatibilityWarning(
    input.snapshot,
    requirements,
    compositionGraph,
  );
  const projectedProcessResultContracts = mergeProjectedProcessResultContracts(input);
  const requestedOutputFormat = input.request?.outputFormatId
    ? outputFormats.find((format) => format.id === input.request?.outputFormatId)
    : undefined;
  const materialRuntime = buildMaterialRuntimeProjection(
    {
      ...input,
      ...projectedProcessResultContracts,
    },
    outputFormats,
    processes,
    shaders,
  );

  for (const requirement of requirements) {
    const shaderDescriptor = isShaderMaterializerRequirement(requirement)
      ? shaderBySourceRef.get(shaderDescriptorKey(
        requirement.sourceRef.extensionId,
        requirement.sourceRef.contributionId,
      ))
      : undefined;
    if (
      shaderDescriptor
      && shaderMaterializerSupportsRoute(shaderDescriptor, requirement, processById)
    ) {
      collectShaderMaterializerRequirement(acc, requirement, shaderDescriptor, processStatusById);
      continue;
    }
    collectRequirement(acc, requirement);
  }
  collectRequestCapabilities(acc, input.request);
  for (const outputFormat of outputFormats) {
    if (input.request?.outputFormatId && input.request.outputFormatId !== outputFormat.id) continue;
    collectOutputFormat(acc, outputFormat, processStatusById, processById);
  }
  collectRequestedOutputRouteSupport(acc, requestedOutputFormat, input.request);
  for (const process of processes) {
    collectProcess(acc, process, processStatusById.get(process.processId));
  }
  for (const material of materialRuntime.materials) {
    collectMaterialRef(acc, material);
  }
  collectRenderGroups(acc, input.snapshot, materialRuntime);
  acc.findings.push(...shaderComposition.findings);
  if (legacyCompatibilityWarning) {
    acc.findings.push(legacyCompatibilityWarning);
  }
  acc.findings.push(...(input.diagnostics ?? []));

  if (input.request?.outputFormatId && !outputFormats.some((format) => format.id === input.request?.outputFormatId)) {
    const blocker: RenderBlocker = {
      id: `planner.outputFormat.${input.request.outputFormatId}.missing`,
      severity: 'error',
      route: input.request.route ?? input.request.routes?.[0] ?? 'sidecar-export',
      reason: 'missing-contribution',
      message: `Output format "${input.request.outputFormatId}" is not registered.`,
      contributionId: input.request.outputFormatId,
      detail: {
        source: 'render-request',
        outputFormatId: input.request.outputFormatId,
      },
    };
    acc.findings.push(blocker);
    acc.blockers.push(blocker);
  }

  const findings = sortedFindings(acc.findings);
  const blockers = sortedBlockers([
    ...acc.blockers,
    ...findings.map(blockerForFinding).filter((blocker): blocker is RenderBlocker => Boolean(blocker)),
  ]);
  const routePlans = Object.freeze(RENDER_ROUTES.map((route) => buildRoutePlan(route, findings, blockers, acc)));
  const routes = Object.freeze(routePlans.map((routePlan) => Object.freeze({
    route: routePlan.route,
    blockerCount: routePlan.blockerCount,
    findingCount: routePlan.findingCount,
    blocked: routePlan.blocked,
  })));
  const browserRoute = routePlans.find((route) => route.route === 'browser-export');
  const workerRoute = routePlans.find((route) => route.route === 'worker-export');

  // Convert projection diagnostics into CapabilityFinding format for the
  // diagnostics field while keeping findings as the deduplicated planner set.
  const projectionFindings: CapabilityFinding[] = materialRuntime.diagnostics.map(
    (diag): CapabilityFinding => ({
      id: `planner.materialRuntime.${diag.code}`,
      severity: diag.severity === 'error' ? 'error' : 'warning',
      route: (diag.detail as Record<string, unknown> | undefined)?.routeScope as RenderRoute | undefined,
      message: diag.message,
      extensionId: diag.extensionId,
      contributionId: diag.contributionId,
      materialRefId: (diag.detail as Record<string, unknown> | undefined)?.materialRefId as string | undefined,
      detail: diag.detail as Record<string, unknown> | undefined,
    }),
  );

  return Object.freeze({
    guard: emptyGuard(findings, blockers),
    findings,
    blockers,
    routes,
    routePlans,
    diagnostics: [
      ...findings,
      ...projectionFindings,
    ],
    nextActions: sortedActions(acc.nextActions),
    canBrowserExport: !browserRoute?.blocked,
    canWorkerExport: !workerRoute?.blocked,
  });
}
